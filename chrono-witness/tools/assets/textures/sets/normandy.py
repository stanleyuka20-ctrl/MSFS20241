"""Normandy, June 1944 (bocage farm hamlet)."""
from __future__ import annotations

import cv2
import numpy as np

from lib.core import (N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral, stamp,
                      uv, warp)
from lib.elements import scatter_stones, voronoi_chunks
from lib.pbr import Material
from lib.strokes import StrokeCanvas, crack_lines
from lib.wood import periodic_grain
from sets.blitz import courses, unit_sdf


def _vimg(n):
    return ((np.arange(n, dtype=np.float32) + 0.5) / n)[:, None] * np.ones((1, n), np.float32)


def _uimg(n):
    return ((np.arange(n, dtype=np.float32) + 0.5) / n)[None, :] * np.ones((n, 1), np.float32)


def _lichen(rng, n, count, r_mu=1.8):
    lich = np.zeros((n, n), np.float32)
    for i in range(count):
        x, y = rng.uniform(0, n, 2)
        r = np.exp(rng.normal(r_mu, 0.5))
        R = int(r * 1.8) + 3
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        nz = cv2.GaussianBlur(rng.standard_normal(xx.shape).astype(np.float32), (0, 0), max(1.0, r * 0.25))
        nz /= nz.std() + 1e-6
        dd = np.sqrt(xx ** 2 + yy ** 2) / r + 0.25 * nz
        stamp(lich, smoothstep(1.0, 0.7, dd).astype(np.float32), x, y, mode="max")
    return blur(lich, 0.8)


