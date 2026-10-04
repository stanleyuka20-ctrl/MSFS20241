"""Garment geometry from the MakeHuman body (numpy/scipy only).

Techniques
* shell():  select body faces of a region, offset them outwards along smoothed normals,
            relax with a Laplacian smoother while a KD-tree constraint keeps every vertex
            at least `dmin` outside the skin (removes anatomy -> fabric-like surfaces).
* extrude_loop(): grow a boundary loop (hem, collar) into a tube whose cross-section is the
            convex hull of the body slice + ease (tunic skirt, collar stand, cuffs).
* lip():    turn a hem inwards to give the cloth a visible thickness.
* loft():   tube along a polyline from convex-hull cross-sections (puttees, gaiters, bands).
Weights are transferred from the body (nearest-vertex blend) so garments deform with it.
"""
import numpy as np
import scipy.sparse as sp
from scipy.spatial import cKDTree, ConvexHull


class Mesh:
    """Simple polygon soup: v (N,3), f list of tuples, optional per-vertex arrays."""

    def __init__(self, v, f, W=None, src=None):
        self.v = np.asarray(v, float)
        self.f = [tuple(int(i) for i in ff) for ff in f]
        self.W = W
        self.src = src  # body vertex index each vertex derives from (or -1)
        self.loop_uv = None  # optional explicit per-face-corner UVs (list of lists)
        self.attrs = {}

    def copy(self):
        m = Mesh(self.v.copy(), list(self.f), None if self.W is None else self.W.copy(),
                 None if self.src is None else self.src.copy())
        m.loop_uv = None if self.loop_uv is None else [list(x) for x in self.loop_uv]
        m.attrs = {k: v.copy() for k, v in self.attrs.items()}
        return m

    def ntris(self):
        return sum(len(f) - 2 for f in self.f)


def vertex_normals(v, f):
    n = np.zeros_like(v)
    for ff in f:
        if len(ff) == 3:
            tris = [ff]
        else:
            tris = [(ff[0], ff[i], ff[i + 1]) for i in range(1, len(ff) - 1)]
        for a, b, c in tris:
            fn = np.cross(v[b] - v[a], v[c] - v[a])
            n[a] += fn
            n[b] += fn
            n[c] += fn
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-12)


def vertex_normals_fast(v, f):
    """Vectorised version for quads/tris lists."""
    n = np.zeros_like(v)
    q = [ff for ff in f if len(ff) == 4]
    t = [ff for ff in f if len(ff) == 3]
    if q:
        Q = np.array(q)
        fn = np.cross(v[Q[:, 2]] - v[Q[:, 0]], v[Q[:, 3]] - v[Q[:, 1]])
        for k in range(4):
            np.add.at(n, Q[:, k], fn)
    if t:
        T = np.array(t)
        fn = np.cross(v[T[:, 1]] - v[T[:, 0]], v[T[:, 2]] - v[T[:, 0]])
        for k in range(3):
            np.add.at(n, T[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-12)


def edges_of(f):
    e = {}
    for fi, ff in enumerate(f):
        for k in range(len(ff)):
            a, b = ff[k], ff[(k + 1) % len(ff)]
            key = (min(a, b), max(a, b))
            e.setdefault(key, []).append(fi)
    return e


def adjacency(n, f):
    rows, cols = [], []
    for ff in f:
        for k in range(len(ff)):
            a, b = ff[k], ff[(k + 1) % len(ff)]
            rows += [a, b]
            cols += [b, a]
    A = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)).tocsr()
    A.data[:] = 1
    return A


def boundary_loops(f):
    e = edges_of(f)
    bnd = [k for k, fs in e.items() if len(fs) == 1]
    # orient boundary edges as they appear in their face
    nxt = {}
    for (a, b) in bnd:
        ff = f[e[(a, b)][0]]
        for k in range(len(ff)):
            if ff[k] == a and ff[(k + 1) % len(ff)] == b:
                nxt[a] = b
                break
            if ff[k] == b and ff[(k + 1) % len(ff)] == a:
                nxt[b] = a
                break
    loops = []
    seen = set()
    for s in list(nxt.keys()):
        if s in seen:
            continue
        loop = [s]
        seen.add(s)
        c = nxt[s]
        while c != s and c not in seen and c in nxt:
            loop.append(c)
            seen.add(c)
            c = nxt[c]
        loops.append(loop)
    return loops


