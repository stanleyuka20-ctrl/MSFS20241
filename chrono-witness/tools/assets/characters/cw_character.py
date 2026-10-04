"""Character geometry assembly (numpy): body variants, landmarks, clothing and gear meshes.
Used by build_character.py (Blender) which adds UVs, textures, LODs and exports."""
import numpy as np

import cw_garment as G
import mhcore as mh
from cw_anim import nrm

BONES = [b[0] for b in mh.reduced_bone_list()]
BI = {n: i for i, n in enumerate(BONES)}


def wsum(W, names):
    return W[:, [BI[n] for n in names if n in BI]].sum(1)


def bones_like(prefixes):
    return [n for n in BONES if n.startswith(tuple(prefixes))]


# ----------------------------------------------------------------------------------
# body
# ----------------------------------------------------------------------------------


class BodyData:
    pass


def build_body(cfg):
    """cfg['macro'], cfg['details'] -> BodyData with canonical-skeleton-fitted verts."""
    base = mh.load_base()
    v = mh.body_verts(cfg["macro"], cfg.get("details"))
    v = v + np.array([0, mh.ground_offset(v), 0])
    Wfull = mh.reduced_weights(len(v))
    # smaller characters (women, children, the elderly): fit onto the canonical skeleton scaled
    # by cfg['scale'], then magnify the mesh back to the canonical size; the exported armature
    # node carries the uniform scale so the shared (rotation + hips-translation) clips play
    # unchanged on every character.
    cs = cfg.get("scale", 1.0)
    v, off = mh.fit_to_canonical(v, Wfull, scale=cs)
    v = v / cs
    fi = base["groups"]["body"]
    faces = [base["faces"][i] for i in fi]
    fuv = [base["face_uv"][i] for i in fi]
    used = np.unique(np.concatenate([np.array(f) for f in faces]))
    remap = -np.ones(len(v), int)
    remap[used] = np.arange(len(used))
    B = BodyData()
    B.v_all = v  # includes helper geometry (for eyes / joints)
    B.v = v[used]
    B.mh_index = used
    B.f = [tuple(remap[list(f)]) for f in faces]
    B.fuv = [[tuple(base["uvs"][t]) for t in tt] for tt in fuv]
    B.W = Wfull[used]
    B.W /= np.maximum(B.W.sum(1, keepdims=True), 1e-9)
    B.ref = G.Body(B.v, B.f, B.W)
    B.n = B.ref.n
    _, csk = mh.canonical()
    B.sk = {b["name"]: b for b in csk}
    B.landmarks = landmarks(B)
    return B


def J(B, name, end="head"):
    return np.asarray(B.sk[name][end])


def landmarks(B):
    v = B.v_all
    base = mh.load_base()
    L = {}
    for s, g in (("L", "helper-l-eye"), ("R", "helper-r-eye")):
        idx = np.unique(np.concatenate([np.array(base["faces"][i]) for i in base["groups"][g]]))
        L["eye." + s] = v[idx].mean(0)
    hv = B.v[B.v[:, 1] > 1.5]
    mid = hv[np.abs(hv[:, 0]) < 0.004]
    sel = mid[(mid[:, 1] < L["eye.L"][1] - 0.01) & (mid[:, 1] > L["eye.L"][1] - 0.08)]
    L["nose"] = sel[np.argmax(sel[:, 2])]
    L["top"] = hv[np.argmax(hv[:, 1])]
    L["back"] = hv[np.argmin(hv[:, 2])]
    s = mh.load_mhskel()
    jp = lambda n: mh.joint_pos(v, n)
    L["mouth"] = (jp("oris01____head") + jp("oris05____head")) / 2
    L["mouth"][2] = max(jp("oris01____head")[2], jp("oris05____head")[2])
    L["mouth_c.L"] = jp("oris03.L____head") + np.array([0.008, 0, -0.004])
    L["mouth_c.R"] = L["mouth_c.L"] * np.array([-1, 1, 1])
    L["chin"] = jp("special04____head")
    L["jaw"] = jp("jaw____head")
    L["head"] = J(B, "head")
    # ears: lateral-most head points around eye height behind the eyes
    for sd, sg in (("L", 1), ("R", -1)):
        c = hv[(hv[:, 1] > L["eye.L"][1] - 0.06) & (hv[:, 1] < L["eye.L"][1] + 0.02) & (hv[:, 2] < L["eye.L"][2] - 0.05)]
        e = c[np.argmax(c[:, 0] * sg)]
        L["ear." + sd] = e
    L["brow.L"] = L["eye.L"] + np.array([0.004, 0.022, 0.012])
    L["brow.R"] = L["eye.R"] + np.array([-0.004, 0.022, 0.012])
    return L


# ----------------------------------------------------------------------------------
# regions (per body vertex scalars)
# ----------------------------------------------------------------------------------


def seg_param(B, p, a_name, b_name, a_end="head", b_end="head"):
    a = J(B, a_name, a_end)
    b = J(B, b_name, b_end)
    d = b - a
    return ((p - a) @ d) / (d @ d)


def regions(B):
    W = B.W
    R = {}
    R["hand"] = wsum(W, bones_like(["wrist", "finger"]))
    R["arm"] = wsum(W, bones_like(["upperarm", "lowerarm", "wrist", "finger", "shoulder01"]))
    R["leg"] = wsum(W, bones_like(["upperleg", "lowerleg", "foot", "toes"]))
    R["foot"] = wsum(W, bones_like(["foot", "toes"]))
    R["head"] = wsum(W, ["head", "jaw"])
    R["neck"] = wsum(W, ["neck01", "neck02"])
    p = B.v
    for s, sg in (("L", 1), ("R", -1)):
        side = (p[:, 0] * sg) > 0
        fa = seg_param(B, p, "lowerarm01." + s, "wrist." + s)
        R["fa." + s] = np.where(side, fa, -9)
        sh = seg_param(B, p, "lowerleg01." + s, "foot." + s)
        R["shin." + s] = np.where(side, sh, -9)
    R["fa"] = np.maximum(R["fa.L"], R["fa.R"])
    R["shin"] = np.maximum(R["shin.L"], R["shin.R"])
    return R


def faces_all(B, vmask):
    vm = np.asarray(vmask)
    return np.array([vm[list(f)].all() for f in B.f])


def faces_any(B, vmask):
    vm = np.asarray(vmask)
    return np.array([vm[list(f)].any() for f in B.f])


# ----------------------------------------------------------------------------------
# garments
# ----------------------------------------------------------------------------------


