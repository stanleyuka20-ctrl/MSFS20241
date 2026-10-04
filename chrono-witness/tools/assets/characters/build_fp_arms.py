"""First-person arms: MakeHuman forearms + hands, dark charcoal wool coat sleeves to
mid-forearm, slim 'temporal device' band on the LEFT wrist (separate emissive material
'device_screen'), own small rig and fp_* clips.  Camera space: origin = camera, looking -Z,
+Y up.  Output: public/assets/characters/fp_arms.glb

    python build_fp_arms.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from scipy.spatial.transform import Rotation as Rot

import cw_anim as ca
import cw_blender as cb
import cw_character as C
import cw_garment as G
import cw_materials as MAT
import cw_paths as P
import cw_tex as T
import mhcore as mh
from cw_anim import nrm

import build_character as BC

FPS = 30
CFG = dict(macro=dict(mh.CANON), skin=(205, 156, 128), skin_dark=(166, 112, 88), skin_red=(200, 112, 96),
           hair_col=(60, 44, 30), stubble=0.0, seed=901, mud=0.0, wet=0.0, face_mud=0.0, cheek_red=0.0)


def fp_skeleton(B):
    """Bones (camera-space positions are applied later): root, upperarm, forearm, forearm_twist,
    hand, 5 fingers x 3 per side."""
    sk = B.sk
    bones = [dict(name="fp_root", parent=None, head=np.zeros(3), tail=np.array([0, 0.1, 0.0]),
                  normal=np.array([1.0, 0, 0]))]
    for s in "LR":
        def jb(n):
            return sk[n]
        ua = dict(name="upperarm." + s, parent="fp_root", head=jb("upperarm01." + s)["head"],
                  tail=jb("lowerarm01." + s)["head"], normal=jb("upperarm02." + s)["normal"])
        fa = dict(name="forearm." + s, parent="upperarm." + s, head=jb("lowerarm01." + s)["head"],
                  tail=jb("lowerarm02." + s)["head"], normal=jb("lowerarm01." + s)["normal"])
        ft = dict(name="forearm_twist." + s, parent="forearm." + s, head=jb("lowerarm02." + s)["head"],
                  tail=jb("wrist." + s)["head"], normal=jb("lowerarm02." + s)["normal"])
        hd = dict(name="hand." + s, parent="forearm_twist." + s, head=jb("wrist." + s)["head"],
                  tail=(jb("finger3-1." + s)["head"]), normal=jb("wrist." + s)["normal"])
        bones += [ua, fa, ft, hd]
        if s == "R":
            bones.append(dict(name="prop.R", parent="hand.R", head=jb("wrist.R")["head"],
                              tail=jb("wrist.R")["head"] + np.array([0, -0.05, 0]), normal=np.array([1.0, 0, 0])))
        msk = mh.load_mhskel()
        for f in range(1, 6):
            par = "hand." + s
            for k in (1, 2, 3):
                n = "finger%d-%d.%s" % (f, k, s)
                b = msk["bones"][n]
                head = mh.joint_pos(B.v_all, b["head"])
                tail = mh.joint_pos(B.v_all, b["tail"])
                pl = msk["planes"][b["rotation_plane"]]
                a_, b_, c_ = [mh.joint_pos(B.v_all, x) for x in pl]
                nn = np.cross(b_ - a_, c_ - b_)
                nn = nn / np.linalg.norm(nn)
                bones.append(dict(name=n, parent=par, head=head, tail=tail, normal=nn))
                par = n
    return bones


def fp_weight_map():
    """MakeHuman bone -> fp bone."""
    s_ = mh.load_mhskel()
    m = {}
    for name in s_["bones"]:
        side = name[-1] if name[-2:] in (".L", ".R") else None
        tgt = None
        if side:
            if name.startswith(("upperarm", "shoulder01", "clavicle")):
                tgt = "upperarm." + side
            elif name.startswith("lowerarm01"):
                tgt = "forearm." + side
            elif name.startswith("lowerarm02"):
                tgt = "forearm_twist." + side
            elif name.startswith(("wrist", "metacarpal")):
                tgt = "hand." + side
            elif name.startswith("finger"):
                tgt = name
        m[name] = tgt or "fp_root"
    return m


def fp_weights(names, nverts):
    mhw = mh.load_mhw()["weights"]
    m = fp_weight_map()
    bi = {n: i for i, n in enumerate(names)}
    W = np.zeros((nverts, len(names)))
    for bname, lst in mhw.items():
        arr = np.array(lst)
        if len(arr) == 0:
            continue
        idx = arr[:, 0].astype(int)
        ok = idx < nverts
        np.add.at(W[:, bi[m.get(bname, "fp_root")]], idx[ok], arr[ok, 1])
    return W


# camera transform: body space -> camera space (camera at the eyes, looking down -Z)
def cam_xform(B):
    eye = (B.landmarks["eye.L"] + B.landmarks["eye.R"]) / 2 + np.array([0, 0, 0.01])
    Ry = np.array([[-1.0, 0, 0], [0, 1, 0], [0, 0, -1.0]])
    return lambda p: (np.asarray(p) - eye) @ Ry.T, Ry


def build_geometry():
    B = C.build_body(CFG)
    R = C.regions(B)
    p = B.v
    names_tmp = None
    out = {}
    side_masks = {}
    t_ua = {}
    for s, sg in (("L", 1), ("R", -1)):
        side = (p[:, 0] * sg) > 0.12
        t_ua[s] = C.seg_param(B, p, "upperarm02." + s, "lowerarm01." + s)
        side_masks[s] = side & (R["arm"] > 0.5) & ((t_ua[s] > 0.35) | (R["fa." + s] > -0.2))
    arm_v = side_masks["L"] | side_masks["R"]
    # skin: from mid-forearm to the finger tips
    skin_v = arm_v & ((R["fa"] > 0.42) | (R["hand"] > 0.3))
    sleeve_v = arm_v & ~((R["fa"] > 0.56) | (R["hand"] > 0.3))
    fsk = C.faces_all(B, skin_v)
    skin = G.submesh(B.v, B.f, fsk, B.W)
    skin.loop_uv = [B.fuv[i] for i in np.where(fsk)[0]]
    skin.attrs["hand"] = R["hand"][skin.src]
    skin.attrs["dens"] = np.zeros(len(skin.v))
    fsl = C.faces_all(B, sleeve_v)
    sleeve = G.shell(B.ref, fsl, 0.010, smooth=14, dmin=0.007)
    for L in G.boundary_loops(sleeve.f):
        c = sleeve.v[L].mean(0)
        G.lip(sleeve, L, depth=0.005, back=0.018)
    # device band on the LEFT wrist + screen patch on the dorsal side
    a = C.J(B, "lowerarm01.L")
    b = C.J(B, "wrist.L")
    mask = (p[:, 0] > 0.2) & (R["arm"] > 0.5) & (R["hand"] < 0.6)
    band = C.limb_wrap(B, mask, a, b, 0.84, 0.95, 0.0032, nseg=40, nring=5)
    # dorsal direction (back of the hand)
    back = MAT.nail_dir(B.sk, "L", 3)
    ax = nrm(b - a)
    cen = band.v.mean(0)
    d = band.v - cen
    d -= (d @ ax)[:, None] * ax
    facing = (nrm(d) @ back)
    # screen: copy the band quads facing the back of the wrist, raised a little
    faces_scr = [f for f in band.f if np.all(facing[list(f)] > 0.55)]
    scr = G.Mesh(band.v.copy(), faces_scr)
    used = np.unique(np.concatenate([np.array(f) for f in faces_scr]))
    remap = -np.ones(len(scr.v), int)
    remap[used] = np.arange(len(used))
    scr = G.Mesh(band.v[used] + nrm(d[used]) * 0.0012, [tuple(remap[list(f)]) for f in faces_scr])
    # screen UV: u around, v along
    ang = np.arctan2(d[used] @ np.cross(ax, back), d[used] @ back)
    al = (band.v[used] - cen) @ ax
    uvv = np.stack([(ang - ang.min()) / max(np.ptp(ang), 1e-6), (al - al.min()) / max(np.ptp(al), 1e-6)], 1)
    scr.loop_uv = [[tuple(uvv[remap[i]]) for i in f] for f in faces_scr]
    # bevelled housing for the screen (slightly larger, darker)
    out = dict(skin=skin, sleeve=sleeve, band=band, screen=scr)
    cover = sleeve_v & (R["fa"] < 0.5)
    return B, R, out


# ----------------------------------------------------------------------------------
# clips
# ----------------------------------------------------------------------------------


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class FPRig:
    def __init__(self, bones_cam):
        self.sk = ca.Skeleton(bones_cam)

    def pose(self, targets, F):
        """targets: dict side -> dict(wrist (F,3), pole (F,3)|(3,), hand_dir, across, fingers (F,5,3) deg)."""
        sk = self.sk
        W = sk.rest_world(F)
        hips = np.zeros((F, 3))
        for s, tg in targets.items():
            W = ca.two_bone_ik(sk, W, hips, "upperarm." + s, "forearm." + s, "hand." + s, tg["wrist"],
                               pole=tg["pole"], chain_lower=("forearm_twist." + s,))
            if tg.get("hand_dir") is not None:
                H, _ = sk.fk_positions(W, hips)
                wr = H[:, sk.i("hand." + s)]
                ib = H[:, sk.i("finger2-1." + s)]
                rb = H[:, sk.i("finger5-1." + s)]
                d = nrm((ib + rb) / 2 - wr)
                acr = nrm(ib - rb)
                Fc = ca.frame(d, acr)
                Ft = ca.frame(np.broadcast_to(tg["hand_dir"], (F, 3)), np.broadcast_to(tg["across"], (F, 3)))
                Rm = np.einsum("fij,fkj->fik", Ft, Fc)
                b = sk.i("hand." + s)
                Wn = W.copy()
                Wn[:, b] = Rm @ W[:, b]
                W = ca.recompute_children(sk, W, Wn, {b})
            # twist split between the forearm twist bone and the hand
            Q = sk.local_from_world(W)
            ih, it = sk.i("hand." + s), sk.i("forearm_twist." + s)
            r = Rot.from_matrix(Q[:, ih])
            q = r.as_quat()
            pr = q[:, 1:2] * np.array([[0, 1.0, 0]])
            tw = np.concatenate([pr, q[:, 3:4]], 1)
            tw /= np.linalg.norm(tw, axis=1, keepdims=True)
            rt = Rot.from_quat(tw)
            ang = rt.as_rotvec()[:, 1]
            Q[:, ih] = (r * rt.inv() * Rot.from_rotvec(np.outer(ang * 0.4, [0, 1, 0]))).as_matrix()
            Q[:, it] = (Rot.from_matrix(Q[:, it]) * Rot.from_rotvec(np.outer(ang * 0.6, [0, 1, 0]))).as_matrix()
            W = sk.world_from_local(Q)
            if "fingers" in tg:
                W = self.fingers(W, s, tg["fingers"])
        return W

    def curl_sign(self, n):
        sk = self.sk
        s = n[-1]
        b = sk.i(n)
        ib = sk.head[sk.i("finger2-1." + s)]
        rb = sk.head[sk.i("finger5-1." + s)]
        wr = sk.head[sk.i("hand." + s)]
        tip = sk.tail[sk.i("finger3-3." + s)]
        mid = sk.head[sk.i("finger3-1." + s)]
        hd = nrm((ib + rb) / 2 - wr)
        bend = (tip - mid) - np.dot(tip - mid, hd) * hd
        palm = nrm(bend)
        if n.startswith("finger1"):
            target = nrm(rb - sk.head[b])
        else:
            target = palm
        tip_move = np.cross(sk.B[b][:, 0], sk.B[b][:, 1])
        return 1 if np.dot(tip_move, target) > 0 else -1

    def fingers(self, W, s, curls):
        """curls: (F,5,3) degrees (thumb..little, joint 1..3)."""
        sk = self.sk
        Q = sk.local_from_world(W)
        F = len(W)
        for f in range(5):
            for k in range(3):
                n = "finger%d-%d.%s" % (f + 1, k + 1, s)
                b = sk.i(n)
                sg = self.curl_sign(n)
                rv = np.zeros((F, 3))
                rv[:, 0] = np.radians(curls[:, f, k]) * sg
                Q[:, b] = Rot.from_rotvec(rv).as_matrix()
        return sk.world_from_local(Q)


HANDS = {
    "relaxed": [(10, 12, 8), (18, 24, 14), (22, 30, 16), (26, 34, 18), (30, 36, 20)],
    "open": [(2, 4, 2), (4, 6, 4), (5, 6, 4), (6, 8, 5), (8, 10, 6)],
    "grip": [(28, 35, 28), (68, 82, 45), (72, 86, 46), (74, 86, 46), (76, 86, 46)],
    "pinch": [(25, 30, 22), (40, 45, 30), (55, 70, 40), (62, 75, 42), (66, 78, 44)],
    "press": [(25, 30, 25), (6, 6, 4), (70, 85, 45), (74, 86, 46), (76, 86, 46)],
}


def hand_curl(name, F, w=None):
    a = np.array(HANDS[name], float)
    return np.broadcast_to(a, (F, 5, 3)).copy()


def blend_curl(a, b, t):
    t = np.asarray(t)[:, None, None]
    return a * (1 - t) + b * t


def noise(F, dt, period, seed, amp):
    return ca.smooth_noise(F, dt, period, seed) * amp


def make_clips(rig):
    clips = {}
    dt = 1 / FPS

    def vec(F, v):
        return np.broadcast_to(np.asarray(v, float), (F, 3)).copy()

    # ---- fp_idle: relaxed, mostly below the frame (loop 4 s)
    F = 120
    t = np.arange(F) * dt
    br = np.sin(2 * np.pi * t / 4.0)
    tg = {}
    for s, sg in (("L", -1), ("R", 1)):
        w = vec(F, [0.2 * sg, -0.56, -0.16])
        w[:, 1] += 0.008 * br + noise(F, dt, 2.0, 3 if s == "L" else 4, 0.004)
        w[:, 0] += noise(F, dt, 2.5, 5 if s == "L" else 6, 0.004)
        tg[s] = dict(wrist=w, pole=np.array([0.6 * sg, -0.3, 0.6]), hand_dir=nrm(np.array([0.05 * sg, -1.0, -0.35])),
                     across=np.array([0, 0, -1.0]), fingers=hand_curl("relaxed", F))
    clips["fp_idle"] = (rig.pose(tg, F), True)

    # ---- fp_reach: right hand reaches forward, presses, returns (one-shot 0.6 s)
    F = 19
    t = np.arange(F) / (F - 1)
    out = ease(t / 0.42) * (1 - ease((t - 0.62) / 0.38))
    pr = ease((t - 0.3) / 0.15) * (1 - ease((t - 0.6) / 0.15))
    w0 = np.array([0.2, -0.56, -0.16])
    w1 = np.array([0.07, -0.15, -0.52])
    wr = w0[None] + (w1 - w0)[None] * out[:, None]
    wr[:, 1] += 0.06 * np.sin(np.pi * out) * (1 - out)
    wr[:, 2] -= 0.025 * pr
    hd = nrm((1 - out)[:, None] * np.array([0.05, -1.0, -0.35]) + out[:, None] * np.array([-0.05, -0.15, -1.0]))
    ac = nrm((1 - out)[:, None] * np.array([0, 0, -1.0]) + out[:, None] * np.array([-1.0, 0.0, 0.0]))
    cur = blend_curl(hand_curl("relaxed", F), hand_curl("open", F), ease(out * 1.5))
    cur = blend_curl(cur, hand_curl("press", F), pr)
    tgR = dict(wrist=wr, pole=np.array([0.9, -0.5, 0.3]), hand_dir=hd, across=ac, fingers=cur)
    Fi = clips["fp_idle"][0]
    tgL = dict(wrist=vec(F, [-0.2, -0.56, -0.16]), pole=np.array([-0.6, -0.3, 0.6]),
               hand_dir=nrm(np.array([-0.05, -1.0, -0.35])), across=np.array([0, 0, -1.0]),
               fingers=hand_curl("relaxed", F))
    clips["fp_reach"] = (rig.pose({"L": tgL, "R": tgR}, F), False)

    # ---- fp_hold: right hand holds a folded paper in view (loop 3 s)
    F = 90
    t = np.arange(F) * dt
    sway = np.sin(2 * np.pi * t / 3.0)
    w = vec(F, [0.13, -0.21, -0.33])
    w[:, 1] += 0.006 * sway + noise(F, dt, 1.5, 11, 0.003)
    w[:, 0] += noise(F, dt, 1.5, 12, 0.003)
    tgR = dict(wrist=w, pole=np.array([1.0, -0.8, 0.2]), hand_dir=nrm(np.array([-0.6, 0.55, -0.55])),
               across=nrm(np.array([0.35, 0.3, 0.9])), fingers=hand_curl("pinch", F))
    tgL = dict(wrist=vec(F, [-0.2, -0.56, -0.16]) + np.stack([np.zeros(F), 0.006 * sway, np.zeros(F)], 1),
               pole=np.array([-0.6, -0.3, 0.6]), hand_dir=nrm(np.array([-0.05, -1.0, -0.35])),
               across=np.array([0, 0, -1.0]), fingers=hand_curl("relaxed", F))
    clips["fp_hold"] = (rig.pose({"L": tgL, "R": tgR}, F), True)

    # ---- fp_scan: left forearm raised, device facing the camera (loop 3 s)
    F = 90
    t = np.arange(F) * dt
    sway = np.sin(2 * np.pi * t / 3.0)
    w = vec(F, [0.03, -0.14, -0.30])
    w[:, 1] += 0.005 * sway + noise(F, dt, 1.5, 21, 0.003)
    w[:, 0] += noise(F, dt, 1.5, 22, 0.002)
    tgL = dict(wrist=w, pole=np.array([-1.0, -0.8, 0.1]), hand_dir=nrm(np.array([0.8, 0.35, -0.45])),
               across=nrm(np.array([0.2, -1.0, -0.25])), fingers=hand_curl("relaxed", F))
    tgR = dict(wrist=vec(F, [0.2, -0.56, -0.16]), pole=np.array([0.6, -0.3, 0.6]),
               hand_dir=nrm(np.array([0.05, -1.0, -0.35])), across=np.array([0, 0, -1.0]),
               fingers=hand_curl("relaxed", F))
    W = rig.pose({"L": tgL, "R": tgR}, F)
    clips["fp_scan"] = (W, True)

    # ---- fp_grip_two: both hands grip handles in front (loop 1.2 s, walking bob)
    F = 36
    t = np.arange(F) * dt
    bob = np.sin(2 * np.pi * t / 0.6)
    tg = {}
    for s, sg in (("L", -1), ("R", 1)):
        w = vec(F, [0.19 * sg, -0.2, -0.42])
        w[:, 1] += 0.012 * bob
        w[:, 0] += 0.004 * np.sin(2 * np.pi * t / 1.2) * sg
        tg[s] = dict(wrist=w, pole=np.array([0.9 * sg, -0.6, 0.3]), hand_dir=nrm(np.array([0.0, -0.45, -1.0])),
                     across=np.array([-1.0 * sg * -1, 0.0, 0.0]) * -1 if False else nrm(np.array([-sg * 1.0, -0.2, 0.0])),
                     fingers=hand_curl("grip", F))
    clips["fp_grip_two"] = (rig.pose(tg, F), True)

    # ---- fp_climb: alternating hands up a ladder (loop 1.6 s, rungs 0.3 m apart)
    F = 48
    t = np.arange(F) / F
    tg = {}
    for s, sg, ph in (("L", -1, 0.0), ("R", 1, 0.5)):
        u = np.mod(t + ph, 1.0)
        # 0..0.6 hand on the rung moving down with the climb, 0.6..1.0 reach up to the next rung
        hold = u < 0.6
        y = np.where(hold, 0.12 - 0.3 * (u / 0.6) * 1.0 - 0.12, 0.0)
        y_hold = 0.06 - (u / 0.6) * 0.30
        k = (u - 0.6) / 0.4
        y_reach = -0.24 + 0.30 * ease(k)
        y = np.where(hold, y_hold, y_reach)
        z = np.where(hold, -0.34, -0.34 + 0.07 * np.sin(np.pi * np.clip(k, 0, 1)))
        w = np.stack([np.full(F, 0.17 * sg), y, z], 1)
        g = np.where(hold, 1.0, 1 - np.sin(np.pi * np.clip(k, 0, 1)))[:, None, None]
        cur = hand_curl("grip", F) * g + hand_curl("open", F) * (1 - g)
        tg[s] = dict(wrist=w, pole=np.array([0.8 * sg, -0.8, 0.2]), hand_dir=nrm(np.array([0.0, 0.2, -1.0])),
                     across=nrm(np.array([-sg * 1.0, 0.0, 0.0])), fingers=cur)
    clips["fp_climb"] = (rig.pose(tg, F), True)
    return clips


# ----------------------------------------------------------------------------------
# build
# ----------------------------------------------------------------------------------


def screen_texture(N=256):
    """Emissive display: concentric arcs, ticks and a segmented readout (own design)."""
    y, x = np.mgrid[0:N, 0:N] / N
    u = x * 2 - 1
    v = y * 2 - 1
    r = np.sqrt((u * 1.0) ** 2 + (v * 1.6) ** 2)
    a = np.arctan2(v, u)
    img = np.zeros((N, N, 3))
    base = np.array([0.02, 0.08, 0.1])
    cyan = np.array([0.25, 0.95, 1.0])
    amber = np.array([1.0, 0.62, 0.2])
    img += base
    ring = np.exp(-((r - 0.62) / 0.025) ** 2) * (np.mod(a * 12 / np.pi, 1.0) < 0.75)
    img += ring[..., None] * cyan * 0.8
    ring2 = np.exp(-((r - 0.42) / 0.012) ** 2) * (a > -0.6) * (a < 2.2)
    img += ring2[..., None] * amber * 0.9
    ticks = (np.abs(r - 0.78) < 0.035) * (np.mod(a * 30 / np.pi, 1.0) < 0.18)
    img += ticks[..., None] * cyan * 0.5
    bars = (np.abs(v) < 0.08) * (np.abs(u) < 0.3) * (np.mod((u + 0.3) * 16, 1.0) < 0.7)
    img += bars[..., None] * cyan * 0.9
    img += (np.exp(-r * 3) * 0.15)[..., None] * cyan
    return np.clip(img, 0, 1)


def main():
    cb.reset()
    bpy.context.scene.render.fps = FPS
    B, R, geo = build_geometry()
    to_cam, Ry = cam_xform(B)
    bones = fp_skeleton(B)
    for b in bones:
        b["head"] = to_cam(b["head"]) if b["name"] != "fp_root" else np.zeros(3)
        b["tail"] = to_cam(b["tail"]) if b["name"] != "fp_root" else np.array([0, 0.1, 0])
        b["normal"] = np.asarray(b["normal"]) @ Ry.T
    rig = FPRig(bones)
    sk = rig.sk
    names = sk.names
    Wbody = fp_weights(names, len(B.v_all))[B.mh_index]
    Wbody /= np.maximum(Wbody.sum(1, keepdims=True), 1e-9)
    ref = G.Body(B.v, B.f, Wbody)
    arm = cb.create_armature(sk, "FPArmature")
    objs = {}
    for k, m in geo.items():
        m.v = to_cam(m.v)
    # weights
    sm = geo["skin"]
    sm.W = Wbody[sm.src]
    for k in ("sleeve", "band", "screen"):
        m = geo[k]
        vb = (m.v @ Ry) + ((B.landmarks["eye.L"] + B.landmarks["eye.R"]) / 2 + np.array([0, 0, 0.01]))
        W = ref.weights_at(vb, k=6)
        if k in ("band", "screen"):
            # rigid to the forearm twist bone / hand blend
            W = np.zeros_like(W)
            W[:, sk.i("forearm_twist.L")] = 0.65
            W[:, sk.i("hand.L")] = 0.35
        m.W = W
    # Blender objects
    mats = {}
    for k, m in geo.items():
        uvs = None
        if m.loop_uv is not None:
            uvs = np.array([uv for f in m.loop_uv for uv in f], float)
        ob = cb.mesh_from_data("fp_" + k, m.v, m.f, uvs)
        if k == "skin":
            BC.pack_only(ob, 0.006)
        elif k != "screen":
            BC.smart_uv(ob, 0.006)
        objs[k] = ob
    # textures
    tmp = BC.TMP
    # skin
    ob = objs["skin"]
    co, vn, tv, tuv = BC.read_mesh(ob)
    attrs = {"kind": np.zeros(len(co)), "hand": None, "dens": np.zeros(len(co))}
    from scipy.spatial import cKDTree
    tr = cKDTree(sm.v)
    _, idx = tr.query(co)
    attrs["hand"] = sm.attrs["hand"][idx]
    for a in BC.ATTRS:
        attrs.setdefault(a, np.zeros(len(co)))
    # paint in body space (landmarks/skeleton are in body space)
    M = BC.raster_group(ob, attrs, 1024)
    eye = (B.landmarks["eye.L"] + B.landmarks["eye.R"]) / 2 + np.array([0, 0, 0.01])
    M["pos"] = M["pos"] @ Ry + eye
    M["nrm"] = M["nrm"] @ Ry
    res = MAT.paint_skin(M, B.landmarks, CFG, B.sk)
    fm = BC.finish_maps(res, M, 1024, 1024, "fp_skin")
    ao = np.ones((1024, 1024))
    pa, po = BC.save_final("fp_skin", fm["albedo_lin"], fm["rough"], fm["metal"], ao, 1024, 512)
    mats["skin"] = BC.make_material("fp_skin", pa, fm["normal"], po)
    # sleeve: dark charcoal wool
    ob = objs["sleeve"]
    co, vn, tv, tuv = BC.read_mesh(ob)
    attrs = {a: np.zeros(len(co)) for a in BC.ATTRS}
    attrs["kind"] = np.full(len(co), float(MAT.K["sleeve"]))
    M = BC.raster_group(ob, attrs, 1024)
    M["pos"] = M["pos"] @ Ry + eye
    M["nrm"] = M["nrm"] @ Ry
    p = M["pos"]
    fib = MAT.wool_fibres(p, 7)
    col = MAT.srgb((48, 48, 52))
    alb = col * (1 + 0.12 * fib[..., None] + 0.06 * MAT.fbm(p * 200, 3, seed=8)[..., None])
    h = 0.00015 * fib
    for s in "LR":
        el = np.asarray(B.sk["lowerarm01." + s]["head"])
        wr = np.asarray(B.sk["wrist." + s]["head"])
        h += MAT.fold_field(p, M["nrm"], el + (wr - el) * 0.3, wr - el, 0.02, 0.05, 0.0015, 9)
        h += MAT.fold_field(p, M["nrm"], el, wr - el, 0.016, 0.05, 0.0018, 10)
    res = dict(albedo=alb, height=h, rough=np.full(h.shape, 0.9), metal=np.zeros(h.shape))
    fm = BC.finish_maps(res, M, 1024, 512, "fp_sleeve")
    pa, po = BC.save_final("fp_sleeve", fm["albedo_lin"], fm["rough"], fm["metal"], np.ones((1024, 1024)), 1024, 512)
    mats["sleeve"] = BC.make_material("fp_sleeve", pa, fm["normal"], po, double_sided=True)
    # device band: dark anodised metal with fine brushed lines
    ob = objs["band"]
    co, vn, tv, tuv = BC.read_mesh(ob)
    attrs = {a: np.zeros(len(co)) for a in BC.ATTRS}
    attrs["kind"] = np.full(len(co), float(MAT.K["device"]))
    M = BC.raster_group(ob, attrs, 256)
    p = M["pos"]
    g = MAT.gnoise(p * np.array([3000, 60, 3000]), 3)
    alb = MAT.srgb((38, 40, 44)) * (1 + 0.1 * g[..., None])
    res = dict(albedo=alb, height=0.00002 * g, rough=0.35 + 0.08 * g, metal=np.full(g.shape, 0.85))
    fm = BC.finish_maps(res, M, 256, 256, "fp_device")
    pa, po = BC.save_final("fp_device", fm["albedo_lin"], fm["rough"], fm["metal"], np.ones((256, 256)), 256, 256)
    mats["band"] = BC.make_material("device_band", pa, fm["normal"], po)
    # screen (emissive)
    scr = screen_texture(256)
    ps = T.save_jpg(T.to_srgb8(scr), os.path.join(tmp, "fp_device_screen.jpg"), 90)
    msc = BC.make_material("device_screen", ps, None, None, rough_const=0.15)
    nt = msc.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"][0]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.0
    mats["screen"] = msc
    for k, ob in objs.items():
        ob.data.materials.append(mats[k])
        cb.set_weights_dense(ob, names, geo[k].W)
    # held paper prop (rigid on the right hand, the runtime may hide it)
    clips = make_clips(rig)
    paper = paper_prop(sk, rig, clips["fp_hold"][0])
    objs["paper"] = paper
    for name, (W, loop) in clips.items():
        Q = sk.local_from_world(W)
        F = len(Q)
        vis = np.full(F, 1.0 if name == "fp_hold" else 0.0001)
        cb.add_action(arm, name, sk, Q, None, loop=loop, loc_bone=None, scales={"prop.R": vis})
    arm.animation_data.action = None
    # join meshes into one 'fp_arms' object (multi-material), keep paper separate
    BC.select_only([objs[k] for k in ("skin", "sleeve", "band", "screen")], objs["skin"])
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = "fp_arms"
    BC.smooth_all(o)
    for ob in (o, paper):
        cb.bind(ob, arm)
    out = os.path.join(P.OUT, "fp_arms.glb")
    BC.select_only([arm, o, paper], arm)
    bpy.ops.export_scene.gltf(
        filepath=out, export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
        export_animations=True, export_animation_mode="ACTIONS", export_force_sampling=True,
        export_anim_single_armature=True, export_reset_pose_bones=True, export_skins=True,
        export_def_bones=False, export_image_format="JPEG", export_jpeg_quality=85, export_image_quality=85,
        export_influence_nb=4, export_cameras=False, export_lights=False, export_extras=False,
        export_anim_slide_to_zero=True, export_optimize_animation_size=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(P.WORK, "fp_arms.blend"))
    print("wrote", out, os.path.getsize(out), "tris", BC.ntris(o), "bones", len(names),
          {k: (len(v[0]), v[1]) for k, v in clips.items()})


def paper_prop(sk, rig, Whold):
    """Folded paper (15 x 10 cm, folded once) held between the right thumb and fingers in
    fp_hold; defined in camera space for that pose and mapped back to the rest pose so it
    is rigidly skinned to hand.R.  Hide it in the runtime except while holding."""
    hb = sk.i("hand.R")
    H, T_ = sk.fk_positions(Whold[:1], np.zeros((1, 3)))
    grip = (T_[0, sk.i("finger1-3.R")] + H[0, sk.i("finger2-3.R")]) / 2
    # paper plane facing the camera, tilted back a little, held at its lower-right corner
    xa = np.array([1.0, 0.0, 0.0])
    ya = nrm(np.array([0.0, 1.0, 0.25]))
    w, hgt = 0.15, 0.10
    V = []
    for j, vv in enumerate(np.linspace(0, 1, 3)):
        for i, uu in enumerate(np.linspace(0, 1, 5)):
            fold = 0.006 * np.sin(np.pi * uu)
            V.append(grip + xa * (-(uu * w) + 0.02) + ya * (vv * hgt - 0.015) + np.array([0, 0, fold]))
    V = np.array(V)
    Wh = Whold[0, hb]
    V = sk.head[hb] + (sk.B[hb] @ (Wh.T @ (V - H[0, hb]).T)).T
    f = []
    for j in range(2):
        for i in range(4):
            a = j * 5 + i
            f.append((a, a + 5, a + 6, a + 1))
    m = G.Mesh(V, f)
    ob = cb.mesh_from_data("fp_paper", m.v, m.f)
    BC.smart_uv(ob, 0.01)
    N = 128
    yy, xx = np.mgrid[0:N, 0:N] / N
    img = np.full((N, N, 3), 0.78) * np.array([1.0, 0.97, 0.88])
    lines = (np.mod(yy * 14, 1.0) < 0.08) * (xx > 0.1) * (xx < 0.9)
    img[lines] *= 0.6
    pth = T.save_jpg(T.to_srgb8(img), os.path.join(BC.TMP, "fp_paper.jpg"), 85)
    mat = BC.make_material("fp_paper", pth, None, None, double_sided=True, rough_const=0.85)
    ob.data.materials.append(mat)
    names = sk.names
    Wp = np.zeros((len(V), len(names)))
    Wp[:, sk.i("prop.R")] = 1
    cb.set_weights_dense(ob, names, Wp)
    return ob


if __name__ == "__main__":
    main()