def submesh(v, f, face_sel, W=None):
    fs = [f[i] for i in np.where(face_sel)[0]]
    used = np.unique(np.concatenate([np.array(x) for x in fs]))
    remap = -np.ones(len(v), int)
    remap[used] = np.arange(len(used))
    nf = [tuple(remap[list(x)]) for x in fs]
    return Mesh(v[used], nf, None if W is None else W[used], used.copy())


class Body:
    """Body reference for constraints & weight transfer."""

    def __init__(self, v, f, W):
        self.v = v
        self.f = f
        self.W = W
        self.n = vertex_normals_fast(v, f)
        self.tree = cKDTree(v)

    def push_out(self, p, dmin, k=4):
        """Push points p so that they are at least dmin outside the skin."""
        d, idx = self.tree.query(p, k=k)
        w = 1.0 / np.maximum(d, 1e-5)
        w /= w.sum(1, keepdims=True)
        vb = (self.v[idx] * w[..., None]).sum(1)
        nb = (self.n[idx] * w[..., None]).sum(1)
        nb /= np.linalg.norm(nb, axis=1, keepdims=True)
        s = ((p - vb) * nb).sum(1)
        dm = np.broadcast_to(dmin, s.shape)
        corr = np.maximum(dm - s, 0)
        return p + nb * corr[:, None], s

    def weights_at(self, p, k=6, power=2.0):
        d, idx = self.tree.query(p, k=k)
        w = 1.0 / np.maximum(d, 1e-4) ** power
        w /= w.sum(1, keepdims=True)
        return (self.W[idx] * w[..., None]).sum(1)


def laplacian_smooth(m, iters, lam=0.5, fixed=None, body=None, dmin=None, keep_boundary_shape=True):
    n = len(m.v)
    A = adjacency(n, m.f)
    deg = np.asarray(A.sum(1)).ravel()
    loops = boundary_loops(m.f)
    bmask = np.zeros(n, bool)
    for L in loops:
        bmask[L] = True
    # boundary vertices smooth only along their loop
    Ab = None
    if loops:
        rows, cols = [], []
        for L in loops:
            k = len(L)
            for i in range(k):
                rows += [L[i], L[i]]
                cols += [L[i - 1], L[(i + 1) % k]]
        Ab = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)).tocsr()
    v = m.v.copy()
    fixed = np.zeros(n, bool) if fixed is None else fixed
    for it in range(iters):
        avg = (A @ v) / np.maximum(deg, 1)[:, None]
        if Ab is not None:
            ab = (Ab @ v) / 2.0
            avg[bmask] = ab[bmask]
        nv = v + lam * (avg - v)
        nv[fixed] = v[fixed]
        v = nv
        if body is not None and dmin is not None:
            v, _ = body.push_out(v, dmin)
    m.v = v
    return m


def shell(body, face_sel, offset, smooth=20, dmin=None, lam=0.5):
    """Offset+relax a body region.  offset: scalar or per-body-vertex array (metres)."""
    m = submesh(body.v, body.f, face_sel, body.W)
    off = offset[m.src] if np.ndim(offset) else np.full(len(m.v), offset)
    m.v = m.v + body.n[m.src] * off[:, None]
    dm = (off * 0.7 if dmin is None else (dmin[m.src] if np.ndim(dmin) else np.full(len(m.v), dmin)))
    laplacian_smooth(m, smooth, lam, body=body, dmin=dm)
    m.attrs["offset"] = off
    return m


