"""Reusable procedural elements: boot prints, stone scatter, wood grain, puddles."""
from __future__ import annotations

import cv2
import numpy as np

from .core import N, TAU, blob_sprite, blur, smoothstep, spectral, stamp, warp


# --------------------------------------------------------------------------- boot print
def boot_outline(left=True):
    """British 1914 'ammunition boot' sole outline, metres, heel at y=0, toe at +y."""
    L = 0.295
    # (s along length 0..1, half width m) for sole (front) and heel
    sole = [(0.34, 0.033), (0.40, 0.037), (0.50, 0.043), (0.60, 0.049), (0.70, 0.052), (0.78, 0.052),
            (0.86, 0.048), (0.92, 0.040), (0.96, 0.031), (0.985, 0.019), (1.0, 0.0)]
    heel = [(0.0, 0.0), (0.01, 0.022), (0.035, 0.033), (0.08, 0.037), (0.16, 0.038), (0.25, 0.036), (0.27, 0.035)]
    bulge = 0.006  # big-toe side bulge (medial side)
    side = -1.0 if left else 1.0

    def poly(prof, close_back):
        right = [(w + (bulge if side > 0 else 0) * np.sin(np.pi * np.clip((s - 0.55) / 0.45, 0, 1)), s * L) for s, w in prof]
        leftp = [(-w - (bulge if side < 0 else 0) * np.sin(np.pi * np.clip((s - 0.55) / 0.45, 0, 1)), s * L) for s, w in prof]
        pts = right + leftp[::-1]
        return np.array(pts, np.float32)

    sole_poly = poly(sole, False)
    sole_poly = np.vstack([sole_poly, [[-0.033, 0.34 * L], [0.033, 0.34 * L]]])
    heel_poly = poly(heel, True)
    return sole_poly, heel_poly, L


