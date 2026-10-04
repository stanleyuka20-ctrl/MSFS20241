"""London 1940 civilian cast: garment/gear builders (numpy) and painters.

Characters are assembled from an `outfit` description in characters_cfg.py (era="1940").
All geometry is built at the canonical (adult) size; smaller characters are scaled by the
exported armature node (cfg['scale']) so the shared clips play unchanged.
"""
import numpy as np

import cw_character as C
import cw_garment as G
import cw_materials as MAT
import cw_tex as T
from cw_anim import nrm
from cw_tex import fbm, gnoise, sstep, srgb

K = MAT.K
K.update(dict(coat=23, overall=24, dress=25, cardigan=26, cape=27, scarf=28, blanket=29, felt_hat=32,
              hatband=33, fire_tunic=34, wood=35, cardboard=36, string=37, shoe=38, slipper=39,
              rubber_boot=41, chrome=42, flatcap=43))
KN = {v: k for k, v in K.items()}


class P_:
    """Light part record (converted to build_character.Part by make_parts)."""

    def __init__(self, group, name, mesh, kind, weights="body", smooth=2, detach=False):
        self.group, self.name, self.m, self.kind = group, name, mesh, kind
        self.weights, self.smooth, self.detach = weights, smooth, detach


# ----------------------------------------------------------------------------------
# letters (helmet "W"/"R", armband "ARP", "AFS")
# ----------------------------------------------------------------------------------

STROKES = {
    "W": [[(-1, 1), (-0.5, -1), (0, 0.35), (0.5, -1), (1, 1)]],
    "R": [[(-0.75, -1), (-0.75, 1), (0.35, 1), (0.75, 0.72), (0.75, 0.28), (0.35, 0.02), (-0.75, 0.02)],
          [(0.05, 0.02), (0.8, -1)]],
    "A": [[(-0.9, -1), (0, 1), (0.9, -1)], [(-0.48, -0.12), (0.48, -0.12)]],
    "F": [[(-0.7, -1), (-0.7, 1), (0.8, 1)], [(-0.7, 0.08), (0.5, 0.08)]],
    "S": [[(0.8, 0.75), (0.4, 1), (-0.4, 1), (-0.8, 0.62), (-0.45, 0.08), (0.45, -0.08), (0.8, -0.55),
           (0.4, -1), (-0.4, -1), (-0.8, -0.75)]],
    "P": [[(-0.75, -1), (-0.75, 1), (0.35, 1), (0.75, 0.68), (0.75, 0.38), (0.35, 0.08), (-0.75, 0.08)]],
}


