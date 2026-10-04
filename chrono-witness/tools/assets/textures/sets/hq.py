"""Time-agency HQ interior: concrete_polished, concrete_board, brushed_steel, oak_veneer, acoustic_fabric."""
from __future__ import annotations

import numpy as np

from lib.core import (N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral, stamp,
                      uv, warp)
from lib.elements import voronoi_chunks
from lib.pbr import Material
from lib.wood import board_bands, periodic_grain


def _arc_swirls(rng, n, count, r_range, width):
    """Power-trowel arcs: overlapping circular arcs (periodic)."""
    out = np.zeros((n, n), np.float32)
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32)
    for i in range(count):
        cx, cy = rng.uniform(0, n, 2)
        r = rng.uniform(*r_range)
        dx = (X - cx + n / 2) % n - n / 2
        dy = (Y - cy + n / 2) % n - n / 2
        d = np.sqrt(dx ** 2 + dy ** 2)
        a0 = rng.uniform(0, TAU)
        span = rng.uniform(0.6, 2.0)
        ang = (np.arctan2(dy, dx) - a0) % TAU
        arcm = smoothstep(span, span * 0.7, ang) * smoothstep(0, 0.2, ang)
        ring = np.exp(-((d - r) / width) ** 2)
        out += ring * arcm * rng.uniform(0.3, 1.0)
    return out


def concrete_polished(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    cement = ramp(norm01(spectral(rng, beta=2.6, fmin=1)), [(0, "#77746e"), (0.5, "#85827b"), (1, "#918d85")])
    cloud = norm01(spectral(rng, beta=2.2, fmin=4))
    col = cement * (0.92 + 0.14 * cloud[..., None])
    # ground exposed aggregate: stone cross-sections (colour only; surface is polished flat)
    agg_cols = ["#4a4846", "#5d5955", "#a9a49a", "#8c7c68", "#2f2e2e", "#b8b2a6", "#6e655b", "#7d7a74"]
    for npts, keep in ((9000, 0.22), (40000, 0.28)):
        ch = voronoi_chunks(rng, npts, n=n, gap=(0.15, 0.5), bevel=0.3, tilt=0.0, keep=keep, jitter=0.95,
                            warp_px=1.2)
        npt = len(ch["pts"])
        ac = np.array([hexlin(agg_cols[i]) for i in rng.integers(len(agg_cols), size=npt)], np.float32)
        ac *= np.exp(rng.normal(0, 0.1, (npt, 1)))
        col = mix(col, ac[ch["cid"]] * (0.92 + 0.12 * cloud[..., None]), ch["mask"] * 0.9)
    fines = spectral(rng, beta=0.4, fmin=200)
    col = col * (1 + 0.06 * fines[..., None])
    # pinholes / air voids
    voids = np.zeros((n, n), np.float32)
    for i in range(500):
        x, y = rng.uniform(0, n, 2)
        r = np.exp(rng.normal(0.0, 0.4))
        R = int(r * 2) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        stamp(voids, smoothstep(r + 0.5, r - 0.5, np.sqrt(xx ** 2 + yy ** 2)).astype(np.float32), x, y, mode="max")
    col = mix(col, hexlin("#3a3835"), voids * 0.7)
    # hairline cracks
    cr = np.abs(bandnoise(rng, f=3, width=0.5))
    crack = smoothstep(0.012, 0.0, cr) * smoothstep(0.6, 0.8, norm01(spectral(rng, beta=2.5, fmin=2)))
    col = mix(col, hexlin("#55524d"), crack * 0.6)
    trowel = _arc_swirls(rng, n, 140, (40, 160), 6.0)
    trowel = trowel / (trowel.max() + 1e-6)
    h = spectral(rng, beta=3.5, fmin=1, fmax=10) * 0.0008 + trowel * 0.00004 - voids * 0.0006 - crack * 0.0003
    wear = norm01(spectral(rng, beta=2.8, fmin=2))
    rough = 0.24 + 0.1 * wear + 0.06 * trowel + 0.04 * norm01(spectral(rng, beta=1.6, fmin=30)) + 0.3 * voids
    col = col * (1 - 0.04 * trowel[..., None])
    return Material(name, tile_m, col, h, np.clip(rough, 0.12, 0.7), ao_radii_m=(0.003, 0.01, 0.03),
                    ao_strength=0.5)


def concrete_board(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    nb = 16                      # 15 cm boards
    bid, vin, dist, edges = board_bands(n, nb, 0)
    F = periodic_grain(rng, ring_px=9, wander=40, knots=10, knot_r=(5, 14), stretch=7)
    late = np.zeros((n, n), np.float32)
    knot = np.zeros((n, n), np.float32)
    off = np.zeros((n, n), np.float32)
    tone = np.zeros((n, n), np.float32)
    for b in range(nb):
        rows = slice(edges[b], edges[b + 1])
        ry, rx = rng.integers(0, n, 2)
        late[rows] = np.roll(np.roll(F["late"], ry, 0), rx, 1)[rows]
        knot[rows] = np.roll(np.roll(F["knot"], ry, 0), rx, 1)[rows]
        off[rows] = rng.normal(0, 0.0012)
        tone[rows] = rng.normal(0, 1)
    # board seams: slight fins (grout leak) and steps between boards
    ed = dist[:, 0:1] * np.ones((1, n), np.float32)
    fin = np.exp(-(ed / 1.2) ** 2) * (0.6 + 0.4 * norm01(spectral(rng, beta=1.8, fmin=20)))
    h = off + late * 0.0005 + knot * 0.0004 + fin * 0.0008
    h += spectral(rng, beta=1.6, fmin=50) * 0.00005
    # tie holes on a 600 mm grid (4 x 4)
    voids = np.zeros((n, n), np.float32)
    Y, X = np.mgrid[0:n, 0:n].astype(np.float32)
    g = n / 4
    for i in range(4):
        for j in range(4):
            cx = (i + 0.5) * g + rng.normal(0, 1.0)
            cy = edges[int(round((j + 0.5) * nb / 4))] + (edges[1] - edges[0]) * 0.5 + rng.normal(0, 1.0)
            R = 16
            yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
            d = np.sqrt(xx ** 2 + yy ** 2)
            cone = -0.012 * smoothstep(11, 4, d)
            stamp(h, cone.astype(np.float32), cx, cy, mode="add")
            stamp(voids, smoothstep(11, 9, d).astype(np.float32), cx, cy, mode="max")
    # bug holes
    bug = np.zeros((n, n), np.float32)
    for i in range(900):
        x, y = rng.uniform(0, n, 2)
        r = np.exp(rng.normal(0.2, 0.5))
        R = int(r * 2) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        stamp(bug, smoothstep(r + 0.5, r - 0.5, np.sqrt(xx ** 2 + (yy * 1.3) ** 2)).astype(np.float32), x, y,
              mode="max")
    h -= bug * 0.002
    base = ramp(norm01(spectral(rng, beta=2.6, fmin=1)), [(0, "#8b8882"), (0.5, "#97948d"), (1, "#a29f97")])
    col = base * (1 + 0.07 * tone[..., None]) * (1 - 0.1 * np.clip(late, 0, 1)[..., None]) * \
        (1 - 0.1 * knot[..., None])
    col = col * (0.95 + 0.08 * norm01(spectral(rng, beta=1.4, fmin=60)))[..., None]
    col = mix(col, hexlin("#6e6b66"), fin * 0.3)
    col = mix(col, hexlin("#5f5d59"), voids * 0.8)
    col = mix(col, hexlin("#55534f"), bug * 0.7)
    stain = smoothstep(0.65, 0.95, norm01(spectral(rng, beta=2.5, fmin=2, stretch=(0.2, 1))))
    col = col * (1 - 0.08 * stain[..., None])
    rough = 0.78 + 0.05 * late - 0.04 * fin + 0.1 * bug
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.95), ao_radii_m=(0.002, 0.008, 0.03),
                    ao_strength=0.9)


