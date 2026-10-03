"""Demonstration-route acceptance: does a candidate area contain every required feature?

Required (task brief, section 2):
  street_and_intersection  - an at-grade intersection of in-scope roads
  slope                    - a ground road with a real grade >= 3 % over >= 30 m
  bridge                   - a bridge deck with ground-level approach at both ends
  underpass                - an in-scope road passing beneath an elevated structure
  transition               - repaired roads that continue into default scenery
The check runs on the real inventory + profiles; a candidate that fails a
criterion is reported, never silently accepted.
"""
from __future__ import annotations

import numpy as np


def evaluate(inv, sel: set[str], profiles: dict) -> dict:
    res = {}
    ints = [j for j in inv.junctions.values()
            if j.kind == "intersection" and set(j.segment_ids) <= sel
            and all(inv.segments[s].scope == "in_scope" and not inv.segments[s].bridge for s in j.segment_ids)]
    res["street_and_intersection"] = {"pass": bool(ints), "examples": [j.id for j in ints[:5]]}

    slopes = []
    for sid in sel:
        p, seg = profiles.get(sid), inv.segments[sid]
        if p is None or seg.bridge or len(p.s) < 3:
            continue
        g = np.diff(p.z_sim) / np.maximum(np.diff(p.s), 1e-6)
        steep = np.abs(g) >= 0.03
        run, best = 0.0, 0.0
        for k, st in enumerate(steep):
            run = run + (p.s[k + 1] - p.s[k]) if st else 0.0
            best = max(best, run)
        if best >= 30:
            slopes.append((sid, round(float(np.abs(g).max()), 3), round(best, 1)))
    res["slope"] = {"pass": bool(slopes), "examples": slopes[:5]}

    decks = []
    for d in inv.bridge_decks.values():
        if not set(d.segment_ids) <= sel:
            continue
        nodes = [n for s in d.segment_ids for n in (inv.segments[s].from_node, inv.segments[s].to_node)]
        ends = [n for n in set(nodes) if nodes.count(n) == 1]
        approached = 0
        for j in inv.junctions.values():
            if j.osm_node_id in ends and any(not inv.segments[s].bridge and s in sel for s in j.segment_ids):
                approached += 1
        if approached >= 2:
            decks.append({"deck": d.id, "name": d.name, "profiled": all(s in profiles for s in d.segment_ids)})
    res["bridge"] = {"pass": any(x["profiled"] for x in decks), "examples": decks[:5],
                     "note": "a deck without elevation controls does not count (see blocked list)"}

    under = [g.id for g in inv.grade_separations.values()
             if g.determinate and g.lower_segment in sel and g.upper_segment in sel
             and not inv.segments[g.lower_segment].tunnel and inv.segments[g.lower_segment].scope == "in_scope"]
    res["underpass"] = {"pass": bool(under), "examples": under[:5]}

    trans = []
    for j in inv.junctions.values():
        inside = [s for s in j.segment_ids if s in sel]
        outside = [s for s in j.segment_ids if s not in sel]
        if inside and outside:
            trans.append(j.id)
    res["transition"] = {"pass": bool(trans), "count": len(trans), "examples": trans[:5]}
    res["all_pass"] = all(v["pass"] for k, v in res.items() if isinstance(v, dict) and "pass" in v)
    return res
