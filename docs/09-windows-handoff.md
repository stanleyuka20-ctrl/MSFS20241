# 09 — Handoff: continue on the Windows simulator host

Everything below needs a Windows PC with MSFS 2024 and its SDK. Work through it
**in order**: each gate must pass before the next starts. Record the outcome
of every step; a step without recorded evidence counts as not done.

Three separate milestones are tracked per package, and are never merged:

| Milestone | Means | Evidence |
|---|---|---|
| **Compiled** | the SDK package tool built it without errors | build log saved to `docs/r1/evidence/<package>/build.log` |
| **Loaded** | the simulator loaded it; geometry appears where expected | load-check notes + screenshots in `docs/r1/evidence/<package>/` |
| **Driven** | telemetry from a player-driven vehicle passed D-tests | `tests/results/*.json` from `nycroads analyse-run` |

## 0. Set up (once)

```powershell
git clone https://github.com/stanleyuka20-ctrl/MSFS20241
cd MSFS20241
git checkout claude/serene-cerf-ejep1h
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dem,sim,dev]"
python -m pytest            # expect all tests to pass
```

The generated package sources for both packages are committed
(`package/nycroads-g1-testpad/`, `package/nycroads-r0-demo/`), so data
downloads are **not** needed to compile and install. They are needed to analyse
telemetry (the analyser rebuilds the inventory) — see step 2.

## 1. Gate G0 — inspect the host (read-only)

```powershell
powershell -ExecutionPolicy Bypass -File tools\inspect_host.ps1
```

Review `docs/host-inspection.json` (simulator edition and build, SDK path and
version, `fspackagetool.exe` and `SimConnect.dll` versions, Community
packages). Disable Community packages flagged *possible NYC scenery conflict*
for testing and note which. Commit the JSON.

## 2. Reproduce the data (optional for compiling; required for telemetry analysis)

```powershell
nycroads fetch overture-roads --bbox 40.47,-74.27,40.93,-73.68 --out data/raw/overture_segments_nyc.parquet
nycroads fetch overture-divisions --bbox 40.47,-74.27,40.93,-73.68 --out data/raw/overture_division_area_nyc.parquet
nycroads fetch usgs-dem --release releases/r0-demo.json
nycroads fetch usgs-dem --release releases/g1-testpad.json
nycroads fetch usgs-lidar --release releases/r0-demo.json        # ~27 M points, several minutes
nycroads check-lidar-datum --release releases/r0-demo.json       # must report median ~0.00 m
nycroads build --release releases/r0-demo.json --allow-unverified   # must reproduce build ids' content
```

Rebuilding regenerates `package/*/PackageSources`; `git diff --stat package/`
should show no geometry changes unless inputs changed.

## 3. Gate V — verify the SDK assumptions (V1–V12)

Use the installed SDK's own documentation, its sample projects, and files
saved by the SDK tools. Record each item in
[`docs/verification/REGISTER.md`](verification/REGISTER.md) with the SDK
version and evidence. **Do not set `config/msfs_gltf.json → "verified": true`
until V2, V3, V5 and V6 are recorded as passed** — the build gate exists to stop
unverified releases, not to be bypassed.

| Item | Concrete check |
|---|---|
| V1 package format | Create an empty Scenery project with the SDK Project Editor named `nycroads-g1-testpad`. Diff its project XML and `PackageDefinitions/*.xml` against `package/nycroads-g1-testpad/`. Replace ours with the SDK's (the generator never overwrites existing project files). |
| V2 placement / model XML | In the Scenery Editor place one library object, save; diff the saved XML element/attribute names against `PackageSources/scene/nycroads-g1-testpad.xml` (`SceneryObject`, `LibraryObject`, `altitudeIsAgl`, `snapToGround`) and a model XML against `modelLib/.../*.xml` (`ModelInfo/LODS/LOD`). |
| V3 collision-only mesh | Find, in the SDK glTF/model documentation or the SDK's Blender exporter, how a mesh is made invisible-but-collidable and how collision is enabled. Compare with `config/msfs_gltf.json` (`ASOBO_tags`, `ASOBO_material_invisible`). If they differ, correct the config and rebuild. |
| V4 vehicle supported by scenery collision | Gate G1 (step 5). |
| V5 markings draw order | SDK docs for decal/draw-order; visual check of markings for z-fighting on the test pad. |
| V6 axis convention | Test-pad orientation marker (red arrow) must point true north with its stub on the east side. |
| V7 height reference | Calibrate (step 5.3). |
| V8 / V9 terrain flatten and exclusion | Scenery Editor test on one Greenpoint street; confirm effect is limited to the polygon. Save one of each and keep the XML as the schema reference for R2. |
| V10 SimConnect | `nycroads record --selftest` while parked at a test-pad start location: lat/lon must match the start's coordinates to < 2 m, heading to < 2°, speed 0. |
| V11 collision vs LOD / streaming | Drive away from the test pad > 5 km and back; telemetry must show no `level_jump`. |
| V12 player vehicle | Step 4. |