def brushed_steel(name, tile_m):
    rng = rng_for(name)
    n = N
    streak = spectral(rng, beta=1.2, fmin=8, stretch=(80.0, 1.0))
    fine = spectral(rng, beta=0.6, fmin=100, stretch=(40.0, 1.0))
    broad = spectral(rng, beta=2.0, fmin=2, stretch=(12.0, 1.0))
    h = streak * 0.000012 + fine * 0.000008
    smudge = smoothstep(0.55, 0.9, norm01(spectral(rng, beta=2.6, fmin=3)))
    scr = np.zeros((n, n), np.float32)
    for i in range(30):
        x0, y0 = rng.uniform(0, n, 2)
        ang = rng.normal(0, 0.25) + (0 if rng.random() < 0.6 else rng.uniform(0, np.pi))
        L = rng.uniform(20, 200)
        for t in np.linspace(0, 1, int(L)):
            xx = int(x0 + np.cos(ang) * L * t) % n
            yy = int(y0 + np.sin(ang) * L * t) % n
            scr[yy, xx] = max(scr[yy, xx], np.sin(np.pi * t) * rng.uniform(0.3, 1.0))
    scr = blur(scr, 0.5)
    h -= scr * 0.000015
    base = hexlin("#b9b9b6")
    col = base[None, None, :] * (1 + 0.06 * streak[..., None] + 0.03 * fine[..., None] + 0.03 * broad[..., None])
    col = col * np.ones((n, n, 1), np.float32)
    rough = 0.3 + 0.08 * streak + 0.04 * fine + 0.04 * broad + 0.08 * smudge - 0.05 * scr
    return Material(name, tile_m, col, h, np.clip(rough, 0.15, 0.5), metal=np.ones((n, n), np.float32),
                    ao_radii_m=(0.001, 0.003, 0.01), ao_strength=0.2)


