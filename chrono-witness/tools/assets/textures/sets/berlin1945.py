"""Berlin, May 1945 (Wilhelmine tenements after the battle)."""
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
from sets.ww1_ground import _chunk_stack


def _vimg(n):
    """Image-row fraction (0 at the top = V 1, 1 at the bottom = V 0) as an n x n array."""
    return ((np.arange(n, dtype=np.float32) + 0.5) / n)[:, None] * np.ones((1, n), np.float32)


def _granite(rng, n, base="#86827d", spread=0.1):
    """Granite colour: grey ground with black biotite and pinkish feldspar specks (linear RGB)."""
    g = ramp(norm01(spectral(rng, beta=2.2, fmin=4)), [(0, "#7a7672"), (1, base)])
    s1 = smoothstep(1.4, 2.2, spectral(rng, beta=0.3, fmin=200))
    s2 = smoothstep(1.6, 2.4, spectral(rng, beta=0.3, fmin=180))
    s3 = smoothstep(1.8, 2.6, spectral(rng, beta=0.3, fmin=220))
    g = mix(g, hexlin("#2b2a29"), s1 * 0.8)
    g = mix(g, hexlin("#a08a80"), s2 * 0.5)
    g = mix(g, hexlin("#c4c0b8"), s3 * 0.6)
    return g


def _pock(h, rem, x, y, r, rng, depth):
    """Bullet strike: conical crater + irregular spalled ring of render removed (written into rem)."""
    R = int(r * 3) + 3
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    d = np.sqrt(xx ** 2 + yy ** 2)
    nz = cv2.GaussianBlur(rng.standard_normal(d.shape).astype(np.float32), (0, 0), max(1.0, r * 0.3))
    nz /= nz.std() + 1e-6
    crater = -depth * smoothstep(r, 0, d + nz * r * 0.15)
    spall = smoothstep(r * 2.2, r * 1.4, d + nz * r * 0.5)
    stamp(h, crater.astype(np.float32), x, y, mode="add")
    stamp(rem, spall.astype(np.float32), x, y, mode="max")


