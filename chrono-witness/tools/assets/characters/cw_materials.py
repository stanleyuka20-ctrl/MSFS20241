"""Procedural material painters (own work).  Each painter receives the rasterized texel
maps of a material atlas (rest-pose position 'pos', normal 'nrm', 'kind' code and other
attributes) and returns linear albedo (N,N,3), height in metres (N,N), roughness, metalness
and an optional extra AO factor.  Everything is evaluated in 3D so islands/seams match."""
import numpy as np

import cw_tex as T
from cw_tex import fbm, gnoise, worley, sstep, srgb

# kind codes ------------------------------------------------------------------------
K = dict(skin=0, tunic=1, trousers=2, puttee=3, collar=4, shirt=5, tie=6, armband=7, jacket=8,
         modern_trousers=9, webbing=10, brass=11, boot=12, leather=13, felt=14, steel=15, canvas=16,
         strap=17, bandage=18, rubber=19, gaiter=20, cap_cloth=21, cap_peak=22, helmet=30, liner=31,
         hair=40, eye=50, device=60, sleeve=61)


def gauss(d, s):
    return np.exp(-(d / s) ** 2)


def dist(p, c, scale=None):
    d = p - np.asarray(c)
    if scale is not None:
        d = d * np.asarray(scale)
    return np.linalg.norm(d, axis=-1)


# ----------------------------------------------------------------------------------
# skin
# ----------------------------------------------------------------------------------


def paint_skin(M, Lm, cfg, sk):
    p = M["pos"]
    n = M["nrm"]
    mask = M["mask"]
    hand = M["hand"][..., 0]
    dens = M["dens"][..., 0]
    seed = cfg.get("seed", 1)
    base_light = srgb(cfg.get("skin", (224, 178, 150)))
    shadow_col = srgb(cfg.get("skin_dark", (178, 120, 95)))
    red_col = srgb(cfg.get("skin_red", (205, 110, 95)))
    hair_col = srgb(cfg.get("hair_col", (60, 42, 28)))
    lip_col = srgb(cfg.get("lip", (170, 95, 85)))
    # low-frequency mottling (melanin) + blotches (hemoglobin)
    mott = fbm(p * 18.0, 4, seed=seed)
    blot = fbm(p * 45.0 + 3.1, 3, seed=seed + 5)
    alb = base_light * (1 + 0.08 * mott[..., None])
    alb = T.lerp(alb, shadow_col, np.clip(0.12 + 0.12 * fbm(p * 7.0, 3, seed=seed + 2), 0, 1))
    # redness map
    red = 0.10 + 0.10 * np.clip(blot, 0, 1)
    for s in "LR":
        e = Lm["eye." + s]
        cheek = e + np.array([0.012 if s == "L" else -0.012, -0.036, 0.0])
        red += cfg.get("cheek_red", 0.45) * gauss(dist(p, cheek, (1, 1.2, 1.5)), 0.026)
        red += 0.5 * gauss(dist(p, Lm["ear." + s], (1.0, 0.7, 1.0)), 0.03)
        # under-eye: slightly darker / violet
        ue = e + np.array([0, -0.017, 0.006])
        alb *= 1 - 0.10 * gauss(dist(p, ue, (0.9, 1.8, 1)), 0.014)[..., None]
    red += 0.55 * gauss(dist(p, Lm["nose"] + np.array([0, 0.002, -0.006]), (1, 1, 1)), 0.016)
    red += 0.25 * gauss(dist(p, Lm["chin"] + np.array([0, 0.004, 0.012]), (1, 1, 1)), 0.02)
    # hands: knuckles, finger tips redder
    red += hand * (0.18 + 0.15 * np.clip(fbm(p * 60, 2, seed=seed + 9), 0, 1))
    for f in (1, 2, 3, 4):
        for side in "LR":
            tip = sk["finger%d-3.%s" % (f, side)]["tail"]
            red += 0.35 * gauss(dist(p, tip), 0.012) * hand
            for k in (1, 2):
                kn = sk["finger%d-%d.%s" % (f, k, side)]["tail"]
                red += 0.25 * gauss(dist(p, kn), 0.008) * hand
    alb = T.lerp(alb, red_col, np.clip(red * cfg.get("redness", 1.0) * 0.35, 0, 0.6))
    # lips
    mo = Lm["mouth"]
    mw = abs(Lm["mouth_c.L"][0] - mo[0]) + 0.002
    lx = (p[..., 0] - mo[0]) / mw
    ly = (p[..., 1] - mo[1])
    lip_h = 0.0065 * np.sqrt(np.clip(1 - lx ** 2, 0, 1)) + 0.0015
    lipm = sstep(1.0, 0.6, np.abs(ly) / np.maximum(lip_h, 1e-4)) * sstep(1.05, 0.85, np.abs(lx)) * \
        (p[..., 2] > mo[2] - 0.02) * (n[..., 2] > 0.1)
    alb = T.lerp(alb, lip_col, lipm * 0.85)
    # stubble / beard shadow
    stub = beard_mask(p, n, Lm) * cfg.get("stubble", 0.5)
    f1, f2 = worley(p * 2200.0, seed=seed + 3)
    dots = sstep(0.35, 0.15, f1)
    stub_col = hair_col * 0.45 + srgb((60, 64, 70)) * 0.35
    alb = T.lerp(alb, stub_col, np.clip(stub * (0.3 + 0.6 * dots), 0, 0.8))
    # eyebrows
    brow = brow_mask(p, n, Lm, cfg)
    brow_col = srgb(cfg["brow_col"]) if "brow_col" in cfg else hair_col * 0.75
    alb = T.lerp(alb, brow_col, np.clip(brow * 1.15, 0, 0.95))
    # scalp under the hair cap / hairline fade
    hl = np.clip(dens * 1.3, 0, 1)
    strands = 0.5 + 0.5 * gnoise(p * np.array([900.0, 300.0, 900.0]), seed + 11)
    alb = T.lerp(alb, hair_col * (0.8 + 0.3 * strands[..., None]), hl * 0.9)
    # freckles / moles
    if cfg.get("freckles", 0) > 0:
        fr1, _ = worley(p * 350.0, seed=seed + 21)
        fr = sstep(0.25, 0.1, fr1) * gauss(dist(p, Lm["nose"] + np.array([0, 0.02, -0.03]), (1, 1.4, 1)), 0.06)
        alb *= 1 - 0.25 * cfg["freckles"] * fr[..., None]
    m1, _ = worley(p * 60.0, seed=seed + 31)
    alb *= 1 - 0.45 * sstep(0.06, 0.03, m1)[..., None]
    # nails
    nails = np.zeros(p.shape[:-1])
    for side in "LR":
        wr = sk["wrist." + side]["head"]
        for f in (1, 2, 3, 4):
            b = sk["finger%d-3.%s" % (f, side)]
            tip = np.asarray(b["tail"])
            hd = np.asarray(b["head"])
            ax = (tip - hd) / np.linalg.norm(tip - hd)
            back = nail_dir(sk, side, f)
            d = dist(p, tip - ax * 0.007 + back * 0.004)
            facing = (n * back).sum(-1)
            nails = np.maximum(nails, sstep(0.0085, 0.006, d) * sstep(0.2, 0.5, facing))
    nail_col = srgb((215, 175, 160))
    alb = T.lerp(alb, nail_col, nails * 0.8)
    # grime / mud
    mud = cfg.get("face_mud", 0.0)
    if mud > 0:
        mn = fbm(p * 30.0, 4, seed=seed + 41)
        g = np.clip((mn + 0.2) * 1.5, 0, 1) * mud * (0.5 + 0.8 * hand + 0.5 * (p[..., 1] < Lm["mouth"][1]))
        alb = T.lerp(alb, srgb((88, 72, 55)), np.clip(g, 0, 0.6))
    # height: pores + fine wrinkles
    pf1, _ = worley(p * 1400.0, seed=seed + 51)
    face = (hand < 0.3)
    porescale = 0.00009 * (1 + 1.5 * gauss(dist(p, Lm["nose"]), 0.04))
    h = -porescale * sstep(0.25, 0.0, pf1)
    h += 0.00003 * gnoise(p * 3000.0, seed + 52)
    age = cfg.get("age", 25)
    wr_amt = np.clip((age - 18) / 30, 0.05, 1.0)
    # forehead lines
    fh = sstep(Lm["eye.L"][1] + 0.03, Lm["eye.L"][1] + 0.045, p[..., 1]) * sstep(Lm["eye.L"][1] + 0.085, Lm["eye.L"][1] + 0.065, p[..., 1])
    fh *= (n[..., 2] > 0.4) * (np.abs(p[..., 0]) < 0.05)
    h += -0.00012 * wr_amt * fh * np.clip(np.sin(p[..., 1] * 2 * np.pi / 0.0075 + 3 * gnoise(p * 40, seed + 53)), 0, 1) ** 4
    # crow's feet
    for s, sg in (("L", 1), ("R", -1)):
        c = Lm["eye." + s] + np.array([0.026 * sg, 0, -0.012])
        d = dist(p, c)
        angl = np.arctan2(p[..., 1] - c[1], np.abs(p[..., 0] - c[0]) + 1e-6)
        h += -0.0001 * wr_amt * gauss(d, 0.012) * np.clip(np.sin(angl * 14 + 2 * gnoise(p * 80, seed + 54)), 0, 1) ** 6
    # knuckle creases
    for side in "LR":
        for f in (1, 2, 3, 4):
            for k in (1, 2):
                b = sk["finger%d-%d.%s" % (f, k, side)]
                tl = np.asarray(b["tail"])
                ax = tl - np.asarray(b["head"])
                ax /= np.linalg.norm(ax)
                along = ((p - tl) * ax).sum(-1)
                rad = dist(p, tl)
                h += -0.00012 * hand * gauss(rad, 0.012) * np.clip(np.sin(along * 2 * np.pi / 0.0025), 0, 1) ** 3
    h += 0.0002 * nails
    rough = 0.55 + 0.06 * fbm(p * 50, 2, seed=seed + 60)
    tz = gauss(dist(p, Lm["nose"] + np.array([0, 0.02, -0.01]), (2.0, 0.7, 1)), 0.05)
    rough -= 0.12 * tz
    rough -= 0.15 * lipm
    rough += 0.05 * hand
    rough = np.where(nails > 0.5, 0.3, rough)
    rough += 0.1 * hl
    return dict(albedo=alb, height=h, rough=np.clip(rough, 0.2, 0.95), metal=np.zeros_like(rough))


