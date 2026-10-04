"""Animation core (numpy/scipy only): BVH loading, retargeting CMU mocap onto the reduced
MakeHuman skeleton, loop extraction, in-place conversion, ground-speed measurement,
2-bone IK and procedural layers (breathing, finger poses, overrides).

Conventions: all world-space maths is done in glTF space (metres, +Y up, character faces +Z,
character's left = +X).  A bone frame B is a 3x3 matrix whose columns are the bone's local
X, Y (along the bone, head->tail) and Z axes in world space (Blender's bone convention).
Posed frames are W.  The Blender pose-bone rotation of bone b is
    Q_b = B_b^T B_p W_p^T W_b
which is independent of the world basis, so it can be fed straight into Blender.
"""
import os
import re

import numpy as np
from scipy.spatial.transform import Rotation as R

import cw_paths as P
import mhcore as mh

CMU_SCALE = 0.056444  # cgspeed BVH units -> metres  ((1/0.45) * 2.54 / 100)

# ----------------------------------------------------------------------------------
# small rotation helpers
# ----------------------------------------------------------------------------------


def nrm(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def frame(primary, secondary):
    """Orthonormal frame, columns = [p, s', p x s']."""
    p = nrm(primary)
    s = np.asarray(secondary, float)
    s = nrm(s - (s * p).sum(-1, keepdims=True) * p)
    return np.stack([p, s, np.cross(p, s)], axis=-1)


def rot_between(a, b):
    """Minimal rotation matrix taking direction a to direction b (batched)."""
    a = nrm(a)
    b = nrm(b)
    v = np.cross(a, b)
    c = (a * b).sum(-1)
    s = np.linalg.norm(v, axis=-1)
    ang = np.arctan2(s, c)
    axis = np.where(s[..., None] > 1e-9, v / np.maximum(s[..., None], 1e-12), np.array([1.0, 0, 0]))
    return R.from_rotvec(axis * ang[..., None]).as_matrix()


def slerp_mat(Ma, Mb, t):
    """Batched slerp between rotation matrices (t scalar or array)."""
    ra = R.from_matrix(Ma)
    rd = ra.inv() * R.from_matrix(Mb)
    rv = rd.as_rotvec() * np.asarray(t)[..., None] if np.ndim(t) else rd.as_rotvec() * t
    return (ra * R.from_rotvec(rv)).as_matrix()


def axis_angle(axis, deg):
    return R.from_rotvec(nrm(axis) * np.radians(deg)).as_matrix()


# ----------------------------------------------------------------------------------
# BVH
# ----------------------------------------------------------------------------------


class BVH:
    def __init__(self, path):
        self.path = path
        self.names, self.parent, self.offset, self.channels, self.endoff = [], [], [], [], {}
        with open(path) as f:
            txt = f.read()
        head, motion = txt.split("MOTION")
        stack = []
        cur = None
        tokens = head.split("\n")
        pending_end = False
        for line in tokens:
            a = line.split()
            if not a:
                continue
            if a[0] in ("ROOT", "JOINT"):
                self.names.append(a[1])
                self.parent.append(stack[-1] if stack else -1)
                self.offset.append(np.zeros(3))
                self.channels.append([])
                cur = len(self.names) - 1
            elif a[0] == "End":
                pending_end = True
            elif a[0] == "{":
                if pending_end:
                    stack.append(("end", cur))
                else:
                    stack.append(cur)
            elif a[0] == "}":
                top = stack.pop()
                if isinstance(top, tuple):
                    pending_end = False
            elif a[0] == "OFFSET":
                o = np.array([float(x) for x in a[1:4]])
                if pending_end:
                    self.endoff[cur] = o
                else:
                    self.offset[cur] = o
            elif a[0] == "CHANNELS":
                self.channels[cur] = a[2:2 + int(a[1])]
            # fix stack holding tuples for parent lookup
            stack = [s for s in stack]
        # parent indices: stack held ints (or tuples for end sites)
        self.parent = [p if not isinstance(p, tuple) else p[1] for p in self.parent]
        lines = motion.strip().split("\n")
        self.nframes = int(lines[0].split()[1])
        self.dt = float(lines[1].split()[2])
        self.data = np.array([[float(x) for x in l.split()] for l in lines[2:2 + self.nframes]])
        self.offset = np.array(self.offset) * CMU_SCALE
        self.endoff = {k: v * CMU_SCALE for k, v in self.endoff.items()}
        self.idx = {n: i for i, n in enumerate(self.names)}

    def fk(self, frames=None):
        """Returns world rotations (F,J,3,3) and positions (F,J,3) in metres (Y-up)."""
        d = self.data if frames is None else self.data[frames]
        F = len(d)
        J = len(self.names)
        Wr = np.zeros((F, J, 3, 3))
        Wp = np.zeros((F, J, 3))
        col = 0
        for j in range(J):
            ch = self.channels[j]
            rot_axes = "".join(c[0] for c in ch if c.endswith("rotation"))
            rot_cols = [col + i for i, c in enumerate(ch) if c.endswith("rotation")]
            pos_cols = {c[0]: col + i for i, c in enumerate(ch) if c.endswith("position")}
            col += len(ch)
            if rot_axes:
                L = R.from_euler(rot_axes.upper(), d[:, rot_cols], degrees=True).as_matrix()
            else:
                L = np.broadcast_to(np.eye(3), (F, 3, 3))
            p = self.parent[j]
            if p < 0:
                t = np.zeros((F, 3))
                for k, ax in enumerate("XYZ"):
                    if ax in pos_cols:
                        t[:, k] = d[:, pos_cols[ax]] * CMU_SCALE
                Wr[:, j] = L
                Wp[:, j] = t + self.offset[j]
            else:
                Wr[:, j] = Wr[:, p] @ L
                Wp[:, j] = Wp[:, p] + np.einsum("fij,j->fi", Wr[:, p], self.offset[j])
        return Wr, Wp

    def local_rot(self, frames=None):
        Wr, _ = self.fk(frames)
        Lr = Wr.copy()
        for j, p in enumerate(self.parent):
            if p >= 0:
                Lr[:, j] = np.transpose(Wr[:, p], (0, 2, 1)) @ Wr[:, j]
        return Lr

    def rest_positions(self):
        J = len(self.names)
        pos = np.zeros((J, 3))
        for j in range(J):
            p = self.parent[j]
            pos[j] = self.offset[j] + (pos[p] if p >= 0 else 0)
        return pos


# ----------------------------------------------------------------------------------
# Target skeleton
# ----------------------------------------------------------------------------------


class Skeleton:
    def __init__(self, sk):
        self.names = [b["name"] for b in sk]
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.parent = [self.idx[b["parent"]] if b["parent"] else -1 for b in sk]
        self.head = np.array([b["head"] for b in sk])
        self.tail = np.array([b["tail"] for b in sk])
        B = []
        for b in sk:
            y = nrm(b["tail"] - b["head"])
            x = b["normal"] - np.dot(b["normal"], y) * y
            if np.linalg.norm(x) < 1e-6:
                x = np.cross(y, [0, 0, 1.0])
            x = nrm(x)
            z = np.cross(x, y)
            B.append(np.stack([x, y, z], axis=1))
        self.B = np.array(B)
        self.n = len(self.names)
        self.children = [[c for c in range(self.n) if self.parent[c] == i] for i in range(self.n)]

    def i(self, n):
        return self.idx[n]

    def fk_positions(self, W, hips_pos):
        """W: (F,n,3,3) world frames; hips_pos (F,3) world head of 'hips'.
        Returns heads (F,n,3) and tails."""
        F = W.shape[0]
        H = np.zeros((F, self.n, 3))
        for b in range(self.n):
            p = self.parent[b]
            if p < 0:
                H[:, b] = self.head[b]
            elif self.names[b] == "hips":
                H[:, b] = hips_pos
            else:
                rel = self.B[p].T @ (self.head[b] - self.head[p])
                H[:, b] = H[:, p] + np.einsum("fij,j->fi", W[:, p], rel)
        T = H + np.einsum("fnij,nj->fni", W, np.einsum("nji,nj->ni", self.B, self.tail - self.head))
        return H, T

    def local_from_world(self, W):
        Q = np.zeros_like(W)
        for b in range(self.n):
            p = self.parent[b]
            if p < 0:
                Q[:, b] = np.einsum("ij,fjk->fik", self.B[b].T, W[:, b])
            else:
                M = np.einsum("ij,jk->ik", self.B[b].T, self.B[p])
                Q[:, b] = np.einsum("ij,fkj,fkl->fil", M, W[:, p], W[:, b])
        return Q

    def world_from_local(self, Q):
        F = Q.shape[0]
        W = np.zeros_like(Q)
        for b in range(self.n):
            p = self.parent[b]
            if p < 0:
                W[:, b] = np.einsum("ij,fjk->fik", self.B[b], Q[:, b])
            else:
                M = self.B[p].T @ self.B[b]
                W[:, b] = np.einsum("fij,jk,fkl->fil", W[:, p], M, Q[:, b])
        return W

    def rest_world(self, F=1):
        return np.broadcast_to(self.B, (F, self.n, 3, 3)).copy()


_sk = {}


def skeleton():
    if "s" not in _sk:
        _, sk = mh.canonical()
        _sk["s"] = Skeleton(sk)
    return _sk["s"]


# ----------------------------------------------------------------------------------
# Retarget
# ----------------------------------------------------------------------------------

X = np.array([1.0, 0, 0])
Y = np.array([0, 1.0, 0])
Z = np.array([0, 0, 1.0])


def flexion_axis(bvh, Lr, joint, fallback, Wrest=None):
    """Dominant rotation axis of a joint's local rotation over the clip, expressed in world
    space at the source rest (T-pose) frame."""
    rv = R.from_matrix(Lr[:, bvh.idx[joint]]).as_rotvec()
    ang = np.linalg.norm(rv, axis=1)
    sel = ang > np.radians(15)
    if sel.sum() < 10:
        return nrm(fallback)
    ax = (rv[sel] / ang[sel, None]).mean(axis=0)
    if np.linalg.norm(ax) < 0.3:
        return nrm(fallback)
    ax = nrm(ax)
    if Wrest is not None:
        ax = Wrest[bvh.parent[bvh.idx[joint]]] @ ax
    return nrm(ax)


def _src_pos(bvh, rest, name, Wrest=None):
    if name.startswith("END:"):
        j = bvh.idx[name[4:]]
        return rest[j] + (Wrest[j] @ bvh.endoff[j] if Wrest is not None else bvh.endoff[j])
    return rest[bvh.idx[name]]


_restcache = {}


def source_rest(bvh):
    """World rotations/positions of the source's T-pose (cgspeed frame 0)."""
    if bvh.path not in _restcache:
        Wr, Wp = bvh.fk(np.array([0]))
        _restcache[bvh.path] = (Wr[0], Wp[0] - Wp[0, 0])
    return _restcache[bvh.path]


def build_mapping(bvh, Lr, sk):
    """Returns list of (target bone, source spec, C matrix)."""
    Wrest, rest = source_rest(bvh)
    th = lambda n: sk.head[sk.i(n)]
    tt = lambda n: sk.tail[sk.i(n)]
    sp = lambda n: _src_pos(bvh, rest, n, Wrest)
    maps = []

    def add(tb, src, tdir, sdir, tsec, ssec):
        Ft = frame(tdir, tsec)
        Fs = frame(sdir, ssec)
        maps.append((tb, src, Fs @ Ft.T))

    maps.append(("hips", "Hips", np.eye(3)))
    # spine: target bone dir vs source segment dir, lateral secondary
    lb = sp("Spine") - sp("LowerBack")
    up = sp("Spine1") - sp("Spine")
    nk = sp("Neck1") - sp("Neck")
    nk2 = sp("Head") - sp("Neck1")
    hd = sp("END:Head") - sp("Head")
    for tb, src, sdir in [("spine05", "LowerBack", lb), ("spine04", "LowerBack", lb),
                          ("spine03", ("slerp", "LowerBack", "Spine", 0.5), (lb + up) / 2),
                          ("spine02", "Spine", up), ("spine01", "Spine1", up),
                          ("neck01", "Neck", nk), ("neck02", "Neck1", nk2), ("head", "Head", hd)]:
        add(tb, src, tt(tb) - th(tb), sdir, X, X)
    for s, S, sgn in (("L", "Left", 1), ("R", "Right", -1)):
        knee_ax_s = flexion_axis(bvh, Lr, S + "Leg", X, Wrest)
        elbow_ax_s = flexion_axis(bvh, Lr, S + "ForeArm", -Y * sgn, Wrest)
        # pelvis follows hip joint
        maps.append(("pelvis." + s, ("L" if s == "L" else "R") + "HipJoint", np.eye(3)))
        thigh_t = th("lowerleg01." + s) - th("upperleg02." + s)
        thigh_s = sp(S + "Leg") - sp(S + "UpLeg")
        for tb in ("upperleg01.", "upperleg02."):
            add(tb + s, S + "UpLeg", thigh_t, thigh_s, X, knee_ax_s)
        shin_t = th("foot." + s) - th("lowerleg01." + s)
        shin_s = sp(S + "Foot") - sp(S + "Leg")
        for tb in ("lowerleg01.", "lowerleg02."):
            add(tb + s, S + "Leg", shin_t, shin_s, X, knee_ax_s)
        add("foot." + s, S + "Foot", th("toes." + s) - th("foot." + s), sp(S + "ToeBase") - sp(S + "Foot"), X, knee_ax_s)
        add("toes." + s, S + "ToeBase", tt("toes." + s) - th("toes." + s), sp("END:" + S + "ToeBase") - sp(S + "ToeBase"), X, knee_ax_s)
        # arms
        # clavicles: keep the MakeHuman rest relation to the chest; only the source's
        # shoulder rotation relative to Spine1 is transferred (CMU rest clavicles point up)
        Csp = [m for m in maps if m[0] == "spine01"][0][2]
        for tb in ("clavicle.", "shoulder01."):
            maps.append((tb + s, S + "Shoulder", Csp))
        ua_t = th("lowerarm01." + s) - th("upperarm02." + s)
        fa_t = th("wrist." + s) - th("lowerarm01." + s)
        elbow_ax_t = nrm(np.cross(ua_t, fa_t))
        ua_s = sp(S + "ForeArm") - sp(S + "Arm")
        fa_s = sp(S + "Hand") - sp(S + "ForeArm")
        for tb in ("upperarm01.", "upperarm02."):
            add(tb + s, S + "Arm", ua_t, ua_s, elbow_ax_t, elbow_ax_s)
        for tb in ("lowerarm01.", "lowerarm02."):
            add(tb + s, S + "ForeArm", fa_t, fa_s, elbow_ax_t, elbow_ax_s)
        # hand: same alignment as the forearm (keeps the rest wrist relation)
        Cf = [m for m in maps if m[0] == "lowerarm01." + s][0][2]
        maps.append(("wrist." + s, S + "Hand", Cf))
    return maps


def retarget(bvh, frames, sk=None, leg_scale=None):
    """Retarget BVH frames. Returns dict(W (F,n,3,3) world frames, hips (F,3), fps)."""
    sk = sk or skeleton()
    Wr, Wp = bvh.fk(frames)
    Lr_all = bvh.local_rot()
    maps = build_mapping(bvh, Lr_all, sk)
    F = Wr.shape[0]
    W = sk.rest_world(F)
    Wrest, _ = source_rest(bvh)
    D = np.einsum("fjik,jlk->fjil", Wr, Wrest)  # world delta from the T-pose: Wr Wrest^T
    for tb, src, C in maps:
        if isinstance(src, tuple):
            Rs = slerp_mat(D[:, bvh.idx[src[1]]], D[:, bvh.idx[src[2]]], src[3])
        else:
            Rs = D[:, bvh.idx[src]]
        b = sk.i(tb)
        W[:, b] = Rs @ (C @ sk.B[b])
    # children without mapping (fingers, jaw) follow parents rigidly
    W = propagate_unmapped(sk, W, {m[0] for m in maps})
    # hips translation scaled by leg length ratio
    rest = bvh.rest_positions()
    sleg = (np.linalg.norm(bvh.offset[bvh.idx["LeftLeg"]]) + np.linalg.norm(bvh.offset[bvh.idx["LeftFoot"]]))
    tleg = (np.linalg.norm(sk.head[sk.i("lowerleg01.L")] - sk.head[sk.i("upperleg02.L")]) +
            np.linalg.norm(sk.head[sk.i("foot.L")] - sk.head[sk.i("lowerleg01.L")]))
    scale = leg_scale or tleg / sleg
    hips_src = Wp[:, bvh.idx["Hips"]]
    hips = hips_src * scale
    # vertical: keep the ratio relative to the source standing height
    return dict(W=W, hips=hips, scale=scale, dt=bvh.dt)


def propagate_unmapped(sk, W, mapped):
    """Bones not in `mapped` keep their rest local rotation relative to their parent."""
    for b in range(sk.n):
        if sk.names[b] in mapped or sk.parent[b] < 0:
            continue
        p = sk.parent[b]
        W[:, b] = W[:, p] @ (sk.B[p].T @ sk.B[b])
    return W


def recompute_children(sk, Wold, Wnew, changed):
    """After changing world frames of bones in `changed`, keep the LOCAL rotations of all
    descendants (so children follow)."""
    Q = sk.local_from_world(Wold)
    Wn = Wnew.copy()
    ch = set(changed)
    for b in range(sk.n):
        p = sk.parent[b]
        if b in ch or p < 0:
            continue
        M = sk.B[p].T @ sk.B[b]
        Wn[:, b] = np.einsum("fij,jk,fkl->fil", Wn[:, p], M, Q[:, b])
    return Wn


# ----------------------------------------------------------------------------------
# clip utilities
# ----------------------------------------------------------------------------------


def resample(clip, step):
    """Take every `step`-th frame (with a light 3-tap smoothing of hips)."""
    W = clip["W"][::step]
    h = clip["hips"]
    if step > 1:
        k = np.ones(step) / step
        hs = np.stack([np.convolve(h[:, i], k, mode="same") for i in range(3)], 1)
        hs[: step] = h[: step]
        hs[-step:] = h[-step:]
        h = hs
    return dict(clip, W=W, hips=h[::step], dt=clip["dt"] * step)


def pose_features(sk, W, hips):
    Q = sk.local_from_world(W)
    sel = [sk.i(n) for n in ["upperleg02.L", "upperleg02.R", "lowerleg01.L", "lowerleg01.R", "foot.L", "foot.R",
                             "upperarm02.L", "upperarm02.R", "lowerarm01.L", "lowerarm01.R", "spine03", "spine01",
                             "head"]]
    f = Q[:, sel].reshape(len(W), -1)
    return f


def heading_yaw(sk, W):
    """Yaw angle (radians) of the hips forward axis per frame."""
    hb = sk.i("hips")
    fwd = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Z)
    return np.arctan2(fwd[:, 0], fwd[:, 2])


