"""Build every humanoid clip (retargeted CMU mocap + procedural/hand-keyed layers) and cache
them as .npz in CACHE/clips.  Pure numpy - run with any python that has numpy+scipy.

    python anim_clips.py            # all clips
    python anim_clips.py walk run   # selected clips
"""
import json
import os
import sys

import numpy as np
from scipy.spatial.transform import Rotation as R

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cw_anim as ca
import cw_paths as P

from cw_anim import X, Y, Z, local_euler, axis_angle

CLIPDIR = os.path.join(P.CACHE, "clips")
os.makedirs(CLIPDIR, exist_ok=True)
FPS = 30
STEP = 4  # 120 Hz mocap -> 30 Hz

sk = ca.skeleton()
_bvh = {}


def bvh(name):
    if name not in _bvh:
        _bvh[name] = ca.BVH(os.path.join(P.CMU_BVH, name + ".bvh"))
    return _bvh[name]


def src(name, start_s=None, end_s=None):
    b = bvh(name)
    fr = None
    if start_s is not None:
        a = int(start_s / b.dt)
        e = int(end_s / b.dt) if end_s else b.nframes
        fr = np.arange(a, min(e, b.nframes))
    c = ca.retarget(b, fr, sk)
    return ca.resample(c, STEP)


def rest_y(bone):
    return sk.head[sk.i(bone)][1]


def ground_fix(c, mode="feet", target=0.0):
    """Shift hips vertically so the lowest foot point touches the ground (per-clip constant)."""
    H, T = sk.fk_positions(c["W"], c["hips"])
    if mode == "stance":
        d = np.concatenate([H[:, sk.i("foot." + s), 1] - rest_y("foot." + s) for s in "LR"])
        off = np.mean(np.sort(d)[: max(3, int(len(d) * 0.15))])
    elif mode == "feet":
        d = []
        for s in "LR":
            d.append(H[:, sk.i("foot." + s), 1] - rest_y("foot." + s))
            d.append(H[:, sk.i("toes." + s), 1] - rest_y("toes." + s))
            d.append(T[:, sk.i("toes." + s), 1] - sk.tail[sk.i("toes." + s)][1])
        d = np.min(np.stack(d, 1), axis=1)
        off = np.percentile(d, 3)
    else:
        off = mode(H, T) - target
    c = dict(c)
    c["hips"] = c["hips"].copy()
    c["hips"][:, 1] -= off
    return c


def face_forward(c, yaw=None):
    if yaw is None:
        v = c.get("ground_vel")
        if v is not None and np.linalg.norm(v) > 0.2:
            yaw = np.arctan2(v[0], v[2])
        else:
            yaws = ca.heading_yaw(sk, c["W"])
            yaw = np.arctan2(np.sin(yaws).mean(), np.cos(yaws).mean())
    c = ca.apply_yaw(sk, c, -yaw)
    if "ground_vel" in c:
        c["ground_vel"] = axis_angle(Y, np.degrees(-yaw)) @ c["ground_vel"]
    return c


def center_xz(c):
    c = dict(c)
    h = c["hips"].copy()
    h[:, 0] -= h[:, 0].mean()
    h[:, 2] -= h[:, 2].mean()
    c["hips"] = h
    return c


def clearance(c, deg=4.0, w=1.0):
    """Abduct upper arms slightly so sleeves/webbing pouches do not intersect the torso."""
    W = c["W"]
    for s, sg in (("L", 1), ("R", -1)):
        # rotate about the world forward axis expressed per frame through the spine01 frame
        fwd = np.einsum("fij,j->fi", W[:, sk.i("spine01")], sk.B[sk.i("spine01")].T @ Z)
        rv = ca.nrm(fwd) * np.radians(deg * sg) * w
        Rm = R.from_rotvec(rv).as_matrix()
        Wn = W.copy()
        b = sk.i("upperarm01." + s)
        for n in ("upperarm01.", "upperarm02."):
            Wn[:, sk.i(n + s)] = Rm @ W[:, sk.i(n + s)]
        W = ca.recompute_children(sk, W, Wn, {sk.i("upperarm01." + s), sk.i("upperarm02." + s)})
    return dict(c, W=W)


def twist_split(c):
    """Distribute forearm/upper-arm twist over the twist bones (avoids candy-wrapping)."""
    Q = sk.local_from_world(c["W"])
    for s in "LR":
        for a, b, frac in (("upperarm01.", "upperarm02.", 0.5), ("lowerarm02.", "wrist.", 0.5),
                           ("upperleg01.", "upperleg02.", 0.5)):
            ia, ib = sk.i(a + s), sk.i(b + s)
            if b == "wrist.":
                # take twist from the wrist (about Y) and move half to lowerarm02, 1/4 to lowerarm01
                rv = R.from_matrix(Q[:, ib])
                sw, tw = swing_twist(rv, Y)
                ang = tw
                Q[:, ib] = (sw * R.from_rotvec(np.outer(ang * 0.35, Y))).as_matrix()
                Q[:, ia] = (R.from_matrix(Q[:, ia]) * R.from_rotvec(np.outer(ang * 0.4, Y))).as_matrix()
                il = sk.i("lowerarm01." + s)
                Q[:, il] = (R.from_matrix(Q[:, il]) * R.from_rotvec(np.outer(ang * 0.25, Y))).as_matrix()
            else:
                ra = R.from_matrix(Q[:, ia])
                sw, tw = swing_twist(ra, Y)
                Q[:, ia] = (sw * R.from_rotvec(np.outer(tw * (1 - frac), Y))).as_matrix()
                Q[:, ib] = (R.from_rotvec(np.outer(tw * frac, Y)) * R.from_matrix(Q[:, ib])).as_matrix()
    return dict(c, W=sk.world_from_local(Q))


def swing_twist(r, axis):
    q = r.as_quat()  # x y z w
    p = (q[:, :3] @ axis)[:, None] * axis[None, :]
    tw = np.concatenate([p, q[:, 3:4]], 1)
    n = np.linalg.norm(tw, axis=1, keepdims=True)
    tw = np.where(n > 1e-9, tw / np.maximum(n, 1e-12), np.array([0, 0, 0, 1.0]))
    rt = R.from_quat(tw)
    ang = rt.as_rotvec() @ axis
    sw = r * rt.inv()
    return sw, ang


def fingers(c, pose_l="relaxed", pose_r="relaxed", wl=1.0, wr=1.0):
    W = ca.finger_pose(sk, c["W"], "L", pose_l, wl)
    W = ca.finger_pose(sk, W, "R", pose_r, wr)
    return dict(c, W=W)


