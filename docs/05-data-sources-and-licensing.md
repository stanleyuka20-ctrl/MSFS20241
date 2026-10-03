# 05 — Data sources, licensing and accuracy

Every raw download is stored with a provenance record (`*.source.json`:
endpoint/URL, query, retrieval time, licence). Releases list the sources used.
This page is guidance for the project, not legal advice; confirm each
provider's current terms when downloading.

## Sources

| Data | Source | Licence / terms (verify at download) | Use |
|---|---|---|---|
| Road centrelines, attributes (`highway`, `lanes`, `width`, `oneway`, `layer`, `bridge`, `tunnel`) | OpenStreetMap via Overpass API | **ODbL 1.0**, attribution "© OpenStreetMap contributors" | Inventory, alignments, connectivity |
| Borough boundaries | OSM admin relations (ODbL) or NYC Open Data *Borough Boundaries* | ODbL / NYC Open Data terms of use | Project boundary |
| Official street centreline (cross-check) | NYC Dept. of City Planning **LION** (NYC Open Data) | NYC Open Data terms | Validate alignments / names; optional |
| Bare-earth DEM | NYC Open Data **1 ft DEM** (2017 lidar-derived; NY State Plane Long Island, US survey feet, NAVD88) or **USGS 3DEP 1 m DEM** (UTM, metres, NAVD88) | NYC Open Data terms / USGS public domain | Ground-road profiles |
| Classified lidar point cloud | NYC 2017 topobathymetric lidar or USGS 3DEP point clouds | Provider terms / public domain | Bridge-deck controls (class 17), DSM fallback |
| Bridge clearances / drawings | NYC DOT, MTA Bridges & Tunnels, NYSDOT, Port Authority (GWB) publications | Per document | Deck controls where lidar is missing; clearance checks |
| Imagery for review only | Provider of the reviewer's choice | Do **not** trace from imagery unless its licence allows derived data | Visual QA |

## Obligations that affect releases

* **ODbL share-alike:** the inventory and coverage GeoJSON/CSV files are
  derived databases of OSM. If distributed, they must be offered under ODbL
  with attribution. The add-on's 3D models are a *produced work*; ship an
  attribution notice ("Contains data © OpenStreetMap contributors, ODbL") in
  the package's documentation and the coverage map.
* Keep any provider's required attribution text in `ATTRIBUTION.md`.
* Do not bundle third-party vehicle add-ons or simulator assets.

## Accuracy limitations (record per release)

* **Horizontal (OSM):** contributor-mapped; accuracy varies by street. Check
  alignment against LION and imagery in the demo area and record observed
  offsets in the release notes. `width` tags are sparse: widths fall back to
  lanes × 3.35 m + class shoulder (`width_source` column says which).
* **`layer` is relative, not a height.** It orders crossing ways only;
  absolute heights come from the DEM (ground) and deck controls (bridges).
  Crossings without a layer difference are reported as *indeterminate grade
  separations* for manual review.
* **DEM:** take the stated vertical accuracy from the product metadata and
  record it. Bare-earth DEMs remove bridges and may remove parts of elevated
  approaches; heights near walls, under trees and at structures are less
  reliable — hence despiking + smoothing anchored at junctions.
* **Vertical datums:** NAVD88 (DEM) ≠ ellipsoid ≠ the simulator's height
  reference. Conversions are explicit and recorded (`data/vertical_reference.json`);
  the simulator side is calibrated in-sim (V7).
* **Units:** NYC State Plane products use **US survey feet**
  (1 ftUS = 1200/3937 m); USGS products use metres. Set `z_units` correctly.
* **Bridge decks:** lidar returns can include vehicles, lamp posts and
  cables; the control extractor rejects outliers and records point count and
  spread per control. Long spans have dead-load camber and thermal variation
  of decimetres; controls are a snapshot of survey conditions.