def nail_dir(sk, side, f):
    """Back-of-hand direction for finger f."""
    w = np.asarray(sk["wrist." + side]["head"])
    i = np.asarray(sk["finger2-1." + side]["head"])
    r = np.asarray(sk["finger4-1." + side]["head"])
    hd = (i + r) / 2 - w
    ac = i - r
    nrm = np.cross(hd, ac) * (1 if side == "L" else -1)
    nrm /= np.linalg.norm(nrm)
    # MakeHuman rest: the palm faces down/back -> back of hand is the opposite of the palm
    # determined by the bend of the fingers (tips curl towards the palm)
    tip = np.asarray(sk["finger3-3." + side]["tail"])
    mid = np.asarray(sk["finger3-1." + side]["head"])
    bend = tip - mid - np.dot(tip - mid, hd / np.linalg.norm(hd)) * hd / np.linalg.norm(hd)
    if np.dot(bend, nrm) > 0:
        nrm = -nrm
    return nrm


def beard_mask(p, n, Lm):
    mo = Lm["mouth"]
    y = p[..., 1]
    z = p[..., 2]
    ax = np.abs(p[..., 0])
    earz = Lm["ear.L"][2]
    # region below the cheekbones, in front of the ears, above the neck middle
    top = Lm["nose"][1] - 0.012 + 0.025 * sstep(0.02, 0.06, ax)
    m = sstep(top, top - 0.012, y)
    m *= sstep(earz + 0.005, earz + 0.025, z)
    m *= sstep(Lm["chin"][1] - 0.06, Lm["chin"][1] - 0.03, y)
    # upper lip moustache area
    lip_clear = gauss(np.abs(y - mo[1]) / 0.006, 1.0) * (ax < 0.03)
    m *= 1 - 0.85 * lip_clear
    return np.clip(m, 0, 1)


