"""Blender helpers shared by the character pipeline scripts (requires bpy)."""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

A = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)  # glTF (Y up) -> Blender (Z up)


def g2b(p):
    """glTF-space points (...,3) -> Blender space."""
    return np.asarray(p) @ A.T


def b2g(p):
    return np.asarray(p) @ A


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def create_armature(sk, name="Armature"):
    """Build an armature whose bone frames equal A @ sk.B (verified)."""
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for i, n in enumerate(sk.names):
        eb = arm.edit_bones.new(n)
        eb.head = Vector(g2b(sk.head[i]))
        eb.tail = Vector(g2b(sk.tail[i]))
        z = A @ sk.B[i][:, 2]
        eb.align_roll(Vector(z))
        eb.use_deform = n != "root"
        ebs[n] = eb
    for i, n in enumerate(sk.names):
        p = sk.parent[i]
        if p >= 0:
            ebs[n].parent = ebs[sk.names[p]]
            ebs[n].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    # verify
    err = 0
    for i, n in enumerate(sk.names):
        M = np.array(arm.bones[n].matrix_local.to_3x3())
        err = max(err, np.abs(M - A @ sk.B[i]).max())
    if err > 1e-4:
        raise RuntimeError("bone frame mismatch %g" % err)
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return ob


def mat_to_quat_wxyz(Q):
    """(F,3,3) -> (F,4) w,x,y,z with sign continuity."""
    from scipy.spatial.transform import Rotation as R
    q = R.from_matrix(Q).as_quat()  # x,y,z,w
    q = q[:, [3, 0, 1, 2]]
    for f in range(1, len(q)):
        if np.dot(q[f], q[f - 1]) < 0:
            q[f] = -q[f]
    return q


def add_action(arm_ob, name, sk, Q, hips_loc, fps=30, loop=True, loc_bone="hips", scales=None):
    """Q (F,n,3,3) local pose rotations, hips_loc (F,3) pose-bone location (bone local)."""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm_ob.animation_data is None:
        arm_ob.animation_data_create()
    arm_ob.animation_data.action = act
    F = Q.shape[0]
    frames = np.arange(F, dtype=float) + 1
    if loop:
        # duplicate first key at the end so the loop closes exactly in the glTF sampler
        Q = np.concatenate([Q, Q[:1]], 0)
        if hips_loc is not None:
            hips_loc = np.concatenate([hips_loc, hips_loc[:1]], 0)
        frames = np.arange(F + 1, dtype=float) + 1
    for i, n in enumerate(sk.names):
        if sk.parent[i] < 0:
            continue
        q = mat_to_quat_wxyz(Q[:, i])
        dp = 'pose.bones["%s"].rotation_quaternion' % n
        for k in range(4):
            fc = act.fcurve_ensure_for_datablock(arm_ob, dp, index=k, group_name=n)
            fc.keyframe_points.add(len(frames))
            co = np.stack([frames, q[:, k]], 1).ravel()
            fc.keyframe_points.foreach_set("co", co)
            fc.keyframe_points.foreach_set("interpolation", [2] * len(frames))  # LINEAR
            fc.update()
        if n == loc_bone and hips_loc is not None:
            dp = 'pose.bones["%s"].location' % n
            for k in range(3):
                fc = act.fcurve_ensure_for_datablock(arm_ob, dp, index=k, group_name=n)
                fc.keyframe_points.add(len(frames))
                co = np.stack([frames, hips_loc[:, k]], 1).ravel()
                fc.keyframe_points.foreach_set("co", co)
                fc.keyframe_points.foreach_set("interpolation", [2] * len(frames))
                fc.update()
    for bn, sc_ in (scales or {}).items():
        sc_ = np.asarray(sc_, float)
        if loop:
            sc_ = np.concatenate([sc_, sc_[:1]])
        dp = 'pose.bones["%s"].scale' % bn
        for k in range(3):
            fc = act.fcurve_ensure_for_datablock(arm_ob, dp, index=k, group_name=bn)
            fc.keyframe_points.add(len(frames))
            fc.keyframe_points.foreach_set("co", np.stack([frames, sc_], 1).ravel())
            fc.keyframe_points.foreach_set("interpolation", [0] * len(frames))  # CONSTANT
            fc.update()
    act.frame_range = (1, len(frames))
    act.use_frame_range = True
    return act