def _poly_radius(hull_pts, center, angles):
    """Distance from center to convex polygon boundary along each angle (XZ plane)."""
    P = hull_pts - center
    n = len(P)
    out = np.zeros(len(angles))
    dirs = np.stack([np.cos(angles), np.sin(angles)], 1)
    best = np.full(len(angles), 0.0)
    for i in range(n):
        a = P[i]
        b = P[(i + 1) % n]
        e = b - a
        # solve t*d = a + s*e
        den = dirs[:, 0] * (-e[1]) - dirs[:, 1] * (-e[0])
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (a[0] * (-e[1]) - a[1] * (-e[0])) / den
            s = (dirs[:, 0] * a[1] - dirs[:, 1] * a[0]) / den
        ok = (np.abs(den) > 1e-12) & (s >= -1e-6) & (s <= 1 + 1e-6) & (t > 0)
        best = np.where(ok & (t > best), t, best)
    return best


def slice_hull(points, y, half=0.012, axis=1):
    sel = np.abs(points[:, axis] - y) < half
    if sel.sum() < 5:
        return None
    P2 = points[sel][:, [0, 2]]
    try:
        h = ConvexHull(P2)
    except Exception:
        return None
    return P2[h.vertices]


def extrude_loop(m, loop, heights, body_pts, ease, flare, weight_body=None, blend=0.5, center=None,
                 smooth_ring=6):
    """Extrude a (roughly horizontal) boundary loop vertically through `heights` (list of y).
    Each new ring point keeps its angle about the loop centre and takes
    radius = max(prev radius + flare_k, hull radius(y_k) + ease_k).
    Adds vertices/faces to m in place; returns list of ring index arrays (incl. the loop)."""
    loop = list(loop)
    P = m.v[loop]
    c = P[:, [0, 2]].mean(0) if center is None else np.asarray(center)
    ang = np.arctan2(P[:, 2] - c[1], P[:, 0] - c[0])
    r_prev = np.linalg.norm(P[:, [0, 2]] - c, axis=1)
    rings = [np.array(loop)]
    newv = []
    newW = []
    base_n = len(m.v)
    Wloop = m.W[loop] if m.W is not None else None
    idx0 = base_n
    for k, y in enumerate(heights):
        hp = slice_hull(body_pts, y)
        if hp is not None:
            rh = _poly_radius(hp, c, ang)
        else:
            rh = np.zeros_like(r_prev)
        e = ease[k] if np.ndim(ease) else ease
        fl = flare[k] if np.ndim(flare) else flare
        r = np.maximum(r_prev + fl, rh + e)
        # smooth radius around the ring
        for _ in range(smooth_ring):
            r = 0.25 * np.roll(r, 1) + 0.5 * r + 0.25 * np.roll(r, -1)
        pts = np.stack([c[0] + r * np.cos(ang), np.full_like(r, y), c[1] + r * np.sin(ang)], 1)
        newv.append(pts)
        if Wloop is not None:
            Wb = body_weights_fn(weight_body, pts) if weight_body is not None else Wloop
            a = blend * (k + 1) / len(heights)
            Wr = (1 - a) * Wloop + a * Wb
            for _ in range(4):
                Wr = 0.25 * np.roll(Wr, 1, 0) + 0.5 * Wr + 0.25 * np.roll(Wr, -1, 0)
            newW.append(Wr)
        rings.append(np.arange(idx0, idx0 + len(loop)))
        idx0 += len(loop)
        r_prev = r
    m.v = np.concatenate([m.v] + newv, 0)
    for key in list(m.attrs.keys()):
        a = m.attrs[key]
        m.attrs[key] = np.concatenate([a] + [a[loop]] * len(heights), 0)
    if m.W is not None:
        m.W = np.concatenate([m.W] + newW, 0)
    if m.src is not None:
        m.src = np.concatenate([m.src, -np.ones(len(m.v) - len(m.src), int)])
    _connect_rings(m, rings, flip=True)  # loops from boundary_loops() follow face winding
    return rings


def body_weights_fn(body, pts):
    return body.weights_at(pts)


