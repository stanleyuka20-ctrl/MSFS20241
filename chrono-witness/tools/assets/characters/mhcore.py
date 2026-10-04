"""MakeHuman (CC0) core: base mesh, morph targets, joints, weights, reduced skeleton.

Pure numpy - no Blender dependency, so it can be unit tested quickly.
Units: the hm08 base mesh is in decimetres; everything returned here is metres,
Y up, character facing +Z, with the soles of the bare feet at y = SOLE_Y.
"""
import json
import os
import re

import numpy as np

import cw_paths as P

DM = 0.1  # decimetre -> metre
SOLE_Y = 0.024  # bare sole height above ground; boot soles fill the gap

# ----------------------------------------------------------------------------------
# OBJ / targets
# ----------------------------------------------------------------------------------

_base_cache = {}


def load_base():
    """Return dict(verts (N,3) m (unshifted), uvs, faces (list of vertex index tuples),
    face_uv, face_group(list str), groups{name: face indices})."""
    if "base" in _base_cache:
        return _base_cache["base"]
    npz = os.path.join(P.CACHE, "base_obj.npz")
    path = os.path.join(P.MH_DATA, "3dobjs", "base.obj")
    verts, uvs, faces, fuv, fgrp = [], [], [], [], []
    g = None
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("g "):
                g = line.split()[1].strip()
            elif line.startswith("f "):
                fv, ft = [], []
                for tok in line.split()[1:]:
                    a = tok.split("/")
                    fv.append(int(a[0]) - 1)
                    ft.append(int(a[1]) - 1 if len(a) > 1 and a[1] else -1)
                faces.append(tuple(fv))
                fuv.append(tuple(ft))
                fgrp.append(g)
    groups = {}
    for i, gg in enumerate(fgrp):
        groups.setdefault(gg, []).append(i)
    d = dict(verts=np.array(verts) * DM, uvs=np.array(uvs), faces=faces, face_uv=fuv,
             face_group=fgrp, groups={k: np.array(v) for k, v in groups.items()})
    _base_cache["base"] = d
    return d


_target_cache = {}


def load_target(relpath):
    """Load a sparse .target as (idx int array, delta (k,3) metres)."""
    if relpath in _target_cache:
        return _target_cache[relpath]
    path = os.path.join(P.MH_DATA, "targets", relpath)
    if not path.endswith(".target"):
        path += ".target"
    idx, dl = [], []
    with open(path) as f:
        for line in f:
            if not line or line[0] in "#\n":
                continue
            a = line.split()
            if len(a) < 4:
                continue
            idx.append(int(a[0]))
            dl.append([float(a[1]), float(a[2]), float(a[3])])
    t = (np.array(idx, dtype=np.int64), np.array(dl) * DM)
    _target_cache[relpath] = t
    return t


def _tri(v, names):
    """MakeHuman piecewise-linear 3-way split of a 0..1 slider (min/average/max)."""
    lo, mid, hi = names
    if v < 0.5:
        return {lo: 1 - v / 0.5, mid: v / 0.5}
    return {mid: 1 - (v - 0.5) / 0.5, hi: (v - 0.5) / 0.5}


def age_value(years):
    """Convert age in years to the MakeHuman 0..1 age slider."""
    if years < 1:
        return 0.0
    if years < 11:
        return (years - 1) / 10 * 0.1875
    if years < 25:
        return 0.1875 + (years - 11) / 14 * 0.3125
    return 0.5 + (years - 25) / 65 * 0.5


def macro_target_weights(gender=1.0, age_years=25, muscle=0.5, weight=0.5, height=0.5,
                         proportions=0.5, race=None):
    """Replicates MakeHuman's MacroModifier weighting. Returns {target relpath: weight}."""
    race = race or {"caucasian": 1.0}
    a = age_value(age_years)
    gw = {"female": 1 - gender, "male": gender}
    if a < 0.1875:
        aw = {"baby": 1 - a / 0.1875, "child": a / 0.1875}
    elif a < 0.5:
        t = (a - 0.1875) / (0.5 - 0.1875)
        aw = {"child": 1 - t, "young": t}
    else:
        t = (a - 0.5) / 0.5
        aw = {"young": 1 - t, "old": t}
    mw = _tri(muscle, ("minmuscle", "averagemuscle", "maxmuscle"))
    ww = _tri(weight, ("minweight", "averageweight", "maxweight"))
    out = {}

    def add(k, w):
        if w > 1e-6:
            out[k] = out.get(k, 0) + w

    for g, gv in gw.items():
        for ag, av in aw.items():
            for rc, rv in race.items():
                add("macrodetails/%s-%s-%s" % (rc, g, ag), gv * av * rv)
            for m, mv in mw.items():
                for wt, wv in ww.items():
                    add("macrodetails/universal-%s-%s-%s-%s" % (g, ag, m, wt), gv * av * mv * wv)
                    if abs(height - 0.5) > 1e-4:
                        hk = "maxheight" if height > 0.5 else "minheight"
                        add("macrodetails/height/%s-%s-%s-%s-%s" % (g, ag, m, wt, hk),
                            gv * av * mv * wv * abs(height - 0.5) / 0.5)
                    if abs(proportions - 0.5) > 1e-4:
                        pk = "idealproportions" if proportions > 0.5 else "uncommonproportions"
                        add("macrodetails/proportions/%s-%s-%s-%s-%s" % (g, ag, m, wt, pk),
                            gv * av * mv * wv * abs(proportions - 0.5) / 0.5)
    return out


