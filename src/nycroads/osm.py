"""OpenStreetMap ingestion (Overpass API) with provenance records.

OSM data is (c) OpenStreetMap contributors, available under the Open Database
License (ODbL 1.0). Every raw download is written next to a ``.source.json``
record (endpoint, query, timestamp, licence) so attribution survives into
releases. Derived databases that we redistribute (the inventory) must also be
offered under ODbL; see docs/05-data-sources-and-licensing.md.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import IN_SCOPE_HIGHWAY, TRACKED_SECONDARY_HIGHWAY

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
ODBL = {
    "license": "ODbL-1.0",
    "attribution": "(c) OpenStreetMap contributors",
    "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
}

# Wikidata IDs of the five boroughs (used to pick the right OSM boundary relations
# without depending on admin_level conventions).
BOROUGH_WIKIDATA = {
    "Manhattan": "Q11299",
    "Brooklyn": "Q18419",
    "Queens": "Q18424",
    "Bronx": "Q18426",
    "Staten Island": "Q18432",
}

# (south, west, north, east). City bbox plus the documented GWB extension in NJ.
NYC_BBOX = (40.4700, -74.2700, 40.9300, -73.6800)
GWB_NJ_EXTENSION_BBOX = (40.8380, -73.9950, 40.8620, -73.9550)


@dataclass
class OsmData:
    nodes: dict[int, tuple[float, float]] = field(default_factory=dict)  # id -> (lon, lat)
    ways: dict[int, dict] = field(default_factory=dict)                  # id -> {"nodes": [...], "tags": {...}}
    relations: dict[int, dict] = field(default_factory=dict)

    @classmethod
    def from_overpass_json(cls, payload: dict) -> "OsmData":
        d = cls()
        for el in payload.get("elements", []):
            t = el["type"]
            if t == "node":
                d.nodes[el["id"]] = (el["lon"], el["lat"])
            elif t == "way":
                d.ways[el["id"]] = {"nodes": el.get("nodes", []), "tags": el.get("tags", {})}
                # 'out geom' variant carries coordinates inline
                if "geometry" in el and el.get("nodes"):
                    for nid, g in zip(el["nodes"], el["geometry"]):
                        d.nodes.setdefault(nid, (g["lon"], g["lat"]))
            elif t == "relation":
                d.relations[el["id"]] = {"members": el.get("members", []), "tags": el.get("tags", {})}
        return d

    @classmethod
    def load(cls, *paths: Path) -> "OsmData":
        out = cls()
        for p in paths:
            part = cls.from_overpass_json(json.loads(Path(p).read_text()))
            out.nodes.update(part.nodes)
            out.ways.update(part.ways)
            out.relations.update(part.relations)
        return out


def roads_query(bbox: tuple[float, float, float, float], timeout: int = 900) -> str:
    s, w, n, e = bbox
    classes = "|".join(sorted(IN_SCOPE_HIGHWAY | TRACKED_SECONDARY_HIGHWAY))
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"(\n"
        f'  way["highway"~"^({classes})$"]({s},{w},{n},{e});\n'
        f'  way["man_made"="bridge"]({s},{w},{n},{e});\n'
        f");\n"
        f"out body;\n>;\nout skel qt;\n"
    )


def boroughs_query(timeout: int = 300) -> str:
    ids = "|".join(BOROUGH_WIKIDATA.values())
    return (
        f"[out:json][timeout:{timeout}];\n"
        f'rel["boundary"="administrative"]["wikidata"~"^({ids})$"];\n'
        f"out geom;\n"
    )


def split_bbox(bbox, nx: int, ny: int):
    s, w, n, e = bbox
    dy, dx = (n - s) / ny, (e - w) / nx
    for j in range(ny):
        for i in range(nx):
            yield (s + j * dy, w + i * dx, s + (j + 1) * dy, w + (i + 1) * dx)


def fetch(query: str, out_path: Path, endpoint: str = OVERPASS_URL, retries: int = 4) -> Path:
    """Run an Overpass query, save JSON and a provenance record."""
    import requests

    out_path.parent.mkdir(parents=True, exist_ok=True)
    delay = 5
    for attempt in range(retries + 1):
        r = requests.post(endpoint, data={"data": query}, timeout=1200)
        if r.status_code == 200:
            break
        if attempt == retries:
            r.raise_for_status()
        time.sleep(delay)
        delay *= 2
    payload = r.json()
    out_path.write_text(json.dumps(payload))
    source = {
        "endpoint": endpoint,
        "query": query,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "osm_base": payload.get("osm3s", {}).get("timestamp_osm_base"),
        **ODBL,
    }
    out_path.with_suffix(".source.json").write_text(json.dumps(source, indent=2))
    return out_path


def borough_polygons(data: OsmData):
    """Build shapely (Multi)Polygons per borough from 'out geom' boundary relations."""
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    inv = {v: k for k, v in BOROUGH_WIKIDATA.items()}
    result = {}
    for rel in data.relations.values():
        name = inv.get(rel["tags"].get("wikidata"))
        if not name:
            continue
        lines = []
        for m in rel["members"]:
            if m.get("type") == "way" and m.get("role") in ("outer", "") and "geometry" in m:
                lines.append(LineString([(g["lon"], g["lat"]) for g in m["geometry"]]))
        polys = list(polygonize(unary_union(lines)))
        if polys:
            result[name] = unary_union(polys)
    return result