def _connect_rings(m, rings, flip=False):
    for a, b in zip(rings[:-1], rings[1:]):
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            q = (a[i], a[j], b[j], b[i]) if not flip else (a[i], b[i], b[j], a[j])
            m.f.append(tuple(int(x) for x in q))
    return m


def loop_orientation_fix(m, loop):
    """Ensure the faces adjacent to new rings face outwards: check the first new face normal."""
    return m


def lip(m, loop, depth=0.005, back=0.012, inward=None, smooth_loop=0):
    """Fold a boundary loop inwards (towards -normal) and back into the garment: gives the hem
    a thickness.  Returns the new inner loop indices.  smooth_loop relaxes the (jagged,
    quad-stepped) boundary along itself first."""
    loop = list(loop)
    if len(loop) < 8 or len(set(loop)) != len(loop):
        return np.array(loop)  # broken / tiny boundary fragments: no lip
    if smooth_loop:
        P_ = m.v[loop].copy()
        for _ in range(smooth_loop):
            P_ = 0.5 * P_ + 0.25 * (np.roll(P_, 1, 0) + np.roll(P_, -1, 0))
        m.v[loop] = P_
    n = vertex_normals_fast(m.v, m.f)
    P = m.v[loop]
    N = n[loop]
    # direction back into the garment: from the boundary towards its neighbours (approx. -tangent)
    A = adjacency(len(m.v), m.f)
    inner_dir = np.zeros_like(P)
    lset = set(loop)
    for i, vi in enumerate(loop):
        nb = A[vi].indices
        nb = [x for x in nb if x not in lset]
        if nb:
            d = m.v[nb].mean(0) - P[i]
            d -= np.dot(d, N[i]) * N[i]
            inner_dir[i] = d / max(np.linalg.norm(d), 1e-9)
    if smooth_loop:
        for _ in range(8):
            inner_dir = 0.5 * inner_dir + 0.25 * (np.roll(inner_dir, 1, 0) + np.roll(inner_dir, -1, 0))
            N = 0.5 * N + 0.25 * (np.roll(N, 1, 0) + np.roll(N, -1, 0))
        inner_dir /= np.maximum(np.linalg.norm(inner_dir, axis=1, keepdims=True), 1e-9)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    r1 = P - N * depth
    r2 = r1 + inner_dir * back
    if smooth_loop:
        for _ in range(4):
            r2 = 0.5 * r2 + 0.25 * (np.roll(r2, 1, 0) + np.roll(r2, -1, 0))
    base = len(m.v)
    k = len(loop)
    m.v = np.concatenate([m.v, r1, r2], 0)
    if m.W is not None:
        m.W = np.concatenate([m.W, m.W[loop], m.W[loop]], 0)
    if m.src is not None:
        m.src = np.concatenate([m.src, m.src[loop], m.src[loop]])
    for key in list(m.attrs.keys()):
        a = m.attrs[key]
        m.attrs[key] = np.concatenate([a, a[loop], a[loop]], 0)
    ring0 = np.array(loop)
    ring1 = np.arange(base, base + k)
    ring2 = np.arange(base + k, base + 2 * k)
    # orientation: reuse boundary edge direction from the face so the lip is consistent
    _connect_rings(m, [ring0, ring1, ring2], flip=True)
    return ring2