def apply_yaw(sk, clip, yaw, about=None):
    Ry = axis_angle(Y, np.degrees(yaw))
    W = np.einsum("ij,fnjk->fnik", Ry, clip["W"])
    W[:, 0] = clip["W"][:, 0]  # the root bone is never animated
    h = clip["hips"] @ Ry.T
    return dict(clip, W=W, hips=h)


def find_loop(sk, clip, min_len, max_len, search=None, w_vel=0.0):
    """Find (a, b) frame pair minimising pose distance with min_len <= b-a <= max_len."""
    W, h = clip["W"], clip["hips"]
    f = pose_features(sk, W, h)
    F = len(W)
    lo, hi = search or (0, F)
    best = (1e9, 0, 0)
    vel = np.gradient(h, axis=0)
    for a in range(lo, hi):
        for b in range(a + min_len, min(a + max_len, hi) + 1):
            if b >= F:
                break
            d = np.sum((f[a] - f[b]) ** 2) + w_vel * np.sum((vel[a] - vel[b]) ** 2) * 1e4
            d += 0.5 * (h[a, 1] - h[b, 1]) ** 2 * 100
            if d < best[0]:
                best = (d, a, b)
    return best


def make_loop(sk, clip, a, b, inplace="trend"):
    """Cut [a, b] (b == duplicate of a after correction) and distribute closure error."""
    W = clip["W"][a:b + 1].copy()
    h = clip["hips"][a:b + 1].copy()
    F = len(W)
    s = np.linspace(0, 1, F)
    # in place: remove linear horizontal trend
    v = (h[-1] - h[0])
    speed_vec = np.array([v[0], 0, v[2]]) / ((F - 1) * clip["dt"])
    if inplace == "trend":
        h[:, 0] -= h[0, 0] + s * v[0]
        h[:, 2] -= h[0, 2] + s * v[2]
    elif inplace == "mean":
        lin = h[0] + s[:, None] * v
        h[:, 0] -= lin[:, 0]
        h[:, 2] -= lin[:, 2]
        h[:, 0] -= h[:, 0].mean()
        h[:, 2] -= h[:, 2].mean()
    h[:, 1] -= s * (h[-1, 1] - h[0, 1])
    # local rotation closure
    Q = sk.local_from_world(W)
    for bi in range(sk.n):
        ra = R.from_matrix(Q[0, bi])
        rb = R.from_matrix(Q[-1, bi])
        d = (rb.inv() * ra).as_rotvec()
        corr = R.from_rotvec(s[:, None] * d[None, :])
        Q[:, bi] = (R.from_matrix(Q[:, bi]) * corr).as_matrix()
    W = sk.world_from_local(Q)
    return dict(clip, W=W[:-1], hips=h[:-1], ground_vel=speed_vec)


