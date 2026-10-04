"""London Blitz, autumn 1940 (East End terraces): masonry, roofs, streets, interiors, Underground."""
from __future__ import annotations

import numpy as np

from lib.core import (N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral, stamp,
                      uv, warp)
from lib.elements import scatter_stones, voronoi_chunks
from lib.pbr import Material
from lib.strokes import StrokeCanvas, crack_lines
from lib.wood import board_bands, periodic_grain
from sets.ww1_wood import _board_field, _nail


# --------------------------------------------------------------------------- layout helpers
def courses(n, rows, row_lengths, row_offsets, wx=None, wy=None):
    """Generic coursed layout (bricks, flags, slates). row_lengths[r] = unit lengths in px summing to n,
    row_offsets[r] = px shift. Optional warp fields. Returns dict of per-pixel arrays:
    sid (unit id), kind (index within the row pattern), lx, ly (px inside unit), w, h (unit size px), row."""
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    if wx is not None:
        X = (X + wx) % n
        Y = (Y + wy) % n
    rh = n / rows
    r_idx = np.floor(Y / rh).astype(int) % rows
    ly = Y - np.floor(Y / rh) * rh
    sid = np.zeros((n, n), np.int32)
    kind = np.zeros((n, n), np.int32)
    lx = np.zeros((n, n), np.float32)
    w = np.zeros((n, n), np.float32)
    c0 = 0
    for r in range(rows):
        lens = np.asarray(row_lengths[r], np.float64)
        b = np.concatenate([[0], np.cumsum(lens)])
        m = r_idx == r
        xs = (X[m] - row_offsets[r]) % n
        j = np.clip(np.searchsorted(b, xs, side="right") - 1, 0, len(lens) - 1)
        sid[m] = c0 + j
        kind[m] = j
        lx[m] = xs - b[j]
        w[m] = lens[j]
        c0 += len(lens)
    return dict(sid=sid, kind=kind, lx=lx, ly=ly, w=w, h=np.full((n, n), rh, np.float32), row=r_idx, count=c0)


def unit_sdf(rng, L, joint_px, chip=1.0, jitter=1.5):
    """Inside-distance (px) of each unit after removing half the joint, with per-unit size jitter
    and chipped arrises."""
    n = L["sid"].shape[0]
    cnt = L["count"]
    sid = L["sid"]
    j = [rng.uniform(-jitter, jitter, cnt)[sid] for _ in range(4)]
    dx = np.minimum(L["lx"] - joint_px / 2 - j[0], L["w"] - joint_px / 2 - L["lx"] + j[1])
    dy = np.minimum(L["ly"] - joint_px / 2 - j[2], L["h"] - joint_px / 2 - L["ly"] + j[3])
    ero = blur(rng.standard_normal((n, n)).astype(np.float32), 1.5) * 2.0 * chip + \
        np.clip(spectral(rng, beta=2.0, fmin=12) - 0.8, 0, None) * 6.0 * chip
    return np.minimum(dx, dy) - np.clip(ero, 0, None)


# --------------------------------------------------------------------------- brick
def _stock_brick(name, tile_m, band):
    rng = rng_for("london_stock_brick")  # the band variant is the same wall with one red course
    n = N
    ppm = n / tile_m
    rows = 14                                  # 71 mm courses (65 mm brick + joint)
    unit = n / 3                               # Flemish bond unit: stretcher + header
    S = unit * (225.0 / 337.5)
    H = unit - S
    g0 = rng.uniform(0, n)
    L = courses(n, rows, [[S, H] * 3] * rows, [g0 + (r % 2) * unit / 2 for r in range(rows)])
    cnt, sid = L["count"], L["sid"]
    joint = 0.01 * ppm
    sdf = unit_sdf(rng, L, joint, chip=0.55)
    inb = smoothstep(-0.5, 1.0, sdf)
    face = np.sqrt(np.clip(sdf / 4.0, 0, 1))
    sand = spectral(rng, beta=1.5, fmin=60)
    pits = np.clip(-spectral(rng, beta=1.0, fmin=120) - 1.6, 0, None)
    proud = rng.normal(0, 0.0012, cnt)[sid]
    tilt = rng.normal(0, 0.0006, cnt)[sid] * (L["lx"] / L["w"] - 0.5) + rng.normal(0, 0.0005, cnt)[sid] * \
        (L["ly"] / L["h"] - 0.5)
    hb = 0.007 * face + proud + tilt + sand * 0.00018 - pits * 0.0007
    mortar_h = -0.003 + spectral(rng, beta=1.8, fmin=40) * 0.0004 - \
        smoothstep(0.4, 0.9, norm01(spectral(rng, beta=2.4, fmin=8))) * 0.003
    h = mix(mortar_h, hb, inb)
    # London stocks: yellow-brown, some burnt darker/purple headers, black ash specks (clinker)
    tones = ["#9a8862", "#8c7a58", "#a59472", "#7f6e52", "#958a70", "#776a56", "#9d8b66", "#85765c"]
    bc = np.array([hexlin(tones[i]) for i in rng.integers(len(tones), size=cnt)], np.float32)
    bc *= np.exp(rng.normal(0, 0.07, (cnt, 1)))
    burnt = (rng.random(cnt) < 0.35) & (np.arange(cnt) % 2 == 1)   # some headers overfired
    bc[burnt] = bc[burnt] * np.array([0.62, 0.55, 0.6], np.float32)
    if band:
        red_row = 6
        reds = ["#7a3a2b", "#843f2e", "#6f3528", "#8a4632"]
        rr = np.array([hexlin(reds[i]) for i in rng.integers(len(reds), size=cnt)], np.float32)
        rowof = np.zeros(cnt, int)
        rowof[sid.ravel()] = L["row"].ravel()
        bc = np.where((rowof == red_row)[:, None], rr, bc)
    bcol = bc[sid]
    cloud = norm01(spectral(rng, beta=2.4, fmin=10))
    bcol = bcol * (0.84 + 0.28 * cloud[..., None]) * (1 + 0.08 * sand[..., None])
    speck = smoothstep(1.7, 2.4, spectral(rng, beta=0.3, fmin=150))
    bcol = mix(bcol, hexlin("#2f2a27"), speck * 0.8)
    mort = ramp(norm01(spectral(rng, beta=2.2, fmin=8)), [(0, "#5e5a53"), (0.5, "#6f6a61"), (1, "#7f796e")])
    mort = mort * (0.9 + 0.15 * norm01(spectral(rng, beta=1.2, fmin=80)))[..., None]
    col = mix(mort, bcol, inb)
    # a century of coal smoke: heavy soot film, streaks running down, darker in the joints/recesses
    soot_f = norm01(spectral(rng, beta=2.6, fmin=2, stretch=(0.35, 1.0))) * 0.7 + \
        0.3 * norm01(spectral(rng, beta=2.0, fmin=10))
    soot = smoothstep(0.15, 0.85, blur(soot_f, 3.0, 1.0))
    col = mix(col, hexlin("#2a2724"), 0.25 + soot * 0.5)
    col = mix(col, hexlin("#24211e"), smoothstep(2.0, -0.5, sdf) * 0.35)
    rough = mix(0.92, 0.82 - 0.04 * cloud, inb)
    rough = np.clip(rough + 0.04 * sand - 0.06 * soot, 0.55, 0.97)
    return Material(name, tile_m, col, h, rough, ao_radii_m=(0.003, 0.01, 0.03), ao_strength=1.1)