# --------------------------------------------------------------------------- rubble wall
def norman_stone_rubble_wall(name, tile_m):
    """Random rubble masonry: grey-brown granite blocks and darker schist slabs, small pinning stones,
    recessed lime mortar, lichen; stones bedded roughly horizontally."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    big = voronoi_chunks(rng, 130, n=n, gap=(0.1, 0.22), bevel=0.8, tilt=0.6, crease=0.4, jitter=0.7,
                         aspect=(0.55, 1.0), warp_px=4)
    small = voronoi_chunks(rng, 1400, n=n, gap=(0.15, 0.35), bevel=0.6, tilt=0.5, keep=0.3, jitter=0.85,
                           aspect=(0.6, 1.0), warp_px=2)
    rb, rs = big["r"] * tile_m, small["r"] * tile_m
    hb = big["h"] * rb * 0.55 + spectral(rng, beta=1.8, fmin=40) * 0.0008
    hs = small["h"] * rs * 0.45 - 0.006
    mort_h = -0.016 + spectral(rng, beta=1.6, fmin=60) * 0.001
    fill = small["mask"] * (1 - big["mask"])
    h = mort_h + (hs - mort_h) * fill
    h = h * (1 - big["mask"]) + hb * big["mask"]
    nb = len(big["pts"])
    nsm = len(small["pts"])
    kinds = ["#6e665c", "#7a7066", "#5f574e", "#756b60", "#4d4943", "#56514a", "#63594f", "#7a6650", "#4a4037",
             "#86807a"]
    bc = np.array([hexlin(kinds[i]) for i in rng.integers(len(kinds), size=nb)], np.float32)
    bc *= np.exp(rng.normal(0, 0.08, (nb, 1)))
    sc_ = np.array([hexlin(kinds[i]) for i in rng.integers(len(kinds), size=nsm)], np.float32)
    schist = (rng.random(nb) < 0.35)[big["cid"]]
    lam = norm01(spectral(rng, beta=1.6, fmin=20, stretch=(4.0, 1.0)))   # schist laminations (horizontal)
    speck = smoothstep(1.5, 2.3, spectral(rng, beta=0.3, fmin=200))      # granite crystals
    bcol = bc[big["cid"]] * np.where(schist, 0.85 + 0.25 * lam, 0.92 + 0.1 * norm01(spectral(rng, beta=1.4, fmin=60)))[..., None]
    bcol = mix(bcol, hexlin("#2e2c2a"), speck * (~schist) * 0.5)
    scol = sc_[small["cid"]] * (0.9 + 0.15 * lam)[..., None]
    mort = ramp(norm01(spectral(rng, beta=2.2, fmin=8)), [(0, "#a39880"), (0.5, "#b3a88f"), (1, "#c0b59c")])
    mort = mort * (0.92 + 0.12 * norm01(spectral(rng, beta=1.2, fmin=90)))[..., None]
    col = mix(mort, scol, fill)
    col = mix(col, bcol, big["mask"])
    prof = np.clip(big["ins"] / (0.5 * big["r"]), 0, 1)
    col = mix(col, mort * 0.9, np.clip(1 - prof * 3, 0, 1) * 0.35 * big["mask"])   # mortar smears on edges
    lich = _lichen(rng, n, 140)
    lc = mix(hexlin("#a5a395"), hexlin("#a8933e"), smoothstep(0.65, 0.8, norm01(spectral(rng, beta=2, fmin=5))))
    col = mix(col, lc, lich * 0.6 * big["mask"])
    moss = smoothstep(0.7, 0.8, norm01(spectral(rng, beta=2.5, fmin=3))) * (1 - big["mask"])
    col = mix(col, hexlin("#3e4527"), moss * 0.7)
    grime = smoothstep(0.5, 0.9, norm01(spectral(rng, beta=2.6, fmin=2)))
    col = col * (1 - 0.15 * grime[..., None])
    rough = mix(0.92, 0.8, big["mask"]) + 0.08 * lich + 0.05 * moss
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.004, 0.015, 0.05),
                    ao_strength=1.2)


# --------------------------------------------------------------------------- limestone ashlar
def limestone_ashlar(name, tile_m):
    """Pale Caen-type limestone ashlar, 6 courses of 0.33 m, fine joints; weathered faces with alveolar
    pitting, claw-tool marks, black crust patches, orange and grey lichen."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows = 6
    lens = []
    for r in range(rows):
        ls = rng.uniform(0.5, 0.9, 8) * ppm
        k = int(np.searchsorted(np.cumsum(ls), n))
        ls = ls[:k + 1]
        lens.append(ls / ls.sum() * n)
    L = courses(n, rows, lens, [rng.uniform(0, n) for _ in range(rows)])
    cnt, sid = L["count"], L["sid"]
    sdf = unit_sdf(rng, L, 0.006 * ppm, chip=1.2, jitter=1.0)
    inb = smoothstep(-0.5, 1.0, sdf)
    arris = np.sqrt(np.clip(sdf / 8.0, 0, 1))
    claw = bandnoise(rng, f=110, width=0.3, stretch=(1.0, 0.12), angle=0.9) * \
        (0.4 + 0.6 * norm01(spectral(rng, beta=2.5, fmin=4)))
    alv_f = norm01(spectral(rng, beta=2.6, fmin=3))
    alv = smoothstep(0.62, 0.8, alv_f) * smoothstep(1.0, 1.8, spectral(rng, beta=0.6, fmin=90))
    h = (0.004 * arris + rng.normal(0, 0.0015, cnt)[sid] + claw * 0.00012 - alv * 0.003 +
         spectral(rng, beta=1.6, fmin=60) * 0.0001) * inb - 0.003 * (1 - inb)
    tones = ["#c9bd9c", "#d1c6a7", "#bfb291", "#c4b99d", "#cbbfa2", "#b8ab8c"]
    bc = np.array([hexlin(tones[i]) for i in rng.integers(len(tones), size=cnt)], np.float32)
    bc *= np.exp(rng.normal(0, 0.04, (cnt, 1)))
    col = bc[sid] * (0.93 + 0.1 * norm01(spectral(rng, beta=2.0, fmin=8)))[..., None]
    col = mix(col, col * 0.75, alv)
    crust = blur(smoothstep(0.66, 0.85, norm01(spectral(rng, beta=2.8, fmin=2, stretch=(0.5, 1.0)))), 2.0)
    col = mix(col, hexlin("#77736a"), crust * 0.55)
    algae = smoothstep(0.6, 0.95, norm01(blur(spectral(rng, beta=2.4, fmin=3, stretch=(0.2, 1)), 1.2, 8)))
    col = mix(col, hexlin("#7d7f66"), algae * 0.35)
    lich_o = _lichen(rng, n, 50, r_mu=1.4)
    lich_g = _lichen(rng, n, 90, r_mu=1.9)
    col = mix(col, hexlin("#b07a2e"), lich_o * 0.6)
    col = mix(col, hexlin("#a9a898"), lich_g * 0.45)
    mort = hexlin("#b7ad97")
    col = mix(mort * (0.9 + 0.1 * norm01(spectral(rng, beta=1.4, fmin=60)))[..., None], col, inb)
    rough = 0.85 + 0.05 * alv - 0.05 * crust + 0.05 * lich_g
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.002, 0.008, 0.03),
                    ao_strength=0.9)


