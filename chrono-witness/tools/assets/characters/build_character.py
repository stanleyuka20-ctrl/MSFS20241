"""Build one (or all) character GLBs.

    python build_character.py soldier_a [officer ...]      (default: all characters)

Pipeline per character: MakeHuman body (macro + face targets, fitted to the shared
canonical skeleton) -> procedural garments/gear (cw_character) -> Blender objects per
material group -> Smart-UV atlas -> collapse decimation to the LOD0 budget -> procedural
textures painted in 3D and rasterised into the atlas (cw_materials/cw_tex) -> Cycles AO
bake -> LOD1 decimation -> skinning -> glTF export with embedded JPEG textures.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from scipy.spatial import cKDTree

import cw_anim as ca
import cw_blender as cb
import cw_character as C
import cw_civil as CV
import cw_garment as G
import cw_materials as MAT
import cw_paths as P
import cw_tex as T
import mhcore as mh
from characters_cfg import CHARACTERS

K = MAT.K
TEXSIZE = {"skin": 1024, "eyes": 256, "hair": 512, "cloth": 1024, "gear": 1024, "helmet": 512}
ORMSIZE = {"skin": 1024, "eyes": 128, "hair": 256, "cloth": 1024, "gear": 512, "helmet": 512}
LOD0_BUDGET = 21600
LOD1_BUDGET = 6900
FIXED0 = {"skin": 6500, "eyes": 560, "hair": 520, "helmet": 1400}
FIXED1 = {"skin": 1900, "eyes": 100, "hair": 220, "helmet": 420}
ATTRS = ["hand", "dens", "loft_s", "loft_c", "loft_sn", "pouch_u", "pouch_v", "pouch_front", "is_pouch",
         "rib_t", "is_ribbon", "outer", "prof_k", "civ1"]
TMP = os.path.join(P.WORK, "tex")
os.makedirs(TMP, exist_ok=True)


class Part:
    def __init__(self, group, name, mesh, kind, weights="body", smooth=2, detach=False):
        self.group, self.name, self.m, self.kind = group, name, mesh, kind
        self.weights = weights
        self.smooth = smooth
        self.detach = detach  # painted in the group atlas, exported as its own (hidden) mesh


# ----------------------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------------------


def loft_attrs(m):
    if "loft_a" in m.attrs:
        m.attrs["loft_c"] = np.cos(m.attrs["loft_a"])
        m.attrs["loft_sn"] = np.sin(m.attrs["loft_a"])
    if "band_a" in m.attrs:
        m.attrs["loft_c"] = np.cos(m.attrs["band_a"])
        m.attrs["loft_sn"] = np.sin(m.attrs["band_a"])
        m.attrs["loft_s"] = m.attrs["band_t"] * 0.045
    if "rib_t" in m.attrs:
        m.attrs["is_ribbon"] = np.ones(len(m.v))
        m.attrs["loft_s"] = m.attrs.get("rib_s", np.zeros(len(m.v)))
    if "pouch_u" in m.attrs:
        m.attrs["is_pouch"] = np.ones(len(m.v))
    return m


def make_parts(cid, cfg, B, R):
    if cfg.get("era") == "1940":
        return [Part(p.group, p.name, p.m, p.kind, p.weights, p.smooth, p.detach)
                for p in CV.make_parts(cid, cfg, B, R)], {}
    parts = []
    cover = np.zeros(len(B.v), bool)
    modern = cfg.get("modern", False)
    officer = cfg.get("uniform") == "officer"
    wounded = cfg.get("wounded", False)
    medic = cfg.get("medic", False)
    # ---- upper garment
    if modern:
        tcfg = dict(hem=0.865, collar="open", v_bottom=1.40, v_width=0.06, lapel=0.04, cuff=0.9, ease=0.013,
                    sleeve_ease=0.012)
        tkind = K["jacket"]
    else:
        tcfg = dict()
        if officer:
            tcfg.update(collar="open", v_bottom=1.37, v_width=0.07, lapel=0.04, hem=0.78)
        if wounded:
            tcfg.update(collar="open", v_bottom=1.38, v_width=0.07, lapel=0.03, short_sleeve=["L"],
                        short_sleeve_at=0.08)
        tkind = K["tunic"]
    tun, cv = C.tunic(B, R, tcfg)
    cover |= cv
    parts.append(Part("cloth", "tunic", tun, tkind, smooth=3))
    if tcfg.get("collar") == "open":
        cover |= C.vneck_region(B, R, tcfg, grow=0.025) & (R["neck"] < 0.5)
        sh = C.shirt_tie(B, R, dict(tcfg, tie=officer, shirt_collar=not wounded))
        for item in sh:
            if isinstance(item, tuple):
                parts.append(Part("cloth", item[0], item[1], K["tie"]))
            else:
                parts.append(Part("cloth", "shirt", item, K["shirt"]))
    # ---- legs
    if modern:
        tr, cv = C.trousers(B, R, dict(bottom_shin=0.95, ease=0.012))
        cover |= cv
        parts.append(Part("cloth", "trousers", tr, K["modern_trousers"]))
        bo, cv = C.boots(B, R, dict(top=0.10, ease=0.006, toe_extra=0.008))
        cover |= cv
        parts.append(Part("gear", "shoes", bo, K["boot"], smooth=1))
    else:
        tr, cv = C.trousers(B, R, dict(bottom_shin=0.36, ease=0.012, breeches=0.035 if officer else 0.0))
        cover |= cv
        parts.append(Part("cloth", "trousers", tr, K["trousers"]))
        for s in "LR":
            if officer:
                w = C.leg_wrap(B, R, s, 0.26, 0.92, 0.016, nseg=18, nring=8)
                parts.append(Part("gear", "gaiter." + s, w, K["gaiter"]))
            else:
                w = C.leg_wrap(B, R, s, 0.25, 0.93, lambda t: 0.017 - 0.004 * t, nseg=18, nring=11)
                parts.append(Part("cloth", "puttee." + s, w, K["puttee"]))
        cover |= (R["shin"] > 0.31) & (R["shin"] < 0.9)
        bo, cv = C.boots(B, R, dict(top=0.165))
        cover |= cv
        parts.append(Part("gear", "boots", bo, K["boot"], smooth=1))
    # ---- webbing / belts / bags
    if cfg.get("webbing"):
        web = C.webbing_1908(B, tun, cfg)
        for k, m in web.items():
            kind = K["brass"] if k == "buckle" else (K["felt"] if k == "bottle" else
                                                     (K["leather"] if k == "scabbard" else K["webbing"]))
            wmode = {"bottle": "hips", "scabbard": "scabbard"}.get(k, "body")
            parts.append(Part("gear", k, m, kind, weights=wmode, smooth=6))
    if officer:
        sb = C.sam_browne(B, tun, cfg)
        for k, m in sb.items():
            kind = K["brass"] if "buckle" in k else K["leather"]
            parts.append(Part("gear", k, m, kind, weights="hips" if k == "holster" else "body", smooth=6))
    if medic:
        web = C.webbing_1908(B, tun, cfg)
        for k in ("belt", "buckle", "bottle"):
            m = web[k]
            kind = K["brass"] if k == "buckle" else (K["felt"] if k == "bottle" else K["webbing"])
            parts.append(Part("gear", k, m, kind, weights="hips" if k == "bottle" else "body", smooth=6))
        bag, strap = C.haversack(B, tun, cfg)
        parts.append(Part("gear", "haversack", bag, K["canvas"], weights="hips"))
        parts.append(Part("gear", "haversack_strap", strap, K["canvas"], smooth=6))
        # SB armband on the left upper arm
        a = C.J(B, "upperarm02.L")
        b = C.J(B, "lowerarm01.L")
        mask = (B.v[:, 0] > 0.15) & (R["arm"] > 0.5)
        arm = C.limb_wrap(B, mask, a, b, 0.32, 0.62, 0.02, nseg=20, nring=4)
        parts.append(Part("cloth", "armband", arm, K["armband"]))
    # ---- head
    hair, dens = C.hair_cap(B, cfg.get("hair", {}))
    parts.append(Part("hair", "hair", hair, K["hair"], weights="head"))
    if cfg.get("helmet"):
        hel, liner, strap = C.brodie_helmet(B, cfg.get("helmet_cfg", {}))
        parts.append(Part("helmet", "helmet", hel, K["helmet"], weights="head"))
        parts.append(Part("helmet", "liner", liner, K["liner"], weights="head"))
        if strap is not None:
            parts.append(Part("gear", "chinstrap", strap, K["leather"], weights="head"))
    if cfg.get("cap_comforter"):
        cc, ccv = C.cap_comforter(B, cfg)
        parts.append(Part("cloth", "cap_comforter", cc, K["cap_cloth"], weights="head"))
    if wounded:
        for i, band in enumerate(C.head_bandage(B, cfg)):
            parts.append(Part("cloth", "head_bandage%d" % i, band, K["bandage"], weights="head"))
        a = C.J(B, "lowerarm01.L")
        b = C.J(B, "wrist.L")
        mask = (B.v[:, 0] > 0.2) & (R["arm"] > 0.5) & (R["hand"] < 0.5)
        fb = C.limb_wrap(B, mask, a, b, 0.25, 0.8, 0.005, nseg=18, nring=9)
        parts.append(Part("cloth", "arm_bandage", fb, K["bandage"]))
        cover |= (R["fa.L"] > 0.3) & (R["fa.L"] < 0.75)
    eyes = C.eyes_mesh(B)
    parts.append(Part("eyes", "eyes", eyes, K["eye"], weights="head"))
    # ---- visible body
    keep = ~C.faces_all(B, cover)
    body = G.submesh(B.v, B.f, keep, B.W)
    body.loop_uv = [B.fuv[i] for i in np.where(keep)[0]]
    body.attrs["hand"] = R["hand"][body.src]
    body.attrs["dens"] = dens[body.src]
    parts.insert(0, Part("skin", "body", body, K["skin"], weights="exact"))
    extra = {}
    if officer:
        cap, peak = C.service_cap(B, cfg)
        extra["cap"] = [Part("cloth", "cap", cap, K["cap_cloth"], weights="head"),
                        Part("cloth", "cap_peak", peak, K["cap_peak"], weights="head")]
    return parts, extra


def finalize_part(pt, B):
    m = pt.m
    loft_attrs(m)
    nW = B.W.shape[1]
    if pt.weights == "head":
        m.W = np.zeros((len(m.v), nW))
        m.W[:, C.BI["head"]] = 1
    elif pt.weights == "hips":
        # rigid: average of body weights around the attachment (keeps it with the pelvis)
        w = B.ref.weights_at(m.v.mean(0)[None], k=12)[0]
        w[[C.BI[n] for n in C.BONES if n.startswith(("upperleg", "lowerleg"))]] *= 0.25
        w /= w.sum()
        m.W = np.broadcast_to(w, (len(m.v), nW)).copy()
    elif pt.weights == "scabbard":
        # hangs from the belt frog but swings with the left thigh (avoids leg intersections)
        w = B.ref.weights_at(m.v[np.argmax(m.v[:, 1])][None], k=12)[0]
        w[[C.BI[n] for n in C.BONES if n.startswith(("upperleg", "lowerleg"))]] = 0
        w /= w.sum()
        w = 0.5 * w
        w[C.BI["upperleg01.L"]] += 0.5
        m.W = np.broadcast_to(w, (len(m.v), nW)).copy()
    elif pt.weights == "bundle":
        # carried bundle: rigid to the upper chest (the carry_box arms hold it there)
        m.W = np.zeros((len(m.v), nW))
        m.W[:, C.BI["spine02"]] = 0.5
        m.W[:, C.BI["spine01"]] = 0.5
    elif pt.weights == "exact":
        pass
    else:
        G.assign_weights(m, B.ref, from_src=m.src is not None, smooth=pt.smooth)
    m.attrs["kind"] = np.full(len(m.v), float(pt.kind))
    # decimation preference: dense body-derived shells may be thinned, low-poly lofts/straps not
    m.attrs["dec_w"] = np.full(len(m.v), 1.0 if (m.src is not None and (m.src >= 0).mean() > 0.5) else 0.3)
    if "kind_override" in m.attrs:
        m.attrs["kind"] = np.full(len(m.v), float(K["tie"]))
    for a in ATTRS:
        if a not in m.attrs:
            m.attrs[a] = np.zeros(len(m.v))
    return m


# ----------------------------------------------------------------------------------
# Blender object helpers
# ----------------------------------------------------------------------------------


def blender_obj(name, m):
    uvs = None
    if m.loop_uv is not None:
        uvs = np.array([uv for face in m.loop_uv for uv in face], float)
    ob = cb.mesh_from_data(name, m.v, m.f, uvs)
    return ob


def pack_only(ob, margin):
    select_only([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=margin, rotate=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def select_only(obs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or obs[0]


def smart_uv(ob, margin=0.004, angle=62):
    select_only([ob])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # degenerate faces left by aggressive decimation can make the island packer hang
    bpy.ops.mesh.dissolve_degenerate(threshold=1e-5)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=np.radians(angle), island_margin=margin, area_weight=1.0,
                             scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def ntris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate(ob, target, symmetric=False, favour=None, factor=1.0):
    """Collapse-decimate to `target` triangles.  favour(co_gltf) -> weight 0..1: vertices with
    weight 1 are decimated preferentially (Blender's vertex-group semantics), 0 = protected."""
    cur = ntris(ob)
    target = max(int(target), 8)
    if cur <= target:
        return cur
    vgname = None
    if favour is not None:
        co = np.zeros(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", co)
        w = favour(cb.b2g(co.reshape(-1, 3))) if callable(favour) else np.asarray(favour)
        vg = ob.vertex_groups.new(name="_dec")
        for val in np.unique(np.round(w, 2)):
            ids = np.where(np.round(w, 2) == val)[0].tolist()
            vg.add(ids, float(val), "REPLACE")
        vgname = vg.name
    for attempt in range(4):
        ratio = target / max(ntris(ob), 1)
        if ratio >= 0.999:
            break
        select_only([ob])
        md = ob.modifiers.new("dec", "DECIMATE")
        md.ratio = ratio
        md.use_collapse_triangulate = True
        if symmetric:
            md.use_symmetry = True
            md.symmetry_axis = "X"
        if vgname:
            md.vertex_group = vgname
            md.vertex_group_factor = factor
        bpy.ops.object.modifier_apply(modifier=md.name)
        if ntris(ob) <= target * 1.01:
            break
    if vgname and vgname in ob.vertex_groups:
        ob.vertex_groups.remove(ob.vertex_groups[vgname])
    return ntris(ob)


def face_protect(co):
    """Decimation preference for the skin: keep the face dense, thin out hands/neck."""
    face = (co[:, 1] > 1.50) & (np.abs(co[:, 0]) < 0.12)
    return np.where(face, 0.3, 1.0)


def enforce_budget(objs, budget):
    tot = sum(ntris(o) for o in objs.values())
    if tot <= budget:
        return
    big = max((g for g in objs if g in ("cloth", "gear", "skin")), key=lambda g: ntris(objs[g]))
    decimate(objs[big], ntris(objs[big]) - (tot - budget) - 20)


def smooth_all(o):
    """Smooth shading everywhere: drop sharp-edge/face flags (decimation can create them) and
    any custom normals so the exporter writes plain smooth vertex normals."""
    me = o.data
    for name in ("sharp_edge", "sharp_face"):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
    if me.has_custom_normals:
        select_only([o])
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.update()


def set_face_int(ob, name, value):
    me = ob.data
    a = me.attributes.get(name) or me.attributes.new(name, "INT", "FACE")
    a.data.foreach_set("value", [int(value)] * len(me.polygons))


def part_tri_counts(ob):
    me = ob.data
    vals = np.zeros(len(me.polygons), int)
    me.attributes["part"].data.foreach_get("value", vals)
    sizes = np.array([len(p.vertices) - 2 for p in me.polygons])
    return {int(k): int(sizes[vals == k].sum()) for k in np.unique(vals)}


def join(obs_, name):
    if len(obs_) > 1:
        select_only(obs_, obs_[0])
        bpy.ops.object.join()
    o = obs_[0]
    o.name = name
    o.data.name = name
    return o


def extract_part(ob, pi, name):
    import bmesh
    o = ob.copy()
    o.data = ob.data.copy()
    o.name = name
    bpy.context.scene.collection.objects.link(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    lay = bm.faces.layers.int.get("part")
    dead = [f for f in bm.faces if f[lay] != pi]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    if len(bm.faces) == 0:
        bm.free()
        bpy.data.objects.remove(o)
        return None
    bm.to_mesh(o.data)
    bm.free()
    return o


def remove_part(ob, pi):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get("part")
    dead = [f for f in bm.faces if f[lay] == pi]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()


def split_skin_components(parts):
    """Split the visible body into connected pieces (head+neck, each hand, ...)."""
    out = []
    for pt in parts:
        if pt.group != "skin":
            out.append(pt)
            continue
        m = pt.m
        n = len(m.v)
        A = G.adjacency(n, m.f)
        from scipy.sparse.csgraph import connected_components
        nc, lab = connected_components(A, directed=False)
        flab = np.array([lab[f[0]] for f in m.f])
        for c in range(nc):
            fs = np.where(flab == c)[0]
            if len(fs) == 0:
                continue
            sub = G.submesh(m.v, m.f, flab == c, m.W)
            sub.attrs = {k: v[sub.src] for k, v in m.attrs.items()}
            sub.loop_uv = [m.loop_uv[i] for i in fs] if m.loop_uv is not None else None
            sub.src = m.src[sub.src] if m.src is not None else None
            out.append(Part(pt.group, "%s_%d" % (pt.name, c), sub, pt.kind, weights="exact"))
    return out


def part_targets(groups, tris, budget, fixed, head_min_frac=0.0, keep_small=True):
    """Triangle target per part.  Fixed group budgets for skin/eyes/hair/helmet, the rest is
    shared by cloth/gear proportionally.  Small low-poly parts are kept intact as far as
    possible; in the skin group the head gets ~72% of the budget."""
    gt = {}
    fixed_sum = sum(min(fixed[g], sum(tris[pi] for pi, _ in lst)) for g, lst in groups.items() if g in fixed)
    flex_tot = sum(sum(tris[pi] for pi, _ in lst) for g, lst in groups.items() if g not in fixed)
    for g, lst in groups.items():
        tot = sum(tris[pi] for pi, _ in lst)
        gt[g] = min(fixed[g], tot) if g in fixed else int((budget - fixed_sum) * tot / max(flex_tot, 1))
    out = {}
    for g, lst in groups.items():
        b = gt[g]
        if g == "skin" and len(lst) > 1:
            head = max(lst, key=lambda x: x[1].m.v[:, 1].mean())
            others = [x for x in lst if x is not head]
            # >= 60% of the head's triangles: lower ratios produce dents at the cheeks/mouth corners
            out[head[0]] = min(tris[head[0]], max(int(b * 0.72), int(tris[head[0]] * head_min_frac)))
            rest = b - out[head[0]]
            ot = sum(tris[pi] for pi, _ in others)
            for pi, _ in others:
                out[pi] = min(tris[pi], int(rest * tris[pi] / max(ot, 1)))
            continue
        # weight: dense shells may lose more than low-poly lofts/straps; tiny parts are kept
        w = {pi: (1.0 if pt.m.attrs.get("dec_w", np.ones(1)).mean() > 0.5 else
                  (0.0 if (keep_small and tris[pi] < 700) else 0.35)) for pi, pt in lst}
        T_ = sum(tris[pi] for pi, _ in lst)
        if T_ <= b:
            for pi, _ in lst:
                out[pi] = tris[pi]
            continue
        k = (T_ - b) / max(sum(tris[pi] * w[pi] for pi, _ in lst), 1)
        for _ in range(3):  # re-solve when clamping kicks in
            f = {pi: float(np.clip(1 - k * w[pi], 0.08, 1.0)) for pi, _ in lst}
            tot = sum(tris[pi] * f[pi] for pi, _ in lst)
            if tot > b * 1.001:
                k *= 1 + (tot - b) / max(T_ - tot, 1) * 0.5 + 0.02
            else:
                break
        for pi, _ in lst:
            out[pi] = int(tris[pi] * f[pi])
    return out


def read_mesh(ob):
    me = ob.data
    me.calc_loop_triangles()
    nv = len(me.vertices)
    co = np.zeros(nv * 3)
    me.vertices.foreach_get("co", co)
    co = cb.b2g(co.reshape(-1, 3))
    vn = np.zeros(nv * 3)
    me.vertex_normals.foreach_get("vector", vn)
    vn = cb.b2g(vn.reshape(-1, 3))
    lt = np.zeros(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get("loops", lt)
    lt = lt.reshape(-1, 3)
    tv = np.zeros(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get("vertices", tv)
    tv = tv.reshape(-1, 3)
    uv = np.zeros(len(me.loops) * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    return co, vn, tv, uv[lt]


def lookup_attrs(co, hi, vn=None):
    """Nearest high-res vertex attributes & weights for decimated vertices.  Normals are part
    of the search key so thin double layers (hems, helmet inner/outer) do not mix."""
    if vn is not None:
        hn = G.vertex_normals_fast(hi.v, hi.f)
        tree = cKDTree(np.concatenate([hi.v, hn * 0.01], 1))
        d, idx = tree.query(np.concatenate([co, vn * 0.01], 1), k=3)
    else:
        tree = cKDTree(hi.v)
        d, idx = tree.query(co, k=3)
    w = 1 / np.maximum(d, 1e-5)
    w /= w.sum(1, keepdims=True)
    W = (hi.W[idx] * w[..., None]).sum(1)
    attrs = {}
    for k, a in hi.attrs.items():
        if k == "kind":
            attrs[k] = a[idx[:, 0]]
        else:
            attrs[k] = (a[idx] * w).sum(1)
    return W, attrs


# ----------------------------------------------------------------------------------
# textures
# ----------------------------------------------------------------------------------


def raster_group(ob, attrs, N):
    co, vn, tv, tuv = read_mesh(ob)
    A = {"pos": co[tv], "nrm": vn[tv]}
    kind_v = attrs["kind"]
    # kind constant per triangle (majority)
    kt = np.array([np.bincount(np.rint(kind_v[t]).astype(int)).argmax() for t in tv])
    A["kind"] = np.repeat(kt[:, None, None].astype(float), 3, axis=1)
    for k in ATTRS:
        if k in attrs:
            A[k] = attrs[k][tv][..., None]
    if "loft_c" in attrs:
        ang = np.arctan2(attrs["loft_sn"], attrs["loft_c"])
        A["loft_a"] = ang[tv][..., None]
    M = T.rasterize(tuv, A, N)
    m = M["mask"]
    nrm = M["nrm"]
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-6)
    M["nrm"] = nrm
    return M


def finish_maps(res, M, N, ormN, name):
    mask = M["mask"]
    su, sv = T.texel_scale(M["pos"], mask)
    h = res["height"]
    nmap = T.height_to_normal(h, su, sv)
    alb = res["albedo"]
    rough = res["rough"]
    metal = res["metal"]
    alb = T.dilate(alb.astype(np.float32), mask, 10)
    nmap = T.dilate(nmap.astype(np.float32), mask, 10)
    nmap /= np.maximum(np.linalg.norm(nmap, axis=-1, keepdims=True), 1e-6)
    rough = T.dilate(rough.astype(np.float32), mask, 10)
    metal = T.dilate(metal.astype(np.float32), mask, 10)
    paths = {}
    paths["albedo_lin"] = alb
    paths["normal"] = T.save_jpg(T.encode_normal(nmap), os.path.join(TMP, name + "_normal.jpg"), 90)
    paths["rough"] = rough
    paths["metal"] = metal
    return paths


def save_final(name, alb, rough, metal, ao, N, ormN):
    from PIL import Image
    alb8 = T.to_srgb8(alb * (0.72 + 0.28 * ao[..., None]))
    pa = T.save_jpg(alb8, os.path.join(TMP, name + "_albedo.jpg"), 88)
    orm = np.stack([ao, rough, metal], -1)
    orm8 = np.clip(orm * 255 + 0.5, 0, 255).astype(np.uint8)
    im = Image.fromarray(orm8)
    if ormN != N:
        im = im.resize((ormN, ormN), Image.LANCZOS)
    po = os.path.join(TMP, name + "_orm.jpg")
    im.save(po, quality=88)
    return pa, po


def gltf_output_group():
    g = bpy.data.node_groups.get("glTF Material Output")
    if g:
        return g
    g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    g.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def make_material(name, albedo, normal, orm, double_sided=False, rough_const=None, emissive=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    out = nt.nodes.get("Material Output")

    def img_node(path, colorspace, x, y):
        im = bpy.data.images.load(path)
        im.colorspace_settings.name = colorspace
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = im
        n.location = (x, y)
        return n

    a = img_node(albedo, "sRGB", -600, 300)
    nt.links.new(a.outputs["Color"], bsdf.inputs["Base Color"])
    if normal:
        nn = img_node(normal, "Non-Color", -600, -300)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-300, -300)
        nt.links.new(nn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if orm:
        on = img_node(orm, "Non-Color", -900, 0)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-600, 0)
        nt.links.new(on.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = gltf_output_group()
        grp.location = (0, -500)
        nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    elif rough_const is not None:
        bsdf.inputs["Roughness"].default_value = rough_const
    if emissive:
        bsdf.inputs["Emission Color"].default_value = (*emissive[0], 1)
        bsdf.inputs["Emission Strength"].default_value = emissive[1]
    mat.use_backface_culling = not double_sided
    return mat


def bake_ao(objs_all, ob, N, name, distance=0.12, samples=48):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.light_settings.distance = distance
    img = bpy.data.images.new(name + "_ao", N, N, float_buffer=True)
    for mat in ob.data.materials:
        nt = mat.node_tree
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        n.name = "AO_BAKE"
        nt.nodes.active = n
    select_only([ob])
    sc.render.bake.margin = 6
    sc.render.bake.use_selected_to_active = False
    bpy.ops.object.bake(type="AO")
    px = np.array(img.pixels[:]).reshape(N, N, 4)[::-1, :, 0]  # Blender images are bottom-up
    for mat in ob.data.materials:
        nt = mat.node_tree
        n = nt.nodes.get("AO_BAKE")
        if n:
            nt.nodes.remove(n)
    bpy.data.images.remove(img)
    return px


# ----------------------------------------------------------------------------------
# main build
# ----------------------------------------------------------------------------------


def build(cid):
    t0 = time.time()
    cfg = dict(CHARACTERS[cid])
    cfg.setdefault("belt_y", 1.0)
    print("==", cid, cfg["desc"])
    B = C.build_body(cfg)
    R = C.regions(B)
    parts, extra = make_parts(cid, cfg, B, R)
    for pt in parts:
        finalize_part(pt, B)
    for lst in extra.values():
        for pt in lst:
            finalize_part(pt, B)
    print(" geometry %.1fs" % (time.time() - t0), {p.name: p.m.ntris() for p in parts})
    cb.reset()
    sk = ca.skeleton()
    arm = cb.create_armature(sk, "Armature")
    parts = split_skin_components(parts)
    groups = {}
    for pi, pt in enumerate(parts):
        groups.setdefault(pt.group, []).append((pi, pt))
    hi = {g: G.merge([pt.m for _, pt in lst]) for g, lst in groups.items()}
    tg0 = part_targets(groups, {pi: pt.m.ntris() for pi, pt in enumerate(parts)}, LOD0_BUDGET, FIXED0,
                       head_min_frac=0.6)
    obs = {}
    for g, lst in groups.items():
        pobs = []
        for pi, pt in lst:
            ob = blender_obj("%s_%s_%d" % (cid, g, pi), pt.m)
            sym = abs(pt.m.v[:, 0].mean()) < 0.01 and g in ("skin", "helmet", "hair")
            decimate(ob, tg0[pi], symmetric=sym)
            set_face_int(ob, "part", pi)
            pobs.append(ob)
        ob = join(pobs, cid + "_" + g)
        print("  group %s: %d parts, %d tris -> UV" % (g, len(pobs), ntris(ob)), flush=True)
        if g in ("skin", "eyes") and hi[g].loop_uv is not None:
            pack_only(ob, 0.006)  # MakeHuman UV islands, repacked to fill the atlas
        else:
            smart_uv(ob, margin=0.004 if TEXSIZE[g] >= 1024 else 0.008)
        obs[g] = ob
    # extra objects (officer cap) share the cloth material
    extra_obs = {}
    for k, lst in extra.items():
        m = G.merge([p.m for p in lst])
        ob = blender_obj(k, m)
        smart_uv(ob, 0.01)
        extra_obs[k] = (ob, m)
    enforce_budget(obs, LOD0_BUDGET)
    print(" LOD0 tris", {g: ntris(o) for g, o in obs.items()}, sum(ntris(o) for o in obs.values()))
    # ---- textures (painted on the LOD0 geometry)
    mats = {}
    maps = {}
    for g, ob in obs.items():
        co, vn, tv, tuv = read_mesh(ob)
        W, attrs = lookup_attrs(co, hi[g], vn)
        maps[g] = dict(W=W, attrs=attrs)
        N = TEXSIZE[g]
        M = raster_group(ob, attrs, N)
        civ = cfg.get("era") == "1940"
        if g == "skin":
            res = MAT.paint_skin(M, B.landmarks, cfg, B.sk)
            moustache(res, M, B.landmarks, cfg)
            CV.legwear(res, M, cfg, B.sk)
        elif g == "cloth" and civ:
            res = CV.paint_cloth(M, cfg, B.sk, B.landmarks)
        elif g == "gear" and civ:
            res = CV.paint_gear(M, cfg, B.sk)
        elif g == "helmet" and civ:
            res = CV.paint_helmet(M, cfg)
        elif g == "cloth":
            res = MAT.paint_cloth(M, dict(cfg, tunic_style=("officer" if cfg.get("uniform") == "officer" else
                                                              cfg.get("tunic_style", "private"))), B.sk, B.landmarks)
            cap_cloth_paint(res, M, cfg)
        elif g == "gear":
            res = MAT.paint_gear(M, cfg, B.sk)
        elif g == "helmet":
            res = MAT.paint_helmet(M, cfg)
        elif g == "hair":
            res = MAT.paint_hair(M, cfg, B.landmarks)
        elif g == "eyes":
            res = MAT.paint_eyes(M, cfg, B.landmarks)
        fm = finish_maps(res, M, N, ORMSIZE[g], "%s_%s" % (cid, g))
        maps[g].update(fm=fm, M=M)
        # temporary material for AO baking
        tmp_alb = T.save_jpg(T.to_srgb8(fm["albedo_lin"]), os.path.join(TMP, "%s_%s_tmp.jpg" % (cid, g)))
        mat = make_material("%s_%s" % (cid, g), tmp_alb, fm["normal"], None,
                            double_sided=(g == "cloth"))
        ob.data.materials.append(mat)
        mats[g] = mat
    print(" textures %.1fs" % (time.time() - t0))
    # ---- AO bake (whole character present)
    for g, ob in obs.items():
        N = TEXSIZE[g]
        if g in ("eyes",) or os.environ.get("CW_FAST"):
            ao = np.ones((N, N))
        else:
            ao = bake_ao(list(obs.values()), ob, N, "%s_%s" % (cid, g),
                         distance=0.03 if g == "hair" else 0.12, samples=32 if N <= 512 else 48)
            ao = np.clip(ao, 0, 1)
            mask = maps[g]["M"]["mask"]
            ao = T.dilate(ao.astype(np.float32), mask, 10)
            ao = 0.35 + 0.65 * ao  # keep it subtle
        fm = maps[g]["fm"]
        pa, po = save_final("%s_%s" % (cid, g), fm["albedo_lin"], fm["rough"], fm["metal"], ao, TEXSIZE[g], ORMSIZE[g])
        # rebuild final material
        old = mats[g]
        newm = make_material("%s_%s" % (cid, g), pa, fm["normal"] if g != "eyes" else None, po,
                             double_sided=(g == "cloth"))
        ob.data.materials[0] = newm
        bpy.data.materials.remove(old)
        newm.name = "%s_%s" % (cid, g)
        mats[g] = newm
    print(" AO %.1fs" % (time.time() - t0))
    # ---- skin weights (LOD0)
    for g, ob in obs.items():
        cb.set_weights_dense(ob, sk.names, maps[g]["W"])
    # ---- detached parts (e.g. the baby bundle): own object, same material/atlas
    for pi, pt in enumerate(parts):
        if pt.detach:
            ob = obs[pt.group]
            od = extract_part(ob, pi, pt.name)
            remove_part(ob, pi)
            extra_obs[pt.name] = (od, None)
    # ---- LOD1: per-part decimation of the LOD0 geometry (keeps the LOD0 UVs / textures)
    lod1 = {}
    part_tris0 = {}
    for g, ob in obs.items():
        for pi, cnt in part_tri_counts(ob).items():
            part_tris0[pi] = cnt
    groups1 = {g: [(pi, pt) for pi, pt in lst if not pt.detach] for g, lst in groups.items()}
    groups1 = {g: lst for g, lst in groups1.items() if lst}
    tg1 = part_targets(groups1, part_tris0, LOD1_BUDGET, FIXED1, keep_small=False)
    for g, ob in obs.items():
        pieces = []
        for pi, _ in groups[g]:
            if parts[pi].detach:
                continue
            obp = extract_part(ob, pi, "%s_%s_%d_LOD1" % (cid, g, pi))
            if obp is None:
                continue
            for vg in list(obp.vertex_groups):
                obp.vertex_groups.remove(vg)
            sym = abs(parts[pi].m.v[:, 0].mean()) < 0.01 and g in ("skin", "helmet", "hair")
            decimate(obp, tg1[pi], symmetric=sym)
            pieces.append(obp)
        lod1[g] = join(pieces, ob.name + "_LOD1")
    for g, ob1 in lod1.items():
        co, vn, tv, tuv = read_mesh(ob1)
        W, _ = lookup_attrs(co, hi[g], vn)
        cb.set_weights_dense(ob1, sk.names, W)
    enforce_budget(lod1, LOD1_BUDGET)
    print(" LOD1 tris", {g: ntris(o) for g, o in lod1.items()}, sum(ntris(o) for o in lod1.values()))
    # ---- extra objects
    for k, (ob, m) in extra_obs.items():
        if m is None:  # detached part: already weighted and textured
            continue
        co, vn, tv, tuv = read_mesh(ob)
        Wx, attrs = lookup_attrs(co, m)
        cb.set_weights_dense(ob, sk.names, Wx)
        ob.data.materials.append(mats["cloth"])
    # ---- join per LOD, bind, export
    order = ["skin", "eyes", "hair", "cloth", "gear", "helmet"]
    l0 = [obs[g] for g in order if g in obs]
    l1 = [lod1[g] for g in order if g in lod1]
    select_only(l0, l0[0])
    bpy.ops.object.join()
    o0 = bpy.context.view_layer.objects.active
    o0.name = cid
    o0.data.name = cid
    select_only(l1, l1[0])
    bpy.ops.object.join()
    o1 = bpy.context.view_layer.objects.active
    o1.name = cid + "_LOD1"
    o1.data.name = cid + "_LOD1"
    final = [o0, o1] + [ob for ob, _ in extra_obs.values()]
    for o in final:
        bpy.context.view_layer.objects.active = o
        smooth_all(o)
        cb.bind(o, arm)
    stats = dict(lod0=ntris(o0), lod1=ntris(o1), extra={k: ntris(ob) for k, (ob, _) in extra_obs.items()})
    # smaller characters: uniform scale on the armature node (bones/clips stay canonical)
    s = float(cfg.get("scale", 1.0))
    arm.scale = (s, s, s)
    stats["scale"] = s
    out = os.path.join(P.OUT, cid + ".glb")
    select_only([arm] + final, arm)
    bpy.ops.export_scene.gltf(
        filepath=out, export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
        export_animations=False, export_skins=True, export_def_bones=False, export_morph=False,
        export_image_format="JPEG", export_jpeg_quality=85, export_image_quality=85,
        export_influence_nb=4, export_all_influences=False, export_tangents=False,
        export_cameras=False, export_lights=False, export_extras=False)
    # keep a .blend for previews/debugging
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P.WORK, cid + ".blend"))
    stats["bytes"] = os.path.getsize(out)
    print(" exported", out, stats, "%.1fs" % (time.time() - t0))
    return stats


def moustache(res, M, Lm, cfg):
    amt = cfg.get("moustache", 0)
    if not amt:
        return
    p = M["pos"]
    mo = Lm["mouth"]
    x = np.abs(p[..., 0] - mo[0])
    y = p[..., 1] - mo[1]
    band = T.sstep(0.022, 0.016, x) * T.sstep(0.0035, 0.006, y) * T.sstep(0.017, 0.012, y) * (M["nrm"][..., 2] > 0.2)
    hairs = 0.5 + 0.5 * MAT.gnoise(np.stack([p[..., 0] * 3000, p[..., 1] * 800, p[..., 2] * 800], -1), 91)
    col = MAT.srgb(cfg.get("hair_col", (70, 50, 34))) * 0.85
    res["albedo"] = T.lerp(res["albedo"], col, np.clip(band * (0.6 + 0.4 * hairs) * amt, 0, 0.95))
    res["height"] = res["height"] + 0.0003 * band * hairs
    res["rough"] = np.where(band > 0.5, 0.6, res["rough"])


def cap_cloth_paint(res, M, cfg):
    """Knitted cap comforter / officer cap colours inside the cloth atlas."""
    kind = np.rint(M["kind"][..., 0]).astype(int)
    p = M["pos"]
    cc = kind == K["cap_cloth"]
    if cc.any():
        rib = np.sin(np.arctan2(p[..., 0], p[..., 2]) * 90)
        knit = 0.5 + 0.5 * MAT.gnoise(p * 1800, 5)
        col = MAT.srgb(cfg.get("cap_col", (98, 90, 62) if cfg.get("uniform") != "officer" else (118, 102, 70)))
        res["albedo"][cc] = (col * (0.85 + 0.12 * rib[..., None] + 0.08 * knit[..., None]))[cc]
        res["height"] = np.where(cc, 0.0004 * rib + 0.0002 * knit, res["height"])
        res["rough"] = np.where(cc, 0.95, res["rough"])
    pk = kind == K["cap_peak"]
    if pk.any():
        res["albedo"][pk] = MAT.srgb((60, 40, 26))
        res["rough"] = np.where(pk, 0.4, res["rough"])


def main(argv):
    ids = argv or list(CHARACTERS.keys())
    allstats = {}
    for cid in ids:
        allstats[cid] = build(cid)
    import json
    sp = os.path.join(P.WORK, "character_stats.json")
    old = json.load(open(sp)) if os.path.exists(sp) else {}
    old.update(allstats)
    json.dump(old, open(sp, "w"), indent=1)
    print(old)


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("-")])
