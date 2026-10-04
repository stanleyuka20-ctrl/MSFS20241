# Character pipeline (CHRONO WITNESS)

Reproducible scripts that build every file in `public/assets/characters/` from CC0 MakeHuman data and
CMU motion capture. Output contract: `docs/ASSET_CONTRACT.md`. Third-party credits:
`ATTRIBUTION_FRAGMENT.md` (to be merged into `ASSETS.md`).

## Requirements

- Python 3.11 with `bpy==5.0.1` (Blender as a module), `numpy<2` (bpy 5.0.1 wheels are built against
  NumPy 1.x), `scipy`, `pillow`:
  `python -m venv venv && venv/bin/pip install bpy==5.0.1 "numpy<2" scipy pillow`
- `git`, `unzip`, network access to github.com.
- Optional, only for the Workbench animation contact sheets (`preview_anim.py`):
  `apt-get install libegl1 libegl-mesa0` (Cycles previews/bakes need nothing extra).
- About 45 min of CPU on 4 cores for a full build (AO bakes dominate); set `CW_FAST=1` to skip the AO
  bakes while iterating.

## Run end to end

```bash
cd tools/assets/characters
export CW_WORK=~/.cache/chrono-witness/characters   # inputs + caches (default shown); not committed
./fetch_inputs.sh                       # MakeHuman CC0 data (sparse git) + 8 CMU BVH takes
PY=/path/to/venv/bin/python
$PY anim_clips.py                       # retarget + clean all humanoid clips -> $CW_WORK/cache/clips/*.npz
$PY build_anims.py                      # -> anims_humanoid.glb + anims_humanoid.json
$PY build_character.py                  # -> soldier_a/b/c, officer, medic, wounded, archivist .glb
$PY build_fp_arms.py                    # -> fp_arms.glb
$PY verify_glb.py                       # checks names/rest pose/budgets/scale/facing/NaNs/textures
$PY make_readme.py                      # -> public/assets/characters/README.md
$PY render_previews.py soldier_a soldier_b soldier_c officer medic wounded archivist \
      --clips walk,crouch_cover,sit_ground     # -> docs/previews/characters/<id>.png, <id>_face.png
$PY render_fp.py                        # -> docs/previews/characters/fp_arms.png
$PY preview_anim.py walk run ...        # quick Workbench contact sheets of cached clips (debug)
```
Single characters: `$PY build_character.py officer medic`. Output dirs can be redirected with
`CW_OUT` / `CW_PREVIEWS`; input locations with `CW_MH_DATA` / `CW_CMU_BVH`.

## How it works

| Script | Role |
|---|---|
| `cw_paths.py` | Paths / env overrides. |
| `mhcore.py` | Loads `base.obj` (body group only), applies MakeHuman macro targets (gender/age/muscle/weight/height/proportions with MakeHuman's interpolation) + face targets, computes joints as means of the joint-helper vertices, builds the reduced 63-bone skeleton and merges dropped bones' skin weights into kept ancestors. A **canonical** body defines the shared skeleton; every character body is warped onto it with a skin-weighted joint-offset LBS so rest poses are identical across files. Also fits MakeHuman `.mhclo` proxies (eyes). |
| `cw_anim.py` | BVH parser/FK, retargeting (per-bone frame alignment from the CMU T-pose using bone direction + measured knee/elbow flexion axes; twist split onto the MakeHuman twist bones), loop search & closure, in-place conversion, ground-speed measurement from stance feet, 2-bone IK, finger poses, breathing layer. |
| `anim_clips.py` | Clip recipes: mocap selection windows, loop cutting, foot locking (heel then toe-roll pinning with IK), foot-pitch/toe-ground fixes, arm clearance for webbing, hand-keyed clips (lie_supine, kneel_work, crouch_cover, point arm, stretcher arms) with eased timing, overlapping action and breathing/micro-noise. |
| `build_anims.py` | Writes the skeleton + all actions to `anims_humanoid.glb` (30 fps, sampled) and the json. |
| `cw_garment.py` | Garment geometry: body-region shells offset along normals and relaxed by a Laplacian smoother under a KD-tree "stay outside the skin" constraint; hem extrusion through convex-hull slices (tunic skirt); hem/cuff lips for cloth thickness; lofts (puttees, gaiters, bands); weight transfer from the body. |
| `cw_character.py` | Uniform/gear builders: SD tunic (stand-and-fall collar or open collar with shirt & tie), trousers/breeches, puttees, ankle boots (two convex-hull lofts with welted sole), 1908 webbing (belt, crossed braces, pouch sets, water bottle, entrenching-tool carrier, bayonet scabbard), Sam Browne + holster, Brodie Mk I helmet (revolved profile, rolled rim, liner, chin strap) fitted over the head, service cap, cap comforter, haversack, SB armband, bandages, hair cap. |
| `cw_tex.py`, `cw_materials.py` | Procedural texturing: triangles are rasterised into the UV atlas to get the rest-pose 3D position/normal/attributes of every texel; colour, height, roughness and metalness are evaluated as 3D fields (gradient/cellular noise, landmark distances, garment details such as pockets, buttons, seams, puttee spirals, folds at elbows/knees, mud by height, chipped helmet paint, skin melanin/haemoglobin variation, pores, wrinkles, stubble, brows, nails...), height is converted to tangent-space normals with the true texel size, islands are dilated. |
| `build_character.py` | Assembles a character: parts -> per-part collapse decimation to the LOD budgets (face kept denser than hands; low-poly lofts/straps protected) -> join per material -> Smart-UV / MakeHuman-UV atlases -> painted textures -> Cycles AO bake -> LOD1 (per-part decimation of LOD0, same UVs) -> skin weights -> glTF export (JPEG textures). |
| `build_fp_arms.py` | First-person arms in camera space, own 40-bone rig (upper-arm stubs, forearm + twist, hand, 5x3 fingers, paper prop bone), IK-driven fp_* clips. |
| `characters_cfg.py` | Per-character body/face/skin/clothing parameters. |
| `verify_glb.py`, `render_previews.py`, `render_fp.py`, `preview_anim.py`, `make_readme.py` | Verification and documentation. |
