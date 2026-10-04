"""Render lit 2x2-tiled previews of texture sets with Blender (bpy module, Cycles CPU).

Usage: python preview_blender.py <textures_root> <out_dir> set1 [set2 ...]
Output: <out_dir>/<set>.png  (768x384: left = oblique view, right = top-down view with raking sun)
"""
import math
import os
import sys

import bpy
from PIL import Image

RES = 384


def build_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "PNG"

    # world: overcast-ish gradient sky (bright zenith/horizon, dark ground) for reflections
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rampn = nt.nodes.new("ShaderNodeValToRGB")
    rampn.color_ramp.elements[0].position = 0.45
    rampn.color_ramp.elements[0].color = (0.05, 0.045, 0.04, 1)
    rampn.color_ramp.elements[1].position = 0.55
    rampn.color_ramp.elements[1].color = (0.75, 0.80, 0.88, 1)
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs[1].default_value = -1
    mapr.inputs[2].default_value = 1
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    # Use "Generated" for world = view direction
    nt.links.new(sep.outputs[2], mapr.inputs[0])
    nt.links.new(mapr.outputs[0], rampn.inputs[0])
    nt.links.new(rampn.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.9
    nt.links.new(bg.outputs[0], out.inputs[0])

    sun_d = bpy.data.lights.new("Sun", "SUN")
    sun_d.energy = 2.6
    sun_d.angle = math.radians(3)
    sun_d.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("Sun", sun_d)
    sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(62), 0, math.radians(35))

    bpy.ops.mesh.primitive_plane_add(size=2.0)
    plane = bpy.context.active_object
    for p in plane.data.uv_layers.active.data:
        pass

    mat = bpy.data.materials.new("M")
    mat.use_nodes = True
    plane.data.materials.append(mat)
    nt = mat.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (2, 2, 1)
    nt.links.new(tc.outputs["UV"], mp.inputs[0])
    ia = nt.nodes.new("ShaderNodeTexImage"); ia.name = "alb"
    inn = nt.nodes.new("ShaderNodeTexImage"); inn.name = "nrm"
    io = nt.nodes.new("ShaderNodeTexImage"); io.name = "orm"
    for t in (ia, inn, io):
        nt.links.new(mp.outputs[0], t.inputs[0])
        t.interpolation = "Cubic"
    sepc = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(io.outputs[0], sepc.inputs[0])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs[0].default_value = 1.0
    nt.links.new(ia.outputs[0], mul.inputs[6])
    nt.links.new(sepc.outputs[0], mul.inputs[7])
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    nt.links.new(sepc.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sepc.outputs[2], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(inn.outputs[0], nm.inputs[1])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], o.inputs[0])

    cam_o_d = bpy.data.cameras.new("CamO")
    cam_o_d.lens = 45
    cam_o = bpy.data.objects.new("CamO", cam_o_d)
    sc.collection.objects.link(cam_o)
    cam_o.location = (0, -1.3, 0.9)
    cam_o.rotation_euler = (math.radians(46), 0, 0)

    cam_t_d = bpy.data.cameras.new("CamT")
    cam_t_d.type = "ORTHO"
    cam_t_d.ortho_scale = 2.0
    cam_t = bpy.data.objects.new("CamT", cam_t_d)
    sc.collection.objects.link(cam_t)
    cam_t.location = (0, 0, 3)
    return sc, mat, cam_o, cam_t, sun


def main():
    root, out_dir = sys.argv[1], sys.argv[2]
    sets = sys.argv[3:]
    sc, mat, cam_o, cam_t, sun = build_scene()
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    nt = mat.node_tree
    for s in sets:
        d = os.path.join(root, s)
        imgs = {}
        for key, suffix, cs in (("alb", "albedo", "sRGB"), ("nrm", "normal", "Non-Color"), ("orm", "orm", "Non-Color")):
            img = bpy.data.images.load(os.path.join(d, f"{s}_{suffix}.jpg"), check_existing=False)
            img.colorspace_settings.name = cs
            nt.nodes[key].image = img
            imgs[key] = img
        views = []
        for cam, sun_rot in ((cam_o, (62, 0, 35)), (cam_t, (68, 0, 120))):
            sc.camera = cam
            sun.rotation_euler = tuple(math.radians(a) for a in sun_rot)
            p = os.path.join(tmp, f"{s}_{cam.name}.png")
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            views.append(Image.open(p).convert("RGB"))
        comp = Image.new("RGB", (RES * 2, RES))
        comp.paste(views[0], (0, 0))
        comp.paste(views[1], (RES, 0))
        comp = comp.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
        comp.save(os.path.join(out_dir, f"{s}.png"), optimize=True)  # palette PNG keeps the repo small
        for img in imgs.values():
            bpy.data.images.remove(img)
        print("preview", s, flush=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)


if __name__ == "__main__":
    main()
