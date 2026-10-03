"""Continuous road surfaces per level ("surface groups").

Replaces per-segment ribbons + per-node junction pads, which cannot represent
real NYC junction clusters (dual carriageways, acute merges, very short
connector segments).

* A surface group is either one bridge deck (``("deck", deck_id)``) or all
  ground roads of one OSM layer (``("ground", layer)``).
* Group footprint = union of the segments' road polygons (flat caps) plus a
  disc at every junction inside the group (fills the corners).
* Where two groups meet (bridge abutments), the lower-priority group is clipped
  by the other near the shared node, so surfaces never overlap.
* The footprint is cut into cells, its boundary densified, and triangulated
  with a constrained Delaunay triangulation (no Steiner points). Vertex height
  is a deterministic function of (x, y): inverse-distance blend of nearby
  centreline profiles of the same group. Cells therefore share identical
  vertices along their cuts (watertight across cells and tiles).
* Height conflicts (blended profiles disagreeing by > 0.3 m inside a road)
  are reported, never hidden.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import shapely
import shapely.geometry.polygon  # noqa: F401  (orient)
from shapely.geometry import LineString, MultiPoint, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from . import config as C
from .meshgen import (BARRIER_H_M, BARRIER_W_M, DECK_THICKNESS_M, SKIRT_DEPTH_M, Mesh,
                      marking_meshes, strip_mesh, wall_mesh)

CELL_M = 250.0
DENSIFY_M = 4.0
HEIGHT_CONFLICT_M = 0.3
ROUND = 4


def group_key(seg):
    return ("deck", seg.bridge_deck_id) if seg.bridge else ("ground", seg.layer)


@dataclass
class Group:
    key: tuple
    seg_ids: list
    footprint: object = None
    lines: list = field(default_factory=list)   # LineString per segment (UTM)
    tree: object = None
    shared_nodes: set = field(default_factory=set)
    open_nodes: set = field(default_factory=set)
    skirt_depth: float = SKIRT_DEPTH_M


@dataclass
class SurfaceResult:
    meshes: list                 # [(cell_center_xy, Mesh)]
    groups: dict
    issues: list
    footprints: dict             # key -> polygon
    heights: dict = field(default_factory=dict)   # key -> HeightField


class HeightField:
    """z(x, y) for one group: inverse-distance blend of nearby centreline profiles."""

    def __init__(self, group: Group, profiles, inv):
        self.g = group
        self.lift = 0.0 if group.key[0] == "deck" else C.GROUND_ROAD_LIFT_M
        self.prof = [profiles[s] for s in group.seg_ids]
        self.hw = np.array([inv.segments[s].width_m / 2 for s in group.seg_ids])
        self.cache = {}
        self.conflicts = []

    def __call__(self, x: float, y: float) -> float:
        k = (round(x, ROUND), round(y, ROUND))
        if k in self.cache:
            return self.cache[k]
        p = Point(x, y)
        idx = self.g.tree.query(p.buffer(float(self.hw.max()) + 3.0))
        zs, ws, inside = [], [], []
        for i in idx:
            line = self.g.lines[i]
            d = line.distance(p)
            pr = self.prof[i]
            z = float(np.interp(line.project(p), pr.s, pr.z_sim))
            zs.append(z)
            ws.append(1.0 / (d + 0.25) ** 2)
            if d <= self.hw[i] + 0.5:
                inside.append(z)
        if not zs:
            # far from every centreline (rare: inside a large junction disc): nearest profile
            dists = [ln.distance(p) for ln in self.g.lines]
            i = int(np.argmin(dists))
            z = float(np.interp(self.g.lines[i].project(p), self.prof[i].s, self.prof[i].z_sim))
        else:
            z = float(np.dot(zs, ws) / np.sum(ws))
        if len(inside) >= 2 and max(inside) - min(inside) > HEIGHT_CONFLICT_M:
            self.conflicts.append((x, y, max(inside) - min(inside)))
        z += self.lift
        self.cache[k] = z
        return z


def _priority(key) -> int:
    # decks keep their footprint at shared nodes; separated ground pieces beat plain ground
    return 0 if key[0] == "deck" else 1 if len(key) > 2 else 2


SAME_LEVEL_M = 0.5      # side-by-side roads closer than this in height may share one blended surface
MIN_OVERLAP_M2 = 1.0


def _z_on(profile, line, pt) -> float:
    return float(np.interp(line.project(pt), profile.s, profile.z_sim))


def _midline_split(la: LineString, lb: LineString, overlap):
    """Split ``overlap`` into the parts closer to la and to lb (Voronoi of densified centrelines)."""
    region = overlap.buffer(30.0)
    pts = []
    for ln in (la, lb):
        part = ln.intersection(region)
        part = part if not part.is_empty else ln
        dense = shapely.segmentize(part, 1.0)
        pts.append([c for g in getattr(dense, "geoms", [dense]) for c in g.coords])
    seen = set()
    for k in range(2):   # GEOS needs unique sites; drop repeats (shared vertices, touching lines)
        uniq = []
        for c in pts[k]:
            key = (round(c[0], 3), round(c[1], 3))
            if key not in seen:
                seen.add(key)
                uniq.append(key)
        pts[k] = uniq
    na = len(pts[0])
    cells = shapely.voronoi_polygons(MultiPoint(pts[0] + pts[1]), extend_to=overlap.buffer(5.0), ordered=True)
    cells = list(shapely.get_parts(cells))
    near_a = unary_union(cells[:na])
    return overlap.intersection(near_a), overlap.difference(near_a)


_RANK = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}


def _assign_groups(inv, profiles, ids, polys, lines):
    """Resolve roads whose footprints overlap away from any shared junction.

    Real data has many such pairs: twin carriageways on one structure, a ramp
    peeling off beside a street, an expressway in a trench beside the street
    above it, and over-estimated default widths. For every such pair:

    * the overlap is split along the Voronoi midline between the centrelines
      (each road keeps the half nearer to it; no surface overlap remains), and
    * if the two are in the same surface group but differ in height by more than
      SAME_LEVEL_M, the HIGHER road (with its connected higher neighbours) becomes
      a separate surface whose skirt reaches down to the lower road (a wall).

    Decks are never merged: twin decks stay separate surfaces with barriers on
    their shared median edge.
    Returns (key_of, skirt_depth_by_key, trimmed polys, partner map).
    """
    key_of = {sid: group_key(inv.segments[sid]) for sid in ids}
    order = list(ids)
    tree = STRtree([polys[s] for s in order])
    node_disc = {}
    for sid in ids:
        seg = inv.segments[sid]
        for n, xy in ((seg.from_node, profiles[sid].xy_utm[0]), (seg.to_node, profiles[sid].xy_utm[-1])):
            r = seg.width_m / 2 + 2.0
            if n not in node_disc or node_disc[n][1] < r:
                node_disc[n] = (xy, r)
    raised = {}
    same_level = []
    partners = defaultdict(set)
    cuts = defaultdict(list)
    for i, a in enumerate(order):
        sa = inv.segments[a]
        for j in tree.query(polys[a], predicate="intersects"):
            if j <= i:
                continue
            b = order[j]
            sb = inv.segments[b]
            inter = polys[a].intersection(polys[b])
            shared = {sa.from_node, sa.to_node} & {sb.from_node, sb.to_node}
            for n in shared:
                xy, r = node_disc[n]
                inter = inter.difference(Point(xy).buffer(r))
            if inter.is_empty or inter.area < MIN_OVERLAP_M2:
                continue
            c = inter.representative_point()
            za, zb = _z_on(profiles[a], lines[a], c), _z_on(profiles[b], lines[b], c)
            same_group = key_of[a] == key_of[b]
            if same_group and abs(za - zb) <= SAME_LEVEL_M:
                same_level.append((a, b))     # same level, same surface: blending is correct
                continue
            part_a, part_b = _midline_split(lines[a], lines[b], inter)
            cuts[a].append(part_b)            # a loses the half nearer to b
            cuts[b].append(part_a)
            partners[a].add(b)
            partners[b].add(a)
            if same_group and key_of[a][0] == "ground":
                hi = a if za > zb else b
                raised[hi] = max(raised.get(hi, 0.0), abs(za - zb))
    trimmed = dict(polys)
    for sid, cs in cuts.items():
        trimmed[sid] = polys[sid].difference(unary_union(cs))

    rp = {}

    def rfind(x):
        while rp.get(x, x) != x:
            x = rp[x]
        return x

    by_node = defaultdict(list)
    for sid in raised:
        for n in (inv.segments[sid].from_node, inv.segments[sid].to_node):
            by_node[n].append(sid)
    for sids in by_node.values():
        for o in sids[1:]:
            ra, rb = rfind(sids[0]), rfind(o)
            if ra != rb:
                rp[rb] = ra
    for a, b in same_level:          # same-level neighbours of raised roads join the same raised piece
        if a in raised and b in raised:
            ra, rb = rfind(a), rfind(b)
            if ra != rb:
                rp[rb] = ra
    depth = {}
    for sid in raised:
        k = ("ground", inv.segments[sid].layer, f"raised-{rfind(sid)}")
        key_of[sid] = k
        depth[k] = max(depth.get(k, SKIRT_DEPTH_M), raised[sid] + 0.5)
    return key_of, depth, trimmed, partners


def _group_footprints(inv, profiles, ids):
    lines = {sid: LineString(profiles[sid].xy_utm) for sid in ids}
    polys = {sid: lines[sid].buffer(inv.segments[sid].width_m / 2, cap_style="flat",
                                    join_style="mitre", mitre_limit=2.0) for sid in ids}
    key_of, depth, trimmed, partners = _assign_groups(inv, profiles, ids, polys, lines)
    groups: dict = {}
    for sid in ids:
        g = groups.setdefault(key_of[sid], Group(key_of[sid], []))
        g.seg_ids.append(sid)
        g.lines.append(lines[sid])
    for k, d in depth.items():
        groups[k].skirt_depth = d
    node_groups = defaultdict(set)
    node_arms = defaultdict(list)   # node -> [(group key, half width)]
    for key, g in groups.items():
        for sid in g.seg_ids:
            seg = inv.segments[sid]
            for n in (seg.from_node, seg.to_node):
                node_groups[n].add(key)
                node_arms[n].append((key, seg.width_m / 2))
    built = set(ids)
    for key, g in groups.items():
        discs = []
        for sid in g.seg_ids:
            seg = inv.segments[sid]
            for n, xy in ((seg.from_node, profiles[sid].xy_utm[0]), (seg.to_node, profiles[sid].xy_utm[-1])):
                if len([1 for k, _ in node_arms[n] if k == key]) >= 2 or len(node_groups[n]) >= 2:
                    discs.append(Point(xy).buffer(max(hw for _, hw in node_arms[n]), quad_segs=8))
                if len(node_groups[n]) >= 2:
                    g.shared_nodes.add(n)
                if any(o not in built for o in _segments_at(inv, n)):
                    g.open_nodes.add(n)
        fp = unary_union([trimmed[s] for s in g.seg_ids] + discs)
        # junction discs must not grow back into a partner road of another group
        others = [trimmed[p] for s in g.seg_ids for p in partners[s] if key_of[p] != key]
        if others:
            fp = fp.difference(unary_union(others))
        g.footprint = fp
        g.tree = STRtree(g.lines)
    # Where two groups overlap at (nearly) the same height - abutments, ramp joins, slivers left
    # by junction discs - the lower-priority group gives the area up. Overlaps with real
    # vertical separation (a road under a deck) are kept.
    order = sorted(groups, key=lambda k: (_priority(k), str(k)))
    for i, hi in enumerate(order):
        for lo in order[i + 1:]:
            G_hi, G_lo = groups[hi], groups[lo]
            if not G_hi.footprint.intersects(G_lo.footprint):
                continue
            inter = G_hi.footprint.intersection(G_lo.footprint)
            cut = []
            for part in getattr(inter, "geoms", [inter]):
                if part.is_empty or part.area < 0.01 or part.geom_type not in ("Polygon", "MultiPolygon"):
                    continue
                c = part.representative_point()
                zh = _group_z(G_hi, profiles, c)
                zl = _group_z(G_lo, profiles, c)
                if abs(zh - zl) < 2.0:
                    cut.append(part)
            if cut:
                G_lo.footprint = G_lo.footprint.difference(unary_union(cut).buffer(0.01))
    return groups


def _group_z(g: Group, profiles, pt) -> float:
    """Height of the group's nearest centreline at ``pt``."""
    i = min(range(len(g.lines)), key=lambda k: g.lines[k].distance(pt))
    return _z_on(profiles[g.seg_ids[i]], g.lines[i], pt)


