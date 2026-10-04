# Environment texture generator

Reproducible, fully procedural (own work, no third-party images) generator for every
environment/prop PBR set and effect texture in `public/assets/textures/`. The output format
follows `docs/ASSET_CONTRACT.md`.

## Run

```bash
PY=/path/to/venv/bin/python        # needs numpy, pillow, scipy, opencv-python-headless; bpy for previews
$PY tools/assets/textures/generate_all.py                  # all PBR sets + fx + manifest (~4 min, 4 cores)
$PY tools/assets/textures/generate_all.py --only mud_wet,sandbag
$PY tools/assets/textures/generate_all.py --fx-only
$PY tools/assets/textures/generate_all.py --only brick_french --check --preview
$PY tools/assets/textures/fx.py rain_ripples               # one fx generator
```

* `--check` prints tile-edge vs interior gradient ratios (seam test). Sets with boards, bricks or tiles
  have a real joint on the tile edge, so a high ratio along that axis is expected there.
* `--preview` renders `docs/previews/textures/<set>.png` with Blender/Cycles (768x384: left = oblique view,
  right = top-down with a raking sun; both show 2x2 tiles).
* All randomness is seeded from the set name (`lib/core.rng_for`), so the output is deterministic for a
  given numpy/scipy/opencv version.

## Output

`public/assets/textures/<set>/<set>_albedo.jpg` (sRGB), `_normal.jpg` (OpenGL, +Y = green up),
`_orm.jpg` (R = AO, G = roughness, B = metalness, linear). 1024², JPEG q88 (albedo 4:2:0, normal/ORM 4:4:4).
`manifest.json` lists `tileMetres`, `notes` (orientation details) and `source` for every set.
Albedo is clamped to 0.012–0.88 linear.

Orientation conventions (see manifest notes): wood grain runs along U; wall materials (earth_wall,
plaster_damaged, wood_planks, roof_tiles, render_stucco, interior_wallpaper, slate_roof) treat V as "up" so
drips, stains and roof slope run towards the bottom of the image; corrugated_iron ridges run along V.
Cross-section sets are meant to be mapped once across their width: pavement_flags (kerb side at V=0) and
concrete_platform (platform edge at V=0, painted strip at V≈0.1). `london_stock_brick_band` is the same wall
as `london_stock_brick` with one red accent course, for a single band row on a facade.

## How it works

Everything is built from periodic primitives, so seamless tiling holds by construction:

| Module | Contents |
|---|---|
| `lib/core.py` | FFT spectral noise (1/f^β, band-pass, anisotropic), periodic Perlin/fBm, periodic Voronoi (`cKDTree(boxsize)`), FFT Gaussian blur, wrapped warps and stamps, colour ramps in linear space |
| `lib/elements.py` | boot-print generator (1914 ammunition boot, hobnails, heel iron), stone scatter, packed Voronoi "chunks" (chalk lumps, rubble, stones), puddle masks |
| `lib/wood.py` | periodic wood grain (irregular ring widths, latewood profile, knots deflecting the grain), board layout |
| `lib/weave.py` | plain-weave thread model (crimp, slubs, wander, twist) used for hessian |
| `lib/strokes.py` | supersampled polygon ribbons (grass blades, roots, stitches) with wrap-around |
| `lib/pbr.py` | height (metres) → OpenGL normal at true texel scale, cavity AO, JPEG writing, manifest |
| `sets/*.py` | one builder per material, returning albedo / height / roughness / metalness (`ww1_*`, `village`, `hq`, `blitz` = London 1940 chapter) |
| `fx.py` | effect textures |
| `preview_blender.py` | Cycles preview renders |

Height maps are authored in metres for the material's real tile size, so normal-map strength is
physically scaled (no arbitrary "strength" fudge, except a per-set multiplier of ~1).

## Effect textures (`public/assets/textures/fx/`, see `fx_manifest.json`)

| File | Layout |
|---|---|
| `rain_ripples_normal.png` | 2048², 4x4 flipbook of 512² frames, row-major from the top left, 16 frames, loops; each frame tiles. OpenGL normals. |
| `footprints_alpha.png` | 1024², 4 cols x 2 rows of 256x512 cells, toe at the top, 1150 px/m (sole ≈ 340 px). RGB = OpenGL normal of the depression (hobnail dimples, heel iron, displaced-mud rim), A = decal mask. Cells: 0 left fresh deep, 1 right fresh deep, 2 left shallow, 3 right shallow, 4 left slipped/smeared, 5 right toe only, 6 left heel only, 7 right old/softened. Suggested decal shading: blend normal by A, darken albedo and lower roughness inside the deep part. |
| `smoke_puff.png`, `dust_puff.png` | 512² single sprites, straight alpha, self-shadowed RGB (never black under transparent texels, safe to premultiply). |
| `cloud_noise.png` | 1024² tileable: R broad fBm, G ridged billows, B fine cellular wisps. |
| `blue_noise.png` | 128² void-and-cluster blue noise (8-bit grey). |
| `water_normal.png` | 1024² tileable small wind waves (Phillips spectrum), ~2 m tile. |
| `grass_blade_atlas.png` | 1024², 4 cols x 2 rows of 256x512 tuft cards, base at the bottom centre; alpha-test at 0.5; colours dilated into transparent texels. |
| `barbed_wire_alpha.png` | 512x128 strip tiling along U, two twisted strands + 4-point barb every 128 px. |
| `fire_flipbook.png` | 2048², 8x8 flipbook of 256² frames (64 frames, row-major from the top left), loops; RGB = emissive flame colour (sRGB), A = flame mask; base at the bottom centre. |
| `smoke_dark.png` | 512² dense dark smoke puff, straight alpha. |
| `window_tape.png` | 512² = one window pane: brown gummed anti-blast tape (border, X, centre cross), alpha ~0.85. |
| `glass_shards.png` | 512² broken window-glass decal (bodies, bright edges, glints), A = coverage. |

## Third-party sources

None. All textures are generated from code in this directory.
