"""Core tileable-noise and image utilities.

Every operation here is periodic on the unit square (wrap-around), so anything built from
these primitives tiles seamlessly by construction:
  * spectral / FFT noise is periodic because the DFT is periodic,
  * lattice (Perlin) noise uses integer cell counts and wrapped lattice indices,
  * Worley/Voronoi uses a periodic KD-tree (boxsize),
  * blurs are FFT based, warps/remaps use wrapped coordinates, stamps wrap at the edges.
"""
from __future__ import annotations

import zlib

import cv2
import numpy as np
from scipy.spatial import cKDTree

N = 1024  # default texture resolution
TAU = 2.0 * np.pi


# --------------------------------------------------------------------------- seeding
def rng_for(name: str, salt: int = 0) -> np.random.Generator:
    """Deterministic RNG from a string (stable across runs/platforms)."""
    return np.random.default_rng(zlib.crc32(name.encode("utf8")) * 1000003 + salt)


# --------------------------------------------------------------------------- basics
def uv(n: int = N):
    """Pixel-centre coordinates in [0,1): returns (u, v_row) grids (row index grows downward)."""
    c = (np.arange(n, dtype=np.float32) + 0.5) / n
    return np.meshgrid(c, c)  # x (cols), y (rows)


def norm01(a, lo_pct=0.5, hi_pct=99.5):
    lo, hi = np.percentile(a, [lo_pct, hi_pct])
    return np.clip((a - lo) / max(hi - lo, 1e-9), 0.0, 1.0).astype(np.float32)


def standardize(a):
    a = a - a.mean()
    return (a / (a.std() + 1e-9)).astype(np.float32)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hexlin(h: str):
    """'#rrggbb' sRGB hex -> linear RGB float32 triple."""
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return srgb_to_lin(np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32))


def ramp(t, stops):
    """Gradient map. stops: list of (pos, '#hex' or linear rgb). t: HxW -> HxWx3 (linear)."""
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.array([hexlin(s[1]) if isinstance(s[1], str) else s[1] for s in stops], np.float32)
    t = np.clip(t, pos[0], pos[-1])
    out = np.empty(t.shape + (3,), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, cols[:, ch])
    return out


def mix(a, b, t):
    """Blend colour images / colours by scalar field t (HxW)."""
    if np.ndim(t) == 2 and (np.shape(a)[-1:] == (3,) or np.shape(b)[-1:] == (3,)):
        t = t[..., None]
    return a + (b - a) * t


def luminance(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


# --------------------------------------------------------------------------- FFT helpers
def _kgrid(n):
    k = np.fft.fftfreq(n) * n  # integer wave numbers (cycles per tile)
    return np.meshgrid(k, k)  # kx (cols), ky (rows)


def blur(a, sigma_x, sigma_y=None, angle=0.0):
    """Periodic Gaussian blur (sigma in pixels), optionally anisotropic + rotated (radians).
    Works on 2-D or HxWxC arrays."""
    if sigma_y is None:
        sigma_y = sigma_x
    if sigma_x <= 0 and sigma_y <= 0:
        return a
    n = a.shape[0]
    kx, ky = _kgrid(n)
    c, s = np.cos(angle), np.sin(angle)
    ku = (kx * c + ky * s) / n
    kv = (-kx * s + ky * c) / n
    H = np.exp(-2 * np.pi ** 2 * ((sigma_x * ku) ** 2 + (sigma_y * kv) ** 2))
    if a.ndim == 3:
        return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., i]) * H)) for i in range(a.shape[2])], -1).astype(np.float32)
    return np.real(np.fft.ifft2(np.fft.fft2(a) * H)).astype(np.float32)