def loop_blend(sk, clip, nblend):
    """Cross-fade the last nblend frames into the frames before the first one (for clips
    whose end and start do not match well). Expects clip with extra frames at the end."""
    return clip


def foot_contacts(sk, clip, speed):
    """Compute ankle/toe positions in a world that moves at +Z `speed`."""
    H, T = sk.fk_positions(clip["W"], clip["hips"])
    t = np.arange(len(H)) * clip["dt"]
    out = {}
    for s in "LR":
        ank = H[:, sk.i("foot." + s)].copy()
        toe = H[:, sk.i("toes." + s)].copy()
        ank[:, 2] += speed * t
        toe[:, 2] += speed * t
        out[s] = (ank, toe)
    return out, H, T


def measure_speed(sk, clip):
    """Measure the ground speed that makes stance feet stationary: median of -dz/dt of the
    in-place lowest point of each foot while it is in contact."""
    H, T = sk.fk_positions(clip["W"], clip["hips"])
    dt = clip["dt"]
    vals = []
    for s in "LR":
        ank = H[:, sk.i("foot." + s)]
        toe = H[:, sk.i("toes." + s)]
        y = np.minimum(ank[:, 1] - 0.07, toe[:, 1] - 0.02)
        ymin = np.percentile(y, 5)
        contact = y < ymin + 0.025
        p = np.where((ank[:, 1] - 0.07 < toe[:, 1] - 0.02)[:, None], ank, toe)
        vz = np.gradient(np.concatenate([p[-1:], p, p[:1]])[:, 2], dt)[1:-1]
        vals.append(-vz[contact])
    v = np.concatenate(vals)
    return float(np.median(v)) if len(v) else 0.0


