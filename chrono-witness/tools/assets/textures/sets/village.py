"""Somme village materials: brick_french, plaster_damaged, roof_tiles, cobblestone_wet."""
from __future__ import annotations

import numpy as np

from lib.core import (N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral, stamp,
                      uv, warp)
from lib.elements import jittered_pts, voronoi_chunks
from lib.pbr import Material


def _bond(n, courses, per_course, offset=0.5):
    """Running bond layout. Returns row, col(id within row), local x,y in px, cell w,h in px, cell id."""
    ch = n / courses
    cw = n / per_course
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    row = np.floor(Y / ch).astype(int)
    off = (row % 2) * offset * cw
    xs = (X - off) % n
    col = np.floor(xs / cw).astype(int)
    lx = xs - col * cw
    ly = Y - row * ch
    cid = row * per_course + col
    return row, col, lx, ly, cw, ch, cid


def brick_french(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    courses, per = 16, 4
    row, colm, lx, ly, cw, ch, cid = _bond(n, courses, per)
    ncell = courses * per
    joint = 0.011 * ppm
    # per-brick size jitter + eroded/chipped arrises
    jl = rng.uniform(-2, 2, ncell)[cid]
    jr = rng.uniform(-2, 2, ncell)[cid]
    jt = rng.uniform(-1.5, 1.5, ncell)[cid]
    jb = rng.uniform(-1.5, 1.5, ncell)[cid]
    ero = blur(rng.standard_normal((n, n)).astype(np.float32), 1.5) * 2.5 + \
        np.clip(spectral(rng, beta=2.0, fmin=12) - 0.8, 0, None) * 7.0 + \
        np.clip(spectral(rng, beta=1.4, fmin=40) - 1.5, 0, None) * 6.0
    dx = np.minimum(lx - joint / 2 - jl, cw - joint / 2 - lx + jr)
    dy = np.minimum(ly - joint / 2 - jt, ch - joint / 2 - ly + jb)
    sdf = np.minimum(dx, dy) - np.clip(ero, 0, None)
    inb = smoothstep(-0.5, 1.0, sdf)
    face_prof = np.sqrt(np.clip(sdf / 4.0, 0, 1))
    tilt_x = rng.normal(0, 0.0006, ncell)[cid] * (lx / cw - 0.5)
    tilt_y = rng.normal(0, 0.0006, ncell)[cid] * (ly / ch - 0.5)
    proud = rng.normal(0, 0.0012, ncell)[cid]
    sand = spectral(rng, beta=1.5, fmin=60)
    pits = np.clip(-spectral(rng, beta=1.0, fmin=120) - 1.8, 0, None)
    hb = 0.008 * face_prof + proud + tilt_x + tilt_y + sand * 0.00015 - pits * 0.0006
    # some damaged bricks: chunks missing
    dmg = (rng.random(ncell) < 0.12)[cid]
    hole = smoothstep(0.55, 0.75, norm01(spectral(rng, beta=2.6, fmin=8))) * dmg
    hb -= hole * 0.008
    mortar_h = -0.002 + spectral(rng, beta=1.8, fmin=40) * 0.0004 - \
        smoothstep(0.4, 0.9, norm01(spectral(rng, beta=2.4, fmin=8))) * 0.003
    h = mix(mortar_h, hb, inb)
    # colours: hand-made red-brown with firing variation
    tones = ["#744235", "#7c4a3a", "#683c30", "#845440", "#64403a", "#8a5a44", "#583631", "#77503f", "#6e4a40"]
    tone_idx = rng.integers(len(tones), size=ncell)
    bc = np.array([hexlin(tones[i]) for i in tone_idx], np.float32) * np.exp(rng.normal(0, 0.07, (ncell, 1)))
    bcol = bc[cid]
    # within-brick firing clouds, darker ends (headers closer to fire), sand specks
    cloud = norm01(spectral(rng, beta=2.4, fmin=10))
    bcol = bcol * (0.82 + 0.3 * cloud[..., None]) * (1 + 0.08 * sand[..., None])
    endd = np.minimum(lx, cw - lx) / cw
    bcol = mix(bcol, bcol * 0.75, smoothstep(0.2, 0.0, endd) * (rng.random(ncell) < 0.3)[cid] * 0.7)
    bcol = mix(bcol, hexlin("#6d4a3a"), hole * 0.6)  # inner fresh broken brick is lighter/duller
    mort = ramp(norm01(spectral(rng, beta=2.2, fmin=8)), [(0, "#7a756b"), (0.5, "#8f897d"), (1, "#a19b8e")])
    mort = mort * (0.9 + 0.15 * norm01(spectral(rng, beta=1.2, fmin=80)))[..., None]
    col = mix(mort, bcol, inb)
    # mortar smears on brick faces near joints
    smear = smoothstep(3, 0, sdf) * smoothstep(0.6, 0.85, norm01(spectral(rng, beta=1.8, fmin=30)))
    col = mix(col, mort, smear * 0.6 * inb)
    # weathering: soot from fire, efflorescence, dirt streaks running down, green algae low
    soot = smoothstep(0.55, 0.92, norm01(spectral(rng, beta=2.6, fmin=2, stretch=(0.35, 1.0))))
    col = mix(col, hexlin("#2a221d"), soot * 0.55)
    eff = smoothstep(0.75, 0.95, norm01(spectral(rng, beta=2.5, fmin=4))) * \
        smoothstep(0.3, 0.7, norm01(spectral(rng, beta=1.4, fmin=40)))
    col = mix(col, hexlin("#c2bcb0"), eff * 0.45)
    streaks = smoothstep(0.6, 0.95, norm01(spectral(rng, beta=2.2, fmin=4, stretch=(0.1, 1.0))))
    col = col * (1 - 0.18 * streaks[..., None])
    rough = mix(0.92, 0.8 - 0.05 * cloud, inb)
    rough = np.clip(rough + 0.04 * sand - 0.1 * soot + 0.05 * eff, 0.5, 0.97)
    return Material(name, tile_m, col, h, rough, ao_radii_m=(0.003, 0.01, 0.03), ao_strength=1.1)


def plaster_damaged(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    # --- underlying rubble-stone masonry
    st = voronoi_chunks(rng, 220, n=n, gap=(0.08, 0.25), bevel=0.8, tilt=0.5, keep=1.0, jitter=0.85,
                        aspect=(1.0, 1.0), warp_px=9.0)
    r_m = st["r"] * tile_m
    stone_h = st["h"] * r_m * 0.5 + spectral(rng, beta=2.0, fmin=40) * 0.0008
    mort_h = -0.008 + spectral(rng, beta=1.6, fmin=50) * 0.001
    mas_h = mix(mort_h, stone_h, st["mask"])
    stones = ["#8f8574", "#9d927d", "#7d7466", "#a39a88", "#867b6c", "#6f675c"]
    sc = np.array([hexlin(stones[i]) for i in rng.integers(len(stones), size=len(st["pts"]))], np.float32)
    scol = sc[st["cid"]] * (0.85 + 0.25 * norm01(spectral(rng, beta=1.8, fmin=30)))[..., None]
    mcol = hexlin("#8d8678") * (0.9 + 0.15 * norm01(spectral(rng, beta=1.4, fmin=60)))[..., None]
    mas_col = mix(mcol, scol, st["mask"])
    # --- plaster layer
    loss_f = norm01(spectral(rng, beta=2.8, fmin=2)) * 0.75 + norm01(spectral(rng, beta=1.8, fmin=12)) * 0.25
    loss_f = warp(loss_f, spectral(rng, beta=2.5, fmin=4) * 6, spectral(rng, beta=2.5, fmin=4) * 6)
    thr = 0.62
    loss = smoothstep(thr - 0.004, thr + 0.004, loss_f)            # 1 = plaster gone
    edge_band = smoothstep(thr - 0.04, thr, loss_f) * (1 - loss)    # broken edge, delaminating
    thick = 0.014
    pl_h = thick + spectral(rng, beta=2.8, fmin=3) * 0.0012 + spectral(rng, beta=1.6, fmin=60) * 0.00012
    # cracks network
    cr = np.abs(bandnoise(rng, f=6, width=0.6))
    cr2 = np.abs(bandnoise(rng, f=14, width=0.6))
    crack = (smoothstep(0.05, 0.0, cr) * smoothstep(0.3, 0.6, norm01(spectral(rng, beta=2, fmin=3))) +
             smoothstep(0.03, 0.0, cr2) * 0.6 * smoothstep(0.5, 0.8, norm01(spectral(rng, beta=2, fmin=3))))
    crack = np.clip(crack, 0, 1)
    pl_h = pl_h - crack * 0.002 - edge_band * 0.002
    h = mix(pl_h, mas_h, loss)
    pcol = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#a79e8b"), (0.5, "#b8af9b"), (1, "#c4bca9")])
    pcol = pcol * (0.95 + 0.07 * norm01(spectral(rng, beta=1.4, fmin=60)))[..., None]
    # old lime-wash layers: patchy lighter/darker
    wash = smoothstep(0.5, 0.8, norm01(spectral(rng, beta=2.2, fmin=5)))
    pcol = mix(pcol, hexlin("#cdc7b8"), wash * 0.4)
    # water stains running down + tide marks, grime
    run = norm01(spectral(rng, beta=2.4, fmin=3, stretch=(0.12, 1.0)))
    stain = smoothstep(0.55, 0.9, run)
    pcol = mix(pcol, hexlin("#7a7262"), stain * 0.45)
    tide = np.exp(-((run - 0.55) / 0.01) ** 2) * 0.3
    pcol = mix(pcol, hexlin("#6a604f"), tide)
    green = smoothstep(0.7, 0.95, norm01(spectral(rng, beta=2.6, fmin=3))) * stain
    pcol = mix(pcol, hexlin("#5c5f45"), green * 0.4)
    pcol = mix(pcol, hexlin("#4d463c"), crack * 0.7)
    pcol = mix(pcol, hexlin("#d0cabd"), edge_band * 0.35)  # fresh broken plaster edge
    col = mix(pcol, mas_col, loss)
    col = mix(col, col * 0.8, stain[..., None] * loss[..., None] * 0.5)
    rough = mix(0.88 + 0.04 * wash, mix(0.92, 0.82, st["mask"]), loss)
    rough = np.clip(rough - 0.12 * stain, 0.55, 0.97)
    return Material(name, tile_m, col, h, rough, ao_radii_m=(0.003, 0.012, 0.04), ao_strength=1.0)


def roof_tiles(name, tile_m):
    """French interlocking 'tuiles mécaniques' (Marseille pattern): 5 columns x 3 rows per tile, slope runs
    down the texture (V decreasing = down-slope at the bottom of the image)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    ncol, nrow = 5, 3
    cw, ch = n / ncol, n / nrow
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    # small per-tile placement jitter (tiles sit a little irregularly)
    row = np.floor(Y / ch).astype(int)
    jx = rng.normal(0, 1.5, (nrow, ncol))
    jy = rng.normal(0, 1.5, (nrow, ncol))
    colm0 = np.floor(X / cw).astype(int) % ncol
    Xs = X - jx[row % nrow, colm0]
    Ys = Y - jy[row % nrow, colm0]
    row = np.floor(Ys / ch).astype(int) % nrow
    colm = np.floor((Xs % n) / cw).astype(int) % ncol
    lx = ((Xs % n) - colm * cw) / cw    # 0..1 across tile
    ly = (Ys - np.floor(Ys / ch) * ch) / ch  # 0 top (under the row above) .. 1 nose (bottom edge)
    tid = row * ncol + colm
    nt = ncol * nrow
    # cross profile: interlock roll on the left, two flutes, central rib, side rib on the right
    prof = (0.010 * np.exp(-((lx - 0.06) / 0.04) ** 2)          # left roll (covers neighbour)
            - 0.011 * np.exp(-((lx - 0.3) / 0.1) ** 2)           # flute
            + 0.006 * np.exp(-((lx - 0.5) / 0.035) ** 2)         # central rib
            - 0.011 * np.exp(-((lx - 0.7) / 0.1) ** 2)           # flute
            + 0.005 * np.exp(-((lx - 0.93) / 0.035) ** 2))       # right rib
    edge_gap = smoothstep(0.0, 0.015, lx) * smoothstep(1.0, 0.985, lx)
    # along slope: tile rises towards its nose, nose rounds off and drops onto the row below
    along = 0.03 * ly ** 1.3
    nose = smoothstep(1.0, 0.95, ly)
    head = 0.0025 * np.exp(-((ly - 0.08) / 0.025) ** 2) + 0.0018 * np.exp(-((ly - 0.15) / 0.02) ** 2)
    h = (prof + along + head) * (0.3 + 0.7 * nose) - 0.01 * (1 - edge_gap)
    h += rng.normal(0, 0.002, nt)[tid] + spectral(rng, beta=1.6, fmin=60) * 0.00012
    broken = (rng.random(nt) < 0.06)[tid] * smoothstep(0.7, 0.8, norm01(spectral(rng, beta=2.6, fmin=8)))
    h -= broken * 0.01
    # colour
    tones = ["#844c35", "#8d573e", "#7a4733", "#975f43", "#734536", "#8a5742", "#7f5546", "#6d4a3e"]
    tc = np.array([hexlin(tones[i]) for i in rng.integers(len(tones), size=nt)], np.float32)
    tc *= np.exp(rng.normal(0, 0.06, (nt, 1)))
    col = tc[tid] * (0.9 + 0.15 * norm01(spectral(rng, beta=2.2, fmin=10)))[..., None]
    # dirt washing down the flutes, darker under the nose overlap (shadow region at top of each tile)
    flute = np.clip(-prof / 0.011, 0, 1)
    dirt = smoothstep(0.4, 0.9, norm01(spectral(rng, beta=2.2, fmin=3, stretch=(0.25, 1.0))))
    col = mix(col, hexlin("#4a3b30"), np.clip(flute * dirt * 0.6 + (1 - smoothstep(0.0, 0.18, ly)) * 0.35, 0, 1))
    # moss in flutes and along the nose, lichen spots on the flats
    moss_f = norm01(spectral(rng, beta=2.8, fmin=3)) * 0.75 + 0.25 * norm01(spectral(rng, beta=1.8, fmin=30))
    moss = smoothstep(0.66, 0.72, moss_f + flute * 0.08 + (1 - smoothstep(0, 0.15, ly)) * 0.25 +
                      (1 - smoothstep(0.85, 1.0, ly)) * 0 + smoothstep(0.9, 1.0, ly) * 0.1)
    moss = blur(moss, 1.0)
    mcol = ramp(norm01(spectral(rng, beta=1.8, fmin=30)), [(0, "#33361f"), (0.6, "#4a4d2a"), (1, "#5d5f33")])
    col = mix(col, mcol, moss * 0.9)
    h += moss * 0.0015 * (0.5 + norm01(spectral(rng, beta=1.0, fmin=100)))
    lich = np.zeros((n, n), np.float32)
    for i in range(90):
        x, y = rng.uniform(0, n, 2)
        r = np.exp(rng.normal(1.5, 0.5))
        R = int(r * 1.6) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        lob = 1 + 0.2 * np.cos(np.arctan2(yy, xx) * rng.integers(3, 7))
        stamp(lich, smoothstep(r * lob, r * lob - 1.2, np.sqrt(xx ** 2 + yy ** 2)).astype(np.float32), x, y, mode="max")
    lcol = hexlin("#8f8a6a")
    col = mix(col, lcol, blur(lich, 0.8) * 0.45)
    grime = smoothstep(0.5, 0.9, norm01(spectral(rng, beta=2.6, fmin=2)))
    col = col * (1 - 0.25 * grime[..., None])
    col = mix(col, hexlin("#5a3a2c"), broken * 0.7)
    col = col * (0.55 + 0.45 * edge_gap)[..., None]
    rough = 0.72 + 0.08 * dirt * flute + 0.15 * moss + 0.05 * lich
    return Material(name, tile_m, col, h, np.clip(rough, 0.5, 0.97), ao_radii_m=(0.004, 0.015, 0.05),
                    ao_strength=1.6)


def cobblestone_wet(name, tile_m):
    """Worn granite/sandstone setts laid in courses along U, wet, mud in the joints, puddles."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows = 16                                   # 12.5 cm courses
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    wx = spectral(rng, beta=2.8, fmin=3) * 5.0
    wy = spectral(rng, beta=2.8, fmin=3) * 4.0
    Xw, Yw = (X + wx) % n, (Y + wy) % n
    # course boundaries wobble a little
    rh = n / rows
    r_idx = np.floor(Yw / rh).astype(int) % rows
    ly = (Yw - np.floor(Yw / rh) * rh)
    sid = np.zeros((n, n), np.int32)
    lx = np.zeros((n, n), np.float32)
    sw = np.zeros((n, n), np.float32)
    count = 0
    bounds_all = []
    for r in range(rows):
        lens = rng.uniform(0.07, 0.11, 40)
        cs = np.cumsum(lens)
        k = int(np.searchsorted(cs, 1.0))
        lens = lens[:k + 1]
        lens = lens / lens.sum()
        b = np.concatenate([[0], np.cumsum(lens)]) * n
        off = rng.uniform(0, n)
        bounds_all.append((b, off, count))
        count += len(lens)
    for r, (b, off, c0) in enumerate(bounds_all):
        m = r_idx == r
        xs = (Xw[m] - off) % n
        j = np.clip(np.searchsorted(b, xs, side="right") - 1, 0, len(b) - 2)
        sid[m] = c0 + j
        lx[m] = xs - b[j]
        sw[m] = (b[j + 1] - b[j])
    ns = count
    joint = 0.012 * ppm
    jx0 = rng.uniform(-2, 2, ns)[sid]
    jx1 = rng.uniform(-2, 2, ns)[sid]
    jy0 = rng.uniform(-2, 2, ns)[sid]
    jy1 = rng.uniform(-2, 2, ns)[sid]
    dx = np.minimum(lx - joint / 2 - jx0, sw - joint / 2 - lx - jx1)
    dy = np.minimum(ly - joint / 2 - jy0, rh - joint / 2 - ly - jy1)
    # rounded-rectangle SDF (corners rounded, more for worn setts)
    rr = rng.uniform(6, 14, ns)[sid]
    qx, qy = rr - dx, rr - dy
    sdf = rr - np.sqrt(np.clip(qx, 0, None) ** 2 + np.clip(qy, 0, None) ** 2) - np.maximum(np.minimum(qx, qy), 0) * 0
    sdf = np.where((qx < 0) & (qy < 0), np.minimum(dx, dy), sdf)
    sdf = sdf - np.clip(spectral(rng, beta=2.0, fmin=20) * 2.0, 0, None)
    mask = smoothstep(-0.5, 1.0, sdf)
    size = np.minimum(sw, rh) * 0.5
    dome = np.sqrt(np.clip(sdf / (size * 0.9), 0, 1))
    tilt = (rng.normal(0, 1, ns)[sid] * (lx / sw - 0.5) + rng.normal(0, 1, ns)[sid] * (ly / rh - 0.5)) * 0.003
    sett_h = dome * 0.014 + tilt + rng.normal(0, 0.002, ns)[sid] + spectral(rng, beta=1.8, fmin=40) * 0.0005
    joint_h = -0.006 + spectral(rng, beta=2.2, fmin=10) * 0.002
    h = mix(joint_h, sett_h, mask)
    h += spectral(rng, beta=3.4, fmin=1, fmax=10) * 0.01   # settlement / undulation
    stones = ["#6c6862", "#77736b", "#615e59", "#7e786d", "#6a645b", "#5a5854", "#827a6c", "#6f6a64", "#5f5a52"]
    sc = np.array([hexlin(stones[i]) for i in rng.integers(len(stones), size=ns)], np.float32)
    sc *= np.exp(rng.normal(0, 0.08, (ns, 1)))
    grain = norm01(spectral(rng, beta=1.4, fmin=60))
    scol = sc[sid] * (0.85 + 0.25 * grain)[..., None]
    mud = ramp(norm01(spectral(rng, beta=2.2, fmin=8)), [(0, "#3a3127"), (1, "#54473a")])
    scol = mix(scol, mud, np.clip(1 - dome * 2.2, 0, 1) * 0.55)
    col = mix(mud, scol, mask)
    film = smoothstep(0.55, 0.85, norm01(spectral(rng, beta=2.4, fmin=4)))
    col = mix(col, mud * 1.1, film * 0.35 * mask)
    col = col * 0.82                                           # wet darkening
    lvl = np.percentile(h, 11)
    water = smoothstep(lvl + 0.0005, lvl - 0.001, h)
    h = np.where(water > 0, h * (1 - water) + lvl * water, h)
    col = mix(col, col * 0.6, water)
    rough = mix(0.45, 0.3 + 0.15 * (1 - dome), mask) + 0.08 * film * mask
    rough = mix(rough, 0.06, water)
    rough = np.clip(rough + 0.03 * spectral(rng, beta=1.8, fmin=20), 0.04, 0.8)
    return Material(name, tile_m, col, h, rough, ao_radii_m=(0.004, 0.015, 0.05), ao_strength=1.1)


SETS = {
    "brick_french": (brick_french, 1.0, "Hand-made red-brown French farmhouse brick, running bond (16 courses x 4 bricks "
                                        "per tile), recessed lime mortar, soot, efflorescence, damaged bricks."),
    "plaster_damaged": (plaster_damaged, 2.0, "Lime plaster over rubble-stone masonry, flaking to expose the stones, "
                                              "cracks, water run-down stains (V = up)."),
    "roof_tiles": (roof_tiles, 1.0, "Terracotta interlocking 'tuiles mécaniques' (5 x 3 tiles per tile), moss and "
                                    "lichen, dirt in the flutes; eaves/down-slope towards V=0 (image bottom)."),
    "cobblestone_wet": (cobblestone_wet, 2.0, "Wet worn grey setts in irregular courses along U, mud joints, puddles "
                                              "(roughness ~0.06)."),
}
