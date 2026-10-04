"""WWI Somme ground materials: mud_wet, earth_wall, chalk_spoil, grass_dead, stone_rubble."""
from __future__ import annotations

import numpy as np

from lib.core import (N, TAU, blur, bandnoise, fbm, hexlin, mix, norm01, ramp, rng_for, smoothstep,
                      spectral, stamp, uv, warp)
from lib.elements import boot_print, puddles, rotate_sprite, scatter_stones
from lib.pbr import Material


def _carve_print(rng, h, ppm, x, y, ang, depth, smear, partial, left, stud_depth=0.002, extra_blur=0.0):
    ph, pm = boot_print(rng, ppm, depth=depth, left=left, smear=smear, partial=partial, stud_depth=stud_depth)
    if extra_blur > 0:
        import cv2
        ph = cv2.GaussianBlur(ph, (0, 0), extra_blur)
    ph = rotate_sprite(ph, ang)
    pm = rotate_sprite(pm, ang)
    n = h.shape[0]
    hh, ww = ph.shape
    ys = (np.arange(int(round(y - hh / 2)), int(round(y - hh / 2)) + hh) % n)
    xs = (np.arange(int(round(x - ww / 2)), int(round(x - ww / 2)) + ww) % n)
    reg = h[np.ix_(ys, xs)]
    lvl = np.median(reg[pm > 0.5]) if (pm > 0.5).any() else reg.mean()
    dep = np.minimum(ph, 0)
    rim = np.maximum(ph, 0)
    w = np.clip(-dep / (depth * 0.25), 0, 1)
    carved = np.minimum(reg, lvl + dep)
    reg = reg * (1 - w) + carved * w + rim
    h[np.ix_(ys, xs)] = reg
    return ys, xs, w


