# 00 — Environment inspection

Two environments matter: the **development container** where this repository
was created, and the **simulator host** (Windows PC with MSFS 2024) where the
add-on is built, installed and driven. Results recorded here decide what may
be claimed in a release.

## A. Development container (inspected 2026-10-03, Release 0)

| Item | Finding | Consequence |
|---|---|---|
| OS | Ubuntu 24.04 (Linux x86-64), 4 vCPU, 15 GB RAM, no GPU | MSFS 2024 is Windows-only (and Xbox). It **cannot run here** |
| MSFS 2024 | Not installed (not installable) | No in-game test, screenshot or performance measurement was possible |
| MSFS 2024 SDK | Not installed; `fspackagetool`, Scenery Editor, Project Editor unavailable | No package was compiled; SDK file formats could not be checked against an installed SDK |
| SimConnect | Not available | Telemetry recorder/recovery code is untested against a live simulator |
| Blender / MSFS exporter | Not installed | Models are written directly as glTF 2.0 by the pipeline |
| Python | 3.11 with numpy, shapely 2.1, pyproj 3.7, networkx, pygltflib | Pipeline and 30 automated tests run here |
| Network | Policy allows package registries and GitHub only. **Denied:** `overpass-api.de`, `api.openstreetmap.org`, `planet.openstreetmap.org`, `download.geofabrik.de`, `data.cityofnewyork.us`, `tnmaccess.nationalmap.gov` (USGS), `docs.flightsimulator.com`, `learn.microsoft.com`, `www.nyc.gov` | No real road, boundary or elevation data was downloaded, and the online SDK documentation could not be read. The pipeline was tested on a **synthetic** network only (`tests/synthetic.py`) |

What this means for Release 0: everything that needs the simulator or real
data is delivered as **tooling + procedure + acceptance criteria**, and is
marked *not done* in [`STATUS.md`](../STATUS.md). Nothing is claimed as
tested in-game.

To let a later session fetch data from this container, an environment admin
can add the denied hosts above to the environment's network allow-list
(cloud environment settings → Network access → Custom). Otherwise run the
`fetch` steps on the simulator host.

## A2. Development container, second session (2026-10-03, R1)

Same container type: Linux, no Windows/MSFS/SDK, no access to the user's PC or
Community folder. The network policy still denies OSM/Overpass, NYC Open Data,
USGS web APIs and the MSFS documentation, **but these public AWS buckets are
reachable**: `overturemaps-us-west-2` (Overture Maps), `prd-tnm` (USGS 3DEP
DEMs), `usgs-lidar-public` (USGS 3DEP EPT lidar), `noaa-nos-coastal-lidar-pds`.
R1 used them for all real data (docs/r1/README.md). Everything that needs the
simulator remains undone; see docs/09.

## B. Simulator host (to be run before any build — gate G0)

Run the read-only inspection script from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools\inspect_host.ps1
```

It writes `docs/host-inspection.json` with: Windows version, CPU/RAM/GPU,
MSFS 2024 edition (Microsoft Store package `Microsoft.Limitless` or Steam app
manifest) and version/build id, `InstalledPackagesPath`, SDK location
(`MSFS2024_SDK`), `fspackagetool.exe` and `SimConnect.dll` versions, and every
Community package (title, type, creator, version) flagged when it may be NYC
scenery or a ground vehicle. Commit the JSON with the release it was used for.

Then complete this checklist by hand (the script cannot see inside the sim):

- [ ] Simulator version shown in the main menu / Developer Mode matches the JSON.
- [ ] SDK version matches the simulator version (SDK release notes). If not, update the SDK first.
- [ ] Open the SDK's **local** documentation (installed with the SDK) — record its version in `docs/host-inspection.json` → `sdk.docs_version`.
- [ ] Work through [the verification register](02-technical-approach.md#verification-register) items V1–V12 and record each result.
- [ ] Disable Community packages flagged as *possible NYC scenery conflict* while testing (record which).
- [ ] List vehicles available to the player (default and Community) for [vehicle selection](04-vehicle.md).
- [ ] Record graphics preset, resolution, render scaling, frame generation/upscaler, and whether photogrammetry and online data are on — needed for every test record.
