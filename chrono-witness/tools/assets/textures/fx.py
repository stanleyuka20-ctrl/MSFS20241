"""Effect textures (public/assets/textures/fx/). Not PBR sets. See README for layouts."""
from __future__ import annotations

import json
import os

import cv2
import numpy as np
from PIL import Image

from lib.core import TAU, blur, fbm, hexlin, lin_to_srgb, norm01, rng_for, smoothstep, spectral, worley
from lib.elements import boot_print
from lib.pbr import encode_normal, height_to_normal
from lib.strokes import StrokeCanvas


def _save_png(arr, path):
    Image.fromarray(arr).save(path, optimize=True)


# --------------------------------------------------------------------------- rain ripples
def rain_ripples(out):
    """4x4 flipbook (16 frames, 512^2 each), looping; each frame tileable. OpenGL normals."""
    rng = rng_for("rain_ripples")
    f, nfr = 512, 16
    ndrop = 70
    px = rng.uniform(0, f, ndrop)
    py = rng.uniform(0, f, ndrop)
    t0 = rng.uniform(0, 1, ndrop)
    amp = rng.uniform(0.6, 1.0, ndrop)
    Y, X = np.mgrid[0:f, 0:f].astype(np.float32)
    life = 0.55
    speed = 70.0      # px per loop-fraction
    lam = 7.0         # wavelength px
    sheet = np.zeros((f * 4, f * 4, 3), np.uint8)
    for fi in range(nfr):
        t = fi / nfr
        hgt = np.zeros((f, f), np.float32)
        for i in range(ndrop):
            age = (t - t0[i]) % 1.0
            if age > life:
                continue
            dx = (X - px[i] + f / 2) % f - f / 2
            dy = (Y - py[i] + f / 2) % f - f / 2
            r = np.sqrt(dx * dx + dy * dy)
            front = speed * age + 1.5
            env = np.exp(-((r - front) / (lam * 1.1)) ** 2)
            fade = (1 - age / life) ** 1.5 * amp[i]
            hgt += np.cos(TAU * (r - front) / lam) * env * fade
        # heights in arbitrary units; peak slope ~0.45 (OpenGL: +Y up the image)
        nx = -(np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5 * 0.8
        ny = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5 * 0.8
        L = np.sqrt(nx * nx + ny * ny + 1)
        nrm = np.stack([nx / L, ny / L, 1 / L], -1)
        r0, c0 = divmod(fi, 4)
        sheet[r0 * f:(r0 + 1) * f, c0 * f:(c0 + 1) * f] = encode_normal(nrm)
    _save_png(sheet, os.path.join(out, "rain_ripples_normal.png"))


# --------------------------------------------------------------------------- footprints
FOOTPRINT_LAYOUT = [
    ("left_fresh_deep", True, 0.028, 0.0, 1.0),
    ("right_fresh_deep", False, 0.028, 0.0, 1.0),
    ("left_shallow", True, 0.012, 0.15, 1.0),
    ("right_shallow", False, 0.012, 0.15, 1.0),
    ("left_slipped_smeared", True, 0.02, 0.8, 1.0),
    ("right_toe_only", False, 0.02, 0.2, 0.55),
    ("left_heel_only", True, 0.022, 0.2, 0.45),
    ("right_old_softened", False, 0.016, 0.6, 1.0),
]


def footprints(out):
    """8 British 1914 ammunition-boot prints, 4 cols x 2 rows of 256x512 cells (toe up)."""
    rng = rng_for("footprints")
    W, H = 256, 512
    ppm = 1150.0  # 0.295 m sole -> ~340 px
    atlas = np.zeros((H * 2, W * 4, 4), np.uint8)
    atlas[..., :3] = (128, 128, 255)
    for k, (label, left, depth, smear, partial) in enumerate(FOOTPRINT_LAYOUT):
        r_ = np.random.default_rng(1000 + k)
        if partial < 1.0:
            # deterministic choice of which end survives
            ph, pm = boot_print(r_, ppm, depth=depth, left=left, smear=smear, partial=1.0, stud_depth=0.0025)
            hh = ph.shape[0]
            s = np.linspace(1, 0, hh)[:, None]  # toe at top (row 0) -> s=1
            keep = smoothstep(1 - partial - 0.1, 1 - partial + 0.05, s) if "toe" in label else \
                smoothstep(partial + 0.1, partial - 0.05, s)
            ph = ph * keep
        else:
            ph, pm = boot_print(r_, ppm, depth=depth, left=left, smear=smear, partial=1.0, stud_depth=0.0025)
        if "smeared" in label:
            M = np.float32([[1, 0.15, 0], [0, 1.12, -10]])
            ph = cv2.warpAffine(ph, M, (ph.shape[1], ph.shape[0]))
        hgt = np.zeros((H, W), np.float32)
        ph_h, ph_w = ph.shape
        y0 = (H - ph_h) // 2
        x0 = (W - ph_w) // 2
        hgt[y0:y0 + ph_h, x0:x0 + ph_w] = ph
        # natural mud irregularity
        hgt += cv2.GaussianBlur(r_.standard_normal((H, W)).astype(np.float32), (0, 0), 2.0) * 0.0003 * \
            (np.abs(hgt) > 1e-4)
        nrm = height_to_normal(hgt, tile_m=H / ppm, strength=1.0)  # px size = H/ppm/H
        mag = np.abs(hgt)
        alpha = smoothstep(0.0003, 0.004, mag)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 1.2)
        cell = np.zeros((H, W, 4), np.uint8)
        cell[..., :3] = encode_normal(nrm)
        cell[..., 3] = np.clip(np.round(alpha * 255), 0, 255).astype(np.uint8)
        r0, c0 = divmod(k, 4)
        atlas[r0 * H:(r0 + 1) * H, c0 * W:(c0 + 1) * W] = cell
    _save_png(atlas, os.path.join(out, "footprints_alpha.png"))


