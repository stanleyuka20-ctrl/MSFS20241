"""Status store and coverage reporting.

Status is kept in data/status.json, separate from the inventory, so re-importing
OSM never loses test evidence. Status of a segment is DERIVED from evidence:

  inventoried        in the inventory
  generated          geometry generated in a build
  geometry_verified  latest build's automated checks had no errors for it
  driven             in-game run(s) passed in every permitted direction
  verified           driven, AND passed again in a run flagged after_restart
  blocked            a recorded blocker (e.g. deck elevation, tunnel feasibility)
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import config as C
from .telemetry import required_directions


class StatusStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"objects": {}, "runs": []}

    def obj(self, oid: str) -> dict:
        return self.data["objects"].setdefault(oid, {"build": None, "drives": [], "blocked": None})

    def record_build(self, build_id: str, generated: set[str], issues: dict, blockers: dict):
        for oid, o in self.data["objects"].items():
            if o.get("build"):
                o["build"]["current"] = False
        for oid in generated | set(issues) | set(blockers):
            o = self.obj(oid)
            errs = [i for i in issues.get(oid, []) if i["type"] in _errors()]
            o["build"] = {"build_id": build_id, "generated": oid in generated, "current": True,
                          "errors": errs, "warnings": [i for i in issues.get(oid, []) if i not in errs]}
            o["blocked"] = blockers.get(oid)

    def record_run(self, run_json: dict):
        self.data["runs"].append({k: run_json[k] for k in ("run_id", "meta")})
        after_restart = bool(run_json["meta"].get("after_restart"))
        for sid, dirs in run_json["segments"].items():
            for d, r in dirs.items():
                self.obj(sid)["drives"].append({"run_id": run_json["run_id"], "direction": d,
                                                "result": r["result"], "after_restart": after_restart,
                                                "build_id": run_json["meta"].get("build_id")})

    def block(self, oid: str, reason: str):
        self.obj(oid)["blocked"] = reason

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_utc"] = datetime.now(timezone.utc).isoformat()
        self.path.write_text(json.dumps(self.data, indent=1))


def _errors():
    from .checks import ERROR_TYPES
    return ERROR_TYPES


def derive_status(seg, o: dict | None) -> str:
    if o is None:
        return "inventoried"
    if o.get("blocked"):
        return C.BLOCKED
    b = o.get("build")
    if not b or not b.get("current") or not b.get("generated"):
        return "inventoried"
    if b["errors"]:
        return "generated"
    build_id = b["build_id"]
    need = required_directions(seg)
    # Only drives against the CURRENT build count: a rebuild invalidates old evidence.
    drives = [d for d in o.get("drives", []) if d.get("build_id") == build_id]
    # A later failure in a direction cancels earlier passes in that direction.
    last = {}
    for d in drives:
        last[d["direction"]] = d
    passed = {k for k, d in last.items() if d["result"] == "pass"}
    if not need <= passed:
        return "geometry_verified"
    restart_ok = all(any(d["direction"] == k and d["result"] == "pass" and d["after_restart"] for d in drives)
                     for k in need)
    return "verified" if restart_ok else "driven"


def coverage_report(inv, store: StatusStore) -> dict:
    rows = defaultdict(lambda: defaultdict(lambda: {"segments": 0, "km": 0.0}))
    seg_status = {}
    for s in inv.segments.values():
        st = derive_status(s, store.data["objects"].get(s.id))
        if s.tunnel and st != C.BLOCKED and st not in ("driven", "verified"):
            st = C.BLOCKED  # tunnels: separate feasibility task (docs/01)
        seg_status[s.id] = st
        if s.scope != "in_scope":
            continue
        r = rows[s.borough][st]
        r["segments"] += 1
        r["km"] += s.length_m / 1000
    totals = defaultdict(lambda: {"segments": 0, "km": 0.0})
    for b, d in rows.items():
        for st, v in d.items():
            totals[st]["segments"] += v["segments"]
            totals[st]["km"] += v["km"]
    all_km = sum(v["km"] for v in totals.values()) or 1.0
    deck_status = {}
    for d in inv.bridge_decks.values():
        sts = [seg_status[i] for i in d.segment_ids]
        order = C.STATUSES + [C.BLOCKED]
        deck_status[d.id] = C.BLOCKED if C.BLOCKED in sts else min(sts, key=order.index)
    return {
        "by_borough": {b: {k: {"segments": v["segments"], "km": round(v["km"], 3)} for k, v in d.items()}
                       for b, d in rows.items()},
        "totals": {k: {"segments": v["segments"], "km": round(v["km"], 3),
                       "pct_km": round(100 * v["km"] / all_km, 2)} for k, v in totals.items()},
        "segment_status": seg_status,
        "bridge_deck_status": deck_status,
    }


def write_coverage(inv, store: StatusStore, out_dir: Path) -> dict:
    rep = coverage_report(inv, store)
    out_dir.mkdir(parents=True, exist_ok=True)
    feats = []
    for s in inv.segments.values():
        feats.append({"type": "Feature", "id": s.id,
                      "properties": {"id": s.id, "name": s.name, "highway": s.highway, "scope": s.scope,
                                     "borough": s.borough, "bridge": s.bridge, "tunnel": s.tunnel,
                                     "status": rep["segment_status"][s.id]},
                      "geometry": {"type": "LineString", "coordinates": s.coords}})
    (out_dir / "coverage.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    (out_dir / "coverage_summary.json").write_text(json.dumps({k: v for k, v in rep.items()
                                                               if k != "segment_status"}, indent=1))
    (out_dir / "COVERAGE.md").write_text(_markdown(rep))
    (out_dir / "coverage_map.html").write_text(_HTML)
    return rep


def _markdown(rep) -> str:
    order = C.STATUSES[1:] + [C.BLOCKED]
    lines = ["# Coverage (in-scope public motor-vehicle roads)", "",
             "Generated by `nycroads coverage`. Status definitions: docs/06-test-protocol.md.", "",
             "| Status | Segments | km | % of km |", "|---|---:|---:|---:|"]
    for st in order:
        v = rep["totals"].get(st)
        if v:
            lines.append(f"| {st} | {v['segments']} | {v['km']:.2f} | {v['pct_km']:.2f} |")
    lines += ["", "## By borough", "", "| Borough | " + " | ".join(order) + " |",
              "|---|" + "---:|" * len(order)]
    for b, d in sorted(rep["by_borough"].items()):
        lines.append(f"| {b} | " + " | ".join(f"{d.get(st, {}).get('km', 0):.2f} km" for st in order) + " |")
    lines += ["", "## Bridge decks", "", "| Deck | Status |", "|---|---|"]
    for k, v in sorted(rep["bridge_deck_status"].items()):
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines) + "\n"


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NYC Drivable Roads coverage</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{height:100%;margin:0}
.legend{background:#fff;padding:8px 10px;font:13px sans-serif;line-height:1.5}
.legend i{display:inline-block;width:18px;height:4px;margin-right:6px;vertical-align:middle}</style>
</head><body><div id="map"></div><script>
// Open via a local web server next to coverage.geojson:  python -m http.server
const COLORS={inventoried:'#9e9e9e',generated:'#ff9800',geometry_verified:'#2196f3',
              driven:'#8bc34a',verified:'#1b5e20',blocked:'#d32f2f'};
const map=L.map('map').setView([40.72,-73.95],12);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,
  attribution:'&copy; OpenStreetMap contributors (ODbL)'}).addTo(map);
fetch('coverage.geojson').then(r=>r.json()).then(g=>{
  L.geoJSON(g,{style:f=>({color:COLORS[f.properties.status]||'#000',
     weight:f.properties.scope==='in_scope'?3:1.5,dashArray:f.properties.tunnel?'4 4':null}),
   onEachFeature:(f,l)=>l.bindPopup(`<b>${f.properties.id}</b><br>${f.properties.name||''}<br>`+
     `${f.properties.highway} · ${f.properties.borough}<br>status: <b>${f.properties.status}</b>`)}).addTo(map);
});
const lg=L.control({position:'bottomright'});
lg.onAdd=()=>{const d=L.DomUtil.create('div','legend');
  d.innerHTML=Object.entries(COLORS).map(([k,c])=>`<i style="background:${c}"></i>${k}`).join('<br>');return d;};
lg.addTo(map);
</script></body></html>
"""
