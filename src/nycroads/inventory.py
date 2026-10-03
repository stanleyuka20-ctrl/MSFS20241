"""Road / bridge / ramp / intersection inventory with stable IDs.

Input: OsmData (+ optional borough polygons and the curated crossings list).
Output: an ``Inventory`` that can be written as GeoJSON / CSV / JSON and is the
denominator for every coverage figure.
"""
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import networkx as nx
from shapely.geometry import LineString, Point, mapping
from shapely.strtree import STRtree

from . import config as C
from .geo import lonlat_to_utm, tile_id_for, utm_to_lonlat
from .ids import IdRegistry, short_hash
from .osm import OsmData


# --------------------------------------------------------------------------- classify

def classify_way(tags: dict) -> tuple[str, str]:
    """Return (scope, reason): scope in {'in_scope', 'secondary', 'excluded'}."""
    hw = tags.get("highway")
    if hw is None:
        return "excluded", "not a highway"
    if tags.get("area") == "yes":
        return "excluded", "area"
    for k in C.ACCESS_KEYS:
        if tags.get(k) in C.EXCLUDING_ACCESS:
            return "excluded", f"{k}={tags[k]}"
    if hw in C.IN_SCOPE_HIGHWAY:
        return "in_scope", hw
    if hw in C.TRACKED_SECONDARY_HIGHWAY:
        if tags.get("service") in C.EXCLUDED_SERVICE_VALUES:
            return "excluded", f"service={tags['service']}"
        return "secondary", hw
    return "excluded", f"highway={hw}"


def parse_layer(tags: dict) -> int:
    try:
        return int(float(tags.get("layer", "0").split(";")[0]))
    except ValueError:
        return 0


def oneway_of(tags: dict) -> str:
    v = tags.get("oneway")
    if v in ("yes", "true", "1"):
        return "forward"
    if v in ("-1", "reverse"):
        return "backward"
    if v is None and (tags.get("highway") in ("motorway",) or tags.get("junction") == "roundabout"):
        return "forward"
    return "both"


def width_of(tags: dict) -> tuple[float, str]:
    """Paved width in metres and where it came from (tag vs default)."""
    w = tags.get("width")
    if w:
        m = re.match(r"^\s*([\d.]+)\s*(m|ft|')?", w)
        if m:
            val = float(m.group(1)) * (0.3048 if m.group(2) in ("ft", "'") else 1.0)
            if 2.0 <= val <= 60.0:
                return val, "osm:width"
    hw = tags.get("highway", "residential")
    base = hw.replace("_link", "") if hw.endswith("_link") else hw
    try:
        lanes = int(tags.get("lanes", "").split(";")[0])
        src = "osm:lanes"
    except ValueError:
        lanes = C.DEFAULT_LANES.get(hw, 2)
        src = "default:class"
    shoulder = C.DEFAULT_SHOULDER_M.get(base, 1.0) if not hw.endswith("_link") else 1.0
    return lanes * C.LANE_WIDTH_M + 2 * shoulder, src


def is_bridge(tags):
    return tags.get("bridge") not in (None, "no")


def is_tunnel(tags):
    return tags.get("tunnel") not in (None, "no")


# --------------------------------------------------------------------------- records

@dataclass
class Segment:
    id: str
    osm_way_id: int
    from_node: int
    to_node: int
    coords: list  # [(lon, lat), ...]
    highway: str
    scope: str
    name: str
    oneway: str
    width_m: float
    width_source: str
    layer: int
    bridge: bool
    tunnel: bool
    ramp: bool
    length_m: float
    borough: str
    tiles: list = field(default_factory=list)
    bridge_deck_id: str | None = None
    ramp_group_id: str | None = None
    component: int = -1
    tags: dict = field(default_factory=dict)


@dataclass
class Junction:
    id: str
    osm_node_id: int
    lon: float
    lat: float
    kind: str               # intersection | connection | dead_end | boundary_cut
    segment_ids: list
    layer_set: list