# --------------------------------------------------------------------------- cob / torchis
def cob_torchis(name, tile_m):
    """Earth-and-straw cob infill (torchis), ochre-brown, hand-smoothed, shrinkage cracks, straw showing."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    lumps = voronoi_chunks(rng, 900, n=n, gap=(0.0, 0.05), bevel=0.8, tilt=0.4, jitter=0.9, warp_px=6)["h"]
    h = spectral(rng, beta=3.0, fmin=2, fmax=60) * 0.004 + spectral(rng, beta=1.8, fmin=40) * 0.0003 + \
        blur(lumps, 2.0) * 0.002
    clay = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#6e5840"), (0.5, "#7e6648"), (1, "#8c7454")])
    col = clay * (0.92 + 0.12 * norm01(spectral(rng, beta=1.6, fmin=40)))[..., None]
    rough = np.full((n, n), 0.9, np.float32)
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "a": 0, "h": 0}, ss=2)
    straws = [hexlin(c) for c in ("#a88f5e", "#9a8152", "#b59c6a", "#8a7650", "#7d6b4c")]
    for i in range(2600):
        x, y = rng.uniform(0, n, 2)
        L = rng.uniform(0.015, 0.07) * ppm
        a = rng.uniform(0, TAU)
        bend = rng.normal(0, 0.15)
        pts = []
        p = np.array([x, y])
        for j in range(5):
            pts.append(p.copy())
            a += bend
            p = p + L / 4 * np.array([np.cos(a), np.sin(a)])
        c = straws[rng.integers(len(straws))] * np.exp(rng.normal(0, 0.1))
        vis = rng.uniform(0.35, 1.0)
        wd = rng.uniform(0.0012, 0.003) * ppm
        sc.ribbon(np.array(pts), np.full(5, wd), lambda si, t, c=c, vis=vis: dict(r=c[0], g=c[1], b=c[2], a=vis,
                                                                                    h=vis))
    a = np.clip(sc.get("a"), 0, 1)
    scol = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1) / np.maximum(a[..., None], 1e-3)
    col = mix(col, scol, a)
    h = h + sc.get("h") * 0.0006
    crk = 1 - voronoi_chunks(rng, 260, n=n, gap=(0.01, 0.03), bevel=0.05, tilt=0, jitter=0.85, warp_px=8)["mask"]
    crk *= smoothstep(0.35, 0.7, norm01(spectral(rng, beta=2.4, fmin=2)))
    h -= crk * 0.004
    col = mix(col, hexlin("#3e2f20"), crk * 0.8)
    scatter_stones(rng, h, col, 120, (1.5, 6), [hexlin("#8a8176"), hexlin("#6e6458"), hexlin("#a39a8c")],
                   embed=(0.4, 0.8), h_scale_m=0.006, angular=0.5, rough_map=rough, rough_val=0.8)
    wash = smoothstep(0.7, 0.74, norm01(spectral(rng, beta=3.0, fmin=2))) * \
        smoothstep(0.3, 0.6, norm01(spectral(rng, beta=1.8, fmin=30)))          # old limewash remnants
    col = mix(col, hexlin("#b9b1a0"), wash * 0.6)
    h = h + wash * 0.0003
    rough = rough - 0.05 * wash
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.002, 0.008, 0.03),
                    ao_strength=1.0)


# --------------------------------------------------------------------------- oak frame
def timber_frame_oak(name, tile_m):
    """Weathered grey oak colombage beams: eroded grain (along U), deep checks, oak pegs, lichen."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    G = periodic_grain(rng, ring_px=12, wander=40, knots=3, knot_r=(10, 22), stretch=7, latewood=0.35)
    late, fib = G["late"], G["fibre"]
    adze = bandnoise(rng, f=14, width=0.4, stretch=(0.25, 1.0)) * 0.2
    checks = crack_lines(rng, n, 10, length_px=(120, 500), width_px=(1.5, 4.0), wobble=0.012, branch=0.0,
                         angle=0.0, angle_jitter=0.01)
    h = late * 0.0008 + fib * 0.00008 + adze * 0.0015 - checks * 0.008 + G["knot"] * 0.0005 + \
        spectral(rng, beta=3.2, fmin=1, fmax=8) * 0.002
    pegs = np.zeros((n, n), np.float32)
    for (px, py) in ((0.22, 0.3), (0.73, 0.68)):
        x, y = px * n + rng.normal(0, 5), py * n + rng.normal(0, 5)
        r = 0.0125 * ppm
        R = int(r * 1.6) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        d = np.sqrt(xx ** 2 + yy ** 2)
        m = smoothstep(r + 0.6, r - 0.6, d)
        stamp(pegs, m.astype(np.float32), x, y, mode="max")
        stamp(h, (m * (0.002 + 0.0006 * np.cos(d / r * TAU * 3)) - smoothstep(r + 2.5, r, d) * (1 - m) * 0.003)
              .astype(np.float32), x, y, mode="add")
    base = mix(hexlin("#878074"), hexlin("#6a6358"), np.clip(late, 0, 1))
    base = base * (1 + 0.06 * fib[..., None])
    groove = smoothstep(0.3, 0.0, late)
    base = mix(base, hexlin("#5a4c3e"), groove * 0.35)
    base = mix(base, hexlin("#3a3028"), G["knot"] * 0.6)
    base = mix(base, hexlin("#2e261f"), np.clip(checks * 1.2, 0, 1))
    base = mix(base, hexlin("#6e5e4a"), pegs * 0.7)
    brown = smoothstep(0.6, 0.9, norm01(spectral(rng, beta=2.5, fmin=2)))
    base = mix(base, hexlin("#6e5b46"), brown * 0.35)
    lich = _lichen(rng, n, 60, r_mu=1.5)
    base = mix(base, hexlin("#9da08a"), lich * 0.5)
    rough = 0.8 + 0.06 * groove + 0.08 * checks
    return Material(name, tile_m, base, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.002, 0.008, 0.025),
                    ao_strength=1.0)