# --------------------------------------------------------------------------- facade render
def berlin_render_facade(name, tile_m):
    """Grey-ochre lime render, V up, moulded string courses every 0.9 m (V≈0.25 and 0.75), sooty and patchy,
    chipped to brick, bullet pocks in bursts and shrapnel gouges."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    vi = _vimg(n)
    # brick underneath (Reichsformat 250 x 65 mm, 12 mm joints)
    rows = int(round(tile_m / 0.077))
    per = int(round(tile_m / 0.262))
    Lb = courses(n, rows, [[n / per] * per] * rows, [(r % 2) * n / per / 2 for r in range(rows)])
    bs = unit_sdf(rng, Lb, 0.012 * ppm, chip=0.6)
    bin_ = smoothstep(-0.5, 1.0, bs)
    btones = ["#6a4234", "#734a3a", "#5f3c30", "#7a5240", "#58382e"]
    bcol = np.array([hexlin(btones[i]) for i in rng.integers(len(btones), size=Lb["count"])], np.float32)[Lb["sid"]]
    bcol = mix(hexlin("#7c776d"), bcol * (0.85 + 0.25 * norm01(spectral(rng, beta=2, fmin=20)))[..., None], bin_)
    brick_h = -0.016 + 0.003 * bin_
    # mouldings: profiled string course 12 cm tall
    mould = np.zeros((n, n), np.float32)
    below = np.zeros((n, n), np.float32)
    for c in (0.25, 0.75):
        d = (vi - c) * tile_m        # metres, positive = below the centre line
        prof = (0.028 * smoothstep(0.065, 0.045, np.abs(d))
                + 0.012 * np.exp(-((d + 0.035) / 0.008) ** 2)     # upper torus
                - 0.008 * np.exp(-((d - 0.02) / 0.007) ** 2)      # cove
                + 0.006 * np.exp(-((d - 0.045) / 0.005) ** 2))    # lower fillet
        mould += prof
        below = np.maximum(below, np.exp(-np.clip(d - 0.06, 0, None) / 0.25) * (d > 0.06))
    render_h = 0.0 + spectral(rng, beta=1.3, fmin=80) * 0.00012 + spectral(rng, beta=3.2, fmin=1, fmax=10) * 0.002
    render_h += mould
    # chips/loss: patchy, more along the mouldings
    loss_f = norm01(spectral(rng, beta=2.7, fmin=3)) * 0.75 + 0.25 * norm01(spectral(rng, beta=1.8, fmin=20))
    loss_f = loss_f + 0.12 * smoothstep(0.08, 0.0, np.minimum(np.abs(vi - 0.25), np.abs(vi - 0.75)) * tile_m)
    rem = smoothstep(0.8, 0.805, loss_f)
    # bullet bursts + shrapnel
    pk = np.zeros((n, n), np.float32)
    for b in range(9):
        cx, cy = rng.uniform(0, n, 2)
        spread = rng.uniform(0.08, 0.3) * ppm
        for k in range(int(rng.integers(4, 18))):
            _pock(pk, rem, cx + rng.normal(0, spread), cy + rng.normal(0, spread * 0.6),
                  rng.uniform(0.008, 0.016) * ppm, rng, rng.uniform(0.008, 0.02))
    for k in range(30):
        x, y = rng.uniform(0, n, 2)
        L = rng.uniform(0.008, 0.03) * ppm
        a = rng.uniform(0, np.pi)
        R = int(L) + 4
        yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
        al = xx * np.cos(a) + yy * np.sin(a)
        ac = -xx * np.sin(a) + yy * np.cos(a)
        nz = cv2.GaussianBlur(rng.standard_normal(al.shape).astype(np.float32), (0, 0), 1.5)
        g = smoothstep(1, 0.3, (al / L) ** 2 + (ac / (L * 0.45)) ** 2 + nz * 0.4)
        stamp(pk, (-0.005 * g).astype(np.float32), x, y, mode="add")
        stamp(rem, (g > 0.6).astype(np.float32), x, y, mode="max")
    rem = np.clip(rem, 0, 1)
    edge = np.clip(blur(rem, 1.5) - rem, 0, 1) * 2
    h = mix(render_h + pk, brick_h + np.minimum(pk, 0) * 0.3, rem) - edge * 0.002
    # colour
    rc = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#8a8170"), (0.5, "#978d78"), (1, "#a39a84")])
    rc = rc * (0.95 + 0.07 * norm01(spectral(rng, beta=1.2, fmin=90)))[..., None]
    patches = smoothstep(0.6, 0.62, norm01(spectral(rng, beta=2.8, fmin=3)))     # old repairs, other tone
    rc = mix(rc, hexlin("#8c8676"), patches * 0.7)
    soot = smoothstep(0.35, 0.9, norm01(spectral(rng, beta=2.6, fmin=2))) * 0.5 + \
        below * smoothstep(0.3, 0.9, norm01(blur(spectral(rng, beta=2.4, fmin=4, stretch=(0.2, 1.0)), 1.2, 8))) * 0.6
    rc = mix(rc, hexlin("#3a3631"), np.clip(soot, 0, 1) * 0.7)
    rc = mix(rc, hexlin("#55504a"), smoothstep(0.0, -0.004, pk) * 0.5)
    rc = mix(rc, hexlin("#b4ab95"), edge * 0.5)                                 # fresh broken edges
    col = mix(rc, bcol * 0.8 * (1 - 0.35 * np.clip(soot, 0, 1))[..., None], rem)
    rough = mix(0.88 + 0.04 * patches, 0.86, rem)
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.003, 0.012, 0.04),
                    ao_strength=1.0)


# --------------------------------------------------------------------------- sidewalk
def berlin_sidewalk(name, tile_m):
    """Berlin Gehweg: central band of large granite slabs (V 0.25-0.75, 1.5 m) with small granite mosaic
    setts either side. Map V across the sidewalk; slabs run along U. Dry, brick grit in joints."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    vi = _vimg(n)
    band = (vi > 0.25) & (vi < 0.75)
    # slabs: lengths 1.0-1.5 m along U
    ls = rng.uniform(1.0, 1.5, 6) * ppm
    k = int(np.searchsorted(np.cumsum(ls), n))
    ls = ls[:k + 1]
    ls = ls / ls.sum() * n
    Ls = courses(n, 1, [ls], [rng.uniform(0, n)])
    lx, w = Ls["lx"], Ls["w"]
    ly = (vi - 0.25) * n
    sh = 0.5 * n
    joint = 0.008 * ppm
    sdx = np.minimum(lx - joint / 2, w - joint / 2 - lx)
    sdy = np.minimum(ly - joint / 2, sh - joint / 2 - ly)
    ero = np.clip(spectral(rng, beta=2.0, fmin=12) - 0.8, 0, None) * 5 + \
        np.clip(blur(rng.standard_normal((n, n)).astype(np.float32), 1.5) * 1.5, 0, None)
    ssdf = np.minimum(sdx, sdy) - ero
    slab = smoothstep(-0.5, 1.0, ssdf) * band
    sid = Ls["sid"]
    cnt = Ls["count"]
    slab_h = 0.004 * np.sqrt(np.clip(ssdf / 6, 0, 1)) + rng.normal(0, 0.003, cnt)[sid] + \
        rng.normal(0, 0.004, cnt)[sid] * (lx / w - 0.5) + spectral(rng, beta=1.4, fmin=80) * 0.00012
    # mosaic setts (~5 cm), only outside the band
    mo = voronoi_chunks(rng, 3600, n=n, gap=(0.08, 0.2), bevel=0.6, tilt=0.4, jitter=0.85, warp_px=1.5)
    mos = mo["mask"] * (~band) * smoothstep(0.0, 0.004, np.minimum(np.abs(vi - 0.25), np.abs(vi - 0.75)))
    mo_h = mo["h"] * mo["r"] * tile_m * 0.5 + spectral(rng, beta=1.4, fmin=80) * 0.0001
    joint_h = -0.008 + spectral(rng, beta=2, fmin=15) * 0.0015
    h = joint_h + (slab_h - joint_h) * slab + (mo_h - joint_h) * mos * (1 - slab)
    h += spectral(rng, beta=3.4, fmin=1, fmax=10) * 0.006
    gran = _granite(rng, n)
    tone_s = np.exp(rng.normal(0, 0.06, cnt))[sid]
    tone_m = np.exp(rng.normal(0, 0.1, len(mo["pts"])))[mo["cid"]]
    mtint = np.array([hexlin(c) for c in rng.choice(["#8a8580", "#7e7a76", "#948d86", "#6e6b68", "#8f8378"],
                                                    len(mo["pts"]))], np.float32)[mo["cid"]]
    scol = gran * tone_s[..., None]
    mcol = mix(gran, mtint, 0.5) * tone_m[..., None]
    grit = ramp(norm01(spectral(rng, beta=1.6, fmin=40)), [(0, "#6b5a4c"), (0.5, "#8a6d58"), (1, "#9c8f80")])
    redbits = smoothstep(1.6, 2.2, spectral(rng, beta=0.4, fmin=150))
    grit = mix(grit, hexlin("#8a4a35"), redbits * 0.7)
    col = grit
    col = mix(col, mcol, mos * (1 - slab))
    col = mix(col, scol, slab)
    # dust film everywhere, heavier near joints; foot-worn cleaner path in the slab band
    dust_f = norm01(spectral(rng, beta=2.5, fmin=3))
    path = np.exp(-((vi - 0.5) / 0.15) ** 2)
    dust = np.clip(0.25 + 0.4 * dust_f - 0.25 * path, 0, 1)
    col = mix(col, hexlin("#9a9184"), dust * 0.45)
    near = smoothstep(4, 0, np.where(band, ssdf, mo["ins"] / mo["r"] * 12))
    col = mix(col, grit, near * 0.35)
    rough = 0.72 + 0.12 * dust - 0.08 * path * slab + 0.1 * (1 - np.maximum(slab, mos))
    return Material(name, tile_m, col, h, np.clip(rough, 0.5, 0.95), ao_radii_m=(0.003, 0.01, 0.03),
                    ao_strength=1.0)