@dataclass
class BridgeDeck:
    id: str
    name: str
    crossing_id: str | None   # link into data/crossings.json for major bridges
    level: int                # OSM layer of this deck
    segment_ids: list
    length_m: float
    boroughs: list
    elevation_source: str | None = None   # filled by elevation stage; must never be 'terrain'


@dataclass
class GradeSeparation:
    id: str
    upper_segment: str | None
    lower_segment: str | None
    seg_a: str
    seg_b: str
    lon: float
    lat: float
    determinate: bool
    note: str = ""


@dataclass
class Inventory:
    segments: dict = field(default_factory=dict)
    junctions: dict = field(default_factory=dict)
    bridge_decks: dict = field(default_factory=dict)
    ramp_groups: dict = field(default_factory=dict)
    grade_separations: dict = field(default_factory=dict)
    excluded_counts: dict = field(default_factory=dict)
    sources: list = field(default_factory=list)

    # ---------------------------------------------------------------- export
    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        feats = []
        for s in self.segments.values():
            props = {k: v for k, v in asdict(s).items() if k not in ("coords", "tags")}
            feats.append({"type": "Feature", "id": s.id, "properties": props,
                          "geometry": mapping(LineString(s.coords))})
        _dump(out_dir / "segments.geojson", {"type": "FeatureCollection", "features": feats})
        jfeats = [{"type": "Feature", "id": j.id,
                   "properties": {k: v for k, v in asdict(j).items() if k not in ("lon", "lat")},
                   "geometry": {"type": "Point", "coordinates": [j.lon, j.lat]}}
                  for j in self.junctions.values()]
        _dump(out_dir / "junctions.geojson", {"type": "FeatureCollection", "features": jfeats})
        _dump(out_dir / "bridge_decks.json", {k: asdict(v) for k, v in self.bridge_decks.items()})
        _dump(out_dir / "ramp_groups.json", self.ramp_groups)
        _dump(out_dir / "grade_separations.json", {k: asdict(v) for k, v in self.grade_separations.items()})
        _dump(out_dir / "summary.json", self.summary())
        with open(out_dir / "segments.csv", "w", newline="") as f:
            w = csv.writer(f)
            cols = ["id", "osm_way_id", "from_node", "to_node", "highway", "scope", "name", "oneway",
                    "width_m", "width_source", "layer", "bridge", "tunnel", "ramp", "length_m", "borough",
                    "bridge_deck_id", "ramp_group_id", "component"]
            w.writerow(cols)
            for s in self.segments.values():
                d = asdict(s)
                w.writerow([d[c] for c in cols])

    def summary(self) -> dict:
        by = defaultdict(lambda: {"segments": 0, "km": 0.0})
        for s in self.segments.values():
            k = f"{s.scope}|{s.borough}"
            by[k]["segments"] += 1
            by[k]["km"] += s.length_m / 1000      # round only once, at the end
        for v in by.values():
            v["km"] = round(v["km"], 3)
        kinds = defaultdict(int)
        for j in self.junctions.values():
            kinds[j.kind] += 1
        comps = {s.component for s in self.segments.values() if s.scope == "in_scope"}
        return {
            "segments_by_scope_borough": dict(by),
            "junctions_by_kind": dict(kinds),
            "bridge_decks": len(self.bridge_decks),
            "ramp_groups": len(self.ramp_groups),
            "grade_separations": len(self.grade_separations),
            "indeterminate_grade_separations": sum(not g.determinate for g in self.grade_separations.values()),
            "tunnel_segments": sum(s.tunnel for s in self.segments.values()),
            "in_scope_components": len(comps),
            "excluded_way_counts": self.excluded_counts,
            "sources": self.sources,
        }


def _dump(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=1, default=str))


# --------------------------------------------------------------------------- build