# ----------------------------------------------------------------------------------
# IK & procedural layers
# ----------------------------------------------------------------------------------


def two_bone_ik(sk, W, hips, upper, lower, end, targets, pole=None, weight=None, chain_upper=(), chain_lower=()):
    """Solve 2-bone IK so the head of `end` reaches targets (F,3). Upper/lower are bone
    names whose world frames are rotated; `chain_upper`/`chain_lower` are additional bones
    rigidly rotated with them (twist bones). The end bone keeps its world orientation.
    pole: (F,3) or (3,) desired direction of the knee/elbow from the chain (optional)."""
    F = len(W)
    H, _ = sk.fk_positions(W, hips)
    iu, il, ie = sk.i(upper), sk.i(lower), sk.i(end)
    a = H[:, iu]
    b = H[:, il]
    c = H[:, ie]
    l1 = np.linalg.norm(b - a, axis=1)
    l2 = np.linalg.norm(c - b, axis=1)
    t = np.asarray(targets, float)
    if weight is not None:
        w = np.asarray(weight, float)[:, None]
        t = c * (1 - w) + t * w
    d = t - a
    dist = np.linalg.norm(d, axis=1)
    dist_c = np.clip(dist, np.abs(l1 - l2) + 1e-4, (l1 + l2) * 0.9995)
    dn = d / dist[:, None]
    if pole is None:
        pv = b - a - ((b - a) * dn).sum(1, keepdims=True) * dn
    else:
        pv = np.broadcast_to(pole, (F, 3)) - (np.broadcast_to(pole, (F, 3)) * dn).sum(1, keepdims=True) * dn
    pv = nrm(pv)
    cosA = (l1 ** 2 + dist_c ** 2 - l2 ** 2) / (2 * l1 * dist_c)
    A = np.arccos(np.clip(cosA, -1, 1))
    b_new = a + l1[:, None] * (np.cos(A)[:, None] * dn + np.sin(A)[:, None] * pv)
    t_eff = a + dn * dist_c[:, None]
    R1 = rot_between(b - a, b_new - a)
    Wn = W.copy()
    for n in (upper,) + tuple(chain_upper):
        Wn[:, sk.i(n)] = R1 @ W[:, sk.i(n)]
    c_after = b_new + np.einsum("fij,fj->fi", R1, c - b)
    R2 = rot_between(c_after - b_new, t_eff - b_new)
    for n in (lower,) + tuple(chain_lower):
        Wn[:, sk.i(n)] = R2 @ R1 @ W[:, sk.i(n)]
    changed = {sk.i(n) for n in (upper, lower) + tuple(chain_upper) + tuple(chain_lower)}
    changed.add(ie)  # keep end world orientation
    Wn[:, ie] = W[:, ie]
    Wn = recompute_children(sk, W, Wn, changed)
    return Wn