def foot_lock(c, speed, thr=0.022):
    """Pin stance feet so they do not slide when the character moves at `speed` (+Z).
    Heel/flat phase pins the ankle, toe-roll phase pins the toe joint (ball of the foot)."""
    W, h = c["W"], c["hips"]
    F = len(W)
    dt = c["dt"]
    H, T = sk.fk_positions(W, h)
    for s in "LR":
        ia, it = sk.i("foot." + s), sk.i("toes." + s)
        ah = H[:, ia, 1] - rest_y("foot." + s)
        th = H[:, it, 1] - rest_y("toes." + s)
        low_a = ah < thr
        low_t = th < thr
        anyc = low_a | low_t
        if anyc.all() or not anyc.any():
            continue
        r0 = int(np.argmin(anyc))  # start in swing
        idx = np.roll(np.arange(F), -r0)
        t = np.arange(F) * dt
        wa = H[idx, ia].copy()
        wt = H[idx, it].copy()
        wa[:, 2] += speed * t
        wt[:, 2] += speed * t
        la, lt = low_a[idx], low_t[idx]
        tgt_a = wa.copy()
        wgt = np.zeros(F)
        f = 0
        while f < F:
            if not (la[f] or lt[f]):
                f += 1
                continue
            g = f
            while g < F and (la[g] or lt[g]):
                g += 1
            run = np.arange(f, g)
            ra = run[la[run]]
            if len(ra):
                pa = np.median(wa[ra][:, [0, 2]], axis=0)
                last_a = ra[-1]
            else:
                pa = None
            # toe pin position: continuation from the pinned ankle at the end of the flat phase
            if pa is not None:
                off = np.array([pa[0] - wa[last_a, 0], 0, pa[1] - wa[last_a, 2]])
                ptoe = wt[last_a] + off
            else:
                ptoe = np.median(wt[run], axis=0)
            for k in run:
                if la[k] and (pa is not None) and k <= last_a:
                    tgt_a[k, 0], tgt_a[k, 2] = pa
                else:
                    d = ptoe - wt[k]
                    tgt_a[k, 0] += d[0]
                    tgt_a[k, 2] += d[2]
                wgt[k] = 1
            f = g
        # soften the weights at the run boundaries
        k3 = np.array([0.25, 0.5, 0.25])
        for _ in range(2):
            wgt = np.convolve(np.concatenate([wgt[-1:], wgt, wgt[:1]]), k3, "same")[1:-1]
        tgt = tgt_a.copy()
        tgt[:, 2] -= speed * t
        ank = H[idx, ia]
        tgt = ank * (1 - wgt[:, None]) + tgt * wgt[:, None]
        tgt_full = np.zeros_like(tgt)
        tgt_full[idx] = tgt
        W = ca.two_bone_ik(sk, W, h, "upperleg01." + s, "lowerleg01." + s, "foot." + s, tgt_full,
                           chain_upper=("upperleg02." + s,), chain_lower=("lowerleg02." + s,))
    return dict(c, W=W)


def slide_report(c, speed):
    H, T = sk.fk_positions(c["W"], c["hips"])
    t = np.arange(len(H)) * c["dt"]
    out = []
    for s in "LR":
        for b in ("foot.", "toes."):
            p = H[:, sk.i(b + s)].copy()
            p[:, 2] += speed * t
            low = p[:, 1] - rest_y(b + s) < 0.015
            v = np.linalg.norm(np.gradient(p[:, [0, 2]], c["dt"], axis=0), axis=1)
            out.append(float(np.median(v[low])) if low.any() else 0)
    return np.round(out, 3)


def foot_pitch_fix(c, max_deg=20.0):
    """CMU T-pose foot calibration varies per subject: rotate each foot by a constant so that
    it is flat (rest pitch) at mid-stance (the frames where the ankle is lowest)."""
    W = c["W"]
    for s in "LR":
        b = sk.i("foot." + s)
        H, _ = sk.fk_positions(W, c["hips"])
        ay = H[:, b, 1]
        st = ay <= np.percentile(ay, 25)
        d = W[:, b][:, :, 1]
        pitch = np.degrees(np.arctan2(d[:, 1], np.linalg.norm(d[:, [0, 2]], axis=1)))
        dr = sk.B[b][:, 1]
        rp = np.degrees(np.arctan2(dr[1], np.linalg.norm(dr[[0, 2]])))
        delta = np.clip(rp - np.median(pitch[st]), -max_deg, max_deg)
        best = None
        for sg in (1, -1):
            Wt = ca.set_local(sk, W, "foot." + s, local_euler([sg * delta, 0, 0]))
            d2 = Wt[:, b][:, :, 1]
            p2 = np.degrees(np.arctan2(d2[:, 1], np.linalg.norm(d2[:, [0, 2]], axis=1)))
            err = abs(np.median(p2[st]) - rp)
            if best is None or err < best[0]:
                best = (err, Wt)
        W = best[1]
    return dict(c, W=W)


def toe_clamp(c):
    """Rotate feet (about their local X) where the toe tip would dip below the ground."""
    W = c["W"]
    for s in "LR":
        b = sk.i("foot." + s)
        tb = sk.i("toes." + s)
        for it in range(3):
            H, T = sk.fk_positions(W, c["hips"])
            depth = (sk.tail[tb][1] - 0.004) - T[:, tb, 1]
            if depth.max() <= 0.001:
                break
            L = np.linalg.norm(T[:, tb] - H[:, b], axis=1)
            ang = np.degrees(np.arcsin(np.clip(np.maximum(depth, 0) / L, 0, 0.9)))
            k = np.array([0.25, 0.5, 0.25])
            ang = np.convolve(np.concatenate([ang[-1:], ang, ang[:1]]), k, "same")[1:-1] * 1.1
            best = None
            for sg in (1, -1):
                Wt = ca.set_local(sk, W, "foot." + s, local_euler([sg, 0, 0]), ang)
                _, T2 = sk.fk_positions(Wt, c["hips"])
                e = np.maximum((sk.tail[tb][1] - 0.004) - T2[:, tb, 1], 0).sum()
                if best is None or e < best[0]:
                    best = (e, Wt)
            W = best[1]
    return dict(c, W=W)


def save(name, c, loop=True, speed=0.0, notes="", source=""):
    W, h = c["W"], c["hips"]
    for k in ("W", "hips"):
        assert np.all(np.isfinite(c[k])), name
    Q = sk.local_from_world(W)
    hb = sk.i("hips")
    hips_loc = (h - sk.head[hb]) @ sk.B[hb]  # world offset -> bone local (B^T v)
    np.savez_compressed(os.path.join(CLIPDIR, name + ".npz"), Q=Q, hips_loc=hips_loc, hips_world=h,
                        dt=c["dt"], loop=loop, speed=speed, notes=notes, source=source)
    print("%-12s frames=%3d dur=%.2fs loop=%s speed=%.3f  %s" % (name, len(W), len(W) * c["dt"], loop, speed, source))


# ----------------------------------------------------------------------------------
# recipes
# ----------------------------------------------------------------------------------


def locomotion(file, min_s, max_s, search=None, fing="relaxed", clear=4.0, lock=True):
    c = src(file)
    lo, hi = (int(search[0] * FPS), int(search[1] * FPS)) if search else (5, len(c["W"]) - 1)
    d, a, b = ca.find_loop(sk, c, int(min_s * FPS), int(max_s * FPS), search=(lo, min(hi, len(c["W"]) - 1)),
                           w_vel=1.0)
    c = ca.make_loop(sk, c, a, b, inplace="trend")
    c = face_forward(c)
    c = twist_split(c)
    c = clearance(c, clear)
    c = fingers(c, fing, fing)
    c = ground_fix(c, "stance")
    c = foot_pitch_fix(c)
    c = ground_fix(c, "stance")
    c = toe_clamp(c)
    speed0 = float(np.linalg.norm(c["ground_vel"]) * 1.0)
    v = ca.measure_speed(sk, c)
    c0 = c
    if lock:
        c = foot_lock(c, v)
        v2 = ca.measure_speed(sk, c)
    else:
        v2 = v
    c["info"] = dict(loop_frames=(a, b), loop_err=d, hips_speed=speed0, foot_speed=v, foot_speed_locked=v2,
                     slide_before=slide_report(c0, v), slide_after=slide_report(c, v2))
    print(file, c["info"])
    return c, v2


