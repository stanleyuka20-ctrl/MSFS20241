"""Overture Maps transportation data -> the inventory's OSM-style input model.

Why: in environments where the OSM APIs are unreachable, Overture's GeoParquet
release on AWS (s3://overturemaps-us-west-2, public, anonymous) provides the
same OpenStreetMap road network (licence ODbL-1.0, attribution "(c) OpenStreetMap
contributors", plus Overture attribution) with stable GERS IDs.

Model differences handled here:
* Overture segments carry *fractional* rules (``between: [a, b]``) for
  bridge / tunnel / level. Each segment is split at every rule boundary so every
  output way has uniform tags (a bridge deck starts exactly where OSM says).
* Topology is given by ``connectors`` at fractional positions; each connector
  becomes a shared node, inserted as a vertex if needed.
* oneway / access come from ``access_restrictions`` (mapping below). Rules
  limited to part of a segment (``between``) are ignored and counted.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .geo import lonlat_to_utm
from .osm import OsmData

BUCKET = "overturemaps-us-west-2"
DEFAULT_RELEASE = "2026-09-23.1"
ATTRIBUTION = {
    "license": "ODbL-1.0",
    "attribution": "(c) OpenStreetMap contributors; Overture Maps Foundation",
    "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
}
MOTOR_MODES = {"motor_vehicle", "car", "vehicle"}
SPLIT_FLAGS = ("is_bridge", "is_tunnel")
EXCLUDE_FLAGS = {"is_under_construction": "construction", "is_abandoned": "abandoned"}

# borough -> Overture division_area (county) names in region US-NY
BOROUGH_COUNTIES = {
    "Manhattan": "New York County", "Brooklyn": "Kings County", "Queens": "Queens County",
    "Bronx": "Bronx County", "Staten Island": "Richmond County",
}


def node_id(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:15], 16)


# ----------------------------------------------------------------- download

def _s3():
    import pyarrow.fs as pafs
    return pafs.S3FileSystem(anonymous=True, region="us-west-2",
                             proxy_options=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))


def fetch(theme: str, typ: str, bbox, out: Path, release: str = DEFAULT_RELEASE, extra_filter=None) -> Path:
    """Download features of one Overture type intersecting bbox (s, w, n, e) to GeoParquet."""
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    s, w, n, e = bbox
    path = f"{BUCKET}/release/{release}/theme={theme}/type={typ}/"
    d = ds.dataset(path, filesystem=_s3(), format="parquet")
    f = ((pc.field("bbox", "xmin") < e) & (pc.field("bbox", "xmax") > w)
         & (pc.field("bbox", "ymin") < n) & (pc.field("bbox", "ymax") > s))
    if extra_filter is not None:
        f = f & extra_filter
    tb = d.to_table(filter=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tb, out, compression="zstd")
    out.with_suffix(".source.json").write_text(json.dumps({
        "endpoint": f"s3://{path}", "bbox_swne": list(bbox), "release": release, "rows": tb.num_rows,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(), **ATTRIBUTION}, indent=2))
    return out


# ----------------------------------------------------------------- boroughs

def borough_polygons(division_area_parquet: Path) -> dict:
    """Borough polygons = union of the county's land and territorial-water areas,
    so bridges between boroughs lie inside the project area."""
    import pyarrow.parquet as pq
    import shapely
    from shapely.ops import unary_union

    rows = pq.read_table(division_area_parquet, columns=["names", "subtype", "region", "geometry"]).to_pylist()
    out = {}
    for borough, county in BOROUGH_COUNTIES.items():
        geoms = [shapely.from_wkb(r["geometry"]) for r in rows
                 if r["subtype"] == "county" and r["region"] == "US-NY"
                 and (r["names"] or {}).get("primary") == county]
        if geoms:
            out[borough] = unary_union(geoms)
    missing = set(BOROUGH_COUNTIES) - set(out)
    if missing:
        raise ValueError(f"county polygons missing for {sorted(missing)}")
    return out


# ----------------------------------------------------------------- tag mapping

def _whole(rule) -> bool:
    return not rule.get("between")


def map_tags(r: dict, stats: Counter) -> dict | None:
    """Overture segment row -> OSM-style tags (None = not a road we model)."""
    cls, sub = r.get("class"), r.get("subclass")
    tags = {"overture_id": r["id"]}
    hw = {"unknown": "road"}.get(cls, cls)
    if sub == "link":
        hw = f"{cls}_link"
    if not hw:
        return None
    tags["highway"] = hw
    if cls == "service" and sub in ("driveway", "parking_aisle", "alley"):
        tags["service"] = sub
    if sub in ("sidewalk", "crosswalk", "cycle_crossing"):
        tags["footway"] = sub
    name = (r.get("names") or {}).get("primary")
    if name:
        tags["name"] = name
    for src in r.get("sources") or []:
        rid = src.get("record_id") or ""
        if src.get("dataset") == "OpenStreetMap" and rid.startswith("w"):
            tags["osm_way"] = rid.split("@")[0][1:]
            break
    for fl in r.get("road_flags") or []:
        if _whole(fl):
            for v in fl["values"]:
                if v in EXCLUDE_FLAGS:
                    tags["highway"] = EXCLUDE_FLAGS[v]
    for wr in r.get("width_rules") or []:
        if _whole(wr) and wr.get("value"):
            tags["width"] = f"{wr['value']:.2f}"
    for a in r.get("access_restrictions") or []:
        w = a.get("when") or {}
        modes = set(w.get("mode") or [])
        motor = not modes or bool(modes & MOTOR_MODES)
        if not _whole(a):
            stats["partial access rule ignored"] += 1
            continue
        if not motor or w.get("during"):
            continue
        t = a.get("access_type")
        if w.get("heading") in ("backward", "forward"):
            if t == "denied":
                tags["oneway"] = "yes" if w["heading"] == "backward" else "-1"
            continue
        if t == "denied" and not (w.get("using") or w.get("recognized")):
            tags["motor_vehicle" if modes else "access"] = "no"
        elif t == "allowed" and "as_private" in (w.get("recognized") or []):
            tags.setdefault("access", "private")
        elif t == "allowed" and "as_customer" in (w.get("using") or []):
            tags.setdefault("access", "customers")
    return tags


def _rules_at(r: dict, frac: float) -> dict:
    """bridge / tunnel / layer that apply at fractional position ``frac``."""
    out = {}
    for fl in r.get("road_flags") or []:
        b = fl.get("between")
        if b is None or b[0] <= frac <= b[1]:
            for v in fl["values"]:
                if v == "is_bridge":
                    out["bridge"] = "yes"
                elif v == "is_tunnel":
                    out["tunnel"] = "yes"
    for lr in r.get("level_rules") or []:
        b = lr.get("between")
        if (b is None or b[0] <= frac <= b[1]) and lr.get("value") is not None:
            out["layer"] = str(lr["value"])
    return out


def _breaks(r: dict) -> list[float]:
    br = set()
    for fl in r.get("road_flags") or []:
        if fl.get("between") and set(fl["values"]) & set(SPLIT_FLAGS):
            br |= {float(fl["between"][0]), float(fl["between"][1])}
    for lr in r.get("level_rules") or []:
        if lr.get("between"):
            br |= {float(lr["between"][0]), float(lr["between"][1])}
    return sorted(b for b in br if 1e-6 < b < 1 - 1e-6)


# ----------------------------------------------------------------- conversion

def to_osmdata(segments_parquet: Path, bbox=None) -> tuple[OsmData, dict]:
    """Convert Overture segments to OsmData. Returns (data, stats)."""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    import shapely

    tb = pq.read_table(segments_parquet)
    if bbox:
        s, w, n, e = bbox
        b = tb.column("bbox")
        m = pc.and_(pc.and_(pc.less(pc.struct_field(b, "xmin"), e), pc.greater(pc.struct_field(b, "xmax"), w)),
                    pc.and_(pc.less(pc.struct_field(b, "ymin"), n), pc.greater(pc.struct_field(b, "ymax"), s)))
        tb = tb.filter(m)
    cols = ["id", "class", "subclass", "names", "connectors", "road_flags", "level_rules",
            "access_restrictions", "width_rules", "sources", "geometry"]
    d = OsmData()
    stats = Counter()
    for r in tb.select(cols).to_pylist():
        tags = map_tags(r, stats)
        if tags is None:
            stats["no class"] += 1
            continue
        g = shapely.from_wkb(r["geometry"])
        coords = [tuple(c[:2]) for c in g.coords]
        if len(coords) < 2:
            continue
        x, y = lonlat_to_utm(np.array([c[0] for c in coords]), np.array([c[1] for c in coords]))
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
        L = cum[-1]
        if L <= 0:
            continue
        frac = cum / L
        # vertex list with fractional positions; then insert connectors and rule breaks
        pts = [(float(f), lon, lat, None) for f, (lon, lat) in zip(frac, coords)]

        def insert(fpos: float, nid: int | None):
            # snap to an existing vertex within 0.5 m, else insert an interpolated vertex
            k = int(np.argmin([abs(p[0] - fpos) for p in pts]))
            if abs(pts[k][0] - fpos) * L <= 0.5:
                f0, lon, lat, old = pts[k]
                pts[k] = (f0, lon, lat, nid if nid is not None else old)
                return k
            i = int(np.searchsorted([p[0] for p in pts], fpos))
            (fa, xa, ya, _), (fb, xb, yb, _) = pts[i - 1], pts[i]
            t = (fpos - fa) / max(fb - fa, 1e-12)
            pts.insert(i, (fpos, xa + t * (xb - xa), ya + t * (yb - ya), nid))
            return i

        for c in r.get("connectors") or []:
            insert(float(c["at"]), node_id("conn:" + c["connector_id"]))
        for b in _breaks(r):
            insert(b, None)
        # assign ids to all vertices (connectors keep theirs)
        ids = []
        for k, (f, lon, lat, nid) in enumerate(pts):
            if nid is None:
                nid = node_id(f"{r['id']}:{f:.9f}")
            d.nodes[nid] = (lon, lat)
            ids.append(nid)
        cuts = [0.0] + _breaks(r) + [1.0]
        fr = [p[0] for p in pts]
        for k in range(len(cuts) - 1):
            a, b = cuts[k], cuts[k + 1]
            ia = int(np.argmin([abs(v - a) for v in fr]))
            ib = int(np.argmin([abs(v - b) for v in fr]))
            if ib <= ia:
                continue
            t = dict(tags)
            t.update(_rules_at(r, (a + b) / 2))
            wid = node_id(f"way:{r['id']}:{k}")
            d.ways[wid] = {"nodes": ids[ia:ib + 1], "tags": t}
            stats["ways"] += 1
            if len(cuts) > 2:
                stats["ways from split segments"] += 1
    return d, dict(stats)