def set_local(sk, W, bone, Rloc_delta, weight=1.0):
    """Post-multiply a bone's local rotation by a delta (in bone local axes), children follow."""
    Q = sk.local_from_world(W)
    b = sk.i(bone)
    F = len(W)
    if np.ndim(weight) == 0:
        weight = np.full(F, weight)
    rv = R.from_matrix(np.broadcast_to(Rloc_delta, (F, 3, 3))).as_rotvec() * np.asarray(weight)[:, None]
    Q[:, b] = Q[:, b] @ R.from_rotvec(rv).as_matrix()
    return sk.world_from_local(Q)


def rotate_world(sk, W, bone, Rw, weight=1.0):
    """Pre-multiply a bone's world frame by a world rotation (children follow)."""
    F = len(W)
    if np.ndim(weight) == 0:
        weight = np.full(F, weight)
    rv = R.from_matrix(np.broadcast_to(Rw, (F, 3, 3))).as_rotvec() * np.asarray(weight)[:, None]
    Rm = R.from_rotvec(rv).as_matrix()
    b = sk.i(bone)
    Wn = W.copy()
    Wn[:, b] = Rm @ W[:, b]
    return recompute_children(sk, W, Wn, {b})


def local_euler(deg_xyz):
    """Local rotation from XYZ euler degrees in the bone's own axes (X = flex axis)."""
    return R.from_euler("XYZ", deg_xyz, degrees=True).as_matrix()