# ---------------------------------------------------------------------------------
# hand-keying helpers
# ---------------------------------------------------------------------------------


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def env(t, t0, t1, t2, t3):
    """0 -> 1 between t0..t1, hold, 1 -> 0 between t2..t3 (eased)."""
    return smoothstep((t - t0) / max(t1 - t0, 1e-6)) * (1 - smoothstep((t - t2) / max(t3 - t2, 1e-6)))


def blend_local(Wa, Wb, w, bones=None, delay=None, dt=1 / 30):
    """Per-bone slerp of local rotations between two clips (same length). w (F,) weights.
    delay: {bone: seconds} lag for overlapping action."""
    Qa = sk.local_from_world(Wa)
    Qb = sk.local_from_world(Wb)
    F = len(Wa)
    t = np.arange(F) * dt
    Q = Qa.copy()
    for b in range(sk.n):
        n = sk.names[b]
        if bones is not None and n not in bones:
            continue
        ww = w
        if delay and n in delay:
            ww = np.interp(t - delay[n], t, w)
        rv = (R.from_matrix(Qa[:, b]).inv() * R.from_matrix(Qb[:, b])).as_rotvec() * np.asarray(ww)[:, None]
        Q[:, b] = (R.from_matrix(Qa[:, b]) * R.from_rotvec(rv)).as_matrix()
    return sk.world_from_local(Q)


def hand_frame(H, side):
    wr = H[:, sk.i("wrist." + side)]
    ib = H[:, sk.i("finger2-1." + side)]
    rb = H[:, sk.i("finger4-1." + side)]
    return wr, ca.nrm((ib + rb) / 2 - wr), ca.nrm(ib - rb)


def arm_ik(W, hips, side, target, pole, hand_dir=None, across=None, weight=None):
    """IK the arm so the wrist reaches target (F,3); optionally orient the hand so that
    wrist->knuckles == hand_dir and index->ring direction == across (both (F,3) or (3,))."""
    W = ca.two_bone_ik(sk, W, hips, "upperarm01." + side, "lowerarm01." + side, "wrist." + side, target,
                       pole=pole, weight=weight, chain_upper=("upperarm02." + side,),
                       chain_lower=("lowerarm02." + side,))
    if hand_dir is not None:
        H, _ = sk.fk_positions(W, hips)
        _, d, a = hand_frame(H, side)
        F = len(W)
        hd = np.broadcast_to(hand_dir, (F, 3))
        ac = np.broadcast_to(across, (F, 3)) if across is not None else a
        Fc = ca.frame(d, a)
        Ft = ca.frame(hd, ac)
        Rm = np.einsum("fij,fkj->fik", Ft, Fc)
        if weight is not None:
            rv = R.from_matrix(Rm).as_rotvec() * np.asarray(weight)[:, None]
            Rm = R.from_rotvec(rv).as_matrix()
        b = sk.i("wrist." + side)
        Wn = W.copy()
        Wn[:, b] = Rm @ W[:, b]
        W = ca.recompute_children(sk, W, Wn, {b})
    return W


def leg_ik(W, hips, side, target, pole, foot_frame=None):
    W = ca.two_bone_ik(sk, W, hips, "upperleg01." + side, "lowerleg01." + side, "foot." + side, target,
                       pole=pole, chain_upper=("upperleg02." + side,), chain_lower=("lowerleg02." + side,))
    if foot_frame is not None:
        b = sk.i("foot." + side)
        Wn = W.copy()
        Wn[:, b] = foot_frame @ sk.B[b] if np.ndim(foot_frame) == 2 else np.einsum("fij,jk->fik", foot_frame, sk.B[b])
        W = ca.recompute_children(sk, W, Wn, {b})
    return W


def yaw_frame(W):
    """(F,3,3) yaw-only frame of the hips (columns: left, up, forward)."""
    hb = sk.i("hips")
    fwd = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Z)
    fwd[:, 1] = 0
    fwd = ca.nrm(fwd)
    up = np.broadcast_to(Y, fwd.shape)
    left = np.cross(up, fwd)
    return np.stack([left, up, fwd], axis=-1)


def static_rest(F, dt=1 / 30.):
    W = sk.rest_world(F)
    h = np.broadcast_to(sk.head[sk.i("hips")], (F, 3)).copy()
    return dict(W=W, hips=h, dt=dt)


def rotw(W, bone, axis, deg, w=1.0):
    return ca.rotate_world(sk, W, bone, axis_angle(axis, 1.0) if False else ca.axis_angle(axis, deg), w)


def mocap_static(file, t0, t1, min_s, max_s, yaw_extra=0.0, ground=True):
    c = src(file, t0, t1)
    F = len(c["W"])
    d, a, b = ca.find_loop(sk, c, int(min_s * FPS), min(int(max_s * FPS), F - 2), search=(0, F - 1))
    c = ca.make_loop(sk, c, a, b, inplace="mean")
    c = face_forward(c)
    if yaw_extra:
        c = ca.apply_yaw(sk, c, np.radians(yaw_extra))
    c = twist_split(c)
    if ground:
        c = ground_fix(c)
    c = center_xz(c)
    print(file, "loop", a, b, "err", round(d, 4), "dur", round((b - a) / FPS, 2))
    return c


RECIPES = {}


def recipe(fn):
    RECIPES[fn.__name__.replace("clip_", "")] = fn
    return fn


@recipe
def clip_walk():
    c, v = locomotion("08_01", 0.9, 1.3)
    save("walk", c, True, v, source="CMU 08_01 (walk)")


@recipe
def clip_run():
    c, v = locomotion("09_11", 0.6, 0.85, fing="loose", clear=6.0)
    save("run", c, True, v, source="CMU 09_11 (run)")


def damp_arms(c, base_W, amount=0.35):
    """Replace the arm pose by a relaxed base pose plus a fraction of the original swing."""
    Q = sk.local_from_world(c["W"])
    Qb = sk.local_from_world(base_W[:1])[0]
    for s in "LR":
        for n in ("clavicle.", "shoulder01.", "upperarm01.", "upperarm02.", "lowerarm01.", "lowerarm02.", "wrist."):
            b = sk.i(n + s)
            r = R.from_matrix(Q[:, b])
            mean = r.mean()
            dev = (mean.inv() * r).as_rotvec() * amount
            Q[:, b] = (R.from_matrix(Qb[b]) * R.from_rotvec(dev)).as_matrix()
    return dict(c, W=sk.world_from_local(Q))


def time_stretch(c, factor):
    """Resample a looping clip to factor x its duration (local-rotation slerp, cyclic)."""
    Q = sk.local_from_world(c["W"])
    h = c["hips"]
    F = len(Q)
    F2 = int(round(F * factor))
    tt = np.arange(F2) * F / F2
    i0 = np.floor(tt).astype(int) % F
    i1 = (i0 + 1) % F
    a = (tt - np.floor(tt))
    Q2 = np.zeros((F2,) + Q.shape[1:])
    for b in range(sk.n):
        r0 = R.from_matrix(Q[i0, b])
        r1 = R.from_matrix(Q[i1, b])
        d = (r0.inv() * r1).as_rotvec() * a[:, None]
        Q2[:, b] = (r0 * R.from_rotvec(d)).as_matrix()
    h2 = h[i0] * (1 - a[:, None]) + h[i1] * a[:, None]
    return dict(c, W=sk.world_from_local(Q2), hips=h2)