_SEGS_AT: dict = {}


def _segments_at(inv, node):
    if id(inv) not in _SEGS_AT:
        m = defaultdict(list)
        for s in inv.segments.values():
            m[s.from_node].append(s.id)
            m[s.to_node].append(s.id)
        _SEGS_AT.clear()
        _SEGS_AT[id(inv)] = m
    return _SEGS_AT[id(inv)].get(node, [])


def _node_xy(inv, profiles, g, n):
    for sid in g.seg_ids:
        seg = inv.segments[sid]
        if seg.from_node == n:
            return profiles[sid].xy_utm[0]
        if seg.to_node == n:
            return profiles[sid].xy_utm[-1]
    raise KeyError(n)


def _polys(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]


def _triangulate(poly: Polygon, hf: HeightField, material: str, collision: bool) -> Mesh:
    poly = shapely.segmentize(poly, DENSIFY_M)
    tris = shapely.constrained_delaunay_triangles(poly)
    m = Mesh(material, collision)
    index = {}
    verts, faces = [], []
    for t in shapely.get_parts(tris):
        cs = list(t.exterior.coords)[:3]
        ids = []
        for x, y in cs:
            k = (round(x, ROUND), round(y, ROUND))
            if k not in index:
                index[k] = len(verts)
                verts.append((x, y, hf(x, y)))
            ids.append(index[k])
        a, b, c = (verts[i] for i in ids)
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < 0:
            ids[1], ids[2] = ids[2], ids[1]
        faces.append(tuple(ids))
    m.add(verts, faces)
    return m


