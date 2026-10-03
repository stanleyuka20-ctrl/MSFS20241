# Project status — Release 0 (2026-10-03)

**Summary:** the toolchain for repairing NYC roads is built and tested
offline. **No road has been driven in the simulator, no package has been
compiled, and no real NYC data has been processed yet.** The environment
this release was built in (Linux, no simulator, network limited to package
registries) made all three impossible — see docs/00.

Coverage: **0 of the in-scope road network is verified.** The denominator
itself (in-scope km per borough) is produced by `nycroads inventory` once OSM
data is fetched; it has not been computed yet.

## Completed (and tested offline: 31 automated tests on a synthetic network)

| Item | Where |
|---|---|
| Scope rules: what counts as a public motor-vehicle road | `src/nycroads/config.py`, docs/01 |
| Boundary policy: city-limit cuts, whole-deck exclusion for NJ bridges, GWB extension | `inventory._drop_outside`, docs/01 |
| Inventory: segments, junctions (intersection/connection/dead end/boundary cut), bridge decks, ramp groups, grade separations, connectivity, stable IDs + registry | `inventory.py`, `ids.py` |
| OSM fetch with provenance/licence records | `osm.py` |
| Vertical profiles: despiking, anchored smoothing, grade checks; datum/units handling; calibration model | `profile.py`, `elevation.py` |
| Bridge decks from controls only (never terrain), continuing approach grades; blocked when controls missing | `elevation.deck_profile` |
| Lidar class-17 deck-control extractor | `deckcontrols.py` |
| Surface generation: ribbons, watertight junction pads, skirts, deck slabs, barriers, markings | `meshgen.py` |
| Offline geometry checks: joint gaps/kinks, clearance, overlaps, deck sources | `checks.py` |
| glTF 2.0 tile writer (visual + separate collision node), MSFS specifics isolated in config | `gltf.py`, `config/msfs_gltf.json` |
| Scenery placement + model-library XML, stable GUIDs | `scenery.py` |
| Telemetry analyser (fall-through, floating, level jumps, airborne, invisible obstacles, recovery, direction, reversing) | `telemetry.py` |
| Status derivation + coverage map/tables | `coverage.py` |
| SimConnect recorder / explicit recovery (code only) | `simbridge.py` |
| Host inspection and package build scripts (code only) | `tools/*.ps1` |
| Documentation: boundary, approach + verification register, demo route + test plan, vehicle decision procedure, data/licensing, test protocol, build/install/remove, roadmap | `docs/` |

## Not done — needs the simulator host or data access

| Item | Blocker | Next step |
|---|---|---|
| Host inspection (version, SDK, packages, vehicles) | no Windows/MSFS here | run `tools/inspect_host.ps1` (docs/00) |
| Verify SDK formats and capabilities V1–V12 | no SDK/docs access | docs/02 register |
| Fetch OSM + borough boundaries; DEM; lidar | network policy denies the hosts | allow hosts or run `nycroads fetch` on the host |
| Confirm demo route meets all criteria | no data | `nycroads build` → `demo_acceptance.json` |
| Pulaski deck controls | no lidar | `nycroads deck-controls` |
| Vertical calibration | no simulator | docs/03 calibration |
| Vehicle selection / build | no simulator | docs/04 decision procedure |
| Gate G1 driving tests D1–D10, restart repeat | no simulator | docs/03 |
| Package compile, install, screenshots, performance | no simulator | docs/06, docs/07 |
| Terrain flatten / exclusion polygon generation | schema unverified (V8/V9) | R1 |
| Textures, visual LODs, curbs/crosswalks detail | after G1 | R2 |

## Technically blocked (by design until proven)

| Item | Reason |
|---|---|
| All tunnels | separate feasibility task (docs/01#tunnels) |
| Any major bridge deck without elevation controls | heights are never guessed from terrain |
| Goethals, Outerbridge, Bayonne bridges | outside boundary; coverage ends before them |

## Known limitations of the generator (R0)

* Junction pads use straight chamfers, not curb-return arcs; motorway gores are chamfered.
* Markings are edge lines + centre line only; no lane lines, crosswalks or stop bars yet.
* One visual LOD; flat-colour PBR materials (no textures).
* Widths fall back to defaults where OSM lacks `width`/`lanes`.
* Junctions whose arms are partly outside a build get no pad (reported as `open_edge`).