@recipe
def clip_limp_walk():
    c, v = locomotion("91_16", 1.0, 1.9, search=(3.0, 7.6), fing="relaxed", lock=False)
    base = mocap_static("77_02", 1.0, 7.8, 4.0, 6.5)
    base = clearance(base, 4.0)
    c = damp_arms(c, base["W"], 0.4)
    c = time_stretch(c, 1.3)  # slower, laboured gait (~0.8 m/s)
    c = fingers(c)
    v = ca.measure_speed(sk, c)
    c = foot_lock(c, v)
    v2 = ca.measure_speed(sk, c)
    save("limp_walk", c, True, v2, source="CMU 91_16 (Limp), arm swing damped towards CMU 77_02 standing pose")


def head_level(c, target_deg=-6.0):
    """Raise/lower the head so its average pitch is target_deg (negative = looking down)."""
    W = c["W"]
    hb = sk.i("head")
    fw = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Z)
    pitch = np.degrees(np.arctan2(fw[:, 1], np.linalg.norm(fw[:, [0, 2]], axis=1))).mean()
    delta = target_deg - pitch  # positive = raise
    for n, f in (("neck01", 0.3), ("neck02", 0.35), ("head", 0.35)):
        W = rotw(W, n, X, -delta * f)
    return dict(c, W=W)


@recipe
def clip_idle():
    c = mocap_static("77_02", 1.0, 7.8, 4.0, 6.5)
    c = head_level(c, -5.0)
    c = clearance(c, 3.0)
    c = fingers(c)
    c["W"] = ca.breathing(sk, c["W"], c["dt"], 0.25, 0.5)
    save("idle", c, True, 0.0, source="CMU 77_02 (standing)")


@recipe
def clip_idle_alt():
    c = mocap_static("111_28", 9.0, 15.5, 4.0, 6.0)
    c = head_level(c, -14.0)
    c = clearance(c, 2.0)
    c = fingers(c, "loose", "loose")
    c["W"] = ca.breathing(sk, c["W"], c["dt"], 0.25, 0.5)
    save("idle_alt", c, True, 0.0, source="CMU 111_28 (standing still, hands clasped)")


@recipe
def clip_talk():
    c = mocap_static("19_08", 10.0, 17.0, 4.5, 6.8)
    c = head_level(c, -4.0)
    base = mocap_static("77_02", 1.0, 7.8, 4.0, 6.5)
    c = damp_arms(c, base["W"], 0.5)  # calmer gestures around a relaxed pose
    c = clearance(c, 3.0)
    c = fingers(c, "loose", "loose")
    F = len(c["W"])
    t = np.arange(F) * c["dt"]
    # jaw: speech-like irregular opening (syllable rate ~4 Hz modulated by phrases)
    phr = np.clip(ca.smooth_noise(F, c["dt"], 1.6, 3) * 1.5 + 0.4, 0, 1)
    syl = 0.5 + 0.5 * np.sin(2 * np.pi * 4.3 * t + 2.0 * np.sin(2 * np.pi * 0.9 * t))
    open_deg = 7.0 * phr * syl
    Q = sk.local_from_world(c["W"])
    jb = sk.i("jaw")
    for f in range(F):
        Q[f, jb] = Q[f, jb] @ local_euler([-open_deg[f] * jaw_sign(), 0, 0])
    c["W"] = sk.world_from_local(Q)
    save("talk", c, True, 0.0, source="CMU 19_08 (conversation, explain with hand gestures), gestures damped 50% towards CMU 77_02 standing pose, procedural jaw")


_js = {}


def jaw_sign():
    """Sign of a local X rotation of the jaw that opens the mouth (chin moves down/back)."""
    if "s" not in _js:
        b = sk.i("jaw")
        x = sk.B[b][:, 0]
        y = sk.B[b][:, 1]
        tip_move = np.cross(x, y)  # tip direction for +X
        _js["s"] = -1 if tip_move[1] < 0 else 1
    return _js["s"]


@recipe
def clip_sit_ground():
    c = mocap_static("82_05", 10.0, 14.2, 2.5, 4.0)
    # lean the trunk back a little more (against a wall)
    F = len(c["W"])
    W = c["W"]
    W = rotw(W, "spine04", X, -4.0)
    c["W"] = W
    c = fingers(c, "relaxed", "relaxed")
    c["W"] = ca.breathing(sk, c["W"], c["dt"], 0.22, 0.8)

    def pelvis_low(H, T):
        return np.percentile(H[:, sk.i("hips"), 1], 50) - 0.13

    c = ground_fix(c, mode=lambda H, T: np.percentile(H[:, sk.i("upperleg02.L"), 1], 50) - 0.105, target=0.0)
    save("sit_ground", c, True, 0.0, source="CMU 82_05 (sitting on ground relaxing)")


@recipe
def clip_crouch_cover():
    dur = 4.0
    F = int(dur * FPS)
    dt = 1 / FPS
    t = np.arange(F) * dt
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"]
    h = h.copy()
    breath = 0.5 - 0.5 * np.cos(2 * np.pi * round(dur * 0.45) * t / dur)
    trem = ca.smooth_noise(F, dt, 0.25, 5, octaves=2)
    h[:, 1] = 0.47 + 0.006 * breath
    h[:, 2] = -0.10
    W = rotw(W, "hips", X, 28)
    for b, a in (("spine05", 10), ("spine04", 11), ("spine03", 12), ("spine02", 12), ("spine01", 9)):
        W = rotw(W, b, X, 1.0, a + 1.2 * breath)
    W = rotw(W, "neck01", X, 18)
    W = rotw(W, "head", X, 16)
    W = rotw(W, "spine03", Z, 1.0, trem * 0.8)
    for s, sg in (("L", 1), ("R", -1)):
        ank = np.broadcast_to(np.array([0.13 * sg, sk.head[sk.i("foot." + s)][1] + 0.025, 0.04]), (F, 3))
        W = leg_ik(W, h, s, ank, pole=np.array([0.35 * sg, 0.1, 1.0]),
                   foot_frame=ca.axis_angle(Y, 8 * sg) @ ca.axis_angle(X, 14))
    H, _ = sk.fk_positions(W, h)
    hb = sk.i("head")
    up = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Y)
    fw = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Z)
    lf = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ X)
    top = H[:, hb] + up * 0.20 + fw * 0.02
    shake = 0.0025 * np.sin(2 * np.pi * 9.0 * t)[:, None] * (0.6 + 0.4 * trem[:, None])
    for s, sg in (("L", 1), ("R", -1)):
        tgt = top + lf * 0.06 * sg - up * 0.025 + shake
        W = arm_ik(W, h, s, tgt, pole=fw * 0.8 + lf * sg * 0.7 - up * 0.5,
                   hand_dir=ca.nrm(-lf * sg * 0.6 + fw * 0.3 - up * 0.5), across=ca.nrm(fw))
    c = dict(c, W=W, hips=h)
    c = twist_split(c)
    c = fingers(c, "cup", "cup")
    save("crouch_cover", c, True, 0.0, source="hand-keyed (IK squat, hands over helmet, breathing/trembling)")


