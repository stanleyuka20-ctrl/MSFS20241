"""Render preview sheets of the exported character GLBs (imports the GLB and the shared
anims_humanoid.glb, so it checks exactly what the runtime receives).

    python render_previews.py soldier_a [--clips walk,idle,crouch_cover] [--engine CYCLES]
Writes docs/previews/characters/<id>.png (rest + clips, front & side) and <id>_face.png.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np
from mathutils import Vector

import cw_blender as cb
import cw_paths as P


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def setup(engine, res, samples):
    sc = cb.setup_render(engine, res, samples)
    if engine == "CYCLES":
        sc.cycles.max_bounces = 4
        sc.cycles.diffuse_bounces = 2
        sc.cycles.glossy_bounces = 2
        sc.cycles.transparent_max_bounces = 2
    cb.add_lights(1.0, world=(0.5, 0.52, 0.56))
    g = cb.add_ground(30, (0.32, 0.29, 0.25))
    return sc


def frame_of(act, t_frac):
    a, b = act.frame_range
    return a + (b - a) * t_frac


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--clips", default="walk,idle_alt,crouch_cover")
    ap.add_argument("--engine", default="CYCLES")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--res", default="420x620")
    ap.add_argument("--lod", default="0")
    a = ap.parse_args([x for x in sys.argv[1:] if x != "--"])
    res = tuple(int(x) for x in a.res.split("x"))
    for cid in a.ids:
        cb.reset()
        sc = setup(a.engine, res, a.samples)
        sc.render.fps = 30
        objs = import_glb(os.path.join(P.OUT, cid + ".glb"))
        arm = [o for o in objs if o.type == "ARMATURE"][0]
        meshes = [o for o in objs if o.type == "MESH"]
        for o in meshes:
            show = (o.name.endswith("_LOD1") == (a.lod == "1")) and o.name not in ("cap", "bundle")
            o.hide_render = not show
        anim_objs = import_glb(os.path.join(P.OUT, "anims_humanoid.glb"))
        acts = {act.name: act for act in bpy.data.actions}
        for o in anim_objs:
            o.hide_render = True
            if o.animation_data:
                o.animation_data.action = None
        cam = cb.add_camera((0, -4, 1), (0, 0, 0.9), lens=50)
        paths = []
        views = [("front", (0, -1, 0)), ("side", (1, 0, 0))]
        clips = ["rest"] + [c for c in a.clips.split(",") if c]
        for clip in clips:
            if arm.animation_data is None:
                arm.animation_data_create()
            if clip == "rest":
                arm.animation_data.action = None
                for pb in arm.pose.bones:
                    pb.rotation_quaternion = (1, 0, 0, 0)
                    pb.location = (0, 0, 0)
                f = 1
            else:
                cand = [k for k in acts if k == clip or k.startswith(clip + "_") or k.split("_Armature")[0] == clip]
                act = acts[cand[0]]
                arm.animation_data.action = act
                if act.slots:
                    arm.animation_data.action_slot = act.slots[0]
                f = int(frame_of(act, 0.3))
            sc.frame_set(f)
            bpy.context.view_layer.update()
            # frame the character
            dg = bpy.context.evaluated_depsgraph_get()
            pts = []
            for o in meshes:
                if o.hide_render:
                    continue
                oe = o.evaluated_get(dg)
                me = oe.to_mesh()
                co = np.zeros(len(me.vertices) * 3)
                me.vertices.foreach_get("co", co)
                co = co.reshape(-1, 3) @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
                pts.append(co[::7])
                oe.to_mesh_clear()
            pts = np.concatenate(pts)
            lo, hi = pts.min(0), pts.max(0)
            ctr = (lo + hi) / 2
            size = max(hi[2] - lo[2], (hi[0] - lo[0]) * 0.75, (hi[1] - lo[1]) * 0.75)
            for vn, d in views:
                dist = size * 1.5 + 0.5
                loc = ctr + np.array(d) * dist + np.array([0, 0, size * 0.08])
                loc[2] = max(loc[2], 0.85)
                cb.look_at(cam, loc, ctr)
                p = os.path.join(P.WORK, "_prev_%s_%s_%s.png" % (cid, clip, vn))
                cb.render(p)
                paths.append(p)
        cb.contact_sheet(paths, os.path.join(P.PREVIEWS, "%s%s.png" % (cid, "_lod1" if a.lod == "1" else "")),
                         cols=len(views) * 2, label="%s   (rest + %s)  LOD%s" % (cid, ", ".join(clips[1:]), a.lod))
        # face close-up (rest pose)
        if a.lod == "0":
            arm.animation_data.action = None
            for pb in arm.pose.bones:
                pb.rotation_quaternion = (1, 0, 0, 0)
                pb.location = (0, 0, 0)
            sc.frame_set(1)
            sc.render.resolution_x, sc.render.resolution_y = 700, 700
            cam.data.lens = 85
            paths = []
            ks = arm.scale[0]  # smaller characters carry a uniform armature scale
            for d, tgt, dd in (((0.0, -1, 0.05), (0, 0.05, 1.63), 1.05), ((0.75, -0.66, 0.05), (0, 0.05, 1.63), 1.05),
                               ((1, 0.15, 0.0), (0, 0.05, 1.63), 1.05), ((0.25, -1, 0.1), (0, 0, 1.2), 2.2)):
                tgt = np.array(tgt) * ks
                cb.look_at(cam, tgt + np.array(d) * dd * ks, tgt)
                p = os.path.join(P.WORK, "_face_%s_%d.png" % (cid, len(paths)))
                cb.render(p)
                paths.append(p)
            cb.contact_sheet(paths, os.path.join(P.PREVIEWS, cid + "_face.png"), cols=4, label=cid + " face / torso")
        print("previews written for", cid)


if __name__ == "__main__":
    main()