# --------------------------------------------------------------------------- thatch
def thatch_roof(name, tile_m):
    """Weathered straw thatch; V points up the roof, stalk butts face down-slope (towards the image bottom)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "a": 0, "h": 0}, ss=2)
    pal = [hexlin(c) for c in ("#6e6352", "#7a6d58", "#857559", "#5f5647", "#8c7a5a", "#9c8458", "#6a6150")]
    count = 15000
    ys = np.sort(rng.uniform(0, n, count))[::-1]          # draw from the bottom up: upper straws lie on top
    sway = spectral(rng, beta=3.0, fmin=2) * 0.18
    for i in range(count):
        y = ys[i]
        x = rng.uniform(0, n)
        L = rng.uniform(0.06, 0.15) * ppm
        a = np.pi / 2 + sway[int(y) % n, int(x) % n] + rng.normal(0, 0.12)
        m = 4
        pts = np.array([[x + np.cos(a) * L * t, y - L + np.sin(a) * L * t] for t in np.linspace(0, 1, m)])
        c = pal[rng.integers(len(pal))] * np.exp(rng.normal(0, 0.1))
        wd = rng.uniform(0.002, 0.0045) * ppm
        z = i / count

        def vals(si, t, c=c, z=z):
            shade = 0.7 + 0.3 * t       # butt end catches light, upper part shadowed by the course above
            return dict(r=c[0] * shade, g=c[1] * shade, b=c[2] * shade, a=1.0, h=z * 0.3 + t)
        sc.ribbon(pts, np.full(m, wd), vals)
    a = np.clip(sc.get("a"), 0, 1)
    col = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1) / np.maximum(a[..., None], 1e-3)
    col = mix(hexlin("#2e2820"), col, a)
    hh = sc.get("h") / np.maximum(a, 1e-3)
    h = hh * 0.004 * a + spectral(rng, beta=3.0, fmin=2, fmax=20) * 0.008
    # courses: faint horizontal steps every ~25 cm
    vi = _vimg(n)
    course = ((vi * tile_m / 0.25) % 1.0)
    h += blur(smoothstep(0.0, 0.9, course) * smoothstep(1.0, 0.92, course), 0.1, 6.0) * 0.004
    moss = smoothstep(0.68, 0.78, norm01(spectral(rng, beta=2.6, fmin=3)))
    col = mix(col, ramp(norm01(spectral(rng, beta=1.8, fmin=30)), [(0, "#2f331f"), (1, "#4d5130")]), moss * 0.8)
    damp = smoothstep(0.5, 0.9, norm01(spectral(rng, beta=2.8, fmin=2)))
    col = col * (1 - 0.25 * damp[..., None])
    rough = 0.86 + 0.08 * moss - 0.06 * damp
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.98), normal_strength=0.8,
                    ao_radii_m=(0.003, 0.01, 0.03), ao_strength=1.2)


# --------------------------------------------------------------------------- summer grass
def grass_summer(name, tile_m):
    """Lush June meadow grass seen from above, clover and a few bare patches."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    h0 = spectral(rng, beta=3.4, fmin=1) * 0.02
    soil = ramp(norm01(spectral(rng, beta=2.6, fmin=3)), [(0, "#3b3125"), (1, "#54452f")])
    bare = smoothstep(0.78, 0.86, norm01(spectral(rng, beta=2.8, fmin=2)))
    dirflow = spectral(rng, beta=3.6, fmin=1) * 1.0 + rng.uniform(0, TAU)
    greens = [("#2f4a1c", "#5f8a35"), ("#35501f", "#6a9440"), ("#3a5222", "#7a9a48"), ("#2c4419", "#557c2e"),
              ("#45562a", "#8a9a55"), ("#4a5a2e", "#9aa060")]
    greens = [(hexlin(a), hexlin(b)) for a, b in greens]
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "h": 0, "a": 0}, ss=2)
    nb = 22000
    for i in range(nb):
        x, y = rng.uniform(0, n, 2)
        if bare[int(y), int(x)] > rng.uniform(0.2, 1.0):
            continue
        fd = dirflow[int(y), int(x)]
        ang = fd + rng.normal(0, 0.7) if rng.random() < 0.5 else rng.uniform(0, TAU)
        L = rng.uniform(0.02, 0.1) * ppm       # foreshortened (blades stand up)
        m = 4
        curv = rng.normal(0, 0.1)
        pts = [np.array([x, y])]
        a = ang
        for j in range(m - 1):
            a += curv
            pts.append(pts[-1] + L / (m - 1) * np.array([np.cos(a), np.sin(a)]))
        c0, c1 = greens[rng.integers(len(greens))]
        br = np.exp(rng.normal(0, 0.12))
        z = i / nb
        w0 = rng.uniform(0.0025, 0.006) * ppm
        sc.ribbon(np.array(pts), w0 * np.array([1, 0.85, 0.6, 0.2]),
                  lambda si, t, c0=c0, c1=c1, br=br, z=z: dict(
                      r=(c0[0] + (c1[0] - c0[0]) * t) * br, g=(c0[1] + (c1[1] - c0[1]) * t) * br,
                      b=(c0[2] + (c1[2] - c0[2]) * t) * br, h=0.3 + 0.7 * z + 0.5 * t, a=1.0))
    # clover: trefoils and white flower heads
    def disc(cx, cy, r, m=10):
        t = np.linspace(0, TAU, m, endpoint=False)
        return np.stack([cx + r * np.cos(t), cy + r * np.sin(t)], 1)
    clover_f = smoothstep(0.55, 0.75, norm01(spectral(rng, beta=2.6, fmin=4)))
    for i in range(2500):
        x, y = rng.uniform(0, n, 2)
        if clover_f[int(y), int(x)] < rng.random():
            continue
        r = rng.uniform(0.004, 0.007) * ppm
        a0 = rng.uniform(0, TAU)
        c = hexlin("#3e6a2a") * np.exp(rng.normal(0, 0.1))
        for k in range(3):
            a = a0 + k * TAU / 3
            sc.polygon(disc(x + np.cos(a) * r, y + np.sin(a) * r, r), dict(r=c[0], g=c[1], b=c[2], h=1.2, a=1.0))
        if rng.random() < 0.12:
            fc = hexlin("#cfcabd") if rng.random() < 0.8 else hexlin("#b8949a")
            sc.polygon(disc(x + r * 2, y, r * 1.6, 12), dict(r=fc[0], g=fc[1], b=fc[2], h=1.6, a=1.0))
    a = np.clip(sc.get("a"), 0, 1)
    gcol = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1) / np.maximum(a[..., None], 1e-3)
    gh = sc.get("h") / np.maximum(a, 1e-3)
    col = mix(soil, gcol, a)
    col = col * (0.62 + 0.38 * np.clip(gh * a / 1.6, 0, 1))[..., None]
    h = h0 + gh * a * 0.006
    rough = mix(0.85, 0.62 + 0.1 * norm01(spectral(rng, beta=1.6, fmin=40)), a)
    return Material(name, tile_m, col, h, np.clip(rough, 0.4, 0.95), normal_strength=0.8,
                    ao_radii_m=(0.003, 0.01, 0.03), ao_strength=1.1)


