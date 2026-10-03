# NYC Drivable Roads — MSFS 2024 scenery add-on

Goal: repair New York City's roads and road bridges in Microsoft Flight
Simulator 2024 so the player can drive a controllable ground vehicle across
all five boroughs on continuous, physically supported surfaces — delivered in
measured releases with an auditable inventory and test evidence.

> **Current release: R0 — toolchain and demonstration-route definition.**
> Nothing has been tested in the simulator yet, no package has been compiled
> and no real NYC data has been processed. See [STATUS.md](STATUS.md) for
> exactly what is done, tested, unfinished and blocked, and
> [docs/00](docs/00-environment-inspection.md) for why.

## How it works

1. **Inventory** — OSM roads inside the borough boundaries become segments,
   junctions, bridge decks, ramps and grade separations with stable IDs. This
   is the denominator for "every road".
2. **Heights** — ground roads follow a despiked, smoothed bare-earth DEM
   anchored at junctions; bridge decks use explicit deck controls (lidar
   bridge-deck class / engineering data) and never the terrain or water below.
3. **Surfaces** — road ribbons, watertight junction pads, skirts, deck slabs
   and barriers; a separate collision node per 1 km tile model; placement at
   absolute altitude.
4. **Checks** — offline geometry checks (gaps, kinks, clearances, overlaps).
   These are *not* driving tests.
5. **Driving evidence** — SimConnect telemetry from a human driving the
   player vehicle is analysed for fall-through, floating, level jumps,
   invisible obstacles and recoveries. Only this promotes a segment to
   `driven` / `verified`.
6. **Coverage** — map + tables of km per status per borough.

## Quick start

```bash
pip install -e ".[dem,dev]"
python -m pytest                     # offline tests on a synthetic network
```

Then follow [docs/03 — demonstration route](docs/03-demo-route.md).

## Documentation

| Doc | |
|---|---|
| [00 Environment inspection](docs/00-environment-inspection.md) | what was inspected; host inspection script |
| [01 Project boundary](docs/01-project-boundary.md) | scope, city-limit policy, GWB extension, tunnels |
| [02 Technical approach](docs/02-technical-approach.md) | architecture, **SDK verification register**, Gate G1 |
| [03 Demonstration route](docs/03-demo-route.md) | Pulaski Bridge corridor, data steps, D1–D10 driving tests |
| [04 Vehicle](docs/04-vehicle.md) | vehicle decision procedure, controls, recovery |
| [05 Data and licensing](docs/05-data-sources-and-licensing.md) | sources, ODbL, accuracy limits |
| [06 Test protocol](docs/06-test-protocol.md) | statuses, checks, telemetry, screenshots, performance |
| [07 Build / install / remove](docs/07-build-install.md) | |
| [08 Roadmap](docs/08-roadmap.md) | releases R0–R7 |

## Repository layout

```
src/nycroads/      pipeline + test tooling (Python)
tests/             offline tests; tests/synthetic.py is a SYNTHETIC network, not NYC
config/            msfs_gltf.json — every MSFS-specific glTF name, pending verification
data/              crossings, tunnels, boundary policy, deck controls, vertical reference
releases/          release configs (r0-demo.json)
package/           MSFS project/package source per release
tools/             Windows scripts: host inspection, package build
vehicle/           vehicle target specification
```

Data attribution: road data © OpenStreetMap contributors, ODbL 1.0 — see
[ATTRIBUTION.md](ATTRIBUTION.md).