## 4. Choose the player vehicle (V12)

Follow [docs/04](04-vehicle.md). Record in `vehicle/selection.md`: the vehicle
(name, version, source, licence), how the player controls it, and its
keyboard and gamepad bindings for throttle, brake, steer, **reverse**, parking
brake; which views give a driver's-eye and an external follow camera; where
speed is shown. An AI-driven or scripted vehicle does not qualify.

## 5. Gate G1 — test pad first (small surface, before the demo route)

1. **Compile** `package/nycroads-g1-testpad` with the SDK (Project Editor build,
   or `tools\build_package.ps1 -Project package\nycroads-g1-testpad\nycroads-g1-testpad.xml`).
   Save the log as `docs/r1/evidence/nycroads-g1-testpad/build.log`. Fix any
   errors at the source (generator or config), never by hand-editing outputs.
2. **Install**: copy the built package folder from
   `package\nycroads-g1-testpad\Packages\` into the Community folder
   (`InstalledPackagesPath` from `docs/host-inspection.json` + `\Community`).
   Start the simulator.
3. **Load and calibrate (V6, V7)**: spawn the vehicle (any free-flight start,
   then `nycroads recover --release releases/g1-testpad.json --start <START-id>
   --ref-height <h> --markers telemetry/markers.txt` with a start id from
   `build/g1-testpad/build_report.json`, or via the vehicle's own placement).
   Check the orientation marker (V6). Park on the flat strip at three points and
   run `nycroads record --selftest`; enter `{lon, lat, native_m, sim_m}` into
   `data/vertical_reference.json` (native = DEM, sim = PLANE ALTITUDE − vehicle
   reference height). If the residuals exceed 0.10 m, rebuild both packages with
   the calibrated reference and reinstall.
4. **Drive** `docs/r1/g1-testpad/TEST_PLAN.md` D1–D8 with telemetry:
   ```powershell
   nycroads record --out telemetry\g1_run1.csv --markers telemetry\markers.txt
   # drive; append notes to telemetry\markers.txt (e.g. "hill start")
   nycroads analyse-run --release releases/g1-testpad.json --run telemetry\g1_run1.csv --meta telemetry\meta.json
   ```
   `meta.json` fields: tester, sim version, SDK version, vehicle, graphics
   settings, weather, time of day, community packages (docs/06).
5. Restart the simulator and repeat D3, D6, D7 with `--after-restart` (D10).
6. **G1 passes** only when every test-pad segment is `verified`
   (`nycroads coverage --release releases/g1-testpad.json`). If the vehicle
   falls through or floats on the deck, stop: correct V3 (collision config),
   rebuild, retest; if no supported configuration works, record the blocker in
   docs/02 and do not build the demo route.

## 6. Demonstration route

Only after G1 passes.

1. Compile `package/nycroads-r0-demo` (after replacing its project files with
   SDK-generated ones as in V1). Save the build log.
2. Install; load the Pulaski Bridge area. **Load checks** (screenshots from
   fixed camera positions per docs/06, add-on enabled and disabled):
   alignment of generated roads with the default imagery/photogrammetry;
   continuity at junctions and tile seams (tiles are listed in
   `build/r0-demo/build_report.json`); both Pulaski decks visible and supported;
   Clay Street passing beneath the Pulaski approach with clearance; conflicts
   with default scenery (photogrammetry poking through, floating default
   objects, duplicate bridges).
3. Drive `docs/r1/r0-demo/TEST_PLAN.md` D1–D10 with telemetry as in 5.4,
   including both Pulaski carriageways (each is one-way), a continuous
   ≥ 20-minute session (D9), and the after-restart repeats (D10).
4. Fix failures at the source, rebuild, **reinstall**, and rerun the affected
   tests — a rebuild invalidates earlier driving evidence for rebuilt segments.
5. `nycroads coverage --release releases/r0-demo.json` and commit
   `coverage/r0-demo/`, `tests/results/`, `data/status.json`, evidence folders.

## 7. What to send back

Commit and push to the branch (or attach): `docs/host-inspection.json`,
`docs/verification/REGISTER.md`, `vehicle/selection.md`, build logs, load-check
notes/screenshots, `tests/results/*.json`, `data/status*.json`,
`data/vertical_reference.json`, and any corrected config/project files. A later
session can then analyse failures and continue from the evidence.