def assign_action(arm_ob, act):
    if arm_ob.animation_data is None:
        arm_ob.animation_data_create()
    arm_ob.animation_data.action = act
    if act.slots:
        arm_ob.animation_data.action_slot = act.slots[0]
    sc = bpy.context.scene
    sc.frame_start = int(act.frame_range[0])
    sc.frame_end = int(act.frame_range[1])


def mesh_from_data(name, verts_g, faces, uvs_per_loop=None, smooth=True):
    """verts in glTF space; faces list of tuples; uvs_per_loop (L,2) in loop order."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(g2b(verts_g).tolist(), [], [tuple(f) for f in faces])
    if uvs_per_loop is not None:
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", np.asarray(uvs_per_loop, float).ravel())
    me.polygons.foreach_set("use_smooth", [smooth] * len(me.polygons))
    me.update()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    return ob


def set_weights(ob, names, idx, w):
    """idx/w (N,k) influences per vertex."""
    groups = {}
    for i, n in enumerate(names):
        groups[i] = ob.vertex_groups.new(name=n) if n not in ob.vertex_groups else ob.vertex_groups[n]
    N, K = idx.shape
    for k in range(K):
        for bi in np.unique(idx[:, k]):
            sel = np.where((idx[:, k] == bi) & (w[:, k] > 1e-5))[0]
            if len(sel) == 0:
                continue
            g = groups[int(bi)]
            # group by identical weights is overkill; add individually
            for v, ww in zip(sel.tolist(), w[sel, k].tolist()):
                g.add([v], ww, "REPLACE")


def set_weights_dense(ob, names, Wd, max_infl=4, eps=1e-4):
    order = np.argsort(-Wd, axis=1)[:, :max_infl]
    w = np.take_along_axis(Wd, order, axis=1)
    w[w < eps] = 0
    s = w.sum(1, keepdims=True)
    s[s == 0] = 1
    w = w / s
    set_weights(ob, names, order, w)


def bind(ob, arm_ob):
    ob.parent = arm_ob
    m = ob.modifiers.new("Armature", "ARMATURE")
    m.object = arm_ob
    return m


def setup_render(engine="CYCLES", res=(640, 900), samples=24):
    sc = bpy.context.scene
    sc.render.engine = engine
    if engine == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.device = "CPU"
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast" if engine != "BLENDER_WORKBENCH" else "None"
    return sc


def add_camera(loc, target, lens=50, name="cam"):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    link(cam)
    cam.data.lens = lens
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def look_at(cam, loc, target):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def add_lights(strength=1.0, world=(0.42, 0.45, 0.5)):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (*world, 1)
    bg.inputs[1].default_value = 0.35 * strength
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
    key.data.energy = 380 * strength
    key.data.size = 2.5
    link(key)
    key.location = (2.2, -3.0, 3.2)
    key.rotation_euler = (Vector((0, 0, 1.2)) - key.location).to_track_quat("-Z", "Y").to_euler()
    fill = bpy.data.objects.new("fill", bpy.data.lights.new("fill", "AREA"))
    fill.data.energy = 110 * strength
    fill.data.size = 3
    link(fill)
    fill.location = (-3.0, -2.0, 1.8)
    fill.rotation_euler = (Vector((0, 0, 1.1)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    rim = bpy.data.objects.new("rim", bpy.data.lights.new("rim", "AREA"))
    rim.data.energy = 220 * strength
    rim.data.size = 1.5
    link(rim)
    rim.location = (0.5, 3.0, 2.8)
    rim.rotation_euler = (Vector((0, 0, 1.3)) - rim.location).to_track_quat("-Z", "Y").to_euler()
    return key, fill, rim


def add_ground(size=8, color=(0.25, 0.22, 0.18)):
    me = bpy.data.meshes.new("ground")
    s = size / 2
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("ground", me)
    link(ob)
    mat = bpy.data.materials.new("ground")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    return ob


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def contact_sheet(paths, out, cols=None, label=None):
    from PIL import Image, ImageDraw
    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    cols = cols or len(ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows + (24 if label else 0)), (30, 30, 30))
    for i, im in enumerate(ims):
        sheet.paste(im.convert("RGB"), ((i % cols) * w, (i // cols) * h + (24 if label else 0)))
    if label:
        d = ImageDraw.Draw(sheet)
        d.text((8, 5), label, fill=(240, 240, 240))
    sheet.save(out)
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass
    return out