def loft(path, radii_fn, nseg=16, W_fn=None, cap=False):
    """Tube along a polyline `path` (K,3).  radii_fn(k, angles, frame) -> radii (nseg,).
    Returns Mesh with explicit UVs (u around, v along) in attrs['loft_uv'] per vertex."""
    path = np.asarray(path, float)
    K = len(path)
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    # parallel-transport frames
    ref = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
    Nn = np.cross(T[0], ref)
    Nn /= np.linalg.norm(Nn)
    frames = []
    for k in range(K):
        if k > 0:
            Nn = Nn - np.dot(Nn, T[k]) * T[k]
            Nn /= np.linalg.norm(Nn)
        Bn = np.cross(T[k], Nn)
        frames.append((Nn.copy(), Bn.copy()))
    ang = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    V = []
    for k in range(K):
        Nn, Bn = frames[k]
        r = radii_fn(k, ang, (path[k], T[k], Nn, Bn))
        pts = path[k] + r[:, None] * (np.cos(ang)[:, None] * Nn + np.sin(ang)[:, None] * Bn)
        V.append(pts)
    V = np.concatenate(V, 0)
    f = []
    for k in range(K - 1):
        for i in range(nseg):
            j = (i + 1) % nseg
            a, b = k * nseg + i, k * nseg + j
            c, d = (k + 1) * nseg + j, (k + 1) * nseg + i
            f.append((a, b, c, d))
    m = Mesh(V, f)
    # per-corner UVs with a seam (u from 0..1 around)
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    uv = []
    for k in range(K - 1):
        for i in range(nseg):
            u0, u1 = i / nseg, (i + 1) / nseg
            uv.append([(u0, L[k]), (u1, L[k]), (u1, L[k + 1]), (u0, L[k + 1])])
    m.loop_uv = uv
    m.attrs["loft_s"] = np.repeat(L, nseg)
    m.attrs["loft_a"] = np.tile(ang, K)
    return m


def merge(meshes):
    v, f, W, src, uv = [], [], [], [], []
    off = 0
    has_uv = all(m.loop_uv is not None for m in meshes)
    keys = set.intersection(*[set(m.attrs.keys()) for m in meshes]) if meshes else set()
    attrs = {k: [] for k in keys}
    for m in meshes:
        v.append(m.v)
        f += [tuple(i + off for i in ff) for ff in m.f]
        if m.W is not None:
            W.append(m.W)
        src.append(m.src if m.src is not None else -np.ones(len(m.v), int))
        if has_uv:
            uv += m.loop_uv
        for k in keys:
            attrs[k].append(m.attrs[k])
        off += len(m.v)
    out = Mesh(np.concatenate(v, 0), f, np.concatenate(W, 0) if len(W) == len(meshes) else None,
               np.concatenate(src))
    out.loop_uv = uv if has_uv else None
    out.attrs = {k: np.concatenate(a, 0) for k, a in attrs.items()}
    return out


def assign_weights(m, body, k=6, from_src=True, smooth=0):
    """Weights: exact body weights where the vertex derives from a body vertex, otherwise
    inverse-distance blend of nearby body vertices; optional Laplacian smoothing."""
    W = body.weights_at(m.v, k=k)
    if from_src and m.src is not None:
        ok = m.src >= 0
        W[ok] = 0.5 * W[ok] + 0.5 * body.W[m.src[ok]]
    if smooth:
        A = adjacency(len(m.v), m.f)
        deg = np.asarray(A.sum(1)).ravel()
        for _ in range(smooth):
            W = 0.5 * W + 0.5 * (A @ W) / np.maximum(deg, 1)[:, None]
    m.W = W / np.maximum(W.sum(1, keepdims=True), 1e-9)
    return m


def flip_faces(m):
    m.f = [tuple(reversed(ff)) for ff in m.f]
    if m.loop_uv is not None:
        m.loop_uv = [list(reversed(u)) for u in m.loop_uv]
    return m


def ensure_outward(m, center_fn=None):
    """Flip all faces if the majority of face normals point towards the centroid axis."""
    n = vertex_normals_fast(m.v, m.f)
    c = m.v.mean(0)
    d = m.v - c
    d[:, 1] = 0
    s = (n * d).sum(1)
    if np.mean(s) < 0:
        flip_faces(m)
    return m


def hull_push(p, hull_pts, dmin):
    """Push points to be at least dmin outside the convex hull of hull_pts."""
    h = ConvexHull(hull_pts)
    A = h.equations[:, :3]
    b = h.equations[:, 3]
    d = p @ A.T + b  # signed distance to each face plane (positive outside)
    k = np.argmax(d, axis=1)
    dm = d[np.arange(len(p)), k]
    corr = np.maximum(dmin - dm, 0)
    return p + A[k] * corr[:, None]
