"""Analysis of in-game driving telemetry (the evidence behind 'driven'/'verified').

A run is a CSV recorded by ``nycroads record`` (simbridge.py) while a human
drives the player vehicle. This module map-matches samples to inventory
segments, compares the vehicle height to the generated surface and detects:

* fall_through      vehicle well below the surface it is on
* floating          vehicle well above the surface while the sim says it is airborne
* level_jump        sudden change of height relative to the surface (snapping between decks)
* airborne          SIM ON GROUND false for longer than a bump would explain
* sudden_stop       deceleration typical of hitting an invisible obstacle (no brake input)
* recovery          explicit recovery/teleport event (never hidden; the segment
                    being driven when recovery was used fails)

CSV columns (SI units; the recorder converts):
  t, lat, lon, alt_m, on_ground, gs_mps, vs_mps, heading_deg, brake, event
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .geo import lonlat_to_utm

FALL_THROUGH_M = -0.6
FLOAT_M = 0.4
JUMP_M = 0.35
AIRBORNE_S = 0.6
SUDDEN_DECEL_MPS2 = 7.0
MATCH_RADIUS_M = 8.0
MIN_STATION_COVERAGE = 0.8


@dataclass
class Sample:
    t: float
    lat: float
    lon: float
    alt_m: float
    on_ground: bool
    gs_mps: float
    vs_mps: float
    heading_deg: float
    brake: float
    event: str = ""


def load_run(path: Path) -> list[Sample]:
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.append(Sample(
                t=float(r["t"]), lat=float(r["lat"]), lon=float(r["lon"]), alt_m=float(r["alt_m"]),
                on_ground=r["on_ground"] in ("1", "True", "true"), gs_mps=float(r["gs_mps"]),
                vs_mps=float(r["vs_mps"]), heading_deg=float(r["heading_deg"]),
                brake=float(r.get("brake") or 0), event=r.get("event", "") or ""))
    return out


@dataclass
class RunResult:
    run_id: str
    meta: dict
    ref_height_m: float
    segments: dict = field(default_factory=dict)   # sid -> {"forward"/"backward": "pass"|"fail"|..., "coverage": ...}
    incidents: list = field(default_factory=list)

    def to_json(self) -> dict:
        return {"run_id": self.run_id, "meta": self.meta, "ref_height_m": self.ref_height_m,
                "segments": self.segments, "incidents": self.incidents}


class _Matcher:
    def __init__(self, inv, profiles):
        self.inv = inv
        self.items = []
        for sid, p in profiles.items():
            for k in range(len(p.s)):
                self.items.append((sid, k))
        self.xy = np.array([profiles[sid].xy_utm[k] for sid, k in self.items]) if self.items else np.zeros((0, 2))
        self.profiles = profiles

    def match(self, x, y, prev_sid=None):
        if not len(self.xy):
            return None
        d = np.hypot(self.xy[:, 0] - x, self.xy[:, 1] - y)
        k = int(np.argmin(d))
        if d[k] > MATCH_RADIUS_M:
            return None
        # Prefer staying on the previous segment if it is almost as close (stacked decks!)
        sid, st = self.items[k]
        if prev_sid and prev_sid != sid:
            mask = np.array([i[0] == prev_sid for i in self.items])
            if mask.any():
                dk = np.where(mask, d, np.inf)
                k2 = int(np.argmin(dk))
                if dk[k2] <= d[k] + 1.5:
                    sid, st = self.items[k2]
        return sid, st

    def surface_and_bearing(self, sid, st):
        p = self.profiles[sid]
        a, b = max(st - 1, 0), min(st + 1, len(p.s) - 1)
        dx, dy = p.xy_utm[b] - p.xy_utm[a]
        bearing = math.degrees(math.atan2(dx, dy)) % 360  # clockwise from north
        return float(p.z_sim[st]), bearing


def _stacked_candidates(matcher, x, y, z_vehicle_surface):
    """With stacked decks, pick the profile whose height is closest to the vehicle."""
    d = np.hypot(matcher.xy[:, 0] - x, matcher.xy[:, 1] - y)
    near = np.where(d <= MATCH_RADIUS_M)[0]
    best = None
    for k in near:
        sid, st = matcher.items[k]
        z = matcher.profiles[sid].z_sim[st]
        score = abs(z - z_vehicle_surface) + 0.1 * d[k]
        if best is None or score < best[0]:
            best = (score, sid, st)
    return None if best is None else (best[1], best[2])


def analyse_run(samples: list[Sample], inv, profiles, run_id: str, meta: dict,
                ref_height_m: float | None = None) -> RunResult:
    """``ref_height_m``: vehicle reference point height above the surface when
    resting; measured with ``nycroads record --calibrate`` or estimated from the
    first 2 s of stationary samples on a matched segment."""
    m = _Matcher(inv, profiles)
    xs, ys = lonlat_to_utm(np.array([s.lon for s in samples]), np.array([s.lat for s in samples]))

    if ref_height_m is None:
        offs = []
        for s, x, y in zip(samples, xs, ys):
            if s.gs_mps < 0.2 and s.on_ground:
                mm = m.match(x, y)
                if mm:
                    offs.append(s.alt_m - m.surface_and_bearing(*mm)[0])
            if len(offs) >= 20:
                break
        if not offs:
            raise ValueError("cannot estimate vehicle reference height: start the run parked on a generated segment")
        ref_height_m = float(np.median(offs))

    res = RunResult(run_id, meta, ref_height_m)
    visits: dict[tuple[str, str], set] = {}
    failed: set[tuple[str, str]] = set()
    prev_sid, prev_dev, air_since, prev = None, None, None, None
    prev_xy = None
    res.meta.setdefault("reverse_distance_m", 0.0)
    for s, x, y in zip(samples, xs, ys):
        course = None
        if prev_xy is not None and math.hypot(x - prev_xy[0], y - prev_xy[1]) > 0.3:
            course = math.degrees(math.atan2(x - prev_xy[0], y - prev_xy[1])) % 360
            # facing opposite to the direction of motion => reversing
            if abs((s.heading_deg - course + 180) % 360 - 180) > 120:
                res.meta["reverse_distance_m"] += math.hypot(x - prev_xy[0], y - prev_xy[1])
            prev_xy = (x, y)
        elif prev_xy is None:
            prev_xy = (x, y)
        surf_guess = s.alt_m - ref_height_m
        mm = _stacked_candidates(m, x, y, surf_guess) or m.match(x, y, prev_sid)
        cur_key = None
        if mm:
            sid, st = mm
            z_surf, bearing = m.surface_and_bearing(sid, st)
            if course is not None and s.gs_mps > 0.5:
                # direction of TRAVEL relative to the OSM way (reversing counts by motion)
                diff = abs((course - bearing + 180) % 360 - 180)
                direction = "forward" if diff < 90 else "backward"
                cur_key = (sid, direction)
                visits.setdefault(cur_key, set()).add(st)
            dev = s.alt_m - ref_height_m - z_surf
            kind = None
            if dev < FALL_THROUGH_M:
                kind = "fall_through"
            elif dev > FLOAT_M and not s.on_ground:
                kind = "floating"
            elif prev_dev is not None and prev_sid == sid and abs(dev - prev_dev) > JUMP_M and s.gs_mps > 1:
                kind = "level_jump"
            if kind:
                res.incidents.append({"t": s.t, "type": kind, "segment": sid, "dev_m": round(dev, 3)})
                if cur_key:
                    failed.add(cur_key)
            prev_sid, prev_dev = sid, dev
        if not s.on_ground:
            air_since = s.t if air_since is None else air_since
            if s.t - air_since > AIRBORNE_S:
                res.incidents.append({"t": s.t, "type": "airborne", "segment": prev_sid})
                if prev_sid:
                    failed.update({(prev_sid, "forward"), (prev_sid, "backward")} & set(visits))
                air_since = s.t + 1e9  # report once per episode
        else:
            air_since = None
        if prev is not None and s.t > prev.t:
            decel = (prev.gs_mps - s.gs_mps) / (s.t - prev.t)
            if decel > SUDDEN_DECEL_MPS2 and s.brake < 0.1 and prev.gs_mps > 3:
                res.incidents.append({"t": s.t, "type": "sudden_stop", "segment": prev_sid,
                                      "decel_mps2": round(decel, 1)})
                if cur_key:
                    failed.add(cur_key)
        if s.event.startswith("recovery"):
            res.incidents.append({"t": s.t, "type": "recovery", "segment": prev_sid, "event": s.event})
            if prev_sid:
                failed.update({k for k in visits if k[0] == prev_sid})
        prev = s

    for (sid, direction), sts in visits.items():
        n = len(profiles[sid].s)
        cov = len(sts) / n
        if (sid, direction) in failed:
            result = "fail"
        elif cov >= MIN_STATION_COVERAGE:
            result = "pass"
        else:
            result = "partial"
        res.segments.setdefault(sid, {})[direction] = {"result": result, "coverage": round(cov, 3)}
    return res


def required_directions(seg) -> set[str]:
    return {"forward"} if seg.oneway == "forward" else {"backward"} if seg.oneway == "backward" \
        else {"forward", "backward"}


def save_result(res: RunResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{res.run_id}.json"
    p.write_text(json.dumps(res.to_json(), indent=1))
    return p
