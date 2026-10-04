"""Export the shared humanoid skeleton + all clips to anims_humanoid.glb / .json.
Run after anim_clips.py:   python build_anims.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import numpy as np

import cw_anim as ca
import cw_blender as cb
import cw_paths as P

CLIPS = ["idle", "idle_alt", "walk", "run", "talk", "sit_ground", "lie_supine", "kneel_work",
         "carry_walk", "limp_walk", "point", "crouch_cover",
         # London 1940 additions
         "lie_sleep", "sit_huddle", "dig", "carry_box", "kneel_listen", "wave", "talk_worried"]

NOTES = {
    "lie_supine": "body lies on its back on the ground plane (back at y~0), head towards -Z, feet towards +Z; "
                  "offset the root to put it on a stretcher",
    "sit_ground": "pelvis on the ground at the origin, back towards -Z (place the origin ~0.25 m in front of a wall)",
    "kneel_work": "kneeling on the right knee, hands working ~0.45 m in front of the origin at ground level",
    "carry_walk": "rear stretcher bearer: hands hold handles ~0.3 m in front of the hips, ~0.95 m above ground",
    "point": "one-shot: points forward-right with the right index finger (~0.7-1.9 s hold)",
    "crouch_cover": "deep squat, head tucked, both hands on top of the helmet, breathing/trembling loop",
    "lie_sleep": "asleep on the LEFT side on the ground plane, head towards -Z, face towards +X, knees drawn up, "
                 "head pillowed on the left forearm; the body extends ~0.75 m along -Z and +-0.4 m in X from the origin",
    "sit_huddle": "pelvis on the ground ~0.18 m behind the origin, knees drawn up, arms wrapped round the shins, "
                  "head bowed, slow rocking",
    "dig": "standing shovelling cycle (thrust, lever, lift, toss to the character's right); hands grip an implied "
           "shovel handle (no prop), blade point ~0.55 m in front of the origin",
    "carry_box": "walk carrying a box (~0.35 m wide) at chest height, hands on its sides ~0.31 m in front of the hips",
    "kneel_listen": "kneeling on the right knee, head bowed and turned (right ear down), right hand cupped to the "
                    "ear, left hand on the rubble ~0.45 m in front",
    "wave": "one-shot: raises the right arm and waves (~1.8 Hz) between ~0.75 s and ~2.8 s, starts/ends in the idle pose",
    "talk_worried": "anxious conversation: hands wringing in front of the stomach, one open-palm gesture per loop, "
                    "shoulders raised, quick breathing, procedural jaw",
}


def export_glb(path, objs, anim=True):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_yup=True,
        export_apply=False, export_animations=anim, export_animation_mode="ACTIONS",
        export_force_sampling=True, export_frame_step=1, export_anim_single_armature=True,
        export_reset_pose_bones=True, export_def_bones=False, export_skins=True,
        export_morph=False, export_extras=False, export_cameras=False, export_lights=False,
        export_optimize_animation_size=True, export_anim_slide_to_zero=True,
    )


def main():
    cb.reset()
    sc = bpy.context.scene
    sc.render.fps = 30
    sk = ca.skeleton()
    arm = cb.create_armature(sk, "Armature")
    meta = {}
    first = None
    for name in CLIPS:
        d = np.load(os.path.join(P.CACHE, "clips", name + ".npz"), allow_pickle=True)
        loop = bool(d["loop"])
        act = cb.add_action(arm, name, sk, d["Q"], d["hips_loc"], loop=loop)
        first = first or act
        F = d["Q"].shape[0]
        dur = (F if loop else F - 1) / 30.0
        meta[name] = {"duration": round(dur, 4), "loop": loop, "speed": round(float(d["speed"]), 3),
                      "source": str(d["source"])}
        if name in NOTES:
            meta[name]["notes"] = NOTES[name]
    cb.assign_action(arm, first)
    # rest pose for export
    arm.animation_data.action = None
    out = os.path.join(P.OUT, "anims_humanoid.glb")
    export_glb(out, [arm])
    with open(os.path.join(P.OUT, "anims_humanoid.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("wrote", out, os.path.getsize(out))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