def london_stock_brick(name, tile_m):
    return _stock_brick(name, tile_m, band=False)


def london_stock_brick_band(name, tile_m):
    return _stock_brick(name, tile_m, band=True)


# --------------------------------------------------------------------------- slate
def slate_roof(name, tile_m):
    """Welsh slates 500x250 mm at 200 mm gauge, 4 across x 5 rows, broken bond. V points up the roof:
    each row's tail (lower edge) is at the bottom of its band and laps over the row below."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows, per = 5, 4
    cw = n / per
    wx = spectral(rng, beta=3.0, fmin=2) * 1.5
    wy = spectral(rng, beta=3.0, fmin=2) * 1.0
    L = courses(n, rows, [[cw] * per] * rows, [rng.uniform(-6, 6) + (r % 2) * cw / 2 for r in range(rows)],
                wx, wy)
    cnt, sid = L["count"], L["sid"]
    lyn = L["ly"] / L["h"]                    # 0 = head (under the row above) .. 1 = tail
    gap = 0.004 * ppm
    dx = np.minimum(L["lx"] - gap / 2, L["w"] - gap / 2 - L["lx"])
    # slipped slates: shifted down the roof, exposing batten/underlay at their top
    slip = np.where(rng.random(cnt) < 0.05, rng.uniform(0.25, 0.5, cnt), 0.0)[sid]
    lys = lyn - slip
    exposed = lys < 0
    side = smoothstep(-0.5, 1.0, dx - np.clip(blur(rng.standard_normal((n, n)).astype(np.float32), 2) * 2, 0, None))
    # cleft surface: stepped laminations
    riven = spectral(rng, beta=2.4, fmin=6, stretch=(1.0, 2.0))
    steps = blur(np.floor(norm01(riven) * 4) / 4, 1.0)
    thick = 0.005
    h = thick * 1.4 * np.clip(lys, 0, 1) + steps * 0.0008 + spectral(rng, beta=1.6, fmin=50) * 0.00006
    h += rng.normal(0, 0.0012, cnt)[sid] + rng.normal(0, 0.001, cnt)[sid] * (L["lx"] / L["w"] - 0.5)
    tail = smoothstep(1.0, 0.985, lyn)
    h = h * (0.5 + 0.5 * tail)
    h = np.where(exposed, -0.01, h)
    h = h * side + (1 - side) * (-0.008)
    # colour: blue-grey / purple Welsh slate, per-slate variation
    tones = ["#4c4e54", "#525158", "#46484d", "#4f4d54", "#56585c", "#49474d", "#57545a"]
    sc = np.array([hexlin(tones[i]) for i in rng.integers(len(tones), size=cnt)], np.float32)
    sc *= np.exp(rng.normal(0, 0.08, (cnt, 1)))
    col = sc[sid] * (0.88 + 0.2 * norm01(riven)[..., None]) * (1 + 0.06 * steps[..., None])
    # grime & soot, darker towards the head of each slate (shadowed, dirt collects)
    col = col * (1 - 0.25 * (1 - smoothstep(0.0, 0.25, lyn)))[..., None]
    grime = smoothstep(0.5, 0.9, norm01(spectral(rng, beta=2.6, fmin=2)))
    col = mix(col, hexlin("#2a2a2c"), grime * 0.35)
    # lichen rosettes and moss along tails and joints
    lich = np.zeros((n, n), np.float32)
    import cv2
    for i in range(70):
        x, y = rng.uniform(0, n, 2)
        r = np.exp(rng.normal(1.9, 0.5))
        R = int(r * 1.8) + 3
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        nz = cv2.GaussianBlur(rng.standard_normal(xx.shape).astype(np.float32), (0, 0), max(1.0, r * 0.25))
        nz /= nz.std() + 1e-6
        dd = np.sqrt(xx ** 2 + yy ** 2) / r + 0.25 * nz
        rim = np.exp(-((dd - 0.85) / 0.12) ** 2) * 0.4      # lichens are brighter at the growing rim
        stamp(lich, np.clip(smoothstep(1.0, 0.75, dd) * (0.55 + 0.45 * rim / 0.4 * 0.5) + rim, 0, 1)
              .astype(np.float32), x, y, mode="max")
    lich = blur(lich, 0.8)
    lc = mix(hexlin("#8f8e84"), hexlin("#9a8f55"), smoothstep(0.6, 0.8, norm01(spectral(rng, beta=2, fmin=5))))
    col = mix(col, lc, lich * 0.6)
    moss_f = norm01(spectral(rng, beta=2.6, fmin=3)) * 0.7 + 0.3 * norm01(spectral(rng, beta=1.6, fmin=40))
    near_joint = smoothstep(10, 0, dx) + smoothstep(0.88, 1.0, lyn)
    moss = smoothstep(0.72, 0.8, moss_f + 0.25 * np.clip(near_joint, 0, 1))
    mcol = ramp(norm01(spectral(rng, beta=1.8, fmin=30)), [(0, "#2f3220"), (1, "#4c5030")])
    col = mix(col, mcol, moss * 0.85)
    h = h + moss * 0.0015
    # exposed batten / felt under slipped slates
    batten = smoothstep(0.02, 0.0, np.abs(lys + 0.12)) * exposed
    col = np.where(exposed[..., None], mix(hexlin("#1c1b1c"), hexlin("#4a3a2a"), batten), col)
    col = col * (0.4 + 0.6 * side)[..., None]
    rough = 0.58 + 0.08 * norm01(riven) + 0.25 * lich + 0.35 * moss + 0.2 * exposed
    return Material(name, tile_m, col, h, np.clip(rough, 0.4, 0.97), ao_radii_m=(0.003, 0.012, 0.04),
                    ao_strength=1.4)


# --------------------------------------------------------------------------- pavement
def pavement_flags(name, tile_m):
    """York stone flags, 3 courses along U. Map V across the pavement: V=0 (image bottom) = kerb side."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows = 3
    lens = []
    for r in range(rows):
        ls = rng.uniform(0.5, 1.0, 12) * ppm
        k = int(np.searchsorted(np.cumsum(ls), n))
        ls = ls[:k + 1]
        lens.append(ls / ls.sum() * n)
    wx = spectral(rng, beta=3.0, fmin=2) * 2.0
    wy = spectral(rng, beta=3.0, fmin=2) * 2.0
    L = courses(n, rows, lens, [rng.uniform(0, n) for _ in range(rows)], wx, wy)
    cnt, sid = L["count"], L["sid"]
    joint = 0.008 * ppm
    sdf = unit_sdf(rng, L, joint, chip=1.4, jitter=2.0)
    inf = smoothstep(-0.5, 1.0, sdf)
    edge_round = np.sqrt(np.clip(sdf / 6.0, 0, 1))
    tiltx = rng.normal(0, 0.004, cnt)[sid] * (L["lx"] / L["w"] - 0.5)
    tilty = rng.normal(0, 0.004, cnt)[sid] * (L["ly"] / L["h"] - 0.5)
    lamin = spectral(rng, beta=2.2, fmin=6, stretch=(1.0, 3.0))
    riven = blur(np.floor(norm01(lamin) * 5) / 5, 1.2)
    hf = 0.004 * edge_round + tiltx + tilty + rng.normal(0, 0.002, cnt)[sid] + riven * 0.0007 + \
        spectral(rng, beta=1.6, fmin=60) * 0.00008
    # a few cracked flags
    cracked = (rng.random(cnt) < 0.25)[sid]
    cr = crack_lines(rng, n, 14, length_px=(80, 260), width_px=(1.0, 2.0), wobble=0.12, branch=0.5) * cracked
    hf -= cr * 0.004
    joint_h = -0.006 + spectral(rng, beta=2, fmin=15) * 0.0015
    h = mix(joint_h, hf, inf)
    tones = ["#8c8574", "#827a69", "#958d7b", "#7a7262", "#8a8170", "#9a917f", "#7f786c"]
    fc = np.array([hexlin(tones[i]) for i in rng.integers(len(tones), size=cnt)], np.float32)
    fc *= np.exp(rng.normal(0, 0.07, (cnt, 1)))
    col = fc[sid] * (0.88 + 0.2 * norm01(lamin)[..., None])
    iron = smoothstep(0.7, 0.9, norm01(spectral(rng, beta=2.4, fmin=4, stretch=(1, 2))))
    col = mix(col, hexlin("#7a6040"), iron * 0.3)
    col = mix(col, hexlin("#3a352e"), cr * 0.8)
    dirt = ramp(norm01(spectral(rng, beta=2, fmin=10)), [(0, "#2e2a25"), (1, "#45403a")])
    col = mix(dirt, col, inf)
    col = mix(col, dirt, smoothstep(5, 0, sdf) * 0.4 * inf)
    # kerb side (V=0 = bottom rows): dirtier, more worn, water collects
    v_img = (np.arange(n, dtype=np.float32) + 0.5)[:, None] / n * np.ones((1, n), np.float32)
    kerb = smoothstep(0.65, 1.0, v_img)
    grime = smoothstep(0.45, 0.85, norm01(spectral(rng, beta=2.6, fmin=2)) + 0.25 * kerb)
    col = mix(col, hexlin("#3b3631"), grime * 0.45)
    col = col * 0.8                                    # wet
    rel = h - blur(h, 0.15 * ppm)
    water = smoothstep(-0.0015 + 0.002 * kerb, -0.003 + 0.002 * kerb, rel) * \
        smoothstep(0.3, 0.6, norm01(spectral(rng, beta=3, fmin=2)) + 0.3 * kerb)
    lvl = blur(h, 0.15 * ppm) - 0.0015
    h = h * (1 - water) + np.minimum(h, lvl) * water
    col = mix(col, col * 0.62, water)
    rough = mix(0.5, 0.42 + 0.08 * norm01(lamin), inf) + 0.08 * grime
    rough = mix(rough, 0.06, water)
    return Material(name, tile_m, col, h, np.clip(rough, 0.04, 0.9), ao_radii_m=(0.004, 0.015, 0.05),
                    ao_strength=1.0)