def _seg_dist(u, v, a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    d = b - a
    t = np.clip(((u - a[0]) * d[0] + (v - a[1]) * d[1]) / (d @ d), 0, 1)
    return np.hypot(u - (a[0] + t * d[0]), v - (a[1] + t * d[1]))


def text_mask(u, v, text, stroke=0.2, spacing=2.5):
    """Block letters from line strokes; (u, v) in letter units (each glyph spans [-1,1]^2),
    the text is centred on u = 0."""
    n = len(text)
    m = np.zeros_like(u)
    for i, ch in enumerate(text):
        cu = (i - (n - 1) / 2) * spacing
        uu = u - cu
        near = (np.abs(uu) < 1.4) & (np.abs(v) < 1.4)
        if not near.any():
            continue
        d = np.full(u.shape, 9.0)
        for poly in STROKES[ch]:
            for a, b in zip(poly[:-1], poly[1:]):
                d = np.minimum(d, _seg_dist(uu, v, a, b))
        m = np.maximum(m, sstep(stroke, stroke * 0.7, d) * near)
    return m


# ----------------------------------------------------------------------------------
# geometry helpers
# ----------------------------------------------------------------------------------


def head_rest_y(B, band_r, zscale=1.1, extra=0.012):
    """Height at which a ring of radius band_r (x) / band_r*zscale (z) rests on the head
    (+ hair / scarf thickness `extra`).  Returns (y, centre_z)."""
    Lm = B.landmarks
    hv = B.v[C.wsum(B.W, ["head"]) > 0.5]
    cz = (Lm["nose"][2] + Lm["back"][2]) / 2 - 0.005
    top = hv[:, 1].max()
    for yy in np.arange(top - 0.004, Lm["eye.L"][1], -0.002):
        sl = hv[np.abs(hv[:, 1] - yy) < 0.004]
        if len(sl) < 6:
            continue
        r = np.sqrt(sl[:, 0] ** 2 + ((sl[:, 2] - cz) / zscale) ** 2).max() + extra
        if r >= band_r:
            return yy, cz
    return Lm["eye.L"][1] + 0.05, cz


def place(m, y, cz, tilt_x=0.0, tilt_z=0.0, dz=0.0):
    a = np.radians(tilt_x)
    Rx = np.array([[1, 0, 0], [0, np.cos(a), np.sin(a)], [0, -np.sin(a), np.cos(a)]])
    b = np.radians(tilt_z)
    Rz = np.array([[np.cos(b), -np.sin(b), 0], [np.sin(b), np.cos(b), 0], [0, 0, 1]])
    m.v = m.v @ (Rz @ Rx).T + np.array([0, y, cz + dz])
    return m


def top_garment(B, R, o):
    """Coat / overall blouse / dress / cardigan / fire tunic built on the tunic shell."""
    hem = o.get("hem", 0.8)
    waist = 0.975
    nlev = max(2, int(round((waist - hem) / 0.045)))
    long_ = hem < 0.7
    t = dict(hem=hem, nlev=nlev, cuff=o.get("cuff", 0.88), ease=o.get("ease", 0.013),
             sleeve_ease=o.get("sleeve_ease", 0.012),
             skirt_ease=o.get("skirt_ease", (0.022, 0.05) if long_ else (0.018, 0.032)),
             skirt_flare=o.get("skirt_flare", (0.0, 0.007) if long_ else (0.0, 0.004)),
             skirt_blend=0.6, smooth=o.get("smooth", 26))
    if o.get("collar", "open") == "open":
        t.update(collar="open", v_bottom=o.get("v_bottom", 1.34), v_width=o.get("v_width", 0.075),
                 lapel=o.get("lapel", 0.045))
    else:
        t.update(collar="stand", collar_h=o.get("collar_h", 0.04))
    if o.get("short_sleeve"):
        t.update(short_sleeve=o["short_sleeve"], short_sleeve_at=o.get("short_sleeve_at", 0.1))
    m, cover = C.tunic(B, R, t)
    return m, cover, t


def cape(B, R, o):
    """Shoulder cape / blanket: shell over the shoulders, then a drape extruded down through
    convex-hull slices of the torso + upper arms."""
    p = B.v
    ys = o.get("top", 1.40)
    hem = o.get("hem", 1.18)
    ease = o.get("ease", 0.024)
    sel_v = (p[:, 1] >= ys) & (R["head"] + R["neck"] < 0.45) & (R["hand"] < 0.1)
    fsel = C.faces_all(B, sel_v)
    m = G.shell(B.ref, fsel, ease, smooth=24, dmin=ease * 0.8)
    loops = G.boundary_loops(m.f)
    nl = max(loops, key=lambda L: m.v[L, 1].mean())
    bl = min(loops, key=lambda L: m.v[L, 1].mean())
    m.v[bl, 1] = ys
    G.laplacian_smooth(m, 4, 0.4, body=B.ref, dmin=ease * 0.7)
    pts = p[(R["hand"] < 0.2) & (R["fa"] < 0.15) & (p[:, 1] > hem - 0.06) & (p[:, 1] < ys + 0.02) &
            (R["head"] + R["neck"] < 0.3)]
    nlev = max(3, int(round((ys - hem) / 0.035)))
    hs = np.linspace(ys, hem, nlev + 1)[1:]
    G.extrude_loop(m, bl, hs, pts, np.linspace(ease + 0.004, ease + 0.016, nlev),
                   np.linspace(0.002, 0.006, nlev), weight_body=B.ref, blend=0.6)
    G.lip(m, nl, depth=-0.004, back=o.get("collar", 0.03), smooth_loop=12)
    loops = G.boundary_loops(m.f)
    hl = min(loops, key=lambda L: m.v[L, 1].mean())
    G.lip(m, hl, depth=0.006, back=0.02)
    m.attrs["civ1"] = m.v[:, 1] - hem
    return m


def shorts(B, R, o):
    return C.trousers(B, R, dict(bottom_shin=o.get("bottom", -0.28), ease=0.014, top=1.0))


def hair_female(B, cfg):
    """Pinned-up 1940 hair: scalp shell (fuller on top) + a rolled pompadour at the nape."""
    h = dict(cfg.get("hair", {}))
    h.setdefault("top_len", 0.013)
    h.setdefault("side", 0.006)
    h.setdefault("hairline", 0.058)
    m, dens = C.hair_cap(B, h)
    Lm = B.landmarks
    hv = B.v[C.wsum(B.W, ["head"]) > 0.5]
    yr = (Lm["ear.L"][1] + Lm["ear.R"][1]) / 2 - 0.03 + h.get("roll_dy", 0.0)
    cz = (Lm["nose"][2] + Lm["back"][2]) / 2
    sl = hv[np.abs(hv[:, 1] - yr) < 0.01]
    c2 = np.array([0.0, cz])
    th = np.radians(np.linspace(-72, 72, 19)) + np.pi * 1.5  # around the back (-Z), ear to ear
    rr = C._hull_radius_2d(sl[:, [0, 2]], c2, th) + h.get("side", 0.006) * 0.5
    path = np.stack([rr * np.cos(th), np.full(len(th), yr), cz + rr * np.sin(th)], 1)
    path[:, 1] += 0.022 * (1 - np.cos(np.linspace(-1.3, 1.3, len(th))) ** 2)  # rises towards the ears
    rad = h.get("roll_r", 0.015) * (0.25 + 0.75 * np.sin(np.linspace(0.08, np.pi - 0.08, len(th))) ** 0.6)

    def radii(k, ang, fr):
        return np.full(len(ang), rad[k])

    roll = G.loft(path, radii, nseg=10)
    roll.v, _ = B.ref.push_out(roll.v, 0.004)
    roll.attrs = {"dens": np.ones(len(roll.v))}
    m.attrs = {"dens": m.attrs["dens"]}
    out = G.merge([m, roll])
    return out, dens


def hair_bob(B, cfg):
    """Girl's bob with a fringe: hair down to the jaw at the sides/back, ears covered."""
    h = cfg.get("hair", {})
    Lm = B.landmarks
    p = B.v
    eye_y = Lm["eye.L"][1]
    hc = Lm["head"]
    front = Lm["nose"][2]
    zf = np.clip((p[:, 2] - (hc[2] - 0.0)) / (front - hc[2]), 0, 1)
    jaw_y = Lm["jaw"][1] - 0.01
    fringe_y = eye_y + h.get("fringe", 0.03)
    thr = fringe_y * zf + jaw_y * (1 - zf)
    headw = C.wsum(B.W, ["head", "neck02"]) > 0.35
    sel_v = (p[:, 1] > thr) & headw
    sel_v &= ~((p[:, 1] < jaw_y + 0.06) & (p[:, 2] > Lm["ear.L"][2] + 0.02))  # keep the cheeks clear
    fsel = C.faces_all(B, sel_v)
    low = np.clip((eye_y + 0.03 - p[:, 1]) / 0.08, 0, 1)
    th = 0.007 + 0.006 * np.clip((p[:, 1] - (eye_y + 0.04)) / 0.06, 0, 1) + 0.012 * low
    m = G.shell(B.ref, fsel, th, smooth=14, dmin=th * 0.6)
    for L in G.boundary_loops(m.f):
        if len(L) >= 8:
            G.lip(m, L, depth=0.004, back=0.006, smooth_loop=8)
    dens = np.clip((p[:, 1] - thr) / 0.02, 0, 1)
    m.attrs = {"dens": np.ones(len(m.v))}
    return m, dens


def headscarf(B, o):
    """Headscarf over the hair, framing the face, tied under the chin (ribbon ties + knot)."""
    Lm = B.landmarks
    p = B.v
    eye_y = Lm["eye.L"][1]
    hc = Lm["head"]
    front = Lm["nose"][2]
    ear_z = (Lm["ear.L"][2] + Lm["ear.R"][2]) / 2
    zf = np.clip((p[:, 2] - (ear_z + 0.005)) / 0.03, 0, 1)
    jaw_y = Lm["jaw"][1] - 0.005
    thr = (eye_y + o.get("front", 0.062)) * zf + jaw_y * (1 - zf)
    headw = C.wsum(B.W, ["head"]) > 0.35
    back_neck = (C.wsum(B.W, ["neck02", "neck01"]) > 0.4) & (p[:, 2] < C.J(B, "neck02")[2] - 0.01) & \
        (p[:, 1] > C.J(B, "neck02")[1] - 0.01)
    sel_v = ((p[:, 1] > thr) & headw) | back_neck
    fsel = C.faces_all(B, sel_v)
    th = o.get("thick", 0.016)
    m = G.shell(B.ref, fsel, th, smooth=16, dmin=th * 0.8)
    loops = G.boundary_loops(m.f)
    L = max(loops, key=len)
    P_ = m.v[L].copy()
    for _ in range(20):
        P_ = 0.5 * P_ + 0.25 * (np.roll(P_, 1, 0) + np.roll(P_, -1, 0))
    m.v[L] = P_
    m.v[L], _ = B.ref.push_out(m.v[L], th * 0.8)
    G.laplacian_smooth(m, 3, 0.4, body=B.ref, dmin=th * 0.7)
    G.lip(m, L, depth=-0.004, back=0.012, smooth_loop=10)
    # ties under the chin
    jl = Lm["jaw"] + np.array([0.05, -0.03, 0.035])
    jr = Lm["jaw"] + np.array([-0.05, -0.03, 0.035])
    ch = Lm["chin"] + np.array([0, -0.022, 0.0])
    ctrl = np.array([jr + np.array([-0.008, 0.02, -0.01]), jr, (jr + ch) / 2 + np.array([0, -0.006, 0]), ch,
                     (jl + ch) / 2 + np.array([0, -0.006, 0]), jl, jl + np.array([0.008, 0.02, -0.01])])
    path = C.catmull(ctrl, 30)
    d, idx = B.ref.tree.query(path, k=4)
    nb = nrm(B.ref.n[idx].mean(1))
    vb = B.ref.v[idx].mean(1)
    sdist = ((path - vb) * nb).sum(1)
    path = path + nb * np.maximum(0.006 - sdist, 0)[:, None]
    ties = C.ribbon(path, 0.022, 0.003, normals=nb)
    knot = C.flat_box(ch + np.array([0, -0.004, 0.006]), nrm(np.array([0, -0.6, 1.0])), 0.03, 0.026, 0.016)
    return m, ties, knot


def revolve_hat(B, prof, band_r, zscale, extra, tilt=4.0, tilt_z=0.0, forward=0.0, nseg=36, dz=0.0, lift=0.0):
    m = C.revolve(prof, nseg, scale_xz=(1.0, zscale))
    y, cz = head_rest_y(B, band_r, zscale, extra)
    if forward:
        m.v[:, 2] += forward * np.clip(m.v[:, 1] / max(m.v[:, 1].max(), 1e-6), 0, 1)
    place(m, y + lift, cz, tilt, tilt_z, dz)
    return m


def felt_hat(B, o):
    """Women's felt hat (WVS): shallow crown, ribbon band, narrow down-turned brim."""
    br = 0.094
    prof = [(0.0, 0.074), (0.055, 0.073), (0.082, 0.066), (0.092, 0.045), (0.095, 0.012), (br, 0.0),
            (0.125, -0.004), (0.142, -0.013), (0.14, -0.017), (0.122, -0.009), (0.093, -0.004),
            (0.089, -0.003), (0.088, 0.06), (0.0, 0.062)]
    m = revolve_hat(B, prof, 0.09, 1.12, o.get("extra", 0.014), tilt=o.get("tilt", 6), tilt_z=o.get("tilt_z", -5))
    k = m.attrs["prof_k"]
    band = (k >= 3) & (k <= 4)
    m.attrs = {"civ1": band.astype(float)}
    return m


def flat_cap(B, o):
    """Cloth flat cap: flat crown pulled forward over a short stiff peak."""
    prof = [(0.0, 0.05), (0.07, 0.049), (0.105, 0.043), (0.116, 0.03), (0.108, 0.012), (0.1, 0.0),
            (0.096, 0.0), (0.094, 0.04), (0.0, 0.042)]
    y, cz = head_rest_y(B, 0.096, 1.14, o.get("extra", 0.01))
    m = C.revolve(prof, 32, scale_xz=(1.0, 1.14))
    m.v[:, 2] += 0.028 * np.clip(m.v[:, 1] / 0.05, 0, 1) ** 1.5
    place(m, y, cz, o.get("tilt", 7))
    ang = np.linspace(-1.15, 1.15, 13) + np.pi / 2
    rin = np.stack([0.097 * np.cos(ang), np.zeros_like(ang), 0.097 * 1.14 * np.sin(ang)], 1)
    rout = np.stack([0.125 * np.cos(ang), -0.012 * np.ones_like(ang), 0.125 * 1.2 * np.sin(ang) + 0.012], 1)
    rout[:, 2] = np.maximum(rout[:, 2], rin[:, 2] + 0.01)
    V = np.concatenate([rin, rout, rin - np.array([0, 0.004, 0]), rout - np.array([0, 0.004, 0])], 0)
    n = len(ang)
    f = []
    for i in range(n - 1):
        f.append((i, i + 1, n + i + 1, n + i))
        f.append((2 * n + i, 3 * n + i, 3 * n + i + 1, 2 * n + i + 1))
        f.append((n + i, n + i + 1, 3 * n + i + 1, 3 * n + i))
    peak = G.Mesh(V, f)
    place(peak, y + 0.004, cz, o.get("tilt", 7))
    return m, peak


def chest_haversack(B, tun, o):
    """Gas-mask haversack worn on the chest (ARP / services), sling round the neck."""
    tt = C.torso_surface(tun, 0.22)
    tfull = G.Mesh(tun.v, tun.f)
    torso = np.abs(tun.v[:, 0]) < 0.24
    tsurf = G.Mesh(tun.v[torso], [])
    c = C.front_point(tsurf, 0.0, o.get("y", 1.16))
    bag = C.box_on_surface(tfull, c, (0.21, 0.18), 0.075, np.array([0, 0.08, 1.0]), nx=6, ny=5, round_=0.35)
    flap = C.box_on_surface(tfull, c + np.array([0, 0.065, 0.0]), (0.215, 0.06), 0.083, np.array([0, 0.1, 1.0]),
                            nx=6, ny=2, round_=0.2)
    top = c + np.array([0, 0.09, 0.03])
    ctrl = np.array([top + np.array([0.085, 0, 0]), C.front_point(tsurf, 0.085, 1.32),
                     C.front_point(tsurf, 0.08, 1.42), np.array([0.085, 1.49, -0.01]),
                     C.front_point(tsurf, 0.0, 1.47, -1),
                     np.array([-0.085, 1.49, -0.01]), C.front_point(tsurf, -0.08, 1.42),
                     C.front_point(tsurf, -0.085, 1.32), top + np.array([-0.085, 0, 0])])
    for i in (3, 5):
        ctrl[i] = C.surface_closest(tt, ctrl[i])
    path, nn = C.surface_path(ctrl, tt, 0.005, n=60)
    sling = C.ribbon(path, 0.03, 0.0025, normals=nn)
    return bag, flap, sling


def crossbody_box(B, tun, o):
    """Civilian gas-mask carton on a string, carried at the left hip, string over the right shoulder."""
    tv = tun.v
    tt = C.torso_surface(tun, 0.26)
    tfull = G.Mesh(tv, tun.f)
    torso = np.abs(tv[:, 0]) < 0.24
    tsurf = G.Mesh(tv[torso], [])
    yb = o.get("y", 0.93)
    sel = (tv[:, 0] > 0.08) & (np.abs(tv[:, 1] - yb) < 0.02) & (tv[:, 2] > -0.02)
    c = tv[sel][np.argmax(tv[sel][:, 0] * 0.6 + tv[sel][:, 2])]
    box = C.box_on_surface(tfull, c, (0.115, 0.14), 0.095, np.array([0.75, -0.05, 0.65]), nx=3, ny=3, round_=0.08)
    ctrl = np.array([c + np.array([-0.01, 0.075, 0.03]), C.front_point(tsurf, 0.06, 1.12), C.front_point(tsurf, -0.05, 1.3),
                     np.array([-0.125, 1.475, 0.0]), C.front_point(tsurf, -0.04, 1.3, -1), C.front_point(tsurf, 0.09, 1.1, -1),
                     c + np.array([-0.02, 0.075, -0.04])])
    ctrl[3] = C.surface_closest(tt, ctrl[3])
    path, nn = C.surface_path(ctrl, tt, 0.004, n=50)
    string = C.ribbon(path, 0.007, 0.0025, normals=nn)
    return box, string


def braces(B, sh, o):
    """Trouser braces visible in the open cardigan (on the shirt shell)."""
    out = []
    surf = G.Mesh(sh.v, sh.f)
    for sg in (1, -1):
        ctrl = np.array([C.front_point(surf, 0.075 * sg, 1.06), C.front_point(surf, 0.08 * sg, 1.2),
                         C.front_point(surf, 0.085 * sg, 1.34)])
        path, nn = C.surface_path(ctrl, surf, 0.003, n=14)
        out.append(C.ribbon(path, 0.022, 0.002, normals=nn))
    return out


def belt_axe(B, tun, o):
    """AFS leather belt with chrome buckle and a fireman's axe in a pouch on the right hip."""
    tv = tun.v
    torso = np.abs(tv[:, 0]) < 0.24
    by = o.get("belt_y", 0.98)
    belt = C.band_around(tun, by, 0.062, 0.004, 0.003, nseg=56, select=torso & (np.abs(tv[:, 1] - by) < 0.05))
    tsurf = G.Mesh(tv[torso], [])
    fp = C.front_point(tsurf, 0.0, by)
    buckle = C.flat_box(fp + np.array([0, 0, 0.008]), np.array([0, 0, 1.0]), 0.06, 0.055, 0.005)
    tfull = G.Mesh(tv, tun.f)
    sel = (tv[:, 0] < -0.1) & (np.abs(tv[:, 1] - (by - 0.07)) < 0.02)
    c = tv[sel][np.argmin(tv[sel][:, 0])]
    pouch = C.box_on_surface(tfull, c, (0.07, 0.12), 0.03, np.array([-1.0, -0.05, 0.1]), nx=3, ny=4, round_=0.3)
    # axe: handle hanging down through the pouch, head at the top (blade forward)
    out_n = nrm(np.array([-1.0, 0, 0.1]))
    base = c + out_n * 0.035
    hprof = [(0.0, 0.0), (0.012, 0.004), (0.014, 0.05), (0.013, 0.3), (0.016, 0.36), (0.0, 0.365)]
    handle = C.revolve([(r, -y) for r, y in hprof][::-1], 8, scale_xz=(0.8, 1.0))
    handle.v = handle.v + base + np.array([0, 0.11, 0])
    head = C.flat_box(base + np.array([0, 0.115, 0.03]), out_n, 0.11, 0.045, 0.014)
    spike = C.flat_box(base + np.array([0, 0.115, -0.05]), out_n, 0.06, 0.02, 0.012)
    return dict(belt=belt, buckle=buckle, axe_pouch=pouch, axe_handle=handle, axe_head=head, axe_spike=spike)


def baby_bundle(B, o):
    """Wrapped baby bundle (separate mesh, hidden by default) placed where the carry_box clip
    holds its hands (~0.3 m in front of the chest)."""
    prof = [(0.0, -0.23), (0.05, -0.215), (0.075, -0.17), (0.085, -0.05), (0.083, 0.08), (0.07, 0.17),
            (0.045, 0.215), (0.0, 0.225)]
    m = C.revolve(prof, 12, scale_xz=(1.0, 0.85))
    # lay it across the arms: long axis along X, slightly tilted (head end up, to the left)
    a = np.radians(-80)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    m.v = m.v @ Rz.T + np.array([0.0, o.get("y", 1.16), o.get("z", 0.30)])
    return m


# ----------------------------------------------------------------------------------
# assembly
# ----------------------------------------------------------------------------------


def make_parts(cid, cfg, B, R):
    o = cfg["outfit"]
    parts = []
    cover = np.zeros(len(B.v), bool)
    top = o["top"]
    tk = {"coat": K["coat"], "overall": K["overall"], "dress": K["dress"], "cardigan": K["cardigan"],
          "fire_tunic": K["fire_tunic"], "jacket": K["coat"]}[top["kind"]]
    tun, cv, tcfg = top_garment(B, R, top)
    cover |= cv
    parts.append(P_("cloth", "top", tun, tk, smooth=3))
    if tcfg.get("collar") == "open":
        cover |= C.vneck_region(B, R, tcfg, grow=0.025) & (R["neck"] < 0.5)
        sh = C.shirt_tie(B, R, dict(tcfg, tie=o.get("tie", False), shirt_collar=o.get("shirt_collar", True)))
        for item in sh:
            if isinstance(item, tuple):
                parts.append(P_("cloth", item[0], item[1], K["tie"]))
            else:
                parts.append(P_("cloth", "shirt", item, K["shirt"]))
                if o.get("braces"):
                    for i, b in enumerate(braces(B, item, o)):
                        parts.append(P_("gear", "brace%d" % i, b, K["strap"], smooth=4))
    # legs
    legs = o.get("legs", "trousers")
    if legs == "trousers":
        under_long = top.get("hem", 0.8) < 0.75
        tr, cv = C.trousers(B, R, dict(bottom_shin=o.get("trouser_bottom", 0.93), ease=o.get("trouser_ease", 0.013),
                                       top=0.9 if under_long else 1.0))
        cover |= cv
        parts.append(P_("cloth", "trousers", tr, K["trousers"]))
    elif legs == "shorts":
        tr, cv = shorts(B, R, o)
        cover |= cv
        parts.append(P_("cloth", "shorts", tr, K["trousers"]))
    # feet
    feet = o.get("feet", "shoes")
    fk = {"shoes": K["shoe"], "boots": K["boot"], "slippers": K["slipper"], "knee_boots": K["rubber_boot"],
          "lace_shoes": K["boot"]}[feet]
    fcfg = {"shoes": dict(top=0.078, ease=0.005, toe_extra=0.006),
            "lace_shoes": dict(top=0.10, ease=0.006, toe_extra=0.008),
            "boots": dict(top=0.165),
            "slippers": dict(top=0.072, ease=0.007, toe_extra=0.01),
            "knee_boots": dict(top=0.40, ease=0.011, toe_extra=0.01)}[feet]
    bo, cv = C.boots(B, R, fcfg)
    cover |= cv
    parts.append(P_("gear", "footwear", bo, fk, smooth=1))
    # over-garments and gear
    if "cape" in o:
        parts.append(P_("cloth", "cape", cape(B, R, o["cape"]), K["cape"], smooth=4))
    if "blanket" in o:
        parts.append(P_("cloth", "blanket", cape(B, R, o["blanket"]), K["blanket"], smooth=4))
    if o.get("gasmask_chest"):
        bag, flap, sling = chest_haversack(B, tun, o.get("gasmask_cfg", {}))
        parts += [P_("gear", "gasmask_bag", bag, K["canvas"], smooth=4),
                  P_("gear", "gasmask_flap", flap, K["canvas"], smooth=4),
                  P_("gear", "gasmask_sling", sling, K["canvas"], smooth=6)]
    if o.get("gasmask_box"):
        box, string = crossbody_box(B, tun, o.get("gasmask_cfg", {}))
        parts += [P_("gear", "gasmask_box", box, K["cardboard"], weights="hips"),
                  P_("gear", "gasmask_string", string, K["string"], smooth=6)]
    if o.get("belt_axe"):
        for k, m in belt_axe(B, tun, o).items():
            kind = {"belt": K["leather"], "buckle": K["chrome"], "axe_pouch": K["leather"], "axe_handle": K["wood"],
                    "axe_head": K["steel"], "axe_spike": K["steel"]}[k]
            parts.append(P_("gear", k, m, kind, weights="body" if k == "belt" else "hips", smooth=6))
    if o.get("belt"):
        tv = tun.v
        torso = np.abs(tv[:, 0]) < 0.24
        by = o.get("belt_y", 0.985)
        belt = C.band_around(tun, by, 0.05, 0.0035, 0.0025, nseg=56, select=torso & (np.abs(tv[:, 1] - by) < 0.05))
        parts.append(P_("gear", "belt", belt, K[o.get("belt_kind", "webbing")], smooth=6))
        fp = C.front_point(G.Mesh(tv[torso], []), 0.0, by)
        parts.append(P_("gear", "buckle", C.flat_box(fp + np.array([0, 0, 0.006]), np.array([0, 0, 1.0]), 0.045, 0.045, 0.004),
                        K["chrome"]))
    if o.get("armband"):
        a = C.J(B, "upperarm02.L")
        b = C.J(B, "lowerarm01.L")
        mask = (B.v[:, 0] > 0.15) & (R["arm"] > 0.5)
        arm = C.limb_wrap(B, mask, a, b, 0.30, 0.60, top.get("sleeve_ease", 0.012) + 0.009, nseg=20, nring=4)
        parts.append(P_("cloth", "armband", arm, K["armband"]))
    # head
    hs = cfg.get("hair_style", "short")
    if hs == "female":
        hair, dens = hair_female(B, cfg)
    elif hs == "bob":
        hair, dens = hair_bob(B, cfg)
    else:
        hair, dens = C.hair_cap(B, cfg.get("hair", {}))
    parts.append(P_("hair", "hair", hair, K["hair"], weights="head"))
    head = o.get("head")
    if head == "helmet":
        hcfg = dict(cfg.get("helmet_cfg", {}))
        if hs == "female":
            hcfg.setdefault("clear", 0.019)
        hel, liner, strap = C.brodie_helmet(B, hcfg)
        parts.append(P_("helmet", "helmet", hel, K["helmet"], weights="head"))
        parts.append(P_("helmet", "liner", liner, K["liner"], weights="head"))
        if strap is not None:
            parts.append(P_("gear", "chinstrap", strap, K["leather"], weights="head"))
    elif head == "headscarf":
        sc, ties, knot = headscarf(B, o.get("scarf_cfg", {}))
        parts += [P_("cloth", "headscarf", sc, K["scarf"], weights="head"),
                  P_("cloth", "scarf_ties", ties, K["scarf"], weights="head"),
                  P_("cloth", "scarf_knot", knot, K["scarf"], weights="head")]
    elif head == "felt_hat":
        parts.append(P_("cloth", "hat", felt_hat(B, o.get("hat_cfg", {})), K["felt_hat"], weights="head"))
    elif head == "flat_cap":
        cap, peak = flat_cap(B, o.get("hat_cfg", {}))
        parts += [P_("cloth", "flatcap", cap, K["flatcap"], weights="head"),
                  P_("cloth", "flatcap_peak", peak, K["flatcap"], weights="head")]
    if o.get("bundle"):
        parts.append(P_("cloth", "bundle", baby_bundle(B, o.get("bundle_cfg", {})), K["blanket"],
                        weights="bundle", detach=True))
    eyes = C.eyes_mesh(B)
    parts.append(P_("eyes", "eyes", eyes, K["eye"], weights="head"))
    keep = ~C.faces_all(B, cover)
    body = G.submesh(B.v, B.f, keep, B.W)
    body.loop_uv = [B.fuv[i] for i in np.where(keep)[0]]
    body.attrs["hand"] = R["hand"][body.src]
    body.attrs["dens"] = dens[body.src]
    parts.insert(0, P_("skin", "body", body, K["skin"], weights="exact"))
    return parts


# ----------------------------------------------------------------------------------
# painters
# ----------------------------------------------------------------------------------

DEFAULT_COLS = dict(coat=(70, 66, 62), overall=(36, 40, 54), dress=(92, 96, 104), cardigan=(110, 92, 70),
                    cape=(30, 34, 52), scarf=(150, 60, 50), blanket=(120, 90, 70), felt_hat=(70, 80, 66),
                    fire_tunic=(30, 32, 44), flatcap=(84, 78, 70), trousers=(60, 58, 58), shirt=(190, 186, 176),
                    tie=(70, 40, 40), armband=(30, 34, 50), hatband=(30, 30, 30))


def col(cfg, name):
    return srgb(cfg.get("cols", {}).get(name, DEFAULT_COLS.get(name, (100, 100, 100))))


def buttons(p, n, xs, ys, r=0.0085):
    """Mask/height of round buttons at the given (x, y) positions on the front."""
    front = sstep(0.1, 0.4, n[..., 2])
    m = np.zeros(p.shape[:-1])
    h = np.zeros(p.shape[:-1])
    for x in xs:
        for y in ys:
            d = np.hypot(p[..., 0] - x, p[..., 1] - y)
            m = np.maximum(m, sstep(r, r * 0.75, d) * front)
            h += 0.0018 * np.sqrt(np.clip(1 - (d / r) ** 2, 0, 1)) * front
    return m, h


def pocket_flap(p, n, cx, top, w, hgt):
    front = sstep(0.1, 0.4, n[..., 2])
    x, y = p[..., 0], p[..., 1]
    inx = np.abs(x - cx) < w / 2
    flp = inx & (y < top) & (y > top - hgt)
    edge = (sstep(0.003, 0.0, np.abs(y - (top - hgt))) * inx +
            sstep(0.003, 0.0, np.abs(np.abs(x - cx) - w / 2)) * (y < top) * (y > top - hgt)) * front
    return 0.0011 * flp * front - 0.0009 * edge, 0.5 * edge


def paint_cloth(M, cfg, sk, Lm):
    p = M["pos"]
    n = M["nrm"]
    kind = np.rint(M["kind"][..., 0]).astype(int)
    seed = cfg.get("seed", 1)
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    alb = np.zeros(p.shape)
    for kn in ("coat", "overall", "dress", "cardigan", "cape", "scarf", "blanket", "felt_hat", "fire_tunic",
               "flatcap", "trousers", "shirt", "tie", "armband"):
        m = kind == K[kn]
        if m.any():
            alb[m] = col(cfg, kn)
    fib = MAT.wool_fibres(p, seed)
    heather = fbm(p * 220.0, 3, seed=seed + 3)
    h = 0.00012 * fib
    rough = np.full(p.shape[:-1], 0.88)
    metal = np.zeros(p.shape[:-1])
    wool = np.isin(kind, [K["coat"], K["dress"], K["cape"], K["fire_tunic"], K["flatcap"], K["trousers"], K["blanket"]])
    alb *= (1 + (0.07 * fib + 0.06 * heather)[..., None] * wool[..., None])
    # flat cap / coat tweed fleck
    tweed = (kind == K["flatcap"]) | ((kind == K["coat"]) & cfg.get("tweed", False))
    if tweed.any():
        fl = sstep(0.55, 0.8, gnoise(p * 900, seed + 9)) - sstep(0.6, 0.85, gnoise(p * 900, seed + 10))
        alb *= (1 + 0.18 * fl * tweed)[..., None]
        h += 0.0002 * fl * tweed
    # cotton drill (overalls): diagonal twill
    ov = kind == K["overall"]
    if ov.any():
        tw = np.sin((x * 0.7 + y * 1.0 + z * 0.5) * 2 * np.pi / 0.0018)
        alb[ov] *= (1 + 0.05 * tw[ov] + 0.06 * heather[ov])[..., None]
        h += np.where(ov, 0.00008 * tw, 0)
        rough = np.where(ov, 0.8, rough)
    # knitted cardigan: vertical ribs + stitch noise
    cd = kind == K["cardigan"]
    if cd.any():
        ang = np.arctan2(x, z)
        rib = np.sin(x * 2 * np.pi / 0.004 + 0.3 * gnoise(p * 60, seed + 4))
        st = gnoise(p * np.array([900, 2600, 900]), seed + 5)
        alb[cd] *= (1 + 0.08 * rib[cd] + 0.07 * st[cd] + 0.05 * heather[cd])[..., None]
        h += np.where(cd, 0.0003 * rib + 0.00015 * st, 0)
        rough = np.where(cd, 0.95, rough)
    # felt hat: very fine, slightly darker band
    fh = kind == K["felt_hat"]
    if fh.any():
        alb[fh] *= (1 + 0.04 * gnoise(p * 1500, seed + 6)[fh])[..., None]
        band = (M["civ1"][..., 0] > 0.5) & fh
        alb[band] = srgb(cfg.get("cols", {}).get("hatband", (30, 30, 30))) * (1 + 0.05 * gnoise(p * 1200, 3)[band])[..., None]
        h += np.where(fh, 0.00006 * gnoise(p * 3000, seed + 7), 0)
        rough = np.where(fh, 0.82, rough)
    # shirt: woven, optional thin stripes
    shm = kind == K["shirt"]
    if shm.any():
        alb[shm] *= (1 + 0.03 * gnoise(p * 2500, seed + 12)[shm])[..., None]
        if cfg.get("shirt_stripes"):
            sc = srgb(cfg["shirt_stripes"])
            stp = sstep(0.25, 0.1, np.abs(np.mod(x / 0.008, 1.0) - 0.5) - 0.25)
            alb[shm] = T.lerp(alb[shm], sc, (stp[shm] * 0.8)[..., None] if False else stp[shm] * 0.8)
        rough = np.where(shm, 0.8, rough)
    # headscarf print
    sf = kind == K["scarf"]
    if sf.any():
        pat = cfg.get("scarf_pattern", "check")
        c2 = srgb(cfg.get("scarf_col2", (220, 210, 190)))
        if pat == "check":
            gx = sstep(0.12, 0.05, np.abs(np.mod(x / 0.03, 1.0) - 0.5) - 0.3)
            gy = sstep(0.12, 0.05, np.abs(np.mod((y + z * 0.3) / 0.03, 1.0) - 0.5) - 0.3)
            pm = np.clip(gx + gy, 0, 1) * 0.75
        else:  # small floral / polka print
            from cw_tex import worley
            d1, _ = worley(p * 70.0, seed=seed + 13)
            pm = sstep(0.28, 0.2, d1)
        alb[sf] = T.lerp(alb[sf], c2, pm[sf])
        h += np.where(sf, 0.00008 * gnoise(p * 2500, seed + 14), 0)
        rough = np.where(sf, 0.7, rough)
    # blanket: plaid + fuzz
    bl = kind == K["blanket"]
    if bl.any():
        c2 = srgb(cfg.get("blanket_col2", (60, 50, 44)))
        c3 = srgb(cfg.get("blanket_col3", (170, 150, 110)))
        sx = np.abs(np.mod(x / 0.09, 1.0) - 0.5)
        sy = np.abs(np.mod((y + 0.3 * z) / 0.09, 1.0) - 0.5)
        band = 0.5 * (sstep(0.36, 0.3, sx) + sstep(0.36, 0.3, sy))
        thin = np.maximum(sstep(0.03, 0.015, np.abs(sx - 0.15)), sstep(0.03, 0.015, np.abs(sy - 0.15)))
        b = T.lerp(alb, c2, band * 0.8)
        b = T.lerp(b, c3, thin * 0.8)
        fuzz = gnoise(p * 1800, seed + 15)
        alb[bl] = (b * (1 + 0.1 * fuzz[..., None]))[bl]
        h += np.where(bl, 0.0003 * fuzz, 0)
        rough = np.where(bl, 0.96, rough)
    # garment construction details -------------------------------------------------
    o = cfg["outfit"]
    top = o["top"]
    topk = {"coat": K["coat"], "overall": K["overall"], "dress": K["dress"], "cardigan": K["cardigan"],
            "fire_tunic": K["fire_tunic"], "jacket": K["coat"]}[top["kind"]]
    tm = kind == topk
    front = sstep(0.1, 0.4, n[..., 2])
    dark = np.zeros(p.shape[:-1])
    bmask = np.zeros(p.shape[:-1])
    hh = np.zeros(p.shape[:-1])
    # front opening (double-breasted: overlap edge to the wearer's left)
    db = top.get("double", False)
    xo = 0.055 if db else 0.004
    vb = top.get("v_bottom", 1.36) if top.get("collar", "open") == "open" else 1.53
    ln = MAT.gauss(np.abs(x - xo) / 0.0012, 1) * front * (y < vb + 0.01) * (y > top.get("hem", 0.8))
    hh -= 0.0006 * ln
    dark += 0.6 * ln
    nb = top.get("buttons", 4)
    if nb:
        ys = np.linspace(min(vb - 0.02, 1.48), max(top.get("hem", 0.8) + 0.12, 0.98 - 0.0 * nb), nb)
        if top.get("hem", 0.8) < 0.7:
            ys = np.linspace(vb - 0.03, 0.80, nb)
        xs = [0.0, 0.1] if db else [0.0]
        if db:
            xs = [-0.045, 0.085]
        bm, bh = buttons(p, n, xs, ys, top.get("button_r", 0.0095))
        bmask = np.maximum(bmask, bm)
        hh += bh
    # pockets
    if top["kind"] in ("coat", "jacket", "fire_tunic"):
        for sg in (1, -1):
            dh, dd = pocket_flap(p, n, 0.13 * sg, 0.93 if top["kind"] != "fire_tunic" else 0.96, 0.17, 0.055)
            hh += dh
            dark += dd
    if top["kind"] in ("overall", "fire_tunic") or top.get("breast_pockets"):
        for sg in (1, -1):
            dh, dd = pocket_flap(p, n, 0.095 * sg, 1.39, 0.12, 0.045)
            hh += dh
            dark += dd
    if top["kind"] == "cardigan":
        band = sstep(0.012, 0.006, np.abs(np.abs(x) - 0.008)) * front * (y > top.get("hem", 0.9))
        hh += 0.0006 * band
    if top["kind"] == "dress" and top.get("suit_hem"):  # jacket hem line of a costume (suit)
        sl = MAT.gauss((y - top["suit_hem"]) / 0.002, 1)
        hh -= 0.0008 * sl
        dark += 0.5 * sl
        for sg in (1, -1):
            dh, dd = pocket_flap(p, n, 0.11 * sg, top["suit_hem"] + 0.12, 0.13, 0.045)
            hh += dh
            dark += dd
    if top.get("apron"):
        ap = (np.abs(x) < 0.16 + 0.12 * np.clip((0.98 - y) / 0.5, 0, 1)) & (y < 0.99) & (y > top.get("hem", 0.4) + 0.06)
        bib = (np.abs(x) < 0.09) & (y >= 0.99) & (y < 1.30)
        apm = (ap | bib) & tm & (n[..., 2] > -0.1)
        alb[apm] = srgb((226, 224, 216)) * (1 + 0.03 * gnoise(p * 2000, 17)[apm])[..., None]
        rough = np.where(apm, 0.8, rough)
        edge = apm & ~((np.abs(x) < 0.155 + 0.12 * np.clip((0.98 - y) / 0.5, 0, 1)) & ~bib | (np.abs(x) < 0.083) & bib)
        dark += 0.25 * edge
    h += hh * (tm | (kind == K["cape"]))
    alb *= (1 - 0.25 * np.clip(dark, -0.5, 1) * tm)[..., None]
    bcol = srgb(top.get("button_col", (40, 34, 30)))
    alb = T.lerp(alb, bcol, bmask * tm)
    if top.get("button_metal"):
        metal = np.maximum(metal, bmask * tm)
        rough = np.where((bmask > 0.5) & tm, 0.3, rough)
    else:
        rough = np.where((bmask > 0.5) & tm, 0.45, rough)
    # cape: scarlet border along the hem / collar
    cpm = kind == K["cape"]
    if cpm.any() and "trim" in cfg.get("cols", {}):
        tr = (M["civ1"][..., 0] < 0.03) | (M["civ1"][..., 0] > (o["cape"].get("top", 1.4) - o["cape"].get("hem", 1.18)) + 0.06)
        alb[cpm & tr] = srgb(cfg["cols"]["trim"]) * (1 + 0.06 * fib[cpm & tr])[..., None]
    # trousers seams + knee folds, elbow folds on tops
    trm = kind == K["trousers"]
    for s, sg in (("L", 1), ("R", -1)):
        hp = np.asarray(sk["upperleg02." + s]["head"])
        seam = MAT.gauss(np.abs(x - (hp[0] + 0.07 * sg)), 0.002) * ((x * sg) > 0)
        h -= 0.00025 * seam * trm
        el = np.asarray(sk["lowerarm01." + s]["head"])
        ax = np.asarray(sk["lowerarm01." + s]["tail"]) - np.asarray(sk["upperarm02." + s]["head"])
        wr = np.asarray(sk["wrist." + s]["head"])
        h += MAT.fold_field(p, n, el, ax, 0.02, 0.05, 0.0016, seed + 11, inner=-(wr - el)) * (tm | cd)
        kn = np.asarray(sk["lowerleg01." + s]["head"])
        axl = np.asarray(sk["foot." + s]["head"]) - np.asarray(sk["upperleg02." + s]["head"])
        h += MAT.fold_field(p, n, kn, axl, 0.024, 0.06, 0.0018, seed + 12, inner=np.array([0, 0, -1.0])) * trm
    # armband with letters
    am = kind == K["armband"]
    if am.any():
        alb[am] = col(cfg, "armband") * (1 + 0.04 * fib[am])[..., None]
        txt = cfg.get("armband_text")
        if txt:
            a = np.asarray(sk["upperarm02.L"]["head"])
            b = np.asarray(sk["lowerarm01.L"]["head"])
            axv = (b - a) / np.linalg.norm(b - a)
            lat = np.array([1.0, 0, 0]) - axv[0] * axv
            lat /= np.linalg.norm(lat)
            fwd = np.cross(axv, lat)
            d = p - a
            t = d @ axv
            tc = 0.45 * np.linalg.norm(b - a)
            q = d - t[..., None] * axv
            angl = np.arctan2(q @ fwd, q @ lat)
            u = -angl / 0.22
            v = -(t - tc) / 0.016
            tm_ = text_mask(u, v, txt, 0.22) * (np.abs(angl) < 1.3)
            alb = np.where((am & (tm_ > 0.5))[..., None], srgb(cfg.get("armband_text_col", (200, 170, 60))), alb)
    # dust (plaster / brick) and soot
    dust = MAT.mud_field(p, n, cfg.get("mud", 0.15), seed + 20, wet=0.0)
    dcol = srgb(cfg.get("mud_col", (150, 144, 134)))
    alb = T.lerp(alb, dcol, dust)
    rough = rough + 0.05 * dust
    h += 0.0003 * dust * fbm(p * 300, 2, seed=seed + 22)
    # general wear: slightly lighter at elbows/knees/shoulders
    fade = fbm(p * 6.0, 3, seed=seed + 7)
    alb *= (1 + 0.05 * fade[..., None])
    return dict(albedo=np.clip(alb, 0, 1), height=h, rough=np.clip(rough, 0.25, 0.97), metal=metal)


def paint_gear(M, cfg, sk):
    cfg = dict(cfg, boot_col=cfg.get("boot_col", cfg.get("shoe_col", (40, 30, 24))))
    res = MAT.paint_gear(M, cfg, sk)
    p = M["pos"]
    n = M["nrm"]
    kind = np.rint(M["kind"][..., 0]).astype(int)
    alb, h, rough, metal = res["albedo"], res["height"], res["rough"], res["metal"]
    seed = cfg.get("seed", 1) + 500
    g = fbm(p * 80, 3, seed=seed)
    crease = fbm(p * np.array([300, 120, 300]), 3, seed=seed + 5)
    for kn, c_, r_ in (("shoe", cfg.get("shoe_col", (34, 26, 22)), 0.32), ("slipper", cfg.get("slipper_col", (96, 70, 52)), 0.9),
                       ("rubber_boot", (24, 24, 26), 0.42)):
        m = kind == K[kn]
        if m.any():
            alb[m] = srgb(c_) * (1 + 0.1 * g[m] - 0.08 * np.abs(crease[m]))[..., None]
            rough[m] = r_ + 0.1 * np.clip(crease[m], 0, 1)
            sole = sstep(0.02, 0.01, p[..., 1])
            alb[m] = T.lerp(alb[m], srgb((30, 24, 20)), sole[m])
            h = np.where(m, 0.0003 * crease if kn != "slipper" else 0.0003 * gnoise(p * 1500, seed + 1), h)
            metal[m] = 0
    wd = kind == K["wood"]
    if wd.any():
        grain = np.sin(p[..., 1] * 600 + 4 * gnoise(p * np.array([60, 6, 60]), seed + 2))
        alb[wd] = srgb((150, 110, 66)) * (1 + 0.12 * grain[wd])[..., None]
        rough[wd] = 0.55
    cb_ = kind == K["cardboard"]
    if cb_.any():
        alb[cb_] = srgb((150, 124, 90)) * (1 + 0.08 * g[cb_] + 0.04 * gnoise(p * 1200, seed + 3)[cb_])[..., None]
        rough[cb_] = 0.9
        metal[cb_] = 0
    st = kind == K["string"]
    if st.any():
        alb[st] = srgb((176, 164, 136))
        rough[st] = 0.9
    ch = kind == K["chrome"]
    if ch.any():
        alb[ch] = srgb((190, 190, 186))
        metal[ch] = 1.0
        rough[ch] = 0.28
    br = kind == K["strap"]
    if br.any():
        alb[br] = srgb(cfg.get("braces_col", (60, 52, 46))) * (1 + 0.05 * g[br])[..., None]
        rough[br] = 0.8
    return res


def paint_helmet(M, cfg):
    res = MAT.paint_helmet(M, cfg)
    txt = cfg.get("helmet_letter")
    if not txt:
        return res
    p = M["pos"]
    n = M["nrm"]
    outer = M["outer"][..., 0] > 0.5
    prof = M["prof_k"][..., 0]
    bowl = outer & (prof < 0.55) & (n[..., 2] > 0.35) & M["mask"]
    if not bowl.any():
        return res
    mid = bowl & (np.abs(p[..., 0]) < 0.012) & (n[..., 2] > 0.5)
    if not mid.any():
        mid = bowl
    ylo, yhi = np.percentile(p[..., 1][mid], 3), np.percentile(p[..., 1][mid], 97)
    yc = ylo + cfg.get("letter_at", 0.42) * (yhi - ylo)
    sz = cfg.get("letter_size", 0.024)
    u = p[..., 0] / sz
    v = (p[..., 1] - yc) / sz
    lm = text_mask(u, v, txt, 0.24, 2.4) * outer * (n[..., 2] > 0.2)
    wcol = srgb((228, 226, 218)) * (1 + 0.05 * gnoise(p * 1500, 3))[..., None]
    res["albedo"] = T.lerp(res["albedo"], wcol, lm * 0.95)
    res["rough"] = np.where(lm > 0.5, 0.55, res["rough"])
    res["height"] = res["height"] + 0.00008 * lm
    return res


def legwear(res, M, cfg, sk):
    """Stockings / knee socks painted onto the visible legs of the skin atlas."""
    lw = cfg.get("legwear")
    if not lw:
        return
    p = M["pos"]
    kind_hand = M["hand"][..., 0] if "hand" in M else np.zeros(p.shape[:-1])
    y = p[..., 1]
    knee = np.asarray(sk["lowerleg01.L"]["head"])[1]
    leg = (y < knee + 0.15) & (np.abs(p[..., 0]) > 0.0) & (y < 0.75)
    c = srgb(lw["col"])
    if lw["kind"] == "stockings":
        a = lw.get("opacity", 0.75)
        seam = MAT.gauss(np.abs(np.abs(p[..., 0]) - np.abs(np.asarray(sk["foot.L"]["head"])[0])) / 0.0015, 1) * (p[..., 2] < np.asarray(sk["foot.L"]["head"])[2] - 0.0) * 0
        res["albedo"] = np.where(leg[..., None], T.lerp(res["albedo"], c, a), res["albedo"])
        res["rough"] = np.where(leg, 0.55, res["rough"])
    else:  # knee socks: wool, turned-down top band
        top = knee - lw.get("below", 0.05)
        sock = y < top
        rib = np.sin(np.arctan2(p[..., 0] - np.sign(p[..., 0]) * 0.1, p[..., 2]) * 60)
        knit = gnoise(p * 1500, 7)
        sc = c * (1 + 0.08 * rib + 0.06 * knit)[..., None]
        band = sock & (y > top - 0.045)
        sc = np.where(band[..., None], sc * 0.85, sc)
        res["albedo"] = np.where(sock[..., None], sc, res["albedo"])
        res["height"] = np.where(sock, 0.0003 * rib + 0.0006 * band, res["height"])
        res["rough"] = np.where(sock, 0.95, res["rough"])