FINGER_POSES = {
    # (metacarpophalangeal, middle, distal) curl degrees for [thumb, index, middle, ring]
    "relaxed": [(8, 10, 8), (18, 22, 12), (24, 28, 14), (30, 32, 16)],
    "loose": [(5, 8, 5), (10, 14, 8), (14, 18, 10), (18, 22, 12)],
    "grip": [(25, 30, 25), (65, 80, 45), (70, 85, 45), (72, 85, 45)],
    "point": [(30, 35, 25), (0, 2, 2), (75, 90, 45), (78, 90, 45)],
    "fist": [(30, 40, 30), (80, 95, 60), (85, 95, 60), (85, 95, 60)],
    "spread": [(0, 5, 5), (4, 6, 4), (6, 8, 4), (8, 10, 6)],
    "cup": [(15, 20, 15), (30, 35, 20), (32, 38, 22), (35, 40, 22)],
}


def finger_pose(sk, W, side, pose, weight=1.0, sign=None):
    """Set finger curls (local X rotation). The sign of the flex axis is determined from the
    rest geometry (curl must move the fingertip towards the palm)."""
    F = len(W)
    Q = sk.local_from_world(W)
    pz = FINGER_POSES[pose] if isinstance(pose, str) else pose
    for fi, f in enumerate((1, 2, 3, 4)):
        for k in (1, 2, 3):
            n = "finger%d-%d.%s" % (f, k, side)
            b = sk.i(n)
            sg = curl_sign(sk, n)
            ang = pz[fi][k - 1] * sg
            if np.ndim(weight):
                rv = np.zeros((F, 3))
                rv[:, 0] = np.radians(ang) * np.asarray(weight)
                Qd = R.from_rotvec(rv).as_matrix()
            else:
                Qd = np.broadcast_to(R.from_euler("X", ang * weight, degrees=True).as_matrix(), (F, 3, 3))
            # replace (not accumulate) the curl
            Q[:, b] = Qd
    return sk.world_from_local(Q)