def mud_wet(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    # --- height (metres)
    macro = spectral(rng, beta=3.6, fmin=1) * 0.02
    wx = spectral(rng, beta=3.0, fmin=2) * 24
    wy = spectral(rng, beta=3.0, fmin=2) * 24
    mid = warp(spectral(rng, beta=3.0, fmin=5, fmax=120), wx, wy)
    churn = blur(np.sign(mid) * np.abs(mid) ** 0.85, 1.2) * 0.0055
    # plastic smears: sharp-crested stretched ridges (squeezed mud) in a few directions
    smear = 0.0
    for i in range(3):
        s = bandnoise(rng, f=rng.uniform(10, 22), width=0.3, stretch=(1.0, 3.5), angle=rng.uniform(0, np.pi))
        smear = smear + (1 - np.abs(s)) ** 4 * rng.uniform(0.6, 1.0)
    smear = smear * 0.003 * smoothstep(0.0, 1.2, spectral(rng, beta=3, fmin=2))
    h = macro + churn + smear
    # ruts / trodden channels running along x (trench direction), periodic in x
    for i in range(2):
        k = int(rng.integers(1, 3))
        yc = rng.uniform(0, 1) + 0.05 * np.sin(TAU * k * u + rng.uniform(0, TAU)) + \
            0.015 * np.sin(TAU * 3 * u + rng.uniform(0, TAU))
        d = np.abs(((v - yc + 0.5) % 1.0) - 0.5) * tile_m  # metres from rut centre
        wdt = rng.uniform(0.08, 0.13)
        dep = rng.uniform(0.02, 0.035) * (0.6 + 0.4 * norm01(spectral(rng, beta=3, fmin=2)))
        h += -dep * np.exp(-(d / wdt) ** 2) + dep * 0.35 * np.exp(-((d - wdt * 1.5) / (wdt * 0.6)) ** 2)
    # old, trampled-over impressions (soft), then a few fresh crisp prints on top
    for i in range(60):
        x, y = rng.uniform(0, n, 2)
        ang = (90 if rng.random() < 0.5 else -90) + rng.normal(0, 25)
        _carve_print(rng, h, ppm, x, y, ang, depth=rng.uniform(0.006, 0.02), smear=rng.uniform(0.5, 1.0),
                     partial=rng.uniform(0.3, 1.0), left=rng.random() < 0.5, stud_depth=0.0,
                     extra_blur=rng.uniform(2, 6))
    # re-smear everything a bit (people walk through it)
    h = h * 0.6 + 0.4 * warp(h, wx * 0.3, wy * 0.3)
    for i in range(6):
        x, y = rng.uniform(0, n, 2)
        ang = (90 if rng.random() < 0.5 else -90) + rng.normal(0, 18)
        _carve_print(rng, h, ppm, x, y, ang, depth=rng.uniform(0.012, 0.025), smear=rng.uniform(0, 0.35),
                     partial=1.0 if rng.random() < 0.6 else rng.uniform(0.5, 0.8), left=rng.random() < 0.5,
                     stud_depth=0.0018, extra_blur=0.6)
    h = h + blur(rng.standard_normal((n, n)).astype(np.float32), 1.4) * 0.00008  # fine grit
    # --- colour
    base_t = norm01(warp(spectral(rng, beta=3.0, fmin=2), wx, wy))
    col = ramp(base_t, [(0, "#3f352a"), (0.4, "#52463a"), (0.75, "#5e5242"), (1.0, "#6a5e4c")])
    grey = norm01(warp(spectral(rng, beta=3.2, fmin=3), wx, wy))
    col = mix(col, hexlin("#6a665e"), smoothstep(0.62, 0.92, grey) * 0.55)    # grey chalky clay smears
    ochre = norm01(warp(spectral(rng, beta=2.8, fmin=5), wx, wy))
    col = mix(col, hexlin("#6a4f33"), smoothstep(0.78, 0.97, ochre) * 0.4)    # iron staining
    col = col * (0.92 + 0.12 * norm01(spectral(rng, beta=2.0, fmin=10))[..., None])
    # stones (flint, chalk bits, brick crumbs)
    rough = np.full((n, n), 0.6, np.float32)
    stone_id = np.zeros((n, n), np.float32)
    pal = [hexlin("#5c5a56"), hexlin("#3e3c3a"), hexlin("#9d978a"), hexlin("#857d70"), hexlin("#6e4836")]
    scatter_stones(rng, h, col, 110, (3, 18), pal, embed=(0.3, 0.75), h_scale_m=0.016, angular=0.5,
                   rough_map=rough, rough_val=0.42, id_map=stone_id, tint_jitter=0.12)
    scatter_stones(rng, h, col, 250, (1.2, 4), pal, embed=(0.4, 0.8), h_scale_m=0.004, angular=0.5,
                   rough_map=rough, rough_val=0.45, id_map=stone_id, tint_jitter=0.12)
    # mud film over stones
    film = smoothstep(0.3, 0.8, norm01(spectral(rng, beta=2.2, fmin=16)))
    col = mix(col, hexlin("#4b4033"), stone_id * 0.5 * film)
    # relative height cues: crests drier/lighter, hollows darker and wetter
    rel = h - blur(h, 0.06 * ppm)
    reln = np.clip(rel / 0.01, -1, 1)
    col = col * (1.0 + 0.14 * reln[..., None])
    rough = rough + 0.13 * reln - 0.04
    # water
    water, lvl = puddles(h, 14, soft_m=0.0015)
    shore = smoothstep(lvl + 0.005, lvl, h) * (1 - water)
    ripple = blur(rng.standard_normal((n, n)).astype(np.float32), 3.0) * 0.00003
    h = h * (1 - water) + (lvl + ripple) * water
    col = col * (1 - 0.28 * shore[..., None])
    wcol = col * 0.6 + hexlin("#2c261e") * 0.2
    col = mix(col, wcol, water)
    rough = rough * (1 - shore * 0.45)
    rough = mix(rough, 0.06 + 0.06 * norm01(spectral(rng, beta=2.5, fmin=6)), water)
    rough = np.clip(rough + 0.035 * spectral(rng, beta=2.2, fmin=12), 0.04, 0.85)
    return Material(name, tile_m, col, h, rough, normal_strength=1.0, ao_radii_m=(0.004, 0.015, 0.05))


def _chalk_texture(rng, shape):
    import cv2
    t = cv2.GaussianBlur(rng.standard_normal(shape).astype(np.float32), (0, 0), 1.2)
    return 1.0 + 0.07 * t / (t.std() + 1e-6)


def earth_wall(name, tile_m):
    """Cut trench wall, V = up. Strata are horizontal and periodic over the 2 m tile."""
    import cv2
    from lib.strokes import StrokeCanvas
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    # strata coordinate: y warped by gentle undulation
    sw = spectral(rng, beta=3.5, fmin=1, stretch=(0.5, 1.0)) * 18 + spectral(rng, beta=2.5, fmin=6) * 2.5
    ys = (np.arange(n)[:, None] + sw) % n
    prof = np.cumsum(rng.standard_normal(n))
    prof = prof - np.linspace(prof[0], prof[-1], n)  # periodic random walk
    prof1 = cv2.GaussianBlur(prof.reshape(-1, 1).astype(np.float32), (0, 0), 6).ravel()
    prof1 = (prof1 - prof1.min()) / (np.ptp(prof1) + 1e-9)
    stratum = np.interp(ys, np.arange(n + 1), np.r_[prof1, prof1[0]]).astype(np.float32)
    # discrete thin bands (chalky / grey clay seams)
    seam_lines = np.zeros(n, np.float32)
    for k in range(7):
        c = rng.uniform(0, n)
        wdt = rng.uniform(3, 14)
        d = np.abs(((np.arange(n) - c + n / 2) % n) - n / 2)
        seam_lines += rng.uniform(0.4, 1.0) * smoothstep(wdt, wdt * 0.4, d)
    seam = np.interp(ys, np.arange(n + 1), np.r_[seam_lines, seam_lines[0]]).astype(np.float32)
    seam *= smoothstep(-0.6, 0.6, spectral(rng, beta=2.8, fmin=3, stretch=(0.3, 1)))
    seam = blur(seam, 1.5)
    # --- height
    # spade facets: vertically elongated scalloped cells
    pts = rng.random((70, 2))
    d, idx, _ = __import__("lib.core", fromlist=["worley"]).worley(rng, pts=pts, k=2, aspect=(1.0, 0.45))
    f1 = d[..., 0]
    scal = f1 ** 2
    scal = scal / np.percentile(scal, 99)
    dxw = (u - pts[idx[..., 0], 0] + 0.5) % 1.0 - 0.5
    dyw = (v - pts[idx[..., 0], 1] + 0.5) % 1.0 - 0.5
    tilt = rng.uniform(-1, 1, len(pts))[idx[..., 0]] * dxw * 2 + rng.uniform(-0.5, 0.5, len(pts))[idx[..., 0]] * dyw
    facet = (-scal * 0.6 + tilt * 0.6) * 0.08
    facet = blur(facet, 1.0)
    scrape = bandnoise(rng, f=70, width=0.5, stretch=(1.0, 0.06)) * 0.0009   # blade striations (vertical)
    scrape *= smoothstep(-0.3, 0.8, spectral(rng, beta=3, fmin=3))
    crumb = spectral(rng, beta=2.6, fmin=8, fmax=250)
    crumb = np.sign(crumb) * np.abs(crumb) ** 1.4 * 0.0011
    macro = spectral(rng, beta=3.5, fmin=1) * 0.02
    h = macro + facet + scrape + crumb * (0.6 + 0.8 * stratum)
    # rain runnels (vertical, soft)
    run = bandnoise(rng, f=30, width=0.4, stretch=(1.0, 0.15))
    h -= np.clip(run - 1.2, 0, None) * 0.004
    # worm / root holes
    for i in range(70):
        x, y = rng.uniform(0, n, 2)
        r = rng.uniform(1.0, 3.5)
        spr = np.zeros((int(r * 4) + 3,) * 2, np.float32)
        c0 = spr.shape[0] / 2
        yy, xx = np.mgrid[0:spr.shape[0], 0:spr.shape[1]]
        spr = -0.005 * np.exp(-(((xx - c0) ** 2 + (yy - c0) ** 2) / (r * r)))
        stamp(h, spr.astype(np.float32), x, y, mode="add")
    # --- colour
    # soften strata: blend with blotchy, lens-shaped mottling so bands are not stripe-regular
    lens = norm01(spectral(rng, beta=3.0, fmin=2, stretch=(0.35, 1.0)))
    stratum = np.clip(stratum * 0.6 + lens * 0.4 + 0.1 * spectral(rng, beta=2.5, fmin=8), 0, 1)
    pal = ramp(stratum, [(0.0, "#4a3a2a"), (0.3, "#5c4632"), (0.55, "#6e5638"), (0.8, "#84694a"),
                         (1.0, "#857a66")])
    col = pal * (0.9 + 0.18 * norm01(spectral(rng, beta=2.6, fmin=4))[..., None])
    col = mix(col, hexlin("#86806f"), np.clip(seam, 0, 1) * 0.45)
    col = mix(col, hexlin("#7c5634"), smoothstep(0.7, 0.95, norm01(spectral(rng, beta=2.2, fmin=10))) * 0.35)
    rough = 0.72 + 0.08 * spectral(rng, beta=2.0, fmin=6)
    # chalk flecks + flints
    flecks = np.zeros((n, n), np.float32)
    scatter_stones(rng, h, col, 500, (0.8, 3.5), [hexlin("#b9b3a3"), hexlin("#a9a291")], embed=(0.4, 0.9),
                   h_scale_m=0.004, angular=0.7, rough_map=rough, rough_val=0.85, id_map=flecks,
                   tint_jitter=0.08, texture_fn=_chalk_texture)
    scatter_stones(rng, h, col, 2500, (1.0, 5.0), [hexlin("#bab4a4"), hexlin("#aaa392")], embed=(0.3, 0.8),
                   h_scale_m=0.006, angular=0.7, faceted=0.5, rough_map=rough, rough_val=0.85, id_map=flecks,
                   tint_jitter=0.08, texture_fn=_chalk_texture, avoid=(seam < 0.2).astype(np.float32))
    scatter_stones(rng, h, col, 60, (3, 12), [hexlin("#b5ae9c"), hexlin("#a39c8a")], embed=(0.4, 0.8),
                   h_scale_m=0.012, angular=0.7, faceted=0.6, rough_map=rough, rough_val=0.85,
                   id_map=flecks, tint_jitter=0.08, texture_fn=_chalk_texture)
    scatter_stones(rng, h, col, 14, (4, 10), [hexlin("#3b3a3a"), hexlin("#4a4744")], embed=(0.4, 0.7),
                   h_scale_m=0.01, angular=0.3, rough_map=rough, rough_val=0.5, tint_jitter=0.1)
    # roots (mostly in the darker loam strata)
    sc = StrokeCanvas(n, {"h": 0.0, "a": 0.0}, ss=2)
    for i in range(70):
        x, y = rng.uniform(0, n, 2)
        if stratum[int(y), int(x)] > 0.6 and rng.random() < 0.5:
            continue
        L = rng.uniform(40, 260)
        m = int(L / 6) + 3
        ang = rng.uniform(0, TAU) if rng.random() < 0.4 else np.pi / 2 + rng.normal(0, 0.6)
        pts = [np.array([x, y])]
        a = ang
        for j in range(m - 1):
            a += rng.normal(0, 0.25)
            pts.append(pts[-1] + 6 * np.array([np.cos(a), np.sin(a)]))
        w0 = rng.uniform(1.5, 6.0)
        widths = np.linspace(w0, 0.8, m)
        hz = rng.uniform(0.6, 1.0)
        sc.ribbon(np.array(pts), widths, lambda i_, t: {"h": hz * (1 - 0.5 * t), "a": 1.0})
        # rootlets
        for b in range(int(rng.integers(0, 4))):
            k0 = int(rng.integers(0, m - 1))
            p0 = pts[k0]
            bl = int(rng.integers(3, 10))
            ba = a + rng.choice([-1, 1]) * rng.uniform(0.5, 1.2)
            q = [p0]
            for j in range(bl):
                ba += rng.normal(0, 0.3)
                q.append(q[-1] + 4 * np.array([np.cos(ba), np.sin(ba)]))
            sc.ribbon(np.array(q), np.linspace(max(widths[k0] * 0.5, 0.6), 0.4, len(q)),
                      lambda i_, t: {"h": hz * 0.6, "a": 1.0})
    ra = sc.get("a")
    rh = sc.get("h")
    bury = smoothstep(-0.8, 0.0, spectral(rng, beta=2.5, fmin=12))  # roots dip in and out of the soil
    ra = ra * bury
    h = h + rh * 0.004 * bury
    rootcol = ramp(norm01(spectral(rng, beta=2, fmin=20)), [(0, "#2e2219"), (0.45, "#4e3c2b"), (0.7, "#7d6c56"),
                                                           (1, "#8f816b")])
    col = mix(col, rootcol, np.clip(ra * 1.2, 0, 1))
    rough = mix(rough, 0.6, ra)
    # damp: darker where wet patches seep (lower half of strata-agnostic noise), glossier
    damp = smoothstep(0.45, 0.85, norm01(spectral(rng, beta=3.0, fmin=2, stretch=(1.0, 0.6))))
    col = col * (1 - 0.3 * damp[..., None])
    rough = rough - 0.22 * damp
    rel = h - blur(h, 0.04 * ppm)
    col = col * (1 + 0.1 * np.clip(rel / 0.008, -1, 1))[..., None]
    rough = np.clip(rough + 0.03 * spectral(rng, beta=2.0, fmin=20), 0.35, 0.95)
    return Material(name, tile_m, col, h, rough, normal_strength=1.0, ao_radii_m=(0.003, 0.012, 0.04))


def _chunk_stack(rng, h, tile_m, layers, keep_field=None):
    """Composite several Voronoi chunk layers on top of base height h (metres).
    layers: list of dicts(npts, keep, gap, lift, embed, tilt). Returns (h, winner, infos)."""
    from lib.elements import voronoi_chunks
    n = h.shape[0]
    winner = np.full((n, n), -1, np.int32)
    infos = []
    hs = blur(h, 6)
    for li, L in enumerate(layers):
        ch = voronoi_chunks(rng, L["npts"], n=n, gap=L.get("gap", (0.05, 0.4)), keep=L.get("keep", 1.0),
                            tilt=L.get("tilt", 0.7), bevel=L.get("bevel", 0.35), crease=L.get("crease", 0.5),
                            jitter=L.get("jitter", 0.9), keep_field=keep_field)
        r_m = ch["r"] * tile_m
        rough_tex = spectral(rng, beta=2.2, fmin=20, fmax=400) * L.get("tex", 0.04)
        lift = rng.uniform(*L.get("lift", (0.3, 0.6)), len(ch["pts"]))[ch["cid"]]
        hc = hs + (ch["h"] * (1 + rough_tex) - lift) * r_m * L.get("hscale", 0.8)
        take = (ch["mask"] > 0.5) & (hc > h)
        h = np.where(take, hc, h)
        winner[take] = li
        # anti-alias the chunk silhouettes a little
        infos.append(ch)
    return h, winner, infos


def chalk_spoil(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    h = spectral(rng, beta=3.3, fmin=1) * 0.03 + spectral(rng, beta=2.3, fmin=10, fmax=300) * 0.0015
    et = norm01(spectral(rng, beta=2.6, fmin=3))
    col = ramp(et, [(0, "#4b4033"), (0.5, "#5a4d3e"), (1, "#6e6555")])
    fines = smoothstep(0.3, 0.8, norm01(spectral(rng, beta=2.4, fmin=6)))
    col = mix(col, hexlin("#8f897b"), fines * 0.5)
    rough = np.full((n, n), 0.75, np.float32) + 0.05 * spectral(rng, beta=2, fmin=8)
    layers = [dict(npts=110, keep=0.6, gap=(0.08, 0.5), lift=(0.2, 0.6), bevel=0.7),
              dict(npts=650, keep=0.65, gap=(0.08, 0.45), lift=(0.2, 0.6), bevel=0.6),
              dict(npts=3500, keep=0.55, gap=(0.1, 0.5), lift=(0.3, 0.7), tex=0.08, bevel=0.5),
              dict(npts=16000, keep=0.4, gap=(0.1, 0.5), lift=(0.3, 0.8), tex=0.1)]
    kf = 0.45 + 1.0 * norm01(spectral(rng, beta=3.2, fmin=2))
    h, win, infos = _chunk_stack(rng, h, tile_m, layers, keep_field=kf)
    pit = norm01(spectral(rng, beta=1.6, fmin=60))
    for li, ch in enumerate(infos):
        sel = (win == li)
        npt = len(ch["pts"])
        tone = rng.uniform(0, 1, npt)[ch["cid"]]
        ccol = ramp(tone, [(0, "#a8a190"), (0.5, "#c0baa9"), (1, "#d2cdbf")])
        prof = np.clip(ch["ins"] / (0.35 * ch["r"]), 0, 1)
        dirt = np.clip(1 - prof * 1.5, 0, 1) * rng.uniform(0.2, 0.7, npt)[ch["cid"]]
        ccol = mix(ccol, hexlin("#6c6252"), dirt)
        stain = (rng.random(npt) < 0.18)[ch["cid"]] * smoothstep(0.55, 0.85, pit)
        ccol = mix(ccol, hexlin("#9c7c55"), stain * 0.5)
        ccol = ccol * (0.94 + 0.1 * pit)[..., None]
        flint = (rng.random(npt) < (0.035 if li in (1, 2) else 0.0))[ch["cid"]] & sel
        fcol = mix(hexlin("#3b3b3d"), hexlin("#a59e8d"), np.clip(1.3 - prof * 2.2, 0, 1))
        ccol = np.where(flint[..., None], fcol, ccol)
        col = np.where(sel[..., None], ccol, col)
        rough = np.where(sel, np.where(flint, 0.32, 0.9 - 0.08 * dirt), rough)
    rel = h - blur(h, 0.05 * ppm)
    gap = smoothstep(0.0, -0.012, rel)
    col = mix(col, hexlin("#5a4f40"), gap * 0.4)
    col = col * (1 + 0.06 * np.clip(rel / 0.01, -1, 1))[..., None]
    damp = smoothstep(0.5, 0.9, norm01(spectral(rng, beta=3, fmin=2)))
    col = col * (1 - 0.15 * damp[..., None])
    rough = np.clip(rough - 0.15 * damp - 0.1 * gap, 0.3, 0.95)
    return Material(name, tile_m, col, h, rough, normal_strength=1.0, ao_radii_m=(0.004, 0.015, 0.05),
                    ao_strength=1.1)


def grass_dead(name, tile_m):
    """Battered autumn grass over mud, viewed from above."""
    from lib.strokes import StrokeCanvas
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    # mud substrate
    h0 = spectral(rng, beta=3.4, fmin=1) * 0.02 + spectral(rng, beta=2.4, fmin=12, fmax=250) * 0.0015
    mud = ramp(norm01(spectral(rng, beta=2.6, fmin=3)), [(0, "#3a3026"), (0.6, "#4b3e30"), (1, "#5a4d3c")])
    density = norm01(blur(spectral(rng, beta=2.8, fmin=2), 4))
    flatten_dir = spectral(rng, beta=3.6, fmin=1) * 1.2 + rng.uniform(0, TAU)  # matted direction field
    stems = [  # straw / dead grass / olive / faded green  (sRGB)
        ("#a08a5f", "#cdb88a"), ("#8a7449", "#b9a273"), ("#76663f", "#a3915f"), ("#6d6a3e", "#9a9363"),
        ("#5d5a35", "#8a8455"), ("#7f6a4a", "#a99070"), ("#93804f", "#c2ad7e"),
        ("#5f5649", "#8a7f6c"), ("#585e36", "#79804c"), ("#6a5137", "#8d6c4a"), ("#4e4a3c", "#6e6857")]
    stems = [(hexlin(a), hexlin(b)) for a, b in stems]
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "h": 0, "a": 0}, ss=2)
    # tussock centres: blades radiate from them
    tus = rng.random((60, 2)) * n
    nb = 16000
    order = 0
    for i in range(nb):
        if rng.random() < 0.45:
            c = tus[rng.integers(len(tus))]
            x, y = c + rng.normal(0, 14, 2)
            base_ang = None
        else:
            x, y = rng.uniform(0, n, 2)
            base_ang = None
        if density[int(y) % n, int(x) % n] < rng.uniform(0.0, 0.55):
            continue
        fd = flatten_dir[int(y) % n, int(x) % n]
        if rng.random() < 0.55:
            ang = fd + rng.normal(0, 0.45)
        else:
            ang = rng.uniform(0, TAU)
        L = rng.uniform(0.06, 0.28) * ppm
        m = max(4, int(L / 5))
        curv = rng.normal(0, 0.012)
        pts = [np.array([x, y])]
        a = ang
        for j in range(m - 1):
            a += curv * 5 + rng.normal(0, 0.03)
            pts.append(pts[-1] + (L / (m - 1)) * np.array([np.cos(a), np.sin(a)]))
        w0 = rng.uniform(0.004, 0.008) * ppm
        widths = w0 * np.clip(1.0 - np.linspace(0, 1, m) ** 1.6, 0.12, 1)
        c0, c1 = stems[rng.integers(len(stems))]
        bright = np.exp(rng.normal(0, 0.15))
        order += 1
        z = order / nb
        lift = rng.uniform(0.002, 0.012)

        def vals(si, t, c0=c0, c1=c1, bright=bright, z=z, lift=lift):
            cc = (c0 + (c1 - c0) * min(1, t * 1.4)) * bright * (0.75 + 0.25 * min(1, t * 3))
            return {"r": cc[0], "g": cc[1], "b": cc[2], "h": 0.004 + z * 0.01 + lift * np.sin(np.pi * t), "a": 1.0}
        sc.ribbon(np.array(pts), widths, vals)
        # midrib (thin brighter ridge for blade cross-curvature)
        if w0 > 1.6:
            sc.ribbon(np.array(pts), widths * 0.35, lambda si, t, v_=vals: {
                "h": v_(si, t)["h"] + 0.0012})
    # a few broad dead leaves (dock/plantain) lying flat
    for i in range(70):
        x, y = rng.uniform(0, n, 2)
        L = rng.uniform(0.05, 0.12) * ppm
        ang = rng.uniform(0, TAU)
        t = np.linspace(0, 1, 9)
        cl = np.stack([x + np.cos(ang) * L * t, y + np.sin(ang) * L * t], 1)
        widths = np.sin(np.pi * np.clip(t, 0.02, 0.98)) ** 0.8 * L * rng.uniform(0.3, 0.45)
        lc = hexlin(["#5a4630", "#6e5434", "#4d3d2b", "#7a6440"][rng.integers(4)]) * np.exp(rng.normal(0, 0.12))
        sc.ribbon(cl, widths, lambda si, tt, lc=lc: {"r": lc[0], "g": lc[1], "b": lc[2], "h": 0.003, "a": 1.0})
    a = np.clip(sc.get("a"), 0, 1)
    gcol = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1) / np.maximum(a[..., None], 1e-3)
    gh = sc.get("h") / np.maximum(a, 1e-3)
    h = h0 + gh * a
    col = mix(mud, gcol, a)
    # self-shadow of the thatch: lower blades darker
    shadow = np.clip(gh * a / 0.014, 0, 1)
    col = col * (0.6 + 0.4 * shadow + 0.0 * a)[..., None] * (0.85 + 0.15 * (1 - a))[..., None]
    rough = mix(np.full((n, n), 0.55, np.float32), 0.75 + 0.1 * spectral(rng, beta=2, fmin=30), a)
    # wet patches of mud show through, glossy
    rough = rough - 0.15 * (1 - a) * smoothstep(0.4, 0.9, norm01(spectral(rng, beta=3, fmin=3)))
    rough = np.clip(rough, 0.3, 0.92)
    return Material(name, tile_m, col, h, rough, normal_strength=0.8, ao_radii_m=(0.003, 0.01, 0.03),
                    ao_strength=1.2)