def boot_print(rng, ppm, depth=0.02, left=True, smear=0.0, partial=1.0, hobnails=True, stud_depth=0.0025):
    """Height-map of a boot print (negative = depression) in metres, plus mask.
    ppm = pixels per metre. Returns (height, mask) arrays sized to fit the print + rim."""
    sole_poly, heel_poly, L = boot_outline(left)
    ss = 4  # supersample
    pad = 0.05
    W = int(np.ceil((0.11 + 2 * pad) * ppm))
    H = int(np.ceil((L + 2 * pad) * ppm))
    sc = ppm * ss

    def to_px(p):
        q = np.empty_like(p)
        q[:, 0] = (p[:, 0] + 0.055 + pad) * sc
        q[:, 1] = (L + pad - p[:, 1]) * sc  # toe at top
        return np.round(q).astype(np.int32)

    big = np.zeros((H * ss, W * ss), np.uint8)
    cv2.fillPoly(big, [to_px(sole_poly)], 255)
    sole_m = big.copy()
    big2 = np.zeros_like(big)
    cv2.fillPoly(big2, [to_px(heel_poly)], 255)
    heel_m = big2
    allm = np.maximum(sole_m, heel_m)
    din = cv2.distanceTransform(allm, cv2.DIST_L2, 5) / sc            # metres inside
    dout = cv2.distanceTransform(255 - allm, cv2.DIST_L2, 5) / sc     # metres outside
    din_heel = cv2.distanceTransform(heel_m, cv2.DIST_L2, 5) / sc
    din_sole = cv2.distanceTransform(sole_m, cv2.DIST_L2, 5) / sc

    yy, xx = np.mgrid[0:H * ss, 0:W * ss].astype(np.float32)
    ym = L + pad - yy / sc   # metres along boot (0 heel .. L toe)
    xm = xx / sc - 0.055 - pad

    wall = 0.006
    h = -depth * smoothstep(0, wall, din)
    # sole bottom isn't flat: toe lifts (rocker), heel deeper (weight)
    s = np.clip(ym / L, 0, 1)
    h *= (1.0 - 0.35 * smoothstep(0.85, 1.0, s)) * (1.0 + 0.15 * smoothstep(0.3, 0.0, s))
    # raised displaced-mud rim
    rim = 0.45 * depth * np.exp(-((dout - 0.008) / 0.012) ** 2) * (dout > 0)
    h += rim
    if hobnails:
        studs = np.zeros_like(h)
        r_st = 0.0035
        pts = []
        # edge row around sole
        cnt = cv2.findContours(sole_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0][0][:, 0, :].astype(np.float32)
        perim = np.cumsum(np.r_[0, np.linalg.norm(np.diff(cnt, axis=0), axis=1)])
        step = 0.0125 * sc
        for t in np.arange(0, perim[-1], step):
            i = np.searchsorted(perim, t)
            i = min(i, len(cnt) - 1)
            p = cnt[i]
            pts.append(p)
        pts = np.array(pts)
        # pull edge studs inward by ~6mm
        cx, cy = np.mean(cnt[:, 0]), np.mean(cnt[:, 1])
        inner = []
        for p in pts:
            d = np.array([cx, cy]) - p
            d /= np.linalg.norm(d) + 1e-6
            inner.append(p + d * 0.007 * sc)
        pts = list(inner)
        # inner grid of studs on the tread
        for yb in np.arange(0.40, 0.92, 0.055):
            for xb in np.arange(-0.03, 0.031, 0.02):
                yy_m = yb * L
                px_ = (xb + 0.055 + pad) * sc
                py_ = (L + pad - yy_m) * sc
                if sole_m[int(py_), int(px_)] and din_sole[int(py_), int(px_)] > 0.012:
                    pts.append(np.array([px_, py_]))
        pts = np.array(pts)
        for p in pts:
            d2 = ((xx - p[0]) ** 2 + (yy - p[1]) ** 2) / sc ** 2
            studs += np.exp(-d2 / (r_st ** 2))
        h -= np.clip(studs, 0, 1) * stud_depth * (din > 0.002)
        # heel iron: horseshoe band at the heel rim
        band = smoothstep(0.001, 0.003, din_heel) * smoothstep(0.014, 0.010, din_heel)
        h -= band * 0.003
        # toe plate
        toe = (s > 0.9) * smoothstep(0.001, 0.003, din_sole) * smoothstep(0.012, 0.008, din_sole)
        h -= toe * 0.0025
    # instep (waist between heel and sole) barely touches -> shallower
    waist = smoothstep(0.26, 0.30, s) * smoothstep(0.38, 0.33, s)
    h *= 1.0 - 0.6 * waist
    if partial < 1.0:  # only front or back part pressed (walking)
        fade = smoothstep(partial - 0.15, partial + 0.05, s if rng.random() < 0.5 else 1 - s)
        h *= 1 - fade
    h = cv2.resize(h, (W, H), interpolation=cv2.INTER_AREA)
    mask = cv2.resize(((din > 0) | (dout < 0.02)).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
    if smear > 0:
        sm = cv2.GaussianBlur(h, (0, 0), sigmaX=0.6 + smear * 2.0, sigmaY=0.6 + smear * 5.0)
        h = h * (1 - smear) + sm * smear
    return h.astype(np.float32), mask.astype(np.float32)


def rotate_sprite(img, angle_deg, scale=1.0):
    h, w = img.shape[:2]
    D = int(np.ceil(np.hypot(h, w) * scale)) + 2
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle_deg, scale)
    M[0, 2] += D / 2 - w / 2
    M[1, 2] += D / 2 - h / 2
    return cv2.warpAffine(img, M, (D, D), flags=cv2.INTER_LINEAR, borderValue=0)


