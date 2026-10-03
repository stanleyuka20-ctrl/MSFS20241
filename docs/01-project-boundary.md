# 01 — Project boundary and scope

## Geographic scope

* **In scope:** the five boroughs — Manhattan (incl. Roosevelt, Randalls/Wards
  islands), Brooklyn, Queens (incl. the Rockaways), the Bronx, Staten Island.
  Boundaries come from the OSM administrative relations identified by Wikidata
  ID (Manhattan Q11299, Brooklyn Q18419, Queens Q18424, Bronx Q18426, Staten
  Island Q18432) — or, preferably for releases, NYC Open Data *Borough
  Boundaries* (public domain); see docs/05.
* **Bridge approaches** between boroughs are inside the union of the borough
  polygons (which extend to the mid-water boundary lines), so inter-borough
  bridges are fully in scope.
* **Documented extension:** the George Washington Bridge and its New Jersey
  approach into Fort Lee (`data/extensions.geojson#GWB-NJ`, placeholder
  polygon, refined in R5).

## What counts as a road ("every road" denominator)

Implemented in `src/nycroads/config.py` and `inventory.classify_way`:

| Included (`in_scope`) | OSM `highway=` motorway, trunk, primary, secondary, tertiary, unclassified, residential, living_street and all `*_link` ramps |
|---|---|
| Tracked, not counted (`secondary`) | `service` roads other than driveways / parking aisles / drive-throughs / emergency access |
| Excluded | `access`/`motor_vehicle`/`motorcar`/`vehicle` = no, private, customers, delivery…; footway, cycleway, pedestrian, path, steps, busway, track, construction, proposed; areas |

Coverage figures are reported per borough and status as **segment counts and
kilometres** of `in_scope` segments (`coverage/COVERAGE.md`). A citywide
completion claim requires 100 % of in-scope km at `verified`, with blocked
segments listed individually.

## Where coverage ends at the city limit

Policy (implemented in `inventory._drop_outside`, tested):

1. Roads are cut where they leave the project area. The cut node is recorded
   as a `boundary_cut` junction; beyond it the default scenery continues the
   road. The repaired surface meets the default terrain there (the R0 demo
   checks this transition explicitly).
2. **A bridge deck that crosses the limit is excluded entirely.** Coverage ends
   at the last land junction before it (`boundary_bridge_cut`), never
   mid-span. This applies to the **Goethals Bridge, Outerbridge Crossing and
   Bayonne Bridge** (Staten Island ↔ New Jersey).
3. Main land-boundary corridors (Bronx ↔ Westchester; Queens ↔ Nassau) are
   listed in `data/boundary_connections.json`; the exhaustive list is the
   set of `boundary_cut` junctions produced by the inventory.

## Tunnels

Tunnels are a **separate feasibility task**. Tunnel segments (`tunnel=yes`)
are inventoried, shown dashed on the coverage map and reported as `blocked`.
No surface road is ever generated in place of a tunnel, and no connection is
created across water where the real route goes underground.

| Tunnel | Connects | Status |
|---|---|---|
| Hugh L. Carey (Brooklyn–Battery) | Manhattan – Brooklyn | blocked: feasibility |
| Queens–Midtown | Manhattan – Queens | blocked: feasibility |
| Lincoln | Manhattan – New Jersey | blocked: feasibility; NJ side outside boundary |
| Holland | Manhattan – New Jersey | blocked: feasibility; NJ side outside boundary |
| Short tunnels / underpasses tagged `tunnel=yes` | various | blocked individually |

Feasibility questions to answer before any tunnel work are in
`data/tunnels.json` (vehicle support below terrain, portal openings in
terrain/photogrammetry, interior lighting).

## Major crossings

`data/crossings.json` lists named crossings with stable IDs (`XS-*`), the
boroughs they connect, a structural note, and the release in which each is
planned. Bridges required by the brief: Brooklyn, Manhattan, Williamsburg,
Queensboro, RFK, Bronx–Whitestone, Throgs Neck, Verrazzano-Narrows, George
Washington (extension) — plus ~20 smaller crossings already listed. All other
road bridges are discovered automatically from OSM `bridge=*` tags and get
`BRG-*` deck IDs.
