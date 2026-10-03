# Asset contract (runtime ⇄ offline pipeline)

All runtime assets live under `public/assets/` and are produced by reproducible scripts in
`tools/assets/`. Every third-party input must be legally usable (CC0 / public domain / own work)
and be listed in `ASSETS.md` (attribution list) with source URL, licence and what was derived.

Units: metres. Up axis: +Y (glTF). Characters face +Z, feet at y = 0.

## Characters — `public/assets/characters/`

| File | Content |
|---|---|
| `anims_humanoid.glb` | The shared skeleton + all humanoid animation clips (no visible mesh needed). |
| `anims_humanoid.json` | Clip metadata: `{ "<clip>": { "duration": s, "loop": bool, "speed": m/s or 0 } }` |
| `<characterId>.glb` | Skinned meshes (LOD0 + `_LOD1` suffixed meshes) bound to the identical skeleton (same bone names, same rest pose). |
| `fp_arms.glb` | First-person forearms + hands (own small rig) with `fp_*` clips. |

Bone names must be identical across every character file and `anims_humanoid.glb`, so a
`THREE.AnimationMixer` can play shared clips on any character by node name. Root bone stays at
the origin (in-place animation); locomotion clips declare their ground speed in the json so
the runtime scales playback rate to the actual velocity (no foot sliding).

Required clips: `idle`, `idle_alt`, `walk` (~1.4 m/s), `run` (~3.6 m/s), `talk` (gesturing idle),
`sit_ground` (seated against a wall, loop), `lie_supine` (lying on a stretcher, breathing loop),
`kneel_work` (kneeling, hands working at ground level), `carry_walk` (walking while holding
stretcher handles low in front), `limp_walk` (~0.8 m/s), `point` (one-shot), `crouch_cover`
(crouched, head down, hands over helmet — for bombardment).

Budget: LOD0 ≤ 22k triangles per character incl. clothing, LOD1 ≤ 7k. ≤ 64 bones.
Textures embedded JPEG, ≤ 1024² (skin, clothing), ≤ 512² (small items). PBR metal/rough.

## Textures — `public/assets/textures/<set>/`

`<set>_albedo.jpg` (sRGB), `<set>_normal.jpg` (OpenGL, +Y), `<set>_orm.jpg` (R = AO, G = roughness,
B = metalness, linear). 1024², seamlessly tileable unless noted. `public/assets/textures/manifest.json`
lists each set: `{ "<set>": { "tileMetres": number, "notes": string, "source": "procedural (own work)" } }`.

## Props — `public/assets/props/`

Optional GLB props (static, PBR, ≤ 5k tris unless hero). Runtime procedurally builds most
chapter geometry; GLB props are used where hand modelling clearly beats procedural code.
