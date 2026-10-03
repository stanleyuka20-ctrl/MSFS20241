# 02 — Technical approach and SDK verification register

## Principle

Use only official SDK interfaces, and treat every simulator-specific detail as
**unverified until checked against the installed MSFS 2024 SDK**. All
simulator-specific names used by the code live in a small number of reviewed
places so a correction is a one-file change:

| What | Where | Verification item |
|---|---|---|
| glTF extensions (collision, invisible collision material, draw order), axis convention | `config/msfs_gltf.json` | V3, V4, V5, V6 |
| Model library XML, scenery placement XML | `src/nycroads/scenery.py` | V2 |
| Project / package definition XML | `package/*/` | V1 |
| Height reference (what "altitude" means to the sim) | `data/vertical_reference.json` | V7 |
| SimConnect variable names / units | `src/nycroads/simbridge.py` | V10 |

`nycroads build` refuses to run while `config/msfs_gltf.json` has
`"verified": false`, unless `--allow-unverified` is given (test builds only).

## Architecture

```
OSM roads ──► inventory (stable IDs, junctions, decks, ramps, grade separations, connectivity)
                 │
DEM (bare earth) ┼──► ground profiles: despike (Hampel) + smooth (Whittaker), anchored at junctions
deck controls ───┴──► deck profiles: controls + abutments only, continuing approach grades (never terrain)
                 │
                 ▼
  surfaces: trimmed ribbons + watertight junction pads + skirts; decks with slab, edges, barriers
                 │
  offline geometry checks  ──►  status: geometry_verified (NOT a driving test)
                 │
  per-tile glTF (visual node + collision node, local ENU frame) + placement XML  ──► SDK build ──► package
                 │
  in-game drive with telemetry recorder ──► analyser ──► status: driven / verified
```

### Road surfaces are scenery objects, not terrain

The repaired driving surface is a set of **3D models with collision**, placed
at absolute altitude (`altitudeIsAgl="FALSE"`, no snapping). Reasons:

* Bridges, ramps, stacked decks and overpasses cannot be represented by a
  single-valued terrain surface at all.
* At ground level, photogrammetry/terrain artefacts (melts, spikes, pits) are
  exactly what we are repairing; following the terrain would reproduce them.
* Heights are computed once, reproducibly, from documented sources.

Terrain is still used where it helps: ground-level roads should get **tight
flatten/terraform polygons** under them (so the terrain does not poke through
the road or leave a visible gap), and tight **exclusion** areas remove default
vegetation/objects that sit on the roadway. Those polygon types are authored
with the SDK Scenery Editor (V8, V9); the pipeline will generate them only
after an editor-saved example confirms the XML schema (R1 task).

### Height reference

All heights are converted to the simulator's reference with a recorded
method: preferably an **in-sim calibration offset** measured at ≥3 control
points (so the generated road matches what the simulator actually renders),
otherwise a PROJ geoid transformation (NAVD88 → assumed simulator geoid) —
the simulator's vertical datum is *not* confirmed (V7).

### Bridge decks

Deck heights come only from explicit **deck controls** (lidar bridge-deck
class 17, class-1 gap fill only between class-17 controls and within 1 m of
their line, engineering data) or — for spans ≤ 60 m that are not named major
crossings — from interpolation between land abutments. The deck stage has no
access to the DEM. Interpolation through controls is shape-preserving (no
invented humps). A deck is **blocked** when controls are missing, inconsistent
(> 10 % between neighbours), or leave a long unmeasured run (> 120 m inside,
> 60 m uncontrolled segment, > 30 m at a free end). Measured decks set their
abutment heights and the approaches continue the deck grade.

### Surfaces, junctions and seams (revised in R1)

R0's per-node junction pads failed on real NYC junction clusters. R1 builds one
continuous surface per level (`surface.py`): the union of all road footprints
of a ground layer, of each bridge deck, or of each raised ground piece;
roads overlapping a non-adjacent road are split along the Voronoi midline;
same-level overlaps between surfaces go to the higher-priority surface. The
footprint is triangulated (constrained Delaunay, no Steiner points) per
250 m cell; vertex height is a deterministic function of position (blend of
centreline profiles), so cells and tiles share identical seam vertices
(tested). Height disagreements inside a surface are reported (> 1 m = error).
Markings follow the profiles at +2 cm with a draw-order extension.

### Ground heights (revised in R1)