# --------------------------------------------------------------------------- stones
def scatter_stones(rng, height, colour, count, r_range_px, palette, embed=(0.3, 0.7),
                   h_scale_m=0.01, angular=0.0, elong=(1.0, 1.6), roughness=0.35,
                   rough_map=None, rough_val=None, id_map=None, n=N, avoid=None, tint_jitter=0.15,
                   texture_fn=None, faceted=0.0, colour_fn=None, id_mode="mask"):
    """Scatter domed stones into `height` (metres) and `colour` (linear RGB) in place.
    Stones protrude above local surface by (1-embed) of their height. Palette is list of
    linear RGB arrays. r_range_px: (min,max) radius in pixels, log-uniform."""
    lo, hi = np.log(r_range_px[0]), np.log(r_range_px[1])
    for k in range(count):
        r = float(np.exp(rng.uniform(lo, hi)))
        x, y = rng.uniform(0, n, 2)
        if avoid is not None and avoid[int(y) % n, int(x) % n] > 0.5:
            continue
        dome, mask = blob_sprite(rng, r, roughness=roughness, angular=angular, elong=rng.uniform(*elong),
                                 faceted=faceted)
        hh, ww = dome.shape
        ys = (np.arange(int(round(y - hh / 2)), int(round(y - hh / 2)) + hh) % n)
        xs = (np.arange(int(round(x - ww / 2)), int(round(x - ww / 2)) + ww) % n)
        reg = height[np.ix_(ys, xs)]
        base = np.median(reg[mask > 0.5]) if (mask > 0.5).any() else reg.mean()
        sh = h_scale_m * (r / r_range_px[1]) ** 0.8 * rng.uniform(0.6, 1.2)
        emb = rng.uniform(*embed)
        # facet/texture noise on the stone surface
        tex = cv2.GaussianBlur(rng.standard_normal(dome.shape).astype(np.float32), (0, 0), max(0.6, r * 0.12))
        tex = tex / (tex.std() + 1e-6)
        stone_h = base + sh * (dome - emb) + sh * 0.08 * tex * dome
        newreg = np.where((stone_h > reg) & (mask > 0.02), mask * stone_h + (1 - mask) * reg, reg)
        vis = ((stone_h > reg) & (mask > 0.02)).astype(np.float32) * mask
        height[np.ix_(ys, xs)] = newreg
        pi = rng.integers(len(palette))
        col = palette[pi] * (1 + 0.04 * rng.standard_normal(3)) * np.exp(tint_jitter * rng.standard_normal())
        shade = (1 + 0.12 * tex)[..., None]
        if texture_fn is not None:
            shade = shade * texture_fn(rng, dome.shape)[..., None]
        scol = col[None, None, :] * shade
        if colour_fn is not None:
            scol = colour_fn(rng, pi, dome, mask, scol)
        creg = colour[np.ix_(ys, xs)]
        colour[np.ix_(ys, xs)] = creg * (1 - vis[..., None]) + scol * vis[..., None]
        if rough_map is not None and rough_val is not None:
            rreg = rough_map[np.ix_(ys, xs)]
            rv = rough_val + 0.05 * rng.standard_normal()
            rough_map[np.ix_(ys, xs)] = rreg * (1 - vis) + rv * vis
        if id_map is not None:
            ireg = id_map[np.ix_(ys, xs)]
            id_map[np.ix_(ys, xs)] = np.where(vis > 0.5, float(pi + 1), ireg) if id_mode == "palette" \
                else np.maximum(ireg, vis)
    return height, colour


# --------------------------------------------------------------------------- wood
def wood_grain_field(rng, n, length_px, width_px, ring_px=6.0, knots=2, cathedral=1.0, ray=False,
                     fibre=0.15):
    """Grain for one board of size (width_px rows x length_px cols), grain along x.
    Returns (ring value 0..1 [latewood=1], knot mask, pore/fibre noise)."""
    h, w = int(width_px), int(length_px)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # distance from the pith in the board's cross-section; flat-sawn => z0 large, varies along length
    z0 = rng.uniform(1.5, 6.0) * h
    yc = rng.uniform(-0.5, 1.5) * h
    zz = z0 + cathedral * (h * 1.5) * np.sin(TAU * (xx / w) * rng.integers(1, 3) + rng.uniform(0, TAU)) * \
        rng.uniform(0.2, 1.0)
    # slow wander of the grain
    wander = np.cumsum(rng.standard_normal(w)) * 0.4
    wander = cv2.GaussianBlur(wander.reshape(1, -1).astype(np.float32), (0, 0), 25).ravel()
    dy = yy - yc + wander[None, :] * 3
    knot_mask = np.zeros((h, w), np.float32)
    for _ in range(knots):
        kx, ky = rng.uniform(0.05, 0.95) * w, rng.uniform(0.1, 0.9) * h
        kr = rng.uniform(0.04, 0.12) * h + 3
        dx_ = (xx - kx)
        dy_ = (yy - ky)
        d = np.sqrt((dx_ / 1.6) ** 2 + dy_ ** 2)
        # grain flows around knots: displace dy
        infl = np.exp(-(d / (kr * 3.5)) ** 2)
        dy += np.sign(dy_ + 1e-3) * infl * kr * 1.8 * np.exp(-(np.abs(dy_) / (kr * 4)))
        zz = zz - infl * h * 0.5
        knot_mask = np.maximum(knot_mask, smoothstep(kr, kr * 0.6, d))
        # rings inside knot
    r = np.sqrt(dy ** 2 + zz ** 2)
    noise = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), sigmaX=12, sigmaY=1.2)
    noise /= noise.std() + 1e-6
    ring = (r / ring_px + noise * 0.25)
    frac = ring - np.floor(ring)
    late = smoothstep(0.55, 0.9, frac) * (1 - smoothstep(0.92, 1.0, frac))
    fib = cv2.GaussianBlur(rng.standard_normal((h, w)).astype(np.float32), (0, 0), sigmaX=6, sigmaY=0.5)
    fib /= fib.std() + 1e-6
    return late.astype(np.float32), knot_mask, (fib * fibre).astype(np.float32)


