"""WWI timber: wood_planks, wood_beam, crate_wood, wicker_hurdle. Grain runs along U (x)."""
from __future__ import annotations

import cv2
import numpy as np

from lib.core import (N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral,
                      stamp, uv)
from lib.pbr import Material
from lib.wood import board_bands, periodic_grain


def _board_field(F, j, stretch):
    """Resample periodic field F (n x n) as a board starting at column j with a butt joint there."""
    n = F.shape[1]
    t = (np.arange(n) - j) % n
    cols = (np.floor(t * stretch).astype(int)) % n
    return F[:, cols]


def _nail(h, col, rough, metal, x, y, r_px, rng, ppm, streak=True, rust_col=None, hole=False, streak_len=1.0):
    n = h.shape[0]
    R = int(np.ceil(r_px * 2)) + 2
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    d = np.sqrt(xx ** 2 + yy ** 2)
    head = smoothstep(r_px + 0.6, r_px - 0.6, d)
    dome = np.sqrt(np.clip(1 - (d / r_px) ** 2, 0, 1))
    if hole:
        stamp(h, (-0.004 * smoothstep(r_px * 0.8, r_px * 0.3, d)).astype(np.float32), x, y, mode="add")
        stamp(col, np.zeros((2 * R + 1, 2 * R + 1, 3), np.float32) + hexlin("#2a2119"), x, y, mode="over",
              alpha=head * 0.85)
    else:
        stamp(h, (head * (0.0006 + 0.0008 * dome) + (1 - head) * 0.0).astype(np.float32), x, y, mode="add")
        nc = hexlin("#3a2a20") * (0.9 + 0.3 * rng.random())
        stamp(col, np.zeros((2 * R + 1, 2 * R + 1, 3), np.float32) + nc, x, y, mode="over", alpha=head)
        stamp(rough, np.full((2 * R + 1, 2 * R + 1), 0.8, np.float32), x, y, mode="over", alpha=head)
    # rust halo + downward streak (rows increase downward = runs down the wall)
    if streak:
        L = rng.uniform(0.04, 0.14) * ppm * streak_len
        W = r_px * rng.uniform(1.2, 2.4)
        H = int(L + 2 * R + 4)
        Wd = int(W * 3 + 6)
        yy2, xx2 = np.mgrid[0:H, 0:Wd].astype(np.float32)
        cx = Wd / 2
        prof = np.exp(-((xx2 - cx) / (W * (0.6 + yy2 / H))) ** 2)
        fade = np.exp(-yy2 / (L * 0.5)) * smoothstep(0, 3, yy2 + 3)
        wob = cv2.GaussianBlur(rng.standard_normal((H, Wd)).astype(np.float32), (0, 0), 2.0, 6.0)
        a = np.clip(prof * fade * (0.9 + 0.6 * wob), 0, 1) * rng.uniform(0.6, 0.95)
        rc = rust_col if rust_col is not None else hexlin("#6b3a1f")
        sprite = np.zeros((H, Wd, 3), np.float32) + rc
        stamp(col, sprite, x, y + H / 2 - R, mode="over", alpha=a)
        halo = np.exp(-(d / (r_px * 1.8)) ** 2) * 0.6
        stamp(col, np.zeros((2 * R + 1, 2 * R + 1, 3), np.float32) + rc, x, y, mode="over", alpha=halo * (1 - head))


