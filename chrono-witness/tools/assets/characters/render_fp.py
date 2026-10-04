"""Preview the first-person arms through the game camera (origin, looking -Z, 70 deg vFOV).
Writes docs/previews/characters/fp_arms.png"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy

import cw_blender as cb
import cw_paths as P


def main():
    cb.reset()
    sc = cb.setup_render("CYCLES", (560, 315), 16)
    cb.add_lights(0.9, world=(0.45, 0.47, 0.5))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(P.OUT, "fp_arms.glb"))
    objs = [o for o in bpy.data.objects if o not in before]
    arm = [o for o in objs if o.type == "ARMATURE"][0]
    # backdrop wall 3 m in front
    me = bpy.data.meshes.new("wall")
    me.from_pydata([(-6, 3, -4), (6, 3, -4), (6, 3, 4), (-6, 3, 4)], [], [(0, 1, 2, 3)])
    w = bpy.data.objects.new("wall", me)
    cb.link(w)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cb.link(cam)
    cam.location = (0, 0, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle = math.radians(70)
    cam.data.clip_start = 0.02
    sc.camera = cam
    # lights near the camera
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.location = (o.location.x * 0.4, -abs(o.location.y) * 0.3 - 0.5, o.location.z * 0.3)
    paths = []
    order = ["fp_idle", "fp_reach", "fp_hold", "fp_scan", "fp_grip_two", "fp_climb"]
    acts = {a.name: a for a in bpy.data.actions}
    for name in order:
        cand = [k for k in acts if k.startswith(name)]
        act = acts[cand[0]]
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action = act
        if act.slots:
            arm.animation_data.action_slot = act.slots[0]
        a, b = act.frame_range
        for frac in ((0.0, 0.5) if name not in ("fp_reach", "fp_climb") else (0.45, 0.25, 0.75)[:2]):
            f = int(a + (b - a) * frac)
            sc.frame_set(f)
            p = os.path.join(P.WORK, "_fp_%s_%d.png" % (name, f))
            cb.render(p)
            paths.append(p)
    cb.contact_sheet(paths, os.path.join(P.PREVIEWS, "fp_arms.png"), cols=4,
                     label="fp_arms: " + ", ".join(order) + " (2 frames each, 70 deg vFOV camera)")


if __name__ == "__main__":
    main()