# --------------------------------------------------------------------------- tarmac
def tarmac_road(name, tile_m):
    """Worn, wet tar-macadam: exposed chippings, crocodile cracking, longitudinal cracks, tar patches.
    Traffic runs along U (wheel tracks along U)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    binder = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#24221f"), (1, "#33302c")])
    ch = voronoi_chunks(rng, 70000, n=n, gap=(0.1, 0.45), bevel=0.4, tilt=0.4, keep=0.55, jitter=0.95, warp_px=0.8)
    npt = len(ch["pts"])
    stones = ["#5f5c57", "#6c6862", "#4e4b47", "#7a756d", "#58524b", "#66625e"]
    sc = np.array([hexlin(stones[i]) for i in rng.integers(len(stones), size=npt)], np.float32)
    sc *= np.exp(rng.normal(0, 0.1, (npt, 1)))
    # wheel tracks: binder worn off the chippings (more exposed, polished)
    track = np.zeros((n, n), np.float32)
    for yc in (rng.uniform(0, 1), ):
        for off in (0.0, 0.47):
            d = np.abs(((v - yc - off + 0.5) % 1.0) - 0.5) * tile_m
            track = np.maximum(track, np.exp(-(d / 0.22) ** 2))
    expose = ch["mask"] * smoothstep(0.2, 0.7, norm01(spectral(rng, beta=2.4, fmin=3)) * 0.7 + 0.5 * track)
    col = mix(binder, sc[ch["cid"]], expose * 0.85)
    h = spectral(rng, beta=3.4, fmin=1, fmax=10) * 0.006 - track * 0.006 + ch["h"] * ch["mask"] * 0.0012
    h += spectral(rng, beta=1.4, fmin=80) * 0.0001
    # tar repair patches (darker, smoother, slightly proud with a seam)
    patch = np.zeros((n, n), np.float32)
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32)
    for i in range(3):
        cx, cy = rng.uniform(0, n, 2)
        hw, hh = rng.uniform(0.2, 0.5, 2) * ppm
        a = rng.normal(0, 0.08)
        dx = (X - cx + n / 2) % n - n / 2
        dy = (Y - cy + n / 2) % n - n / 2
        ru = dx * np.cos(a) + dy * np.sin(a)
        rv = -dx * np.sin(a) + dy * np.cos(a)
        e = np.minimum(hw - np.abs(ru), hh - np.abs(rv)) + blur(rng.standard_normal((n, n)).astype(np.float32), 3) * 4
        patch = np.maximum(patch, smoothstep(-1, 1, e))
    seam = np.clip(blur(patch, 1.0) * (1 - blur(patch, 1.0)) * 4, 0, 1)
    pcol = ramp(norm01(spectral(rng, beta=2, fmin=8)), [(0, "#23211f"), (1, "#302d2a")])
    pcol = mix(pcol, sc[ch["cid"]] * 0.8, ch["mask"] * 0.25)
    col = mix(col, pcol, patch * 0.85)
    h = h + patch * 0.0015 + seam * 0.0008
    # cracks: longitudinal + crocodile network in fatigued areas
    lon = crack_lines(rng, n, 10, length_px=(150, 500), width_px=(1.0, 2.2), wobble=0.08, branch=0.6,
                      angle=0.0, angle_jitter=0.25)
    croc_cells = voronoi_chunks(rng, 2500, n=n, gap=(0.02, 0.05), bevel=0.05, tilt=0.0, jitter=0.9, warp_px=3)
    croc = (1 - croc_cells["mask"]) * smoothstep(0.62, 0.75, norm01(spectral(rng, beta=2.8, fmin=2)) + 0.2 * track)
    crack = np.clip(lon + croc, 0, 1) * (1 - patch)
    col = mix(col, hexlin("#151413"), crack * 0.85)
    h = h - crack * 0.004
    # wet: dark, glossy binder; puddles in the wheel ruts
    col = col * 0.85
    lvl = np.percentile(h, 14)
    water = smoothstep(lvl + 0.0006, lvl - 0.0012, h)
    h = h * (1 - water) + np.maximum(h, lvl) * water
    col = mix(col, col * 0.7, water)
    rough = 0.32 + 0.12 * expose + 0.08 * norm01(spectral(rng, beta=2, fmin=6)) - 0.08 * patch + 0.25 * crack
    rough = mix(rough, 0.05, water)
    return Material(name, tile_m, col, h, np.clip(rough, 0.04, 0.85), ao_radii_m=(0.003, 0.01, 0.03),
                    ao_strength=0.8)


# --------------------------------------------------------------------------- painted wood
def painted_wood(name, tile_m):
    """Chipped dark-green enamel (cream undercoat, red-oxide primer) over softwood; grain along U."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    G = periodic_grain(rng, ring_px=10, wander=30, knots=2, knot_r=(8, 16), stretch=8)
    late, fib = G["late"], G["fibre"]
    wood = mix(hexlin("#8a7f6c"), hexlin("#5d5446"), np.clip(late, 0, 1))      # weathered grey wood
    wood = mix(wood, hexlin("#3e352b"), G["knot"] * 0.7)
    # old paint crackle network + wear concentrated on arrises (none in a tile) -> patches & scuffs
    crk = voronoi_chunks(rng, 900, n=n, gap=(0.0, 0.03), bevel=0.05, tilt=0.0, jitter=0.9, warp_px=4,
                         aspect=(0.5, 1.0))
    crackle = 1 - crk["mask"]
    wear = norm01(spectral(rng, beta=2.6, fmin=3)) * 0.7 + 0.3 * norm01(spectral(rng, beta=1.8, fmin=20))
    cell_wear = rng.uniform(0, 1, len(crk["pts"]))[crk["cid"]]
    lose_top = (wear + 0.3 * cell_wear) > 0.98
    lose_under = (wear + 0.3 * cell_wear) > 1.05
    lose_primer = (wear + 0.3 * cell_wear) > 1.1
    top_a = blur((~lose_top).astype(np.float32), 0.6)
    und_a = blur((~lose_under).astype(np.float32), 0.6)
    pri_a = blur((~lose_primer).astype(np.float32), 0.6)
    brush = spectral(rng, beta=1.4, fmin=30, stretch=(20.0, 1.0))
    green = mix(hexlin("#1d3427"), hexlin("#26402f"), norm01(spectral(rng, beta=2.4, fmin=3)))
    green = green * (1 + 0.05 * brush[..., None])
    chalk = smoothstep(0.55, 0.9, norm01(spectral(rng, beta=2.2, fmin=4)))       # UV-faded, chalky enamel
    green = mix(green, hexlin("#4a5a4c"), chalk * 0.35)
    col = mix(wood, hexlin("#7c4a38"), pri_a)          # red-oxide primer
    col = mix(col, hexlin("#b3a684"), und_a)           # cream undercoat
    col = mix(col, green, top_a)
    col = mix(col, hexlin("#141a15"), crackle * top_a * 0.6)
    # scuffs and scratches (lighter, through the enamel sheen)
    scuff = smoothstep(1.6, 2.6, spectral(rng, beta=0.8, fmin=40, stretch=(6.0, 1.0), angle=0.3))
    col = mix(col, hexlin("#3f4f43"), scuff * top_a * 0.6)
    paint_t = 0.00012 * top_a + 0.00008 * und_a + 0.00005 * pri_a
    h = late * 0.0002 * (1 - top_a * 0.6) + fib * 0.00003 + paint_t + brush * 0.000015 * top_a - \
        crackle * top_a * 0.0001 + spectral(rng, beta=3.0, fmin=1, fmax=8) * 0.0003
    rough = mix(0.8, 0.6, und_a)
    rough = mix(rough, 0.38 + 0.2 * chalk + 0.1 * scuff, top_a)
    return Material(name, tile_m, col, h, np.clip(rough, 0.3, 0.9), ao_radii_m=(0.0006, 0.002, 0.006),
                    ao_strength=0.6)


