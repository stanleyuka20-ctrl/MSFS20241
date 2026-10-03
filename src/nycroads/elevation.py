"""Elevation sources, vertical datums and per-segment profiles.

Rules enforced here (see docs/02-technical-approach.md):

* Ground-level roads: bare-earth DEM, despiked + smoothed, anchored at junctions.
* Bridge decks: NEVER from the DEM under the deck. Heights come from explicit
  deck control points (survey / lidar bridge-deck class / engineering data),
  or, for short spans only, from interpolation between abutments that sit on
  land. Anything else is reported as blocked ("needs deck controls").
* All heights are converted to the simulator's height reference with an
  explicit, recorded method (geoid chain or in-sim calibration offset).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from .geo import lonlat_to_utm, utm_to_lonlat
from .profile import grade_issues, smooth_profile, stations

FT = 0.3048006096  # US survey foot (NYC DEM products are in US survey feet)

# Short bridges whose deck may be interpolated between land abutments.
MAX_ABUTMENT_INTERPOLATION_SPAN_M = 60.0


class DEM(Protocol):
    def sample(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray: ...  # metres, native datum


@dataclass
class FunctionDEM:
    """Analytic DEM for tests and synthetic fixtures."""
    fn: Callable[[np.ndarray, np.ndarray], np.ndarray]
    datum: str = "synthetic"

    def sample(self, lon, lat):
        return np.asarray(self.fn(np.asarray(lon, float), np.asarray(lat, float)), float)


class RasterDEM:
    """GeoTIFF DEM via rasterio (optional dependency: pip install .[dem])."""

    def __init__(self, path: Path, z_units: str = "m", datum: str = "NAVD88", band: int = 1):
        import rasterio
        from pyproj import Transformer

        self.ds = rasterio.open(path)
        self.band = band
        self.scale = FT if z_units in ("ftUS", "us-ft") else 0.3048 if z_units == "ft" else 1.0
        self.datum = datum
        self._tr = Transformer.from_crs("EPSG:4326", self.ds.crs, always_xy=True)
        self.nodata = self.ds.nodata

    def sample(self, lon, lat):
        xs, ys = self._tr.transform(np.atleast_1d(lon), np.atleast_1d(lat))
        vals = np.array([v[0] for v in self.ds.sample(zip(xs, ys), indexes=self.band)], float)
        if self.nodata is not None:
            vals[vals == self.nodata] = np.nan
        return vals * self.scale


# ----------------------------------------------------------------- vertical reference

@dataclass
class VerticalReference:
    """Converts native DEM heights (m) to simulator heights (m).

    method:
      * ``calibrated_offset`` – sim_h = native + offset, offset measured in-sim at
        control points (preferred: it matches what the simulator actually renders).
      * ``geoid_chain`` – pyproj transformation from ``source_crs`` to
        ``target_crs`` (needs PROJ geoid grids installed); the target geoid used
        by MSFS 2024 is NOT confirmed by this project -> UNVERIFIED.
    """
    method: str = "calibrated_offset"
    offset_m: float = 0.0
    control_points: list = field(default_factory=list)  # [{lon, lat, native_m, sim_m}]
    source_crs: str = "EPSG:4269+5703"   # NAD83 + NAVD88 height
    target_crs: str = "EPSG:4326+3855"   # WGS84 + EGM2008 height (assumption, verify)
    verified: bool = False

    @classmethod
    def load(cls, path: Path) -> "VerticalReference":
        d = json.loads(Path(path).read_text())
        return cls(**{k: v for k, v in d.items() if not k.startswith("_")})

    def to_sim(self, lon, lat, z_native):
        """Always returns a 1-D array."""
        z_native = np.atleast_1d(np.asarray(z_native, float))
        if self.method == "calibrated_offset":
            if len(self.control_points) >= 3:
                return z_native + self._idw_offset(np.atleast_1d(lon), np.atleast_1d(lat))
            return z_native + self.offset_m
        if self.method == "geoid_chain":
            from pyproj import Transformer
            t = Transformer.from_crs(self.source_crs, self.target_crs, always_xy=True)
            _, _, z = t.transform(np.atleast_1d(lon), np.atleast_1d(lat), np.atleast_1d(z_native),
                                  errcheck=True)
            return np.asarray(z)
        raise ValueError(self.method)

    def _idw_offset(self, lon, lat):
        cp = self.control_points
        X = np.array([lonlat_to_utm(c["lon"], c["lat"]) for c in cp])
        d_off = np.array([c["sim_m"] - c["native_m"] for c in cp])
        px, py = lonlat_to_utm(lon, lat)
        P = np.column_stack([px, py])
        dist = np.linalg.norm(P[:, None, :] - X[None, :, :], axis=2)
        w = 1.0 / np.maximum(dist, 1.0) ** 2
        return (w * d_off).sum(1) / w.sum(1)


# ----------------------------------------------------------------- deck controls

@dataclass
class DeckControl:
    lon: float
    lat: float
    z_sim_m: float      # already in simulator reference
    source: str         # e.g. "lidar-class17", "survey", "drawing:<ref>"


def load_deck_controls(path: Path, vref: "VerticalReference | None" = None) -> dict[str, list[DeckControl]]:
    """deck/crossing id -> controls. File format: see data/deck_controls.json.

    Controls with ``z_native_m`` are converted with ``vref`` (the current vertical
    reference); others are taken as already in simulator reference."""
    if not Path(path).exists():
        return {}
    raw = json.loads(Path(path).read_text())
    out = {}
    for key, entry in raw.items():
        if key.startswith("_"):
            continue
        cs = []
        for c in entry.get("controls", []):
            z = c["z_sim_m"]
            if vref is not None and c.get("z_native_m") is not None:
                z = float(vref.to_sim(c["lon"], c["lat"], c["z_native_m"])[0])
            cs.append(DeckControl(c["lon"], c["lat"], z, c.get("source", "")))
        out[key] = cs
    return out


# ----------------------------------------------------------------- profiles

@dataclass
class Profile:
    segment_id: str
    s: np.ndarray
    xy_utm: np.ndarray
    z_sim: np.ndarray
    source: str
    issues: list
    info: dict

    def end_heights(self):
        return float(self.z_sim[0]), float(self.z_sim[-1])


def _line_utm(coords):
    from shapely.geometry import LineString
    return LineString([lonlat_to_utm(lon, lat) for lon, lat in coords])


def junction_heights(inv, dem: DEM, vref: VerticalReference, radius_m: float = 3.0,
                     skip_nodes: set | None = None, lidar=None) -> dict[int, float]:
    """Sim-reference height of every *ground-level* junction node (median over a small disk).

    ``skip_nodes``: abutments of measured decks. A bare-earth DEM at an abutment
    often already shows the ground under the structure, so those heights come
    from the deck measurements instead."""
    out = {}
    skip_nodes = skip_nodes or set()
    for j in inv.junctions.values():
        if j.osm_node_id in skip_nodes:
            continue
        segs = [inv.segments[s] for s in j.segment_ids]
        if not any(not (s.bridge or s.tunnel) for s in segs):
            continue  # purely elevated / buried junctions are set by the deck stage
        x, y = lonlat_to_utm(j.lon, j.lat)
        if lidar is not None:
            zl = lidar.point_surface(x, y, radius_m)
            if zl is not None:
                out[j.osm_node_id] = float(vref.to_sim(j.lon, j.lat, zl)[0])
                continue
        ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        xs = np.concatenate([[x], x + radius_m * np.cos(ang)])
        ys = np.concatenate([[y], y + radius_m * np.sin(ang)])
        lon, lat = utm_to_lonlat(xs, ys)
        z = dem.sample(lon, lat)
        if np.all(np.isnan(z)):
            continue
        zn = float(np.nanmedian(z))
        if lidar is not None:
            from .lidarsurface import dem_is_continuous
            if not dem_is_continuous(lidar, x, y, zn):
                continue   # DEM shows ground under a structure here; leave the node to the profiles
        out[j.osm_node_id] = float(vref.to_sim(j.lon, j.lat, zn)[0])
    return out


ABUTMENT_DEM_MASK_M = 15.0


def ground_profile(seg, dem: DEM, vref: VerticalReference, node_h: dict[int, float],
                   measured_abutments: dict[int, float] | None = None, lidar=None) -> Profile:
    """Ground road profile from the DEM.

    ``measured_abutments``: node -> grade leaving the measured deck at that node
    (moving away from the deck). DEM samples within ABUTMENT_DEM_MASK_M of such a
    node are ignored and the profile continues the deck's grade there."""
    measured_abutments = measured_abutments or {}
    line = _line_utm(seg.coords)
    s, xy = stations(line)
    lon, lat = utm_to_lonlat(xy[:, 0], xy[:, 1])
    z_native = dem.sample(lon, lat)
    z = vref.to_sim(lon, lat, z_native)
    source = "dem+smoothing"
    lidar_info = {}
    if lidar is not None:
        from .lidarsurface import choose_surface
        g, dk = lidar.station_values(xy)
        g = np.where(np.isfinite(g), vref.to_sim(lon, lat, np.nan_to_num(g)), np.nan)
        dk = np.where(np.isfinite(dk), vref.to_sim(lon, lat, np.nan_to_num(dk)), np.nan)
        z, src = choose_surface(s, g, dk, z, (node_h.get(seg.from_node), node_h.get(seg.to_node)),
                                lidar.max_jump, lidar.ref_window)
        lidar_info = {k: int((src == k).sum()) for k in set(src)}
        source = "lidar+smoothing"
    anchors = {}
    if seg.from_node in node_h:
        anchors[0] = node_h[seg.from_node]
    if seg.to_node in node_h:
        anchors[len(s) - 1] = node_h[seg.to_node]
    mask = np.ones(len(s), bool)
    eg = {}
    if seg.from_node in measured_abutments:
        mask &= s > ABUTMENT_DEM_MASK_M
        eg["start"] = measured_abutments[seg.from_node]
    if seg.to_node in measured_abutments:
        mask &= s < s[-1] - ABUTMENT_DEM_MASK_M
        eg["end"] = -measured_abutments[seg.to_node]
    zs, info = smooth_profile(s, z, anchors, data_mask=mask, end_grades=eg)
    info.update({"stations_" + k: v for k, v in lidar_info.items()})
    return Profile(seg.id, s, xy, zs, source, grade_issues(s, zs, seg.highway), info)