def oak_veneer(name, tile_m):
    """Fumed dark oak veneer: flat-cut leaves 30 cm wide (seams along U), grain along U, satin lacquer."""
    rng = rng_for(name)
    n = N
    nleaf = 4
    bid, vin, dist, edges = board_bands(n, nleaf, 0)
    leaves = [periodic_grain(rng, ring_px=14, wander=45, knots=1, knot_r=(4, 8), stretch=8, ring_var=0.35,
                             latewood=0.45) for _ in range(2)]
    late = np.zeros((n, n), np.float32)
    tone = np.zeros((n, n), np.float32)
    ring = np.zeros((n, n), np.float32)
    for b in range(nleaf):
        rows = slice(edges[b], edges[b + 1])
        F = leaves[b % 2]
        ry = int(rng.integers(0, n))
        late[rows] = np.roll(F["late"], ry, 0)[rows]
        ring[rows] = np.roll(F["ring"], ry, 0)[rows]
        tone[rows] = rng.normal(0, 1)
    # ring-porous earlywood: pores = small dark dashes, densest at the start of each ring
    fracr = ring - np.floor(ring)
    early = smoothstep(0.25, 0.0, fracr) + smoothstep(0.92, 1.0, fracr)
    pores_n = spectral(rng, beta=0.2, fmin=150, stretch=(6.0, 1.0))
    pores = smoothstep(1.3, 2.2, pores_n) * (0.35 + 0.65 * early)
    pores = np.clip(pores + smoothstep(1.9, 2.6, spectral(rng, beta=0.2, fmin=150, stretch=(6, 1))) * 0.5, 0, 1)
    # medullary ray flecks (short, across the grain)
    rays = smoothstep(2.0, 2.8, spectral(rng, beta=0.3, fmin=80, stretch=(0.3, 1.0)))
    fib = spectral(rng, beta=1.5, fmin=30, stretch=(30, 1))
    base = mix(hexlin("#5a3d28"), hexlin("#352315"), np.clip(late, 0, 1))
    base = base * (1 + 0.04 * tone[..., None]) * (1 + 0.04 * fib[..., None])
    base = mix(base, hexlin("#24170e"), pores * 0.6)
    base = mix(base, hexlin("#6d5038"), rays * 0.35)
    seam = smoothstep(1.5, 0.0, dist[:, 0:1] * np.ones((1, n), np.float32))
    base = mix(base, hexlin("#2b1c12"), seam * 0.5)
    h = late * 0.00002 - pores * 0.00004 - seam * 0.00005 + spectral(rng, beta=3.2, fmin=1, fmax=8) * 0.00015
    rough = 0.36 + 0.06 * pores + 0.02 * fib
    return Material(name, tile_m, base, h, np.clip(rough, 0.25, 0.55), ao_radii_m=(0.001, 0.003, 0.01),
                    ao_strength=0.3)


def acoustic_fabric(name, tile_m):
    """Charcoal needle-felt / woven wool acoustic panel fabric."""
    rng = rng_for(name)
    n = N
    fibres = spectral(rng, beta=0.9, fmin=60)
    weave = (np.sin(TAU * np.arange(n) / 4.0)[None, :] * np.sin(TAU * np.arange(n) / 4.0)[:, None]) * 0.5
    weave = blur(weave.astype(np.float32), 0.4)
    heather = norm01(spectral(rng, beta=0.6, fmin=120))     # mixed fibre colours (heathered wool)
    pill = np.zeros((n, n), np.float32)
    for i in range(900):
        x, y = rng.uniform(0, n, 2)
        r = rng.uniform(0.8, 2.0)
        R = int(r * 2) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        stamp(pill, np.exp(-(xx ** 2 + yy ** 2) / (r * r)).astype(np.float32), x, y, mode="max")
    h = fibres * 0.00008 + weave * 0.00006 + pill * 0.00015 + spectral(rng, beta=3.0, fmin=1, fmax=10) * 0.0004
    col = mix(hexlin("#2f2f31"), hexlin("#46464a"), heather)
    col = col * (0.92 + 0.1 * norm01(spectral(rng, beta=2.4, fmin=3)))[..., None]
    col = col * (1 + 0.08 * pill[..., None])
    rough = 0.93 + 0.04 * norm01(fibres)
    return Material(name, tile_m, col, h, np.clip(rough, 0.85, 1.0), ao_radii_m=(0.0005, 0.002, 0.008),
                    ao_strength=0.6)


SETS = {
    "concrete_polished": (concrete_polished, 3.0, "Polished/sealed concrete floor with ground exposed aggregate, "
                                                  "power-trowel swirls, pinholes; roughness ~0.2-0.4."),
    "concrete_board": (concrete_board, 2.4, "Board-formed architectural concrete: 16 x 150 mm boards along U with "
                                            "wood-grain imprint, fins, 600 mm tie-hole grid, bug holes."),
    "brushed_steel": (brushed_steel, 1.0, "Brushed stainless steel, metalness 1, brushing along U (anisotropic "
                                          "streaks in roughness/normal)."),
    "oak_veneer": (oak_veneer, 1.2, "Fumed dark-oak flat-cut veneer, 4 leaves of 30 cm per tile (seams and grain "
                                    "along U), pores and ray flecks, satin lacquer."),
    "acoustic_fabric": (acoustic_fabric, 1.0, "Charcoal heathered wool/felt acoustic panel fabric, very rough."),
}
