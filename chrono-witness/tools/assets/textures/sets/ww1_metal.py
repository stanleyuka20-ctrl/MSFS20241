"""WWI metals: corrugated_iron (rusted galvanised sheet), rusty_steel."""
from __future__ import annotations

import numpy as np

from lib.core import (N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral, stamp,
                      uv, worley)
from lib.elements import voronoi_chunks
from lib.pbr import Material

RUST_STOPS = [(0.0, "#2c1e16"), (0.25, "#44291b"), (0.5, "#5c3620"), (0.72, "#744326"), (0.88, "#8a5530"),
              (1.0, "#857052")]


def _rust_colour(rng, n=N):
    t = norm01(spectral(rng, beta=2.4, fmin=3)) * 0.65 + 0.35 * norm01(spectral(rng, beta=1.6, fmin=30))
    c = ramp(t, RUST_STOPS)
    speck = norm01(spectral(rng, beta=0.8, fmin=150))
    c = c * (0.85 + 0.3 * speck[..., None])
    return c, t


def _pits(rng, n, count, r_range, depth):
    h = np.zeros((n, n), np.float32)
    for i in range(count):
        x, y = rng.uniform(0, n, 2)
        r = np.exp(rng.uniform(np.log(r_range[0]), np.log(r_range[1])))
        R = int(r * 2.5) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        d2 = (xx ** 2 + yy ** 2) / (r * r)
        spr = -np.exp(-d2 * 1.5) + 0.25 * np.exp(-((np.sqrt(d2) - 1.1) ** 2) / 0.08)  # crater with rim
        stamp(h, (spr * depth * rng.uniform(0.5, 1.2) * (r / r_range[1]) ** 0.5).astype(np.float32), x, y, mode="add")
    return h


