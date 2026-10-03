"""Offline geometry checks.

These are GEOMETRY checks only. Passing them promotes a segment to
'geometry_verified'; it says nothing about whether the simulator's vehicle is
supported by the surface. Only telemetry from in-game driving (telemetry.py)
can promote to 'driven' / 'verified'.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from . import config as C
from .geo import lonlat_to_utm
from .meshgen import DECK_THICKNESS_M
from .profile import grade_out

ERROR_TYPES = {
    "joint_gap", "underpass_clearance", "overlap", "deck_elevation_missing",
    "junction_trim_conflict", "junction_pad_invalid", "deck_from_terrain",
}
WARNING_TYPES = {"grade", "grade_change", "joint_kink", "open_edge", "grade_separation_indeterminate"}
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

    for i in build.issues:
        issues[i["id"]].append(i)

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

    # Overlapping surfaces of different, non-adjacent segments at similar height.
    polys, ids = [], []
    for sid, meshes in build.meshes_by_segment.items():
        surf = meshes[0]
        v = np.asarray(surf.vertices)
        n = len(v) // 2
        if n < 2:
            continue
        ring = list(map(tuple, v[:n, :2])) + list(map(tuple, v[n:, :2][::-1]))
        poly = Polygon(ring).buffer(0)
        polys.append(poly)
        ids.append(sid)
    tree = STRtree(polys)
    for i, pi in enumerate(polys):
        for j in tree.query(pi, predicate="intersects"):
            if j <= i:
                continue
            a, b = inv.segments[ids[i]], inv.segments[ids[j]]
            if {a.from_node, a.to_node} & {b.from_node, b.to_node}:
                continue
            inter = pi.intersection(polys[j])
            if inter.area < 0.5:
                continue
            c = inter.representative_point()
            za, _ = _z_at(profiles[a.id], c.x, c.y)
            zb, _ = _z_at(profiles[b.id], c.x, c.y)
            if abs(za - zb) < 2.0:
                for sid in (a.id, b.id):
                    issues[sid].append({"type": "overlap", "other": b.id if sid == a.id else a.id,
                                        "area_m2": round(inter.area, 1), "dz_m": round(abs(za - zb), 2)})
    return dict(issues)


def has_errors(issue_list) -> bool:
    return any(i["type"] in ERROR_TYPES for i in issue_list)