def tunic(B, R, cfg):
    """Service-dress style tunic: shell above the waist, extruded skirt, stand collar,
    cuff lips.  Returns (mesh, body coverage mask)."""
    hem = cfg.get("hem", 0.775)
    waist = cfg.get("waist_cut", 0.975)
    cuff = cfg.get("cuff", 0.86)
    p = B.v
    sel_v = (p[:, 1] >= waist) & (R["hand"] < 0.35) & (R["fa"] < cuff) & (R["neck"] + R["head"] < 0.55)
    if cfg.get("collar") == "open":
        sel_v &= ~vneck_region(B, R, cfg)
    # a sleeve may be rolled up (wounded): cut that forearm higher
    for s in cfg.get("short_sleeve", []):
        sel_v &= ~(R["fa." + s] > cfg.get("short_sleeve_at", 0.05))
    fsel = faces_all(B, sel_v)
    ease = np.full(len(p), cfg.get("ease", 0.011))
    ease += 0.004 * np.clip((1.3 - p[:, 1]) / 0.3, 0, 1)  # looser over the belly / skirt top
    ease = np.where(R["arm"] > 0.5, cfg.get("sleeve_ease", 0.010), ease)
    m = G.shell(B.ref, fsel, ease, smooth=cfg.get("smooth", 24), dmin=ease * 0.75)
    loops = G.boundary_loops(m.f)
    # identify loops by mean height / position
    info = []
    for L in loops:
        c = m.v[L].mean(0)
        info.append((L, c))
    waist_loop = min(info, key=lambda x: x[1][1])[0]
    neck_loop = max(info, key=lambda x: x[1][1] if abs(x[1][0]) < 0.05 else -9)[0]
    cuffs = [x[0] for x in info if abs(x[1][0]) > 0.2]
    # flatten waist loop to a horizontal ring
    m.v[waist_loop, 1] = waist
    G.laplacian_smooth(m, 4, 0.4, body=B.ref, dmin=0.008)
    body_pts = B.v[(R["arm"] < 0.4)]
    nlev = cfg.get("nlev", 7)
    hs = np.linspace(waist, hem, nlev + 1)[1:]
    se = cfg.get("skirt_ease", (0.016, 0.03))
    sf = cfg.get("skirt_flare", (0.0, 0.004))
    eases = np.linspace(se[0], se[1], nlev)
    flares = np.linspace(sf[0], sf[1], nlev)
    G.extrude_loop(m, waist_loop, hs, body_pts, eases, flares, weight_body=B.ref, blend=cfg.get("skirt_blend", 0.55))
    # collar: stand up the neck, then fall back down outside
    nl = neck_loop
    neck_pts = B.v[(R["neck"] > 0.3) | (R["head"] > 0.3)]
    y0 = m.v[nl, 1].mean()
    collar_h = cfg.get("collar_h", 0.040)
    if cfg.get("collar", "stand") == "stand":
        ny = m.v[nl, 1]
        # move the neck loop vertices up in 3 steps following the neck hull (+ease)
        loopv = m.v[nl]
        ctr = loopv[:, [0, 2]].mean(0)
        ang = np.arctan2(loopv[:, 2] - ctr[1], loopv[:, 0] - ctr[0])
        r0 = np.linalg.norm(loopv[:, [0, 2]] - ctr, axis=1)
        prev = np.array(nl)
        new_rings = []
        for k, dy in enumerate(np.linspace(collar_h / 3, collar_h, 3)):
            ys = ny + dy
            hp = G.slice_hull(neck_pts, ys.mean(), half=0.01)
            rh = G._poly_radius(hp, ctr, ang) if hp is not None else r0
            r = np.maximum(rh + 0.004, r0 * (1 - 0.09 * (k + 1)))
            for _ in range(5):
                r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
            pts = np.stack([ctr[0] + r * np.cos(ang), ys, ctr[1] + r * np.sin(ang)], 1)
            new_rings.append(pts)
        # fold: out and down
        top = new_rings[-1]
        outd = np.stack([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1)
        f1 = top + outd * 0.0035 + np.array([0, 0.0015, 0])
        f2 = top + outd * 0.006 - np.array([0, collar_h * 0.6, 0])
        f2[:, 1] = np.maximum(f2[:, 1], ny + 0.004)
        f3 = f2 + outd * 0.012 - np.array([0, 0.010, 0])
        allr = new_rings + [f1, f2, f3]
        base = len(m.v)
        m.v = np.concatenate([m.v] + allr, 0)
        Wn = m.W[nl]
        m.W = np.concatenate([m.W] + [Wn] * len(allr), 0)
        m.src = np.concatenate([m.src, -np.ones(len(nl) * len(allr), int)])
        for key in list(m.attrs.keys()):
            m.attrs[key] = np.concatenate([m.attrs[key]] + [m.attrs[key][nl]] * len(allr), 0)
        rings = [np.array(nl)] + [np.arange(base + i * len(nl), base + (i + 1) * len(nl)) for i in range(len(allr))]
        G._connect_rings(m, rings, flip=_ring_flip(m, nl))
        m.attrs.setdefault("part", np.zeros(len(m.v)))
    elif cfg.get("collar") == "open":
        # fold the whole neck opening outwards onto the chest: lapels + flat collar
        G.lip(m, nl, depth=-0.0035, back=cfg.get("lapel", 0.035), smooth_loop=12)
    for c in cuffs:
        G.lip(m, c, depth=0.004, back=0.015, smooth_loop=4)
    # hem lip
    loops = G.boundary_loops(m.f)
    hem_loop = min(loops, key=lambda L: m.v[L, 1].mean())
    G.lip(m, hem_loop, depth=0.005, back=0.02)
    cover = sel_v.copy()
    # body under the skirt / collar is hidden too (keep a margin near the openings)
    cover |= (p[:, 1] > hem + 0.06) & (R["arm"] < 0.3) & (R["neck"] + R["head"] < 0.3)
    cover &= ~((R["fa"] > cuff - 0.08) | (R["hand"] > 0.1))
    cover &= ~((R["neck"] + R["head"]) > 0.25)
    if cfg.get("collar") == "open":
        cover &= ~vneck_region(B, R, cfg, grow=0.02)
    return m, cover


def _ring_flip(m, loop):
    """Decide orientation for rings attached to a boundary loop so normals face outwards:
    boundary edge (a->b) in its face; new quad (a,b,b',a') must traverse a->b reversed."""
    e = G.edges_of(m.f)
    a, b = loop[0], loop[1]
    fs = e.get((min(a, b), max(a, b)), [])
    if not fs:
        return False
    ff = m.f[fs[0]]
    for k in range(len(ff)):
        if ff[k] == a and ff[(k + 1) % len(ff)] == b:
            return True  # face has a->b, new quad must have b->a: (a, b', ...) flip variant
    return False


def trousers(B, R, cfg):
    top = cfg.get("top", 1.0)
    bottom_shin = cfg.get("bottom_shin", 0.32)  # shin parameter where the puttee starts
    p = B.v
    sel_v = (p[:, 1] <= top) & (R["leg"] + wsum(B.W, ["hips", "spine05", "pelvis.L", "pelvis.R"]) > 0.5) & \
            (R["shin"] < bottom_shin) & (R["foot"] < 0.3) & (R["hand"] < 0.1)
    fsel = faces_all(B, sel_v)
    ease = np.full(len(p), cfg.get("ease", 0.012))
    # riding breeches flare on the outer thigh
    if cfg.get("breeches"):
        for s, sg in (("L", 1), ("R", -1)):
            th = seg_param(B, p, "upperleg02." + s, "lowerleg01." + s)
            outer = np.clip(p[:, 0] * sg - np.abs(J(B, "upperleg02." + s)[0]) + 0.03, 0, 0.06) / 0.06
            bump = np.exp(-((th - 0.45) / 0.22) ** 2) * outer
            ease = ease + np.where(p[:, 0] * sg > 0, bump * cfg["breeches"], 0)
    m = G.shell(B.ref, fsel, ease, smooth=cfg.get("smooth", 18), dmin=ease * 0.7)
    loops = G.boundary_loops(m.f)
    for L in loops:
        if m.v[L, 1].mean() < 0.7:
            G.lip(m, L, depth=0.004, back=0.012)
    cover = sel_v & (R["shin"] < bottom_shin - 0.06)
    return m, cover


def leg_wrap(B, R, side, t0, t1, ease, nseg=18, nring=10, kind="puttee"):
    """Loft around the lower leg between shin params t0..t1 (0 knee, 1 ankle)."""
    a = J(B, "lowerleg01." + side)
    b = J(B, "foot." + side)
    p = B.v
    sidem = (p[:, 0] * (1 if side == "L" else -1)) > 0.02
    legpts = p[sidem & (R["leg"] > 0.5) & (R["foot"] < 0.6)]
    ts = np.linspace(t0, t1, nring)
    path = a[None] + (b - a)[None] * ts[:, None]
    axis = nrm(b - a)

    def radii(k, ang, fr):
        c, T, Nn, Bn = fr
        d = legpts - c
        along = d @ T
        sl = legpts[np.abs(along) < 0.012]
        if len(sl) < 6:
            return np.full(len(ang), 0.05)
        q = sl - c
        x = q @ Nn
        y = q @ Bn
        P2 = np.stack([x, y], 1)
        try:
            h = G.ConvexHull(P2)
            hp = P2[h.vertices]
            r = G._poly_radius(hp, np.zeros(2), ang)
        except Exception:
            r = np.full(len(ang), np.sqrt((P2 ** 2).sum(1)).max())
        e = ease(k / (nring - 1)) if callable(ease) else ease
        r = r + e
        for _ in range(4):
            r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
        return r

    m = G.loft(path, radii, nseg=nseg)
    m.attrs["part"] = np.zeros(len(m.v))
    return m


def _hull_radius_2d(P2, center, ang):
    try:
        h = G.ConvexHull(P2)
        return G._poly_radius(P2[h.vertices], center, ang)
    except Exception:
        return np.full(len(ang), np.sqrt(((P2 - center) ** 2).sum(1)).max() if len(P2) else 0.02)


def boots(B, R, cfg):
    """Ankle boots built from two lofts: the foot (slices along the foot axis, convex hulls
    of the foot cross-sections + ease, rounded heel/toe caps, flat welted sole) and the ankle
    shaft (horizontal hull slices of the ankle).  Returns (mesh, body coverage)."""
    p = B.v
    top = cfg.get("top", 0.165)
    ease = cfg.get("ease", 0.007)
    meshes = []
    for s, sg in (("L", 1), ("R", -1)):
        side = (p[:, 0] * sg) > 0.02
        fv = p[side & (R["foot"] > 0.3) & (p[:, 1] < 0.115)]
        z0, z1 = fv[:, 2].min() - 0.004, fv[:, 2].max() + cfg.get("toe_extra", 0.004)
        nst = 16
        zs = np.linspace(z0, z1, nst)
        nseg = 20
        ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
        rings = []
        cx_prev = None
        for k, z in enumerate(zs):
            sl = fv[np.abs(fv[:, 2] - z) < 0.012]
            if len(sl) < 5:
                sl = fv[np.argsort(np.abs(fv[:, 2] - z))[:12]]
            P2 = np.concatenate([sl[:, [0, 1]], np.stack([sl[:, 0], np.zeros(len(sl))], 1)], 0)
            c = np.array([P2[:, 0].mean(), (P2[:, 1].max() + 0.0) / 2])
            r = _hull_radius_2d(P2, c, ang) + ease
            for _ in range(3):
                r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
            ring = np.stack([c[0] + r * np.cos(ang), c[1] + r * np.sin(ang), np.full(nseg, z)], 1)
            rings.append(ring)
        R3 = np.array(rings)
        for _ in range(3):
            R3[1:-1, :, :2] = 0.25 * R3[:-2, :, :2] + 0.5 * R3[1:-1, :, :2] + 0.25 * R3[2:, :, :2]
        rings = list(R3)
        # rounded caps
        def cap(ring, zc, dz, scales):
            c = ring.mean(0)
            c[1] = ring[:, 1].min() + 0.32 * (ring[:, 1].max() - ring[:, 1].min())
            out = []
            for i, sc in enumerate(scales):
                rr = c + (ring - c) * sc
                rr[:, 2] = zc + dz * (i + 1) / len(scales)
                out.append(rr)
            return out
        heel = cap(rings[0], zs[0], -0.014, [0.93, 0.78, 0.5])[::-1]
        toe = cap(rings[-1], zs[-1], 0.018, [0.95, 0.84, 0.62, 0.3])
        allr = heel + rings + toe
        V = np.concatenate(allr, 0)
        K = len(allr)
        f = []
        for k in range(K - 1):
            for i in range(nseg):
                j = (i + 1) % nseg
                a, b = k * nseg + i, k * nseg + j
                c_, d = (k + 1) * nseg + j, (k + 1) * nseg + i
                f.append((a, d, c_, b))
        # poles
        pa = len(V)
        pb = pa + 1
        pc0 = allr[0].mean(0)
        pc0[1] = allr[0][:, 1].min() + 0.32 * np.ptp(allr[0][:, 1])
        pc1 = allr[-1].mean(0)
        pc1[1] = allr[-1][:, 1].min() + 0.32 * np.ptp(allr[-1][:, 1])
        V = np.concatenate([V, pc0[None] + np.array([0, 0, -0.002]), pc1[None] + np.array([0, 0, 0.002])], 0)
        for i in range(nseg):
            j = (i + 1) % nseg
            f.append((pa, i, j))
            f.append((pb, (K - 1) * nseg + j, (K - 1) * nseg + i))
        foot = G.Mesh(V, f)
        G.ensure_outward(foot)
        # flat welted sole
        y = foot.v[:, 1]
        foot.v[:, 1] = np.where(y < 0.013, 0.0, foot.v[:, 1])
        c2 = foot.v[:, [0, 2]].mean(0)
        low = foot.v[:, 1] < 0.02
        d = foot.v[low][:, [0, 2]] - c2
        foot.v[np.where(low)[0][:, None], [0, 2]] += nrm(np.concatenate([d[:, :1], np.zeros((len(d), 1)), d[:, 1:]], 1))[:, [0, 2]] * 0.003
        foot.attrs["bootpart"] = np.zeros(len(foot.v))
        meshes.append(foot)
        # shaft
        a = J(B, "foot." + s)
        kn = J(B, "lowerleg01." + s)
        legv = p[side & (R["leg"] > 0.5) & (p[:, 1] > 0.03) & (p[:, 1] < top + 0.03)]
        hs = np.linspace(0.06, top, 6)
        sh_rings = []
        nseg2 = 20
        ang2 = np.linspace(0, 2 * np.pi, nseg2, endpoint=False)
        for k, yv in enumerate(hs):
            t = (yv - a[1]) / (kn[1] - a[1])
            cc = a + (kn - a) * t
            sl = legv[np.abs(legv[:, 1] - yv) < 0.012]
            if yv < 0.1:  # include the heel/ankle bone bulk
                sl = np.concatenate([sl, fv[(np.abs(fv[:, 1] - yv) < 0.015) & (fv[:, 2] < a[2] + 0.03)]], 0)
            P2 = sl[:, [0, 2]]
            r = _hull_radius_2d(P2, cc[[0, 2]], ang2) + ease + 0.002
            for _ in range(3):
                r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
            sh_rings.append(np.stack([cc[0] + r * np.cos(ang2), np.full(nseg2, yv), cc[2] + r * np.sin(ang2)], 1))
        V = np.concatenate(sh_rings, 0)
        f = []
        for k in range(len(sh_rings) - 1):
            for i in range(nseg2):
                j = (i + 1) % nseg2
                a_, b_ = k * nseg2 + i, k * nseg2 + j
                c_, d_ = (k + 1) * nseg2 + j, (k + 1) * nseg2 + i
                f.append((a_, d_, c_, b_))
        shaft = G.Mesh(V, f)
        G.ensure_outward(shaft)
        top_loop = list(range((len(sh_rings) - 1) * nseg2, len(sh_rings) * nseg2))
        loops = G.boundary_loops(shaft.f)
        tl = max(loops, key=lambda L: shaft.v[L, 1].mean())
        G.lip(shaft, tl, depth=0.004, back=0.015)
        shaft.attrs["bootpart"] = np.ones(len(shaft.v))
        meshes.append(shaft)
    m = G.merge(meshes)
    sel_v = (R["foot"] + wsum(B.W, ["lowerleg02.L", "lowerleg02.R"]) > 0.4) & (p[:, 1] < top)
    cover = sel_v & (p[:, 1] < top - 0.02)
    return m, cover


def hair_cap(B, cfg):
    """Short hair: scalp shell with tapered thickness, top longer than back/sides."""
    Lm = B.landmarks
    p = B.v
    eye_y = Lm["eye.L"][1]
    hc = Lm["head"]
    rel = p - hc
    front = Lm["nose"][2]
    style = cfg.get("style", "short_back_sides")
    # hairline: forehead line, temples, around ears, nape
    hl_front = eye_y + cfg.get("hairline", 0.062)
    z = p[:, 2]
    y = p[:, 1]
    ax = np.abs(p[:, 0])
    # height threshold as function of z (front high, sides lower, nape lowest)
    zf = np.clip((z - (hc[2] - 0.02)) / (front - hc[2]), 0, 1)
    thr = (hl_front * zf + (eye_y + 0.01) * (1 - zf))
    thr = np.where(z < hc[2] - 0.03, J(B, "neck02")[1] + 0.035, thr)
    # temples recede slightly
    thr += 0.012 * np.exp(-((ax - 0.055) / 0.02) ** 2) * zf
    dens = np.clip((y - thr) / cfg.get("fade", 0.022), 0, 1)
    # ears excluded
    for s in "LR":
        e = Lm["ear." + s]
        d = np.linalg.norm((p - e) * np.array([1.0, 0.75, 1.0]), axis=1)
        dens *= np.clip((d - 0.03) / 0.012, 0, 1)
    head_r = (wsum(B.W, ["head"]) > 0.5)
    sel_v = (dens > cfg.get("cap_from", 0.4)) & head_r
    fsel = faces_all(B, sel_v)
    # thickness: top 9 mm, sides/back 2-3 mm
    top_amt = np.clip((y - (eye_y + 0.04)) / 0.06, 0, 1)
    cap_from = cfg.get("cap_from", 0.4)
    ramp = np.clip((dens - cap_from) / (1 - cap_from), 0, 1) ** 0.7
    th = (cfg.get("side", 0.0025) + cfg.get("top_len", 0.008) * top_amt) * ramp
    th = np.maximum(th, 0.0004)
    m = G.shell(B.ref, fsel, th, smooth=6, dmin=th * 0.6)
    m.attrs["dens"] = dens[m.src]
    return m, dens


# ----------------------------------------------------------------------------------
# hard-surface / gear
# ----------------------------------------------------------------------------------


def revolve(profile, nseg, scale_xz=(1.0, 1.0), close_top=True):
    """profile: list of (r, y) from the axis outward/downward. Returns Mesh (Y axis)."""
    prof = np.asarray(profile, float)
    ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    V = []
    for r, y in prof:
        V.append(np.stack([r * np.cos(ang) * scale_xz[0], np.full(nseg, y), r * np.sin(ang) * scale_xz[1]], 1))
    V = np.concatenate(V, 0)
    f = []
    K = len(prof)
    for k in range(K - 1):
        for i in range(nseg):
            j = (i + 1) % nseg
            a, b = k * nseg + i, k * nseg + j
            c, d = (k + 1) * nseg + j, (k + 1) * nseg + i
            if prof[k][0] < 1e-6:
                # pole row: triangles
                f.append((a, d, c))
            else:
                f.append((a, d, c, b))
    m = G.Mesh(V, f)
    m.attrs["prof_k"] = np.repeat(np.arange(K), nseg).astype(float)
    m.attrs["ang"] = np.tile(ang, K)
    return m


def brodie_helmet(B, cfg):
    """Brodie Mk I steel helmet: shallow bowl, wide brim, rolled rim, liner, chin strap."""
    Lm = B.landmarks
    H = cfg.get("H", 0.092)  # crown height above brim plane
    Rb = 0.112  # bowl radius at the brim junction (x)
    Rr = 0.157  # brim outer radius
    # dense outer profile: dome -> fillet -> gently drooping brim
    pts = []
    for r in np.linspace(0, Rb, 26):
        pts.append((r, H * max(1 - (r / Rb) ** 2.6, 0) ** 0.55))
    for r in np.linspace(Rb, Rr, 14)[1:]:
        t = (r - Rb) / (Rr - Rb)
        pts.append((r, -0.009 * t ** 1.3))
    pts = np.array(pts)
    for _ in range(6):  # fillet the bowl/brim kink
        pts[1:-1] = 0.25 * pts[:-2] + 0.5 * pts[1:-1] + 0.25 * pts[2:]
    pts[0] = (0.0, pts[1][1])
    # resample by arc length
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    sl = np.linspace(0, L[-1], 24)
    outer = np.stack([np.interp(sl, L, pts[:, 0]), np.interp(sl, L, pts[:, 1])], 1)
    outer[0, 0] = 0.0
    # 2D normals of the profile (pointing outwards/up)
    tg = np.gradient(outer, axis=0)
    nr = np.stack([tg[:, 1], -tg[:, 0]], 1)
    nr /= np.linalg.norm(nr, axis=1, keepdims=True)
    if nr[0, 1] < 0:
        nr = -nr
    th = 0.0016
    inner = outer - nr * th
    # rolled rim: small curl at the edge
    e = outer[-1]
    curl = [e + np.array([0.0012, -0.0006]), e + np.array([0.0016, -0.0024]), e + np.array([0.0006, -0.0036]),
            inner[-1] + np.array([-0.0006, -0.0012])]
    prof = [tuple(x) for x in outer]
    profile = prof + [tuple(x) for x in curl] + [tuple(x) for x in inner[::-1][:-1]] + [(0.0, inner[0][1])]
    m = revolve(profile, cfg.get("nseg", 40), scale_xz=(1.0, 1.085))
    no = len(prof)
    m.attrs["outer"] = (m.attrs["prof_k"] < no + 2).astype(float)
    # 0 at the crown .. 1 at the rim edge (for chipping)
    m.attrs["prof_k"] = np.clip(m.attrs["prof_k"] / (no + 2), 0, 1) * (m.attrs["prof_k"] < no + 4) + \
        (m.attrs["prof_k"] >= no + 4) * np.clip(1 - (m.attrs["prof_k"] - no - 4) / (no + 2), 0, 1)
    # liner: a short dark band inside the bowl
    def inner_r(yv):
        # radius of the inner bowl surface at height yv
        rr = np.linspace(0, Rb, 200)
        yy = (H - 0.002) * np.clip(1 - (rr / Rb) ** 2.6, 0, 1) ** 0.55
        return np.interp(-yv, -yy, rr)
    liner = revolve([(inner_r(0.046) - 0.005, 0.046), (inner_r(0.024) - 0.005, 0.024),
                     (inner_r(0.012) - 0.006, 0.012), (inner_r(0.012) - 0.016, 0.010)], 28, scale_xz=(1.0, 1.085))
    liner.attrs["outer"] = np.full(len(liner.v), 2.0)
    liner.attrs["prof_k"] = np.zeros(len(liner.v))
    G.flip_faces(liner)
    # place: tilt slightly forward, fit over the head + hair
    tilt = np.radians(cfg.get("tilt", 8.0))
    Rx = np.array([[1, 0, 0], [0, np.cos(tilt), np.sin(tilt)], [0, -np.sin(tilt), np.cos(tilt)]])
    cx = np.array([0, 0, (Lm["nose"][2] + Lm["back"][2]) / 2 - 0.006])
    hv = B.v[(wsum(B.W, ["head"]) > 0.5)]
    # solve height so the bowl interior clears the scalp (+hair) by `clear`
    clear = cfg.get("clear", 0.011)
    best = None
    for yb in np.linspace(Lm["eye.L"][1] + 0.0, Lm["eye.L"][1] + 0.11, 111):
        o = np.array([0, yb, cx[2]])
        q = (hv - o) @ Rx  # into helmet space (inverse rotation)
        r = np.sqrt(q[:, 0] ** 2 + (q[:, 2] / 1.085) ** 2)
        inside = r < Rb - 0.004
        t = np.clip(r / (Rb - 0.002), 0, 1)
        t = np.arcsin(np.clip(t, 0, 1) ** (1 / 0.9)) / (np.pi / 2)
        y_in = (H - 0.002) * (1 - t ** 2.3) ** 0.75
        ok = np.all(q[inside, 1] + clear < y_in[inside])
        if ok:
            best = yb
            break
    o = np.array([0, best + cfg.get("lift", 0.0), cx[2]])
    for mm in (m, liner):
        mm.v = mm.v @ Rx.T + o
    strap = None
    if cfg.get("chinstrap", True):
        # strap from the bowl sides down under the chin
        side_l = o + Rx @ np.array([Rb - 0.004, 0.010, 0.016])
        side_r = o + Rx @ np.array([-(Rb - 0.004), 0.010, 0.016])
        ch = Lm["chin"] + np.array([0, -0.012, 0.004])
        jl = Lm["jaw"] + np.array([0.055, -0.035, 0.03])
        jr = Lm["jaw"] + np.array([-0.055, -0.035, 0.03])
        ctrl = [side_r, (side_r + jr) / 2, jr, ch, jl, (side_l + jl) / 2, side_l]
        path = catmull(np.array(ctrl), 36)
        # keep the strap 3 mm off the skin
        sel = path[:, 1] < o[1] - 0.005
        d, idx = B.ref.tree.query(path, k=4)
        nb = nrm(B.ref.n[idx].mean(1))
        vb = B.ref.v[idx].mean(1)
        sdist = ((path - vb) * nb).sum(1)
        path = path + nb * np.maximum(0.003 - sdist, 0)[:, None] * sel[:, None]
        strap = ribbon(path, 0.011, 0.0022, B, normals=nb)
    return m, liner, strap


def catmull(ctrl, n):
    P = np.concatenate([ctrl[:1], ctrl, ctrl[-1:]], 0)
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, max(2, n // (len(ctrl) - 1)), endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(ctrl[-1])
    return np.array(out)


def ribbon(path, width, thick, B=None, outward_from=None, normals=None):
    """Flat strap along a path; normal = away from `outward_from` (or given normals)."""
    path = np.asarray(path)
    K = len(path)
    T = np.gradient(path, axis=0)
    T = nrm(T)
    if normals is None:
        Nn = nrm(path - outward_from)
    else:
        Nn = nrm(normals)
    Nn = nrm(Nn - (Nn * T).sum(1, keepdims=True) * T)
    S = np.cross(T, Nn)
    hw = width / 2
    # 4 verts per station: outer-left, outer-right, inner-right, inner-left
    V = np.concatenate([path + S * hw + Nn * thick, path - S * hw + Nn * thick, path - S * hw, path + S * hw], 0)
    f = []
    for k in range(K - 1):
        ol, orr, ir, il = k, K + k, 2 * K + k, 3 * K + k
        ol2, or2, ir2, il2 = ol + 1, orr + 1, ir + 1, il + 1
        f += [(ol, ol2, or2, orr), (orr, or2, ir2, ir), (ir, ir2, il2, il), (il, il2, ol2, ol)]
    # caps
    f.append((0, K, 2 * K, 3 * K))
    e = K - 1
    f.append((e + 3 * K, e + 2 * K, e + K, e))
    m = G.Mesh(V, f)
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    m.attrs["rib_s"] = np.tile(L, 4)
    m.attrs["rib_t"] = np.concatenate([np.ones(K), np.zeros(K), np.zeros(K), np.ones(K)])
    m.attrs["rib_out"] = np.concatenate([np.ones(2 * K), np.zeros(2 * K)])
    return m


def surface_path(points_ctrl, surf_mesh, offset, n=40, tree=None):
    """Spline through control points, projected onto a surface (closest vertex normal)."""
    from scipy.spatial import cKDTree
    path = catmull(np.asarray(points_ctrl, float), n)
    t = tree or cKDTree(surf_mesh.v)
    nm = G.vertex_normals_fast(surf_mesh.v, surf_mesh.f)
    for it in range(3):
        d, idx = t.query(path, k=6)
        w = 1 / np.maximum(d, 1e-4)
        w /= w.sum(1, keepdims=True)
        sp = (surf_mesh.v[idx] * w[..., None]).sum(1)
        sn = nrm((nm[idx] * w[..., None]).sum(1))
        path = sp + sn * offset
        # resmooth
        path[1:-1] = 0.25 * path[:-2] + 0.5 * path[1:-1] + 0.25 * path[2:]
    d, idx = t.query(path, k=6)
    w = 1 / np.maximum(d, 1e-4)
    w /= w.sum(1, keepdims=True)
    sn = nrm((nm[idx] * w[..., None]).sum(1))
    return path, sn


def band_around(surf_mesh, y_center, width, thick, offset, nseg=48, tilt=None, center=None, select=None):
    """Closed belt-like band around a mesh at height y (on the outside of surf_mesh)."""
    from scipy.spatial import cKDTree
    v = surf_mesh.v if select is None else surf_mesh.v[select]
    sl = v[np.abs(v[:, 1] - y_center) < max(width * 0.6, 0.02)]
    c = sl[:, [0, 2]].mean(0) if center is None else center
    P2 = sl[:, [0, 2]]
    h = G.ConvexHull(P2)
    hp = P2[h.vertices]
    ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    r = G._poly_radius(hp, c, ang) + offset
    for _ in range(3):
        r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
    ring = np.stack([c[0] + r * np.cos(ang), np.full(nseg, y_center), c[1] + r * np.sin(ang)], 1)
    if tilt is not None:
        ring[:, 1] += tilt(ang)
    outd = np.stack([np.cos(ang), np.zeros(nseg), np.sin(ang)], 1)
    hw = width / 2
    up = np.array([0, 1.0, 0])
    rings = [ring - up * hw, ring + up * hw, ring + up * hw + outd * thick, ring - up * hw + outd * thick]
    V = np.concatenate(rings, 0)
    f = []
    for a, b in ((0, 3), (3, 2), (2, 1), (1, 0)):
        for i in range(nseg):
            j = (i + 1) % nseg
            f.append((a * nseg + i, a * nseg + j, b * nseg + j, b * nseg + i))
    m = G.Mesh(V, f)
    G.ensure_outward(m)
    m.attrs["band_a"] = np.tile(ang, 4)
    m.attrs["band_t"] = np.concatenate([np.zeros(nseg), np.ones(nseg), np.ones(nseg), np.zeros(nseg)])
    m.attrs["band_out"] = np.concatenate([np.zeros(nseg), np.zeros(nseg), np.ones(nseg), np.ones(nseg)])
    return m


def box_on_surface(surf_mesh, center, size, depth, normal_hint, nx=5, ny=4, round_=0.35, tree=None):
    """A pouch-like rounded box whose back conforms to a surface. center: point near the
    surface; size: (width, height); returns Mesh with attr 'pouch_uv' (u,v,front)."""
    from scipy.spatial import cKDTree
    t = tree or cKDTree(surf_mesh.v)
    nm = G.vertex_normals_fast(surf_mesh.v, surf_mesh.f)
    nh = nrm(np.asarray(normal_hint, float))
    up = np.array([0, 1.0, 0])
    xs = nrm(np.cross(up, nh))
    ys = np.cross(nh, xs)
    w, h = size
    us = np.linspace(-0.5, 0.5, nx)
    vs = np.linspace(-0.5, 0.5, ny)
    back = np.zeros((ny, nx, 3))
    norms = np.zeros((ny, nx, 3))
    for j, vv in enumerate(vs):
        for i, uu in enumerate(us):
            q = center + xs * uu * w + ys * vv * h
            d, idx = t.query(q, k=6)
            ww = 1 / np.maximum(d, 1e-4)
            ww /= ww.sum()
            sp = (surf_mesh.v[idx] * ww[:, None]).sum(0)
            sn = nrm((nm[idx] * ww[:, None]).sum(0))
            # project q onto the tangent plane at sp
            back[j, i] = sp + sn * 0.002
            norms[j, i] = sn
    nav = nrm(norms.reshape(-1, 3).mean(0))
    # front surface: offset by depth, slightly domed, corners rounded inwards
    U, Vv = np.meshgrid(us, vs)
    edge = np.maximum(np.abs(U) * 2, np.abs(Vv) * 2)
    dome = depth * (1 - round_ * edge ** 4)
    front = back + nav * dome[..., None]
    # shrink front slightly for a tapered box
    cen = front.reshape(-1, 3).mean(0)
    front = cen + (front - cen) * 0.94
    V = np.concatenate([front.reshape(-1, 3), back.reshape(-1, 3)], 0)
    N = nx * ny
    f = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            f.append((a, a + 1, a + nx + 1, a + nx))
    # sides: connect border of front to border of back
    border = [(0, i) for i in range(nx)] + [(j, nx - 1) for j in range(1, ny)] + \
             [(ny - 1, i) for i in range(nx - 2, -1, -1)] + [(j, 0) for j in range(ny - 2, 0, -1)]
    bidx = [j * nx + i for j, i in border]
    K = len(bidx)
    for k in range(K):
        a, b = bidx[k], bidx[(k + 1) % K]
        f.append((a + N, b + N, b, a))
    m = G.Mesh(V, f)
    # orientation check: front faces should point along nav
    fn = np.cross(V[f[0][1]] - V[f[0][0]], V[f[0][3]] - V[f[0][0]])
    if np.dot(fn, nav) < 0:
        G.flip_faces(m)
    uu = np.concatenate([(U.ravel() + 0.5), (U.ravel() + 0.5)])
    vv = np.concatenate([(Vv.ravel() + 0.5), (Vv.ravel() + 0.5)])
    m.attrs["pouch_u"] = uu
    m.attrs["pouch_v"] = vv
    m.attrs["pouch_front"] = np.concatenate([np.ones(N), np.zeros(N)])
    return m


# ----------------------------------------------------------------------------------
# 1908 pattern webbing & accessories
# ----------------------------------------------------------------------------------


def front_point(surf, x, y, side=1, tree=None):
    """Point on a mesh surface at (x, y), front (side=1) or back (side=-1)."""
    v = surf.v
    sel = (np.abs(v[:, 0] - x) < 0.02) & (np.abs(v[:, 1] - y) < 0.02)
    if not sel.any():
        sel = np.argsort(np.abs(v[:, 0] - x) + np.abs(v[:, 1] - y))[:10]
        c = v[sel]
    else:
        c = v[sel]
    z = c[:, 2].max() if side > 0 else c[:, 2].min()
    return np.array([x, y, z])


def webbing_1908(B, tun, cfg):
    """Belt, crossed braces, two ammunition pouch sets, water bottle, entrenching tool
    head carrier, bayonet scabbard.  Returns dict name -> Mesh (with attr 'kind')."""
    out = {}
    from scipy.spatial import cKDTree
    tv = tun.v
    torso = (np.abs(tv[:, 0]) < 0.24)
    tt = G.Mesh(tv, tun.f)
    tree = cKDTree(tv[torso])
    tsurf = G.Mesh(tv[torso], [])
    tsurf_n = G.vertex_normals_fast(tun.v, tun.f)[torso]
    by = cfg.get("belt_y", 1.0)
    belt = band_around(tun, by, 0.068, 0.004, 0.0025, nseg=56,
                       select=torso & (np.abs(tv[:, 1] - by) < 0.05))
    out["belt"] = belt
    # buckle (brass) at the front
    fp = front_point(tsurf, 0.0, by)
    buckle = flat_box(fp + np.array([0, 0, 0.007]), np.array([0, 0, 1.0]), 0.055, 0.05, 0.004)
    out["buckle"] = buckle
    # pouches
    for s, sg in (("L", 1), ("R", -1)):
        c = front_point(tsurf, 0.095 * sg, 1.112)
        nh = np.array([0.18 * sg, 0.05, 1.0])
        m = box_on_surface(tt, c, (0.165, 0.13), 0.052, nh, nx=7, ny=5, round_=0.3)
        out["pouch." + s] = m
    # braces: front from the pouch top over the shoulder, crossing at the back to the belt
    for s, sg in (("L", 1), ("R", -1)):
        ctrl = [front_point(tsurf, 0.095 * sg, 1.17), front_point(tsurf, 0.10 * sg, 1.30),
                front_point(tsurf, 0.115 * sg, 1.40), np.array([0.125 * sg, 1.475, 0.005]),
                front_point(tsurf, 0.10 * sg, 1.40, -1), front_point(tsurf, 0.03 * sg, 1.25, -1),
                front_point(tsurf, -0.06 * sg, 1.12, -1), front_point(tsurf, -0.10 * sg, by + 0.01, -1)]
        ctrl = np.array(ctrl)
        ctrl[3] = surface_closest(tt, ctrl[3])
        path, nn = surface_path(ctrl, tt, 0.004, n=60)
        out["brace." + s] = ribbon(path, 0.048, 0.003, normals=nn)
    # water bottle (right hip), entrenching tool carrier (rear), bayonet scabbard (left hip)
    wb = revolve([(0.0, 0.0), (0.03, 0.004), (0.055, 0.03), (0.06, 0.08), (0.056, 0.13), (0.04, 0.158),
                  (0.015, 0.165), (0.013, 0.178), (0.0, 0.18)], 18, scale_xz=(0.62, 1.0))
    wb.v = wb.v[:, [0, 1, 2]]
    yaw = np.radians(-70)
    Ry = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    hipR = front_point(G.Mesh(B.v, []), -0.17, 0.92)
    wb.v = wb.v @ Ry.T + np.array([-0.205, by - 0.235, -0.01])
    out["bottle"] = wb
    et = box_on_surface(tt, front_point(tsurf, 0.0, 0.89, -1), (0.17, 0.16), 0.045, np.array([0, -0.1, -1.0]),
                        nx=5, ny=4, round_=0.45)
    out["etool"] = et
    sc = scabbard(np.array([0.175, by - 0.03, -0.075]), length=0.46, angle_deg=cfg.get("scab_angle", 14))
    out["scabbard"] = sc
    return out


def surface_closest(mesh, p):
    d = np.linalg.norm(mesh.v - p, axis=1)
    i = np.argmin(d)
    n = G.vertex_normals_fast(mesh.v, mesh.f)[i]
    return mesh.v[i] + n * 0.003


def flat_box(center, normal, w, h, d):
    n = nrm(normal)
    up = np.array([0, 1.0, 0])
    x = nrm(np.cross(up, n))
    y = np.cross(n, x)
    corners = []
    for dz in (0, d):
        for sy in (-1, 1):
            for sx in (-1, 1):
                corners.append(center + x * sx * w / 2 + y * sy * h / 2 + n * dz)
    V = np.array(corners)
    f = [(4, 5, 7, 6), (0, 2, 3, 1), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    m = G.Mesh(V, f)
    return m


def scabbard(top, length=0.46, angle_deg=14):
    """Leather bayonet scabbard hanging from the belt frog, tilted backwards."""
    prof = [(0.0, 0.0), (0.006, 0.005), (0.012, 0.03), (0.016, 0.2), (0.019, 0.38), (0.02, length - 0.02),
            (0.023, length), (0.0, length + 0.002)]
    m = revolve([(r, -y) for r, y in prof][::-1], 10, scale_xz=(0.45, 1.0))
    a = np.radians(angle_deg)
    Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    m.v = m.v + np.array([0, 0, 0])
    m.v = (m.v) @ Rx.T + top
    # frog (leather loop) at the top
    return m


def eyes_mesh(B, which="high-poly"):
    import os
    import cw_paths as P
    path = os.path.join(P.MH_DATA, "eyes", which, which + ".mhclo")
    clo = mh.load_mhclo(path)
    ev, euv, ef, efuv = mh.load_obj_simple(clo["obj"])
    pv = mh.fit_mhclo(clo, B.v_all)
    m = G.Mesh(pv, ef)
    m.loop_uv = [[tuple(euv[t]) for t in tt] for tt in efuv]
    return m


def vneck_region(B, R, cfg, grow=0.0):
    p = B.v
    yv = cfg.get("v_bottom", 1.36) - grow
    ytop = 1.53
    w = np.clip((p[:, 1] - yv) / (ytop - yv), 0, 1) ** 0.8 * (cfg.get("v_width", 0.075) + grow)
    front = p[:, 2] > J(B, "spine01")[2] + 0.02
    below_head = (p[:, 1] < J(B, "neck01")[1] + 0.03) & (R["head"] < 0.15)
    return front & (np.abs(p[:, 0]) < w) & (p[:, 1] > yv) & (R["arm"] < 0.3) & below_head


def shirt_tie(B, R, cfg):
    """Shirt visible in the open neck (+ optional collar and tie)."""
    p = B.v
    vr = vneck_region(B, R, cfg, grow=0.05)
    neckband = (R["neck"] > 0.15) & (p[:, 1] < J(B, "neck01")[1] + 0.02) & (R["head"] < 0.1)
    sel_v = (vr | neckband) & (R["arm"] < 0.3)
    fsel = faces_all(B, sel_v)
    m = G.shell(B.ref, fsel, 0.004, smooth=10, dmin=0.003)
    loops = G.boundary_loops(m.f)
    parts = [m]
    if cfg.get("shirt_collar", True):
        nl = max(loops, key=lambda L: m.v[L, 1].mean())
        loopv = m.v[nl]
        ctr = loopv[:, [0, 2]].mean(0)
        ang = np.arctan2(loopv[:, 2] - ctr[1], loopv[:, 0] - ctr[0])
        neck_pts = B.v[(R["neck"] > 0.3) | (R["head"] > 0.3)]
        ny = loopv[:, 1]
        ring_list = []
        r0 = np.linalg.norm(loopv[:, [0, 2]] - ctr, axis=1)
        for k, dy in enumerate((0.01, 0.019, 0.026)):
            hp = G.slice_hull(neck_pts, (ny + dy).mean(), half=0.01)
            rh = G._poly_radius(hp, ctr, ang) if hp is not None else r0
            r = rh + 0.004
            for _ in range(4):
                r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
            ring_list.append(np.stack([ctr[0] + r * np.cos(ang), ny + dy, ctr[1] + r * np.sin(ang)], 1))
        top = ring_list[-1]
        outd = np.stack([np.cos(ang), np.zeros_like(ang), np.sin(ang)], 1)
        f1 = top + outd * 0.003 + np.array([0, 0.001, 0])
        f2 = top + outd * 0.006 - np.array([0, 0.022, 0])
        # collar points at the front
        frontw = np.clip(np.sin(ang), 0, 1) ** 6
        f2 += outd * 0.004 * frontw[:, None] - np.array([0, 0.008, 0]) * frontw[:, None]
        allr = ring_list + [f1, f2]
        base = len(m.v)
        m.v = np.concatenate([m.v] + allr, 0)
        m.src = np.concatenate([m.src, -np.ones(len(nl) * len(allr), int)])
        for key in list(m.attrs.keys()):
            m.attrs[key] = np.concatenate([m.attrs[key]] + [m.attrs[key][nl]] * len(allr), 0)
        rings = [np.array(nl)] + [np.arange(base + i * len(nl), base + (i + 1) * len(nl)) for i in range(len(allr))]
        G._connect_rings(m, rings, flip=True)
    if cfg.get("tie", False):
        fy = J(B, "neck01")[1] + 0.012
        ctrl = [front_point(G.Mesh(m.v, []), 0.0, fy), front_point(G.Mesh(m.v, []), 0.0, fy - 0.06),
                front_point(G.Mesh(m.v, []), 0.0, cfg.get("v_bottom", 1.36) - 0.05)]
        path, nn = surface_path(np.array(ctrl), m, 0.004, n=16)
        tie = ribbon(path, 0.045, 0.004, normals=nn)
        tie.attrs["kind_override"] = np.ones(len(tie.v))
        knot = flat_box(path[0] + nn[0] * 0.004, nn[0], 0.022, 0.02, 0.008)
        parts += [("tie", tie), ("tie", knot)]
    return parts


def limb_wrap(B, pts_mask, a, b, t0, t1, ease, nseg=18, nring=8):
    p = B.v[pts_mask]
    ts = np.linspace(t0, t1, nring)
    path = a[None] + (b - a)[None] * ts[:, None]

    def radii(k, ang, fr):
        c, T, Nn, Bn = fr
        d = p - c
        along = d @ T
        sl = p[np.abs(along) < 0.012]
        if len(sl) < 6:
            return np.full(len(ang), 0.04)
        q = sl - c
        P2 = np.stack([q @ Nn, q @ Bn], 1)
        r = _hull_radius_2d(P2, np.zeros(2), ang)
        e = ease(k / max(nring - 1, 1)) if callable(ease) else ease
        r = r + e
        for _ in range(4):
            r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
        return r

    return G.loft(path, radii, nseg=nseg)


def torso_surface(tun, xmax=0.2):
    src = tun.src if tun.src is not None else np.zeros(len(tun.v), int)
    keep = np.array([np.all(np.abs(tun.v[list(f), 0]) < xmax) and np.all(src[list(f)] >= 0) for f in tun.f])
    return G.submesh(tun.v, tun.f, keep)


def sam_browne(B, tun, cfg):
    out = {}
    tv = tun.v
    torso = np.abs(tv[:, 0]) < 0.24
    tt = torso_surface(tun)
    tsurf = G.Mesh(tv[torso], [])
    by = cfg.get("belt_y", 1.0)
    out["sb_belt"] = band_around(tun, by, 0.056, 0.004, 0.0025, nseg=56, select=torso & (np.abs(tv[:, 1] - by) < 0.05))
    fp = front_point(tsurf, 0.0, by)
    out["sb_buckle"] = flat_box(fp + np.array([0, 0, 0.006]), np.array([0, 0, 1.0]), 0.05, 0.045, 0.004)
    ctrl = np.array([front_point(tsurf, 0.10, by + 0.02), front_point(tsurf, 0.05, 1.2), front_point(tsurf, -0.04, 1.33),
                     front_point(tsurf, -0.11, 1.42), np.array([-0.14, 1.47, 0.0]),
                     front_point(tsurf, -0.09, 1.38, -1), front_point(tsurf, 0.0, 1.22, -1),
                     front_point(tsurf, 0.10, by + 0.02, -1)])
    ctrl[4] = surface_closest(tt, ctrl[4])
    path, nn = surface_path(ctrl, tt, 0.006, n=60)
    out["sb_strap"] = ribbon(path, 0.03, 0.003, normals=nn)
    # holster (right hip) and ammunition pouch (left)
    out["holster"] = box_on_surface(tt, front_point(tsurf, -0.17, by - 0.07), (0.1, 0.17), 0.045,
                                    np.array([-1.0, -0.1, 0.35]), nx=4, ny=5, round_=0.5)
    out["sb_pouch"] = box_on_surface(tt, front_point(tsurf, 0.15, by - 0.05), (0.07, 0.07), 0.03,
                                     np.array([0.8, -0.1, 0.6]), nx=3, ny=3, round_=0.5)
    return out


def service_cap(B, cfg):
    """Officer's soft service cap (separate mesh 'cap', hidden by default)."""
    Lm = B.landmarks
    yb = Lm["eye.L"][1] + 0.052
    cz = (Lm["nose"][2] + Lm["back"][2]) / 2 - 0.004
    prof = [(0.0, 0.085), (0.06, 0.084), (0.115, 0.078), (0.135, 0.068), (0.128, 0.05), (0.104, 0.045),
            (0.1, 0.03), (0.099, 0.0), (0.094, 0.0), (0.094, 0.044), (0.0, 0.046)]
    m = revolve(prof, 36, scale_xz=(1.0, 1.12))
    G.flip_faces(m) if False else None
    tilt = np.radians(-3)
    Rx = np.array([[1, 0, 0], [0, np.cos(tilt), np.sin(tilt)], [0, -np.sin(tilt), np.cos(tilt)]])
    m.v = m.v @ Rx.T + np.array([0, yb, cz])
    # peak
    ang = np.linspace(-1.25, 1.25, 13) + np.pi / 2
    rin = np.stack([0.099 * np.cos(ang), np.zeros_like(ang), 0.099 * 1.12 * np.sin(ang)], 1)
    rout = np.stack([0.15 * np.cos(ang), -0.022 * np.ones_like(ang), 0.15 * 1.08 * np.sin(ang)], 1)
    rout[:, 2] = np.maximum(rout[:, 2], rin[:, 2] + 0.01)
    V = np.concatenate([rin, rout, rin - np.array([0, 0.003, 0]), rout - np.array([0, 0.003, 0])], 0)
    n = len(ang)
    f = []
    for i in range(n - 1):
        f.append((i, i + 1, n + i + 1, n + i))
        f.append((2 * n + i, 3 * n + i, 3 * n + i + 1, 2 * n + i + 1))
    peak = G.Mesh(V, f)
    peak.v = peak.v @ Rx.T + np.array([0, yb + 0.003, cz])
    return m, peak


def cap_comforter(B, cfg):
    """Knitted wool cap comforter worn as a beanie with a rolled brim."""
    Lm = B.landmarks
    p = B.v
    hc = Lm["head"]
    eye_y = Lm["eye.L"][1]
    front = Lm["nose"][2]
    zf = np.clip((p[:, 2] - (hc[2] - 0.02)) / (front - hc[2]), 0, 1)
    thr = (eye_y + 0.05) * zf + (eye_y + 0.02) * (1 - zf)
    for s in "LR":
        e = Lm["ear." + s]
        thr = np.maximum(thr, np.where(np.linalg.norm(p - e, axis=1) < 0.045, e[1] + 0.045, thr))
    sel_v = (p[:, 1] > thr) & (wsum(B.W, ["head"]) > 0.5)
    fsel = faces_all(B, sel_v)
    m = G.shell(B.ref, fsel, 0.009, smooth=12, dmin=0.007)
    # slightly peaked crown
    top = np.clip((m.v[:, 1] - (eye_y + 0.09)) / 0.03, 0, 1)
    m.v[:, 1] += 0.006 * top
    loops = G.boundary_loops(m.f)
    L = max(loops, key=len)
    P_ = m.v[L].copy()
    for _ in range(25):
        P_ = 0.5 * P_ + 0.25 * (np.roll(P_, 1, 0) + np.roll(P_, -1, 0))
    m.v[L] = P_
    m.v[L], _ = B.ref.push_out(m.v[L], 0.007)
    G.laplacian_smooth(m, 4, 0.4, body=B.ref, dmin=0.006)
    G.lip(m, L, depth=-0.006, back=0.026, smooth_loop=12)
    return m, sel_v


def haversack(B, tun, cfg):
    tv = tun.v
    tt = torso_surface(tun, 0.26)
    tfull = G.Mesh(tv, tun.f)
    c = np.array([0.19, 0.87, 0.02])
    sel = (tv[:, 0] > 0.1) & (np.abs(tv[:, 1] - c[1]) < 0.02)
    c = tv[sel][np.argmax(tv[sel][:, 0])]
    bag = box_on_surface(tfull, c, (0.25, 0.19), 0.065, np.array([1.0, -0.05, 0.15]), nx=6, ny=5, round_=0.35)
    torso = np.abs(tv[:, 0]) < 0.24
    tsurf = G.Mesh(tv[torso], [])
    ctrl = np.array([c + np.array([-0.02, 0.09, 0.05]), front_point(tsurf, 0.08, 1.1), front_point(tsurf, -0.04, 1.3),
                     np.array([-0.125, 1.475, 0.0]), front_point(tsurf, -0.04, 1.3, -1), front_point(tsurf, 0.09, 1.1, -1),
                     c + np.array([-0.02, 0.09, -0.05])])
    ctrl[3] = surface_closest(tt, ctrl[3])
    path, nn = surface_path(ctrl, tt, 0.006, n=60)
    strap = ribbon(path, 0.038, 0.003, normals=nn)
    return bag, strap


def head_bandage(B, cfg):
    """Gauze bandage wound around the head: two overlapping band regions of the scalp/forehead
    (tilted planes), shelled 4-6 mm off the skin + hair, with rolled edges."""
    Lm = B.landmarks
    p = B.v
    hc = Lm["head"]
    eye_y = Lm["eye.L"][1]
    head = wsum(B.W, ["head"]) > 0.55
    out = []
    bands = [  # (centre point on the forehead, plane normal, half width)
        (np.array([0, eye_y + 0.03, 0.0]), nrm(np.array([0, 1.0, -0.2])), 0.024),
        (np.array([0, eye_y + 0.07, 0.0]), nrm(np.array([0.5, 1.0, -0.1])), 0.021),
    ]
    for k, (c, n_, hw) in enumerate(bands):
        d = (p - c) @ n_
        # keep clear of the eyes and ears
        sel = head & (np.abs(d) < hw)
        for s in "LR":
            sel &= np.linalg.norm(p - Lm["ear." + s], axis=1) > 0.03
        sel &= p[:, 1] > eye_y + 0.018
        fsel = faces_all(B, sel)
        # keep the largest connected strip only (avoids bow-tie fragments)
        fidx = np.where(fsel)[0]
        if len(fidx) < 10:
            continue
        sub = G.submesh(B.v, B.f, fsel)
        from scipy.sparse.csgraph import connected_components
        nc, lab = connected_components(G.adjacency(len(sub.v), sub.f), directed=False)
        flab = np.array([lab[f[0]] for f in sub.f])
        big = np.bincount(flab).argmax()
        fsel = np.zeros(len(B.f), bool)
        fsel[fidx[flab == big]] = True
        m = G.shell(B.ref, fsel, 0.009 + 0.005 * k, smooth=10, dmin=0.008 + 0.005 * k)
        for L in G.boundary_loops(m.f):
            G.lip(m, L, depth=0.003, back=0.008, smooth_loop=10)
        dd = (m.v - c) @ n_
        ang = np.arctan2(m.v[:, 0] - hc[0], m.v[:, 2] - hc[2])
        m.attrs = {"loft_s": dd + 0.03 * k, "loft_a": ang}
        out.append(m)
    return out