Bare-earth DEMs remove every structure; in NYC many streets OSM does not tag
as bridges are carried over trenches and tunnel approaches. Ground roads
therefore use classified lidar road-surface returns (class 2; class 17 only
when continuous with the street's own ground, which rejects overpasses), with
the DEM as a continuity-checked fallback (`lidarsurface.py`).

### Tiling and LOD

Geometry is grouped into 1 km UTM tiles; each tile model uses an exact local
East-North-Up frame (no UTM scale error), origin at the tile centre. Collision
is a separate, lighter node (road top + barriers only). **Vehicle support must
never change with LOD or streaming.** How MSFS 2024 takes collision from a
multi-LOD model is not confirmed (V11), so R0 emits a single LOD; visual LODs
(R2) will be added only after V11 shows the collision is identical at every
LOD (e.g. the same collision node in each LOD file).

## Verification register

Evidence is recorded in [verification/REGISTER.md](verification/REGISTER.md); procedures in [09](09-windows-handoff.md#3-gate-v--verify-the-sdk-assumptions-v1v12).

Each item must be checked on the simulator host against the installed SDK
(local docs, sample projects, and an editor-saved file), with the result,
SDK version and date recorded here. Until then the item is **UNVERIFIED**.

| ID | Capability / assumption | Used by | How to verify | Status |
|---|---|---|---|---|
| V1 | Project + package definition XML format (`Project`, `AssetPackage`, asset group types `ContentInfo`, `ModelLib`, `BGL`) | `package/*` | Create a Scenery project with the installed SDK Project Editor; diff against `package/nycroads-r0-demo` | UNVERIFIED |
| V2 | `ModelInfo/LODS/LOD` model XML; `FSData/SceneryObject/LibraryObject` placement with `altitudeIsAgl`, `snapToGround` | `scenery.py` | Place one library object with the Scenery Editor, save, diff the XML | UNVERIFIED |
| V3 | glTF node/material extension that makes a mesh **collision-only** (invisible) | `msfs_gltf.json` | SDK glTF extension docs + Blender exporter material options | UNVERIFIED |
| V4 | Collision on a scenery object **supports the player vehicle's ground contact** (wheels rest on it; no fall-through) — the critical capability | everything | Gate G1 test (below) | UNVERIFIED |
| V5 | Draw-order / decal extension for markings | `msfs_gltf.json` | SDK docs; visual check for z-fighting | UNVERIFIED |
| V6 | Model axis convention (heading 0 = +Z north, +Y up) | `msfs_gltf.json` | Orientation marker in the demo package | UNVERIFIED |
| V7 | Simulator height reference (geoid) for absolute altitude | `vertical_reference.json` | Calibration at control points (docs/03) | UNVERIFIED |
| V8 | Terrain flatten / terraform polygon behaviour around photogrammetry | ground roads | Scenery Editor test on one street | UNVERIFIED |
| V9 | Exclusion of default objects/vegetation/photogrammetry inside a tight polygon | ground roads, decks | Scenery Editor test; verify neighbours untouched | UNVERIFIED |
| V10 | SimConnect SimVars/units via Python-SimConnect (`PLANE_LATITUDE`, `PLANE_ALTITUDE`, `SIM_ON_GROUND`, `GROUND_VELOCITY`, `VERTICAL_SPEED`, `PLANE_HEADING_DEGREES_TRUE`) and settable position for recovery | `simbridge.py` | `nycroads record --selftest` at a known spot; `recover` test | UNVERIFIED |
| V11 | Collision independent of visual LOD switching / tile streaming | tiles | Drive away and back; long continuous session; telemetry shows no level jumps | UNVERIFIED |
| V12 | A player-controllable ground vehicle exists or can be built with supported SDK features | vehicle | docs/04 decision procedure | UNVERIFIED |

### Gate G1 — prove vehicle support before generating more scenery

1. Build the R0 package with `--allow-unverified`, install, load the demo area.
2. Spawn the candidate vehicle on the R0 orientation marker, then drive onto a
   generated ground road, then up the bridge approach onto the deck.
3. Record telemetry for the whole session (`nycroads record`), analyse it
   (`nycroads analyse-run`).
4. **Pass** = no `fall_through`, `floating`, `level_jump`, `airborne`, or
   `sudden_stop` incidents on the deck and its approaches in both directions.

If G1 fails because scenery-object collision does not support the vehicle,
**stop generating scenery** and evaluate, in order: (a) different collision
configuration on the deck model (V3 variants), (b) a vehicle built with a
different supported contact model (docs/04), (c) restricting the add-on to
ground-level roads using terrain modification only, with bridges documented as
technically blocked. Record the outcome here before continuing.
