# 07 — Build, install and remove

## Prerequisites

* **Pipeline (any OS):** Python ≥ 3.10. `pip install -e ".[dem,dev]"`
  (`dem` adds rasterio for GeoTIFF DEMs). Lidar deck controls additionally need
  `pip install "laspy[lazrs]"`.
* **Package build and testing (Windows):** MSFS 2024, the MSFS 2024 SDK
  (installed from the simulator's Developer Mode), and for telemetry
  `pip install -e ".[sim]"`.

## Build

```bash
python -m pytest                                   # 31 offline tests (synthetic fixture)
nycroads inventory --release releases/r0-demo.json
nycroads build     --release releases/r0-demo.json [--allow-unverified]
nycroads coverage  --release releases/r0-demo.json
```

`build` writes:

* `build/r0-demo/models/*.gltf|.bin` — one model per 1 km tile
* `build/r0-demo/build_report.json` — issues, blocked items, tiles, start locations
* `build/r0-demo/profiles.json` — the road height profiles (used by the telemetry analyser)
* `build/r0-demo/demo_acceptance.json` — demo-route criteria
* `package/nycroads-r0-demo/PackageSources/…` — model library + placement XML

Compile the package on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_package.ps1 -Project package\nycroads-r0-demo\nycroads-r0-demo.xml
```

or open the project in the simulator's Developer Mode Project Editor and use
its build command (record which method was used). Before the first real
build, complete V1–V6 in [docs/02](02-technical-approach.md#verification-register):
the safest path is to create an empty Scenery project with the installed SDK,
then copy `PackageSources` content from this repository into it, so the
project/package definitions are the SDK's own.

## Install

1. Find the Community folder: `InstalledPackagesPath` in `UserCfg.opt`
   (reported by `tools/inspect_host.ps1`) + `\Community`.
2. Copy the built package folder (`package\nycroads-r0-demo\Packages\nycroads-r0-demo`)
   into `Community`.
3. Start the simulator. Load the demo area; check the orientation marker (V6).

Packages from different releases are separate folders
(`nycroads-r0-demo`, later `nycroads-<district>`), so districts can be added
or removed independently. Never install two releases that cover the same tiles.

## Remove

Quit the simulator and delete the package folder(s) `nycroads-*` from
`Community`. The add-on changes nothing outside its own folder.

## Reproducibility

Inputs are the OSM extract(s) with `.source.json`, the DEM file (record its
product name/version in the release notes), `data/deck_controls.json`,
`data/vertical_reference.json` and `config/msfs_gltf.json`. With the same
inputs the build is deterministic (stable segment IDs, UUIDv5 model GUIDs).