def brow_mask(p, n, Lm, cfg):
    out = np.zeros(p.shape[:-1])
    thick = cfg.get("brow_thick", 1.0)
    for s, sg in (("L", 1), ("R", -1)):
        e = Lm["eye." + s]
        x = (p[..., 0] - e[0]) * sg  # outward positive
        u = (x + 0.018) / 0.042  # 0 inner .. 1 outer
        arc = e[1] + 0.017 + 0.006 * np.sin(np.clip(u, 0, 1) * np.pi * 0.9) - 0.004 * u
        hw = (0.0055 - 0.003 * np.clip(u, 0, 1)) * thick
        d = np.abs(p[..., 1] - arc)
        band = sstep(hw, hw * 0.4, d) * sstep(-0.05, 0.05, u) * sstep(1.05, 0.85, u)
        band *= (p[..., 2] > e[2] - 0.02) * (n[..., 2] > 0.05)
        hairs = 0.5 + 0.5 * gnoise(np.stack([p[..., 0] * 400 * sg - p[..., 1] * 900, p[..., 1] * 2500, p[..., 2] * 900], -1), 77)
        out = np.maximum(out, band * (0.55 + 0.45 * hairs))
    return out


# ----------------------------------------------------------------------------------
# wool cloth (tunic, trousers, puttees, collar, armband, shirt...)
# ----------------------------------------------------------------------------------


def wool_fibres(p, seed, scale=1.0):
    a = gnoise(p * np.array([1400, 500, 1400]) * scale, seed)
    b = gnoise(p * np.array([500, 1400, 500]) * scale, seed + 1)
    c = gnoise(p * 4200 * scale, seed + 2)
    return 0.45 * a + 0.45 * b + 0.3 * c


def fold_field(p, n, center, axis, wavelength, radius, amp, seed, inner=None):
    """Concentric folds around a joint: ridges perpendicular to the limb axis."""
    axis = np.asarray(axis, float)
    axis /= np.linalg.norm(axis)
    d = p - np.asarray(center)
    along = (d * axis).sum(-1)
    radial = np.linalg.norm(d - along[..., None] * axis, axis=-1)
    fall = gauss(along / radius, 1.0) * sstep(0.09, 0.03, radial)
    warp = 0.6 * gnoise(p * 25.0, seed) + 0.3 * gnoise(p * 60, seed + 1)
    wave = np.sin(along * 2 * np.pi / wavelength + warp * 3.0)
    sharp = np.sign(wave) * np.abs(wave) ** 0.6
    if inner is not None:
        fall = fall * (0.35 + 0.65 * np.clip((n * np.asarray(inner)).sum(-1) + 0.3, 0, 1))
    return amp * sharp * fall