def spectral(rng, n=N, beta=2.0, fmin=1.0, fmax=None, stretch=(1.0, 1.0), angle=0.0):
    """Periodic 1/f^beta noise via FFT. stretch=(sx, sy) elongates features along x/y
    (sx>1 = features longer along x). Returns zero-mean, unit-std float32."""
    kx, ky = _kgrid(n)
    c, s = np.cos(angle), np.sin(angle)
    ku = kx * c + ky * s
    kv = -kx * s + ky * c
    k = np.sqrt((ku * stretch[0]) ** 2 + (kv * stretch[1]) ** 2)
    k[0, 0] = 1e9
    amp = np.power(np.maximum(k, 1e-6), -beta / 2.0)
    amp *= smoothstep(fmin * 0.5, fmin, k)
    if fmax is not None:
        amp *= 1.0 - smoothstep(fmax, fmax * 1.6, k)
    amp[0, 0] = 0
    w = rng.standard_normal((n, n)).astype(np.float32)
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * amp))
    return standardize(out)


def bandnoise(rng, n=N, f=8.0, width=0.5, stretch=(1.0, 1.0), angle=0.0):
    """Noise concentrated around spatial frequency f (cycles/tile): log-gaussian band."""
    kx, ky = _kgrid(n)
    c, s = np.cos(angle), np.sin(angle)
    ku = kx * c + ky * s
    kv = -kx * s + ky * c
    k = np.sqrt((ku * stretch[0]) ** 2 + (kv * stretch[1]) ** 2)
    k[0, 0] = 1e-6
    amp = np.exp(-0.5 * (np.log(k / f) / width) ** 2)
    amp[0, 0] = 0
    w = rng.standard_normal((n, n)).astype(np.float32)
    return standardize(np.real(np.fft.ifft2(np.fft.fft2(w) * amp)))


# --------------------------------------------------------------------------- lattice noise
def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def perlin(rng, freq, n=N):
    """Periodic gradient noise with integer `freq` cells (int or (fx, fy))."""
    fx, fy = (freq, freq) if np.isscalar(freq) else freq
    fx, fy = int(max(1, fx)), int(max(1, fy))
    ang = rng.uniform(0, TAU, (fy, fx))
    gx, gy = np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32)
    xs = (np.arange(n) + 0.5) * fx / n
    ys = (np.arange(n) + 0.5) * fy / n
    x0 = np.floor(xs).astype(int); tx = (xs - x0).astype(np.float32); x0 %= fx; x1 = (x0 + 1) % fx
    y0 = np.floor(ys).astype(int); ty = (ys - y0).astype(np.float32); y0 %= fy; y1 = (y0 + 1) % fy

    def dot(iy, ix, dy, dx):
        return gx[iy[:, None], ix[None, :]] * dx[None, :] + gy[iy[:, None], ix[None, :]] * dy[:, None]

    n00 = dot(y0, x0, ty, tx)
    n10 = dot(y0, x1, ty, tx - 1)
    n01 = dot(y1, x0, ty - 1, tx)
    n11 = dot(y1, x1, ty - 1, tx - 1)
    sx = _fade(tx)[None, :]
    sy = _fade(ty)[:, None]
    return (lerp(lerp(n00, n10, sx), lerp(n01, n11, sx), sy) * 1.4142).astype(np.float32)


def fbm(rng, base, octaves=6, gain=0.5, lac=2.0, n=N, ridged=False):
    out = np.zeros((n, n), np.float32)
    amp, tot = 1.0, 0.0
    fx, fy = (base, base) if np.isscalar(base) else base
    for i in range(octaves):
        f = (int(round(fx * lac ** i)), int(round(fy * lac ** i)))
        if min(f) > n // 2:
            break
        p = perlin(rng, f, n)
        if ridged:
            p = 1.0 - np.abs(p)
            p = p * p
        out += amp * p
        tot += amp
        amp *= gain
    return out / tot


