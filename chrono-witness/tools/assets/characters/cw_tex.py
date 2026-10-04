"""Procedural texture authoring (numpy only).

Workflow: rasterize a mesh's triangles into UV space to get, per texel, the 3D rest-pose
position, normal and any custom per-corner attribute ("texel -> 3D"), evaluate procedural
3D fields there (noise, landmark distances, seams ...), convert height fields into
tangent-space normal maps (OpenGL convention, +Y = +V) and dilate across island borders.
All of it is own work - no external images are used.
"""
import numpy as np
from PIL import Image

# ----------------------------------------------------------------------------------
# rasterizer
# ----------------------------------------------------------------------------------


def rasterize(uv, attrs, N, pad_tri=0.5):
    """uv: (T,3,2) per-corner UVs (Blender convention, v up).  attrs: {name: (T,3,C)}.
    Returns dict name -> (N,N,C) float32 images, plus 'mask' (N,N) bool and 'tri' (N,N) int.
    Image row 0 is v = 1 (top), matching how glTF/three.js sample the image."""
    T = uv.shape[0]
    px = uv[..., 0] * N - 0.5
    py = (1.0 - uv[..., 1]) * N - 0.5
    out = {k: np.zeros((N, N, v.shape[-1]), np.float32) for k, v in attrs.items()}
    mask = np.zeros((N, N), bool)
    tri = -np.ones((N, N), np.int32)
    x0 = np.floor(px.min(1) - pad_tri).astype(int).clip(0, N - 1)
    x1 = np.ceil(px.max(1) + pad_tri).astype(int).clip(0, N - 1)
    y0 = np.floor(py.min(1) - pad_tri).astype(int).clip(0, N - 1)
    y1 = np.ceil(py.max(1) + pad_tri).astype(int).clip(0, N - 1)
    keys = list(attrs.keys())
    av = [attrs[k] for k in keys]
    for t in range(T):
        xs = np.arange(x0[t], x1[t] + 1)
        ys = np.arange(y0[t], y1[t] + 1)
        if len(xs) == 0 or len(ys) == 0:
            continue
        gx, gy = np.meshgrid(xs, ys)
        ax, ay = px[t, 0], py[t, 0]
        bx, by = px[t, 1], py[t, 1]
        cx, cy = px[t, 2], py[t, 2]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        w2 = 1 - w0 - w1
        eps = -0.02  # tiny overlap so triangle edges leave no holes
        ins = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not ins.any():
            continue
        yy, xx = gy[ins], gx[ins]
        b0, b1, b2 = w0[ins], w1[ins], w2[ins]
        for k, a in zip(keys, av):
            out[k][yy, xx] = b0[:, None] * a[t, 0] + b1[:, None] * a[t, 1] + b2[:, None] * a[t, 2]
        mask[yy, xx] = True
        tri[yy, xx] = t
    out["mask"] = mask
    out["tri"] = tri
    return out


def dilate(img, mask, iters=12):
    """Grow island borders outwards (prevents seams under mip-mapping)."""
    img = img.copy()
    m = mask.copy()
    if img.ndim == 2:
        img = img[..., None]
        squeeze = True
    else:
        squeeze = False
    for _ in range(iters):
        acc = np.zeros_like(img)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sm = np.roll(np.roll(m, dy, 0), dx, 1)
            si = np.roll(np.roll(img, dy, 0), dx, 1)
            acc += si * sm[..., None]
            cnt += sm
        grow = (~m) & (cnt > 0)
        img[grow] = acc[grow] / cnt[grow][:, None]
        m = m | grow
        if m.all():
            break
    # fill the rest with the mean
    if not m.all():
        img[~m] = img[m].mean(0) if m.any() else 0
    return img[..., 0] if squeeze else img


# ----------------------------------------------------------------------------------
# noise
# ----------------------------------------------------------------------------------

_PERM = np.random.default_rng(1916).permutation(4096).astype(np.int64)
_GRAD = np.random.default_rng(1917).normal(size=(4096, 3))
_GRAD /= np.linalg.norm(_GRAD, axis=1, keepdims=True)


def _hash3(ix, iy, iz, seed=0):
    h = _PERM[(ix + seed * 131) & 4095]
    h = _PERM[(h + iy) & 4095]
    return _PERM[(h + iz) & 4095]