@recipe
def clip_carry_walk():
    c, v = locomotion("35_01", 0.95, 1.3, lock=False)
    c = head_level(c, -8.0)
    W, h = c["W"], c["hips"]
    F = len(W)
    W = rotw(W, "spine03", X, 3)
    W = rotw(W, "spine01", X, 2)
    yf = yaw_frame(W)
    H, _ = sk.fk_positions(W, h)
    hb = H[:, sk.i("hips")]
    bob = (hb[:, 1] - hb[:, 1].mean()) * 0.6
    for s, sg in (("L", 1), ("R", -1)):
        off = np.array([0.245 * sg, 0.04, 0.36])
        tgt = hb + np.einsum("fij,j->fi", yf, off)
        tgt[:, 1] = hb[:, 1].mean() + 0.04 + bob
        pole = np.einsum("fij,j->fi", yf, np.array([0.7 * sg, -0.3, -1.0]))
        hd = np.einsum("fij,j->fi", yf, ca.nrm(np.array([0.0, -0.75, 0.6])))
        ac = np.einsum("fij,j->fi", yf, np.array([0, 0, 1.0]))  # index finger forward
        W = arm_ik(W, h, s, tgt, pole, hand_dir=hd, across=ac)
    c["W"] = W
    c = twist_split(c)
    c = fingers(c, "grip", "grip")
    c = ground_fix(c)
    vv = ca.measure_speed(sk, c)
    c = foot_lock(c, vv)
    v2 = ca.measure_speed(sk, c)
    save("carry_walk", c, True, v2, source="CMU 35_01 (walk) + stretcher-handle arm IK")


@recipe
def clip_point():
    base = mocap_static("77_02", 1.0, 7.8, 2.6, 3.4)
    base = head_level(base, -4.0)
    F = len(base["W"])
    dt = base["dt"]
    t = np.arange(F) * dt
    W0, h = base["W"], base["hips"]
    W0 = ca.finger_pose(sk, W0, "L", "relaxed")
    W0 = ca.finger_pose(sk, W0, "R", "relaxed")
    # pointing pose (whole clip) then blend in/out with overlapping timing
    Wp = rotw(W0, "spine03", Y, -6)
    Wp = rotw(Wp, "spine01", Y, -6)
    Wp = rotw(Wp, "neck02", Y, -10)
    Wp = rotw(Wp, "head", Y, -8)
    Wp = rotw(Wp, "head", X, -3)
    H, _ = sk.fk_positions(Wp, h)
    sh = H[:, sk.i("upperarm01.R")]
    dirp = ca.nrm(np.array([-0.45, 0.22, 1.0]))
    tgt = sh + dirp * 0.56
    Wp = arm_ik(Wp, h, "R", tgt, pole=np.array([-0.3, -1.0, -0.2]), hand_dir=dirp,
                across=ca.nrm(np.array([0.0, 1.0, 0.1])))
    Wp = rotw(Wp, "clavicle.R", Z, 5)
    Wp = ca.finger_pose(sk, Wp, "R", "point")
    w = env(t, 0.25, 0.75, 1.9, 2.55)
    delay = {"clavicle.R": -0.04, "upperarm01.R": 0.0, "upperarm02.R": 0.0, "lowerarm01.R": 0.06,
             "lowerarm02.R": 0.07, "wrist.R": 0.1, "head": -0.12, "neck02": -0.1}
    for f in (1, 2, 3, 4):
        for k in (1, 2, 3):
            delay["finger%d-%d.R" % (f, k)] = 0.12
    W = blend_local(W0, Wp, w, delay=delay, dt=dt)
    c = dict(base, W=W)
    c = twist_split(c)
    c["W"] = ca.breathing(sk, c["W"], dt, 0.25, 0.5)
    save("point", c, False, 0.0, source="CMU 77_02 (standing) base + hand-keyed pointing arm (IK)")


@recipe
def clip_lie_supine():
    dur = 8.0
    F = int(dur * FPS)
    dt = 1 / FPS
    t = np.arange(F) * dt
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"]
    # legs straight, feet rolled out; arms by the sides, right hand resting on the belly
    for s, sg in (("L", 1), ("R", -1)):
        W = rotw(W, "upperleg01." + s, Z, -2 * sg)
        W = rotw(W, "upperleg01." + s, Y, 14 * sg)
        W = rotw(W, "foot." + s, X, 18)
    W = arm_ik(W, h, "L", np.broadcast_to([0.25, 0.87, -0.01], (F, 3)), pole=np.array([0.6, 0, -1.0]),
               hand_dir=np.array([0.05, -1, 0.05]), across=np.array([0, 0, 1.0]))
    W = arm_ik(W, h, "R", np.broadcast_to([-0.04, 1.03, 0.16], (F, 3)), pole=np.array([-1.0, -0.3, -0.4]),
               hand_dir=np.array([0.95, -0.25, 0.1]), across=np.array([0, 1.0, 0]))
    W = rotw(W, "spine01", X, -3)
    W = rotw(W, "head", Y, 12)
    W = rotw(W, "head", X, -6)
    # lay down: rotate the whole body back by 90 deg about the hips
    W = rotw(W, "hips", X, -90)
    h = h.copy()
    h[:, 1] = 0.12
    h[:, 2] = 0.0
    c = dict(c, W=W, hips=h)
    c = fingers(c, "relaxed", "loose")
    # breathing (deeper, slower) + small irregular head/hand motion
    c["W"] = ca.breathing(sk, c["W"], dt, 0.3, 1.5)
    n1 = ca.smooth_noise(F, dt, 4.0, 11)
    n2 = ca.smooth_noise(F, dt, 3.0, 12)
    c["W"] = rotw(c["W"], "head", Z, 1.0, n1 * 2.5)
    c["W"] = rotw(c["W"], "lowerarm01.L", Z, 1.0, n2 * 2.0)
    # belly rise moves the resting hand a little
    save("lie_supine", c, True, 0.0, source="hand-keyed (procedural breathing)")


@recipe
def clip_kneel_work():
    dur = 6.0
    F = int(dur * FPS)
    dt = 1 / FPS
    t = np.arange(F) * dt
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"]
    l1 = np.linalg.norm(sk.head[sk.i("lowerleg01.R")] - sk.head[sk.i("upperleg01.R")])
    # kneel on the right knee, left foot forward
    hip_r = sk.head[sk.i("upperleg01.R")]
    knee_y = 0.065
    hip_drop = 0.0
    hz = 0.0
    hips_y = knee_y + np.sqrt(l1 ** 2 - 0.12 ** 2)
    dh = hips_y - hip_r[1]
    sway = ca.smooth_noise(F, dt, 3.0, 21) * 0.008
    h = h.copy()
    h[:, 1] += dh + sway * 0.5
    h[:, 0] += sway
    W = rotw(W, "hips", X, 12)
    for b, a in (("spine05", 7), ("spine04", 8), ("spine03", 8), ("spine02", 7), ("spine01", 5)):
        W = rotw(W, b, X, a)
    W = rotw(W, "neck01", X, 8)
    W = rotw(W, "head", X, 16)
    W = rotw(W, "spine02", Y, -5)
    H, _ = sk.fk_positions(W, h)
    # right leg: knee on the ground just in front of the hip, shin back along the ground
    hipR = H[:, sk.i("upperleg01.R")]
    knee = hipR + np.array([0.0, 0, 0.12])
    knee[:, 1] = knee_y
    l2 = np.linalg.norm(sk.head[sk.i("foot.R")] - sk.head[sk.i("lowerleg01.R")])
    ank = knee + np.array([0.02, 0.0, -l2 * 0.97])
    ank[:, 1] = 0.105
    W = leg_ik(W, h, "R", ank, pole=np.array([0, -0.3, 1.0]),
               foot_frame=ca.axis_angle(X, 70) @ ca.axis_angle(Y, 0))
    # left leg: foot planted forward
    hipL = H[:, sk.i("upperleg01.L")]
    ankL = hipL + np.array([0.06, 0, 0.42])
    ankL[:, 1] = sk.head[sk.i("foot.L")][1]
    W = leg_ik(W, h, "L", ankL, pole=np.array([0.2, 0.3, 1.0]), foot_frame=np.eye(3))
    # hands working at ground level in front
    H, _ = sk.fk_positions(W, h)
    base = H[:, sk.i("hips")] * np.array([1, 0, 1]) + np.array([0, 0.0, 0.0])
    ph = 2 * np.pi * t / dur
    rh = np.stack([-0.10 + 0.05 * np.cos(3 * ph), 0.13 + 0.035 * np.sin(3 * ph) + 0.02 * np.sin(6 * ph),
                   0.48 + 0.04 * np.sin(3 * ph + 0.6)], 1)
    lh = np.stack([0.12 + 0.015 * np.sin(2 * ph + 1), 0.11 + 0.01 * np.sin(4 * ph), 0.47 + 0.02 * np.cos(2 * ph)], 1)
    W = arm_ik(W, h, "R", base + rh, pole=np.array([-0.8, -0.2, -0.4]),
               hand_dir=ca.nrm(np.array([0.25, -0.75, 0.6])), across=np.array([-0.2, 0.0, 1.0]))
    W = arm_ik(W, h, "L", base + lh, pole=np.array([0.8, -0.2, -0.4]),
               hand_dir=ca.nrm(np.array([-0.2, -0.8, 0.6])), across=np.array([0.2, 0.0, 1.0]))
    c = dict(c, W=W, hips=h)
    c = twist_split(c)
    c = fingers(c, "cup", "cup")
    c["W"] = ca.breathing(sk, c["W"], dt, 0.33, 1.0)
    save("kneel_work", c, True, 0.0, source="hand-keyed (IK, procedural working hands + breathing)")


