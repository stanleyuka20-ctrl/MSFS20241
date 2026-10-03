"""Concrete driving-test plan (D1-D10) derived from a build: start points, headings
and the segments each test must cover. Output feeds the human tester and the
telemetry analyser; it is a plan, not evidence."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point

from .geo import utm_to_lonlat


def _pt(p, k, reverse=False):
    k = max(0, min(k, len(p.s) - 1))
    a, b = max(k - 1, 0), min(k + 1, len(p.s) - 1)
    dx, dy = p.xy_utm[b] - p.xy_utm[a]
    hdg = math.degrees(math.atan2(dx, dy)) % 360
    if reverse:
        hdg = (hdg + 180) % 360
    lon, lat = utm_to_lonlat(*p.xy_utm[k])
    return {"lat": round(float(lat), 7), "lon": round(float(lon), 7), "heading_deg": round(hdg, 1),
            "surface_alt_m": round(float(p.z_sim[k]), 2)}


def _k_at(p, dist):
    return int(np.searchsorted(p.s, dist))


def make_plan(inv, profiles, report: dict, sel: set[str]) -> dict:
    ok = set(profiles) - set(report.get("segments_with_errors", [])) - set(report.get("blocked", {}))
    segs = {s: inv.segments[s] for s in ok}
    plan = {"build_id": report["build_id"], "tests": {}}

    def grade(p):
        return np.diff(p.z_sim) / np.maximum(np.diff(p.s), 1e-6)

    # decks that were generated
    decks = [d for d in inv.bridge_decks.values() if all(s in ok for s in d.segment_ids)]
    main_deck = max(decks, key=lambda d: d.length_m) if decks else None
    # D1/D2/D4: straight, flat, two-way street >= 80 m, closest to the main deck
    ref = None
    if main_deck:
        dp = profiles[main_deck.segment_ids[0]]
        ref = Point(*dp.xy_utm[0])
    cands = []
    for sid, s in segs.items():
        p = profiles[sid]
        if s.bridge or s.oneway != "both" or s.length_m < 80 or s.scope != "in_scope":
            continue
        line = LineString(p.xy_utm)
        straight = line.length / max(Point(p.xy_utm[0]).distance(Point(p.xy_utm[-1])), 1e-6) < 1.02
        if straight and np.abs(grade(p)).max() < 0.03:
            cands.append((line.distance(ref) if ref else 0, sid))
    if cands:
        sid = sorted(cands)[0][1]
        p = profiles[sid]
        start = _pt(p, _k_at(p, 10))
        plan["tests"]["D1"] = {"what": "spawn and wait 10 s", "start": start, "segment": sid, "name": segs[sid].name}
        plan["tests"]["D2"] = {"what": "accelerate to ~40 km/h along the street, brake to a stop before its end",
                               "start": start, "segments": [sid], "length_m": segs[sid].length_m}
        plan["tests"]["D4"] = {"what": "from the D2 stop, reverse 30 m", "segments": [sid]}
    # D3: 4+ arm intersection of in-scope ground roads, all generated
    best = None
    for j in inv.junctions.values():
        if j.kind != "intersection" or len(j.segment_ids) < 4:
            continue
        if not all(s in segs and not segs[s].bridge and segs[s].scope == "in_scope" for s in j.segment_ids):
            continue
        d = Point(*profiles[j.segment_ids[0]].xy_utm[0]).distance(ref) if ref else 0
        if best is None or d < best[0]:
            best = (d, j)
    if best:
        j = best[1]
        plan["tests"]["D3"] = {"what": "approach the intersection on every arm in its permitted direction; "
                                       "turn left, right and go straight from each",
                               "junction": j.id, "lat": round(j.lat, 7), "lon": round(j.lon, 7),
                               "arms": [{"segment": s, "name": segs[s].name, "oneway": segs[s].oneway}
                                        for s in j.segment_ids]}
    # D5: steepest ground segment (non-motorway), start at the bottom heading uphill
    steep = []
    for allow_deck in (False, True):          # prefer a ground hill; else the steepest deck ramp
        for sid, s in segs.items():
            if (s.bridge and not allow_deck) or s.highway.startswith("motorway") or s.scope != "in_scope":
                continue
            g = grade(profiles[sid])
            if len(g) and np.abs(g).max() >= 0.03:
                steep.append((float(np.abs(g).max()), sid))
        if steep:
            break
    if steep:
        gmax, sid = max(steep)
        p = profiles[sid]
        g = grade(p)
        k = int(np.argmax(np.abs(g)))
        uphill_forward = g[k] > 0
        if segs[sid].oneway == "forward" and not uphill_forward or segs[sid].oneway == "backward" and uphill_forward:
            note = "permitted direction is downhill here: do the hold-and-release test facing downhill (brake hold)"
        else:
            note = "start below the steep part, stop on it, hold 10 s with brakes, release, hill start"
        plan["tests"]["D5"] = {"what": note, "segment": sid, "name": segs[sid].name, "max_grade": round(gmax, 3),
                               "stop_point": _pt(p, k, reverse=not uphill_forward)}
    # D6: each generated deck of the main crossing, in each permitted direction
    if main_deck:
        crossing = [d for d in decks if (d.crossing_id and d.crossing_id == main_deck.crossing_id) or d is main_deck]
        runs = []
        for d in crossing:
            for sid in d.segment_ids:
                s, p = segs[sid], profiles[sid]
                dirs = ["forward", "backward"] if s.oneway == "both" else [s.oneway]
                for dr in dirs:
                    runs.append({"deck": d.id, "segment": sid, "direction": dr,
                                 "deck_start": _pt(p, 0 if dr == "forward" else len(p.s) - 1, reverse=dr == "backward"),
                                 "crown_alt_m": round(float(p.z_sim.max()), 2)})
        plan["tests"]["D6"] = {"what": "start ~150 m before the deck on its approach, drive approach -> deck -> exit "
                                       "without stopping, then repeat with a stop on the steepest part",
                               "crossing": main_deck.name, "runs": runs}
    # D7: road beneath a generated deck
    unders = []
    for g in inv.grade_separations.values():
        if g.determinate and g.lower_segment in segs and g.upper_segment in segs and segs[g.upper_segment].bridge \
                and not segs[g.lower_segment].bridge:
            unders.append(g)
    if unders:
        g = unders[0]
        p = profiles[g.lower_segment]
        line = LineString(p.xy_utm)
        from .geo import lonlat_to_utm
        k = _k_at(p, max(line.project(Point(*lonlat_to_utm(g.lon, g.lat))) - 40, 0))
        plan["tests"]["D7"] = {"what": "drive beneath the structure in each permitted direction",
                               "grade_separation": g.id, "lower": g.lower_segment, "lower_name": segs[g.lower_segment].name,
                               "upper": g.upper_segment, "upper_name": segs[g.upper_segment].name,
                               "start": _pt(p, k), "all_candidates": [u.id for u in unders]}
    # D8: transition from generated roads into default scenery
    trans = []
    for j in inv.junctions.values():
        inside = [s for s in j.segment_ids if s in segs]
        outside = [s for s in j.segment_ids if s not in sel]
        if inside and outside:
            d = Point(*profiles[inside[0]].xy_utm[0]).distance(ref) if ref else 0
            trans.append((d, j, inside[0]))
    if trans:
        _, j, sid = sorted(trans, key=lambda t: t[0])[0]
        plan["tests"]["D8"] = {"what": "drive from the generated road across this junction into default scenery and back; "
                                       "record any visible step or gap at the hand-over",
                               "junction": j.id, "lat": round(j.lat, 7), "lon": round(j.lon, 7), "segment": sid,
                               "name": segs[sid].name}
    plan["tests"]["D9"] = {"what": "one continuous recording of >= 20 min covering D2-D8 with no recovery"}
    plan["tests"]["D10"] = {"what": "restart the simulator; repeat D3, D6 and D7 with `--after-restart`"}
    return plan


def to_markdown(plan: dict, title: str) -> str:
    L = [f"# {title}", "", f"Generated from build `{plan['build_id']}` by `nycroads test-plan`. "
         "Coordinates are WGS84; heights are the generated road surface in the current simulator "
         "height reference (UNVERIFIED until V7 calibration).", ""]
    for k, t in plan["tests"].items():
        L.append(f"## {k}")
        L.append("")
        L.append(f"**Do:** {t['what']}")
        L.append("")
        rest = {kk: vv for kk, vv in t.items() if kk != "what"}
        if rest:
            L += ["```json", json.dumps(rest, indent=1), "```", ""]
    return "\n".join(L)


def write(plan: dict, out_dir: Path, title: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "test_plan.json").write_text(json.dumps(plan, indent=1))
    (out_dir / "TEST_PLAN.md").write_text(to_markdown(plan, title))