def paint_cloth(M, cfg, sk, Lm):
    p = M["pos"]
    n = M["nrm"]
    kind = np.rint(M["kind"][..., 0]).astype(int)
    seed = cfg.get("seed", 1)
    N = p.shape[0]
    khaki = srgb(cfg.get("khaki", (112, 97, 64)))
    alb = np.broadcast_to(khaki, p.shape).copy()
    fib = wool_fibres(p, seed)
    heather = fbm(p * 220.0, 3, seed=seed + 3)
    alb *= (1 + 0.07 * fib[..., None] + 0.05 * heather[..., None])
    h = 0.00012 * fib
    rough = np.full(p.shape[:-1], 0.88)
    metal = np.zeros(p.shape[:-1])
    # per-kind base colours
    tro = srgb(cfg.get("khaki_trousers", cfg.get("khaki", (112, 97, 64))))
    put = srgb(cfg.get("khaki_puttee", (104, 92, 62)))
    alb[kind == K["trousers"]] *= (tro / khaki)
    alb[kind == K["modern_trousers"]] *= (tro / khaki)
    alb[kind == K["puttee"]] *= (put / khaki)
    if "shirt_col" in cfg:
        alb[kind == K["shirt"]] = srgb(cfg["shirt_col"]) * (1 + 0.05 * fib[kind == K["shirt"]][..., None])
    if "tie_col" in cfg:
        alb[kind == K["tie"]] = srgb(cfg["tie_col"]) * (1 + 0.04 * fib[kind == K["tie"]][..., None])
    # long-wave fading + wear at edges / elbows / knees
    fade = fbm(p * 6.0, 3, seed=seed + 7)
    alb *= (1 + 0.05 * fade[..., None])
    for s, sg in (("L", 1), ("R", -1)):
        for jn, r, a in (("lowerarm01." + s, 0.05, 0.10), ("lowerleg01." + s, 0.06, 0.08)):
            c = np.asarray(sk[jn]["head"])
            alb *= (1 + a * gauss(dist(p, c), r))[..., None]
    # tunic details ---------------------------------------------------------------
    tun = (kind == K["tunic"]) | (kind == K["collar"]) | (kind == K["jacket"])
    det_h, det_dark, brass = tunic_details(p, n, cfg, sk, Lm)
    h = h + det_h * tun
    alb *= (1 - 0.25 * det_dark * tun)[..., None]
    if cfg.get("buttons", "brass") == "brass":
        bcol = srgb((176, 140, 70)) * (1 + 0.2 * gnoise(p * 900, 5))[..., None]
        bm = brass * tun
        alb = T.lerp(alb, bcol, bm)
        metal = np.maximum(metal, bm)
        rough = np.where(bm > 0.5, 0.35, rough)
    elif cfg.get("buttons") == "dark":
        bm = brass * tun
        alb = T.lerp(alb, srgb((40, 34, 28)), bm)
        rough = np.where(bm > 0.5, 0.45, rough)
    # trousers: side seams
    trm = (kind == K["trousers"]) | (kind == K["modern_trousers"])
    for s, sg in (("L", 1), ("R", -1)):
        hp = np.asarray(sk["upperleg02." + s]["head"])
        seam = gauss(np.abs(p[..., 0] - (hp[0] + 0.07 * sg) * 1.0 + 0.0), 0.002) * ((p[..., 0] * sg) > 0)
        h -= 0.00025 * seam * trm
    # puttees: spiral wrap
    ptm = kind == K["puttee"]
    if ptm.any():
        s_ = M["loft_s"][..., 0]
        a_ = M["loft_a"][..., 0]
        pitch = 0.065
        side = np.sign(p[..., 0])
        phase = s_ / pitch + side * a_ / (2 * np.pi)
        fr = phase - np.floor(phase)
        ridge = 0.0012 * (fr - 0.5) + 0.0008 * sstep(0.92, 1.0, fr)
        h = np.where(ptm, h + ridge - 0.0004 * sstep(0.0, 0.06, fr), h)
        alb[ptm] *= (1 - 0.18 * sstep(0.85, 1.0, fr[ptm]) - 0.1 * sstep(0.08, 0.0, fr[ptm]))[..., None]
    # folds ---------------------------------------------------------------------
    for s, sg in (("L", 1), ("R", -1)):
        el = np.asarray(sk["lowerarm01." + s]["head"])
        ax = np.asarray(sk["lowerarm01." + s]["tail"]) - np.asarray(sk["upperarm02." + s]["head"])
        inner = np.cross(np.asarray(sk["upperarm02." + s]["head"]) - el, np.asarray(sk["wrist." + s]["head"]) - el)
        h += fold_field(p, n, el, ax, 0.018, 0.05, 0.0018, seed + 11, inner=-(np.asarray(sk["wrist." + s]["head"]) - el)) * tun
        kn = np.asarray(sk["lowerleg01." + s]["head"])
        axl = np.asarray(sk["foot." + s]["head"]) - np.asarray(sk["upperleg02." + s]["head"])
        h += fold_field(p, n, kn, axl, 0.022, 0.06, 0.002, seed + 12, inner=np.array([0, 0, -1.0])) * trm
        # sleeve bunching above the cuff
        wr = np.asarray(sk["wrist." + s]["head"])
        cuffc = el + (wr - el) * 0.8
        h += fold_field(p, n, cuffc, wr - el, 0.016, 0.04, 0.0012, seed + 13) * tun
        # armpit / shoulder drag folds
        sh = np.asarray(sk["upperarm01." + s]["head"])
        h += fold_field(p, n, sh + np.array([-0.04 * sg, -0.07, 0]), np.array([sg, -0.6, 0]), 0.03, 0.05, 0.0012, seed + 14) * tun
    # waist bunching below the belt and wrinkles at the crotch
    wy = cfg.get("belt_y", 1.0)
    bunch = gauss((p[..., 1] - (wy - 0.05)) / 0.03, 1) * np.clip(np.sin(np.arctan2(p[..., 0], p[..., 2]) * 22 + 2 * gnoise(p * 20, 9)), -1, 1)
    h += 0.0012 * bunch * tun
    # mud & wet --------------------------------------------------------------------
    mud_amt = cfg.get("mud", 0.5)
    mud = mud_field(p, n, mud_amt, seed + 20, wet=cfg.get("wet", 0.5))
    mud_col = srgb(cfg.get("mud_col", (78, 64, 48)))
    dry_col = srgb((128, 112, 88))
    mc = T.lerp(mud_col, dry_col, np.clip(fbm(p * 40, 2, seed=seed + 21) * 0.5 + 0.3, 0, 1))
    alb = T.lerp(alb, mc, mud)
    rough = rough - 0.3 * mud * cfg.get("wet", 0.5)
    h += 0.0006 * mud * fbm(p * 300, 2, seed=seed + 22)
    # rain-darkened shoulders
    wetd = cfg.get("wet", 0.5) * sstep(1.2, 1.5, p[..., 1]) * np.clip(n[..., 1], 0, 1)
    alb *= (1 - 0.18 * wetd)[..., None]
    rough -= 0.12 * wetd
    # bandage / armband / special kinds
    if (kind == K["armband"]).any():
        am = kind == K["armband"]
        alb[am] = srgb((215, 212, 200)) * (1 + 0.04 * fib[am][..., None])
        sbm = armband_text(M, p, sk)
        alb = np.where((am & (sbm > 0.5))[..., None], srgb((150, 30, 28)), alb)
        alb[am] = T.lerp(alb[am], mc[am], np.clip(mud[am] * 0.5, 0, 1))
    if (kind == K["bandage"]).any():
        bm = kind == K["bandage"]
        bh, ba = bandage_pattern(M, p, seed)
        alb[bm] = (srgb((222, 218, 206)) * ba[bm][..., None])
        h = np.where(bm, bh, h)
        rough = np.where(bm, 0.92, rough)
    return dict(albedo=np.clip(alb, 0, 1), height=h, rough=np.clip(rough, 0.25, 0.97), metal=metal)


def mud_field(p, n, amt, seed, wet=0.5):
    y = p[..., 1]
    base = np.clip((0.55 - y) / 0.5, 0, 1) ** 1.5  # stronger towards the ground
    splat = fbm(p * np.array([30, 18, 30]), 4, seed=seed)
    spots, _ = worley(p * 70.0, seed=seed + 1)
    s = np.clip(base * 1.6 + splat * 0.7 - 0.35, 0, 1)
    s += 0.6 * sstep(0.22, 0.08, spots) * np.clip(1.4 - y, 0, 1) * (splat > -0.1)
    # knees and seat
    s += 0.5 * np.clip(fbm(p * 20, 3, seed=seed + 2) + 0.2, 0, 1) * gauss((y - 0.5) / 0.08, 1) * (n[..., 2] > 0.2)
    return np.clip(s * amt, 0, 1)