# --------------------------------------------------------------------------- voronoi
def worley(rng, npts=None, pts=None, n=N, k=2, aspect=(1.0, 1.0), metric=2):
    """Periodic Voronoi. Returns (dist[k], idx[k], pts). Distances are in UV units (x scaled
    by aspect[0], y by aspect[1]). pts are (x, y) in [0,1)."""
    if pts is None:
        pts = rng.random((npts, 2))
    ax, ay = aspect
    box = np.array([ax, ay])
    sp = np.mod(pts, 1.0) * box
    sp = np.minimum(sp, box - 1e-9)
    tree = cKDTree(sp, boxsize=box)
    u, v = uv(n)
    q = np.stack([u.ravel() * ax, v.ravel() * ay], -1)
    d, i = tree.query(q, k=k, p=metric, workers=-1)
    d = d.reshape(n, n, k).astype(np.float32)
    i = i.reshape(n, n, k)
    return d, i, pts


def voronoi_edge_dist(rng, pts, n=N, aspect=(1.0, 1.0), k=3):
    """Approximate true distance to the Voronoi edge (UV units), cell id and pts."""
    d, idx, pts = worley(rng, pts=pts, n=n, k=k, aspect=aspect)
    ax, ay = aspect
    u, v = uv(n)
    P = np.stack([u * ax, v * ay], -1)
    sp = np.mod(pts, 1.0) * np.array([ax, ay])
    best = np.full((n, n), 1e9, np.float32)
    a = sp[idx[..., 0]]
    da = _wrapvec(P - a, ax, ay)
    for j in range(1, k):
        b = sp[idx[..., j]]
        ab = _wrapvec(b - a, ax, ay)
        # distance from P to the bisector of a and b
        L = np.linalg.norm(ab, axis=-1) + 1e-9
        dist = np.abs(np.sum((da - ab * 0.5) * ab, -1) / L)
        best = np.minimum(best, dist)
    return best, idx[..., 0], pts


def _wrapvec(dv, ax, ay):
    dv = dv.copy()
    dv[..., 0] -= ax * np.round(dv[..., 0] / ax)
    dv[..., 1] -= ay * np.round(dv[..., 1] / ay)
    return dv


# --------------------------------------------------------------------------- warping
def warp(img, dx, dy, interp=cv2.INTER_LINEAR):
    """Sample img at (x+dx, y+dy) (pixels) with wrap-around."""
    n = img.shape[0]
    X, Y = np.meshgrid(np.arange(n, dtype=np.float32), np.arange(n, dtype=np.float32))
    mx = np.mod(X + dx, n).astype(np.float32)
    my = np.mod(Y + dy, n).astype(np.float32)
    src = img.astype(np.float32)
    return cv2.remap(src, mx, my, interp, borderMode=cv2.BORDER_WRAP)


def resize(a, size, interp=cv2.INTER_AREA):
    return cv2.resize(a.astype(np.float32), (size, size), interpolation=interp)


def tile_upsample(a, size):
    """Periodic upsample of a small tileable array to size (cubic, wrap)."""
    m = a.shape[0]
    pad = 4
    big = np.pad(a, ((pad, pad), (pad, pad)) + ((0, 0),) * (a.ndim - 2), mode="wrap")
    scale = size / m
    r = cv2.resize(big.astype(np.float32), (int(round(big.shape[1] * scale)), int(round(big.shape[0] * scale))),
                   interpolation=cv2.INTER_CUBIC)
    o = int(round(pad * scale))
    return r[o:o + size, o:o + size]


# --------------------------------------------------------------------------- stamping
def stamp(canvas, sprite, x, y, mode="max", alpha=None, value_scale=1.0):
    """Paste sprite (h x w [x c]) centred at pixel (x, y) with wrap-around.
    mode: 'max', 'add', 'over' (needs alpha), 'min', 'mul'."""
    n0, n1 = canvas.shape[:2]
    h, w = sprite.shape[:2]
    x0 = int(round(x - w / 2.0))
    y0 = int(round(y - h / 2.0))
    ys = (np.arange(y0, y0 + h) % n0)
    xs = (np.arange(x0, x0 + w) % n1)
    region = canvas[np.ix_(ys, xs)]
    s = sprite * value_scale
    if mode == "max":
        region = np.maximum(region, s)
    elif mode == "min":
        region = np.minimum(region, s)
    elif mode == "add":
        region = region + s
    elif mode == "mul":
        region = region * s
    elif mode == "over":
        a = alpha if region.ndim == alpha.ndim else alpha[..., None]
        region = region * (1 - a) + s * a
    canvas[np.ix_(ys, xs)] = region
    return canvas