# --------------------------------------------------------------------------- dirt lane
def _hoof(rng, ppm, horse):
    S = int(0.16 * ppm) + 4
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) - S / 2
    xm, ym = xx / ppm, yy / ppm
    if horse:      # horseshoe: crescent ring open at the heel
        r = np.sqrt(xm ** 2 + (ym * 1.1) ** 2)
        ring = smoothstep(0.012, 0.004, np.abs(r - 0.05))
        open_ = smoothstep(0.01, -0.02, ym)  # open towards +y (heel)
        frog = smoothstep(0.035, 0.02, r) * 0.6
        return -(ring * open_ * 0.012 + frog * 0.008 + smoothstep(0.065, 0.045, r) * 0.004)
    # cattle: two kidney-shaped claws
    out = np.zeros_like(xm)
    for s in (-1, 1):
        dx = xm - s * 0.022
        d = np.sqrt((dx / 0.018) ** 2 + (ym / 0.04) ** 2)
        out += smoothstep(1.0, 0.7, d)
    return -out * 0.01


def dirt_lane(name, tile_m):
    """Dry rutted farm lane running along V: compacted earth, hoof prints, wheel ruts at U≈0.27/0.73,
    grass strip down the middle at U≈0.5. Map U across the lane (3 m)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    ui = _uimg(n)
    wob = spectral(rng, beta=3.4, fmin=1, stretch=(1.0, 4.0)) * 0.012
    h = spectral(rng, beta=3.2, fmin=1) * 0.012 + spectral(rng, beta=2.2, fmin=10, fmax=200) * 0.0012
    crown = np.zeros((n, n), np.float32)
    for c in (0.27, 0.73):
        d = (ui - c + wob) * tile_m
        h += -0.05 * np.exp(-(d / 0.14) ** 2) + 0.015 * np.exp(-((np.abs(d) - 0.2) / 0.06) ** 2)
        crown = np.maximum(crown, np.exp(-(d / 0.12) ** 2))
    strip_d = np.abs(ui - 0.5 + wob * 0.5) * tile_m
    strip = smoothstep(0.2, 0.14, strip_d + spectral(rng, beta=2.4, fmin=8) * 0.025)
    h += strip * 0.02
    for i in range(70):
        x = (rng.choice([0.27, 0.73, 0.4, 0.6]) + rng.normal(0, 0.06)) * n
        y = rng.uniform(0, n)
        horse = rng.random() < 0.5
        spr = _hoof(rng, ppm, horse)
        spr = cv2.GaussianBlur(spr.astype(np.float32), (0, 0), rng.uniform(0.6, 2.0))
        from lib.elements import rotate_sprite
        spr = rotate_sprite(spr, rng.normal(0, 25) + (180 if rng.random() < 0.5 else 0))
        stamp(h, spr.astype(np.float32), x, y, mode="add")
    soil = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#6f5a42"), (0.5, "#836b4f"), (1, "#957d5f")])
    rel = h - blur(h, 0.05 * ppm)
    col = soil * (1 + 0.15 * np.clip(rel / 0.01, -1, 1))[..., None]
    col = mix(col, hexlin("#5a4936"), crown * 0.35)
    cracks = (1 - voronoi_chunks(rng, 1500, n=n, gap=(0.02, 0.05), bevel=0.05, tilt=0, jitter=0.85, warp_px=3)["mask"])
    cracks *= crown * smoothstep(0.4, 0.7, norm01(spectral(rng, beta=2.4, fmin=3)))
    h -= cracks * 0.003
    col = mix(col, hexlin("#3a2e22"), cracks * 0.7)
    rough = np.full((n, n), 0.9, np.float32)
    scatter_stones(rng, h, col, 500, (1.5, 7), [hexlin("#8a8176"), hexlin("#6e6458"), hexlin("#a39a8c"),
                                                 hexlin("#5a554f")], embed=(0.3, 0.75), h_scale_m=0.008,
                   angular=0.5, rough_map=rough, rough_val=0.8, avoid=strip)
    dust = smoothstep(0.4, 0.85, norm01(spectral(rng, beta=2.4, fmin=3)))
    col = mix(col, hexlin("#a08e74"), dust * 0.3 * (1 - crown))
    # grass strip: blades over the crown
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "a": 0}, ss=2)
    gpal = [(hexlin(a), hexlin(b)) for a, b in (("#3a5222", "#7a9a48"), ("#45562a", "#8a9a55"), ("#5a5a30", "#a09a60"),
                                                ("#2f4a1c", "#5f8a35"))]
    for i in range(9000):
        x = (0.5 + rng.normal(0, 0.045)) * n
        y = rng.uniform(0, n)
        if strip[int(y) % n, int(x) % n] < rng.uniform(0.1, 0.9):
            continue
        a = rng.uniform(0, TAU)
        L = rng.uniform(0.02, 0.09) * ppm
        pts = np.array([[x + np.cos(a) * L * t, y + np.sin(a) * L * t] for t in np.linspace(0, 1, 4)])
        c0, c1 = gpal[rng.integers(len(gpal))]
        sc.ribbon(pts, rng.uniform(0.003, 0.006) * ppm * np.array([1, 0.8, 0.5, 0.2]),
                  lambda si, t, c0=c0, c1=c1: dict(r=c0[0] + (c1[0] - c0[0]) * t, g=c0[1] + (c1[1] - c0[1]) * t,
                                                   b=c0[2] + (c1[2] - c0[2]) * t, a=1.0))
    ga = np.clip(sc.get("a"), 0, 1)
    gcol = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1) / np.maximum(ga[..., None], 1e-3)
    col = mix(col, gcol, ga)
    h = h + ga * 0.004
    rough = mix(rough, 0.65, ga)
    return Material(name, tile_m, col, h, np.clip(rough, 0.5, 0.97), ao_radii_m=(0.004, 0.015, 0.05),
                    ao_strength=1.0)


# --------------------------------------------------------------------------- hedgerow bank
def hedgerow_bank(name, tile_m):
    """Bocage earth bank (vertical, V up): soil with roots, stones, ferns, ivy and grass tufts."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    h = spectral(rng, beta=3.2, fmin=1) * 0.03 + spectral(rng, beta=2.4, fmin=8, fmax=250) * 0.002
    soil = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#3d3023"), (0.5, "#4f3e2c"), (1, "#5e4b36")])
    col = soil * (0.9 + 0.15 * norm01(spectral(rng, beta=1.6, fmin=40)))[..., None]
    rough = np.full((n, n), 0.85, np.float32)
    scatter_stones(rng, h, col, 90, (3, 14), [hexlin("#7e766c"), hexlin("#5d5953"), hexlin("#8a8076")],
                   embed=(0.3, 0.7), h_scale_m=0.02, angular=0.5, rough_map=rough, rough_val=0.8)
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "a": 0, "h": 0, "rg": 0}, ss=2)

    def C(c, hh, rg):
        return dict(r=c[0], g=c[1], b=c[2], a=1.0, h=hh, rg=rg)
    # roots
    for i in range(30):
        x, y = rng.uniform(0, n, 2)
        a = np.pi / 2 + rng.normal(0, 0.6)
        pts = [np.array([x, y])]
        for j in range(int(rng.integers(10, 40))):
            a += rng.normal(0, 0.25)
            pts.append(pts[-1] + 5 * np.array([np.cos(a), np.sin(a)]))
        c = hexlin(rng.choice(["#5a4632", "#6e5a44", "#3e3022"]))
        sc.ribbon(np.array(pts), np.linspace(rng.uniform(2, 6), 0.8, len(pts)), lambda si, t, c=c: C(c, 0.4, 0.7))
    # grass tufts
    for i in range(3500):
        x, y = rng.uniform(0, n, 2)
        a = -np.pi / 2 + rng.normal(0, 0.5)    # blades grow upwards (V up)
        L = rng.uniform(0.03, 0.12) * ppm
        pts = np.array([[x + np.cos(a) * L * t, y + np.sin(a) * L * t] for t in np.linspace(0, 1, 4)])
        c = hexlin(rng.choice(["#4a5f2e", "#5a6a38", "#6e7444", "#857f55"])) * np.exp(rng.normal(0, 0.1))
        sc.ribbon(pts, rng.uniform(1.0, 2.5) * np.array([1, 0.8, 0.5, 0.2]), lambda si, t, c=c: C(c * (0.7 + 0.3 * t),
                                                                                             0.6 + 0.4 * t, 0.7))
    # ferns: rachis with alternating pinnae
    fern_f = norm01(spectral(rng, beta=2.6, fmin=2))
    for i in range(45):
        x, y = rng.uniform(0, n, 2)
        if fern_f[int(y), int(x)] < 0.45:
            continue
        a = -np.pi / 2 + rng.normal(0, 0.6)
        L = rng.uniform(0.2, 0.45) * ppm
        m = 16
        rach = np.array([[x + np.cos(a + 0.3 * t * t) * L * t, y + np.sin(a + 0.3 * t * t) * L * t]
                         for t in np.linspace(0, 1, m)])
        c = hexlin(rng.choice(["#3f5a2c", "#4a6634", "#56703a", "#5e6a38"])) * np.exp(rng.normal(0, 0.08))
        sc.ribbon(rach, np.linspace(3, 1, m), lambda si, t, c=c: C(c * 0.8, 1.0, 0.6))
        for j in range(1, m - 1):
            t = j / (m - 1)
            pl = L * 0.28 * np.sin(np.pi * min(1, t * 1.15)) + 3
            for s in (-1, 1):
                pa = a + 0.3 * t * t + s * 1.2
                p0 = rach[j]
                pin = np.array([p0 + np.array([np.cos(pa), np.sin(pa)]) * pl * q for q in np.linspace(0, 1, 5)])
                sc.ribbon(pin, pl * 0.22 * np.sin(np.pi * np.clip(np.linspace(0.05, 0.95, 5), 0, 1)),
                          lambda si, tt, c=c: C(c * (0.85 + 0.25 * tt), 1.1, 0.6))
    # ivy: stems with glossy lobed leaves
    ivy_f = norm01(spectral(rng, beta=2.6, fmin=2))

    def ivy_leaf(cx, cy, r, ang):
        t = np.linspace(0, TAU, 30, endpoint=False)
        rr = r * (0.5 + 0.5 * np.abs(np.cos(t * 2.5)) ** 0.35)
        return np.stack([cx + rr * np.cos(t + ang), cy + rr * np.sin(t + ang)], 1)
    for i in range(60):
        x, y = rng.uniform(0, n, 2)
        if ivy_f[int(y), int(x)] < 0.5:
            continue
        a = rng.uniform(0, TAU)
        p = np.array([x, y])
        pts = [p]
        for j in range(int(rng.integers(20, 60))):
            a += rng.normal(0, 0.2)
            p = p + 5 * np.array([np.cos(a), np.sin(a)])
            pts.append(p)
            if j % 4 == 0:
                r = rng.uniform(0.025, 0.045) * ppm
                c = hexlin(rng.choice(["#25331f", "#2c3c24", "#33452a", "#3d4f31"])) * np.exp(rng.normal(0, 0.1))
                off = np.array([np.cos(a + 1.5), np.sin(a + 1.5)]) * r * rng.choice([-1, 1])
                sc.polygon(ivy_leaf(*(p + off), r, rng.uniform(0, TAU)), C(c, 1.4, 0.38))
        sc.ribbon(np.array(pts), np.full(len(pts), 1.5), lambda si, t: C(hexlin("#4a3a28"), 1.2, 0.7))
    a = np.clip(sc.get("a"), 0, 1)
    vcol = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1) / np.maximum(a[..., None], 1e-3)
    vh = sc.get("h") / np.maximum(a, 1e-3)
    vr = sc.get("rg") / np.maximum(a, 1e-3)
    col = mix(col, vcol, a)
    col = col * (0.7 + 0.3 * np.clip(vh * a / 1.4 + (1 - a), 0, 1))[..., None]
    h = h + vh * a * 0.006
    rough = mix(rough, vr, a)
    return Material(name, tile_m, col, h, np.clip(rough, 0.3, 0.95), normal_strength=0.9,
                    ao_radii_m=(0.003, 0.012, 0.04), ao_strength=1.2)


