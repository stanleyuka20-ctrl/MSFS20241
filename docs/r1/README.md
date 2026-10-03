# R1 — real demonstration-area data and generated geometry

Session date 2026-10-03. Environment: the same remote Linux container as R0
(no Windows, no MSFS 2024, no SDK). This release therefore contains **data
processing and geometry generation only**. Nothing here has been compiled with
the SDK, loaded in the simulator or driven. See [STATUS.md](../../STATUS.md).

## 1. Data actually used

| Data | Source | Licence | Verified here |
|---|---|---|---|
| Road network | Overture Maps release `2026-09-23.1`, transportation/segment (OSM-derived) via `s3://overturemaps-us-west-2` | ODbL-1.0 — © OpenStreetMap contributors; Overture Maps Foundation | 505,391 road rows for the NYC bbox; converter handles fractional bridge/tunnel/level rules (240 ways split at rule boundaries in the demo window) |
| Borough boundaries | Overture divisions/division_area, US-NY counties (New York, Kings, Queens, Bronx, Richmond) incl. territorial water | ODbL-1.0 | Mid-span points of Pulaski, Brooklyn and Verrazzano bridges fall inside the union |
| Bare-earth DEM | USGS 3DEP 1 m, project `NY_CMPG_2013`, tiles x58y451, x58y452, x59y451, x59y452 (+ x59y450 for the test pad) | Public domain | Tile metadata: NAD83/UTM 18N, **NAVD88 metres**, collected 2013-08-06 … 2014-04-21 |
| Classified lidar | USGS 3DEP EPT `NY_NewYorkCity` (`s3://usgs-lidar-public`), classes 2 + 17 (+1 for gap fill) | Public domain | **Vertical datum established empirically**: class-2 returns vs the NAVD88 DEM over 200,000 points: median 0.000 m, MAD 0.02 m, p5/p95 ±0.07 m → same survey, NAVD88 metres (`nycroads check-lidar-datum`) |