# --------------------------------------------------------------------------- smoke / dust sprites
def _puff(rng, s=512, lobes=26, wisp=0.5, softness=1.0):
    """Billowy puff: union of noisy spheres. Returns (alpha, shade)."""
    Y, X = np.mgrid[0:s, 0:s].astype(np.float32) / s - 0.5
    dens = np.zeros((s, s), np.float32)
    lit_sum = np.zeros((s, s), np.float32)
    w_sum = np.full((s, s), 1e-6, np.float32)
    Lv = np.array([-0.45, -0.6, 0.65])
    Lv = Lv / np.linalg.norm(Lv)
    for i in range(lobes):
        a = rng.uniform(0, TAU)
        rr = min(abs(rng.normal(0, 0.12)), 0.24)
        cx, cy = np.cos(a) * rr, np.sin(a) * rr * 0.8
        cz = rng.normal(0, 0.06)
        rad = rng.uniform(0.09, 0.2) * (1 - rr * 1.6)
        d2 = (X * 0.6 - cx) ** 2 + (Y * 0.6 - cy) ** 2
        zc = np.sqrt(np.clip(rad * rad - d2, 0, None))
        dens += 2 * zc
        nx, ny, nz = (X * 0.6 - cx) / rad, (Y * 0.6 - cy) / rad, zc / rad
        l = np.clip(nx * Lv[0] + ny * Lv[1] + nz * Lv[2], 0, 1)
        wgt = (zc / rad) ** 2 * np.exp((cz + zc) * 25.0)   # soft blend, front-most lobes dominate
        lit_sum += l * wgt
        w_sum += wgt
    n1 = norm01(fbm(rng, 6, octaves=6, n=s))
    n2 = norm01(fbm(rng, 12, octaves=5, n=s, ridged=True))
    lit = lit_sum / w_sum
    lit = np.clip(lit + 0.25 * (n1 - 0.5) + 0.1 * (n2 - 0.5), 0, 1)
    dens = dens / (dens.max() + 1e-6)
    dens = dens * (0.6 + 0.8 * n1) * (0.85 + wisp * 0.4 * n2)
    edge = smoothstep(0.0, 0.25, dens - 0.08 * (1 - n1))  # eroded, wispy boundary
    dens = dens * edge
    dens = cv2.GaussianBlur(dens, (0, 0), 1.2 * softness)
    # centre the puff in the sprite and fade to zero well inside the border
    ys, xs = np.nonzero(dens > 0.05)
    if len(xs):
        dens = np.roll(dens, (s // 2 - int(ys.mean()), s // 2 - int(xs.mean())), (0, 1))
        lit = np.roll(lit, (s // 2 - int(ys.mean()), s // 2 - int(xs.mean())), (0, 1))
        n2 = np.roll(n2, (s // 2 - int(ys.mean()), s // 2 - int(xs.mean())), (0, 1))
    dens *= smoothstep(0.49, 0.38, np.sqrt(X ** 2 + Y ** 2))
    alpha = 1 - np.exp(-dens * 4.0)
    lit = cv2.GaussianBlur(lit, (0, 0), 3.0 * softness)
    shade = 0.58 + 0.42 * lit * (0.85 + 0.15 * n2)
    shade = np.where(alpha > 0.01, shade, 0.8)
    return np.clip(alpha, 0, 1), np.clip(shade, 0, 1)


def smoke_and_dust(out):
    rng = rng_for("smoke_puff")
    a, sh = _puff(rng)
    rgb = np.stack([sh, sh, sh * 0.98], -1)
    img = np.dstack([np.round(rgb * 255), np.round(a * 255)]).astype(np.uint8)
    _save_png(img, os.path.join(out, "smoke_puff.png"))
    rng = rng_for("dust_puff")
    a, sh = _puff(rng, lobes=34, wisp=1.0, softness=2.2)
    a = a * 0.8
    tint = lin_to_srgb(hexlin("#9c8b74"))
    rgb = np.clip(sh[..., None] * tint[None, None, :] * 1.25, 0, 1)
    img = np.dstack([np.round(rgb * 255), np.round(a * 255)]).astype(np.uint8)
    _save_png(img, os.path.join(out, "dust_puff.png"))


# --------------------------------------------------------------------------- noise textures
def cloud_noise(out):
    rng = rng_for("cloud_noise")
    n = 1024
    r = norm01(fbm(rng, 2, octaves=8, gain=0.55, n=n), 0.2, 99.8)                      # broad cloud masses
    g = norm01(fbm(rng, 6, octaves=7, gain=0.5, n=n, ridged=True), 0.2, 99.8)           # billowy mid detail
    d, _, _ = worley(rng, npts=600, n=n, k=1)
    w = 1 - norm01(d[..., 0])
    b = norm01(0.6 * w + 0.4 * norm01(fbm(rng, 24, octaves=5, n=n)), 0.2, 99.8)        # fine cells/wisps
    img = np.stack([r, g, b], -1)
    _save_png(np.round(img * 255).astype(np.uint8), os.path.join(out, "cloud_noise.png"))


def blue_noise(out, n=128):
    """Void-and-cluster (Ulichney) blue-noise ranking, 8-bit."""
    rng = rng_for("blue_noise")
    sigma = 1.9
    k = np.fft.fftfreq(n) * n
    yy, xx = np.meshgrid(k, k, indexing="ij")
    kern = np.exp(-(xx ** 2 + yy ** 2) / (2 * sigma * sigma)).astype(np.float64)  # wrapped Gaussian (dist)

    def energy(binary):
        return np.real(np.fft.ifft2(np.fft.fft2(binary) * np.fft.fft2(kern)))

    total = n * n
    init = rng.random((n, n)) < 0.1
    binary = init.astype(np.float64)
    # relax initial pattern
    for _ in range(4 * total):
        E = energy(binary)
        cl = np.unravel_index(np.argmax(np.where(binary > 0, E, -np.inf)), E.shape)
        binary[cl] = 0
        E = energy(binary)
        vd = np.unravel_index(np.argmin(np.where(binary == 0, E, np.inf)), E.shape)
        if vd == cl:
            binary[cl] = 1
            break
        binary[vd] = 1
    rank = np.zeros((n, n), np.int64)
    ones = int(binary.sum())
    # phase 1: remove clusters from initial pattern
    b = binary.copy()
    E = energy(b)
    for r in range(ones - 1, -1, -1):
        cl = np.unravel_index(np.argmax(np.where(b > 0, E, -np.inf)), E.shape)
        b[cl] = 0
        E -= np.roll(np.roll(kern, cl[0], 0), cl[1], 1)
        rank[cl] = r
    # phase 2/3: fill voids
    b = binary.copy()
    E = energy(b)
    for r in range(ones, total):
        vd = np.unravel_index(np.argmin(np.where(b == 0, E, np.inf)), E.shape)
        b[vd] = 1
        E += np.roll(np.roll(kern, vd[0], 0), vd[1], 1)
        rank[vd] = r
    img = np.round((rank + 0.5) / total * 255).astype(np.uint8)
    _save_png(img, os.path.join(out, "blue_noise.png"))


def water_normal(out):
    """Small wind-driven waves for puddles / flooded craters (Phillips spectrum, integer wave numbers)."""
    rng = rng_for("water_normal")
    n = 1024
    tile_m = 2.0
    k = np.fft.fftfreq(n) * n * TAU / tile_m
    kx, ky = np.meshgrid(k, k)
    K = np.sqrt(kx ** 2 + ky ** 2) + 1e-9
    wind = np.array([np.cos(0.6), np.sin(0.6)])
    V = 2.2
    Lw = V * V / 9.81
    cosw = (kx * wind[0] + ky * wind[1]) / K
    P = np.exp(-1.0 / (K * Lw) ** 2) / K ** 4 * (0.25 + 0.75 * cosw ** 2) * np.exp(-(K * 0.004) ** 2)
    P[0, 0] = 0
    h0 = (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))) * np.sqrt(P / 2)
    H = np.real(np.fft.ifft2(h0))
    sx = np.real(np.fft.ifft2(1j * kx * h0))
    sy = np.real(np.fft.ifft2(1j * ky * h0))
    sc = 0.32 / (np.sqrt(sx ** 2 + sy ** 2).std() * 2.2 + 1e-12)
    nx, ny = -sx * sc, sy * sc    # ky grows with row index -> flip for OpenGL
    L = np.sqrt(nx * nx + ny * ny + 1)
    nrm = np.stack([nx / L, ny / L, 1 / L], -1)
    _save_png(encode_normal(nrm), os.path.join(out, "water_normal.png"))


# --------------------------------------------------------------------------- grass atlas
GRASS_COLOURS = [("#5c5634", "#b8a274"), ("#4f4a2c", "#a38d5f"), ("#5a5a31", "#8f8b55"), ("#4b3f2c", "#9a805b"),
                 ("#605536", "#c4b084"), ("#4a4a2e", "#7d7d4a"), ("#55462f", "#a48b66")]


def grass_atlas(out):
    """8 dead/autumn grass tufts, 4 cols x 2 rows of 256x512 cells, base at cell bottom centre."""
    rng = rng_for("grass_blade_atlas")
    W, H = 256, 512
    ss = 3
    atlas = np.zeros((H * 2, W * 4, 4), np.float32)
    for t in range(8):
        r_ = np.random.default_rng(500 + t)
        sc = StrokeCanvas(max(W, H), {"r": 0, "g": 0, "b": 0, "a": 0}, ss=ss)
        nbl = int(r_.integers(22, 48))
        height = r_.uniform(0.7, 0.95) * H
        cols = [tuple(hexlin(c) for c in GRASS_COLOURS[i]) for i in r_.choice(len(GRASS_COLOURS), 3, replace=False)]
        order = r_.permutation(nbl)
        for bi in order:
            c0, c1 = cols[r_.integers(len(cols))]
            bright = np.exp(r_.normal(0, 0.12))
            bx = W / 2 + r_.normal(0, 10)
            by = H - 4
            L = height * r_.uniform(0.35, 1.0)
            lean = r_.normal(0, 0.2)
            curl = r_.normal(0, 0.7) * (1 + abs(lean))
            m = 14
            pts = []
            ang = -np.pi / 2 + lean
            p = np.array([bx, by])
            broken = r_.random() < 0.22
            kink = r_.uniform(0.4, 0.8)
            for j in range(m):
                pts.append(p.copy())
                tt = j / (m - 1)
                ang += curl * 0.06 * (0.3 + tt * 1.5)
                if broken and abs(tt - kink) < 0.5 / m:
                    ang += r_.choice([-1, 1]) * r_.uniform(1.2, 2.2)  # snapped, hanging blade
                p = p + (L / (m - 1)) * np.array([np.cos(ang), np.sin(ang)])
            pts = np.array(pts)
            w0 = r_.uniform(2.5, 7.0)
            widths = w0 * np.clip(1 - np.linspace(0, 1, m) ** 1.3, 0.08, 1)

            def vals(si, tt, c0=c0, c1=c1, bright=bright):
                cc = (c0 + (c1 - c0) * min(1.0, tt * 1.3 + 0.1)) * bright * (0.55 + 0.45 * min(1.0, tt * 2.5))
                return {"r": cc[0], "g": cc[1], "b": cc[2], "a": 1.0}
            sc.ribbon(pts, widths, vals)
            if r_.random() < 0.18 and not broken:  # seed head on a stem
                tip = pts[-1]
                dirv = pts[-1] - pts[-2]
                dirv /= np.linalg.norm(dirv) + 1e-6
                head = np.array([tip + dirv * s_ * 4 for s_ in range(8)])
                sc.ribbon(head, np.linspace(5, 2, 8), lambda si, tt: {"r": hexlin("#8a7656")[0],
                                                                      "g": hexlin("#8a7656")[1],
                                                                      "b": hexlin("#8a7656")[2], "a": 1.0})
        # StrokeCanvas is square (max(W,H)); crop the left W columns centred
        big_a = sc.get("a")
        big = np.stack([sc.get("r"), sc.get("g"), sc.get("b")], -1)
        S = big_a.shape[0]
        xo = 0
        a = big_a[:H, xo:xo + W]
        rgb = big[:H, xo:xo + W] / np.maximum(a[..., None], 1e-4)
        # dilate colour into transparent texels (mip-safe edges)
        filled = rgb.copy()
        known = a > 0.02
        for it in range(24):
            if known.all():
                break
            acc = np.zeros_like(filled)
            cnt = np.zeros(a.shape, np.float32)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                sh_k = np.roll(known, (dy, dx), (0, 1))
                acc += np.roll(filled, (dy, dx), (0, 1)) * sh_k[..., None]
                cnt += sh_k
            newk = (~known) & (cnt > 0)
            filled[newk] = acc[newk] / cnt[newk][:, None]
            known = known | newk
        filled[~known] = np.mean(rgb[a > 0.5], 0) if (a > 0.5).any() else 0.2
        srgb = lin_to_srgb(np.clip(filled, 0, 1))
        r0, c0 = divmod(t, 4)
        atlas[r0 * H:(r0 + 1) * H, c0 * W:(c0 + 1) * W, :3] = srgb
        atlas[r0 * H:(r0 + 1) * H, c0 * W:(c0 + 1) * W, 3] = np.clip(a, 0, 1)
    _save_png(np.round(atlas * 255).astype(np.uint8), os.path.join(out, "grass_blade_atlas.png"))


# --------------------------------------------------------------------------- barbed wire
def barbed_wire(out):
    """512x128 RGBA strip, tiles along U: two twisted strands + 4-point barbs every 128 px."""
    W, H, ss = 512, 128, 4
    w, h = W * ss, H * ss
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    yc = h / 2
    depth = np.full((h, w), -1e9, np.float32)
    shade = np.zeros((h, w), np.float32)
    cover = np.zeros((h, w), np.float32)
    pitch = w / 8.0  # 8 half-twists per strip
    r_w = 2.2 * ss
    for s in range(2):
        ph = s * np.pi
        cy = yc + 7 * ss * np.sin(TAU * X[0] / (2 * pitch) + ph)
        z = np.cos(TAU * X[0] / (2 * pitch) + ph)
        d = (Y - cy[None, :]) / r_w
        inside = np.abs(d) < 1
        zz = z[None, :] + np.sqrt(np.clip(1 - d ** 2, 0, 1)) * 0.3
        take = inside & (zz > depth)
        depth = np.where(take, zz, depth)
        nl = np.clip(0.55 - d * 0.6, 0, 1)  # light from above
        shade = np.where(take, 0.35 + 0.65 * nl * (0.75 + 0.25 * z[None, :]), shade)
        cover = np.maximum(cover, inside.astype(np.float32))
    # barbs: two short wires wrapped round the strands, four points
    for bi in range(4):
        bx = (bi + 0.5) * w / 4
        for ang in (0.9, -0.9, np.pi - 0.9, np.pi + 0.9):
            L = 13 * ss
            for tt in np.linspace(0, 1, 60):
                x = bx + np.cos(ang) * L * tt * 0.55
                y = yc - np.sin(ang) * L * tt
                rr = 1.6 * ss * (1 - 0.6 * tt)
                m = ((X - x) ** 2 + (Y - y) ** 2) < rr * rr
                shade = np.where(m, 0.4 + 0.5 * (1 - tt * 0.3), shade)
                depth = np.where(m, 2.0, depth)
                cover = np.maximum(cover, m.astype(np.float32))
        # wrap coil
        m = (np.abs(X - bx) < 4 * ss) & (np.abs(Y - yc) < 9 * ss)
        coil = 0.5 + 0.4 * np.sin((Y - yc) / ss * 2.0)
        shade = np.where(m, coil * 0.8, shade)
        cover = np.maximum(cover, m.astype(np.float32))
    rn = np.random.default_rng(7).random((h, w)).astype(np.float32)
    rn = cv2.GaussianBlur(rn, (0, 0), 6)
    rn = (rn - rn.min()) / (np.ptp(rn) + 1e-6)
    base = hexlin("#4a3a30") * (1 - rn[..., None]) + hexlin("#6a4630") * rn[..., None]
    rgb = np.clip(base * (shade[..., None] * 1.6), 0, 1)
    a = cv2.resize(cover, (W, H), interpolation=cv2.INTER_AREA)
    rgb = cv2.resize(rgb * cover[..., None], (W, H), interpolation=cv2.INTER_AREA) / np.maximum(a[..., None], 1e-3)
    rgb[a < 0.01] = base.mean((0, 1))
    srgb = lin_to_srgb(np.clip(rgb, 0, 1))
    img = np.dstack([np.round(srgb * 255), np.round(a * 255)]).astype(np.uint8)
    _save_png(img, os.path.join(out, "barbed_wire_alpha.png"))


# --------------------------------------------------------------------------- Blitz effects
FIRE_STOPS = [(0.0, (0.0, 0.0, 0.0)), (0.12, (0.22, 0.025, 0.0)), (0.3, (0.75, 0.16, 0.01)),
              (0.5, (1.0, 0.42, 0.06)), (0.72, (1.0, 0.7, 0.25)), (0.9, (1.0, 0.88, 0.6)), (1.0, (1.0, 0.95, 0.82))]


def fire_flipbook(out):
    """8x8 flipbook (64 frames of 256^2), looping flame. RGB = emissive colour (sRGB), A = flame mask."""
    from lib.core import ramp, spectral
    rng = rng_for("fire_flipbook")
    F, nfr = 256, 64
    A1 = spectral(rng, n=F, beta=2.8, fmin=2, stretch=(0.45, 1.0))   # features elongated vertically
    A2 = spectral(rng, n=F, beta=2.2, fmin=4, stretch=(0.4, 1.0))
    Wn = spectral(rng, n=F, beta=2.6, fmin=2)
    Y, X = np.mgrid[0:F, 0:F].astype(np.float32)
    sheet = np.zeros((F * 8, F * 8, 4), np.float32)

    def samp(img, yoff, xoff=0.0):
        return cv2.remap(img, ((X + xoff) % F).astype(np.float32), ((Y + yoff) % F).astype(np.float32),
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

    for f in range(nfr):
        t = f / nfr
        # integer numbers of full noise periods per loop -> seamless loop
        n1 = samp(A1, t * F * 3)
        n2 = samp(A2, t * F * 5)
        w = samp(Wn, t * F * 2)
        turb = 0.6 * n1 + 0.4 * n2
        v = np.clip((242 - Y) / 200.0, -0.2, 1.4)           # 0 at the base, 1 near the tip
        sway = 10 * np.sin(TAU * (2 * t) + v * 2.5) * v + 16 * v * w
        u = (X - 128 + sway) / 128.0
        width = 0.5 * np.clip(1 - v, 0, 1) ** 0.8 * (1 + 0.35 * turb) + 0.03
        body = smoothstep(width, width - 0.3, np.abs(u))
        height_cut = smoothstep(1.1, 0.45, v + 0.5 * turb)        # tongues break off at the top
        base = smoothstep(-0.12, 0.04, v)
        core = np.exp(-(u / 0.22) ** 2) * smoothstep(0.6, 0.0, v)  # white-hot near the fuel
        T = body * height_cut * base * (0.6 + 0.3 * turb) * (1.0 - 0.7 * np.clip(v, 0, 1)) + 0.35 * core * base
        T = np.clip(T, 0, 1)
        T = cv2.GaussianBlur(T, (0, 0), 1.0)
        col = ramp(T, FIRE_STOPS)
        a = smoothstep(0.06, 0.4, T)
        r0, c0 = divmod(f, 8)
        sheet[r0 * F:(r0 + 1) * F, c0 * F:(c0 + 1) * F, :3] = lin_to_srgb(col)
        sheet[r0 * F:(r0 + 1) * F, c0 * F:(c0 + 1) * F, 3] = a
    # keep RGB of fully transparent texels a dark ember red (no fringes when filtered)
    trans = sheet[..., 3] < 0.01
    sheet[trans, :3] = lin_to_srgb(np.array([0.2, 0.02, 0.0], np.float32))
    _save_png(np.round(np.clip(sheet, 0, 1) * 255).astype(np.uint8), os.path.join(out, "fire_flipbook.png"))


def smoke_dark(out):
    rng = rng_for("smoke_dark")
    a, sh = _puff(rng, lobes=30, wisp=0.7, softness=1.0)
    a = np.clip(1 - (1 - a) ** 1.8, 0, 1)                  # denser
    base = lin_to_srgb(np.array([0.045, 0.04, 0.035], np.float32))
    lit = lin_to_srgb(np.array([0.16, 0.145, 0.13], np.float32))
    rgb = base[None, None, :] + (lit - base)[None, None, :] * ((sh - 0.58) / 0.42)[..., None]
    img = np.dstack([np.round(np.clip(rgb, 0, 1) * 255), np.round(a * 255)]).astype(np.uint8)
    _save_png(img, os.path.join(out, "smoke_dark.png"))


def window_tape(out):
    """Anti-blast gummed paper tape on a window pane (pane = whole texture): border, X and centre cross."""
    rng = rng_for("window_tape")
    S, ss = 512, 4
    sc = StrokeCanvas(S, {"a": 0.0, "layers": 0.0}, ss=ss)
    wpx = 22.0
    strips = [((wpx / 2, 0), (wpx / 2, S)), ((S - wpx / 2, 0), (S - wpx / 2, S)),
              ((0, wpx / 2), (S, wpx / 2)), ((0, S - wpx / 2), (S, S - wpx / 2)),
              ((0, 0), (S, S)), ((S, 0), (0, S)), ((S / 2, 0), (S / 2, S)), ((0, S / 2), (S, S / 2))]
    acc = np.zeros((S, S), np.float32)
    for (p0, p1) in strips:
        p0 = np.array(p0, np.float64) + rng.normal(0, 1.5, 2)
        p1 = np.array(p1, np.float64) + rng.normal(0, 1.5, 2)
        one = StrokeCanvas(S, {"a": 0.0}, ss=ss)
        pts = np.linspace(p0, p1, 24)
        w = wpx * (1 + 0.04 * rng.standard_normal(24))
        # draw unwrapped: clip to the pane instead of wrapping
        d = p1 - p0
        nrm = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9)
        poly = np.concatenate([pts + nrm * w[:, None] / 2, (pts - nrm * w[:, None] / 2)[::-1]])
        from PIL import ImageDraw
        dr = ImageDraw.Draw(one.imgs["a"])
        dr.polygon([(x * ss, y * ss) for x, y in poly], fill=1.0)
        acc += one.get("a")
    cover = np.clip(acc, 0, 1)
    rag = cv2.GaussianBlur(rng.standard_normal((S, S)).astype(np.float32), (0, 0), 1.2)
    edge = cv2.GaussianBlur(cover, (0, 0), 1.0)
    cover = np.clip((edge - 0.5) * 3 + 0.5 + rag * 0.25, 0, 1) * (edge > 0.02)
    fib = norm01(cv2.GaussianBlur(rng.standard_normal((S, S)).astype(np.float32), (0, 0), 0.8))
    blot = norm01(cv2.GaussianBlur(rng.standard_normal((S, S)).astype(np.float32), (0, 0), 25))
    base = hexlin("#bfa57c")
    col = base[None, None, :] * (0.92 + 0.12 * fib[..., None]) * (0.9 + 0.15 * blot[..., None])
    overlap = np.clip(acc - 1, 0, 1)
    col = col * (1 - 0.18 * overlap[..., None])            # double layers read darker
    alpha = cover * np.clip(0.82 + 0.1 * overlap + 0.06 * fib, 0, 1)
    rgb = lin_to_srgb(np.clip(col, 0, 1))
    rgb[alpha < 0.01] = lin_to_srgb(base)
    img = np.dstack([np.round(rgb * 255), np.round(alpha * 255)]).astype(np.uint8)
    _save_png(img, os.path.join(out, "window_tape.png"))


def glass_shards(out):
    """Scattered broken window-glass fragments decal: faint greenish body, bright edges, glints."""
    from PIL import ImageDraw
    rng = rng_for("glass_shards")
    S, ss = 512, 4
    body = Image.new("F", (S * ss, S * ss), 0.0)
    edges = Image.new("F", (S * ss, S * ss), 0.0)
    db, de = ImageDraw.Draw(body), ImageDraw.Draw(edges)
    for i in range(240):
        r = float(np.exp(rng.uniform(np.log(3), np.log(40))))
        cx, cy = rng.uniform(r, S - r, 2) if r < S / 4 else rng.uniform(S * 0.25, S * 0.75, 2)
        k = int(rng.integers(3, 6))
        ang = np.sort(rng.uniform(0, TAU, k))
        rad = r * rng.uniform(0.35, 1.0, k)
        rad[rng.integers(k)] *= rng.uniform(1.5, 2.5)            # long sliver point
        pts = [((cx + np.cos(a) * q) * ss, (cy + np.sin(a) * q * 0.9) * ss) for a, q in zip(ang, rad)]
        db.polygon(pts, fill=float(rng.uniform(0.25, 0.45)))
        de.line(pts + [pts[0]], fill=1.0, width=max(1, int(ss * rng.uniform(0.6, 1.4))))
    b = cv2.resize(np.asarray(body, np.float32), (S, S), interpolation=cv2.INTER_AREA)
    e = cv2.resize(np.asarray(edges, np.float32), (S, S), interpolation=cv2.INTER_AREA)
    glint = (rng.random((S, S)) > 0.9993).astype(np.float32)
    glint = cv2.GaussianBlur(glint, (0, 0), 0.8) * 6 * (b > 0.1)
    alpha = np.clip(b + e * 0.6 + glint, 0, 1)
    shade = np.clip(0.55 + 0.45 * e + glint, 0, 1)
    tint = np.array([0.72, 0.8, 0.76], np.float32)
    rgb = lin_to_srgb(np.clip(shade[..., None] * tint[None, None, :] + glint[..., None] * 0.3, 0, 1))
    rgb[alpha < 0.01] = lin_to_srgb(tint * 0.6)
    img = np.dstack([np.round(rgb * 255), np.round(alpha * 255)]).astype(np.uint8)
    _save_png(img, os.path.join(out, "glass_shards.png"))


FX_DOC = {
    "rain_ripples_normal.png": {"size": [2048, 2048], "layout": "4x4 flipbook, 16 frames of 512x512, row-major "
                                "from top-left; loops (frame 15 -> 0); each frame tiles. OpenGL tangent normals, "
                                "flat = (128,128,255).", "suggestedTileMetres": 1.0, "fps": 16},
    "footprints_alpha.png": {"size": [1024, 1024], "layout": "4 cols x 2 rows of 256x512 cells, toe towards the "
                             "top of the image (+V); sole ~0.295 m ~= 340 px (1150 px/m, cell = 0.22 x 0.445 m). "
                             "RGB = OpenGL normal of the depression, A = decal mask. Cells (row-major): " +
                             ", ".join(l for l, *_ in FOOTPRINT_LAYOUT) + ".",
                             "cellMetres": [0.2226, 0.4452]},
    "smoke_puff.png": {"size": [512, 512], "layout": "single sprite, straight alpha, RGB light-grey self-shadowed "
                       "shading (never black in transparent texels; safe to premultiply)."},
    "dust_puff.png": {"size": [512, 512], "layout": "single sprite, tan/brown dust, softer & wispier, straight alpha."},
    "cloud_noise.png": {"size": [1024, 1024], "layout": "tileable; R = broad fbm masses, G = ridged/billow mid "
                        "detail, B = fine cellular wisps. Linear data."},
    "blue_noise.png": {"size": [128, 128], "layout": "8-bit greyscale void-and-cluster blue noise, tileable."},
    "water_normal.png": {"size": [1024, 1024], "layout": "tileable small wind-wave normal map (OpenGL), "
                         "Phillips spectrum, designed for ~2 m tile.", "suggestedTileMetres": 2.0},
    "grass_blade_atlas.png": {"size": [1024, 1024], "layout": "4 cols x 2 rows of 256x512 cells; each a dead/autumn "
                              "grass tuft card with its base at the bottom centre of the cell; sRGB colour, "
                              "alpha-tested (A>0.5); colours dilated into transparent texels.",
                              "cardMetres": [0.3, 0.6]},
    "fire_flipbook.png": {"size": [2048, 2048], "layout": "8x8 flipbook, 64 frames of 256x256, row-major from the "
                          "top left, loops (frame 63 -> 0). RGB = emissive flame colour (sRGB, use additively or "
                          "as emissive), A = flame mask; flame base at the bottom centre of each frame.", "fps": 24},
    "smoke_dark.png": {"size": [512, 512], "layout": "single dense dark smoke puff (burning buildings), straight "
                       "alpha, self-shadowed dark grey-brown RGB."},
    "window_tape.png": {"size": [512, 512], "layout": "whole texture = one window pane: brown gummed anti-blast "
                        "paper tape (border, X and centre cross), straight alpha ~0.85, transparent elsewhere."},
    "glass_shards.png": {"size": [512, 512], "layout": "decal of scattered broken window glass on the ground: "
                         "faint greenish bodies, bright edges and glints in RGB, A = coverage. Not tileable."},
    "barbed_wire_alpha.png": {"size": [512, 128], "layout": "horizontal strip tiling along U: two twisted strands "
                              "with a 4-point barb every 128 px (~0.1 m if the strip is 0.4 m long).",
                              "stripMetres": [0.4, 0.1]},
}


def generate_all(out):
    os.makedirs(out, exist_ok=True)
    steps = [("rain_ripples", rain_ripples), ("footprints", footprints), ("smoke/dust", smoke_and_dust),
             ("cloud_noise", cloud_noise), ("blue_noise", blue_noise), ("water_normal", water_normal),
             ("grass_atlas", grass_atlas), ("barbed_wire", barbed_wire), ("fire_flipbook", fire_flipbook),
             ("smoke_dark", smoke_dark), ("window_tape", window_tape), ("glass_shards", glass_shards)]
    import time
    for label, fn in steps:
        t = time.time()
        fn(out)
        print(f"[{time.time() - t:5.1f}s] fx {label}", flush=True)
    with open(os.path.join(out, "fx_manifest.json"), "w") as f:
        json.dump(FX_DOC, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.abspath(os.path.join(here, "..", "..", "..", "public", "assets", "textures", "fx"))
    if len(sys.argv) > 1:
        globals()[sys.argv[1]](out)
    else:
        generate_all(out)
