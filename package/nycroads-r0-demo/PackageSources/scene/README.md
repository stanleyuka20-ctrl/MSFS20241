`nycroads build --release releases/r0-demo.json` writes `nycroads-r0-demo.xml` (object placements) here.

Terrain-flatten / exclusion polygons authored in the simulator's Scenery Editor are saved by the
SDK into an XML in this folder as well. Keep those in a separate file (e.g. `editor-polygons.xml`)
so regenerating road placements never overwrites hand-authored work.
