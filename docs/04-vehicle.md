# 04 — Player-controlled ground vehicle

Requirement: a vehicle **the player drives** (not AI traffic on a scripted
path) with acceleration, braking, steering, reversing, hill starts, a
driver's-eye view and an external follow camera, keyboard and gamepad input,
visible speed, and an explicit recovery function.

**Status: no vehicle has been selected or tested (V12 UNVERIFIED).** This
project could not inspect a simulator installation (docs/00), so it does not
claim that MSFS 2024 does or does not offer a suitable vehicle.

## Decision procedure (on the simulator host)

Evaluate in this order and stop at the first option that passes the
acceptance tests below. Record the result in `vehicle/selection.md`.

### Option A — a ground vehicle supported by MSFS 2024 itself

Check, with the installed simulator and SDK documentation:
1. Is any ground vehicle player-controllable in free roam (not only inside a
   scripted activity)?
2. Does the SDK document a ground-vehicle SimObject that a third party can
   package and that the player can select and drive?
3. Which input bindings and cameras does it expose?

If yes, use it (or package a variant through the documented SimObject route).
This is the preferred option: native physics, controls and cameras.

### Option B — an existing third-party vehicle add-on

`tools/inspect_host.ps1` flags Community packages that look like ground
vehicles. Use one only if its licence allows our users to install it
alongside this add-on; we never redistribute it. Document version and source.

### Option C — build a vehicle as a SimObject through the documented aircraft route

A SimObject configured through the standard documented configuration files
(contact points/wheels, engine, brakes, steering, no meaningful lift) can
behave as a road vehicle. This route has known risks that must be measured,
not assumed:

| Risk | Test |
|---|---|
| Reversing may need reverse thrust or a pushback-style mechanism rather than a reverse gear | D4 |
| Aircraft-oriented tyre/brake/steering models may feel wrong at low speed in tight turns | D3, D5 |
| Wheel contact with scenery-object collision (V4) | Gate G1 |
| Camera definitions for a low eye-point | camera check |

Target specification for Option C: `vehicle/requirements.json`.

## Acceptance tests (any option)

The vehicle passes when, on the R0 demo route, D1–D10 of
[docs/03](03-demo-route.md#required-in-game-tests-all-with-telemetry)
pass, and additionally:

* Keyboard **and** gamepad bindings exist for throttle, brake, steer left/right,
  reverse, handbrake/parking brake; written down in `vehicle/controls.md`.
* Driver's-eye camera at a plausible eye height (≈1.2 m above road for a car)
  and an external follow camera both work.
* Speed is visible on screen (vehicle instrument, or the sim's own display).
* Telemetry selftest (V10) reports correct position, heading and speed.

## Recovery

`nycroads recover --release … --start START-… --ref-height … --markers telemetry/markers.txt`
moves the vehicle to a start location that is on a generated, error-free
segment (`build_report.json → start_locations`). It always writes a
`recovery` line to the markers file; the analyser then **fails** the segment
being driven, so recovery can never hide a broken connection. If SimConnect
position setting does not work for the chosen vehicle (V10), the fallback is
to restart the flight at the start location via the simulator's own UI and log
that as a recovery event manually.

## Tuning targets (urban driving)

Tuning is done only after Gate G1. Targets to measure on the demo route:
0–50 km/h in 6–12 s; 50–0 km/h braking in ≤ 25 m on dry asphalt; turning
circle ≤ 12 m; holds position on the steepest demo grade with brakes; no
oscillation at 30–60 km/h on straight road.
