# Project status — R1 (2026-10-03)

**Summary.** The Pulaski Bridge demonstration route and a Gate-G1 test pad have
been generated from **real data** (Overture/OSM roads, USGS 1 m DEM, USGS
classified lidar) with **zero offline geometry errors**, and their MSFS package
sources are committed. **Nothing has been compiled with the SDK, loaded in
MSFS 2024, or driven.** This session ran in a remote Linux container with no
access to the Windows PC, the simulator, its SDK or the Community folder
(docs/00). The exact continuation steps are in
[docs/09-windows-handoff.md](docs/09-windows-handoff.md).

## Coverage (evidence-based only)

Denominator measured for the first time: **105,997 in-scope segments / 11,115.4 km**
in the five boroughs (+73.0 km in the placeholder GWB NJ extension, not included below).

| Status (five boroughs) | km | Meaning |
|---|---:|---|
| driven / verified | **0** | no in-game driving has taken place |
| geometry_verified | 30.27 | offline geometry checks passed in the demo build — **not** a driving test |
| blocked | 42.87 | tunnels citywide, plus the demo's tunnel approaches and unmeasured LIE decks |
| inventoried | 11,042.27 | in the inventory, no work yet |

Source: `coverage/citywide/COVERAGE.md` (regenerate the map with
`nycroads coverage --release releases/citywide-inventory.json`).

## Milestones per package

| Package | Generated (offline) | Compiled (SDK) | Loaded (MSFS) | Driven (telemetry) |
|---|---|---|---|---|
| `nycroads-g1-testpad` | yes — 8 segments, 0 errors | **no** | **no** | **no** |
| `nycroads-r0-demo` | yes — 377 segments / 33.4 km, 0 errors, 14 segments + 2 decks blocked | **no** | **no** | **no** |

## Completed and tested offline (40 automated tests + real-data builds)

| Item | Evidence |
|---|---|
| Overture → inventory converter (fractional bridge/tunnel/level rules, oneway/access) | `src/nycroads/overture.py`; citywide inventory run |
| Borough polygons incl. territorial water | inter-borough bridge mid-spans inside |
| USGS DEM + EPT lidar access, lidar vertical datum established (= DEM NAVD88, median 0.000 m) | `nycroads check-lidar-datum` |
| Deck controls from lidar class 17 (+ class-1 gap fill with continuity limits) for all 6 decks in the demo | `data/deck_controls.json` |
| Road surfaces from lidar where the DEM is wrong (streets on unmapped structures) | `src/nycroads/lidarsurface.py`, tests |
| Continuous per-level surfaces (no overlaps, watertight across cells) | `src/nycroads/surface.py`, tests |
| Unmeasured deck runs are blocked, not extrapolated | LIE decks blocked |
| Demo acceptance on real data: all five required features present | `build/r0-demo/demo_acceptance.json` |
| Concrete D1–D10 plans with coordinates | `docs/r1/*/TEST_PLAN.md` |
| Package sources (glTF tiles + placement XML + baseline project XML) | `package/nycroads-g1-testpad`, `package/nycroads-r0-demo` |

Details and findings: [docs/r1/README.md](docs/r1/README.md).

## Not done — needs the Windows simulator host

| Step | Blocker here | Where |
|---|---|---|
| Host inspection (sim/SDK versions, Community packages, vehicles) | no Windows host | docs/09 §1 |
| SDK verification V1–V12 (build gate stays closed) | no SDK / docs | docs/09 §3, docs/verification/REGISTER.md |
| Player vehicle selection | no simulator | docs/09 §4 |
| Compile, install, load-check test pad and demo | no SDK / simulator | docs/09 §5–6 |
| In-sim vertical calibration (V7 simulator side) | no simulator | docs/09 §5.3 |
| D1–D10 driving, restart repeats, screenshots, performance | no simulator | docs/09 §5–6, docs/06 |
| Terrain flatten / exclusion polygon generation | schema needs V8/V9 | R2 |

## Technically blocked (by design until resolved)

| Item | Reason |
|---|---|
| All tunnels (412 segments citywide) | separate feasibility task (docs/01) |
| Queens–Midtown Tunnel open-cut approach (9 segments in the demo) | split-level ramps share nodes; part of the tunnel task |
| LIE viaduct decks in the demo window (2 decks) | 236 m segment with no lidar deck returns; 360 m unmeasured end — need other measurements |
| Goethals, Outerbridge, Bayonne bridges | outside the boundary; coverage ends before them |

## Known limitations

* Widths: Overture has no `lanes`; class defaults apply where OSM `width` is absent.
* Survey epoch 2013–14; later construction is not reflected.
* 7,148 Overture `unknown`-class ways excluded pending review.
* GWB NJ extension polygon is a placeholder box (73 km of Fort Lee streets) — refine in R5.
* MSFS-specific glTF/XML names unverified (config/msfs_gltf.json, V1–V3, V5–V6).
* One visual LOD; flat-colour materials; markings are edge/centre lines only.