# --------------------------------------------------------------------------- stucco
def render_stucco(name, tile_m):
    """Cream lime stucco ruled as ashlar (5 courses of 0.4 m), soot streaks running down (V up), cracks,
    patch repairs and small spalls exposing brick."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows = 5
    lens = []
    for r in range(rows):
        k = int(rng.integers(2, 4))
        lens.append([n / k] * k)
    L = courses(n, rows, lens, [rng.uniform(0, n) for _ in range(rows)])
    groove = smoothstep(2.5, 0.5, np.minimum(np.minimum(L["lx"], L["w"] - L["lx"]),
                                             np.minimum(L["ly"], L["h"] - L["ly"])))
    sand = spectral(rng, beta=1.2, fmin=100)
    float_marks = _swirl(rng, n)
    h = sand * 0.00008 + float_marks * 0.00012 - groove * 0.003 + spectral(rng, beta=3.2, fmin=1, fmax=10) * 0.002
    # cracks
    mapc = (1 - voronoi_chunks(rng, 700, n=n, gap=(0.0, 0.012), bevel=0.05, tilt=0, jitter=0.9,
                               warp_px=6)["mask"]) * smoothstep(0.6, 0.8, norm01(spectral(rng, beta=2.4, fmin=2)))
    c2 = crack_lines(rng, n, 6, length_px=(150, 450), width_px=(0.8, 1.6), wobble=0.15, branch=0.6,
                     angle=np.pi / 2, angle_jitter=0.5)
    crack = np.clip(mapc * 0.7 + c2, 0, 1)
    h -= crack * 0.0015
    # spalls exposing brick
    sp_f = norm01(spectral(rng, beta=2.6, fmin=4)) * 0.8 + 0.2 * norm01(spectral(rng, beta=1.8, fmin=20))
    spall = smoothstep(0.9, 0.905, sp_f)
    edge = smoothstep(0.87, 0.9, sp_f) * (1 - spall)
    brick_y = (np.arange(n)[:, None] % int(0.075 * ppm)) < 3
    brick = mix(hexlin("#8a7450"), hexlin("#5e5a52"), brick_y.astype(np.float32) * np.ones((1, n), np.float32))
    h = h * (1 - spall) - spall * 0.015 - edge * 0.002
    base = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#b4a688"), (0.5, "#c0b394"), (1, "#c9bd9f")])
    base = base * (0.96 + 0.06 * norm01(sand))[..., None]
    patch = smoothstep(0.7, 0.72, norm01(spectral(rng, beta=2.8, fmin=3)))
    base = mix(base, hexlin("#b0a68e"), patch * 0.6)
    # soot: streaks running down from sills/ledges, heavier general grime
    streak = norm01(blur(spectral(rng, beta=2.6, fmin=3, stretch=(0.2, 1.0)), 1.2, 8.0))
    soot = smoothstep(0.45, 0.95, streak) * 0.75 + smoothstep(0.4, 0.9, norm01(spectral(rng, beta=2.5, fmin=2))) * 0.35
    base = mix(base, hexlin("#3a3530"), np.clip(soot, 0, 1) * 0.6)
    base = mix(base, hexlin("#4a443c"), groove * 0.5)
    base = mix(base, hexlin("#4d463d"), crack * 0.7)
    base = mix(base, hexlin("#d2c8b0"), edge * 0.3)
    col = mix(base, brick, spall)
    rough = 0.86 + 0.04 * norm01(sand) - 0.08 * patch
    rough = mix(rough, 0.9, spall)
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.002, 0.008, 0.03),
                    ao_strength=0.9)


def _swirl(rng, n):
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32)
    out = np.zeros((n, n), np.float32)
    for i in range(70):
        cx, cy = rng.uniform(0, n, 2)
        r = rng.uniform(30, 90)
        dx = (X - cx + n / 2) % n - n / 2
        dy = (Y - cy + n / 2) % n - n / 2
        d = np.sqrt(dx ** 2 + dy ** 2)
        out += np.exp(-((d - r) / 5) ** 2) * smoothstep(r + 30, r, d) * rng.uniform(0.3, 1.0)
    return out / (out.max() + 1e-6)


# --------------------------------------------------------------------------- wallpaper
def interior_wallpaper(name, tile_m):
    """Faded 1930s floral wallpaper (half-drop repeat, two 0.5 m strips per tile) over lime plaster,
    torn, water-stained and mould-spotted. V up (stains run down)."""
    rng = rng_for(name)
    n = N
    sc = StrokeCanvas(n, {"r": 0, "g": 0, "b": 0, "a": 0}, ss=2)
    ground = hexlin("#cdbf9c")
    stripe = hexlin("#c4b591")
    # background: fine two-tone stripes
    for k in range(32):
        x0 = k * n / 32
        sc.polygon([(x0, 0), (x0 + n / 64, 0), (x0 + n / 64, n), (x0, n)], dict(r=stripe[0], g=stripe[1], b=stripe[2],
                                                                                   a=1))
    rose, rose_d = hexlin("#b07668"), hexlin("#8e5550")
    leaf, leaf_d = hexlin("#7e8a65"), hexlin("#5e6b4c")
    ochre = hexlin("#c49a52")
    mr = np.random.default_rng(42)
    petals = [(mr.uniform(0.8, 1.1), mr.uniform(0.85, 1.15)) for _ in range(6)]

    def C(c):
        return dict(r=c[0], g=c[1], b=c[2], a=1.0)

    def ellipse(cx, cy, rx, ry, ang, m=20):
        t = np.linspace(0, TAU, m, endpoint=False)
        x, y = rx * np.cos(t), ry * np.sin(t)
        return np.stack([cx + x * np.cos(ang) - y * np.sin(ang), cy + x * np.sin(ang) + y * np.cos(ang)], 1)

    def motif(cx, cy, s, flip):
        f = -1 if flip else 1
        stem = np.array([[cx, cy + 60 * s], [cx + f * 18 * s, cy + 90 * s], [cx + f * 10 * s, cy + 125 * s]])
        sc.ribbon(stem, np.array([3.0, 2.6, 2.0]) * s, lambda i, t: C(leaf_d))
        for k, (la, ll) in enumerate(((0.6, 1.0), (2.4, 0.8), (-0.4, 0.7))):
            a = la if f > 0 else np.pi - la
            bx, by = cx + f * 6 * s, cy + (55 + 25 * k) * s
            tt = np.linspace(0, 1, 9)
            cl = np.stack([bx + np.cos(a) * 46 * s * ll * tt, by + np.sin(a) * 46 * s * ll * tt], 1)
            wd = np.sin(np.pi * np.clip(tt, 0.03, 0.97)) * 15 * s * ll
            sc.ribbon(cl, wd, lambda i, t: C(leaf))
            sc.ribbon(cl, wd * 0.12, lambda i, t: C(leaf_d))
        for k, (rl, rw) in enumerate(petals):
            a = k * TAU / 6 + 0.3
            sc.polygon(ellipse(cx + np.cos(a) * 18 * s, cy + np.sin(a) * 18 * s, 21 * s * rl, 13 * s * rw, a),
                       C(rose))
        for k in range(6):
            a = k * TAU / 6 + 0.8
            sc.polygon(ellipse(cx + np.cos(a) * 9 * s, cy + np.sin(a) * 9 * s, 11 * s, 7 * s, a), C(rose_d))
        sc.polygon(ellipse(cx, cy, 7 * s, 7 * s, 0), C(ochre))
        for k in range(3):  # buds
            a = -0.9 - k * 0.7 if f > 0 else np.pi + 0.9 + k * 0.7
            sc.polygon(ellipse(cx + np.cos(a) * 52 * s, cy + np.sin(a) * 52 * s, 7 * s, 5 * s, a), C(rose))

    def sprig(cx, cy, s):
        for k in range(3):
            a = -np.pi / 2 + (k - 1) * 0.7
            tt = np.linspace(0, 1, 7)
            cl = np.stack([cx + np.cos(a) * 26 * s * tt, cy + np.sin(a) * 26 * s * tt], 1)
            sc.ribbon(cl, np.sin(np.pi * np.clip(tt, 0.05, 0.95)) * 8 * s, lambda i, t: C(leaf))
        sc.polygon(ellipse(cx, cy - 30 * s, 6 * s, 6 * s, 0), C(ochre))

    cell = n / 4
    for i in range(4):
        for j in range(4):
            motif((i + 0.5) * cell, (j + 0.3 + 0.5 * (i % 2)) * cell, 1.45, flip=(i % 2 == 1))
            sprig((i + 0.0) * cell, (j + 0.05 + 0.5 * (i % 2)) * cell, 1.1)
    a = np.clip(sc.get("a"), 0, 1)
    pat = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1)
    paper = mix(ground[None, None, :] * np.ones((n, n, 1), np.float32), pat / np.maximum(a[..., None], 1e-3), a)
    # print registration softness + paper fibre
    paper = blur(paper, 0.6) * (0.97 + 0.05 * norm01(spectral(rng, beta=1.0, fmin=100)))[..., None]
    # ageing: sun-fading, yellowing, water stains running down, mould
    fade = smoothstep(0.3, 0.9, norm01(spectral(rng, beta=3.0, fmin=1)))
    grey = (paper[..., 0:1] * 0.3 + paper[..., 1:2] * 0.59 + paper[..., 2:3] * 0.11)
    paper = mix(paper, grey * np.array([1.05, 1.0, 0.86], np.float32), fade * 0.55)
    paper = paper * np.array([1.0, 0.97, 0.88], np.float32)
    run = norm01(blur(spectral(rng, beta=2.6, fmin=2, stretch=(0.3, 1.0)), 1.5, 8.0))
    stain = smoothstep(0.6, 0.9, run)
    tide = np.exp(-((run - 0.6) / 0.012) ** 2)
    paper = mix(paper, hexlin("#8a7556"), stain * 0.45)
    paper = mix(paper, hexlin("#6d5a40"), tide * 0.25)
    mould = blur((spectral(rng, beta=0.4, fmin=150) > 2.1).astype(np.float32), 0.7) * \
        smoothstep(0.6, 0.9, norm01(spectral(rng, beta=2.8, fmin=3)))
    paper = mix(paper, hexlin("#3d3a30"), np.clip(mould * 1.5, 0, 0.8))
    # strip seams at U=0 and U=0.5 (slightly lifted, dark line)
    xs = (np.arange(n, dtype=np.float32) + 0.5)
    sd = np.minimum(xs % (n / 2), n / 2 - xs % (n / 2))[None, :] * np.ones((n, 1), np.float32)
    seam = smoothstep(1.5, 0.0, sd)
    paper = mix(paper, paper * 0.75, seam)
    # tears: paper gone -> plaster; torn edge shows white paper backing; flaps curl up
    tear_f = norm01(spectral(rng, beta=2.8, fmin=2)) * 0.8 + 0.2 * norm01(spectral(rng, beta=1.8, fmin=16))
    tear_f = warp(tear_f, spectral(rng, beta=2.5, fmin=6) * 5, spectral(rng, beta=2.5, fmin=6) * 5)
    gone = smoothstep(0.66, 0.665, tear_f)
    backing = smoothstep(0.64, 0.66, tear_f) * (1 - gone)
    plaster = ramp(norm01(spectral(rng, beta=2.4, fmin=4)), [(0, "#a8998a"), (1, "#bcae9e")])
    plaster = mix(plaster, hexlin("#7c6c58"), stain * 0.4)
    col = mix(paper, hexlin("#ddd5c3"), backing * 0.8)
    col = mix(col, plaster, gone)
    h = 0.00015 * (1 - gone) + backing * 0.0008 + seam * 0.0001 + spectral(rng, beta=1.4, fmin=80) * 0.00002 + \
        gone * spectral(rng, beta=2.0, fmin=20) * 0.0004 + spectral(rng, beta=3.2, fmin=1, fmax=8) * 0.0008
    rough = mix(0.82 - 0.05 * fade, 0.92, gone)
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.001, 0.004, 0.015),
                    ao_strength=0.8)


# --------------------------------------------------------------------------- floorboards
def floorboards_interior(name, tile_m):
    """Dusty pine floorboards, 8 x 150 mm boards per tile along U, cut nails on 400 mm joists."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    nb, gap = 8, 3
    bid, vin, dist, edges = board_bands(n, nb, gap)
    fields = [periodic_grain(rng, ring_px=8, wander=34, knots=5, knot_r=(4, 10), stretch=7) for _ in range(2)]
    late = np.zeros((n, n), np.float32)
    knot = np.zeros((n, n), np.float32)
    fib = np.zeros((n, n), np.float32)
    tone = np.zeros((n, n), np.float32)
    joint_x = np.full(nb, -1)
    for b in range(nb):
        F = fields[b % 2]
        ry = int(rng.integers(0, n))
        j = int(rng.integers(0, n)) if rng.random() < 0.6 else -1
        joint_x[b] = j
        rows = slice(edges[b], edges[b + 1])
        for key, dst in (("late", late), ("knot", knot), ("fibre", fib)):
            A = _board_field(np.roll(F[key], ry, axis=0), j if j >= 0 else 0, 0.85 if j >= 0 else 1.0)
            dst[rows] = A[rows]
        tone[rows] = np.exp(rng.normal(0, 0.1))
    X = np.arange(n)[None, :].repeat(n, 0)
    jd = np.full((n, n), 1e9, np.float32)
    for b in range(nb):
        if joint_x[b] >= 0:
            rows = slice(edges[b], edges[b + 1])
            jd[rows] = np.abs((X[rows] - joint_x[b] + n / 2) % n - n / 2)
    en = blur(rng.standard_normal((n, n)).astype(np.float32), 2.5) * 2
    de = np.minimum(dist - gap * (vin < 0.5) + en * 0.2, jd - 1 + en * 0.2)
    bm = smoothstep(-0.5, 1.5, de)
    h = (0.0012 * np.sqrt(np.clip(de / 5, 0, 1)) + late * 0.0002 + fib * 0.00004 +
         np.repeat(rng.uniform(-0.0008, 0.0008, nb), np.diff(edges))[:, None]
         + 0.0008 * ((vin - 0.5) * 2) ** 2) * bm - 0.008 * (1 - bm)
    wood = mix(hexlin("#9a7550"), hexlin("#6a4a2e"), np.clip(late, 0, 1)) * tone[..., None]
    wood = mix(wood, hexlin("#4a321f"), knot * 0.8)
    wood = wood * (1 + 0.05 * fib[..., None])
    wood = mix(wood, hexlin("#3a281a"), smoothstep(4, 0, jd) * 0.5)
    # worn old varnish/wax down the middle of the room vs dust everywhere else
    dust_f = norm01(spectral(rng, beta=2.6, fmin=2)) * 0.7 + 0.3 * norm01(spectral(rng, beta=1.6, fmin=30))
    dust = smoothstep(0.3, 0.75, dust_f) * 0.7 + smoothstep(6, 0, de) * 0.4
    dust = np.clip(dust, 0, 1)
    dcol = ramp(norm01(spectral(rng, beta=1.8, fmin=20)), [(0, "#8d857a"), (1, "#a59d90")])
    col = mix(wood, dcol, dust * 0.75)
    col = mix(hexlin("#2a2520"), col, bm)
    rough = mix(0.55 + 0.05 * late, 0.9, dust)
    metal = np.zeros((n, n), np.float32)
    joists = [rng.uniform(0, n / 3) + k * n / 3 for k in range(3)]
    for b in range(nb):
        y = (edges[b] + edges[b + 1]) / 2
        for x in joists:
            for dy in (-0.25, 0.25):
                _nail(h, col, rough, metal, x + rng.normal(0, 1.5), y + dy * (edges[1] - edges[0]),
                      rng.uniform(2.0, 2.6), rng, ppm, streak=False)
    # plaster crumbs from the ceiling
    crumbs = np.zeros((n, n), np.float32)
    scatter_stones(rng, h, col, 300, (1.0, 4.0), [hexlin("#b9b0a2"), hexlin("#a49b8d")], embed=(0.0, 0.3),
                   h_scale_m=0.003, angular=0.7, rough_map=rough, rough_val=0.92, id_map=crumbs)
    return Material(name, tile_m, col, h, np.clip(rough, 0.4, 0.95), metal=metal,
                    ao_radii_m=(0.002, 0.006, 0.02), ao_strength=0.8)