# ----------------------------------------------------------------------------------
# London 1940 clips (hand-keyed + CMU bases)
# ----------------------------------------------------------------------------------


def periodic(times, values, t, period):
    """Periodic cubic interpolation of keyframes (times in [0, period), values (K, ...))."""
    from scipy.interpolate import CubicSpline
    tt = np.concatenate([times, [times[0] + period]])
    vv = np.concatenate([values, values[:1]], 0)
    cs = CubicSpline(tt, vv, axis=0, bc_type="periodic")
    return cs(np.mod(t - times[0], period) + times[0])


def speech_jaw(c, amount=7.0, seed=3):
    F = len(c["W"])
    t = np.arange(F) * c["dt"]
    phr = np.clip(ca.smooth_noise(F, c["dt"], 1.6, seed) * 1.5 + 0.4, 0, 1)
    syl = 0.5 + 0.5 * np.sin(2 * np.pi * 4.3 * t + 2.0 * np.sin(2 * np.pi * 0.9 * t))
    open_deg = amount * phr * syl
    Q = sk.local_from_world(c["W"])
    jb = sk.i("jaw")
    for f in range(F):
        Q[f, jb] = Q[f, jb] @ local_euler([-open_deg[f] * jaw_sign(), 0, 0])
    return dict(c, W=sk.world_from_local(Q))


def joint(W, h, name):
    H, _ = sk.fk_positions(W, h)
    return H[:, sk.i(name)]


@recipe
def clip_lie_sleep():
    """Asleep on the left side, knees drawn up, head pillowed on the left forearm."""
    dur = 8.0
    F = int(dur * FPS)
    dt = 1 / FPS
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"].copy()
    # pose in the upright frame first, then lay the body down on its left side
    for b, a in (("spine05", 4), ("spine04", 5), ("spine03", 6), ("spine02", 5), ("spine01", 3)):
        W = rotw(W, b, X, a)
    W = rotw(W, "neck01", X, 10)
    W = rotw(W, "head", X, 12)
    W = rotw(W, "neck02", Z, -6)   # head tips a little towards the pillowing arm (left)
    H, _ = sk.fk_positions(W, h)
    for s, sg, hipf, kneef, dx in (("L", 1, 62, 95, 0.0), ("R", -1, 80, 100, 0.10)):
        hip = H[:, sk.i("upperleg01." + s)]
        l1 = np.linalg.norm(sk.head[sk.i("lowerleg01." + s)] - sk.head[sk.i("upperleg01." + s)])
        l2 = np.linalg.norm(sk.head[sk.i("foot." + s)] - sk.head[sk.i("lowerleg01." + s)])
        a1 = np.radians(hipf)
        a2 = np.radians(hipf - kneef)
        knee = hip + l1 * np.array([0, -np.cos(a1), np.sin(a1)])
        ank = knee + l2 * np.array([0, -np.cos(a2), np.sin(a2)])
        ank[:, 0] += dx  # upper leg rests forward/down on the lower one
        W = leg_ik(W, h, s, ank, pole=np.array([dx * 3, 0.2, 1.0]),
                   foot_frame=ca.axis_angle(X, -25 + 30))
    H, _ = sk.fk_positions(W, h)
    shL = H[:, sk.i("upperarm01.L")]
    head = H[:, sk.i("head")]
    # lower (left) arm: forearm under the side of the head
    W = arm_ik(W, h, "L", head + np.array([0.13, 0.02, 0.17]), pole=np.array([0.5, -0.8, 0.4]),
               hand_dir=ca.nrm(np.array([-0.4, 0.5, 0.5])), across=np.array([0, 0, 1.0]))
    # upper (right) arm draped forward, hand resting on the ground in front of the chest
    W = arm_ik(W, h, "R", np.broadcast_to([0.14, 1.12, 0.36], (F, 3)), pole=np.array([-1.0, -0.2, -0.2]),
               hand_dir=ca.nrm(np.array([0.6, -0.3, 0.6])), across=np.array([0, 1.0, 0.2]))
    # lay down: face towards +X, left side on the ground, head towards -Z
    W = rotw(W, "hips", X, -90)
    W = rotw(W, "hips", Z, -90)
    c = dict(c, W=W, hips=h)
    c = fingers(c, "relaxed", "relaxed")
    c = twist_split(c)
    c["W"] = ca.breathing(sk, c["W"], dt, 0.22, 1.3)
    n1 = ca.smooth_noise(F, dt, 4.0, 31)
    c["W"] = rotw(c["W"], "lowerarm01.R", Y, 1.0, n1 * 1.5)
    # rest on the ground: lowest of shoulder/hip/knee joints minus flesh thickness = 0
    H, _ = sk.fk_positions(c["W"], h)
    low = min(np.percentile(H[:, sk.i("upperarm01.L"), 1], 50) - 0.065,
              np.percentile(H[:, sk.i("upperleg01.L"), 1], 50) - 0.13,
              np.percentile(H[:, sk.i("lowerleg01.L"), 1], 50) - 0.055,
              np.percentile(H[:, sk.i("head"), 1], 50) - 0.15)
    c["hips"] = h.copy()
    c["hips"][:, 1] -= low
    save("lie_sleep", c, True, 0.0, source="hand-keyed (IK, slow breathing)")