def deck_profile(deck, inv, controls: list[DeckControl], node_h: dict[int, float],
                 approach_grade_out: dict[int, float] | None = None) -> tuple[dict, str | None]:
    """Profiles for every segment of a bridge deck.

    ``approach_grade_out``: abutment node -> grade of the ground approach measured
    moving away from the node; the deck continues that grade so the joint has no kink.
    Returns ({segment_id: Profile}, blocker_reason_or_None). The DEM is never sampled.
    """
    approach_grade_out = approach_grade_out or {}
    segs = [inv.segments[i] for i in deck.segment_ids]
    # abutment nodes: deck nodes shared with ground-level segments
    deck_nodes = {n for s in segs for n in (s.from_node, s.to_node)}
    abut = {n: node_h[n] for n in deck_nodes if n in node_h}
    long_span = deck.length_m > MAX_ABUTMENT_INTERPOLATION_SPAN_M or deck.crossing_id is not None
    if long_span and len(controls) < 2:
        return {}, f"needs deck controls (span {deck.length_m:.0f} m{', major crossing' if deck.crossing_id else ''})"
    if not controls and len(abut) < 2:
        return {}, "needs deck controls (fewer than two land abutments)"
    source = "deck_controls" if controls else "abutment_interpolation"
    bad = _inconsistent_controls(controls)
    if bad:
        return {}, f"inconsistent deck controls ({bad}); possible overhead structure in lidar"
    ctrl_xy = np.array([lonlat_to_utm(c.lon, c.lat) for c in controls]) if controls else np.zeros((0, 2))
    def solve(seg, extra: dict[int, float]):
        line = _line_utm(seg.coords)
        s, xy = stations(line)
        anchors = {}
        for node, idx in ((seg.from_node, 0), (seg.to_node, len(s) - 1)):
            if node in abut:
                anchors[idx] = abut[node]
            elif node in extra:
                anchors[idx] = extra[node]
        ctrl_idx = set()
        for c, cxy in zip(controls, ctrl_xy):
            d = np.hypot(xy[:, 0] - cxy[0], xy[:, 1] - cxy[1])
            k = int(np.argmin(d))
            if d[k] <= max(seg.width_m, 8.0):
                anchors[k] = c.z_sim_m
                ctrl_idx.add(k)
        if not anchors:
            return None
        # continue the approach grade across each abutment (sign flips: the
        # deck leaves the node in the opposite direction to the approach)
        eg = {}
        if seg.from_node in abut and seg.from_node in approach_grade_out:
            eg["start"] = -approach_grade_out[seg.from_node]
        if seg.to_node in abut and seg.to_node in approach_grade_out:
            eg["end"] = approach_grade_out[seg.to_node]
        mask = np.zeros(len(s), bool)   # ignore all terrain data on the deck
        if len(anchors) == 1 and not eg:
            zs, info = np.full(len(s), list(anchors.values())[0]), {"despiked": 0, "ignored": len(s)}
        elif len(anchors) >= 2 and controls:
            # Shape-preserving interpolation through the measured controls: no invented
            # humps or dips in gaps (a smoothing spline overshoots across long gaps).
            from scipy.interpolate import PchipInterpolator
            ks = sorted(anchors)
            f = PchipInterpolator(s[ks], [anchors[k] for k in ks], extrapolate=True)
            zs = f(s)
            # beyond the outermost controls continue linearly (no curvature extrapolation)
            for end, k0 in (("start", ks[0]), ("end", ks[-1])):
                g = eg.get(end, float(f.derivative()(s[k0])))
                rng = s < s[k0] if end == "start" else s > s[k0]
                zs[rng] = anchors[k0] + g * (s[rng] - s[k0])
            info = {"despiked": 0, "ignored": len(s)}
        else:
            zs, info = smooth_profile(s, np.full(len(s), np.nan), anchors, lam=50.0, data_mask=mask,
                                      end_grades=eg)
        # measurement coverage, counted from MEASURED controls only (not node heights)
        kc = sorted(ctrl_idx)
        if kc:
            gaps = np.diff(s[kc])
            info.update({"controls": len(kc), "max_control_gap_m": float(gaps.max()) if len(gaps) else 0.0,
                         "unmeasured_start_m": float(s[kc[0]]), "unmeasured_end_m": float(s[-1] - s[kc[-1]])})
        else:
            info.update({"controls": 0, "max_control_gap_m": float(s[-1]),
                         "unmeasured_start_m": float(s[-1]), "unmeasured_end_m": float(s[-1])})
        return Profile(seg.id, s, xy, zs, source, grade_issues(s, zs, seg.highway), info)

    # Pass 1: each segment from its own anchors. Pass 2: pin interior deck nodes
    # to the mean of the pass-1 end heights so adjoining deck segments meet exactly.
    first = {}
    for seg in segs:
        p = solve(seg, {})
        if p is not None:
            first[seg.id] = p
    node_vals: dict[int, list[float]] = {}
    for seg in segs:
        p = first.get(seg.id)
        if p is None:
            continue
        node_vals.setdefault(seg.from_node, []).append(float(p.z_sim[0]))
        node_vals.setdefault(seg.to_node, []).append(float(p.z_sim[-1]))
    interior = {n: float(np.mean(v)) for n, v in node_vals.items() if n not in abut}
    out = {}
    for seg in segs:
        p = solve(seg, interior)
        if p is None:
            return {}, f"segment {seg.id} on deck {deck.id} has no height anchor"
        if controls:
            reason = _coverage_blocker(seg, p.info, segs)
            if reason:
                return {}, reason + " - needs deck controls"
        out[seg.id] = p
    deck.elevation_source = source
    return out, None