# --------------------------------------------------------------------------- cobbles
def berlin_cobbles(name, tile_m):
    """Dry grey granite setts (Kopfsteinpflaster) in courses along U, dusty sand/brick-dust joints."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    rows = 14
    wx = spectral(rng, beta=2.8, fmin=3) * 5.0
    wy = spectral(rng, beta=2.8, fmin=3) * 4.0
    lens = []
    for r in range(rows):
        ls = rng.uniform(0.13, 0.2, 30) * ppm
        k = int(np.searchsorted(np.cumsum(ls), n))
        ls = ls[:k + 1]
        lens.append(ls / ls.sum() * n)
    L = courses(n, rows, lens, [rng.uniform(0, n) for _ in range(rows)], wx, wy)
    sid, ns = L["sid"], L["count"]
    joint = 0.014 * ppm
    sdf = unit_sdf(rng, L, joint, chip=0.8, jitter=2.0)
    rr = rng.uniform(6, 14, ns)[sid]
    sdf = sdf - np.clip(spectral(rng, beta=2.0, fmin=20) * 2.0, 0, None)
    mask = smoothstep(-0.5, 1.0, sdf)
    size = np.minimum(L["w"], L["h"]) * 0.5
    dome = np.sqrt(np.clip(sdf / (size * 0.9), 0, 1))
    tilt = (rng.normal(0, 1, ns)[sid] * (L["lx"] / L["w"] - 0.5) + rng.normal(0, 1, ns)[sid] *
            (L["ly"] / L["h"] - 0.5)) * 0.003
    sett_h = dome * 0.016 + tilt + rng.normal(0, 0.002, ns)[sid] + spectral(rng, beta=1.8, fmin=40) * 0.0005
    joint_h = -0.01 + spectral(rng, beta=2.2, fmin=10) * 0.002
    h = mix(joint_h, sett_h, mask) + spectral(rng, beta=3.4, fmin=1, fmax=10) * 0.01
    gran = _granite(rng, n, base="#8e8a85")
    tint = np.array([hexlin(c) for c in rng.choice(["#8a8784", "#7a7672", "#959089", "#6c6a68", "#8d8379",
                                                    "#7f7d7c"], ns)], np.float32)[sid]
    scol = mix(gran, tint, 0.45) * np.exp(rng.normal(0, 0.07, ns))[sid][..., None]
    # polished crowns (lighter, smoother), dust around the shoulders
    joint_col = ramp(norm01(spectral(rng, beta=2, fmin=10)), [(0, "#7d6f5f"), (0.6, "#968a7a"), (1, "#a49a8c")])
    joint_col = mix(joint_col, hexlin("#86503c"), smoothstep(1.6, 2.2, spectral(rng, beta=0.4, fmin=150)) * 0.6)
    scol = mix(scol, joint_col, np.clip(1 - dome * 2.2, 0, 1) * 0.5)
    col = mix(joint_col, scol, mask)
    film = smoothstep(0.45, 0.9, norm01(spectral(rng, beta=2.4, fmin=3)))
    col = mix(col, hexlin("#9b9285"), film * 0.3)
    rough = mix(0.88, 0.62 - 0.12 * dome, mask) + 0.1 * film
    return Material(name, tile_m, col, h, np.clip(rough, 0.4, 0.95), ao_radii_m=(0.004, 0.015, 0.05),
                    ao_strength=1.1)


# --------------------------------------------------------------------------- rubble
def rubble_brick_plaster(name, tile_m):
    """Heap of broken red brick, plaster lumps, mortar, splinters and dust (lighter than stone_rubble)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    h = spectral(rng, beta=3.3, fmin=1) * 0.05 + spectral(rng, beta=2.2, fmin=12, fmax=300) * 0.0012
    dust = hexlin("#a39a8c")
    col = ramp(norm01(spectral(rng, beta=2.5, fmin=3)), [(0, "#7e7568"), (0.5, "#91887b"), (1, "#a49b8d")])
    rough = np.full((n, n), 0.9, np.float32)
    layers = [dict(npts=55, keep=0.6, gap=(0.06, 0.4), lift=(0.15, 0.5), tilt=0.9),
              dict(npts=360, keep=0.65, gap=(0.06, 0.4), lift=(0.2, 0.6), tilt=0.9),
              dict(npts=2300, keep=0.6, gap=(0.08, 0.45), lift=(0.3, 0.7), tex=0.06),
              dict(npts=12000, keep=0.45, gap=(0.1, 0.5), lift=(0.3, 0.8), tex=0.06)]
    kf = 0.5 + 0.9 * norm01(spectral(rng, beta=3.2, fmin=2))
    h, win, infos = _chunk_stack(rng, h, tile_m, layers, keep_field=kf)
    probs = np.array([0.55, 0.25, 0.12, 0.08])          # brick, plaster, mortar, roof tile
    cols = {0: ["#7e4a39", "#875443", "#724536", "#8e5c48", "#7a5244"], 1: ["#c9c1b2", "#d2cbbd", "#bdb5a6"],
            2: ["#a39d92", "#968f84"], 3: ["#8f5240", "#7c4636"]}
    for li, ch in enumerate(infos):
        sel = win == li
        npt = len(ch["pts"])
        cls = rng.choice(4, npt, p=probs)
        base = np.array([hexlin(cols[c][rng.integers(len(cols[c]))]) for c in cls], np.float32)
        base *= np.exp(rng.normal(0, 0.07, (npt, 1)))
        ccol = base[ch["cid"]] * (0.9 + 0.15 * norm01(spectral(rng, beta=1.4, fmin=80)))[..., None]
        c = cls[ch["cid"]]
        prof = np.clip(ch["ins"] / (0.35 * ch["r"]), 0, 1)
        # plaster lumps keep paint/wallpaper scraps on one face; bricks carry mortar crusts
        crust = (c == 0) * smoothstep(0.6, 0.8, norm01(blur(rng.standard_normal((n, n)).astype(np.float32), 3)))
        ccol = mix(ccol, hexlin("#b3ad9f"), crust * 0.8)
        paint = (c == 1) * (rng.random(npt) < 0.3)[ch["cid"]] * smoothstep(0.5, 0.7, prof)
        ccol = mix(ccol, hexlin("#8c9478"), paint * 0.6)
        ccol = mix(ccol, dust, np.clip(1 - prof * 1.5, 0, 1) * 0.55)
        col = np.where(sel[..., None], ccol, col)
        rough = np.where(sel, np.where(c == 1, 0.93, 0.86), rough)
    # wooden splinters / laths
    sc = StrokeCanvas(n, {"h": 0.0, "a": 0.0}, ss=2)
    for i in range(26):
        x, y = rng.uniform(0, n, 2)
        L = rng.uniform(0.08, 0.35) * ppm
        a = rng.uniform(0, TAU)
        wd = rng.uniform(0.018, 0.04) * ppm
        pts = np.array([[x + np.cos(a) * L * t, y + np.sin(a) * L * t] for t in np.linspace(0, 1, 6)])
        sc.ribbon(pts, wd * np.array([0.4, 1, 1, 1, 0.9, 0.3]), lambda i_, t: {"h": 1.0, "a": 1.0})
    sa = sc.get("a")
    lift = blur(h, 4) + 0.012
    h = np.where(sa > 0.3, np.maximum(h, lift * sa + h * (1 - sa)), h)
    wood = ramp(norm01(spectral(rng, beta=1.6, fmin=40, stretch=(4, 1))), [(0, "#5a4632"), (1, "#7e6548")])
    col = mix(col, wood, sa * 0.9)
    rough = mix(rough, 0.8, sa)
    rel = h - blur(h, 0.05 * ppm)
    crev = smoothstep(0.0, -0.02, rel)
    col = mix(col, dust, crev * 0.5)
    film = smoothstep(0.2, 0.9, norm01(spectral(rng, beta=2.4, fmin=6)))
    col = mix(col, dust * 1.04, film * 0.4)
    col = col * (1 + 0.08 * np.clip(rel / 0.015, -1, 1))[..., None]
    rough = np.clip(rough + 0.05 * crev, 0.6, 0.97)
    return Material(name, tile_m, col, h, rough, ao_radii_m=(0.005, 0.02, 0.07), ao_strength=1.1)