@recipe
def clip_sit_huddle():
    """Sitting on the ground, knees drawn up, arms wrapped round the shins, head bowed, rocking."""
    dur = 6.0
    F = int(dur * FPS)
    dt = 1 / FPS
    t = np.arange(F) * dt
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"].copy()
    rock = np.sin(2 * np.pi * 2 * t / dur)
    W = rotw(W, "hips", X, -8)
    for b, a in (("spine05", 6), ("spine04", 7), ("spine03", 8), ("spine02", 7), ("spine01", 5)):
        W = rotw(W, b, X, 1.0, a + 1.5 * rock)
    W = rotw(W, "neck01", X, 14)
    W = rotw(W, "head", X, 1.0, 22 + 3 * rock)
    W = rotw(W, "head", Y, 1.0, 4 * ca.smooth_noise(F, dt, 3.0, 41))
    # pelvis on the ground
    H, _ = sk.fk_positions(W, h)
    hipy = (H[:, sk.i("upperleg01.L"), 1] + H[:, sk.i("upperleg01.R"), 1]) / 2
    h[:, 1] -= hipy - 0.115
    h[:, 2] = -0.18
    H, _ = sk.fk_positions(W, h)
    for s, sg in (("L", 1), ("R", -1)):
        ank = H[:, sk.i("upperleg01." + s)] * np.array([1, 0, 1]) + np.array([0.035 * sg, sk.head[sk.i("foot." + s)][1] + 0.01, 0.37])
        W = leg_ik(W, h, s, ank, pole=np.array([0.15 * sg, 1.0, 0.6]),
                   foot_frame=ca.axis_angle(Y, 6 * sg) @ ca.axis_angle(X, -8))
    H, _ = sk.fk_positions(W, h)
    kn = (H[:, sk.i("lowerleg01.L")] + H[:, sk.i("lowerleg01.R")]) / 2
    for s, sg, dy in (("L", 1, -0.10), ("R", -1, -0.135)):
        tgt = kn + np.array([-0.035 * sg, dy, 0.085])
        W = arm_ik(W, h, s, tgt, pole=np.array([1.0 * sg, -0.3, 0.1]),
                   hand_dir=ca.nrm(np.array([-1.0 * sg, -0.15, -0.1])), across=np.array([0, 0.3, 1.0]))
    c = dict(c, W=W, hips=h)
    c = twist_split(c)
    c = fingers(c, "cup", "cup")
    c["W"] = ca.breathing(sk, c["W"], dt, 0.33, 0.9)
    save("sit_huddle", c, True, 0.0, source="hand-keyed (IK, rocking + breathing)")


@recipe
def clip_dig():
    """Shovelling rubble: thrust, lever, lift and toss to the right (implied shovel, no prop)."""
    dur = 2.4
    F = int(dur * FPS)
    dt = 1 / FPS
    t = np.arange(F) * dt
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"].copy()
    kt = np.array([0.0, 0.55, 1.0, 1.5, 1.9]) * dur / 2.4
    #            drop  flex  yaw   L hand (lower)        R hand (upper, handle top)
    keys = np.array([
        [0.07, 30, 0, 0.03, 0.60, 0.50, -0.06, 0.92, 0.24],
        [0.11, 40, 2, 0.03, 0.40, 0.56, -0.04, 0.74, 0.32],
        [0.12, 42, 0, 0.02, 0.47, 0.50, -0.05, 0.58, 0.20],
        [0.05, 22, -12, -0.02, 0.86, 0.44, -0.10, 0.92, 0.12],
        [0.03, 18, -34, -0.24, 0.96, 0.38, -0.30, 0.98, 0.04],
    ])
    k = periodic(kt, keys, t, dur)
    h[:, 1] -= k[:, 0]
    h[:, 2] -= 0.04 * k[:, 0] / 0.12
    W = rotw(W, "hips", X, 1.0, k[:, 1] * 0.35)
    for b, a in (("spine05", 0.14), ("spine04", 0.14), ("spine03", 0.14), ("spine02", 0.13), ("spine01", 0.1)):
        W = rotw(W, b, X, 1.0, k[:, 1] * a)
        W = rotw(W, b, Y, 1.0, k[:, 2] * 0.16)
    W = rotw(W, "neck01", X, 1.0, k[:, 1] * 0.1)
    W = rotw(W, "head", X, 1.0, 8 + k[:, 1] * 0.15)
    W = rotw(W, "head", Y, 1.0, -k[:, 2] * 0.3)
    H, _ = sk.fk_positions(W, h)
    for s, sg, z in (("L", 1, 0.20), ("R", -1, -0.14)):
        ank = np.broadcast_to(np.array([0.15 * sg, sk.head[sk.i("foot." + s)][1], z]), (F, 3))
        W = leg_ik(W, h, s, ank, pole=np.array([0.25 * sg, 0.0, 1.0]), foot_frame=ca.axis_angle(Y, (10 if s == "L" else -25)))
    for s, sg, cols in (("L", 1, slice(3, 6)), ("R", -1, slice(6, 9))):
        W = arm_ik(W, h, s, k[:, cols], pole=np.array([0.9 * sg, -0.6, -0.2]))
    c = dict(c, W=W, hips=h)
    c = twist_split(c)
    c = fingers(c, "grip", "grip")
    c["W"] = ca.breathing(sk, c["W"], dt, 0.42, 0.8)
    save("dig", c, True, 0.0, source="hand-keyed (IK shovelling cycle)")


@recipe
def clip_carry_box():
    c, v = locomotion("35_01", 0.95, 1.3, lock=False)
    c = head_level(c, -10.0)
    W, h = c["W"], c["hips"]
    W = rotw(W, "spine03", X, -3)  # lean back against the load
    W = rotw(W, "spine01", X, -2)
    yf = yaw_frame(W)
    H, _ = sk.fk_positions(W, h)
    hb = H[:, sk.i("hips")]
    bob = (hb[:, 1] - hb[:, 1].mean()) * 0.5
    for s, sg in (("L", 1), ("R", -1)):
        off = np.array([0.175 * sg, 0.0, 0.31])
        tgt = hb + np.einsum("fij,j->fi", yf, off)
        tgt[:, 1] = hb[:, 1].mean() + 0.22 + bob
        pole = np.einsum("fij,j->fi", yf, np.array([0.8 * sg, -0.6, -0.4]))
        hd = np.einsum("fij,j->fi", yf, ca.nrm(np.array([-0.25 * sg, -0.25, 1.0])))
        ac = np.einsum("fij,j->fi", yf, np.array([0, 1.0, 0]))
        W = arm_ik(W, h, s, tgt, pole, hand_dir=hd, across=ac)
    c["W"] = W
    c = twist_split(c)
    c = fingers(c, "cup", "cup")
    c = ground_fix(c)
    vv = ca.measure_speed(sk, c)
    c = foot_lock(c, vv)
    v2 = ca.measure_speed(sk, c)
    save("carry_box", c, True, v2, source="CMU 35_01 (walk) + box-carrying arm IK")