_curl = {}


def curl_sign(sk, n):
    """+1 if a positive local-X rotation moves the bone tip towards the palm."""
    if n in _curl:
        return _curl[n]
    side = n[-1]
    b = sk.i(n)
    wr = sk.i("wrist." + side)
    # palm normal: cross of (index base - ring base) and hand direction, pointing palmar
    ib = sk.head[sk.i("finger2-1." + side)]
    rb = sk.head[sk.i("finger4-1." + side)]
    hdir = nrm((ib + rb) / 2 - sk.head[wr])
    across = nrm(ib - rb)
    palm = nrm(np.cross(hdir, across))
    # make palm point roughly to the body side the fingers naturally curl to: test with mesh
    # (MakeHuman rest: palms face backwards/inwards). Fingers curl towards -palm if wrong.
    if n.startswith("finger1"):
        # thumb curls across the palm towards the little finger
        target = nrm(rb - sk.head[b])
    else:
        target = palm * (1 if side == "L" else -1) * _palm_sign(sk, side)
    yb = sk.B[b][:, 1]
    xb = sk.B[b][:, 0]
    tip_move = np.cross(xb, yb)  # direction the tip moves for +X rotation
    _curl[n] = 1 if np.dot(tip_move, target) > 0 else -1
    return _curl[n]