# --------------------------------------------------------------------------- cellar
def cellar_whitewash(name, tile_m):
    """Whitewashed brick cellar wall (Reichsformat bricks), flaking, rising damp below V≈0.3 with salts and
    mould. V up, V=0 = floor."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    vi = _vimg(n)
    rows, per = 26, 8
    L = courses(n, rows, [[n / per] * per] * rows, [(r % 2) * n / per / 2 for r in range(rows)])
    sdf = unit_sdf(rng, L, 0.013 * ppm, chip=0.8)
    inb = smoothstep(-0.5, 1.0, sdf)
    face = np.sqrt(np.clip(sdf / 3.5, 0, 1))
    h = mix(-0.004 + spectral(rng, beta=1.8, fmin=40) * 0.0005, 0.005 * face + rng.normal(0, 0.001, L["count"])[L["sid"]],
            inb) + spectral(rng, beta=1.3, fmin=80) * 0.0002
    btones = ["#7f4434", "#8a4c38", "#73402f", "#91573f"]
    bcol = np.array([hexlin(btones[i]) for i in rng.integers(4, size=L["count"])], np.float32)[L["sid"]]
    brick = mix(hexlin("#8a857b"), bcol, inb)
    # whitewash layers: thick in joints, thin on faces; flaking to brick
    wash = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#bdb7aa"), (1, "#d4cfc4")])
    thin = smoothstep(0.3, 0.8, norm01(spectral(rng, beta=1.6, fmin=40))) * inb * 0.35
    flake_f = norm01(spectral(rng, beta=2.6, fmin=3)) * 0.7 + 0.3 * norm01(spectral(rng, beta=1.6, fmin=30))
    damp_zone = smoothstep(0.6, 0.78, vi)                        # lower ~0.3 of the tile
    flake_f = flake_f + 0.15 * damp_zone
    lost = smoothstep(0.78, 0.785, flake_f)
    wa = (1 - lost) * (1 - thin)
    col = mix(brick, wash, wa)
    edge = np.clip(blur(lost, 1.0) - lost, 0, 1) * 2
    h = h + 0.0004 * (1 - lost) + edge * 0.0004
    # rising damp: darker band with a wavy tide line, white salt efflorescence and mould at the line
    tide_y = 0.7 + 0.03 * spectral(rng, beta=3.0, fmin=2, stretch=(1.0, 4.0))
    damp = smoothstep(tide_y - 0.01, tide_y + 0.02, vi)
    line = np.exp(-((vi - tide_y) / 0.006) ** 2)
    col = col * (1 - 0.3 * damp[..., None])
    col = mix(col, hexlin("#7a7060"), line * 0.5)
    salt = smoothstep(0.55, 0.85, norm01(spectral(rng, beta=1.4, fmin=40))) * np.exp(-((vi - tide_y + 0.02) / 0.03) ** 2)
    col = mix(col, hexlin("#e0ddd5"), salt * 0.7)
    mould = blur((spectral(rng, beta=0.4, fmin=150) > 1.9).astype(np.float32), 0.7) * damp * \
        smoothstep(0.5, 0.8, norm01(spectral(rng, beta=2.5, fmin=3)))
    col = mix(col, hexlin("#2e3127"), np.clip(mould * 1.4, 0, 0.85))
    drips = smoothstep(0.6, 0.95, norm01(blur(spectral(rng, beta=2.4, fmin=4, stretch=(0.2, 1)), 1.2, 8)))
    col = col * (1 - 0.12 * drips[..., None])
    rough = 0.9 - 0.15 * damp + 0.04 * salt
    return Material(name, tile_m, col, h, np.clip(rough, 0.6, 0.97), ao_radii_m=(0.002, 0.008, 0.03),
                    ao_strength=0.9)


# --------------------------------------------------------------------------- terrazzo
def terrazzo_stair(name, tile_m):
    """Worn grey terrazzo; darker border band along U at V 0-0.12 (nosing side) behind a brass divider."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    vi = _vimg(n)
    border = smoothstep(0.877, 0.88, vi)
    divider = np.exp(-((vi - 0.8785) * n / 1.4) ** 2)
    base = mix(hexlin("#8e8b85"), hexlin("#4e4b47"), border)
    base = base * (0.95 + 0.07 * norm01(spectral(rng, beta=2.2, fmin=3)))[..., None]
    col = base
    fc = ["#d9d5cc", "#c8c3b8", "#2f2e2d", "#6f6c69", "#9a968f", "#8a4e3e", "#5c6a5a"]
    fp = np.array([0.25, 0.2, 0.18, 0.15, 0.12, 0.05, 0.05])
    bc = ["#2a2928", "#3a3836", "#6a6764", "#d0ccc3", "#4a3a34"]
    bp = np.array([0.35, 0.25, 0.2, 0.1, 0.1])
    for npts, keep in ((7000, 0.32), (28000, 0.35)):
        ch = voronoi_chunks(rng, npts, n=n, gap=(0.12, 0.45), bevel=0.3, tilt=0.0, keep=keep, jitter=0.95,
                            warp_px=1.0)
        npt = len(ch["pts"])
        f_col = np.array([hexlin(c) for c in rng.choice(fc, npt, p=fp)], np.float32)
        b_col = np.array([hexlin(c) for c in rng.choice(bc, npt, p=bp)], np.float32)
        chip = mix(f_col[ch["cid"]], b_col[ch["cid"]], border)
        col = mix(col, chip, ch["mask"] * 0.92)
    col = col * (1 + 0.05 * spectral(rng, beta=0.4, fmin=200)[..., None])
    # brass divider strip
    col = mix(col, hexlin("#a88c58"), divider)
    metal = divider
    # wear: polished dished path, chipped nosing, dust in the unused margins
    path = np.exp(-((vi - 0.45) / 0.2) ** 2) * (1 - border * 0.5)
    h = -path * 0.0012 + spectral(rng, beta=3.4, fmin=1, fmax=10) * 0.0006 + spectral(rng, beta=1.4, fmin=80) * 0.00003
    nose = smoothstep(0.97, 1.0, vi) * smoothstep(0.6, 0.8, norm01(spectral(rng, beta=2.2, fmin=12)))
    h -= nose * 0.004
    crack = crack_lines(rng, n, 3, length_px=(150, 400), width_px=(0.7, 1.2), wobble=0.1)
    h -= crack * 0.0005
    col = mix(col, hexlin("#3a3734"), crack * 0.6)
    dust = np.clip(0.4 * (1 - path) * norm01(spectral(rng, beta=2.5, fmin=3)) + 0.15, 0, 1)
    col = mix(col, hexlin("#a29a8e"), dust * 0.35)
    col = mix(col, hexlin("#7a7570"), nose * 0.5)
    rough = 0.42 - 0.22 * path + 0.25 * dust + 0.3 * nose
    rough = mix(rough, 0.38, divider)
    return Material(name, tile_m, col, h, np.clip(rough, 0.12, 0.9), metal=metal, ao_radii_m=(0.002, 0.006, 0.02),
                    ao_strength=0.6)


