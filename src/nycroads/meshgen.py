"""Road, junction and bridge-deck geometry (simulator-agnostic triangle meshes).

Coordinates produced here are UTM-18N x/y plus simulator height z. The glTF
writer converts them into each tile's local ENU frame.

Watertightness strategy:
* Each segment ribbon is trimmed back from its junctions.
* A junction pad is built whose boundary vertices ARE the trimmed ribbon end
  vertices (shared positions, same heights), so there are no gaps, no
  overlapping coplanar surfaces and no z-fighting at intersections.
* At 2-way 'connection' nodes both ribbons use one mitred end normal.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import Polygon

from . import config as C

DECK_THICKNESS_M = 1.2
BARRIER_H_M = 0.81      # NJ/F-shape concrete barrier nominal height (32 in)
BARRIER_W_M = 0.25
SKIRT_DEPTH_M = 0.6
MARKING_LIFT_M = 0.02
MARKING_W_M = 0.12


@dataclass
class Mesh:
    material: str
    collision: bool
    vertices: list = field(default_factory=list)   # [(x, y, z)]
    triangles: list = field(default_factory=list)  # [(i, j, k)] counter-clockwise seen from above/outside

    def add(self, verts, tris):
        base = len(self.vertices)
        self.vertices.extend(verts)
        self.triangles.extend((a + base, b + base, c + base) for a, b, c in tris)

    def merge(self, other: "Mesh"):
        self.add(other.vertices, other.triangles)


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def _left_normal(t):
    return np.array([-t[1], t[0]])


def _tangents(xy):
    t = np.zeros_like(xy)
    t[0] = xy[1] - xy[0]
    t[-1] = xy[-1] - xy[-2]
    t[1:-1] = xy[2:] - xy[:-2]
    return np.array([_unit(v) for v in t])


def _cut(s, xy, z, s0, s1):
    """Sub-profile between distances s0..s1 with interpolated end stations."""
    keep = (s > s0) & (s < s1)
    ss = np.concatenate([[s0], s[keep], [s1]])
    xs = np.interp(ss, s, xy[:, 0])
    ys = np.interp(ss, s, xy[:, 1])
    zs = np.interp(ss, s, z)
    return ss, np.column_stack([xs, ys]), zs


def ribbon(xy, z, width, start_normal=None, end_normal=None):
    """Left/right edge points of a road ribbon. Returns (left[N,3], right[N,3])."""
    t = _tangents(xy)
    n = np.array([_left_normal(v) for v in t])
    # mitre interior vertices so width stays constant through bends
    for i in range(1, len(xy) - 1):
        a, b = _left_normal(_unit(xy[i] - xy[i - 1])), _left_normal(_unit(xy[i + 1] - xy[i]))
        m = _unit(a + b)
        cosang = max(np.dot(m, a), 0.5)  # clamp mitre length at 2x
        n[i] = m / cosang
    if start_normal is not None:
        n[0] = start_normal
    if end_normal is not None:
        n[-1] = end_normal
    h = width / 2
    left = np.column_stack([xy + n * h, z])
    right = np.column_stack([xy - n * h, z])
    return left, right


def strip_mesh(left, right, material, collision):
    m = Mesh(material, collision)
    N = len(left)
    verts = [tuple(p) for p in left] + [tuple(p) for p in right]
    tris = []
    for i in range(N - 1):
        l0, l1, r0, r1 = i, i + 1, N + i, N + i + 1
        tris += [(l0, r0, r1), (l0, r1, l1)]
    m.add(verts, tris)
    return m


def wall_mesh(edge, depth, material, collision=False, outward_left=True):
    """Vertical skirt hanging ``depth`` below a polyline edge."""
    top = [tuple(p) for p in edge]
    bot = [(p[0], p[1], p[2] - depth) for p in edge]
    m = Mesh(material, collision)
    N = len(top)
    tris = []
    for i in range(N - 1):
        a, b, c, d = i, i + 1, N + i, N + i + 1
        tris += [(a, c, d), (a, d, b)] if outward_left else [(a, b, d), (a, d, c)]
    m.add(top + bot, tris)
    return m


def barrier_mesh(edge_xy, edge_z, inward_dir_sign, normals, material="concrete_barrier"):
    """Simple box-section barrier along one deck edge (collision enabled)."""
    m = Mesh(material, True)
    inner = edge_xy + normals * (inward_dir_sign * BARRIER_W_M)
    for base_xy, sign in ((edge_xy, 1), (inner, -1)):
        e = np.column_stack([base_xy, edge_z + BARRIER_H_M])
        m.merge(wall_mesh(e, BARRIER_H_M, material, True, outward_left=(sign * inward_dir_sign) < 0))
    top = strip_mesh(np.column_stack([edge_xy, edge_z + BARRIER_H_M]),
                     np.column_stack([inner, edge_z + BARRIER_H_M]), material, True)
    m.merge(top)
    return m


def marking_meshes(xy, z, width, oneway: str, lanes: int | None):
    """Edge lines + centre line following the surface (no floating)."""
    out = []
    left, right = ribbon(xy, z + MARKING_LIFT_M, width - 0.6)
    for edge in (left, right):
        l2, r2 = ribbon(edge[:, :2], edge[:, 2], MARKING_W_M)
        out.append(strip_mesh(l2, r2, "marking_white", False))
    if oneway == "both":
        for off in (-0.1, 0.1):
            l, r = ribbon(xy, z + MARKING_LIFT_M, 2 * abs(off) + MARKING_W_M)
            edge = l if off > 0 else r
            l2, r2 = ribbon(edge[:, :2], edge[:, 2], MARKING_W_M)
            out.append(strip_mesh(l2, r2, "marking_yellow", False))
    return out


# ----------------------------------------------------------------- junction pads

def junction_trim(arms):
    """Trim distance so neighbouring arms' ribbons do not overlap.

    ``arms``: list of (direction_unit_vec, half_width). Returns metres.
    """
    if len(arms) < 3:
        return 0.0
    ang = sorted((math.atan2(d[1], d[0]), hw) for d, hw in arms)
    r = max(hw for _, hw in ang)
    for k in range(len(ang)):
        a0, h0 = ang[k]
        a1, h1 = ang[(k + 1) % len(ang)]
        theta = (a1 - a0) % (2 * math.pi)
        theta = max(theta, math.radians(10))
        if theta < math.pi:
            r = max(r, max(h0, h1) / math.tan(theta / 2))
    return min(r + 0.5, 40.0)


def junction_pad(arm_edges, material, collision=True, skirt_depth: float = SKIRT_DEPTH_M):
    """Polygon pad from arm end-edges.

    ``arm_edges``: list of (angle, cw_point(x,y,z), ccw_point(x,y,z)) sorted or not.
    Triangulated without Steiner points so every vertex is a shared ribbon vertex.
    """
    arm_edges = sorted(arm_edges, key=lambda a: a[0])
    ring = []
    for _, cw, ccw in arm_edges:
        ring += [tuple(cw), tuple(ccw)]
    poly2d = Polygon([(p[0], p[1]) for p in ring])
    if not poly2d.is_valid or poly2d.area <= 0:
        return None
    zmap = {(round(p[0], 4), round(p[1], 4)): p[2] for p in ring}
    tris = shapely.constrained_delaunay_triangles(poly2d)
    m = Mesh(material, collision)
    for tri in shapely.get_parts(tris):
        pts = list(tri.exterior.coords)[:3]
        try:
            v = [(x, y, zmap[(round(x, 4), round(y, 4))]) for x, y in pts]
        except KeyError:
            return None
        # orient counter-clockwise from above
        if (v[1][0] - v[0][0]) * (v[2][1] - v[0][1]) - (v[1][1] - v[0][1]) * (v[2][0] - v[0][0]) < 0:
            v[1], v[2] = v[2], v[1]
        m.add(v, [(0, 1, 2)])
    # skirts along the open sides between arms (curb returns) so no gap to terrain shows
    if skirt_depth > 0:
        for k in range(len(arm_edges)):
            a = arm_edges[k][2]
            b = arm_edges[(k + 1) % len(arm_edges)][1]
            m.merge(wall_mesh(np.array([a, b]), skirt_depth, material + "_skirt", outward_left=False))
    return m


# ----------------------------------------------------------------- network builder

@dataclass
class BuildResult:
    meshes_by_segment: dict          # segment_id -> list[Mesh]
    pads_by_junction: dict           # junction_id -> Mesh
    issues: list                     # [{"id", "type", ...}]
    trims: dict                      # (segment_id, 'from'|'to') -> metres


def build_network(inv, profiles: dict, segment_ids=None) -> BuildResult:
    """Generate surfaces for the given segments (default: all with profiles)."""
    ids = [i for i in (segment_ids or profiles.keys()) if i in profiles]
    idset = set(ids)
    issues = []

    # arms per junction
    arms = defaultdict(list)  # node -> [(seg_id, end, dir, half_width)]
    for sid in ids:
        p, seg = profiles[sid], inv.segments[sid]
        xy = p.xy_utm
        d0 = _unit(xy[min(1, len(xy) - 1)] - xy[0])
        d1 = _unit(xy[max(len(xy) - 2, 0)] - xy[-1])
        arms[seg.from_node].append((sid, "from", d0, seg.width_m / 2))
        arms[seg.to_node].append((sid, "to", d1, seg.width_m / 2))

    trims, end_normals = {}, {}
    for node, a in arms.items():
        if len(a) >= 3:
            r = junction_trim([(d, hw) for _, _, d, hw in a])
            for sid, end, _, _ in a:
                L = profiles[sid].s[-1]
                rr = r
                if r > 0.45 * L:
                    rr = 0.45 * L
                    issues.append({"id": sid, "type": "junction_trim_conflict", "node": node,
                                   "needed_m": round(r, 2), "segment_length_m": round(float(L), 2)})
                trims[(sid, end)] = rr
        elif len(a) == 2:
            (s1, e1, d1, _), (s2, e2, d2, _) = a
            # outward directions d1, d2 point away from node; a through-road has d1 ~ -d2
            t = _unit(d2 - d1)  # direction of travel from arm1 into arm2
            n = _left_normal(t)
            # each ribbon's own 'left' depends on its orientation
            end_normals[(s1, e1)] = n if e1 == "to" else -n
            end_normals[(s2, e2)] = n if e2 == "from" else -n

    meshes, pad_edges = {}, defaultdict(list)
    for sid in ids:
        p, seg = profiles[sid], inv.segments[sid]
        lift = 0.0 if (seg.bridge or p.source.startswith("deck")) else C.GROUND_ROAD_LIFT_M
        s0 = trims.get((sid, "from"), 0.0)
        s1 = p.s[-1] - trims.get((sid, "to"), 0.0)
        ss, xy, z = _cut(p.s, p.xy_utm, p.z_sim + lift, s0, s1)
        nf, nt = end_normals.get((sid, "from")), end_normals.get((sid, "to"))
        left, right = ribbon(xy, z, seg.width_m, nf, nt)
        parts = [strip_mesh(left, right, "concrete_deck" if seg.bridge else "asphalt", True)]
        if seg.bridge:
            n = np.array([_left_normal(t) for t in _tangents(xy)])
            parts.append(barrier_mesh(left[:, :2], left[:, 2], -1, n))
            parts.append(barrier_mesh(right[:, :2], right[:, 2], +1, n))
            under_l = left.copy(); under_l[:, 2] -= DECK_THICKNESS_M
            under_r = right.copy(); under_r[:, 2] -= DECK_THICKNESS_M
            parts.append(strip_mesh(under_r, under_l, "concrete_deck_underside", False))
            parts.append(wall_mesh(left, DECK_THICKNESS_M, "concrete_deck_edge", outward_left=True))
            parts.append(wall_mesh(right, DECK_THICKNESS_M, "concrete_deck_edge", outward_left=False))
        else:
            parts.append(wall_mesh(left, SKIRT_DEPTH_M, "asphalt_skirt", outward_left=True))
            parts.append(wall_mesh(right, SKIRT_DEPTH_M, "asphalt_skirt", outward_left=False))
        parts += marking_meshes(xy, z, seg.width_m, seg.oneway, None)
        meshes[sid] = parts
        # end edges for pads: (outward angle, cw point, ccw point) relative to the node
        for end, idx in (("from", 0), ("to", -1)):
            node = seg.from_node if end == "from" else seg.to_node
            if (sid, end) not in trims:
                continue
            d = _unit((xy[1] - xy[0]) if end == "from" else (xy[-2] - xy[-1]))
            ang = math.atan2(d[1], d[0])
            L, R = left[idx], right[idx]
            # For a 'from' end the ribbon's left lies CCW of the outward direction.
            cw, ccw = (R, L) if end == "from" else (L, R)
            pad_edges[node].append((ang, cw, ccw))

    pads = {}
    node_to_jct = {j.osm_node_id: j.id for j in inv.junctions.values()}
    for node, edges in pad_edges.items():
        if len(edges) < 3:
            continue
        mat = "concrete_deck" if any(inv.segments[a[0]].bridge for a in arms[node]) else "asphalt"
        pad = junction_pad(edges, mat)
        jid = node_to_jct.get(node, f"node:{node}")
        if pad is None:
            issues.append({"id": jid, "type": "junction_pad_invalid", "node": node})
        else:
            pads[jid] = pad
    # arms leading to segments outside this build are reported, not silently dropped
    for node, a in arms.items():
        j = node_to_jct.get(node)
        if j and len(inv.junctions[j].segment_ids) != len(a):
            missing = sorted(set(inv.junctions[j].segment_ids) - {x[0] for x in a})
            if missing and any(m not in idset for m in missing):
                issues.append({"id": j, "type": "open_edge", "missing_segments": missing})
    return BuildResult(meshes, pads, issues, trims)