def _utm_line(coords):
    return LineString([lonlat_to_utm(lon, lat) for lon, lat in coords])


def _borough_of(lon, lat, boroughs: dict | None, extensions: dict | None) -> str:
    if not boroughs:
        return "unassigned"
    p = Point(lon, lat)
    for name, poly in boroughs.items():
        if poly.covers(p):
            return name
    for name, poly in (extensions or {}).items():
        if poly.covers(p):
            return name
    return "outside"


def build_inventory(data: OsmData, boroughs: dict | None = None, extensions: dict | None = None,
                    crossings: list | None = None, registry: IdRegistry | None = None,
                    drop_outside: bool = True) -> Inventory:
    """Split OSM ways into routable segments and derive all inventory objects.

    ``boroughs``: name -> shapely polygon (lon/lat). ``extensions``: documented
    out-of-city areas that are in scope (e.g. the GWB NJ approach).
    """
    registry = registry or IdRegistry(None)
    inv = Inventory()
    excluded = defaultdict(int)

    roads = {}
    for wid, w in data.ways.items():
        scope, reason = classify_way(w["tags"])
        if scope == "excluded":
            if "highway" in w["tags"]:
                excluded[reason] += 1
            continue
        if len(w["nodes"]) < 2 or any(n not in data.nodes for n in w["nodes"]):
            excluded["incomplete geometry"] += 1
            continue
        roads[wid] = (scope, w)
    inv.excluded_counts = dict(excluded)

    # Split at every node shared by two or more road ways (OSM models at-grade
    # junctions as shared nodes; grade-separated crossings share none).
    use = defaultdict(int)
    for _, w in roads.values():
        for n in set(w["nodes"]):
            use[n] += 1
        use[w["nodes"][0]] += 1
        use[w["nodes"][-1]] += 1

    pieces = []  # (key, match, wid, scope, tags, nodes)
    for wid, (scope, w) in sorted(roads.items()):
        nodes = w["nodes"]
        start = 0
        for i in range(1, len(nodes)):
            if use[nodes[i]] >= 2 or i == len(nodes) - 1:
                sub = nodes[start:i + 1]
                key = f"{wid}:{sub[0]}:{sub[-1]}:{start}"
                match = ":".join(map(str, sorted((sub[0], sub[-1])))) + f":{len(sub)}"
                pieces.append((key, match, wid, scope, w["tags"], sub))
                start = i
    ids = registry.assign_batch("segment", "SEG", [(p[0], p[1]) for p in pieces])

    for key, _, wid, scope, tags, sub in pieces:
        coords = [data.nodes[n] for n in sub]
        mid = coords[len(coords) // 2]
        borough = _borough_of(mid[0], mid[1], boroughs, extensions)
        line = _utm_line(coords)
        width, wsrc = width_of(tags)
        tiles = sorted({tile_id_for(x, y, C.TILE_SIZE_M) for x, y in line.coords})
        seg = Segment(
            id=ids[key], osm_way_id=wid, from_node=sub[0], to_node=sub[-1], coords=coords,
            highway=tags["highway"], scope=scope, name=tags.get("name", tags.get("ref", "")),
            oneway=oneway_of(tags), width_m=round(width, 2), width_source=wsrc,
            layer=parse_layer(tags), bridge=is_bridge(tags), tunnel=is_tunnel(tags),
            ramp=tags["highway"].endswith("_link"), length_m=round(line.length, 2),
            borough=borough, tiles=tiles, tags=dict(tags),
        )
        inv.segments[seg.id] = seg

    _build_bridge_decks(inv, registry, crossings or [])
    cut_nodes = _drop_outside(inv, boroughs, extensions) if (drop_outside and boroughs) else set()
    _build_junctions(inv, data, registry, boroughs, cut_nodes)
    _build_ramp_groups(inv)
    _build_grade_separations(inv)
    _build_components(inv)
    return inv


def _drop_outside(inv: Inventory, boroughs: dict, extensions: dict | None) -> set[int]:
    """Remove segments outside the project area.

    A bridge deck that is partly outside (e.g. a bridge to New Jersey whose
    state line is mid-span) is removed ENTIRELY: coverage ends at the last
    land junction before it, never half-way across a deck. Returns the nodes
    where removed decks met kept roads.
    """
    from shapely.ops import unary_union
    area = unary_union(list(boroughs.values()) + list((extensions or {}).values()))
    drop = {sid for sid, s in inv.segments.items() if s.borough == "outside"}
    cut_nodes = set()
    for did, d in list(inv.bridge_decks.items()):
        partly_out = any(not area.covers(LineString(inv.segments[i].coords)) for i in d.segment_ids)
        if partly_out or set(d.segment_ids) & drop:
            drop |= set(d.segment_ids)
            for sid in d.segment_ids:
                cut_nodes |= {inv.segments[sid].from_node, inv.segments[sid].to_node}
            del inv.bridge_decks[did]
    for sid in drop:
        del inv.segments[sid]
    inv.excluded_counts["outside project area (segments)"] = len(drop)
    return cut_nodes


def _build_junctions(inv: Inventory, data: OsmData, registry: IdRegistry, boroughs,
                     cut_nodes: set[int] = frozenset()) -> None:
    at = defaultdict(list)
    for s in inv.segments.values():
        at[s.from_node].append(s.id)
        at[s.to_node].append(s.id)
    items = [(f"node:{n}", f"node:{n}") for n in sorted(at)]
    ids = registry.assign_batch("junction", "JCT", items)
    for n, segs in sorted(at.items()):
        deg = len(segs)
        kind = "intersection" if deg >= 3 else "connection" if deg == 2 else "dead_end"
        lon, lat = data.nodes[n]
        layers = sorted({inv.segments[s].layer for s in segs})
        inv.junctions[ids[f"node:{n}"]] = Junction(ids[f"node:{n}"], n, lon, lat, kind, segs, layers)
    for j in inv.junctions.values():
        if j.kind == "dead_end" and j.osm_node_id in cut_nodes:
            j.kind = "boundary_bridge_cut"   # road continues onto an out-of-scope bridge
    # Dead ends created by clipping at the project boundary are boundary cuts,
    # not real dead ends: the default scenery continues the road.
    if boroughs:
        for j in inv.junctions.values():
            if j.kind == "dead_end":
                seg = inv.segments[j.segment_ids[0]]
                tags_end_of_road = seg.tags.get("noexit") == "yes"
                if not tags_end_of_road and _near_boundary(j, data, boroughs):
                    j.kind = "boundary_cut"


def _near_boundary(j: Junction, data: OsmData, boroughs, tol_deg: float = 0.0015) -> bool:
    p = Point(j.lon, j.lat)
    return any(poly.boundary.distance(p) < tol_deg for poly in boroughs.values())


def _match_crossing(name: str, crossings: list) -> dict | None:
    for c in crossings:
        for pat in c.get("osm_name_patterns", []):
            if re.search(pat, name or "", re.I):
                return c
    return None


def _build_bridge_decks(inv: Inventory, registry: IdRegistry, crossings: list) -> None:
    g = nx.Graph()
    for s in inv.segments.values():
        if s.bridge:
            g.add_node(s.id)
    by_node = defaultdict(list)
    for s in inv.segments.values():
        if s.bridge:
            by_node[s.from_node].append(s)
            by_node[s.to_node].append(s)
    for segs in by_node.values():
        for a in segs:
            for b in segs:
                if a.id < b.id and a.layer == b.layer:
                    g.add_edge(a.id, b.id)
    groups = [sorted(c) for c in nx.connected_components(g)]
    items = []
    for grp in groups:
        segs = [inv.segments[i] for i in grp]
        key = "deck:" + ":".join(str(w) for w in sorted({s.osm_way_id for s in segs}))
        match = "deck:" + short_hash(":".join(sorted(f"{s.from_node}-{s.to_node}" for s in segs)))
        items.append((key, match))
    ids = registry.assign_batch("bridge_deck", "BRG", items)
    for grp, (key, _) in zip(groups, items):
        segs = [inv.segments[i] for i in grp]
        names = [s.tags.get("bridge:name") or s.name for s in segs]
        name = max(set(names), key=names.count) if names else ""
        crossing = _match_crossing(" ".join(set(names)), crossings)
        deck = BridgeDeck(
            id=ids[key], name=name, crossing_id=crossing["id"] if crossing else None,
            level=segs[0].layer, segment_ids=grp,
            length_m=round(sum(s.length_m for s in segs), 1),
            boroughs=sorted({s.borough for s in segs}),
        )
        inv.bridge_decks[deck.id] = deck
        for s in segs:
            s.bridge_deck_id = deck.id


def _build_ramp_groups(inv: Inventory) -> None:
    g = nx.Graph()
    ramps = [s for s in inv.segments.values() if s.ramp]
    by_node = defaultdict(list)
    for s in ramps:
        g.add_node(s.id)
        by_node[s.from_node].append(s.id)
        by_node[s.to_node].append(s.id)
    for ids_ in by_node.values():
        for a in ids_:
            for b in ids_:
                if a < b:
                    g.add_edge(a, b)
    for comp in nx.connected_components(g):
        comp = sorted(comp)
        rid = "RMP-" + short_hash(":".join(comp))
        inv.ramp_groups[rid] = {"segment_ids": comp,
                                "length_m": round(sum(inv.segments[i].length_m for i in comp), 1)}
        for i in comp:
            inv.segments[i].ramp_group_id = rid


def _vertical_rank(s: Segment) -> float:
    """Relative height hint from tags only (no elevation data)."""
    return s.layer + (0.5 if s.bridge else 0) - (0.5 if s.tunnel else 0)


def _build_grade_separations(inv: Inventory) -> None:
    segs = list(inv.segments.values())
    lines = [_utm_line(s.coords) for s in segs]
    tree = STRtree(lines)
    for i, li in enumerate(lines):
        for j in tree.query(li, predicate="intersects"):
            if j <= i:
                continue
            a, b = segs[i], segs[j]
            inter = li.intersection(lines[j])
            # Remove shared endpoints: touching there is an at-grade junction.
            for n in {a.from_node, a.to_node} & {b.from_node, b.to_node}:
                c = a.coords[0] if n == a.from_node else a.coords[-1]
                inter = inter.difference(Point(lonlat_to_utm(*c)).buffer(0.5))
            if inter.is_empty:
                continue
            pt = inter if inter.geom_type == "Point" else inter.representative_point()
            pair = tuple(sorted((a.id, b.id)))
            lon, lat = utm_to_lonlat(pt.x, pt.y)
            gid = "GSX-" + short_hash(":".join(pair))
            ra, rb = _vertical_rank(a), _vertical_rank(b)
            if ra == rb:
                note = ("crossing without shared node and no layer/bridge/tunnel difference: "
                        "OSM data error or missing junction")
                inv.grade_separations[gid] = GradeSeparation(gid, None, None, a.id, b.id, lon, lat, False, note)
            else:
                up, lo = (a, b) if ra > rb else (b, a)
                inv.grade_separations[gid] = GradeSeparation(gid, up.id, lo.id, a.id, b.id, lon, lat, True)


def _build_components(inv: Inventory) -> None:
    g = nx.MultiGraph()
    for s in inv.segments.values():
        if s.scope == "in_scope":
            g.add_edge(s.from_node, s.to_node, sid=s.id)
    for k, comp in enumerate(sorted(nx.connected_components(g), key=len, reverse=True)):
        for _, _, d in g.subgraph(comp).edges(data=True):
            inv.segments[d["sid"]].component = k