def detail_target_weights(details):
    """details: {"nose/nose-hump": +0.4, "chin/chin-width": -0.3, "head/head-oval": 0.5}
    A signed value picks the -incr/-decr (or -up/-down etc.) file pair automatically."""
    out = {}
    pairs = [("incr", "decr"), ("up", "down"), ("out", "in"), ("forward", "backward"),
             ("convex", "concave"), ("compress", "uncompress")]
    for key, v in details.items():
        if abs(v) < 1e-6:
            continue
        base = os.path.join(P.MH_DATA, "targets", key)
        if os.path.exists(base + ".target"):
            out[key] = out.get(key, 0) + v
            continue
        done = False
        for pos, neg in pairs:
            if os.path.exists(base + "-" + pos + ".target"):
                k = key + "-" + (pos if v > 0 else neg)
                out[k] = out.get(k, 0) + abs(v)
                done = True
                break
        if not done:
            raise FileNotFoundError(key)
    return out


def build_verts(target_weights):
    base = load_base()
    v = base["verts"].copy()
    for t, w in target_weights.items():
        idx, d = load_target(t)
        if len(idx):
            v[idx] += w * d
    return v


# ----------------------------------------------------------------------------------
# Skeleton
# ----------------------------------------------------------------------------------

_skel_cache = {}


def load_mhskel():
    if "s" not in _skel_cache:
        _skel_cache["s"] = json.load(open(os.path.join(P.MH_DATA, "rigs", "default.mhskel")))
    return _skel_cache["s"]


def load_mhw():
    if "w" not in _skel_cache:
        _skel_cache["w"] = json.load(open(os.path.join(P.MH_DATA, "rigs", "default_weights.mhw")))
    return _skel_cache["w"]


def joint_pos(verts, name):
    s = load_mhskel()
    return verts[s["joints"][name]].mean(axis=0)


# Reduced skeleton: (name, mh source bone or None, parent)
SIDES = ("L", "R")


def reduced_bone_list():
    bones = [("root", None, None), ("hips", "root", "root")]
    sp = ["spine05", "spine04", "spine03", "spine02", "spine01"]
    par = "hips"
    for b in sp:
        bones.append((b, b, par))
        par = b
    bones += [("neck01", "neck01", "spine01"), ("neck02", "neck02", "neck01"),
              ("head", "head", "neck02"), ("jaw", "jaw", "head")]
    for s in SIDES:
        bones += [("pelvis.%s" % s, "pelvis.%s" % s, "hips"),
                  ("upperleg01.%s" % s, "upperleg01.%s" % s, "pelvis.%s" % s),
                  ("upperleg02.%s" % s, "upperleg02.%s" % s, "upperleg01.%s" % s),
                  ("lowerleg01.%s" % s, "lowerleg01.%s" % s, "upperleg02.%s" % s),
                  ("lowerleg02.%s" % s, "lowerleg02.%s" % s, "lowerleg01.%s" % s),
                  ("foot.%s" % s, "foot.%s" % s, "lowerleg02.%s" % s),
                  ("toes.%s" % s, None, "foot.%s" % s)]
    for s in SIDES:
        bones += [("clavicle.%s" % s, "clavicle.%s" % s, "spine01"),
                  ("shoulder01.%s" % s, "shoulder01.%s" % s, "clavicle.%s" % s),
                  ("upperarm01.%s" % s, "upperarm01.%s" % s, "shoulder01.%s" % s),
                  ("upperarm02.%s" % s, "upperarm02.%s" % s, "upperarm01.%s" % s),
                  ("lowerarm01.%s" % s, "lowerarm01.%s" % s, "upperarm02.%s" % s),
                  ("lowerarm02.%s" % s, "lowerarm02.%s" % s, "lowerarm01.%s" % s),
                  ("wrist.%s" % s, "wrist.%s" % s, "lowerarm02.%s" % s)]
        for f in (1, 2, 3, 4):
            par = "wrist.%s" % s
            for k in (1, 2, 3):
                n = "finger%d-%d.%s" % (f, k, s)
                bones.append((n, n, par))
                par = n
    return bones


