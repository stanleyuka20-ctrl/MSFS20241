"""Offline geometry checks.

These are GEOMETRY checks only. Passing them promotes a segment to
'geometry_verified'; it says nothing about whether the simulator's vehicle is
supported by the surface. Only telemetry from in-game driving (telemetry.py)
can promote to 'driven' / 'verified'.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from . import config as C
from .geo import lonlat_to_utm
from .meshgen import DECK_THICKNESS_M
from .profile import grade_out

ERROR_TYPES = {
    "joint_gap", "underpass_clearance", "overlap", "deck_elevation_missing",
    "deck_from_terrain", "height_conflict",
}
WARNING_TYPES = {"grade", "grade_change", "joint_kink", "junction_warp", "grade_separation_indeterminate"}
MAX_JOINT_KINK = 0.03


def _z_at(profile, x, y):
    d = np.hypot(profile.xy_utm[:, 0] - x, profile.xy_utm[:, 1] - y)
    k = int(np.argmin(d))
    return float(profile.z_sim[k]), float(d[k])


def run_checks(inv, profiles: dict, build, blockers: dict[str, str]) -> dict[str, list]:
    """Return {object_id: [issue, ...]} for segments, decks and junctions."""
    issues = defaultdict(list)

    for deck_id, reason in blockers.items():
        issues[deck_id].append({"type": "deck_elevation_missing", "detail": reason})
        for sid in inv.bridge_decks[deck_id].segment_ids:
            issues[sid].append({"type": "deck_elevation_missing", "deck": deck_id})
    for d in inv.bridge_decks.values():
        if d.elevation_source == "terrain":
            issues[d.id].append({"type": "deck_from_terrain"})

    for sid, p in profiles.items():
        for i in p.issues:
            issues[sid].append(i)

    # Continuity at 2-way connections: both ribbons must end at the same height.
    for j in inv.junctions.values():
        if j.kind != "connection":
            continue
        ends, grades = [], []
        for sid in j.segment_ids:
            p = profiles.get(sid)
            if p is None:
                continue
            at_start = inv.segments[sid].from_node == j.osm_node_id
            ends.append(p.z_sim[0] if at_start else p.z_sim[-1])
            grades.append(grade_out(p.s, p.z_sim, at_start))
        if len(ends) == 2 and abs(ends[0] - ends[1]) > C.MAX_JOINT_GAP_M:
            for sid in j.segment_ids:
                issues[sid].append({"type": "joint_gap", "junction": j.id,
                                    "dz_m": round(abs(ends[0] - ends[1]), 3)})
        # through a 2-way joint the outgoing grades should be opposite: g1 = -g2
        if len(grades) == 2 and abs(grades[0] + grades[1]) > MAX_JOINT_KINK:
            for sid in j.segment_ids:
                issues[sid].append({"type": "joint_kink", "junction": j.id,
                                    "grade_change": round(abs(grades[0] + grades[1]), 4)})

    # Underpass clearance at grade separations.
    for g in inv.grade_separations.values():
        if not g.determinate:
            for sid in (g.seg_a, g.seg_b):
                issues[sid].append({"type": "grade_separation_indeterminate", "gsx": g.id})
            continue
        up, lo = profiles.get(g.upper_segment), profiles.get(g.lower_segment)
        if up is None or lo is None or inv.segments[g.lower_segment].tunnel:
            continue
        x, y = lonlat_to_utm(g.lon, g.lat)
        zu, _ = _z_at(up, x, y)
        zl, _ = _z_at(lo, x, y)
        clearance = zu - DECK_THICKNESS_M - zl
        if clearance < C.MIN_UNDERPASS_CLEARANCE_M:
            for sid in (g.upper_segment, g.lower_segment):
                issues[sid].append({"type": "underpass_clearance", "gsx": g.id,
                                    "clearance_m": round(clearance, 2),
                                    "min_m": C.MIN_UNDERPASS_CLEARANCE_M})

    # Surface issues: height conflicts inside a group are attributed to the nearby segments.
    for i in build.issues:
        for sid in i.get("segments", []):
            issues[sid].append(i)

    # Overlapping surfaces of different groups at similar height (outside abutment clip zones).
    keys = sorted(build.footprints, key=str)
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            fa, fb = build.footprints[keys[a]], build.footprints[keys[b]]
            if fa.is_empty or fb.is_empty or not fa.intersects(fb):
                continue
            inter = fa.intersection(fb)
            for part in getattr(inter, "geoms", [inter]):
                if part.area < 0.5:
                    continue
                c = part.representative_point()
                za, zb = build.heights[keys[a]](c.x, c.y), build.heights[keys[b]](c.x, c.y)
                if abs(za - zb) < 2.0:
                    near = []
                    for k in (keys[a], keys[b]):
                        g = build.groups[k]
                        near += [g.seg_ids[i] for i in g.tree.query(c.buffer(15))]
                    for sid in near:
                        issues[sid].append({"type": "overlap", "groups": [str(keys[a]), str(keys[b])],
                                            "area_m2": round(part.area, 1), "dz_m": round(abs(za - zb), 2)})
    return dict(issues)


def has_errors(issue_list) -> bool:
    return any(i["type"] in ERROR_TYPES for i in issue_list)
