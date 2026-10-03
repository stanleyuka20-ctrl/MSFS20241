"""glTF 2.0 writer for tile models.

Produces standard glTF (validated structurally with pygltflib). MSFS-specific
extensions are injected only from config/msfs_gltf.json so that every
simulator-specific name lives in one reviewed, version-stamped file.
"""
from __future__ import annotations

import base64
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pygltflib as G

from .geo import ENUFrame, utm_to_lonlat
from .meshgen import Mesh


def load_msfs_config(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def _axis_matrix(mapping: dict) -> np.ndarray:
    basis = {"east": 0, "north": 1, "up": 2}
    M = np.zeros((3, 3))
    for row, axis in enumerate(("x", "y", "z")):
        spec = mapping[axis]
        sign = -1.0 if spec.startswith("-") else 1.0
        M[row, basis[spec.lstrip("-")]] = sign
    if abs(np.linalg.det(M) - 1.0) > 1e-9:
        raise ValueError("axis mapping must be a proper rotation (det +1) to keep triangle winding")
    return M


def to_local(meshes: list[Mesh], frame: ENUFrame, z_origin: float, axis: np.ndarray):
    """Convert mesh vertices (UTM x, y, sim z) into the tile's glTF frame."""
    out = []
    for m in meshes:
        v = np.asarray(m.vertices, float)
        if len(v) == 0:
            continue
        lon, lat = utm_to_lonlat(v[:, 0], v[:, 1])
        # z is treated as height above the tile datum; the geoid/ellipsoid offset
        # changes horizontal ENU positions by < 1e-5 m at tile scale.
        e, n, u = frame.from_geodetic(lon, lat, v[:, 2] - z_origin)
        local = (axis @ np.vstack([e, n, u])).T
        out.append((m, local))
    return out


def _normals(pos: np.ndarray, tris: np.ndarray) -> np.ndarray:
    n = np.zeros_like(pos)
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return (n / ln).astype(np.float32)


class _Buf:
    def __init__(self):
        self.data = bytearray()

    def add(self, arr: np.ndarray) -> tuple[int, int]:
        while len(self.data) % 4:
            self.data.append(0)
        off = len(self.data)
        self.data.extend(arr.tobytes())
        return off, arr.nbytes


def write_tile_gltf(path: Path, local_meshes, cfg: dict, embed: bool = False) -> dict:
    """Write one tile model: a visual node (all non-collision materials) and,
    separately, a collision node. Returns stats."""
    path.parent.mkdir(parents=True, exist_ok=True)
    gl = G.GLTF2(asset=G.Asset(version="2.0", generator="nycroads"))
    buf = _Buf()
    mat_index = {}
    used_ext = set()

    def material(name: str, collision: bool) -> int:
        key = ("collision" if collision else name)
        if key in mat_index:
            return mat_index[key]
        spec = cfg["materials"].get(key, cfg["materials"]["asphalt"])
        m = G.Material(name=key, doubleSided=False,
                       pbrMetallicRoughness=G.PbrMetallicRoughness(
                           baseColorFactor=spec["baseColor"], metallicFactor=spec["metallic"],
                           roughnessFactor=spec["roughness"]))
        ext = dict(cfg.get("collision_material_extensions", {})) if collision else \
            dict(cfg.get("material_extensions", {}).get(key, {}))
        if ext:
            m.extensions = ext
            used_ext.update(ext)
        gl.materials.append(m)
        mat_index[key] = len(gl.materials) - 1
        return mat_index[key]

    groups = {"visual": defaultdict(list), "collision": defaultdict(list)}
    for m, local in local_meshes:
        tris = np.asarray(m.triangles, np.uint32)
        groups["visual"][m.material].append((local, tris))
        if m.collision:
            groups["collision"]["collision"].append((local, tris))

    stats = {"triangles_visual": 0, "triangles_collision": 0, "vertices": 0}
    for kind in ("visual", "collision"):
        prims = []
        for matname, parts in sorted(groups[kind].items()):
            pos_list, idx_list, base = [], [], 0
            for local, tris in parts:
                pos_list.append(local)
                idx_list.append(tris + base)
                base += len(local)
            pos = np.concatenate(pos_list).astype(np.float32)
            idx = np.concatenate(idx_list).astype(np.uint32)
            nor = _normals(pos, idx.reshape(-1, 3))
            # planar world-space UVs (4 m repeat) from the horizontal axes
            uv = (pos[:, [0, 2]] / 4.0).astype(np.float32)
            attrs = {}
            for name, arr, typ in (("POSITION", pos, G.VEC3), ("NORMAL", nor, G.VEC3), ("TEXCOORD_0", uv, G.VEC2)):
                off, n = buf.add(arr)
                gl.bufferViews.append(G.BufferView(buffer=0, byteOffset=off, byteLength=n, target=G.ARRAY_BUFFER))
                acc = G.Accessor(bufferView=len(gl.bufferViews) - 1, componentType=G.FLOAT, count=len(arr), type=typ)
                if name == "POSITION":
                    acc.min, acc.max = pos.min(0).tolist(), pos.max(0).tolist()
                gl.accessors.append(acc)
                attrs[name] = len(gl.accessors) - 1
            off, n = buf.add(idx)
            gl.bufferViews.append(G.BufferView(buffer=0, byteOffset=off, byteLength=n, target=G.ELEMENT_ARRAY_BUFFER))
            gl.accessors.append(G.Accessor(bufferView=len(gl.bufferViews) - 1, componentType=G.UNSIGNED_INT,
                                           count=len(idx), type=G.SCALAR))
            prims.append(G.Primitive(attributes=G.Attributes(**attrs), indices=len(gl.accessors) - 1,
                                     material=material(matname, kind == "collision")))
            stats["triangles_" + kind] += len(idx) // 3
            stats["vertices"] += len(pos)
        if not prims:
            continue
        gl.meshes.append(G.Mesh(name=kind, primitives=prims))
        node = G.Node(name=kind, mesh=len(gl.meshes) - 1)
        ext = cfg.get("collision_node_extensions" if kind == "collision" else "visual_node_extensions", {})
        if ext:
            node.extensions = dict(ext)
            used_ext.update(ext)
        gl.nodes.append(node)
    gl.scenes.append(G.Scene(nodes=list(range(len(gl.nodes)))))
    gl.scene = 0
    gl.extensionsUsed = sorted(used_ext)
    data = bytes(buf.data)
    if embed:
        gl.buffers.append(G.Buffer(byteLength=len(data),
                                   uri="data:application/octet-stream;base64," + base64.b64encode(data).decode()))
    else:
        bin_name = path.with_suffix(".bin").name
        (path.parent / bin_name).write_bytes(data)
        gl.buffers.append(G.Buffer(byteLength=len(data), uri=bin_name))
    gl.save_json(str(path))
    return stats


def orientation_marker(x_utm: float, y_utm: float, z: float, size: float = 6.0) -> Mesh:
    """Arrow pointing true north with a stub on its east side.

    Placed at the demo-route start: if, in the simulator, the arrow does not
    point north or the stub is on the west, the axis mapping is wrong.
    """
    m = Mesh("orientation_marker", False)
    h = z + 0.03
    tip = (x_utm, y_utm + size, h)
    bl, br = (x_utm - size / 3, y_utm, h), (x_utm + size / 3, y_utm, h)
    stub = [(x_utm + size / 3, y_utm + 0.5, h), (x_utm + size, y_utm + 0.5, h),
            (x_utm + size, y_utm + 1.5, h), (x_utm + size / 3, y_utm + 1.5, h)]
    m.add([bl, br, tip], [(0, 1, 2)])
    m.add(stub, [(0, 1, 2), (0, 2, 3)])
    return m