Provenance records: `data/provenance/*.source.json`. Raw files are not
committed (`data/raw/`, `data/dem/`); reproduce them with the commands in
[docs/09](../09-windows-handoff.md#2-reproduce-the-data-optional).

Known data limitations: Overture has no `lanes` attribute, so widths use the
class defaults unless OSM `width` is present (most NYC streets); the survey is
2013–14 (changes since then are not reflected); NAD83(2011)↔WGS84 are treated as
identical for DEM sampling (~1 m horizontal), which does not affect road heights
on smooth surfaces but is recorded.

## 2. Citywide denominator (first measured)

`nycroads inventory --release releases/citywide-inventory.json` (km summed from segment lengths; an accumulation-rounding bug in the first summary was found and fixed — it under-reported by 0.7 km):

| Borough | In-scope segments | In-scope km |
|---|---:|---:|
| Manhattan | 9,303 | 1,018.2 |
| Brooklyn | 24,714 | 2,690.7 |
| Queens | 41,272 | 4,231.8 |
| Bronx | 15,311 | 1,574.7 |
| Staten Island | 15,397 | 1,600.0 |
| **Five boroughs** | **105,997** | **11,115.4** |
| GWB NJ extension (placeholder box, too generous — refine in R5) | 900 | 73.0 |

Also: 1,410 bridge decks, 1,640 ramp groups, 3,787 grade separations (4
indeterminate), 412 tunnel segments, 395 boundary cuts, 33 bridge cuts at the
city limit. 7,148 ways of Overture class `unknown` are excluded and listed
(`highway=road`); they need review because some may be public roads.

## 3. Findings from real data (and what changed in the generator)

| Finding | Evidence | Change |
|---|---|---|
| Per-node "junction pad" geometry cannot represent real NYC junction clusters | 129 trim conflicts, 54 overlaps, 6 invalid pads on the first real build | Replaced with continuous surfaces per level (`surface.py`): union footprints, constrained Delaunay without Steiner points, height = blend of centreline profiles. Watertight by construction (tested) |
| **Streets carried on structures that OSM does not tag as bridges** (11th Street / Jackson Avenue over the Queens–Midtown Tunnel / LIE trench) | Lidar shows a continuous road at ~6.2 m; bare-earth DEM shows the trench floor at ~2.2 m → 3–4 m holes in DEM-based roads | Ground roads use lidar road-surface returns (class 2, else class 17 only when continuous with nearby ground — never an overpass above) with the DEM as fallback (`lidarsurface.py`). 1,134 of 7,852 stations in the demo use class-17 deck returns |
| Bare-earth DEM drops at bridge abutments | Approach profiles pulled 3–5.5 m low at the Pulaski and LIE abutments | Measured decks set their abutment heights; DEM ignored within 15 m of them; approaches continue the deck grade |
| DEM junction heights under structures | Borden Ave at 27th St anchored at −1.6 m (the creek under the Borden Ave bridge) | DEM junction heights accepted only when continuous with lidar ground; otherwise left to the profiles |
| Smoothing spline invented a 0.6 m hump over the unmeasured Pulaski bascule span | Preview render | Shape-preserving (PCHIP) interpolation through controls |
| Pulaski bascule leaves are lidar class 1, not 17 | 52–67 class-1 returns per station at 16.2–16.4 m | Class-1 gap fill between class-17 controls, only within 1 m of the class-17 line, labelled per control |
| Long LIE viaduct stretches have no deck returns | 236 m segment with none; 360 m unmeasured end | Decks with long unmeasured runs are **blocked**, not extrapolated |
| Queens–Midtown Tunnel open-cut approach: split-level ramps share OSM nodes (−2.3 m vs +3.6 m) | Height conflicts | 9 segments excluded by ID with reason (tunnel feasibility task); see `releases/r0-demo.json` |
| Twin carriageways / ramps beside streets overlap with default widths | Overlaps, height conflicts | Voronoi midline split; raised pieces become separate surfaces with wall-height skirts; decks never merged |

## 4. Demonstration route result (geometry only)

Build `releases/r0-demo.json` (selection window 40.7340–40.7480 N,
73.9580–73.9440 W):

* **377 segments / 33.4 km generated, 0 with geometry errors** (the build log's "4 with errors" are the blocked LIE deck segments, which are not generated), 7 surface
  groups, 9 tiles, 51,707 visual / 18,356 collision triangles.
* **All five required features present in the real data**
  (`build/r0-demo/demo_acceptance.json`): intersections, ≥3 % slopes (Pulaski
  approach 5.2 %), bridge with approaches (Pulaski Bridge, both carriageways,
  plus 49th Ave and 21st St decks), roads beneath structures (Clay Street under
  the Pulaski approach, and others), 46 transitions to default scenery.
* Deck heights: Pulaski northbound/southbound 33/32 lidar controls each
  (5 class-1 gap fills on the bascule), crown 16.4 m NAVD88; 49th Ave 5; 21st St 4.
* **Blocked (14 segments + 2 decks):** 5 Queens–Midtown Tunnel segments, 9
  tunnel open-cut approach segments, both LIE viaduct decks (unmeasured runs).
* Warnings for review: 31 warped junctions (smoothly blended), a service ramp
  at 23 % (tracked, not in the denominator), the LIE at 6.05 % vs a 6 % review
  threshold, two 4 % service-road kinks.

Previews (renders of generated geometry — **not simulator screenshots**):
`docs/r1/previews/`. Test pad: `docs/r1/previews/g1/`.

## 5. Gate G1 test pad

A small designed layout (`src/nycroads/testpad.py`) on the disused runway area
of Floyd Bennett Field — chosen after checking real data: no buildings
(Overture) in the 588 × 340 m area, DEM 3.6–4.2 m (p5–p95). It contains a 4-way
intersection, a 300 m flat strip, a deck climbing at 5 % to ~5 m above ground
with every grade change spread over 20 m, an 8 % descent for hill starts, and a
street passing beneath the deck with 3.8 m clearance. 8 segments, 0 errors.
Package source: `package/nycroads-g1-testpad/`.

## 6. Driving test plans

`docs/r1/g1-testpad/TEST_PLAN.md` and `docs/r1/r0-demo/TEST_PLAN.md` give exact
start coordinates, headings and segments for D1–D10, generated from the builds
(`nycroads test-plan`).