_palm = {}


def _palm_sign(sk, side):
    """Determine palmar direction from the mesh: the side of the hand plane where the
    finger chain bends (rest pose fingers are slightly curled)."""
    if side in _palm:
        return _palm[side]
    ib = sk.head[sk.i("finger3-1." + side)]
    tip = sk.tail[sk.i("finger3-3." + side)]
    mid = sk.head[sk.i("finger3-2." + side)]
    wr = sk.head[sk.i("wrist." + side)]
    ib2 = sk.head[sk.i("finger2-1." + side)]
    rb = sk.head[sk.i("finger4-1." + side)]
    hdir = nrm((ib2 + rb) / 2 - wr)
    across = nrm(ib2 - rb)
    palm = nrm(np.cross(hdir, across)) * (1 if side == "L" else -1)
    # the fingertip deviates from the straight line towards the palm
    bend = (tip - ib) - np.dot(tip - ib, nrm(mid - ib)) * nrm(mid - ib)
    _palm[side] = 1 if np.dot(bend, palm) > 0 else -1
    return _palm[side]


def palm_normal(sk, side):
    ib2 = sk.head[sk.i("finger2-1." + side)]
    rb = sk.head[sk.i("finger4-1." + side)]
    wr = sk.head[sk.i("wrist." + side)]
    hdir = nrm((ib2 + rb) / 2 - wr)
    across = nrm(ib2 - rb)
    return nrm(np.cross(hdir, across)) * (1 if side == "L" else -1) * _palm_sign(sk, side)


def smooth_noise(F, dt, period, seed, octaves=3):
    """Band-limited smooth noise in [-1,1] that loops over F frames."""
    rng = np.random.default_rng(seed)
    t = np.arange(F) / F
    out = np.zeros(F)
    dur = F * dt
    base = max(1, int(round(dur / period)))
    amp = 1.0
    for o in range(octaves):
        k = base * (2 ** o)
        ph = rng.uniform(0, 2 * np.pi, 2)
        out += amp * (np.sin(2 * np.pi * k * t + ph[0]) * 0.7 + np.sin(2 * np.pi * (k + 1) * t + ph[1]) * 0.3)
        amp *= 0.45
    return out / 1.6


def breathing(sk, W, dt, rate_hz=0.25, amp=1.0, seed=0):
    """Chest rise/fall + clavicle/shoulder lift + slight head counter motion.
    rate rounded so the loop closes."""
    F = len(W)
    dur = F * dt
    n = max(1, round(dur * rate_hz))
    t = np.arange(F) * dt
    ph = 2 * np.pi * n * t / dur
    # asymmetric breath: quicker inhale, slower exhale
    b = 0.5 - 0.5 * np.cos(ph + 0.35 * np.sin(ph))
    W = set_local(sk, W, "spine02", local_euler([-1.6 * amp, 0, 0]), b)
    W = set_local(sk, W, "spine01", local_euler([-1.2 * amp, 0, 0]), b)
    for s in "LR":
        W = set_local(sk, W, "clavicle." + s, local_euler([0, 0, (1.2 if s == "L" else -1.2) * amp]), b)
    W = set_local(sk, W, "neck01", local_euler([1.4 * amp, 0, 0]), b)
    return W
