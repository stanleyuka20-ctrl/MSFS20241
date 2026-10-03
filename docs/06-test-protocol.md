# 06 — Test protocol, statuses and evidence

## Statuses (derived, never typed by hand)

Status is derived by `src/nycroads/coverage.py` from evidence in
`data/status.json`. A rebuild invalidates driving evidence for the rebuilt
segments (only drives against the current build count).

| Status | Requires | Kind of evidence |
|---|---|---|
| `inventoried` | in the inventory with a stable ID | data |
| `generated` | surface generated in the current build | data |
| `geometry_verified` | no **error** from the offline checks in the current build | **geometry check — not a driving test** |
| `driven` | latest in-game run in **every permitted direction** passed (oneway → one direction; two-way → both) | in-game telemetry |
| `verified` | `driven`, plus a pass in each direction in a run flagged `--after-restart` | in-game telemetry after simulator restart |
| `blocked` | recorded blocker (missing deck controls, tunnel feasibility, …) | data |

A later failing run in a direction cancels earlier passes in that direction.

## Offline geometry checks (`src/nycroads/checks.py`)

Errors (block `geometry_verified`): `joint_gap` (> 1 cm height step at a 2-way
join), `underpass_clearance` (< 3.5 m between deck underside and road below),
`overlap` (two non-adjacent surfaces overlapping in plan within 2 m height —
duplicate geometry / z-fighting), `deck_elevation_missing`, `deck_from_terrain`,
`junction_trim_conflict` (segment too short for the junction trims),
`junction_pad_invalid`.

Warnings (reviewed, listed in the build report): `grade` / `grade_change`
above review thresholds (`config.py`), `joint_kink` (grade change > 3 %
across a join), `open_edge` (junction arm outside the build),
`grade_separation_indeterminate` (OSM crossing without layer information).

## In-game test runs

1. Record environment: `tools/inspect_host.ps1` output for the session, and a
   `meta.json` per run:
   ```json
   {"tester": "...", "sim_version": "...", "sdk_version": "...", "vehicle": "...",
    "graphics": "preset/resolution/upscaler/frame-gen", "photogrammetry": true,
    "weather": "clear", "time": "13:00 local", "community_packages": ["..."], "route": "D6"}
   ```
2. `nycroads record --out telemetry/<run>.csv --markers telemetry/markers.txt`
3. Drive the route; append notes to the markers file (`restart_marker`, `hill start`, …).
4. `nycroads analyse-run --release <release.json> --run telemetry/<run>.csv --meta meta.json [--after-restart]`
5. Commit `tests/results/<run>.json` (small) and keep the CSV in the release's evidence archive.

Incidents detected: `fall_through` (vehicle > 0.6 m below the surface),
`floating` (> 0.4 m above while airborne), `level_jump` (> 0.35 m change
relative to the surface between samples — snapping between decks), `airborne`
(> 0.6 s off ground), `sudden_stop` (> 7 m/s² deceleration without brake —
invisible obstacle), `recovery` (explicit; fails the segment).

Coverage of a segment counts only if ≥ 80 % of its stations were driven in
that direction.

## Mandatory test locations per release

Intersections, ramps (merge and diverge), bridge seams (abutments and
deck-to-deck joins), underpasses, tile boundaries (from the build report's
tile list), and every permitted direction. Each release adds a continuous
session (≥ 20 min, no recovery) and the after-restart repeat.

## Screenshots (before / after)

Fixed camera positions are taken from `start_locations` plus one per bridge
deck end and per underpass. For each position capture: add-on **disabled**
(before) and **enabled** (after), each in day/clear, night/clear and
day/rain, same time, weather preset and camera. Name files
`<release>/<position-id>_<before|after>_<day|night|rain>.png`.

## Performance measurement

Measure, do not promise. On the same recorded route (D9) with the add-on
disabled and enabled, same settings:

* average FPS and 1 % low; count of frame-time spikes > 50 ms
  (capture with the simulator's developer-mode performance display or an
  external frame-time capture tool such as PresentMon / CapFrameX);
* system RAM and VRAM peak (Task Manager / tool log);
* time from "Fly"/start to drivable, and any stutter on entering new tiles.

Report hardware (from host-inspection.json), settings and the numbers in the
release notes. Visual LOD changes must not alter vehicle support: telemetry of
the same route must show no `level_jump` while LODs switch (V11).