@recipe
def clip_kneel_listen():
    """Kneeling on the right knee over rubble, head bowed and turned, right hand cupped to the ear."""
    dur = 6.0
    F = int(dur * FPS)
    dt = 1 / FPS
    t = np.arange(F) * dt
    c = static_rest(F, dt)
    W, h = c["W"], c["hips"].copy()
    l1 = np.linalg.norm(sk.head[sk.i("lowerleg01.R")] - sk.head[sk.i("upperleg01.R")])
    hip_r = sk.head[sk.i("upperleg01.R")]
    knee_y = 0.065
    h[:, 1] += knee_y + np.sqrt(l1 ** 2 - 0.12 ** 2) - hip_r[1]
    W = rotw(W, "hips", X, 18)
    for b, a in (("spine05", 8), ("spine04", 9), ("spine03", 9), ("spine02", 8), ("spine01", 6)):
        W = rotw(W, b, X, a)
    hold = ca.smooth_noise(F, dt, 3.0, 51)
    W = rotw(W, "neck01", X, 12)
    W = rotw(W, "head", X, 1.0, 22 + 2 * hold)
    W = rotw(W, "neck02", Y, 14)          # right ear turned down towards the rubble
    W = rotw(W, "head", Z, 1.0, 16 + 2 * hold)
    H, _ = sk.fk_positions(W, h)
    hipR = H[:, sk.i("upperleg01.R")]
    knee = hipR + np.array([0.0, 0, 0.12])
    knee[:, 1] = knee_y
    l2 = np.linalg.norm(sk.head[sk.i("foot.R")] - sk.head[sk.i("lowerleg01.R")])
    ank = knee + np.array([0.02, 0.0, -l2 * 0.97])
    ank[:, 1] = 0.105
    W = leg_ik(W, h, "R", ank, pole=np.array([0, -0.3, 1.0]), foot_frame=ca.axis_angle(X, 70))
    hipL = H[:, sk.i("upperleg01.L")]
    ankL = hipL + np.array([0.08, 0, 0.42])
    ankL[:, 1] = sk.head[sk.i("foot.L")][1]
    W = leg_ik(W, h, "L", ankL, pole=np.array([0.3, 0.3, 1.0]), foot_frame=np.eye(3))
    H, _ = sk.fk_positions(W, h)
    hb = sk.i("head")
    up = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Y)
    fw = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ Z)
    lf = np.einsum("fij,j->fi", W[:, hb], sk.B[hb].T @ X)
    ear = H[:, hb] - lf * 0.085 + up * 0.035 - fw * 0.01
    W = arm_ik(W, h, "R", ear - lf * 0.03 - up * 0.07 - fw * 0.045, pole=np.array([-1.0, -0.6, 0.2]),
               hand_dir=ca.nrm(up * 0.9 + fw * 0.3), across=ca.nrm(lf))
    base = H[:, sk.i("hips")] * np.array([1, 0, 1])
    W = arm_ik(W, h, "L", base + np.array([0.16, 0.10, 0.44]), pole=np.array([0.8, -0.2, -0.4]),
               hand_dir=ca.nrm(np.array([-0.1, -0.5, 1.0])), across=np.array([-1.0, 0.0, 0.1]))
    c = dict(c, W=W, hips=h)
    c = twist_split(c)
    c = fingers(c, "loose", "cup")
    c["W"] = ca.breathing(sk, c["W"], dt, 0.2, 0.7)  # holding the breath to listen: slow and shallow
    save("kneel_listen", c, True, 0.0, source="hand-keyed (IK, kneeling, hand cupped to the ear)")


@recipe
def clip_wave():
    base = mocap_static("77_02", 1.0, 7.8, 3.0, 3.6)
    base = head_level(base, -2.0)
    F = len(base["W"])
    dt = base["dt"]
    t = np.arange(F) * dt
    W0, h = base["W"], base["hips"]
    W0 = ca.finger_pose(sk, W0, "L", "relaxed")
    W0 = ca.finger_pose(sk, W0, "R", "relaxed")
    Wp = rotw(W0, "spine03", Z, 3)
    Wp = rotw(Wp, "head", X, -6)
    H, _ = sk.fk_positions(Wp, h)
    sh = H[:, sk.i("upperarm01.R")]
    ph = 2 * np.pi * 1.8 * t
    osc = np.sin(ph)
    tgt = sh + np.stack([-0.20 + 0.10 * osc, 0.47 + 0.02 * np.cos(2 * ph), 0.14 + 0.0 * osc], 1)
    hd = ca.nrm(np.stack([-0.45 * osc - 0.1, np.ones(F), 0.15 * np.ones(F)], 1))
    Wp = arm_ik(Wp, h, "R", tgt, pole=np.array([-1.0, -0.4, -0.1]), hand_dir=hd,
                across=np.array([1.0, 0.0, 0.15]))
    Wp = rotw(Wp, "clavicle.R", Z, 8)
    Wp = ca.finger_pose(sk, Wp, "R", "spread")
    w = env(t, 0.2, 0.75, F * dt - 0.8, F * dt - 0.15)
    delay = {"clavicle.R": -0.04, "lowerarm01.R": 0.05, "lowerarm02.R": 0.06, "wrist.R": 0.09,
             "head": -0.1, "neck02": -0.08}
    W = blend_local(W0, Wp, w, delay=delay, dt=dt)
    c = dict(base, W=W)
    c = twist_split(c)
    c["W"] = ca.breathing(sk, c["W"], dt, 0.25, 0.6)
    save("wave", c, False, 0.0, source="CMU 77_02 (standing) base + hand-keyed waving arm (IK)")


@recipe
def clip_talk_worried():
    c = mocap_static("77_02", 1.0, 7.8, 4.0, 6.5)
    c = head_level(c, -9.0)
    F = len(c["W"])
    dt = c["dt"]
    t = np.arange(F) * dt
    dur = F * dt
    W0, h = c["W"], c["hips"]
    W = W0
    for s, sg in (("L", 1), ("R", -1)):
        W = ca.set_local(sk, W, "clavicle." + s, local_euler([0, 0, 5 * sg]), 1.0)  # shoulders raised
    W = rotw(W, "spine01", X, 4)
    yf = yaw_frame(W)
    H, _ = sk.fk_positions(W, h)
    hb = H[:, sk.i("hips")]
    nw = max(1, round(dur * 0.7))
    ph = 2 * np.pi * nw * t / dur
    gest = env(np.mod(t, dur), dur * 0.38, dur * 0.48, dur * 0.62, dur * 0.74)
    for s, sg in (("L", 1), ("R", -1)):
        wring = np.stack([0.016 * np.cos(ph) * sg, 0.014 * np.sin(ph) * sg, 0.008 * np.sin(ph + 1)], 1)
        off = np.array([0.04 * sg, 0.085, 0.215]) + wring
        if s == "R":  # one open-palm "what can we do" gesture per loop
            off = off * (1 - gest[:, None]) + np.array([-0.24, 0.12, 0.30]) * gest[:, None]
        tgt = hb + np.einsum("fij,fj->fi", yf, off)
        hd = np.einsum("fij,j->fi", yf, ca.nrm(np.array([-0.75 * sg, 0.1, 0.6])))
        ac = np.einsum("fij,j->fi", yf, np.array([0, 1.0, 0.0]))
        if s == "R":
            hd = ca.nrm(hd * (1 - gest[:, None]) + np.einsum("fij,j->fi", yf, ca.nrm(np.array([-0.3, 0.1, 1.0]))) * gest[:, None])
            ac = ca.nrm(ac * (1 - gest[:, None]) + np.einsum("fij,j->fi", yf, np.array([1.0, 0.0, 0.0])) * gest[:, None])
        pole = np.einsum("fij,j->fi", yf, np.array([0.8 * sg, -0.7, -0.3]))
        W = arm_ik(W, h, s, tgt, pole, hand_dir=hd, across=ac)
    # anxious head: small shakes and glances up
    W = rotw(W, "head", Y, 1.0, 5 * np.sin(2 * np.pi * round(dur * 0.5) * t / dur) * ca.smooth_noise(F, dt, 2.0, 61))
    W = rotw(W, "neck02", X, 1.0, -6 * gest)
    c = dict(c, W=W)
    c = twist_split(c)
    c = fingers(c, "loose", "loose")
    c["W"] = ca.breathing(sk, c["W"], dt, 0.4, 0.7)  # quicker, shallow breathing
    c = speech_jaw(c, 6.5, seed=7)
    save("talk_worried", c, True, 0.0, source="CMU 77_02 (standing) base + hand-keyed hand-wringing/gesture (IK), procedural jaw")


def main(names):
    for n in names or RECIPES:
        RECIPES[n]()


if __name__ == "__main__":
    main(sys.argv[1:])


def raw(file):
    """Debug helper: whole clip, grounded, facing forward on average."""
    c = src(file)
    c = face_forward(c)
    c = ground_fix(c)
    save("raw_" + file, c, False, 0.0, source=file)
