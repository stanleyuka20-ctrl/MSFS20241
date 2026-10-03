# SDK verification register (V1–V12)

One entry per item. An item is **VERIFIED** only with: the installed simulator
and SDK versions, the exact check performed, the evidence (file, screenshot,
log or telemetry result), and the outcome. Anything else stays **UNVERIFIED**.
Procedures: [docs/09 §3](../09-windows-handoff.md#3-gate-v--verify-the-sdk-assumptions-v1v12).

Environment of record: _(fill from docs/host-inspection.json)_ — simulator
build `…`, SDK `…`, date `…`, tester `…`.

| ID | Item | Status | Evidence | Correction made |
|---|---|---|---|---|
| V1 | Project / package definition XML | UNVERIFIED | | |
| V2 | Placement + model-library XML | UNVERIFIED | | |
| V3 | Collision-only mesh / collision enable (glTF extensions) | UNVERIFIED | | |
| V4 | Player vehicle supported by scenery-object collision | UNVERIFIED | | |
| V5 | Marking draw order (no z-fighting) | UNVERIFIED | | |
| V6 | Axis convention (orientation marker) | UNVERIFIED | | |
| V7 | Simulator height reference (calibration residuals < 0.10 m) | UNVERIFIED (data side done, see below) | | |
| V8 | Terrain flatten / terraform polygons | UNVERIFIED | | |
| V9 | Tight exclusion polygons | UNVERIFIED | | |
| V10 | SimConnect variables / units / settable position | UNVERIFIED | | |
| V11 | Collision unaffected by LOD / streaming | UNVERIFIED | | |
| V12 | Player-controllable ground vehicle | UNVERIFIED | | |

## Evidence already established without the simulator (data side only)

* **Lidar and DEM share NAVD88 metres** — `nycroads check-lidar-datum
  --release releases/r0-demo.json`: n = 200,000, median 0.000 m, MAD 0.02 m,
  p5/p95 −0.07/+0.07 m (2026-10-03). This fixes the *native* side of V7; the
  simulator side (NAVD88 → simulator altitude) still needs the in-sim calibration.
* **Generated glTF files are structurally valid glTF 2.0** (pygltflib load in
  tests; separate `visual` and `collision` nodes). Whether MSFS 2024 interprets
  the collision node as intended is V3/V4.

## Entry template

```
### Vn — <title>
Simulator build / SDK version:
Date / tester:
Check performed (exact steps, files compared):
Evidence (paths):
Result: PASS | FAIL
If FAIL — what was wrong, what was changed (commit), re-check result:
```