def tunic_details(p, n, cfg, sk, Lm):
    """Front placket + buttons, breast/skirt pocket flaps, shoulder straps, rifle patches.
    Returns (height, dark seam mask, brass mask)."""
    h = np.zeros(p.shape[:-1])
    dark = np.zeros(p.shape[:-1])
    brass = np.zeros(p.shape[:-1])
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    front = sstep(0.1, 0.4, n[..., 2])
    style = cfg.get("tunic_style", "private")
    # front opening line (slightly off-centre) and placket
    if style != "open":
        ln = gauss(np.abs(x - 0.004) / 0.0012, 1) * front * (y < 1.52) * (y > 0.78)
        h -= 0.0006 * ln
        dark += 0.6 * ln
        ys = np.linspace(1.48, 1.08, 5) if style == "private" else np.linspace(1.36, 0.98, 4)
        for by in ys:
            d = dist(np.stack([x, y], -1), (0.0, by))
            bt = sstep(0.0085, 0.0065, d) * front
            h += 0.0016 * np.sqrt(np.clip(1 - (d / 0.0085) ** 2, 0, 1)) * (d < 0.0085) * front
            brass = np.maximum(brass, bt)
    # breast pockets
    for sg in (1, -1):
        cx = 0.092 * sg
        top = 1.39 if style == "private" else 1.40
        pw, ph = 0.125, 0.135
        inx = np.abs(x - cx) < pw / 2
        iny = (y < top) & (y > top - ph)
        box = (inx & iny) * front
        edge = (sstep(0.004, 0.0, np.abs(np.abs(x - cx) - pw / 2)) * iny +
                sstep(0.004, 0.0, np.abs(y - (top - ph))) * inx) * front
        h += 0.0012 * box - 0.0008 * edge
        dark += 0.5 * edge
        # flap
        fl = (y < top + 0.005) & (y > top - 0.05) & (np.abs(x - cx) < pw / 2 + 0.004)
        flp = fl * front * (1 - 0.6 * sstep(top - 0.05, top - 0.03, y) * 0)
        h += 0.0012 * flp
        fe = sstep(0.003, 0.0, np.abs(y - (top - 0.05 + 0.012 * (1 - np.abs(x - cx) / (pw / 2))))) * \
            (np.abs(x - cx) < pw / 2) * front
        h -= 0.001 * fe
        dark += 0.6 * fe
        # box pleat (privates)
        if style == "private":
            pl = gauss(np.abs(np.abs(x - cx) - 0.016) / 0.0012, 1) * iny * front
            h -= 0.0006 * pl
            dark += 0.4 * pl
        d = dist(np.stack([x, y], -1), (cx, top - 0.038))
        brass = np.maximum(brass, sstep(0.0075, 0.0058, d) * front)
        h += 0.0014 * (d < 0.0075) * front
    # skirt pocket flaps
    for sg in (1, -1):
        cx = 0.125 * sg
        top = 0.955
        fw = 0.18
        inx = np.abs(x - cx) < fw / 2
        flp = inx & (y < top) & (y > top - 0.065)
        h += 0.0012 * flp * front
        fe = sstep(0.003, 0.0, np.abs(y - (top - 0.065))) * inx * front + \
            sstep(0.003, 0.0, np.abs(np.abs(x - cx) - fw / 2)) * (y < top) * (y > top - 0.065) * front
        h -= 0.001 * fe
        dark += 0.5 * fe
        d = dist(np.stack([x, y], -1), (cx, top - 0.045))
        brass = np.maximum(brass, sstep(0.0075, 0.0058, d) * front)
    # shoulder straps
    for sg in (1, -1):
        a = np.array([0.075 * sg, 1.505, 0.0])
        b = np.array([0.19 * sg, 1.46, 0.0])
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1.1)
        q = a + t[..., None] * ab
        dxz = np.linalg.norm((p - q)[..., [0, 2]] * np.array([0.3, 1.0]), axis=-1)
        up = np.clip(n[..., 1], 0, 1)
        on = (np.abs(p[..., 2] - q[..., 2]) < 0.024) * (t < 1.0) * (up > 0.3)
        h += 0.0015 * on
        e = (sstep(0.004, 0.0, np.abs(np.abs(p[..., 2] - q[..., 2]) - 0.024)) * (t < 1.0) * (up > 0.3))
        dark += 0.5 * e
        bp = a + 0.15 * ab
        d = np.linalg.norm(p - bp, axis=-1)
        brass = np.maximum(brass, sstep(0.0075, 0.0058, d) * (up > 0.3))
    # rifle patches (privates)
    if style == "private":
        for sg in (1, -1):
            c = np.array([0.15 * sg, 1.42, 0.06])
            d = np.abs(p - c)
            patch = (d[..., 0] < 0.05) * (d[..., 1] < 0.06) * front
            h += 0.0008 * patch
            pe = patch * (sstep(0.045, 0.05, d[..., 0]) + sstep(0.055, 0.06, d[..., 1]))
            dark += 0.4 * pe
    # cuff seam / officer cuff rank
    for s, sg in (("L", 1), ("R", -1)):
        el = np.asarray(sk["lowerarm01." + s]["head"])
        wr = np.asarray(sk["wrist." + s]["head"])
        ax = wr - el
        t = ((p - el) @ ax) / (ax @ ax)
        side = (x * sg) > 0.25
        if style == "officer":
            for k, tt in enumerate((0.74, 0.77, 0.80)):
                ring = gauss((t - tt) / 0.006, 1) * side
                h += 0.0006 * ring
                dark -= 0.15 * ring
        else:
            ring = gauss((t - 0.8) / 0.006, 1) * side
            h -= 0.0005 * ring
            dark += 0.3 * ring
    return h, np.clip(dark, -0.5, 1), np.clip(brass, 0, 1)