# --------------------------------------------------------------------------- distemper
def interior_paint_distemper(name, tile_m):
    """Two-tone distemper: faded green below the dado line (V≈0.4), cream above, thin dark lining stripe;
    cracked (craquelure), flaking to plaster, water-stained from above, scuffed low down. V up."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    vi = _vimg(n)
    dado = 0.6                                   # image-row fraction of V = 0.4
    lower = smoothstep(dado - 0.0015, dado + 0.0015, vi)
    stripe = np.exp(-((vi - dado) * tile_m / 0.005) ** 2)
    green = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#6f7a5f"), (1, "#808b6e")])
    cream = ramp(norm01(spectral(rng, beta=2.6, fmin=2)), [(0, "#c2b597"), (1, "#cfc3a6")])
    brushes = spectral(rng, beta=1.6, fmin=20, stretch=(1.0, 1.0), angle=0.4) * 0.5 + \
        spectral(rng, beta=1.6, fmin=20, angle=-0.6) * 0.5
    col = mix(cream, green, lower) * (1 + 0.04 * brushes[..., None])
    col = mix(col, hexlin("#3c4634"), stripe)
    fade = smoothstep(0.35, 0.9, norm01(spectral(rng, beta=3.0, fmin=1)))
    col = mix(col, col * 0.5 + hexlin("#c9c2b0") * 0.5, fade[..., None] * 0.35)
    craz = 1 - voronoi_chunks(rng, 2500, n=n, gap=(0.0, 0.015), bevel=0.05, tilt=0, jitter=0.9, warp_px=3)["mask"]
    craz *= smoothstep(0.45, 0.75, norm01(spectral(rng, beta=2.5, fmin=2)))
    flake_f = norm01(spectral(rng, beta=2.7, fmin=3)) * 0.75 + 0.25 * norm01(spectral(rng, beta=1.8, fmin=25))
    lost = smoothstep(0.8, 0.805, flake_f)
    plaster = ramp(norm01(spectral(rng, beta=2.2, fmin=6)), [(0, "#b1a291"), (1, "#c0b3a3")])
    col = mix(col, hexlin("#4d4a40"), craz * 0.45 * (1 - lost))
    col = mix(col, plaster, lost)
    run = norm01(blur(spectral(rng, beta=2.6, fmin=2, stretch=(0.3, 1.0)), 1.5, 8.0))
    stain = smoothstep(0.62, 0.9, run) * smoothstep(0.75, 0.2, vi)
    tide = np.exp(-((run - 0.62) / 0.01) ** 2) * smoothstep(0.75, 0.2, vi)
    col = mix(col, hexlin("#8a7a5c"), stain * 0.4)
    col = mix(col, hexlin("#6d5d44"), tide * 0.3)
    scuff = smoothstep(0.85, 1.0, vi) * smoothstep(1.4, 2.4, spectral(rng, beta=0.8, fmin=30, stretch=(5, 1)))
    col = mix(col, hexlin("#4a4a3e"), scuff * 0.5)
    h = (1 - lost) * 0.0003 + brushes * 0.00003 - craz * 0.00012 + spectral(rng, beta=3.2, fmin=1, fmax=8) * 0.0008 \
        + np.clip(blur(lost, 1.0) - lost, 0, 1) * 0.0004
    rough = 0.93 - 0.05 * stain + 0.02 * lost
    return Material(name, tile_m, col, h, np.clip(rough, 0.75, 0.98), ao_radii_m=(0.001, 0.004, 0.015),
                    ao_strength=0.7)


# --------------------------------------------------------------------------- parquet
def parquet_oak(name, tile_m):
    """Herringbone oak parquet, slats 70 x 354 mm at ±45°, zig-zag rows along U; worn, dusty, a few
    missing slats showing black bitumen."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    k = 5
    Wm = 0.1 / np.sqrt(2)                       # slat width -> exactly periodic over 1 m
    Y, X = np.mgrid[0:n, 0:n].astype(np.float64) + 0.5
    Xm, Ym = X / ppm, Y / ppm
    xc = (Xm + Ym) / (np.sqrt(2) * Wm)
    yc = (Xm - Ym) / (np.sqrt(2) * Wm)
    cx, cy = np.floor(xc).astype(int), np.floor(yc).astype(int)
    m = np.mod(cx - cy, 2 * k)
    horiz = m < k
    x0 = cx - m
    y0 = cy - (2 * k - 1 - m)
    along = np.where(horiz, (xc - x0) / k, (yc - y0) / k)
    across = np.where(horiz, yc - cy, xc - cx)
    a_key = np.where(horiz, x0, cx)
    b_key = np.where(horiz, cy, y0)
    P = int(round(tile_m / (np.sqrt(2) * Wm)))           # 10 cells per metre along each diagonal
    key = (np.mod(a_key + b_key, 2 * P) * (2 * P) + np.mod(a_key - b_key, 2 * P)) * 2 + horiz.astype(int)
    nk = (2 * P) * (2 * P) * 2
    rnd = rng.random((nk, 6))
    # grain per slat: sample a periodic grain field along the slat direction
    G = periodic_grain(rng, ring_px=13, wander=30, knots=0, stretch=8, latewood=0.35)
    slat_px = (along * k * Wm * ppm * 1.0)
    acr_px = across * Wm * ppm
    gx = (slat_px + rnd[key, 0] * n).astype(np.float32) % n
    gy = (acr_px + rnd[key, 1] * n).astype(np.float32) % n
    late = cv2.remap(G["late"], gx, gy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    fib = cv2.remap(G["fibre"], gx, gy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    ray = smoothstep(2.0, 2.8, cv2.remap(spectral(rng, beta=0.3, fmin=80, stretch=(0.3, 1.0)), gx, gy,
                                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP))
    gap_px = 1.2
    da = np.minimum(along, 1 - along) * k * Wm * ppm
    dc = np.minimum(across, 1 - across) * Wm * ppm
    sdf = np.minimum(da, dc)
    inb = smoothstep(gap_px * 0.5, gap_px * 1.5, sdf)
    tone = np.exp(rng.normal(0, 0.14, nk))[key]
    oak = mix(hexlin("#9a7a52"), hexlin("#7a5c3e"), np.clip(late, 0, 1)) * tone[..., None]
    oak = oak * (1 + 0.05 * fib[..., None])
    oak = mix(oak, hexlin("#b0926a"), ray * 0.3)
    missing = rnd[key, 2] < 0.02
    bitumen = hexlin("#151311")
    h = (0.0006 * np.sqrt(np.clip(sdf / 3, 0, 1)) + (rnd[key, 3] - 0.5) * 0.0008 + late * 0.00005) * inb \
        - 0.001 * (1 - inb)
    h = np.where(missing, -0.008 + spectral(rng, beta=2, fmin=20) * 0.0005, h)
    col = mix(hexlin("#2a2219"), oak, inb)
    col = np.where(missing[..., None], bitumen * (1 + 0.3 * norm01(spectral(rng, beta=1.5, fmin=30)))[..., None], col)
    # wear path (finish gone, greyed) + dust and plaster grit
    vi = _vimg(n)
    wear = smoothstep(0.3, 0.8, norm01(spectral(rng, beta=2.8, fmin=2)))
    col = mix(col, col * 0.8 + hexlin("#8a7c68") * 0.2, wear[..., None] * 0.6)
    dust = smoothstep(0.35, 0.85, norm01(spectral(rng, beta=2.4, fmin=3))) * 0.6 + smoothstep(3, 0, sdf) * 0.3
    col = mix(col, hexlin("#a09787"), np.clip(dust, 0, 1) * 0.5)
    rough = mix(0.5, 0.8, wear) + 0.2 * dust
    rough = np.where(missing, 0.6, rough)
    crumbs = np.zeros((n, n), np.float32)
    rough = rough.astype(np.float32)
    h = h.astype(np.float32)
    col = col.astype(np.float32)
    scatter_stones(rng, h, col, 160, (1.0, 3.5), [hexlin("#b9b0a2"), hexlin("#8a4a38")], embed=(0.0, 0.3),
                   h_scale_m=0.003, angular=0.7, rough_map=rough, rough_val=0.92, id_map=crumbs)
    return Material(name, tile_m, col, h, np.clip(rough, 0.35, 0.95), ao_radii_m=(0.001, 0.004, 0.012),
                    ao_strength=0.7)


# --------------------------------------------------------------------------- cast iron
def pump_iron_green(name, tile_m):
    """Dark-green painted cast iron (street pumps, lamp posts): sand-cast texture, chipped through red-lead
    primer to rust, rust bleeding down (V up)."""
    rng = rng_for(name)
    n = N
    ppm = n / tile_m
    cast = spectral(rng, beta=2.2, fmin=20, fmax=300)
    pits = np.clip(-spectral(rng, beta=0.8, fmin=150) - 1.7, 0, None)
    crk = voronoi_chunks(rng, 700, n=n, gap=(0.0, 0.03), bevel=0.05, tilt=0.0, jitter=0.9, warp_px=4)
    crackle = 1 - crk["mask"]
    wear = norm01(spectral(rng, beta=2.6, fmin=3)) * 0.7 + 0.3 * norm01(spectral(rng, beta=1.8, fmin=20))
    cw = rng.uniform(0, 1, len(crk["pts"]))[crk["cid"]]
    t = wear + 0.3 * cw
    top_a = blur((t < 0.97).astype(np.float32), 0.6)
    pri_a = blur((t < 1.04).astype(np.float32), 0.6)
    rust_c = ramp(norm01(spectral(rng, beta=2.0, fmin=10)), [(0, "#2e1f17"), (0.6, "#4a2e1e"), (1, "#5e3a24")])
    col = mix(rust_c, hexlin("#6e3e2c"), pri_a)
    green = mix(hexlin("#1f3326"), hexlin("#2a3f30"), norm01(spectral(rng, beta=2.4, fmin=3)))
    chalk = smoothstep(0.55, 0.9, norm01(spectral(rng, beta=2.2, fmin=4)))
    green = mix(green, hexlin("#46564a"), chalk * 0.35)
    col = mix(col, green, top_a)
    col = mix(col, hexlin("#141a15"), crackle * top_a * 0.5)
    # rust bleeding down from the chips
    chips = 1 - top_a
    bleed = np.zeros((n, n), np.float32)
    k = blur(chips, 0.5)
    for s in range(1, 40, 3):
        bleed = np.maximum(bleed, np.roll(k, s, axis=0) * np.exp(-s / 18.0))
    bleed = blur(bleed, 1.5, 3.0) * (1 - chips) * smoothstep(0.3, 0.7, norm01(spectral(rng, beta=2, fmin=10)))
    col = mix(col, hexlin("#5a3420"), np.clip(bleed, 0, 1) * 0.6)
    h = cast * 0.00015 - pits * 0.0004 + 0.00015 * top_a + 0.0001 * pri_a - crackle * top_a * 0.00008 + \
        (1 - pri_a) * spectral(rng, beta=1.6, fmin=60) * 0.00008
    rough = mix(0.88, 0.7, pri_a)
    rough = mix(rough, 0.42 + 0.2 * chalk, top_a)
    return Material(name, tile_m, col, h, np.clip(rough, 0.3, 0.95), ao_radii_m=(0.0006, 0.002, 0.006),
                    ao_strength=0.7)


SETS = {
    "berlin_render_facade": (berlin_render_facade, 1.8, "Grey-ochre lime render, V up, moulded string courses every "
                                                        "0.9 m (at V≈0.25 and 0.75), soot, chips to red brick, bullet "
                                                        "and shrapnel pocks."),
    "berlin_sidewalk": (berlin_sidewalk, 3.0, "Berlin sidewalk: granite slab band (V 0.25-0.75, slabs along U) with "
                                              "small granite mosaic setts either side; map V across the sidewalk. "
                                              "Dry, dust and brick grit in joints."),
    "berlin_cobbles": (berlin_cobbles, 2.0, "Dry grey granite setts (Kopfsteinpflaster), 14 courses along U, dusty "
                                            "sand/brick-dust joints."),
    "rubble_brick_plaster": (rubble_brick_plaster, 2.0, "Heap surface: broken red brick, plaster lumps, mortar, "
                                                        "splinters, heavy light dust."),
    "cellar_whitewash": (cellar_whitewash, 2.0, "Whitewashed brick cellar wall (26 courses), flaking; rising damp, "
                                                "salts and mould below V≈0.3. V up, V=0 = floor."),
    "terrazzo_stair": (terrazzo_stair, 1.0, "Worn grey terrazzo; darker border band along U at V 0-0.12 (nosing side) "
                                            "behind a brass divider (metalness 1)."),
    "interior_paint_distemper": (interior_paint_distemper, 2.0, "Two-tone distemper: faded green below the dado line "
                                                                "at V≈0.4, cream above, dark lining stripe; cracked, "
                                                                "flaking, water stains. V up."),
    "parquet_oak": (parquet_oak, 1.0, "Herringbone oak parquet (70 x 354 mm slats at ±45°, zig-zag along U), worn, "
                                      "dusty, a few missing slats showing bitumen."),
    "pump_iron_green": (pump_iron_green, 0.5, "Dark-green painted cast iron chipped through red-lead primer to rust, "
                                              "rust bleeding downwards (V up)."),
}