def blob_sprite(rng, r_px, roughness=0.35, angular=0.0, elong=1.0, lumps=6, res_pad=3, faceted=0.0):
    """Irregular rock/clod mask with a domed height. Returns (height[0..1], mask[0..1]).
    angular>0 gives faceted silhouettes (chalk/rubble), elong stretches it."""
    R = int(np.ceil(r_px * max(1.0, elong) * 1.6)) + res_pad
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
    ang0 = rng.uniform(0, TAU)
    c, s = np.cos(ang0), np.sin(ang0)
    xr = (xx * c + yy * s) / elong
    yr = -xx * s + yy * c
    th = np.arctan2(yr, xr)
    rr = np.sqrt(xr ** 2 + yr ** 2)
    rad = np.ones_like(th)
    for k in range(2, 2 + lumps):
        rad += roughness / k * rng.uniform(0.4, 1.0) * np.cos(k * th + rng.uniform(0, TAU))
    if angular > 0:  # polygonal facets
        m = rng.integers(4, 8)
        phis = np.sort(rng.uniform(0, TAU, m))
        poly = np.full_like(th, 1e9)
        for p in phis:
            dirx, diry = np.cos(p), np.sin(p)
            dist = rng.uniform(0.75, 1.0)
            # distance to half-plane, in units of radius
            proj = (xr * dirx + yr * diry) / max(r_px, 1e-6)
            poly = np.minimum(poly, dist - proj)
        circ = rad - rr / max(r_px, 1e-6)
        sdf = (1 - angular) * circ + angular * np.minimum(circ, poly * 1.2)
    else:
        sdf = rad - rr / max(r_px, 1e-6)
    sdf = sdf * r_px  # pixels inside (>0)
    mask = np.clip(sdf + 0.5, 0, 1)
    dome = np.sqrt(np.clip(sdf / max(r_px, 1e-6), 0, 1))
    if faceted > 0:  # convex chunk: min of a few tilted planes -> flat facets with crisp arrises
        top = np.full_like(xr, 1.0)
        m = rng.integers(4, 8)
        for p in rng.uniform(0, TAU, m):
            slope = np.tan(np.radians(rng.uniform(20, 55)))
            off = rng.uniform(0.2, 0.7)
            proj = (xx * np.cos(p) + yy * np.sin(p)) / max(r_px, 1e-6)
            top = np.minimum(top, off + 0.35 + slope * (1.0 - proj) * 0.5 - 0.5 * slope * 0.3)
        top = np.clip(top, 0, None)
        top = top / (top[mask > 0.5].max() + 1e-6) if (mask > 0.5).any() else top
        edge = np.clip(sdf / max(r_px * 0.15, 1.0), 0, 1)  # rounded-off rim
        dome = (1 - faceted) * dome + faceted * np.minimum(top, 1.0) * np.sqrt(edge)
    return dome.astype(np.float32), mask.astype(np.float32)


# --------------------------------------------------------------------------- strokes
def draw_polyline_wrapped(draw_fn, pts, n):
    """Call draw_fn(pts_offset) for every wrap offset that may intersect the tile."""
    pts = np.asarray(pts, np.float32)
    lo = pts.min(0)
    hi = pts.max(0)
    for ox in (-n, 0, n):
        for oy in (-n, 0, n):
            if hi[0] + ox < -8 or lo[0] + ox > n + 8 or hi[1] + oy < -8 or lo[1] + oy > n + 8:
                continue
            draw_fn(pts + np.array([ox, oy], np.float32))