def corrugated_iron(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    pitch_count = 13  # 76.9 mm pitch, ridges vertical (along V)
    phase = TAU * pitch_count * u
    A = 0.0095
    h = A * np.cos(phase)
    h += spectral(rng, beta=3.6, fmin=1, fmax=8) * 0.003
    for i in range(5):  # dents
        cx, cy = rng.uniform(0, n, 2)
        r = rng.uniform(0.03, 0.09) * ppm
        X, Y = np.meshgrid(np.arange(n), np.arange(n))
        dx = (X - cx + n / 2) % n - n / 2
        dy = (Y - cy + n / 2) % n - n / 2
        h -= np.exp(-(dx ** 2 + dy ** 2) / (r * r)) * rng.uniform(0.002, 0.006)
    trough = smoothstep(0.3, -0.8, np.cos(phase))
    # rust distribution: patches + vertical run-off + more in troughs + rust along nail row
    patches = norm01(spectral(rng, beta=2.6, fmin=2)) * 0.6 + 0.4 * norm01(spectral(rng, beta=2.0, fmin=10))
    runs = norm01(spectral(rng, beta=2.2, fmin=3, stretch=(0.08, 1.0)))
    nail_y = 0.1
    nail_band = np.exp(-(((v - nail_y + 0.5) % 1.0 - 0.5) / 0.05) ** 2)
    rust_f = patches * 0.55 + runs * 0.35 + trough * 0.15 + nail_band * 0.08
    edge_noise = spectral(rng, beta=1.4, fmin=40) * 0.035
    rust = smoothstep(0.36, 0.40, rust_f + edge_noise)
    white = smoothstep(0.28, 0.35, rust_f + edge_noise) * (1 - rust)          # zinc oxide halo
    # galvanised spangle
    d, idx, _ = worley(rng, npts=2600, k=1)
    sp_val = rng.uniform(-1, 1, 2600)[idx[..., 0]].astype(np.float32)
    zinc = hexlin("#7d7f80") * (1 + 0.07 * sp_val)[..., None]
    zinc = mix(zinc, hexlin("#5e6062"), smoothstep(0.4, 0.9, norm01(spectral(rng, beta=2.5, fmin=4))) * 0.6)
    rc, rt = _rust_colour(rng)
    rc = mix(rc, hexlin("#3a2618"), trough * 0.3)
    col = mix(zinc, hexlin("#9c9a92"), white * 0.85)
    col = mix(col, rc, rust)
    # rust run-off stains on the zinc
    stain = smoothstep(0.55, 0.9, runs) * (1 - rust) * 0.6
    col = mix(col, hexlin("#7a4a2a"), stain)
    metal = (1 - rust) * (1 - white * 0.9) * (1 - stain * 0.8)
    # rust relief: scale + pits + blistered edge
    flakes = voronoi_chunks(rng, 3000, n=n, gap=(0.0, 0.15), bevel=0.5, tilt=0.4, keep=0.8, jitter=0.9)
    h += rust * (flakes["h"] * 0.00025 + spectral(rng, beta=1.8, fmin=30) * 0.00012)
    h += _pits(rng, n, 2500, (1.0, 4.0), 0.0004) * rust
    h += rust * 0.00012
    # nail heads on every second crest
    for k in range(0, pitch_count, 2):
        x = (k / pitch_count) * n
        y = nail_y * n + rng.normal(0, 1.5)
        R = 9
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        dd = np.sqrt(xx ** 2 + yy ** 2)
        head = smoothstep(5.5, 4.5, dd)
        stamp(h, (head * 0.0015 * np.sqrt(np.clip(1 - (dd / 5.5) ** 2, 0, 1))).astype(np.float32), x, y, mode="add")
        stamp(col, np.zeros((2 * R + 1, 2 * R + 1, 3), np.float32) + hexlin("#3a2417"), x, y, mode="over",
              alpha=np.clip(head + smoothstep(9, 5, dd) * 0.6, 0, 1))
        stamp(metal, np.zeros((2 * R + 1, 2 * R + 1), np.float32), x, y, mode="over", alpha=smoothstep(9, 5, dd))
    rough = mix(0.5 + 0.06 * sp_val + 0.12 * norm01(spectral(rng, beta=2, fmin=8)), 0.8, white)
    rough = mix(rough, 0.82 + 0.1 * norm01(spectral(rng, beta=1.8, fmin=20)), np.maximum(rust, stain * 0.7))
    return Material(name, tile_m, col, h, np.clip(rough, 0.3, 0.95), metal=np.clip(metal, 0, 1),
                    ao_radii_m=(0.002, 0.008, 0.03), ao_strength=0.7)


def rusty_steel(name, tile_m):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    h = spectral(rng, beta=3.4, fmin=1, fmax=16) * 0.0006
    # flaking rust scale: plates with lifted edges
    fl = voronoi_chunks(rng, 900, n=n, gap=(0.0, 0.12), bevel=0.3, tilt=0.8, keep=0.85, jitter=0.95)
    scale_mask = smoothstep(0.35, 0.65, norm01(spectral(rng, beta=2.6, fmin=3)))
    h += fl["h"] * 0.00045 * scale_mask
    # blisters
    bl = np.zeros((n, n), np.float32)
    for i in range(120):
        x, y = rng.uniform(0, n, 2)
        r = rng.uniform(4, 18)
        R = int(r * 1.6) + 2
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        dd = np.sqrt(xx ** 2 + yy ** 2) / r
        stamp(bl, (np.sqrt(np.clip(1 - dd ** 2, 0, 1)) * rng.uniform(0.5, 1)).astype(np.float32), x, y, mode="max")
    h += bl * 0.0004
    cl = norm01(spectral(rng, beta=2.6, fmin=3))
    pits = _pits(rng, n, 5000, (1.0, 6.0), 0.0006) * (0.3 + 1.0 * cl)
    h += pits
    h += spectral(rng, beta=1.6, fmin=40) * 0.00004
    rc, rt = _rust_colour(rng)
    # darker rust in pits, brighter orange on exposed flake tops, ochre powder
    pit_m = np.clip(-pits / 0.0003, 0, 1)
    rc = mix(rc, hexlin("#3a2216"), pit_m * 0.5)
    rc = mix(rc, hexlin("#9b5a2b"), np.clip(fl["h"] - 0.8, 0, 1) * scale_mask * 0.6)
    ochre = smoothstep(0.65, 0.9, norm01(spectral(rng, beta=2.2, fmin=6)))
    rc = mix(rc, hexlin("#93703f"), ochre * 0.35)
    # remnants of black mill scale / old paint
    scale_rem = smoothstep(0.74, 0.8, norm01(spectral(rng, beta=2.8, fmin=3)) + spectral(rng, beta=1.4, fmin=40) * 0.04)
    col = mix(rc, hexlin("#3b3430") * (0.9 + 0.2 * norm01(spectral(rng, beta=1.5, fmin=50)))[..., None], scale_rem)
    # bright scratches / wear to bare steel
    sc = np.zeros((n, n), np.float32)
    for i in range(12):
        x0, y0 = rng.uniform(0, n, 2)
        ang = rng.uniform(0, np.pi)
        L = rng.uniform(15, 80)
        t = np.linspace(0, 1, int(L))
        for tt in t:
            xx = int(x0 + np.cos(ang) * L * tt) % n
            yy = int(y0 + np.sin(ang) * L * tt) % n
            sc[yy, xx] = max(sc[yy, xx], np.sin(np.pi * tt) * rng.uniform(0.5, 1.0))
    sc = np.clip(blur(sc, 0.5) * 2.0, 0, 1)
    worn = smoothstep(0.8, 0.86, norm01(spectral(rng, beta=2.4, fmin=5)) + spectral(rng, beta=1.4, fmin=40) * 0.03)
    bare = np.clip(sc + worn * 0.9, 0, 1)
    col = mix(col, hexlin("#a7a7a3") * (0.9 + 0.15 * norm01(spectral(rng, beta=1.2, fmin=60)))[..., None], bare)
    h -= sc * 0.00006
    metal = bare
    rough = 0.86 + 0.08 * norm01(spectral(rng, beta=1.8, fmin=20)) - 0.1 * pit_m * 0
    rough = mix(rough, 0.55, scale_rem)
    rough = mix(rough, 0.38, bare)
    return Material(name, tile_m, col, h, np.clip(rough, 0.3, 0.97), metal=metal,
                    ao_radii_m=(0.0008, 0.003, 0.01), ao_strength=0.9)


SETS = {
    "corrugated_iron": (corrugated_iron, 1.0, "Galvanised corrugated sheet, 13 corrugations per tile (~76 mm pitch), "
                                              "ridges along V; heavy rust (metalness 0) over zinc (metalness 1), "
                                              "nail row at V≈0.9. Corrugation is in the normal map only."),
    "rusty_steel": (rusty_steel, 0.5, "Pitted, flaking rusty steel with mill-scale remnants and bare-metal "
                                      "scratches (metalness 1 only there)."),
}