def armband_text(M, p, sk=None):
    """'SB' letters on the outer side of the left upper-arm armband (3D placement)."""
    a = np.asarray(sk["upperarm02.L"]["head"])
    b = np.asarray(sk["lowerarm01.L"]["head"])
    ax = (b - a) / np.linalg.norm(b - a)
    lat = np.array([1.0, 0, 0]) - np.dot([1.0, 0, 0], ax) * ax
    lat /= np.linalg.norm(lat)
    fwd = np.cross(ax, lat)
    d = p - a
    t = d @ ax
    tc = 0.47 * np.linalg.norm(b - a)
    q = d - t[..., None] * ax
    ang = np.arctan2(q @ fwd, q @ lat)
    u = -ang / 0.75
    v = -(t - tc) / 0.017
    return letters_SB(u, v) * (np.abs(ang) < 1.2)


def letters_SB(u, v):
    """Procedural blocky serif-less 'S' and 'B' in [-1,1]^2 (u horizontal)."""
    m = np.zeros_like(u)
    th = 0.16
    # S on the left half: centre u=-0.42
    su = (u + 0.42) / 0.36
    sv = v
    inS = (np.abs(su) <= 1) & (np.abs(sv) <= 1)
    top = (np.abs(sv - 0.85) < th) & (np.abs(su) < 0.9)
    mid = (np.abs(sv) < th) & (np.abs(su) < 0.9)
    bot = (np.abs(sv + 0.85) < th) & (np.abs(su) < 0.9)
    lft = (np.abs(su + 0.8) < th * 1.2) & (sv > 0) & (sv < 0.9)
    rgt = (np.abs(su - 0.8) < th * 1.2) & (sv < 0) & (sv > -0.9)
    m = np.maximum(m, (inS & (top | mid | bot | lft | rgt)).astype(float))
    bu = (u - 0.42) / 0.36
    inB = (np.abs(bu) <= 1) & (np.abs(sv) <= 1)
    stem = np.abs(bu + 0.8) < th * 1.2
    btop = (np.abs(sv - 0.85) < th) & (bu < 0.6)
    bmid = (np.abs(sv) < th) & (bu < 0.7)
    bbot = (np.abs(sv + 0.85) < th) & (bu < 0.7)
    r1 = (np.abs(bu - 0.68) < th * 1.2) & (sv > 0.05) & (sv < 0.85)
    r2 = (np.abs(bu - 0.78) < th * 1.2) & (sv < -0.05) & (sv > -0.85)
    m = np.maximum(m, (inB & (stem | btop | bmid | bbot | r1 | r2)).astype(float))
    return m


def bandage_pattern(M, p, seed):
    s = M["loft_s"][..., 0] if "loft_s" in M else p[..., 1]
    a = M["loft_a"][..., 0] if "loft_a" in M else np.zeros_like(s)
    phase = s / 0.03 + a / (2 * np.pi) * 0.6
    fr = phase - np.floor(phase)
    weave = 0.5 + 0.5 * np.sin(p[..., 0] * 4000) * np.sin(p[..., 1] * 4000 + p[..., 2] * 3000)
    h = 0.0008 * (fr - 0.5) + 0.00008 * weave
    alb = 0.92 + 0.05 * weave - 0.12 * sstep(0.9, 1.0, fr) - 0.05 * fbm(p * 40, 2, seed=seed + 70)
    return h, np.clip(alb, 0.6, 1.0)


# ----------------------------------------------------------------------------------
# gear (webbing, leather, brass, boots, felt, steel, canvas)
# ----------------------------------------------------------------------------------


