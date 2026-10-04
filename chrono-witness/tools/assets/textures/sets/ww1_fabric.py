"""WWI textiles: sandbag (hessian), canvas_tent."""
from __future__ import annotations

import numpy as np

from lib.core import N, TAU, bandnoise, blur, hexlin, mix, norm01, ramp, rng_for, smoothstep, spectral, stamp, uv
from lib.pbr import Material
from lib.strokes import StrokeCanvas
from lib.weave import plain_weave


def sandbag(name, tile_m):
    """Coarse jute hessian (~4.5 threads/cm), wet and mud-stained, one stitched seam along U."""
    return hessian(name, tile_m, dry=False)


def sandbag_dry(name, tile_m):
    """Newer, dry hessian (London 1940): lighter jute, dusty rather than muddy."""
    return hessian(name, tile_m, dry=True)


def hessian(name, tile_m, dry=False):
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    W = plain_weave(rng, n_warp=224, n_weft=200, width=0.86, crimp=0.4, wander=0.3, slub=0.35, twist=0.5,
                    hair=0.3)
    pitch_m = tile_m / 212
    h = W["h"] * pitch_m * 0.8
    # cloth-scale wrinkles / bag bulges
    wr = spectral(rng, beta=3.4, fmin=1, fmax=30)
    crease = blur((1 - np.abs(bandnoise(rng, f=5, width=0.4, stretch=(1, 3), angle=rng.uniform(0, np.pi)))) ** 4, 3)
    h = h + wr * 0.004
    # seam: folded double layer band + heavy twine stitches crossing it
    u, v = uv(n)
    yc = 0.78 + 0.004 * np.sin(TAU * u * 2 + 1.0)
    dseam = (v - yc) * tile_m
    band = smoothstep(0.012, 0.006, np.abs(dseam))
    fold = np.exp(-(dseam / 0.004) ** 2)
    h = h + band * 0.0015 + fold * 0.0012 - np.exp(-((np.abs(dseam) - 0.013) / 0.002) ** 2) * 0.001
    sc = StrokeCanvas(n, {"h": 0.0, "a": 0.0}, ss=2)
    step = 0.009 * ppm
    for k in range(int(n / step)):
        x = k * step + rng.normal(0, 0.8)
        y = (0.78 + 0.004 * np.sin(TAU * (x / n) * 2 + 1.0)) * n
        p0 = np.array([x - 0.004 * ppm, y - 0.008 * ppm])
        p1 = np.array([x + 0.004 * ppm, y + 0.008 * ppm])
        pts = np.linspace(p0, p1, 6)
        sc.ribbon(pts, np.full(6, 0.0022 * ppm), lambda i, t: {"h": np.sin(np.pi * t) * 0.8 + 0.2, "a": 1.0})
    st_a, st_h = sc.get("a"), sc.get("h")
    h = h + st_h * 0.0012
    # --- colour: jute fibres vary thread to thread
    tid = W["tid"]
    tone = np.exp(rng.normal(0, 0.12, 200001))[np.clip(tid, 0, 200000)].astype(np.float32)
    fib = spectral(rng, beta=1.5, fmin=60)
    jute_stops = [(0, "#9a8458"), (0.5, "#ab9465"), (1, "#b9a274")] if dry else \
        [(0, "#7b6646"), (0.5, "#8c7650"), (1, "#9a845c")]
    jute = ramp(norm01(spectral(rng, beta=2.2, fmin=6)), jute_stops)
    col = jute * tone[..., None] * (0.9 + 0.1 * fib[..., None])
    th = norm01(W["h"])
    col = col * (0.65 + 0.35 * th[..., None])  # fibres in the crossings are shadowed
    # through the gaps you see the bag's earth fill
    fill = hexlin("#4a4031") if dry else hexlin("#2e261d")
    col = mix(col, fill, W["gap"].astype(np.float32) * 0.85)
    # wet: big darker patches, glossier; mud stains clogging the weave
    wet = smoothstep(0.35, 0.8, norm01(spectral(rng, beta=3.0, fmin=2)))
    if dry:
        wet = wet * 0.12  # only faint damp/handling marks
    col = col * (1 - 0.45 * wet[..., None])
    mud_m = smoothstep(0.55, 0.85, norm01(spectral(rng, beta=2.6, fmin=3)) + 0.15 * spectral(rng, beta=1.8, fmin=20))
    mudc = ramp(norm01(spectral(rng, beta=2, fmin=8)), [(0, "#3d3328"), (1, "#5a4c3b")])
    if dry:  # brick dust / grime instead of mud, much less of it
        mudc = ramp(norm01(spectral(rng, beta=2, fmin=8)), [(0, "#7a6d5c"), (1, "#8f8373")])
        mud_m = mud_m * 0.5
    clog = mud_m * (1 - th * 0.5)
    col = mix(col, mudc, np.clip(clog, 0, 1) * 0.85)
    h = h + mud_m * 0.0008 * (1 - th)
    # stitch twine colour (lighter, less soiled)
    col = mix(col, (hexlin("#a49478") if dry else hexlin("#7a6b52")) * (1 - 0.4 * wet[..., None]) * (0.8 + 0.3 * norm01(st_h))[..., None],
              st_a * 0.85)
    rough = 0.9 - 0.25 * wet - 0.15 * mud_m * wet + 0.03 * fib + (0.02 if dry else 0.0)
    return Material(name, tile_m, col, h, np.clip(rough, 0.45, 0.97), normal_strength=1.0,
                    ao_radii_m=(0.0008, 0.003, 0.012), ao_strength=0.9)