# --------------------------------------------------------------------------- apple bark
def orchard_bark(name, tile_m):
    """Gnarled apple-tree bark: scaly plates flaking off (V along the trunk), orange-brown underbark where
    plates have fallen, grey-green lichen and algae, moss in crevices."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    pl = voronoi_chunks(rng, 220, n=n, gap=(0.05, 0.16), bevel=0.4, tilt=0.9, crease=0.3, jitter=0.8,
                        aspect=(1.0, 0.55), warp_px=14)
    small = voronoi_chunks(rng, 2200, n=n, gap=(0.03, 0.1), bevel=0.3, tilt=0.6, jitter=0.85, aspect=(1.0, 0.6),
                           warp_px=4)
    r_m = pl["r"] * tile_m
    burl = spectral(rng, beta=3.6, fmin=1, fmax=8) * 0.02
    flaked = (rng.random(len(pl["pts"])) < 0.1)[pl["cid"]]
    plate_h = pl["h"] * r_m * 0.12 + small["h"] * 0.0015
    h = np.where(pl["mask"] > 0.5, np.where(flaked, -0.002 + small["h"] * 0.0008, plate_h), -0.008)
    h = blur(h.astype(np.float32), 0.7) + burl + spectral(rng, beta=1.6, fmin=60) * 0.0002
    bark = ramp(norm01(spectral(rng, beta=2.2, fmin=6)), [(0, "#4e463d"), (0.5, "#625950"), (1, "#756b60")])
    tone = np.exp(rng.normal(0, 0.08, len(pl["pts"])))[pl["cid"]]
    col = bark * tone[..., None] * (0.9 + 0.15 * norm01(small["h"]))[..., None]
    under = ramp(norm01(spectral(rng, beta=2, fmin=10)), [(0, "#62483a"), (1, "#7a5a44")])
    col = np.where(flaked[..., None] & (pl["mask"] > 0.5)[..., None], under, col)
    crev = 1 - pl["mask"]
    col = mix(col, hexlin("#221b15"), crev * 0.85)
    algae = smoothstep(0.45, 0.85, norm01(spectral(rng, beta=2.4, fmin=3)))
    col = mix(col, hexlin("#5f6a45"), algae * 0.35 * pl["mask"])
    lich = _lichen(rng, n, 80, r_mu=2.2)
    col = mix(col, hexlin("#8f9a80"), lich * 0.55)
    moss = crev * smoothstep(0.6, 0.8, norm01(spectral(rng, beta=2.5, fmin=4)))
    col = mix(col, hexlin("#3a4524"), moss * 0.8)
    rough = 0.85 + 0.08 * crev - 0.1 * flaked * pl["mask"] + 0.05 * lich
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.003, 0.01, 0.03),
                    ao_strength=1.3)


SETS = {
    "norman_stone_rubble_wall": (norman_stone_rubble_wall, 2.0, "Random rubble masonry: grey-brown granite and "
                                                                "schist, small pinning stones, recessed lime mortar, "
                                                                "lichen."),
    "limestone_ashlar": (limestone_ashlar, 2.0, "Pale Caen-type limestone ashlar, 6 courses of 0.33 m, weathered: "
                                                "alveolar pitting, claw marks, black crust, lichen."),
    "cob_torchis": (cob_torchis, 1.0, "Ochre-brown earth-and-straw cob infill, shrinkage cracks, straw and grit, "
                                      "limewash remnants."),
    "timber_frame_oak": (timber_frame_oak, 1.0, "Weathered silver-grey oak beams, eroded grain along U, deep checks, "
                                                "oak pegs, lichen."),
    "thatch_roof": (thatch_roof, 1.0, "Weathered straw thatch, V up the roof (stalk butts face down-slope), moss, "
                                      "faint 25 cm courses."),
    "grass_summer": (grass_summer, 3.0, "Lush June meadow grass with clover and white clover flowers, few bare "
                                        "patches."),
    "dirt_lane": (dirt_lane, 3.0, "Dry rutted farm lane running along V; map U across the lane: wheel ruts at "
                                  "U≈0.27/0.73, grass strip at U≈0.5, hoof prints, stones."),
    "hedgerow_bank": (hedgerow_bank, 2.0, "Bocage earth bank, vertical (V up): soil, roots, stones, ferns, glossy "
                                          "ivy, grass tufts."),
    "orchard_bark": (orchard_bark, 1.0, "Gnarled apple-tree bark, scaly plates flaking to orange-brown underbark, "
                                        "lichen, algae; V along the trunk."),
}
