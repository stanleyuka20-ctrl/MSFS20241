"""Derive bridge-deck control points from classified lidar.

Input: points (x, y, z, classification) in any projected CRS, typically read
from LAS/LAZ with laspy (``pip install laspy[lazrs]``). ASPRS class 17 is
"Bridge Deck". If a survey has no class 17, pass ``classes=(1,)`` etc. only
together with ``first_return_dsm=True`` provenance so the source is recorded as
the weaker DSM method (docs/05).

For each station along the deck centreline (every ``step_m``), the control
height is the median z of selected points within ``radius_m`` of the
centreline, after rejecting points more than ``reject_m`` from the local
median (lamp posts, vehicles, cables, overhead structures).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString

BRIDGE_DECK_CLASS = 17


def controls_from_points(centreline_lonlat, pts_xyz: np.ndarray, cls: np.ndarray, crs: str,
                         to_sim, step_m: float = 25.0, radius_m: float = 1.0, reject_m: float = 0.5,
                         classes=(BRIDGE_DECK_CLASS,), z_scale: float = 1.0, min_points: int = 5,
                         source: str = "lidar-class17", native_datum: str = "NAVD88") -> list[dict]:
    """Return deck control dicts ({lon, lat, z_sim_m, z_native_m, native_datum, source, n_points, spread_m}).

    ``z_native_m`` is authoritative: builds re-derive ``z_sim_m`` from it with the
    current vertical reference, so recalibrating never requires re-extraction."""
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    xs, ys = fwd.transform(*np.array(centreline_lonlat).T)
    line = LineString(zip(xs, ys))
    sel = np.isin(cls, classes)
    P = pts_xyz[sel]
    out = []
    for d in np.arange(0.0, line.length + 1e-6, step_m):
        p = line.interpolate(d)
        near = P[np.hypot(P[:, 0] - p.x, P[:, 1] - p.y) <= radius_m]
        if len(near) < min_points:
            continue
        z = near[:, 2] * z_scale
        med = np.median(z)
        z = z[np.abs(z - med) <= reject_m]
        if len(z) < min_points:
            continue
        lon, lat = inv.transform(p.x, p.y)
        z_native = float(np.median(z))
        z_sim = float(np.atleast_1d(to_sim(lon, lat, z_native))[0])
        out.append({"lon": round(lon, 8), "lat": round(lat, 8), "z_sim_m": round(z_sim, 3),
                    "z_native_m": round(z_native, 3), "native_datum": native_datum,
                    "source": source, "n_points": int(len(z)), "radius_m": radius_m,
                    "spread_m": round(float(np.percentile(z, 90) - np.percentile(z, 10)), 3)})
    return out


def read_las(path: Path):
    import laspy  # optional dependency

    las = laspy.read(str(path))
    crs = las.header.parse_crs()
    pts = np.column_stack([las.x, las.y, las.z])
    return pts, np.asarray(las.classification), (crs.to_string() if crs else None)


def update_controls_file(path: Path, key: str, controls: list[dict], extra: dict | None = None) -> None:
    data = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    data[key] = {**(extra or {}), "controls": controls,
                 "status": f"{len(controls)} controls from lidar" if controls else "NO lidar deck returns found: unresolved"}
    Path(path).write_text(json.dumps(data, indent=1))


def controls_with_fallback(centreline_lonlat, pts_xyz, cls, crs, to_sim, radii=(1.0, 2.5), min_controls=2,
                           gap_fill_classes=(1,), max_gap_dev_m: float = 1.0, **kw):
    """Class-17 controls (increasing search radius until >= min_controls), then gap filling.

    Gap filling: stations without a class-17 control that lie BETWEEN two class-17
    controls may take a control from ``gap_fill_classes`` (default class 1,
    unclassified - e.g. open steel-grid bascule leaves are often left unclassified)
    only if it is within ``max_gap_dev_m`` of the straight line between the two
    neighbouring class-17 controls. Such controls are labelled with their class.
    """
    out = []
    used_r = radii[0]
    for r in radii:
        out = controls_from_points(centreline_lonlat, pts_xyz, cls, crs, to_sim, radius_m=r, **kw)
        used_r = r
        if len(out) >= min_controls:
            break
    if len(out) < 2 or not gap_fill_classes:
        return out
    kw2 = dict(kw)
    src = kw2.pop("source", "lidar")
    extra = controls_from_points(centreline_lonlat, pts_xyz, cls, crs, to_sim, radius_m=used_r,
                                 classes=tuple(gap_fill_classes), source=src.replace("class17", "class1-gapfill"), **kw2)
    if not extra:
        return out
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = fwd.transform(*np.array(centreline_lonlat).T)
    line = LineString(zip(xs, ys))

    def station(c):
        from shapely.geometry import Point
        x, y = fwd.transform(c["lon"], c["lat"])
        return line.project(Point(x, y))

    have = sorted((station(c), c) for c in out)
    st17 = np.array([h[0] for h in have])
    z17 = np.array([h[1]["z_native_m"] for h in have])
    step = kw.get("step_m", 25.0)
    for c in extra:
        sc = station(c)
        if np.min(np.abs(st17 - sc)) < step / 2:
            continue                       # a class-17 control already covers this station
        if sc <= st17[0] or sc >= st17[-1]:
            continue                       # only fill gaps BETWEEN measured deck controls
        line_z = float(np.interp(sc, st17, z17))
        if abs(c["z_native_m"] - line_z) <= max_gap_dev_m:
            c["gap_fill"] = {"class": list(gap_fill_classes), "dev_from_class17_line_m": round(c["z_native_m"] - line_z, 3)}
            out.append(c)
    out.sort(key=station)
    return out