# --------------------------------------------------------------------------- station tiles
def tile_station(name, tile_m):
    """Cream glazed 6x3-inch-style wall tiles in half bond (6 x 12 per tile) with a two-course green band
    (courses 7-8 from the top). No logos or text."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows, per = 12, 6
    cw = n / per
    L = courses(n, rows, [[cw] * per] * rows, [(r % 2) * cw / 2 for r in range(rows)])
    cnt, sid, row = L["count"], L["sid"], L["row"]
    joint = 0.003 * ppm
    sdf = unit_sdf(rng, L, joint, chip=0.0, jitter=0.4)
    # chipped glaze on a few tiles
    chipped = (rng.random(cnt) < 0.12)[sid]
    chip = chipped * smoothstep(0.8, 0.85, norm01(spectral(rng, beta=2.4, fmin=10))) * smoothstep(12, 2, sdf)
    inb = smoothstep(-0.5, 1.0, sdf)
    cushion = np.sqrt(np.clip(sdf / 7.0, 0, 1))
    wav = spectral(rng, beta=3.0, fmin=4, fmax=60)
    h = (0.0025 * cushion + rng.normal(0, 0.0005, cnt)[sid] + wav * 0.00015
         + rng.normal(0, 0.0004, cnt)[sid] * (L["lx"] / L["w"] - 0.5)) * inb - 0.0015 * (1 - inb) - chip * 0.0012
    green_row = (row == 7) | (row == 8)
    cream = hexlin("#d6ccaa")
    greens = hexlin("#2f5e44")
    tc = np.where(green_row[..., None], greens, cream) * np.exp(rng.normal(0, 0.035, (cnt, 1)))[sid]
    tc = tc * (0.97 + 0.05 * norm01(wav))[..., None]
    # glaze pooling darker at the edges of green tiles
    tc = np.where(green_row[..., None], tc * (0.8 + 0.2 * cushion[..., None]), tc)
    # crazing on cream tiles, grime-filled
    craze = (1 - voronoi_chunks(rng, 6000, n=n, gap=(0.0, 0.015), bevel=0.05, tilt=0, jitter=0.9,
                                warp_px=2)["mask"]) * (~green_row) * smoothstep(0.4, 0.8, norm01(spectral(rng, beta=2.5,
                                                                                                         fmin=3)))
    tc = mix(tc, hexlin("#8a8270"), craze * 0.5)
    tc = mix(tc, hexlin("#c8beab"), chip)          # biscuit body
    grout = ramp(norm01(spectral(rng, beta=2, fmin=10)), [(0, "#3e3a35"), (1, "#5e5850")])
    col = mix(grout, tc, inb)
    # soot / grime film: heavier low down (tile V=0 side) and streaky
    grime = smoothstep(0.4, 0.95, norm01(blur(spectral(rng, beta=2.6, fmin=2, stretch=(0.3, 1.0)), 1.2, 6.0)))
    col = mix(col, hexlin("#4a4438"), grime * 0.3)
    rough = mix(0.88, 0.1 + 0.06 * norm01(wav) + 0.18 * grime, inb)
    rough = mix(rough, 0.8, chip)
    rough = mix(rough, 0.35, craze * 0.5)
    return Material(name, tile_m, col, h, np.clip(rough, 0.05, 0.95), ao_radii_m=(0.001, 0.004, 0.012),
                    ao_strength=0.7)


# --------------------------------------------------------------------------- platform
def concrete_platform(name, tile_m):
    """Worn Underground platform concrete with a worn white painted safety strip (150 mm) along U near the
    platform edge. Map V across the platform: the edge side is V=0, strip centre at V≈0.1."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    base = ramp(norm01(spectral(rng, beta=2.6, fmin=1)), [(0, "#6f6b64"), (0.5, "#7b766e"), (1, "#88837a")])
    ch = voronoi_chunks(rng, 20000, n=n, gap=(0.15, 0.5), bevel=0.3, tilt=0.0, keep=0.3, jitter=0.95, warp_px=1)
    npt = len(ch["pts"])
    ag = np.array([hexlin(c) for c in rng.choice(["#5a5752", "#8d877c", "#6e655a", "#9a958a"], npt)], np.float32)
    # worn path (foot traffic) exposes aggregate, mostly in the middle band of the platform
    v_img = (np.arange(n, dtype=np.float32) + 0.5)[:, None] / n * np.ones((1, n), np.float32)
    path = np.exp(-((v_img - 0.62) / 0.22) ** 2)
    wear = smoothstep(0.3, 0.8, norm01(spectral(rng, beta=2.5, fmin=2)) * 0.6 + path * 0.6)
    col = mix(base, ag[ch["cid"]], ch["mask"] * wear * 0.75)
    col = col * (0.95 + 0.08 * norm01(spectral(rng, beta=1.2, fmin=100)))[..., None]
    stains = smoothstep(0.65, 0.9, norm01(spectral(rng, beta=2.4, fmin=3)))
    col = mix(col, hexlin("#3e3a35"), stains * 0.45)
    crack = crack_lines(rng, n, 7, length_px=(100, 400), width_px=(0.8, 1.6), wobble=0.12, branch=0.5)
    joint = smoothstep(2.0, 0.5, np.minimum(np.arange(n), n - 1 - np.arange(n)))[None, :] * np.ones((n, 1))
    col = mix(col, hexlin("#2e2b28"), np.clip(crack + joint, 0, 1) * 0.8)
    # painted strip (blackout-era white edge line), worn by feet, chipped
    yc = 0.9  # image row fraction -> V = 0.1
    d = np.abs(v - yc) * tile_m
    strip = smoothstep(0.077, 0.073, d + blur(rng.standard_normal((n, n)).astype(np.float32), 2) * 0.0015)
    pw = norm01(spectral(rng, beta=2.2, fmin=6)) * 0.7 + 0.3 * norm01(spectral(rng, beta=1.4, fmin=60))
    paint = strip * smoothstep(0.78, 0.72, pw)
    pcol = mix(hexlin("#c9c4b4"), hexlin("#a8a292"), norm01(spectral(rng, beta=2, fmin=8)))
    col = mix(col, pcol, paint)
    col = mix(col, hexlin("#55514a"), paint * stains * 0.5)
    h = spectral(rng, beta=3.4, fmin=1, fmax=10) * 0.002 + ch["mask"] * wear * 0.0004 + \
        spectral(rng, beta=1.4, fmin=80) * 0.00008 - (crack + joint) * 0.003 + paint * 0.0002
    rough = 0.78 - 0.18 * path * wear + 0.04 * stains
    rough = mix(rough, 0.55, paint)
    return Material(name, tile_m, col, h, np.clip(rough, 0.4, 0.95), ao_radii_m=(0.002, 0.008, 0.03),
                    ao_strength=0.7)