def mh_to_reduced_map():
    """Map every MakeHuman bone to the reduced bone that inherits its weights."""
    s = load_mhskel()
    kept = {b[1]: b[0] for b in reduced_bone_list() if b[1]}
    m = {}
    for name in s["bones"]:
        if name in kept:
            m[name] = kept[name]
            continue
        mt = re.match(r"finger5-(\d)\.(L|R)", name)
        if mt:  # little finger rides on the ring-finger chain
            m[name] = "finger4-%s.%s" % mt.groups()
            continue
        mt = re.match(r"toe\d-\d\.(L|R)", name)
        if mt:
            m[name] = "toes.%s" % mt.group(1)
            continue
        p = name
        while p not in kept:
            p = s["bones"][p]["parent"]
            if p is None:
                break
        m[name] = kept.get(p, "hips")
    return m


def skeleton_rest(verts):
    """Compute rest heads/tails (metres, Y-up, +Z forward) and roll normals for the
    reduced skeleton from (target-deformed, unshifted) base verts.
    Returns list of dict(name,parent,head,tail,znormal)."""
    s = load_mhskel()
    bl = reduced_bone_list()
    out = []
    jp = lambda n: joint_pos(verts, n)
    for name, src, par in bl:
        if name == "root":
            hd = np.array([0.0, 0.0, 0.0])
            tl = np.array([0.0, 0.0, 0.25])
            nrm = np.array([0.0, 1.0, 0.0])
        elif name.startswith("toes."):
            sd = name[-1]
            heads = [jp("toe%d-1.%s____head" % (i, sd)) for i in range(1, 6)]
            tails = [jp("toe%d-3.%s____tail" % (i, sd)) if i > 1 else jp("toe1-2.%s____tail" % sd)
                     for i in range(1, 6)]
            hd = np.mean(heads, axis=0)
            tl = np.mean(tails, axis=0)
            nrm = np.array([1.0, 0.0, 0.0])
        else:
            b = s["bones"][src]
            hd = jp(b["head"])
            tl = jp(b["tail"])
            pl = s["planes"].get(b["rotation_plane"])
            nrm = None
            if pl:
                a, bb, c = [jp(x) for x in pl]
                nrm = np.cross(bb - a, c - bb)
                if np.linalg.norm(nrm) < 1e-9:
                    nrm = None
                else:
                    nrm /= np.linalg.norm(nrm)
            if nrm is None:
                nrm = np.array([1.0, 0.0, 0.0])
        out.append(dict(name=name, src=src, parent=par, head=hd, tail=tl, normal=nrm))
    # neck02 tail -> head joint, neck02 replaced neck03: extend neck02 to head head
    bd = {b["name"]: b for b in out}
    bd["neck02"]["tail"] = bd["head"]["head"].copy()
    return out


def reduced_weights(nverts, max_infl=4):
    """Return (idx (N,4) int, w (N,4)) using reduced bone indices (order of reduced_bone_list)."""
    mhw = load_mhw()["weights"]
    m = mh_to_reduced_map()
    names = [b[0] for b in reduced_bone_list()]
    bi = {n: i for i, n in enumerate(names)}
    W = np.zeros((nverts, len(names)), dtype=np.float64)
    for bname, lst in mhw.items():
        tgt = bi[m.get(bname, "hips")]
        arr = np.array(lst)
        if len(arr) == 0:
            continue
        idx = arr[:, 0].astype(int)
        ok = idx < nverts
        np.add.at(W[:, tgt], idx[ok], arr[ok, 1])
    return W


def limit_weights(W, max_infl=4):
    order = np.argsort(-W, axis=1)[:, :max_infl]
    w = np.take_along_axis(W, order, axis=1)
    s = w.sum(axis=1, keepdims=True)
    s[s == 0] = 1
    return order, w / s


# ----------------------------------------------------------------------------------
# Body construction
# ----------------------------------------------------------------------------------

CANON = dict(gender=1.0, age_years=26, muscle=0.55, weight=0.5, height=0.5, proportions=0.6,
             race={"caucasian": 1.0})