def stone_rubble(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    h = spectral(rng, beta=3.3, fmin=1) * 0.05 + spectral(rng, beta=2.2, fmin=12, fmax=300) * 0.0015
    dust = hexlin("#8a8378")
    col = ramp(norm01(spectral(rng, beta=2.5, fmin=3)), [(0, "#5d554b"), (0.5, "#71685c"), (1, "#878071")])
    rough = np.full((n, n), 0.88, np.float32)
    layers = [dict(npts=60, keep=0.6, gap=(0.06, 0.4), lift=(0.15, 0.5), tilt=0.9),
              dict(npts=380, keep=0.65, gap=(0.06, 0.4), lift=(0.2, 0.6), tilt=0.9),
              dict(npts=2400, keep=0.6, gap=(0.08, 0.45), lift=(0.3, 0.7), tex=0.08),
              dict(npts=14000, keep=0.5, gap=(0.1, 0.5), lift=(0.3, 0.8), tex=0.1)]
    kf = 0.4 + 1.1 * norm01(spectral(rng, beta=3.2, fmin=2))
    h, win, infos = _chunk_stack(rng, h, tile_m, layers, keep_field=kf)
    # material classes: 0 brick, 1 limestone, 2 mortar, 3 roof tile, 4 plaster
    probs = np.array([0.42, 0.18, 0.24, 0.07, 0.09])
    cols = {0: [("#6f4535"), ("#7d4d3a"), ("#64402f"), ("#875a44")], 1: ["#a99f89", "#b6ad97", "#9b917d"],
            2: ["#958f84", "#a29c91", "#8a8479"], 3: ["#8e5a42", "#7f4f3a"], 4: ["#b8b2a5", "#c4beb2"]}
    grain = norm01(spectral(rng, beta=1.4, fmin=80))
    for li, ch in enumerate(infos):
        sel = (win == li)
        npt = len(ch["pts"])
        cls = rng.choice(5, npt, p=probs)
        base = np.zeros((npt, 3), np.float32)
        for i in range(npt):
            opts = cols[cls[i]]
            base[i] = hexlin(opts[rng.integers(len(opts))]) * np.exp(rng.normal(0, 0.08))
        ccol = base[ch["cid"]]
        c = cls[ch["cid"]]
        ccol = ccol * (0.9 + 0.2 * grain)[..., None]
        prof = np.clip(ch["ins"] / (0.35 * ch["r"]), 0, 1)
        # mortar crusts on bricks, dust in low edges
        crust = (c == 0) * smoothstep(0.6, 0.8, norm01(blur(rng.standard_normal((n, n)).astype(np.float32), 3)))
        ccol = mix(ccol, hexlin("#9f998d"), crust * 0.8)
        ccol = mix(ccol, dust, np.clip(1 - prof * 1.4, 0, 1) * 0.5)
        col = np.where(sel[..., None], ccol, col)
        rough = np.where(sel, np.where(c == 3, 0.7, 0.86), rough)
    rel = h - blur(h, 0.05 * ppm)
    crev = smoothstep(0.0, -0.02, rel)
    col = mix(col, dust * 0.95, crev * 0.5)
    film = smoothstep(0.2, 0.9, norm01(spectral(rng, beta=2.4, fmin=6)))
    col = mix(col, dust * 1.05, film * 0.3)
    col = col * (1 + 0.08 * np.clip(rel / 0.015, -1, 1))[..., None]
    rough = np.clip(rough + 0.06 * crev + 0.03 * spectral(rng, beta=2, fmin=20), 0.5, 0.97)
    return Material(name, tile_m, col, h, rough, normal_strength=1.0, ao_radii_m=(0.005, 0.02, 0.07),
                    ao_strength=1.2)


SETS = {
    "mud_wet": (mud_wet, 2.0, "Churned Somme trench-floor mud (brown-grey clay), boot prints, ruts along U, "
                              "flint/chalk stones; puddles = roughness ~0.07 areas."),
    "earth_wall": (earth_wall, 2.0, "Spade-cut trench wall, V = up: layered loam/clay strata (periodic over the "
                                    "tile), chalk flecks, flints, roots, spade facets, damp seeps."),
    "chalk_spoil": (chalk_spoil, 2.0, "Somme chalk spoil: angular white-grey chalk lumps, flints, brown earth "
                                      "matrix and chalk fines; parapets / spoil heaps."),
    "grass_dead": (grass_dead, 3.0, "Matted dead autumn grass, tussocks and fallen leaves over wet mud "
                                    "(behind-the-lines ground)."),
    "stone_rubble": (stone_rubble, 2.0, "Shattered masonry rubble: brick, limestone, mortar and tile fragments "
                                        "in plaster/brick dust."),
}