def wood_planks(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    nb = 6
    gap = 6
    bid, vin, dist, edges = board_bands(n, nb, gap)
    fields = [periodic_grain(rng, ring_px=8, wander=38, knots=6, knot_r=(5, 13), stretch=7) for _ in range(2)]
    late = np.zeros((n, n), np.float32)
    knot = np.zeros((n, n), np.float32)
    kr = np.zeros((n, n), np.float32)
    fib = np.zeros((n, n), np.float32)
    joint_x = np.full(nb, -1)
    tone = np.zeros((n, n), np.float32)
    for b in range(nb):
        F = fields[b % 2]
        ry = int(rng.integers(0, n))
        j = int(rng.integers(0, n)) if rng.random() < 0.65 else -1
        joint_x[b] = j
        rows = slice(edges[b], edges[b + 1])
        for key, dst in (("late", late), ("knot", knot), ("knot_rings", kr), ("fibre", fib)):
            A = np.roll(F[key], ry, axis=0)
            A = _board_field(A, j if j >= 0 else 0, 0.83 if j >= 0 else 1.0)
            dst[rows] = A[rows]
        tone[rows] = np.exp(rng.normal(0, 0.1))
    # --- height
    edge_noise = blur(rng.standard_normal((n, n)).astype(np.float32), 3) * 4
    de = dist - gap * (vin < 0.5) + edge_noise * 0.3  # gap sits at top of each board
    # per-pixel distance to the board's joint (columns)
    X = np.arange(n)[None, :].repeat(n, 0)
    jd = np.full((n, n), 1e9, np.float32)
    for b in range(nb):
        if joint_x[b] >= 0:
            rows = slice(edges[b], edges[b + 1])
            dj = np.abs((X[rows] - joint_x[b] + n / 2) % n - n / 2).astype(np.float32)
            jd[rows] = dj
    de = np.minimum(de, jd + edge_noise * 0.3 - 1)
    board_mask = smoothstep(-0.5, 1.5, de)
    round_edge = np.sqrt(np.clip(de / 7.0, 0, 1))
    cup = 0.0015 * ((vin - 0.5) * 2) ** 2
    hb = (0.002 * round_edge + cup + late * 0.0006 + fib * 0.00006 - knot * 0.0002)
    hb += np.repeat(rng.uniform(-0.0012, 0.0012, nb), np.diff(edges))[:, None]  # board-to-board offsets
    h = np.where(board_mask > 0, hb, 0) * board_mask + (1 - board_mask) * (-0.012)
    # checks/cracks along the grain
    crack = np.zeros((n, n), np.float32)
    for i in range(16):
        b = int(rng.integers(nb))
        y0 = rng.uniform(edges[b] + 12, edges[b + 1] - 12)
        L = rng.uniform(0.05, 0.4) * ppm
        x0 = joint_x[b] + (1 if rng.random() < 0.5 else -L) if joint_x[b] >= 0 and rng.random() < 0.6 \
            else rng.uniform(0, n)
        xs = np.arange(int(L))
        ys = y0 + np.cumsum(rng.normal(0, 0.15, len(xs)))
        w = np.sin(np.pi * np.clip(xs / L, 0, 1)) ** 0.5 * rng.uniform(0.6, 1.8)
        for xi, yi, wi in zip(xs, ys, w):
            xx = int(x0 + xi) % n
            for dy in range(-2, 3):
                yy = int(round(yi)) + dy
                crack[yy % n, xx] = max(crack[yy % n, xx], np.clip(wi - abs(yi - round(yi) - dy), 0, 1))
    crack = blur(crack, 0.5)
    h -= crack * 0.003
    # --- colour (wet, weathered softwood)
    wood_lo, wood_hi = hexlin("#3f3226"), hexlin("#7a6650")
    base = mix(wood_hi, wood_lo, np.clip(late, 0, 1))
    base = base * tone[..., None] * (1 + fib[..., None] * 0.08)
    grey = smoothstep(0.35, 0.85, norm01(spectral(rng, beta=2.6, fmin=2, stretch=(4, 1))))
    base = mix(base, hexlin("#6f6a5f") * (0.85 + 0.3 * late[..., None] * 0), grey * 0.55)   # silvering
    base = mix(base, hexlin("#3c2c21"), np.clip(knot * 0.9 + kr * 0.3, 0, 1))
    base = mix(base, hexlin("#2a211a"), np.clip(crack * 1.5, 0, 1))
    # wetness / water staining: darker blotches running down
    wet = norm01(spectral(rng, beta=2.8, fmin=2, stretch=(0.4, 1.0)))
    base = base * (0.75 + 0.35 * (1 - wet))[..., None]
    rough = 0.62 - 0.18 * wet + 0.05 * late - 0.03 * spectral(rng, beta=2, fmin=30)
    # end grain darker at joints
    base = mix(base, hexlin("#33271e"), smoothstep(4, 0, jd) * 0.6)
    # gaps
    col = mix(hexlin("#1d1712"), base, board_mask)
    rough = mix(0.8, rough, board_mask)
    metal = np.zeros((n, n), np.float32)
    # nails at two studs (600 mm) + at joints
    stud_x = [rng.uniform(0.1, 0.4) * n]
    stud_x.append(stud_x[0] + n / 2)
    for b in range(nb):
        yc = [edges[b] + (edges[b + 1] - edges[b]) * f for f in (0.3, 0.72)]
        xs = list(stud_x)
        if joint_x[b] >= 0:
            xs += [joint_x[b] + 0.025 * ppm, joint_x[b] - 0.025 * ppm]
        for x in xs:
            for y in yc:
                if rng.random() < 0.08:
                    continue
                _nail(h, col, rough, metal, x + rng.normal(0, 2), y + rng.normal(0, 2), rng.uniform(3.0, 4.0),
                      rng, ppm, hole=rng.random() < 0.15)
    # mud splashes on the bottom board(s)
    bottom = smoothstep(edges[-2] - 120, n, np.arange(n, dtype=np.float32))[:, None] * np.ones((1, n), np.float32)
    splash = np.zeros((n, n), np.float32)
    for i in range(700):  # splatter: a main drop with an elongated tail and satellite droplets
        y = n - 8 - abs(rng.normal(0, 0.08)) * n
        x = rng.uniform(0, n)
        r = np.exp(rng.normal(0.4, 0.55))
        ang = -np.pi / 2 + rng.normal(0, 0.5)  # thrown upward from the ground
        for k in range(int(rng.integers(1, 6))):
            rr = r * (1.0 if k == 0 else rng.uniform(0.2, 0.6))
            off = 0 if k == 0 else rng.uniform(1.5, 5.0) * r
            cx = x + np.cos(ang + rng.normal(0, 0.3)) * off
            cy = y + np.sin(ang + rng.normal(0, 0.3)) * off
            R = int(rr * 3) + 3
            yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
            ca, sa = np.cos(ang), np.sin(ang)
            along = xx * ca + yy * sa
            across = -xx * sa + yy * ca
            el = rng.uniform(1.0, 2.2)
            dd = np.sqrt((along / el) ** 2 + across ** 2)
            edge = rr * (1 + 0.25 * np.cos(np.arctan2(across, along) * rng.integers(3, 7) + rng.uniform(0, TAU)))
            sp = smoothstep(edge + 0.6, edge - 0.6, dd)
            stamp(splash, sp.astype(np.float32), cx, cy, mode="max")
    smear = smoothstep(0.75, 1.0, bottom * (0.7 + 0.5 * norm01(spectral(rng, beta=3.0, fmin=4, stretch=(1, 0.5)))))
    mud = np.clip(splash * smoothstep(0.0, 0.3, bottom + 0.1) + smear, 0, 1)
    mudc = ramp(norm01(spectral(rng, beta=2, fmin=10)), [(0, "#3e3428"), (1, "#5a4d3d")])
    col = mix(col, mudc, mud * 0.9)
    h = h + mud * 0.0006
    rough = mix(rough, 0.45, mud)
    # damp, slightly green-tinged lower boards
    col = mix(col, col * np.array([0.8, 0.86, 0.72], np.float32), bottom * 0.6)
    rough = np.clip(rough + 0.0, 0.3, 0.9)
    return Material(name, tile_m, col, h, rough, metal=metal, ao_radii_m=(0.002, 0.008, 0.02))


def wood_beam(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    G = periodic_grain(rng, ring_px=10, wander=45, knots=5, knot_r=(12, 30), stretch=7, ring_var=0.5)
    late, knot, kr, fib = G["late"], G["knot"], G["knot_rings"], G["fibre"]
    # band-saw marks across the grain, uneven spacing and depth
    saw = bandnoise(rng, f=1.0 / 0.006 * tile_m / 1.0 * 0.5, width=0.25, stretch=(1.0, 0.02))
    saw *= 0.6 + 0.4 * norm01(spectral(rng, beta=3, fmin=2))
    fuzz = spectral(rng, beta=1.2, fmin=60, stretch=(12, 1))
    h = 0.0004 * late + 0.00045 * saw + 0.00015 * fuzz + spectral(rng, beta=3.5, fmin=1) * 0.0015
    # long drying checks with knot radial cracks
    crack = np.zeros((n, n), np.float32)
    for i in range(7):
        y0, x0 = rng.uniform(0, n, 2)
        L = rng.uniform(0.15, 0.7) * ppm
        xs = np.arange(int(L))
        ys = y0 + np.cumsum(rng.normal(0, 0.25, len(xs)))
        w = np.sin(np.pi * xs / L) ** 0.6 * rng.uniform(1.0, 3.0)
        for xi, yi, wi in zip(xs, ys, w):
            for dy in range(-3, 4):
                yy = int(round(yi)) + dy
                xx = int(x0 + xi) % n
                crack[yy % n, xx] = max(crack[yy % n, xx], np.clip(wi * 0.5 - abs(yi - round(yi) - dy) + 0.5, 0, 1))
    crack = blur(crack, 0.6)
    h -= crack * 0.006
    base = mix(hexlin("#63503c"), hexlin("#33271d"), np.clip(late * 0.9, 0, 1))
    base = base * (1 + 0.07 * fib[..., None]) * (0.9 + 0.1 * norm01(saw)[..., None])
    base = mix(base, hexlin("#2c211a"), np.clip(knot * 0.9 + kr * 0.25, 0, 1))
    base = mix(base, hexlin("#1f1813"), np.clip(crack * 1.3, 0, 1))
    damp = norm01(spectral(rng, beta=3.0, fmin=2))
    base = base * (0.7 + 0.35 * (1 - damp))[..., None]
    # mould / black water stains, grey weathered patches
    mould = smoothstep(0.7, 0.95, norm01(spectral(rng, beta=2.3, fmin=5, stretch=(2, 1))))
    base = mix(base, hexlin("#2b2a22"), mould * 0.5)
    greyp = smoothstep(0.6, 0.9, norm01(spectral(rng, beta=2.8, fmin=3, stretch=(3, 1))))
    base = mix(base, hexlin("#625b50"), greyp * 0.35)
    rough = 0.72 - 0.2 * damp + 0.06 * fuzz * 0.3 + 0.05 * crack
    return Material(name, tile_m, base, h, np.clip(rough, 0.4, 0.92), ao_radii_m=(0.002, 0.006, 0.02))


def crate_wood(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    nb = 7
    gap = 3
    bid, vin, dist, edges = board_bands(n, nb, gap)
    F = periodic_grain(rng, ring_px=7, wander=32, knots=6, knot_r=(4, 10), stretch=7)
    late = np.zeros((n, n), np.float32)
    knot = np.zeros((n, n), np.float32)
    fib = np.zeros((n, n), np.float32)
    tone = np.zeros((n, n), np.float32)
    paint_fade = np.zeros((n, n), np.float32)
    for b in range(nb):
        rows = slice(edges[b], edges[b + 1])
        ry, rx = rng.integers(0, n, 2)
        late[rows] = np.roll(np.roll(F["late"], ry, 0), rx, 1)[rows]
        knot[rows] = np.roll(np.roll(F["knot"], ry, 0), rx, 1)[rows]
        fib[rows] = np.roll(np.roll(F["fibre"], ry, 0), rx, 1)[rows]
        tone[rows] = np.exp(rng.normal(0, 0.08))
        paint_fade[rows] = rng.uniform(0, 1)
    en = blur(rng.standard_normal((n, n)).astype(np.float32), 2.5) * 3
    de = dist - gap * (vin < 0.5) + en * 0.25
    board_mask = smoothstep(-0.5, 1.5, de)
    h = (0.0012 * np.sqrt(np.clip(de / 5, 0, 1)) + late * 0.00018 + fib * 0.00005) * board_mask - \
        0.006 * (1 - board_mask)
    wood = mix(hexlin("#857661"), hexlin("#5c4e3e"), np.clip(late * 0.8, 0, 1)) * tone[..., None]
    wood = mix(wood, hexlin("#7c776c"), 0.4)  # weathered grey
    wood = mix(wood, hexlin("#3d3027"), knot * 0.8)
    # paint: faded grey-green, worn at edges/arrises, flaking in patches
    wear = norm01(spectral(rng, beta=2.6, fmin=3)) * 0.75 + 0.25 * norm01(spectral(rng, beta=1.8, fmin=25,
                                                                                  stretch=(4, 1)))
    edge_wear = smoothstep(12, 0, de) * 0.5 + smoothstep(0.6, 0.95, norm01(spectral(rng, beta=1.5, fmin=40))) * 0.4
    keep = (wear * 0.8 + edge_wear - 0.15 * late) < (0.64 - 0.12 * paint_fade)
    paint_a = blur(keep.astype(np.float32), 0.6)
    # paint edge lip: slightly thicker paint at flake edges
    lip = np.clip(blur(keep.astype(np.float32), 2.0) - paint_a, -1, 1)
    pcol = mix(hexlin("#545849"), hexlin("#6f7264"), paint_fade[..., None] * 0.6 +
               0.3 * norm01(spectral(rng, beta=2.5, fmin=6))[..., None])
    pcol = pcol * (0.95 + 0.08 * norm01(fib)[..., None]) * (1.04 - 0.1 * np.clip(late, 0, 1))[..., None]
    chalky = smoothstep(0.5, 0.9, norm01(spectral(rng, beta=2.5, fmin=3)))
    pcol = mix(pcol, hexlin("#7f8279"), chalky * 0.15)
    col = mix(wood, pcol, paint_a)
    h = h + paint_a * 0.00015 * board_mask - lip * 0.00005
    rough = mix(0.78 + 0.05 * fib, 0.62 + 0.1 * chalky, paint_a)
    # grime: dirt in gaps / near edges, dark water stains
    grime = smoothstep(6, 0, de) * 0.6 + smoothstep(0.6, 0.95, norm01(spectral(rng, beta=2.8, fmin=3))) * 0.4
    col = mix(col, hexlin("#3a3128"), np.clip(grime, 0, 1) * 0.5)
    col = mix(hexlin("#17120e"), col, board_mask)
    metal = np.zeros((n, n), np.float32)
    for x in (0.06 * n, 0.56 * n):
        for b in range(nb):
            for f in (0.3, 0.7):
                y = edges[b] + (edges[b + 1] - edges[b]) * f
                _nail(h, col, rough, metal, x + rng.normal(0, 2), y + rng.normal(0, 1.5), rng.uniform(2.6, 3.3),
                      rng, ppm, streak=rng.random() < 0.45, streak_len=0.35)
    return Material(name, tile_m, col, h, np.clip(rough, 0.35, 0.92), metal=metal,
                    ao_radii_m=(0.002, 0.006, 0.015))


def wicker_hurdle(name, tile_m):
    """Woven hazel/willow brushwood hurdle: horizontal rods woven around vertical stakes (25 cm)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    X, Y = np.meshgrid(np.arange(n, dtype=np.float32), np.arange(n, dtype=np.float32))
    n_st = 4
    sp = n / n_st
    # rods: integer count, varying diameters, positions by cumulative diameters
    nr = 30
    dia = np.exp(rng.normal(0, 0.25, nr))
    dia = dia / dia.sum() * n
    cy = np.cumsum(dia) - dia / 2
    h = np.full((n, n), -0.05, np.float32)
    col = np.zeros((n, n, 3), np.float32) + hexlin("#15110d")
    rid = np.full((n, n), -1, np.int32)
    bark = spectral(rng, beta=1.8, fmin=30, stretch=(6, 1))
    lent = (bandnoise(rng, f=150, width=0.3, stretch=(0.3, 1)) > 2.3).astype(np.float32)  # lenticels
    buds = np.zeros((n, n), np.float32)
    for i in range(500):
        x, y = rng.uniform(0, n, 2)
        r = rng.uniform(1.5, 3.5)
        R = int(r * 2) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        stamp(buds, np.exp(-((xx / (r * 1.6)) ** 2 + (yy / r) ** 2)).astype(np.float32), x, y, mode="max")
    stake_x = rng.uniform(0, sp) + np.arange(n_st) * sp
    for i in range(nr):
        phase = (i % 2) * np.pi + rng.normal(0, 0.15)
        jx = rng.uniform(0, n)
        t = ((X[0] - jx) % n) / n          # 0 at the thick butt, 1 at the thin tip of this rod
        taper = 1.0 - 0.45 * t + 0.05 * np.sin(TAU * 3 * X[0] / n + rng.uniform(0, TAU))
        r_row = dia[i] * 0.5 * taper * 1.04
        wob = np.sin(TAU * X[0] / n * rng.integers(1, 3) + rng.uniform(0, TAU)) * dia[i] * 0.22 + \
            np.sin(TAU * X[0] / n * rng.integers(3, 6) + rng.uniform(0, TAU)) * dia[i] * 0.08
        yc = cy[i] + wob
        z = 0.018 * np.cos(TAU * (X[0] - stake_x[0]) / (2 * sp) + phase)
        dy = (Y - yc[None, :] + n / 2) % n - n / 2
        inside = np.abs(dy) < r_row[None, :]
        prof = np.sqrt(np.clip(1 - (dy / r_row[None, :]) ** 2, 0, 1))
        rr_m = r_row / ppm
        hr = z[None, :] + prof * rr_m[None, :]
        take = inside & (hr > h)
        h = np.where(take, hr, h)
        rid[take] = i
        c0 = hexlin(["#5a4634", "#4e3b2c", "#665040", "#5b5045", "#6d5843", "#4a3e33", "#6a5a4c"][rng.integers(7)])
        c0 = c0 * np.exp(rng.normal(0, 0.12))
        ctip = c0 * np.array([1.15, 1.0, 0.85], np.float32)  # younger, redder tips
        cc = c0[None, None, :] + (ctip - c0)[None, None, :] * t[None, :, None]
        rc = cc * (0.85 + 0.25 * norm01(bark)[..., None]) * (0.7 + 0.3 * prof[..., None])
        rc = mix(rc, hexlin("#8a7a64"), lent * 0.5)
        peel = smoothstep(0.78, 0.92, norm01(spectral(rng, beta=2.0, fmin=12, stretch=(5, 1))))
        rc = mix(rc, hexlin("#9a8a6a"), peel * 0.5 * (rng.random() < 0.35))
        col = np.where(take[..., None], rc, col)
    # stakes (sails): vertical round poles, visible between rods when rods pass behind
    for sx in stake_x:
        rs = rng.uniform(0.022, 0.03) * ppm
        dx = (X - sx + n / 2) % n - n / 2
        prof = np.sqrt(np.clip(1 - (dx / rs) ** 2, 0, 1))
        hs = -0.004 + prof * rs / ppm * 0.6
        take = (np.abs(dx) < rs) & (hs > h)
        h = np.where(take, hs, h)
        sc = hexlin("#4d3f31")[None, None, :] * (0.8 + 0.3 * norm01(bark)[..., None]) * (0.7 + 0.3 * prof[..., None])
        col = np.where(take[..., None], sc, col)
    # twig stubs & bark texture in height
    h = h + bark * 0.0003 + lent * 0.0002 + buds * 0.0015 * (rid >= 0)
    h = blur(h, 0.6)
    depth = np.clip(-h / 0.03, 0, 1)
    col = col * (1 - 0.6 * depth[..., None])
    dirt = smoothstep(0.55, 0.9, norm01(spectral(rng, beta=2.8, fmin=3)))
    col = mix(col, hexlin("#3e3328"), dirt * 0.4)
    rough = 0.72 + 0.08 * bark * 0.3 - 0.15 * dirt * 0
    return Material(name, tile_m, col, h, np.clip(rough, 0.5, 0.9), ao_radii_m=(0.004, 0.012, 0.03),
                    ao_strength=1.3)


SETS = {
    "wood_planks": (wood_planks, 1.2, "Weathered wet softwood planks, 6 horizontal boards per tile (grain along U), "
                                      "butt joints, nails with rust streaks, mud splashes on the bottom board (V=0)."),
    "wood_beam": (wood_beam, 1.0, "Rough band-sawn timber, dark and damp, drying checks and knots; grain along U."),
    "crate_wood": (crate_wood, 1.0, "Supply-crate boards (7 per tile, grain along U), faded grey-green paint worn "
                                    "to grey wood, nails; no stencils."),
    "wicker_hurdle": (wicker_hurdle, 1.0, "Woven brushwood revetment hurdle: horizontal rods woven round 4 vertical "
                                          "stakes per tile (25 cm)."),
}
