"""Render animation contact sheets (Workbench) of clips cached by anim_clips.py on the
skinned canonical body.  Usage:  python preview_anim.py clip1 clip2 ...  [--frames N]
[--views front,side] [--out DIR] [--world]   (--world moves the body at the clip speed so
foot sliding is visible)."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np

import cw_anim as ca
import cw_blender as cb
import cw_paths as P
import mhcore as mh


def build_body(sk):
    v, _ = mh.canonical()
    base = mh.load_base()
    fi = base["groups"]["body"]
    faces = [base["faces"][i] for i in fi]
    used = np.unique(np.concatenate([np.array(f) for f in faces]))
    remap = -np.ones(len(v), int)
    remap[used] = np.arange(len(used))
    faces = [tuple(remap[list(f)]) for f in faces]
    ob = cb.mesh_from_data("body", v[used], faces)
    W = mh.reduced_weights(len(v))[used]
    cb.set_weights_dense(ob, sk.names, W)
    return ob


def load_clip(name):
    d = np.load(os.path.join(P.CACHE, "clips", name + ".npz"), allow_pickle=True)
    return {k: d[k] for k in d.files}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--views", default="front,side")
    ap.add_argument("--out", default=os.path.join(P.WORK, "anim_previews"))
    ap.add_argument("--world", action="store_true")
    ap.add_argument("--res", default="260x420")
    a = ap.parse_args([x for x in sys.argv[1:] if x != "--"])
    os.makedirs(a.out, exist_ok=True)
    cb.reset()
    sk = ca.skeleton()
    arm = cb.create_armature(sk)
    body = build_body(sk)
    cb.bind(body, arm)
    sc = cb.setup_render("BLENDER_WORKBENCH", tuple(int(x) for x in a.res.split("x")))
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.75, 0.72, 0.68)
    sc.display.shading.show_shadows = True
    sc.display.shading.show_cavity = True
    gnd = cb.add_ground(30)
    cam = cb.add_camera((0, -4, 1), (0, 0, 0.9), lens=40)
    for name in a.clips:
        c = load_clip(name)
        Q = c["Q"]
        F = len(Q)
        act = cb.add_action(arm, name, sk, Q, c["hips_loc"], loop=bool(c["loop"]))
        cb.assign_action(arm, act)
        speed = float(c["speed"])
        dt = float(c["dt"])
        paths = []
        for view in a.views.split(","):
            for k in range(a.frames):
                f = int(round(k * F / a.frames)) + 1
                sc.frame_set(f)
                off = speed * (f - 1) * dt if a.world else 0.0
                arm.location = (0, -off, 0)  # glTF +Z == Blender -Y
                hz = c["hips_world"][f - 1] if "hips_world" in c else np.array([0, 0.9, 0])
                tgt = np.array([hz[0], -hz[2] - off, max(0.5, hz[1] * 0.85)])
                if view == "front":
                    cb.look_at(cam, tgt + np.array([0, -3.6, 0.25]), tgt)
                elif view == "side":
                    cb.look_at(cam, tgt + np.array([3.6, 0, 0.25]), tgt)
                elif view == "top":
                    cb.look_at(cam, tgt + np.array([0.01, -0.5, 4.0]), tgt)
                elif view == "back":
                    cb.look_at(cam, tgt + np.array([0, 3.6, 0.25]), tgt)
                p = os.path.join(a.out, "_%s_%s_%02d.png" % (name, view, k))
                cb.render(p)
                paths.append(p)
        cb.contact_sheet(paths, os.path.join(a.out, name + ".png"), cols=a.frames,
                         label="%s  F=%d dt=%.3f speed=%.2f" % (name, F, dt, speed))
        arm.location = (0, 0, 0)


if __name__ == "__main__":
    main()