# --------------------------------------------------------------------------- water
def puddles(height, level_pct, soft_m=0.003):
    """Water where height below the given percentile. Returns (water mask 0..1, water level)."""
    lvl = np.percentile(height, level_pct)
    wmask = smoothstep(lvl + soft_m * 0.2, lvl - soft_m, height)
    return wmask.astype(np.float32), lvl


# --------------------------------------------------------------------------- voronoi chunks
def voronoi_chunks(rng, npts, n=N, gap=(0.05, 0.35), bevel=0.35, tilt=0.6, keep=1.0, pts=None,
                   crease=0.5, aspect=(1.0, 1.0), jitter=None, keep_field=None, warp_px=0.0):
    """Packed angular chunks (stones, chalk lumps, rubble, cobbles) from a periodic Voronoi.
    Returns dict: h (0..~1.4, unit = cell radius), mask (0..1), cid (cell id), ins (UV inside
    distance), r (typical cell radius in UV units), pts."""
    from .core import uv, voronoi_edge_dist, _wrapvec
    if pts is None:
        pts = jittered_pts(rng, npts, jitter) if jitter is not None else rng.random((npts, 2))
    npts = len(pts)
    e, cid, pts = voronoi_edge_dist(rng, pts, n=n, aspect=aspect, k=4)
    r = 0.5 * np.sqrt(aspect[0] * aspect[1] / npts)
    gaps = rng.uniform(*gap, npts) * r
    if keep_field is not None:  # spatially varying keep probability, sampled at cell sites
        ix = (np.mod(pts[:, 0], 1.0) * n).astype(int) % n
        iy = (np.mod(pts[:, 1], 1.0) * n).astype(int) % n
        present = rng.random(npts) < keep * keep_field[iy, ix]
    else:
        present = rng.random(npts) < keep
    ins = e - gaps[cid]
    px = 1.0 / n
    mask = np.clip(ins / (1.2 * px) + 0.5, 0, 1) * present[cid]
    prof = np.sqrt(np.clip(ins / (bevel * r), 0, 1))
    u, v = uv(n)
    P = np.stack([u * aspect[0], v * aspect[1]], -1)
    C = np.mod(pts, 1.0) * np.array(aspect)
    d = _wrapvec(P - C[cid], aspect[0], aspect[1]) / r
    ang = rng.uniform(0, TAU, npts)
    mag = rng.uniform(0.2, 1.0, npts) * tilt
    plane = (np.cos(ang)[cid] * d[..., 0] + np.sin(ang)[cid] * d[..., 1]) * mag[cid]
    ang2 = rng.uniform(0, TAU, npts)
    off2 = rng.uniform(-0.5, 0.5, npts)
    cr = np.abs(np.cos(ang2)[cid] * d[..., 0] + np.sin(ang2)[cid] * d[..., 1] - off2[cid]) * \
        crease * (rng.random(npts) < 0.6)[cid]
    base = rng.uniform(0.6, 1.0, npts)[cid]
    h = prof * np.clip(base + 0.35 * plane - 0.35 * cr, 0.1, None)
    out = dict(h=h.astype(np.float32), mask=mask.astype(np.float32), cid=cid, ins=ins.astype(np.float32),
               r=r, pts=pts, present=present)
    if warp_px > 0:  # irregular, non-straight cell borders
        import cv2
        from .core import warp, spectral
        wx = spectral(rng, beta=2.6, fmin=4, n=n) * warp_px
        wy = spectral(rng, beta=2.6, fmin=4, n=n) * warp_px
        for k in ("h", "mask", "ins"):
            out[k] = warp(out[k], wx, wy)
        out["cid"] = warp(out["cid"].astype(np.float32), wx, wy, interp=cv2.INTER_NEAREST).astype(int)
    return out


def cell_values(rng, cid, npts, lo=0.0, hi=1.0):
    return rng.uniform(lo, hi, npts)[cid].astype(np.float32)


def jittered_pts(rng, npts, jitter=0.8):
    """~npts points on a jittered grid in [0,1)^2 (fewer slivers than uniform random)."""
    g = max(1, int(round(np.sqrt(npts))))
    yy, xx = np.mgrid[0:g, 0:g].astype(np.float64)
    off = (yy % 2) * 0.5  # hex-ish rows
    p = np.stack([(xx + 0.5 + off + rng.uniform(-0.5, 0.5, xx.shape) * jitter) / g,
                  (yy + 0.5 + rng.uniform(-0.5, 0.5, yy.shape) * jitter) / g], -1).reshape(-1, 2)
    return np.mod(p, 1.0)