def paint_gear(M, cfg, sk):
    p = M["pos"]
    n = M["nrm"]
    kind = np.rint(M["kind"][..., 0]).astype(int)
    seed = cfg.get("seed", 1) + 100
    alb = np.zeros(p.shape)
    h = np.zeros(p.shape[:-1])
    rough = np.full(p.shape[:-1], 0.8)
    metal = np.zeros(p.shape[:-1])
    g = fbm(p * 80, 3, seed=seed)
    # webbing (1908 pattern: pale khaki-green woven cotton)
    web = (kind == K["webbing"]) | (kind == K["canvas"]) | (kind == K["strap"])
    wc = srgb(cfg.get("web_col", (150, 140, 102)))
    rib = np.sin((p[..., 0] * 0.4 + p[..., 1] * 1.0 + p[..., 2] * 0.3) * 2 * np.pi / 0.0016)
    alb[web] = wc * (1 + 0.08 * g[web][..., None] + 0.04 * rib[web][..., None])
    h += np.where(web, 0.00012 * rib + 0.0001 * gnoise(p * 2000, seed + 1), 0)
    rough[web] = 0.85
    if (kind == K["canvas"]).any():
        cm = kind == K["canvas"]
        alb[cm] = srgb(cfg.get("canvas_col", (138, 126, 92))) * (1 + 0.08 * g[cm][..., None])
    # pouch flaps / edges using pouch params
    if "pouch_u" in M:
        pu = M["pouch_u"][..., 0]
        pv = M["pouch_v"][..., 0]
        pf = M["pouch_front"][..., 0]
        isp = M["is_pouch"][..., 0] > 0.5
        ncols = np.where(pv > 0.45, 3, 2)
        col_f = pu * ncols
        sep = np.abs(col_f - np.round(col_f))
        groove = sstep(0.06, 0.0, sep) * (np.round(col_f) > 0) * (np.round(col_f) < ncols) * pf
        row = sstep(0.03, 0.0, np.abs(pv - 0.45)) * pf
        flap = sstep(0.04, 0.0, np.abs(np.mod(pv, 0.55) - 0.4)) * pf
        h += np.where(isp, -0.0012 * (groove + row) - 0.0006 * flap, 0)
        alb[isp] *= (1 - 0.25 * (groove + row)[isp] - 0.1 * flap[isp])[..., None]
        # press studs
        cu = (np.floor(col_f) + 0.5) / ncols
        cv = np.where(pv > 0.45, 0.62, 0.15)
        d = np.sqrt(((pu - cu) * 0.17) ** 2 + ((pv - cv) * 0.13) ** 2)
        stud = sstep(0.0055, 0.004, d) * pf * isp
        alb = T.lerp(alb, srgb((170, 135, 70)), stud)
        metal = np.maximum(metal, stud)
        h += 0.0012 * stud
    # ribbon edges (straps/braces/belt) darker & raised stitch rows
    if "rib_t" in M:
        rt = M["rib_t"][..., 0]
        isr = M["is_ribbon"][..., 0] > 0.5
        e = sstep(0.12, 0.0, np.minimum(rt, 1 - rt))
        h += np.where(isr, -0.0004 * e, 0)
        alb[isr] *= (1 - 0.15 * e[isr])[..., None]
    # brass
    br = kind == K["brass"]
    alb[br] = srgb((180, 142, 72)) * (1 + 0.15 * g[br][..., None])
    metal[br] = 1.0
    rough[br] = 0.35 + 0.2 * np.clip(g[br], 0, 1)
    # leather (chin strap, Sam Browne, scabbard)
    le = kind == K["leather"]
    lc = srgb(cfg.get("leather_col", (92, 58, 34)))
    crease = fbm(p * np.array([300, 120, 300]), 3, seed=seed + 5)
    alb[le] = lc * (1 + 0.15 * g[le][..., None] - 0.1 * np.abs(crease[le])[..., None])
    h += np.where(le, 0.0003 * crease + 0.00008 * gnoise(p * 3000, seed + 6), 0)
    rough[le] = 0.5 - 0.15 * np.clip(crease[le], 0, 1)
    # boots: brown leather, toe-cap seam, laces, heavy mud
    bo = kind == K["boot"]
    bc = srgb(cfg.get("boot_col", (86, 56, 34)))
    alb[bo] = bc * (1 + 0.12 * g[bo][..., None] - 0.12 * np.abs(crease[bo])[..., None])
    h += np.where(bo, 0.0004 * crease, 0)
    rough[bo] = 0.55
    if bo.any():
        for s, sg in (("L", 1), ("R", -1)):
            toe = np.asarray(sk["toes." + s]["head"])
            side = (p[..., 0] * sg) > 0
            # toe cap seam: arc across the forefoot
            d = np.abs(p[..., 2] - (toe[2] + 0.015 - 0.4 * (p[..., 0] - toe[0]) ** 2 * 30))
            seam = gauss(d / 0.0015, 1) * side * (p[..., 1] > 0.015)
            h -= 0.0007 * seam * bo
            # laces on the instep
            ank = np.asarray(sk["foot." + s]["head"])
            lx = np.abs(p[..., 0] - ank[0])
            lace_zone = (lx < 0.018) * (p[..., 2] > ank[2] + 0.01) * (p[..., 2] < toe[2] - 0.02) * (n[..., 1] > 0.3) * side
            rows = np.abs(np.sin(p[..., 2] * 2 * np.pi / 0.012))
            alb[bo & (lace_zone > 0)] *= 0.55
            h += 0.0006 * lace_zone * rows * bo
        # sole edge dark
        sole = sstep(0.022, 0.012, p[..., 1])
        alb[bo] = T.lerp(alb[bo], srgb((40, 30, 24)), sole[bo])
    # felt (water bottle cover)
    fe = kind == K["felt"]
    alb[fe] = srgb(cfg.get("felt_col", (92, 86, 70))) * (1 + 0.08 * gnoise(p * 600, 7)[fe][..., None])
    rough[fe] = 0.95
    h += np.where(fe, 0.0002 * gnoise(p * 1500, seed + 8), 0)
    # steel parts
    st = kind == K["steel"]
    alb[st] = srgb((70, 70, 68)) * (1 + 0.1 * g[st][..., None])
    metal[st] = 0.9
    rough[st] = 0.45
    # rubber/plastic (modern)
    rb = kind == K["rubber"]
    alb[rb] = srgb(cfg.get("rubber_col", (35, 35, 36)))
    rough[rb] = 0.7
    # gaiters (officer): leather
    ga = kind == K["gaiter"]
    alb[ga] = srgb(cfg.get("gaiter_col", (100, 64, 38))) * (1 + 0.12 * g[ga][..., None])
    rough[ga] = 0.45
    # device band (fp arms)
    # mud
    mud = mud_field(p, n, cfg.get("mud", 0.5) * 1.1, seed + 30)
    mud_col = srgb(cfg.get("mud_col", (78, 64, 48)))
    sel = kind != K["brass"]
    alb = T.lerp(alb, mud_col, mud * sel)
    rough = rough - 0.25 * mud * cfg.get("wet", 0.5) * sel
    h += 0.0005 * mud * fbm(p * 300, 2, seed=seed + 31)
    # boots get a lot more mud
    bm = np.clip((0.14 - p[..., 1]) / 0.1, 0, 1) * cfg.get("boot_mud", 0.8) * (0.6 + 0.4 * fbm(p * 50, 3, seed=seed + 32))
    alb = T.lerp(alb, mud_col * 0.9, np.clip(bm, 0, 0.95) * (bo | (kind == K["gaiter"])))
    return dict(albedo=np.clip(alb, 0, 1), height=h, rough=np.clip(rough, 0.2, 0.97), metal=metal)


# ----------------------------------------------------------------------------------
# helmet
# ----------------------------------------------------------------------------------