def canvas_tent(name, tile_m):
    """Weathered khaki/off-white cotton duck canvas, water stains, felled seam along U."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    u, v = uv(n)
    # weave far below pixel size -> fine anisotropic fabric grain + slight cross-hatch
    fine = bandnoise(rng, f=n * 0.35, width=0.25, stretch=(1.0, 0.1)) + \
        bandnoise(rng, f=n * 0.33, width=0.25, stretch=(0.1, 1.0))
    slubs = spectral(rng, beta=1.5, fmin=40, stretch=(10, 1)) * 0.5 + spectral(rng, beta=1.5, fmin=40, stretch=(1, 10)) * 0.5
    # tension wrinkles and sag
    wr = 0.0
    for i in range(3):
        b = bandnoise(rng, f=rng.uniform(2, 4), width=0.35, stretch=(1, 3), angle=rng.uniform(0, np.pi))
        wr = wr + (1 - np.abs(b)) ** 2 * rng.uniform(0.5, 1.0)
    wr = blur(wr, 5)
    h = fine * 0.00003 + slubs * 0.00004 + wr * 0.0015 + spectral(rng, beta=3.5, fmin=1, fmax=12) * 0.006
    # felled seam: overlapped band ~2 cm with two stitch rows
    yc = 0.3
    d = (v - yc) * tile_m
    band = smoothstep(0.012, 0.009, np.abs(d))
    h = h + band * 0.0016 + np.exp(-(d / 0.005) ** 2) * 0.0003
    stitches = np.zeros((n, n), np.float32)
    for row in (-0.0065, 0.0065):
        yr = (yc + row / tile_m) * n
        step = 0.0035 * ppm
        for k in range(int(n / step)):
            x = (k + 0.5) * step
            spr = np.zeros((5, 7), np.float32)
            yy, xx = np.mgrid[0:5, 0:7].astype(np.float32)
            spr = np.exp(-(((xx - 3) / 1.6) ** 2 + ((yy - 2) / 0.6) ** 2)).astype(np.float32)
            stamp(stitches, spr, x, yr, mode="max")
    h = h + stitches * 0.0003 - np.exp(-((np.abs(d) - 0.0065) / 0.0008) ** 2) * 0.0002
    # --- colour
    base = ramp(norm01(spectral(rng, beta=2.8, fmin=2)), [(0, "#9e8e68"), (0.5, "#ad9d76"), (1, "#bbab84")])
    base = base * (0.96 + 0.06 * slubs[..., None])
    # water stains: tide-line rings with darker edges
    stains = np.zeros((n, n), np.float32)
    rings = np.zeros((n, n), np.float32)
    X, Y = np.meshgrid(np.arange(n), np.arange(n))
    for i in range(6):
        cx, cy = rng.uniform(0, n, 2)
        r = rng.uniform(0.06, 0.2) * n
        dx = (X - cx + n / 2) % n - n / 2
        dy = (Y - cy + n / 2) % n - n / 2
        el = rng.uniform(0.5, 1.0)
        th = np.arctan2(dy, dx)
        rr = np.sqrt(dx ** 2 + (dy / el) ** 2)
        lob = 1.0
        for k in range(2, 7):
            lob = lob + rng.uniform(0.03, 0.12) / k * 3 * np.cos(k * th + rng.uniform(0, TAU))
        wob = blur(rng.standard_normal((n, n)).astype(np.float32), 6)
        wob /= wob.std() + 1e-6
        edge = r * lob + wob * 3.0
        inside = smoothstep(edge + 3, edge - 6, rr)
        arc = smoothstep(-0.3, 0.6, np.cos(th - rng.uniform(0, TAU)))  # tide line only on part of the rim
        stains = np.maximum(stains, inside * rng.uniform(0.3, 0.7))
        rings = np.maximum(rings, np.exp(-((rr - edge) / 3.5) ** 2) * rng.uniform(0.3, 0.7) * arc)
    # vertical run-down streaks
    streak = smoothstep(0.6, 0.95, norm01(spectral(rng, beta=2.6, fmin=2, stretch=(0.15, 1.0))))
    base = base * (1 - 0.1 * stains[..., None] - 0.18 * rings[..., None] - 0.12 * streak[..., None])
    base = mix(base, hexlin("#8a7a5c"), rings * 0.3)
    # mildew speckle clusters
    cluster = smoothstep(0.7, 0.95, norm01(spectral(rng, beta=2.8, fmin=3)))
    speck = (spectral(rng, beta=0.5, fmin=200) > 2.0).astype(np.float32)
    speck = blur(speck, 0.6) * cluster
    base = mix(base, hexlin("#3d3d31"), np.clip(speck * 1.5, 0, 0.8))
    # dirt in the wrinkle valleys + grime on seam
    val = smoothstep(0.0, -0.002, h - blur(h, 20))
    base = base * (1 - 0.05 * val[..., None])
    base = mix(base, hexlin("#8a7c60"), band * 0.2)
    fold_edge = np.exp(-((np.abs(d) - 0.0115) / 0.0012) ** 2)
    base = mix(base, hexlin("#6e624b"), fold_edge * 0.45)
    base = mix(base, hexlin("#c8bfa8"), stitches * 0.4)
    rough = 0.85 + 0.04 * slubs - 0.06 * stains
    return Material(name, tile_m, base, h, np.clip(rough, 0.6, 0.95), normal_strength=1.0,
                    ao_radii_m=(0.002, 0.008, 0.03), ao_strength=0.8)


SETS = {
    "sandbag": (sandbag, 0.5, "Coarse jute hessian sack weave (~4.5 threads/cm), wet, mud-clogged; one stitched seam "
                              "runs along U at V≈0.22. Bag shape comes from geometry."),
    "sandbag_dry": (sandbag_dry, 0.5, "Dry, newer jute hessian (lighter variant of sandbag), dusty not muddy; stitched "
                                      "seam along U at V≈0.22."),
    "canvas_tent": (canvas_tent, 1.5, "Weathered khaki/off-white cotton duck canvas: tension wrinkles, tide-line water "
                                      "stains, mildew, felled seam along U at V≈0.7."),
}
