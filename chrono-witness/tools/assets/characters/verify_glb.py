"""Verify the exported character GLBs (pure python + numpy + Pillow, no Blender needed).

Checks: identical joint names/rest pose across characters and anims_humanoid.glb, triangle
budgets per LOD, bone count, NaNs, scale (height), feet at y~0, facing +Z, texture sizes,
animation targets.  Prints a report and writes stats JSON (used for the README).

    python verify_glb.py
"""
import io
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cw_paths as P

CTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load_glb(path):
    data = open(path, "rb").read()
    magic, ver, length = struct.unpack("<III", data[:12])
    assert magic == 0x46546C67
    off = 12
    js, binc = None, None
    while off < length:
        clen, ctype = struct.unpack("<II", data[off:off + 8])
        chunk = data[off + 8:off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            binc = chunk
        off += 8 + clen
    return js, binc


def accessor(js, binc, i):
    a = js["accessors"][i]
    bv = js["bufferViews"][a["bufferView"]]
    dt = CTYPE[a["componentType"]]
    n = NCOMP[a["type"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0)
    cnt = a["count"]
    item = np.dtype(dt).itemsize * n
    if stride and stride != item:
        raw = np.frombuffer(binc, dtype=np.uint8, count=stride * cnt, offset=start).reshape(cnt, stride)[:, :item]
        arr = np.frombuffer(raw.tobytes(), dtype=dt).reshape(cnt, n)
    else:
        arr = np.frombuffer(binc, dtype=dt, count=cnt * n, offset=start).reshape(cnt, n)
    if a.get("normalized"):
        arr = arr.astype(np.float32) / np.iinfo(dt).max
    return arr


def node_world(js):
    nodes = js["nodes"]
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    from scipy.spatial.transform import Rotation as R

    def local(n):
        M = np.eye(4)
        if "matrix" in n:
            return np.array(n["matrix"]).reshape(4, 4).T
        t = n.get("translation", [0, 0, 0])
        r = n.get("rotation", [0, 0, 0, 1])
        s = n.get("scale", [1, 1, 1])
        M[:3, :3] = R.from_quat(r).as_matrix() * np.array(s)
        M[:3, 3] = t
        return M

    W = {}

    def world(i):
        if i in W:
            return W[i]
        M = local(nodes[i])
        if i in parent:
            M = world(parent[i]) @ M
        W[i] = M
        return M

    for i in range(len(nodes)):
        world(i)
    return W


def analyse(path):
    js, binc = load_glb(path)
    out = {"file": os.path.basename(path), "bytes": os.path.getsize(path)}
    nodes = js["nodes"]
    W = node_world(js)
    skins = js.get("skins", [])
    if skins:
        joints = [nodes[j]["name"] for j in skins[0]["joints"]]
        out["bones"] = joints
        jpos = {nodes[j]["name"]: W[j][:3, 3] for j in skins[0]["joints"]}
        out["joint_pos"] = jpos
    meshes = {}
    for ni, n in enumerate(nodes):
        if "mesh" not in n:
            continue
        m = js["meshes"][n["mesh"]]
        tris = 0
        pos_all = []
        nan = False
        prims = []
        for p in m["primitives"]:
            if "indices" in p:
                tris += js["accessors"][p["indices"]]["count"] // 3
            pos = accessor(js, binc, p["attributes"]["POSITION"])
            nan |= not np.all(np.isfinite(pos))
            for k in ("NORMAL", "TEXCOORD_0", "WEIGHTS_0"):
                if k in p["attributes"]:
                    nan |= not np.all(np.isfinite(accessor(js, binc, p["attributes"][k]).astype(np.float64)))
            pos_all.append(pos)
            mat = js["materials"][p["material"]]["name"] if "material" in p else None
            prims.append(mat)
        pos = np.concatenate(pos_all)
        # skinned meshes: positions are in bind space == world rest pose for our exports
        meshes[n["name"]] = dict(tris=tris, nan=nan, materials=prims, min=pos.min(0).round(3).tolist(),
                                 max=pos.max(0).round(3).tolist(), skinned="skin" in n, pos=pos)
    out["meshes"] = meshes
    imgs = []
    for im in js.get("images", []):
        bv = js["bufferViews"][im["bufferView"]]
        b = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        from PIL import Image
        I = Image.open(io.BytesIO(b))
        imgs.append((im.get("name", "?"), I.size, im.get("mimeType"), len(b)))
    out["images"] = imgs
    anims = []
    for a in js.get("animations", []):
        tmax = 0
        targets = set()
        for ch in a["channels"]:
            s = a["samplers"][ch["sampler"]]
            inp = js["accessors"][s["input"]]
            tmax = max(tmax, inp["max"][0])
            targets.add(nodes[ch["target"]["node"]]["name"])
        anims.append(dict(name=a["name"], duration=round(tmax, 3), channels=len(a["channels"]),
                          targets=sorted(targets)))
    out["animations"] = anims
    out["materials"] = [m["name"] for m in js.get("materials", [])]
    out["emissive"] = [m["name"] for m in js.get("materials", []) if "emissiveTexture" in m or
                       any(v > 0 for v in m.get("emissiveFactor", [0, 0, 0]))]
    return out


def main():
    files = ["soldier_a", "soldier_b", "soldier_c", "officer", "medic", "wounded", "archivist"]
    ref = analyse(os.path.join(P.OUT, "anims_humanoid.glb"))
    ok = True
    report = {}
    ref_names = None
    # anims file: armature nodes (no skin) -> collect node names
    js, _ = load_glb(os.path.join(P.OUT, "anims_humanoid.glb"))
    anim_nodes = [n["name"] for n in js["nodes"]]
    Wa = node_world(js)
    anim_pos = {js["nodes"][i]["name"]: Wa[i][:3, 3] for i in range(len(js["nodes"]))}
    meta = json.load(open(os.path.join(P.OUT, "anims_humanoid.json")))
    print("anims_humanoid.glb: %d nodes, %d clips, %.2f MB" % (len(anim_nodes), len(ref["animations"]),
                                                               ref["bytes"] / 1e6))
    for a in ref["animations"]:
        m = meta.get(a["name"])
        flag = "" if m and abs(m["duration"] - a["duration"]) < 0.05 else "  <-- json mismatch"
        missing = [t for t in a["targets"] if t not in anim_nodes]
        print("   %-12s %.2fs speed=%s channels=%d %s%s" % (a["name"], a["duration"], m and m["speed"], a["channels"],
                                                         flag, " MISSING TARGETS" if missing else ""))
    for f in files:
        p = os.path.join(P.OUT, f + ".glb")
        if not os.path.exists(p):
            print("MISSING", p)
            ok = False
            continue
        r = analyse(p)
        names = r.get("bones", [])
        if ref_names is None:
            ref_names = names
        same = names == ref_names
        sub = all(n in anim_nodes for n in names)
        dpos = max(np.linalg.norm(r["joint_pos"][n] - anim_pos[n]) for n in names if n in anim_pos)
        lod0 = [m for k, m in r["meshes"].items() if not k.endswith("_LOD1") and k != "cap"]
        lod1 = [m for k, m in r["meshes"].items() if k.endswith("_LOD1")]
        t0 = sum(m["tris"] for m in lod0)
        t1 = sum(m["tris"] for m in lod1)
        allpos = np.concatenate([m["pos"] for m in lod0])
        height = allpos[:, 1].max()
        feet = allpos[:, 1].min()
        head = allpos[allpos[:, 1] > height - 0.35]
        # facing: the nose/brim region should be in +Z: compare z of the face (eyes level) extremes
        face = allpos[(allpos[:, 1] > 1.55) & (allpos[:, 1] < 1.7) & (np.abs(allpos[:, 0]) < 0.03)]
        facing = "+Z" if face[:, 2].max() > -face[:, 2].min() else "-Z?"
        nan = any(m["nan"] for m in r["meshes"].values())
        print("%-10s %.2f MB bones=%d same_names=%s in_anims=%s max_joint_delta=%.4f LOD0=%d LOD1=%d "
              "height=%.3f feet_y=%.3f facing=%s nan=%s" % (f, r["bytes"] / 1e6, len(names), same, sub, dpos, t0, t1,
                                                           height, feet, facing, nan))
        print("           meshes:", {k: (m["tris"], m["materials"]) for k, m in r["meshes"].items()})
        print("           images:", [(n, s, b // 1024) for n, s, mt, b in r["images"]])
        cond = same and sub and dpos < 1e-3 and t0 <= 22000 and t1 <= 7000 and len(names) <= 64 and not nan and \
            1.6 < height < 2.0 and abs(feet) < 0.01 and facing == "+Z" and r["bytes"] < 6.5e6 and \
            all(max(s) <= 1024 for _, s, _, _ in r["images"])
        ok &= cond
        report[f] = dict(bytes=r["bytes"], lod0=t0, lod1=t1, bones=len(names), height=round(float(height), 3),
                         images=[(n, s) for n, s, _, _ in r["images"]],
                         meshes={k: m["tris"] for k, m in r["meshes"].items()})
        if not cond:
            print("   !! check failed for", f)
    fp = analyse(os.path.join(P.OUT, "fp_arms.glb"))
    t = sum(m["tris"] for m in fp["meshes"].values())
    print("fp_arms    %.2f MB bones=%d tris=%d materials=%s emissive=%s clips=%s" % (
        fp["bytes"] / 1e6, len(fp["bones"]), t, fp["materials"], fp["emissive"],
        [(a["name"], a["duration"]) for a in fp["animations"]]))
    print("           images:", [(n, s, b // 1024) for n, s, mt, b in fp["images"]])
    ok &= "device_screen" in fp["emissive"]
    report["fp_arms"] = dict(bytes=fp["bytes"], tris=t, bones=len(fp["bones"]),
                             clips=[(a["name"], a["duration"]) for a in fp["animations"]],
                             images=[(n, s) for n, s, _, _ in fp["images"]])
    report["anims_humanoid"] = dict(bytes=ref["bytes"], bones=len([n for n in anim_nodes]),
                                    clips=[(a["name"], a["duration"]) for a in ref["animations"]])
    json.dump(report, open(os.path.join(P.WORK, "verify_report.json"), "w"), indent=1)
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