def _boundary_lines(poly: Polygon):
    yield poly.exterior
    yield from poly.interiors


def build_surfaces(inv, profiles: dict, ids=None, cell_m: float = CELL_M) -> SurfaceResult:
    ids = [i for i in (ids or profiles.keys()) if i in profiles]
    groups = _group_footprints(inv, profiles, ids)
    meshes, issues, footprints, heights = [], [], {}, {}
    for key, g in sorted(groups.items(), key=lambda kv: str(kv[0])):
        hf = HeightField(g, profiles, inv)
        heights[key] = hf
        deck = key[0] == "deck"
        mat = "concrete_deck" if deck else "asphalt"
        fp = g.footprint
        footprints[key] = fp
        if fp.is_empty:
            continue
        minx, miny, maxx, maxy = fp.bounds
        for ix in range(int(minx // cell_m), int(maxx // cell_m) + 1):
            for iy in range(int(miny // cell_m), int(maxy // cell_m) + 1):
                cell = box(ix * cell_m, iy * cell_m, (ix + 1) * cell_m, (iy + 1) * cell_m)
                part = fp.intersection(cell)
                for poly in _polys(part):
                    if poly.area < 0.05:
                        continue
                    centre = ((ix + 0.5) * cell_m, (iy + 0.5) * cell_m)
                    top = _triangulate(poly, hf, mat, True)
                    meshes.append((centre, top))
                    if deck:
                        under = Mesh("concrete_deck_underside", False)
                        under.add([(x, y, z - DECK_THICKNESS_M) for x, y, z in top.vertices],
                                  [(a, c, b) for a, b, c in top.triangles])
                        meshes.append((centre, under))
        # skirts / deck edges / barriers along the true footprint boundary
        keep_open = unary_union([Point(_node_xy(inv, profiles, g, n)).buffer(
            max(inv.segments[s].width_m for s in g.seg_ids) / 2 + 1.0)
            for n in (g.shared_nodes | g.open_nodes)]) if (g.shared_nodes | g.open_nodes) else None
        for poly in _polys(fp):
            poly = shapely.geometry.polygon.orient(poly, sign=1.0)   # road surface on the LEFT of every ring
            for ring in _boundary_lines(poly):
                ring = shapely.segmentize(LineString(ring.coords), DENSIFY_M)
                pts = list(ring.coords)
                if len(pts) < 2:
                    continue
                xy = np.array(pts)
                z = np.array([hf(x, y) for x, y in pts])
                edge = np.column_stack([xy, z])
                centre = tuple(xy.mean(0))
                outward_left = False
                if deck:
                    meshes.append((centre, wall_mesh(edge, DECK_THICKNESS_M, "concrete_deck_edge",
                                                     outward_left=outward_left)))
                    for run in _runs_outside(xy, keep_open):
                        meshes.append((centre, _barrier(edge[run[0]:run[1] + 1], outward_left)))
                else:
                    meshes.append((centre, wall_mesh(edge, g.skirt_depth, "asphalt_skirt",
                                                     outward_left=outward_left)))
        for x, y, dz in hf.conflicts:
            # > 1 m: two different-level roads merged into one surface (error);
            # otherwise a warped (non-planar) junction, smoothly blended (warning)
            issues.append({"id": f"{key[0]}:{key[1]}", "type": "height_conflict" if dz > 1.0 else "junction_warp",
                           "x": round(x, 1), "y": round(y, 1), "dz_m": round(dz, 2),
                           "segments": _segments_near(g, x, y)})
    meshes += _markings(inv, profiles, ids, groups)
    return SurfaceResult(meshes, groups, issues, footprints, heights)


def _segments_near(g: Group, x, y, r: float = 15.0) -> list:
    return [g.seg_ids[i] for i in g.tree.query(Point(x, y).buffer(r))]


def _runs_outside(xy: np.ndarray, zone) -> list[tuple[int, int]]:
    """Index ranges of consecutive boundary points outside ``zone`` (where barriers go)."""
    if zone is None:
        return [(0, len(xy) - 1)]
    inside = shapely.contains_xy(zone, xy[:, 0], xy[:, 1])
    runs, start = [], None
    for i, v in enumerate(inside):
        if not v and start is None:
            start = i
        elif v and start is not None:
            if i - 1 > start:
                runs.append((start, i - 1))
            start = None
    if start is not None and len(xy) - 1 > start:
        runs.append((start, len(xy) - 1))
    return runs


def _barrier(edge: np.ndarray, outward_left: bool) -> Mesh:
    """Box-section barrier standing on the deck along an edge polyline (inside the edge)."""
    xy = edge[:, :2]
    t = np.gradient(xy, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    left = np.column_stack([-t[:, 1], t[:, 0]])
    inward = -left if outward_left else left
    inner = xy + inward * BARRIER_W_M
    m = Mesh("concrete_barrier", True)
    top_o = np.column_stack([xy, edge[:, 2] + BARRIER_H_M])
    top_i = np.column_stack([inner, edge[:, 2] + BARRIER_H_M])
    m.merge(wall_mesh(top_o, BARRIER_H_M, "concrete_barrier", True, outward_left=outward_left))
    m.merge(wall_mesh(top_i, BARRIER_H_M, "concrete_barrier", True, outward_left=not outward_left))
    m.merge(strip_mesh(top_o, top_i, "concrete_barrier", True) if outward_left else
            strip_mesh(top_i, top_o, "concrete_barrier", True))
    return m


def _markings(inv, profiles, ids, groups) -> list:
    """Edge and centre lines, kept clear of junction areas (where lanes cross)."""
    from .meshgen import _cut
    out = []
    deg = defaultdict(int)
    for sid in ids:
        seg = inv.segments[sid]
        deg[seg.from_node] += 1
        deg[seg.to_node] += 1
    for sid in ids:
        seg, p = inv.segments[sid], profiles[sid]
        L = float(p.s[-1])
        clear = seg.width_m * 0.75
        s0 = clear if deg[seg.from_node] >= 3 else 0.0
        s1 = L - (clear if deg[seg.to_node] >= 3 else 0.0)
        if s1 - s0 < 5.0:
            continue
        lift = 0.0 if seg.bridge else C.GROUND_ROAD_LIFT_M
        ss, xy, z = _cut(p.s, p.xy_utm, p.z_sim + lift, s0, s1)
        centre = tuple(xy[len(xy) // 2])
        for mk in marking_meshes(xy, z, seg.width_m, seg.oneway, None):
            out.append((centre, mk))
    return out
