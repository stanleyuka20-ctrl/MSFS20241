"""Mesh primitives (simulator-agnostic triangle meshes) used by surface.py.

Coordinates are UTM-18N x/y plus simulator height z. The glTF writer converts
them into each tile's local ENU frame. Road surfaces themselves are built by
surface.py (continuous surface per level); this module provides the Mesh type,
strips, walls/skirts, barriers and markings.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


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