MAX_CONTROL_GRADE = 0.10
MAX_UNMEASURED_DECK_END_M = 30.0      # at a free deck end (abutment / open end)
MAX_UNMEASURED_DECK_GAP_M = 120.0      # inside a deck, between measured controls
MAX_UNCONTROLLED_SEGMENT_M = 60.0      # deck segment with no measured control at all


def _coverage_blocker(seg, info: dict, deck_segs) -> str | None:
    """Reasons a measured deck may not be generated: long stretches with no measurement."""
    if info["controls"] == 0 and info["max_control_gap_m"] > MAX_UNCONTROLLED_SEGMENT_M:
        return f"deck segment {seg.id} ({info['max_control_gap_m']:.0f} m) has no lidar deck returns"
    if info["max_control_gap_m"] > MAX_UNMEASURED_DECK_GAP_M:
        return f"unmeasured gap of {info['max_control_gap_m']:.0f} m on deck segment {seg.id}"
    for key, node in (("unmeasured_start_m", seg.from_node), ("unmeasured_end_m", seg.to_node)):
        deck_degree = sum(node in (o.from_node, o.to_node) for o in deck_segs)
        if deck_degree == 1 and info[key] > MAX_UNMEASURED_DECK_END_M:
            return f"deck end unmeasured for {info[key]:.0f} m (segment {seg.id})"
    return None


def _inconsistent_controls(controls) -> str | None:
    """Neighbouring controls (< 40 m apart) implying > 10 % grade are not plausible deck data."""
    if len(controls) < 2:
        return None
    xy = np.array([lonlat_to_utm(c.lon, c.lat) for c in controls])
    z = np.array([c.z_sim_m for c in controls])
    for i in range(len(controls)):
        d = np.hypot(xy[:, 0] - xy[i, 0], xy[:, 1] - xy[i, 1])
        for j in np.where((d > 2.0) & (d < 40.0))[0]:
            if abs(z[j] - z[i]) / d[j] > MAX_CONTROL_GRADE:
                return f"{abs(z[j] - z[i]):.2f} m over {d[j]:.1f} m"
    return None


def deck_node_heights(profiles: dict, inv) -> dict[int, float]:
    """End heights of deck segments, for anchoring ground segments that join decks."""
    out = {}
    for sid, p in profiles.items():
        seg = inv.segments[sid]
        out.setdefault(seg.from_node, float(p.z_sim[0]))
        out.setdefault(seg.to_node, float(p.z_sim[-1]))
    return out