# --------------------------------------------------------------------------- char
def soot_scorch(name, tile_m):
    """Charred timber ('alligator' char): checks elongated along U (grain), silvery char tops, ash and
    brown unburnt wood in the deepest cracks."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    ch = voronoi_chunks(rng, 420, n=n, gap=(0.04, 0.14), bevel=0.35, tilt=0.5, crease=0.3, jitter=0.85,
                        aspect=(0.45, 1.0), warp_px=5)
    r_m = ch["r"] * tile_m
    grain = spectral(rng, beta=1.4, fmin=30, stretch=(25.0, 1.0))
    small = voronoi_chunks(rng, 4000, n=n, gap=(0.0, 0.06), bevel=0.2, tilt=0.3, jitter=0.9, aspect=(0.5, 1.0),
                           warp_px=2)
    top = ch["h"] * r_m * 0.25 + small["h"] * 0.0015 + grain * 0.0002
    h = np.where(ch["mask"] > 0.5, top, -0.012) * ch["mask"] + (1 - ch["mask"]) * -0.012
    h = blur(h, 0.7) + spectral(rng, beta=3.2, fmin=1, fmax=8) * 0.004
    crack = 1 - ch["mask"]
    fine = 1 - small["mask"]
    char = ramp(norm01(spectral(rng, beta=2.0, fmin=10)), [(0, "#151311"), (0.6, "#1d1a17"), (1, "#26221e")])
    sheen = np.clip(ch["h"], 0, 1)
    char = mix(char, hexlin("#34312e"), sheen * 0.25)
    char = char * (1 + 0.1 * grain[..., None])
    brown = smoothstep(0.65, 0.85, norm01(spectral(rng, beta=2.4, fmin=4)))       # less-burnt zones
    char = mix(char, hexlin("#3a2617"), brown * 0.5)
    ash = smoothstep(0.5, 0.8, norm01(spectral(rng, beta=2.2, fmin=6)))
    deep = mix(hexlin("#0d0c0b"), hexlin("#5a3a22"), brown)
    deep = mix(deep, hexlin("#8a857e"), ash * 0.8)
    col = mix(char, deep, crack)
    col = mix(col, hexlin("#0f0e0d"), fine * 0.6)
    ash_film = smoothstep(0.7, 0.92, norm01(spectral(rng, beta=2.0, fmin=8)))
    col = mix(col, hexlin("#77736d"), ash_film * 0.3 * ch["mask"])
    rough = 0.62 - 0.18 * sheen + 0.3 * crack + 0.25 * ash_film + 0.1 * brown
    return Material(name, tile_m, col, h, np.clip(rough, 0.35, 0.97), ao_radii_m=(0.003, 0.01, 0.03),
                    ao_strength=1.3)


SETS = {
    "london_stock_brick": (london_stock_brick, 1.0, "Yellow-brown London stock brick, Flemish bond (14 courses, 3 "
                                                    "stretcher+header units per tile), heavy soot, blackened lime "
                                                    "mortar."),
    "london_stock_brick_band": (london_stock_brick_band, 1.0, "Accent-course option: identical wall to "
                                                              "london_stock_brick with one red-brick course at V≈0.55; "
                                                              "use for one band row of a facade."),
    "slate_roof": (slate_roof, 1.0, "Welsh slate roof, 4 slates x 5 rows (200 mm gauge), broken bond, rows along U; "
                                    "V points up the roof (tails at the bottom of each row). Moss, lichen, slipped "
                                    "slates."),
    "pavement_flags": (pavement_flags, 2.0, "Wet York stone flags in 3 courses along U; map V across the pavement "
                                            "with the kerb side at V=0 (more dirt, puddles: roughness ~0.06)."),
    "tarmac_road": (tarmac_road, 3.0, "Old wet tar-macadam: exposed chippings, wheel tracks along U, crocodile and "
                                      "longitudinal cracks, tar patches, puddles in ruts. No tram rails."),
    "painted_wood": (painted_wood, 0.5, "Chipped dark-green enamel over cream undercoat and red-oxide primer on "
                                        "softwood, scuffed; grain along U."),
    "render_stucco": (render_stucco, 2.0, "Cream lime stucco ruled as ashlar (5 courses of 0.4 m), soot streaks "
                                          "running down (V up), cracks, patches, spalls showing brick."),
    "interior_wallpaper": (interior_wallpaper, 1.0, "Faded 1930s floral wallpaper (half-drop repeat, strip seams at "
                                                    "U=0/0.5), torn to plaster, water stains (V up), mould."),
    "floorboards_interior": (floorboards_interior, 1.2, "Dusty pine floorboards, 8 x 150 mm boards along U, butt "
                                                        "joints, cut nails on 400 mm joists, plaster crumbs."),
    "tile_station": (tile_station, 1.0, "Cream glazed wall tiles in half bond (6 x 12 per tile) with a two-course "
                                        "green band at V≈0.3; crazing, chips, grime. No logos or text."),
    "concrete_platform": (concrete_platform, 2.0, "Worn platform concrete; worn white painted 150 mm strip along U at "
                                                  "V≈0.1 (platform edge side = V=0); expansion joint at U=0."),
    "soot_scorch": (soot_scorch, 1.0, "Charred timber (alligator char), checks elongated along U, ash and brown "
                                      "unburnt wood in cracks; very dark albedo."),
}