def paint_helmet(M, cfg):
    p = M["pos"]
    n = M["nrm"]
    kind = np.rint(M["kind"][..., 0]).astype(int)
    seed = cfg.get("seed", 1) + 200
    outer = M["outer"][..., 0]
    prof = M["prof_k"][..., 0]
    paint = srgb(cfg.get("helmet_col", (92, 88, 60)))
    g = fbm(p * 60, 3, seed=seed)
    grit = gnoise(p * 2500, seed + 1)  # sand/sawdust textured paint
    alb = paint * (1 + 0.08 * g[..., None] + 0.04 * grit[..., None])
    h = 0.00015 * grit + 0.00008 * gnoise(p * 6000, seed + 2)
    rough = 0.72 + 0.08 * grit
    metal = np.zeros(p.shape[:-1])
    # chipped paint along the rim edge (+ a few scratches on the bowl)
    rim = sstep(0.86, 0.99, prof) * (outer > 0.5)
    chips_n = fbm(p * 400, 3, seed=seed + 3)
    chip = np.clip((chips_n - 0.55 + 0.5 * rim) * 6, 0, 1) * rim
    scr = sstep(0.965, 0.995, np.abs(gnoise(p * np.array([40, 900, 40]), seed + 4)))
    chip = np.maximum(chip, 0.7 * scr * (fbm(p * 20, 2, seed=seed + 5) > 0.25) * (outer > 0.5))
    steel = srgb((70, 68, 64)) * (1 + 0.15 * gnoise(p * 800, seed + 6))[..., None]
    rust = srgb((96, 56, 34))
    rusty = np.clip(fbm(p * 90, 3, seed=seed + 7) * 1.5, 0, 1) * cfg.get("rust", 0.3)
    metal_col = T.lerp(steel, rust, rusty)
    alb = T.lerp(alb, metal_col, chip)
    metal = np.maximum(metal, chip * (1 - rusty))
    rough = np.where(chip > 0.5, 0.45 + 0.4 * rusty, rough)
    h -= 0.00012 * chip
    # liner: dark brown oilcloth/leather
    ln = kind == K["liner"]
    alb[ln] = srgb((52, 38, 28)) * (1 + 0.1 * g[ln][..., None])
    rough[ln] = 0.6
    # inside the bowl a bit darker (dirt)
    inside = (outer < 0.5) & ~ln
    alb[inside] *= 0.8
    # mud splashes + rain wetness
    mud = np.clip((fbm(p * 45, 4, seed=seed + 8) - 0.25) * 2.5, 0, 1) * cfg.get("helmet_mud", 0.35)
    mud *= (outer > 0.5)
    alb = T.lerp(alb, srgb((80, 66, 50)), mud)
    rough -= 0.25 * mud
    rough -= 0.15 * cfg.get("wet", 0.5) * np.clip(n[..., 1], 0, 1) * (outer > 0.5)
    return dict(albedo=np.clip(alb, 0, 1), height=h, rough=np.clip(rough, 0.2, 0.95), metal=np.clip(metal, 0, 1))


# ----------------------------------------------------------------------------------
# hair & eyes
# ----------------------------------------------------------------------------------


def paint_hair(M, cfg, Lm):
    p = M["pos"]
    n = M["nrm"]
    seed = cfg.get("seed", 1) + 300
    col = srgb(cfg.get("hair_col", (60, 42, 28)))
    # flow direction: from the crown down/back over the scalp
    crown = Lm["head"] + np.array([0, 0.13, -0.03])
    d = p - crown
    flow = d - (d * n).sum(-1, keepdims=True) * n
    flow /= np.maximum(np.linalg.norm(flow, axis=-1, keepdims=True), 1e-6)
    # anisotropic strand noise: sample noise in a frame stretched along the flow
    side = np.cross(n, flow)
    q1 = (p * side).sum(-1) * 2600
    q2 = (p * flow).sum(-1) * 260
    strands = gnoise(np.stack([q1, q2, (p * n).sum(-1) * 100], -1), seed)
    strands2 = gnoise(np.stack([q1 * 2.3, q2 * 1.7, p[..., 1] * 50], -1), seed + 1)
    s = 0.6 * strands + 0.4 * strands2
    alb = col * (1 + 0.35 * s[..., None]) * (1 + 0.15 * fbm(p * 40, 2, seed=seed + 2)[..., None])
    # greying for the older character
    grey = cfg.get("grey", 0.0)
    if grey:
        gm = np.clip(gnoise(p * 900, seed + 5) * 0.5 + 0.5, 0, 1) * grey * sstep(Lm["eye.L"][1], Lm["eye.L"][1] + 0.05, p[..., 1])
        alb = T.lerp(alb, srgb((150, 145, 140)), gm)
    h = 0.0003 * s
    rough = 0.55 + 0.15 * s
    dens = M["dens"][..., 0] if "dens" in M else np.ones(p.shape[:-1])
    return dict(albedo=np.clip(alb, 0, 1), height=h, rough=np.clip(rough, 0.3, 0.9), metal=np.zeros_like(rough))


def paint_eyes(M, cfg, Lm):
    p = M["pos"]
    seed = cfg.get("seed", 1) + 400
    alb = np.zeros(p.shape)
    out_r = np.full(p.shape[:-1], 0.12)
    iris_col = srgb(cfg.get("iris", (95, 70, 45)))
    for s in "LR":
        c = Lm["eye." + s] + np.array([0, 0, -0.002])
        side = (p[..., 0] > 0) if s == "L" else (p[..., 0] <= 0)
        d = p - c
        r = np.linalg.norm(d, axis=-1)
        ang = np.degrees(np.arccos(np.clip(d[..., 2] / np.maximum(r, 1e-6), -1, 1)))
        theta = np.arctan2(d[..., 1], d[..., 0])
        sclera = srgb((228, 222, 212)) * (1 - 0.06 * sstep(40, 90, ang))[..., None]
        veins = sstep(0.75, 0.95, np.abs(gnoise(np.stack([theta * 6, ang * 0.3, np.zeros_like(ang)], -1), seed))) * sstep(45, 80, ang)
        sclera = T.lerp(sclera, srgb((190, 110, 100)), veins * 0.3)
        fib = 0.5 + 0.5 * gnoise(np.stack([theta * 30, ang * 1.5, np.zeros_like(ang)], -1), seed + 1)
        iris = iris_col * (0.6 + 0.7 * fib[..., None]) * (1 - 0.4 * sstep(18, 26, ang))[..., None]
        iris = T.lerp(iris, iris_col * 1.5, sstep(9, 6, ang) * 0.4)
        e = sstep(27, 24, ang)
        pupil = sstep(10.5, 8.5, ang)
        col = T.lerp(sclera, iris, e)
        col = T.lerp(col, np.array([0.01, 0.01, 0.012]), pupil)
        alb = np.where(side[..., None], col, alb)
    return dict(albedo=np.clip(alb, 0, 1), height=np.zeros(p.shape[:-1]), rough=out_r, metal=np.zeros(p.shape[:-1]))