def body_verts(macro, details=None):
    tw = macro_target_weights(**macro)
    if details:
        tw.update({k: tw.get(k, 0) + v for k, v in detail_target_weights(details).items()})
    return build_verts(tw)


def ground_offset(verts):
    base = load_base()
    body = np.unique(np.concatenate([base["faces"][i] for i in base["groups"]["body"]]
                                    if False else [np.array(base["faces"][i]) for i in base["groups"]["body"]]))
    return SOLE_Y - verts[body, 1].min()


_canon = {}


def canonical():
    """Canonical body verts (shifted to ground) and skeleton - shared by all characters."""
    if "c" not in _canon:
        v = body_verts(CANON)
        off = ground_offset(v)
        v = v + np.array([0, off, 0])
        sk = skeleton_rest(v)
        _canon["c"] = (v, sk)
    return _canon["c"]


def fit_to_canonical(verts, W, scale=1.0):
    """Warp a character's verts (already ground shifted with its own offset) so its joints
    coincide with the canonical skeleton: per-vertex LBS of joint translation offsets.
    Also returns the per-bone offsets."""
    cv, csk = canonical()
    sk = skeleton_rest(verts)
    off = np.array([c["head"] * scale - b["head"] for c, b in zip(csk, sk)])
    # root has no geometric meaning - use hips offset
    off[0] = off[1]
    Wn = W / np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
    return verts + Wn @ off, off


def body_face_mask(groups=("body",)):
    base = load_base()
    m = np.zeros(len(base["faces"]), bool)
    for g in groups:
        m[base["groups"][g]] = True
    return m


# mhclo fitting -------------------------------------------------------------------

def load_mhclo(path):
    """Return dict(obj, refs (n,3) int, w (n,3), off (n,3), scales{x:(v1,v2,d)})"""
    refs, ws, offs, sc = [], [], [], {}
    obj = None
    inverts = False
    with open(path) as f:
        for line in f:
            a = line.split()
            if not a or a[0].startswith("#"):
                continue
            if a[0] == "obj_file":
                obj = os.path.join(os.path.dirname(path), a[1])
            elif a[0] in ("x_scale", "y_scale", "z_scale"):
                sc[a[0][0]] = (int(a[1]), int(a[2]), float(a[3]))
            elif a[0] == "verts":
                inverts = True
            elif inverts and len(a) == 9:
                refs.append([int(x) for x in a[:3]])
                ws.append([float(x) for x in a[3:6]])
                offs.append([float(x) for x in a[6:9]])
            elif inverts and len(a) == 1:
                refs.append([int(a[0])] * 3)
                ws.append([1, 0, 0])
                offs.append([0, 0, 0])
            elif inverts and a[0] in ("delete_verts",):
                inverts = False
    return dict(obj=obj, refs=np.array(refs), w=np.array(ws), off=np.array(offs), scales=sc)


def fit_mhclo(clo, verts_dm):
    """verts_dm: base verts in decimetres (MakeHuman units). Returns fitted verts (dm)."""
    v = verts_dm
    s = []
    for ax, i in (("x", 0), ("y", 1), ("z", 2)):
        v1, v2, d = clo["scales"][ax]
        s.append(abs(v[v1, i] - v[v2, i]) / d)
    s = np.array(s)
    p = (v[clo["refs"]] * clo["w"][..., None]).sum(axis=1) + clo["off"] * s
    return p


def load_obj_simple(path):
    verts, uvs, faces, fuv = [], [], [], []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("vt "):
                uvs.append([float(x) for x in line.split()[1:3]])
            elif line.startswith("f "):
                fv, ft = [], []
                for tok in line.split()[1:]:
                    a = tok.split("/")
                    fv.append(int(a[0]) - 1)
                    ft.append(int(a[1]) - 1 if len(a) > 1 and a[1] else -1)
                faces.append(tuple(fv))
                fuv.append(tuple(ft))
    return np.array(verts), np.array(uvs), faces, fuv


if __name__ == "__main__":
    v, sk = canonical()
    base = load_base()
    bodyv = np.unique(np.concatenate([np.array(base["faces"][i]) for i in base["groups"]["body"]]))
    print("height", v[bodyv, 1].max(), "minY", v[bodyv, 1].min(), "nbones", len(sk))
    for b in sk:
        print("%-16s %-14s head %s tail %s" % (b["name"], b["parent"], np.round(b["head"], 3), np.round(b["tail"], 3)))
    m = mh_to_reduced_map()
    W = reduced_weights(len(v))
    print("weights rowsum min/max over body", W[bodyv].sum(1).min(), W[bodyv].sum(1).max())
