# CHRONO WITNESS

A first-person historical time-travel adventure built with **Three.js + TypeScript**. From a near-future
headquarters you travel to historical moments, explore what those places may have looked like and
complete fictional, personal missions. The documented outcome of major events never changes.

> **Status: work in progress — 3 of 8 historical chapters playable.** The **Headquarters**, the
> **Western Front (Somme, October 1916)**, **London during the Blitz (September 1940)** and **Berlin after
> the surrender (18 May 1945)** are playable from start to finish, and an automated playthrough checks
> every mission stage of each chapter. London's and Berlin's characters are still **stand-ins**
> (recoloured WW1 models) until their period casts are made. The other five destinations are registered
> in the destination selector as **in development**, with research files and a planned mission outline
> but no playable content, so the full game is not finished. See [Status by destination](#status-by-destination) and [Known limitations](#known-limitations).

## Contents

- [Run it](#run-it)
- [Controls](#controls)
- [What is playable](#what-is-playable)
- [Status by destination](#status-by-destination)
- [Graphics, performance and accessibility](#graphics-performance-and-accessibility)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Adding a destination](#adding-a-destination)
- [History: documented vs reconstructed](#history-documented-vs-reconstructed)
- [Assets and credits](#assets-and-credits)
- [Known limitations](#known-limitations)

## Run it

Requirements: Node.js 20+ (tested with 22) and a desktop browser with WebGL 2 and hardware
acceleration (current Chrome, Edge or Firefox).

```bash
cd chrono-witness
npm install
npm run dev          # http://localhost:5173
```

Production build:

```bash
npm run build        # type-checks, then builds to dist/
npm run preview      # serves dist/ on http://localhost:4173
```

`dist/` is a static site. Any static file server works, and it does not need to be served from the root.
Click the view to capture the mouse. Esc releases it and pauses the game.

## Controls

| Action | Key |
|---|---|
| Look | Mouse (pointer lock) |
| Move | W A S D (or arrow keys) |
| Sprint | Shift (hold, or toggle in Settings) |
| Crouch | C or Ctrl (hold, or toggle in Settings) |
| Jump / climb onto a ledge / let go of a ladder | Space |
| Interact (hold when the prompt shows a ring) | E |
| Temporal scanner on/off (aim, then hold E to record) | Q |
| Temporal observation mode (limited energy) | F |
| Journal | J or Tab |
| Inventory | I |
| Skip an intense scripted sequence | T, or Pause menu → Skip |
| Skip a cinematic | Hold Enter |
| Dialogue choices | 1–4, or click |
| Pause menu | Esc or P |
| Performance overlay (FPS, 1% low, draw calls, triangles) | F3 |

Ladders: walk into one while facing it to climb, and walk off the top towards the ladder to climb down.
Ledges up to about 1.5 m: press Space while facing them.

## What is playable

**Headquarters (the Meridian Archive):**
- temporal gate and destination selector console
- artifact gallery that fills as you complete chapters
- historical-records terminal, with every record tagged documented, reconstruction or fiction
- the archivist, Dr. Mara Quill, who briefs you through branching dialogue
- a short orientation mission

**Western Front: "The Runner" (Somme, October 1916, fictional sector).**
Autumn rain, mud, distant guns, and a populated trench system: support line, communication trenches,
a front line of fire bays and linked shell holes, cut-and-cover dugouts, a flooded old German trench
and a ruined Picardy village.

Main mission, 10 stages with explicit unavailable/active/completed/failed states:
1. Report to the company sergeant and receive the field message (Army Form C.2121).
2. Carry it up the Pall Mall communication trench.
3. **Scripted event:** a bombardment. Reach the shelter before the timer runs out (failing returns you
   to the checkpoint). Wait it out while the trench ahead collapses. The sequence can be skipped
   without losing progress.
4. Find another route: Tottenham Sap, then flooded Old Boot Alley (wading slows you), then a ladder and
   a duckboard bridge over a crater.
5. Deliver the message to the company commander in the front line.
6. Investigate the ruined Moulin Farm: a dropped stretcher, fresh tracks, and a temporal echo of what
   happened, shown in observation mode.
7. Find a crowbar in the Royal Engineers' store and lever a fallen beam off the cellar steps.
8. Carry a wounded soldier on a stretcher with the stretcher-bearer (escort and carry). Crouch when a
   shell comes over.
9. Speak with the medical officer at the Regimental Aid Post.
10. Return to the temporal anchor.

Optional tasks:
- **A Thread of Wire:** follow the telephone cable, find the break and splice it. This changes later dialogue.
- **Words Home:** find a lost diary and return it to its owner.
- **Witness Record:** record 8 of 14 historical objects with the scanner.

Six checkpoints are saved to browser storage. You can resume, retry from the last checkpoint, replay a
chapter, and return to headquarters with progress saved. Completing the chapter catalogues artifacts
in the headquarters gallery.

**London during the Blitz: "Blackout" (late September 1940, fictional East End street).**
Night raid over Cable Row, a terraced street near the burning docks: blackout, taped windows, the
siren's warble, searchlights, anti-aircraft bursts, barrage balloons and the glow of the docks to the
south. The High Street has shops, a First Aid Post, an ARP depot, a WVS canteen van and an AFS trailer
pump towed by a taxi. Morley Road station has a booking hall, two stair flights and a tiled platform
tunnel where shelterers sit and sleep (no bunks yet in September 1940).

Main mission, 9 stages:
1. The siren: report to Warden Pike at the sandbagged ARP post and get a bucket of sand.
2. Knock at No. 9 for the Hartleys and find Joan's gas-mask box in the front room.
3. **Escort under a timer:** incendiaries land in the street as you step out. The family waits in the
   doorway while you smother them with sand (hold E). If the timer runs out a house catches fire and you
   retry from the checkpoint. Then lead the family down to the platform; they follow your exact route.
4. **Scripted event:** a high-explosive bomb hits No. 14 while you walk back. It is announced first and
   can be skipped. Find the deaf Mr Moss tapping under the stairs.
5. Report to Pike, then clear the fallen bricks and draw the bolt on the back-alley gate so the Heavy
   Rescue party can get round the crater that blocks Dock Lane. They then walk the route you opened.
6. Carry dressings from the ARP depot to the nurse (no running or climbing while carrying).
7. The rescue silence: stand still and watch the tapping marks over the rubble, then point out the
   right spot.
8. Pass timbers to the rescuers. Dawn breaks with the steady "Raiders Passed".
9. Return to the temporal anchor.

Optional tasks: **Fire-Watch** (incendiaries in the back yards, reached by the alleys), **Strong and
Sweet** (tea from the WVS canteen for the rescue party), **Witness Record** (8 of 13 objects).
Five checkpoints.

**Berlin after the surrender: "Chalk" (Friday 18 May 1945, fictional street).**
A sunny, dusty late-spring day ten days after the surrender. Lindenhofstraße has Wilhelmine tenements
with sheared-off fronts and burnt-out shells, a stranded tram, white sheets in windows, a Litfaß
pillar with the city commandant's orders, a Soviet traffic regulator at the crossing and a cast-iron
street pump with a queue. No. 12 has a carriage gateway, a courtyard with a chestnut in leaf, a side
wing with a broken stairwell and the cellar where the residents now live; the school across the street
is the ration-card office.

Main mission, 11 stages:
1. Find Frau Brandt in the courtyard and take her buckets.
2. Queue at the street pump (the queue moves only while you wait in it), pump, and carry the water
   down to the cellar (slow, no running).
3. Herr Lenz has heard nothing from his daughter since April. Read the messages chalked on a bare
   firewall at the west end, find hers, and chalk his answer underneath.
4. Fetch his papers from the second floor of the side wing: steps are missing, so carry planks from the
   woodpile and lay them across the gap.
5. Wait your turn at the ration-card office and bring back his new cards (the five-group system began
   on 15 May).
6. **Scripted event:** children have found an unexploded shell in the ruins. Send them away, tell the
   Soviet traffic regulator, and stand back while a sapper blows it up (announced first, skippable).
7. Join neighbours passing buckets of rubble from a doorway (a timed hand-over).
8. Lotte, who saw the answer on the wall, arrives at the cellar.
9. Return to the anchor.

Optional tasks: **Frau Kaminski** (a second trip to the pump), **Firewood** (broken timber for the cellar
stove), **Witness Record** (8 of 13 objects). Six checkpoints.

## Status by destination

| Destination | Status |
|---|---|
| Headquarters | Playable |
| Western Front, Somme, Oct 1916 | **Playable**, full mission chain verified by automated playthrough |
| London Blitz, Sept 1940 | **Playable**, full mission chain verified by automated playthrough. Characters are stand-ins until the period cast exists. |
| Normandy, June 1944 | In development (research notes and mission outline only) |
| Berlin, 18 May 1945 | **Playable**, full mission chain verified by automated playthrough. Characters are stand-ins until the period cast exists. |
| Hiroshima, 6 August 1945 | In development. Research notes include mandatory depiction guidance; nothing is implemented. |
| Pompeii, AD 79 | In development (needs a decision on the date: 24 August or about 24 October) |
| RMS Titanic, 1912 | In development (research notes and mission outline only) |
| Berlin Wall, 9 November 1989 | In development (research notes and mission outline only) |

Research notes are in [`docs/history/`](docs/history/).

## Graphics, performance and accessibility

**Presets:** Low, Medium, High and Custom. Low keeps the art direction by lowering render resolution,
shadow resolution and distance, AO, texture size, draw distance and rain/detail density first.

You can also set:
- FPS cap: V-Sync, 30, 60, 120 or 144
- resolution scale
- optional adaptive quality, which lowers resolution when frame time exceeds the target (60, 120 or 144 fps)

**Rendering:**
- PBR materials
- terrain shader that blends mud, earth, grass and chalk using vertex weights, with animated rain ripples in puddles
- wetness response on materials exposed to rain
- baked horizon-based ambient occlusion on terrain and revetments
- image-based lighting from the procedural sky
- camera-following, texel-snapped sun shadows
- optional GTAO, SMAA/FXAA/MSAA, and restrained bloom
- AgX tone mapping

**Performance work:**
- instancing, split into spatial cells so frustum culling still works
- terrain and sandbag/duckboard LODs
- per-NPC frustum culling and character LOD1
- animation throttling with distance
- a fixed-size pool of interior lamps, so no shaders recompile at runtime
- shaders precompiled during loading
- every chapter fully unloaded and disposed when you leave it

Measured results and how to benchmark are in [docs/PERFORMANCE.md](docs/PERFORMANCE.md).
**No FPS figure for real hardware has been measured yet.**

**Accessibility:**
- every mission can be completed without audio
- full subtitles, with speaker labels and adjustable background
- visual, directional indicators for important sounds; danger cues are always shown
- written objectives with detailed instructions in the journal
- objective markers and a visual danger indicator with a countdown
- text size, mouse sensitivity, invert Y and FOV
- camera shake, head bob and motion-effect sliders
- a reduced-flashing mode for artillery, flares and temporal transitions
- high-contrast prompts and a multiplier for timed hazards
- toggle sprint and crouch
- a prompt before intense sequences that offers a skip without losing progress
- cinematics can be skipped

## Project structure

```
chrono-witness/
  src/
    core/        Game (loop, states, chapter transitions, services), Input, Settings, Events, Random
    render/      RenderSystem (post chain), Environment (sky/IBL/sun/fog), Rain, Materials (terrain + wetness),
                 Assets (loading, fallbacks), AdaptiveQuality, PerfStats, Disposal
    physics/     CollisionWorld (three-mesh-bvh), CharacterController (capsule, step-up, mantle, ladders)
    player/      Player (camera, bob, shake), Interaction, FirstPersonHands
    npc/         CharacterLibrary, NPC (speed-matched locomotion, look-at, LOD), NPCManager, NavGraph (A*)
    missions/    MissionSystem, FactStore, data types (missions, dialogue, journal)
    save/        SaveSystem (versioned localStorage checkpoints)
    audio/       AudioSystem (procedural WebAudio + visual cue events)
    ui/          HUD, menus, settings, journal, selector, dialogue, loading, cinematic (DOM/CSS)
    bench/       Benchmark routes and result collection
    chapters/    registry, shared types, common/ (builder, geometry batching, fire, particles),
                 HQ, WW1 (layout, terrain, dressing, dugouts, village, props, world, runtime),
                 London (layout, houses, street, tube, sky, runtime), Berlin 1945 (layout, world, runtime),
                 common/urban.ts (tenement kit), common/RuntimeBase.ts, planned (in-development destinations)
  public/assets/ textures/ (procedural PBR sets + fx), characters/ (GLB characters, animations, first-person arms)
  tools/         smoke.mjs, playthrough.mjs, playthrough_london.mjs, harness.mjs, shots.mjs, bench.mjs,
                 assets/ (texture + character generators)
  tests/         vitest unit tests
  docs/          history research, asset contract, performance, previews, screenshots
```

## Testing

```bash
npm test                                   # vitest unit tests (missions, facts, nav, controller, presets, stats)
npm run dev &                               # then, in another shell:
node tools/playthrough.mjs                 # full automated playthrough of the WW1 chapter (49 checks)
node tools/playthrough_london.mjs          # full automated playthrough of the London chapter (64 checks)
node tools/playthrough_berlin45.mjs        # full automated playthrough of the Berlin 1945 chapter (43 checks)
node tools/smoke.mjs                       # boot + load screenshots
node tools/shots.mjs                       # fixed viewpoints → docs/screenshots
node tools/bench.mjs <url> 1920 1080 medium 30   # benchmark routes → bench-results/*.json
```

The playthrough runs the real game simulation with real collision in headless Chromium:
- walks every route, using navigation paths and contextual ladders
- aims at interactables, uses them and answers dialogue
- triggers and survives the bombardment
- fails on purpose under shellfire, then retries from the checkpoint
- carries the stretcher
- checks the saved data and the return to headquarters

The London playthrough also smothers the incendiaries under the timer, leads the family down to the
platform, takes the bomb sequence, retries from a checkpoint, opens the gate, carries the dressings,
completes the silence and the rescue, and does two optional tasks.

Last results: `tests/playthrough-result.json`, `tests/playthrough-london-result.json` and
`tests/playthrough-berlin45-result.json`.

The tools use the Playwright Chromium build at `/opt/pw-browsers/chromium` by default. Set
`CHROMIUM_PATH` to use another browser.

## Adding a destination

1. Add a `ChapterConfig` (see `src/chapters/types.ts`). It holds the missions, dialogue, items,
   journal/scan entries with source keys, artifacts, checkpoints (x and z only; the runtime resolves
   heights), intro and outro shots, and `load: () => import('./MyRuntime')`.
2. Implement `ChapterRuntime`:
   - `build(report)`: environment, NPCs, interactables and colliders
   - `applyCheckpoint(id)`: place the world for the restored facts
   - `update(dt)` and `scriptState()`
   - optional: `resolveSpawnHeight`, `benchmarkRoutes` and `skipSequence`
3. Register the chapter in `src/chapters/registry.ts`. It then appears in the selector, gets saving and
   checkpoints, and is fully unloaded when the player leaves.

Missions only advance from **facts** (`interact.<id>`, `zone.<id>`, `scan.<id>`, `dlg.<dialogue>.<node>`,
items and script flags). A chapter script sets facts in response to what the player does, never on a timer
alone.

## History: documented vs reconstructed

- **Journal:** every journal and scanner entry is tagged **documented** (with sources),
  **reconstruction** (plausible, not a recorded fact) or **fiction** (invented for the game).
- **Fiction:** the units, people, trench and farm names, the diary and all objectives are fiction. In
  London, Cable Row, Morley Road station, the warden, the Hartleys, Mr Moss, the rescue party and the
  nurse are fiction.
- **Research files:** [`docs/history/ww1_somme_1916.md`](docs/history/ww1_somme_1916.md) and
  `.json` hold 46 facts and 14 scanner entries, with 56 sources (Imperial War Museums, National Army
  Museum, Western Front Association and others).
- **London research:** [`docs/history/london_blitz_1940.md`](docs/history/london_blitz_1940.md) and
  `.json` hold 45 facts and 14 scanner entries with 46 sources. Corrections adopted: the all-clear is
  the "Raiders Passed" signal; September 1940 is "ARP" (the name "Civil Defence" came in 1941); there
  were no Tube bunks yet; fire-watching was still voluntary; most static water tanks and Morrison
  shelters came in 1941, so neither appears.
- **Berlin 1945 research:** [`docs/history/berlin_1945.md`](docs/history/berlin_1945.md) and `.json`:
  45 facts, 13 scanner entries, 29 sources. Corrections adopted: the date is set to 18 May 1945 (after
  the 15 May ration system, before Moscow time was ordered on 20 May); the word "Trümmerfrauen" is not
  used, because compulsory rubble work for women began on 1 June and early clearing relied largely on
  others; trams are stranded, not running; no Berliner Zeitung yet. The chalk messages and the sapper
  are marked reconstruction or fiction.
- **Research still to verify:** the files for Titanic, Hiroshima and the Berlin Wall were written after
  the research tool's web-search allowance ran out. Their facts beyond the earlier notes are tagged
  reconstruction and marked unverified in the `.md` files; they need a verification pass before those
  chapters are built and shipped.
- **Corrections adopted from research (WW1):** the message form is Army Form C.2121, in Army Book 153. The
  PH gas helmet and Small Box Respirator coexisted in late 1916. Villages in the battle zone were
  shelled flat, so the farm is a roofless ruin over an intact cellar. British clocks were on GMT
  after 1 October 1916.
- **Verification caveat:** the research sandbox could not open the cited pages directly. Facts were
  checked against search-result summaries of those pages. Every citation should be confirmed on the
  live page before release. The in-game credits say so as well.

## Assets and credits

See [ASSETS.md](ASSETS.md). In summary:
- **Textures:** all environment textures are procedural, original work.
- **Characters:** derived from **MakeHuman** CC0 assets, with original clothing, gear and textures.
- **Animation:** retargeted from the **CMU Graphics Lab Motion Capture Database** (free for commercial
  use, which allows inclusion in products), plus hand-keyed clips.
- **Audio:** fully procedural.
- **Libraries:** three.js and three-mesh-bvh, both MIT.

## Known limitations

- **Three of eight historical chapters are playable.** The five other destinations are not implemented
  (see the table above). Hiroshima in particular has only research and depiction guidance.
- **London and Berlin characters are placeholders.** Until the period cast (warden, mother and children, rescue
  men, nurse, WVS, AFS, civilians) is built, London uses the WW1 character models, recoloured to darker
  civilian/ARP tones, with helmets hidden and children scaled down. They are recognisably soldiers'
  bodies and uniforms. This is the most visible gap in the London chapter.
- **Performance is not yet measured on real hardware.** This environment has no GPU. The only
  measurements are SwiftShader CPU rendering, which is useless as a performance guide.
  [docs/PERFORMANCE.md](docs/PERFORMANCE.md) defines the reference system and the procedure; the
  60 fps @ 1080p target is a design target until it is measured there.
- **Visual fidelity is procedural.**
  - The environment is generated by code, and the textures are procedural.
  - Materials hold up at play distance. Close inspection shows tiling in some sets (the boot prints
    in `mud_wet`) and simplified wall detail (`earth_wall`).
  - Ruined buildings are procedural walls with real openings and ragged tops. They do not have
    hand-modelled detail such as timber framing or plaster.
- **Characters:**
  - They are MakeHuman-based and readable as period soldiers.
  - Faces and cloth folds are simpler than a modern AAA standard.
  - There is no facial animation or lip sync, and no voice acting (dialogue is text only, by design
    for accessibility).
- **Missing features:**
  - No rebindable keys in the UI (bindings are in `src/core/Input.ts`).
  - No gamepad support.
  - No asset compression pipeline (KTX2/Draco). Textures are 1024² JPEGs that are downscaled at load
    on Low.
- **Historical verification:** research citations were checked only against search summaries (see above).
- **London environment:** houses, shops and the station are procedural (boxes, walls with real openings,
  sloped roofs). Only Nos. 9 and 14 have interiors. Distant docks, cranes and rooftops are flat
  silhouettes. The night grade is strongly red-tinted by the fire glow.
- **NPC navigation:**
  - NPCs follow authored waypoint graphs built from the trench centrelines. There is no general navmesh.
  - In London, NPCs walk scripted routes, and the escorted family follows the player's own trail.
  - In narrow trenches NPCs wait for the player rather than squeezing past.