def gnoise(p, seed=0):
    """3D gradient (Perlin-style) noise, p (...,3) -> (...) in ~[-1,1]."""
    p = np.asarray(p, np.float64)
    sh = p.shape[:-1]
    p = p.reshape(-1, 3)
    pi = np.floor(p).astype(np.int64)
    pf = p - pi
    u = pf * pf * pf * (pf * (pf * 6 - 15) + 10)
    res = 0
    vals = {}
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                g = _GRAD[_hash3(pi[:, 0] + dx, pi[:, 1] + dy, pi[:, 2] + dz, seed)]
                d = pf - np.array([dx, dy, dz])
                vals[(dx, dy, dz)] = (g * d).sum(1)
    x00 = vals[(0, 0, 0)] * (1 - u[:, 0]) + vals[(1, 0, 0)] * u[:, 0]
    x10 = vals[(0, 1, 0)] * (1 - u[:, 0]) + vals[(1, 1, 0)] * u[:, 0]
    x01 = vals[(0, 0, 1)] * (1 - u[:, 0]) + vals[(1, 0, 1)] * u[:, 0]
    x11 = vals[(0, 1, 1)] * (1 - u[:, 0]) + vals[(1, 1, 1)] * u[:, 0]
    y0 = x00 * (1 - u[:, 1]) + x10 * u[:, 1]
    y1 = x01 * (1 - u[:, 1]) + x11 * u[:, 1]
    res = y0 * (1 - u[:, 2]) + y1 * u[:, 2]
    return (res * 1.8).reshape(sh)


def fbm(p, octaves=4, lac=2.0, gain=0.5, seed=0):
    p = np.asarray(p, np.float64)
    out = np.zeros(p.shape[:-1])
    a = 1.0
    tot = 0
    for o in range(octaves):
        out += a * gnoise(p * (lac ** o), seed + o * 7)
        tot += a
        a *= gain
    return out / tot


def worley(p, seed=0):
    """F1 and F2 cellular distances (cell size 1) for p (...,3)."""
    p = np.asarray(p, np.float64)
    sh = p.shape[:-1]
    p = p.reshape(-1, 3)
    pi = np.floor(p).astype(np.int64)
    f1 = np.full(len(p), 9.0)
    f2 = np.full(len(p), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = pi + np.array([dx, dy, dz])
                h = _hash3(c[:, 0], c[:, 1], c[:, 2], seed)
                fp = c + (np.stack([_PERM[h], _PERM[(h * 7 + 3) & 4095], _PERM[(h * 13 + 5) & 4095]], 1) / 4096.0)
                d = np.linalg.norm(p - fp, axis=1)
                f2 = np.where(d < f1, f1, np.minimum(f2, d))
                f1 = np.minimum(f1, d)
    return f1.reshape(sh), f2.reshape(sh)


# ----------------------------------------------------------------------------------
# normal maps / output
# ----------------------------------------------------------------------------------


def texel_scale(pos, mask):
    """World metres per texel along +u (x) and +v (row up) from a position image."""
    gx = np.gradient(pos, axis=1)
    gy = -np.gradient(pos, axis=0)
    su = np.linalg.norm(gx, axis=-1)
    sv = np.linalg.norm(gy, axis=-1)
    med = np.median(su[mask]) if mask.any() else 1e-3
    su = np.where(mask & (su > 0) & (su < med * 6), su, med)
    medv = np.median(sv[mask]) if mask.any() else 1e-3
    sv = np.where(mask & (sv > 0) & (sv < medv * 6), sv, medv)
    return su, sv


def height_to_normal(h, su, sv, strength=1.0):
    """Height (metres) -> tangent-space normal (OpenGL: green = +v)."""
    dhdx = np.gradient(h, axis=1) / su
    dhdy = -np.gradient(h, axis=0) / sv  # +v is up in the image
    n = np.stack([-dhdx * strength, -dhdy * strength, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


def encode_normal(n):
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def to_srgb8(lin):
    lin = np.clip(lin, 0, 1)
    s = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
    return np.clip(s * 255 + 0.5, 0, 255).astype(np.uint8)


def srgb(c):
    """sRGB 0-255 tuple -> linear float array."""
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def save_jpg(arr8, path, q=85):
    Image.fromarray(arr8).save(path, quality=q, optimize=True, subsampling=0 if arr8.ndim == 3 else 0)
    return path


def save_png(arr8, path):
    Image.fromarray(arr8).save(path)
    return path


def blur(img, r=1):
    """Cheap box blur (separable, wrap-free)."""
    out = img.astype(np.float32)
    for ax in (0, 1):
        acc = np.zeros_like(out)
        for d in range(-r, r + 1):
            acc += np.roll(out, d, ax)
        out = acc / (2 * r + 1)
    return out


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-12), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    t = np.asarray(t)
    if np.ndim(a) and np.asarray(a).shape[-1] == 3 and np.ndim(t) and t.shape[-1:] != (3,):
        t = t[..., None]
    return a * (1 - t) + b * t
