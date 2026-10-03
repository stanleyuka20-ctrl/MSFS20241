# 03 — Demonstration route (Release 0 / Gate G1)

> **R1 result (2026-10-03):** confirmed on real data — all five required
> features are present in the Pulaski Bridge corridor (`build/r0-demo/demo_acceptance.json`);
> 377 segments generated with 0 geometry errors. Data steps below were run with
> Overture (instead of Overpass, which is blocked in the cloud container) and
> USGS 3DEP DEM + EPT lidar. Results and findings: [r1/README.md](r1/README.md);
> concrete test locations: [r1/r0-demo/TEST_PLAN.md](r1/r0-demo/TEST_PLAN.md);
> before the demo, prove the vehicle on the test pad
> ([r1/g1-testpad/TEST_PLAN.md](r1/g1-testpad/TEST_PLAN.md)).

## Choice: Pulaski Bridge corridor (Greenpoint, Brooklyn ↔ Long Island City, Queens)

Why this corridor: a compact (~1.5 × 1.2 km) area with an ordinary street
grid and intersections on both sides, a raised approach and bridge deck over
Newtown Creek with ground-level entry and exit, roads passing beneath raised
structures near the Queens landing (the Queens–Midtown Tunnel / LIE approach
area), real grades on the approaches, and plenty of edges where repaired roads
hand over to default scenery. It is far smaller and simpler than a major East
River crossing, so it is a fair test of the method before scale-up.

**The choice is provisional until the data confirms it.** The selection window
is `releases/r0-demo.json → bbox` (approximate). `nycroads build` evaluates the
real inventory inside it and writes `build/r0-demo/demo_acceptance.json`:

| Criterion | Automated test (`src/nycroads/demo.py`) |
|---|---|
| Ordinary street + intersection | an at-grade junction of ≥3 in-scope, non-bridge segments, all inside the build |
| Slope / elevation change | a ground segment with ≥3 % grade sustained over ≥30 m in the generated profile |
| Bridge approach, raised deck, exit | a deck with ground-level approaches at both ends **and** an elevation source (controls) |
| Road beneath an elevated structure | a determinate grade separation whose lower road is in scope and not a tunnel |
| Transition to surrounding world | junctions where generated segments meet non-generated ones |

If any criterion fails, adjust the bbox or switch to a fallback candidate
listed in the release file; record the decision here.

## Steps (simulator host or any machine with network access)

```bash
pip install -e ".[dem,dev]"
# 1. Data (needs network access to overpass-api.de; see docs/00 if blocked)
nycroads fetch boroughs --out data/raw/boroughs.json
nycroads fetch roads --bbox 40.7300,-73.9650,40.7520,-73.9380 --out data/raw/roads_r0.json
# 2. DEM: put a bare-earth DEM covering the fetch bbox at data/dem/r0_dem.tif
#    (NYC 1 ft DEM: US survey feet, NAVD88 -> z_units "ftUS"; USGS 3DEP 1 m: metres -> "m")
# 3. Inventory
nycroads inventory --release releases/r0-demo.json
```

### Deck elevation

The Pulaski deck is a major crossing, so it needs explicit controls
(`data/deck_controls.json → XS-PULASKI`). From classified lidar tiles covering
the bridge (e.g. NYC 2017 topobathymetric lidar or USGS 3DEP point cloud):

```bash
pip install "laspy[lazrs]"
nycroads deck-controls --release releases/r0-demo.json --key XS-PULASKI --las path/to/tiles/*.laz --z-units ftUS
```

Check the result: `n_points` ≥ 5 and `spread_m` small at every control; no
control should be near water level. If the survey has no class 17, document
the alternative source used (docs/05) — never terrain under the deck.

### Vertical calibration (verification item V7)

1. Build and install a test package (below), open the area in the simulator.
2. Park the vehicle at ≥3 flat, open, ground-level spots inside the area
   (choose from `build/r0-demo/build_report.json → start_locations`).
3. At each, run `nycroads record --selftest`; compute
   `sim_ground = alt_m − vehicle reference height` and enter
   `{lon, lat, native_m, sim_m}` in `data/vertical_reference.json → control_points`
   (`native_m` = DEM height there). With ≥3 points the offset is interpolated.
4. Rebuild. Set `"verified": true` only when residuals at all points are < 0.10 m.

### Build, install

```bash
nycroads build --release releases/r0-demo.json --allow-unverified   # test build until V1–V6 verified
```

Then on Windows: `tools\build_package.ps1 -Project package\nycroads-r0-demo\nycroads-r0-demo.xml`
(or build from the SDK Project Editor) and install per [docs/07](07-build-install.md).
Set `orientation_marker_at` in the release file to a start location first, so
axis convention (V6) is checked on the first load: the red arrow must point
true north with the stub on its east side.

## Required in-game tests (all with telemetry)

Start every run with `nycroads record --out telemetry/<run>.csv --markers telemetry/markers.txt`
and note events by appending lines to the markers file. Analyse each run with
`nycroads analyse-run --release releases/r0-demo.json --run telemetry/<run>.csv --meta <meta.json>`.

| # | Manoeuvre | Pass condition |
|---|---|---|
| D1 | Spawn at a start location, wait 10 s | no incident; reference height measured |
| D2 | Accelerate to ~40 km/h on a straight street, brake to stop | no `sudden_stop` without brake; no incidents |
| D3 | Turn left, right and straight through the main intersection from every approach | every arm segment `pass` in its permitted direction |
| D4 | Reverse 30 m on a two-way street | `reverse_distance_m` ≥ 30, no incidents |
| D5 | Stop on the steepest approach grade, hold 10 s, release, hill start | no incidents; roll-back ≤ 1 m (read from the CSV around the `hill start` marker — not yet automated) |
| D6 | Cross the bridge in each permitted direction (approach → deck → exit) | all deck and approach segments `pass` both ways; no `level_jump`, `fall_through`, `floating` |
| D7 | Drive the road beneath the raised structure, both directions | `pass`, no `sudden_stop` (invisible obstacle) |
| D8 | Drive off the repaired area onto default scenery and back | transition segments `pass`; report visual step at the hand-over |
| D9 | Continuous 20 min session covering D2–D8 without recovery | zero incidents |
| D10 | Restart the simulator, repeat D3, D6, D7 with `--after-restart` | all `pass` → segments become `verified` |

D1–D10 complete = Gate G1 passed. Until then no further districts are generated.
