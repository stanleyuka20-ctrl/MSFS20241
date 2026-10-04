# CHRONO WITNESS

A first-person historical time-travel adventure built with **Three.js + TypeScript**. From a near-future
headquarters you travel to historical moments, explore what those places may have looked like and
complete fictional, personal missions. The documented outcome of major events never changes.

> **Status: vertical slice.** The **Headquarters** and the **Western Front, Somme sector, October 1916**
> chapter are playable from start to finish, and an automated playthrough checks every mission stage.
> The other seven destinations are registered in the destination selector as **in development**.
> Each has research notes and a planned mission outline, but no playable content yet, so the full game
> is not finished. See [Status by destination](#status-by-destination) and [Known limitations](#known-limitations).

## Contents

- [Run it](#run-it)
- [Controls](#controls)
- [What is in the slice](#what-is-in-the-slice)
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

## What is in the slice

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

## Status by destination

| Destination | Status |
|---|---|
| Headquarters | Playable |
| Western Front, Somme, Oct 1916 | **Playable**, full mission chain verified by automated playthrough |
| London Blitz, 1940 | In development (research notes and mission outline only) |
| Normandy, June 1944 | In development (research notes and mission outline only) |
| Berlin, April 1945 | In development (research notes and mission outline only) |
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
    chapters/    registry, shared types, HQ, WW1 (layout, terrain, dressing, dugouts, village, props, world, runtime),
                 planned (in-development destinations)
  public/assets/ textures/ (procedural PBR sets + fx), characters/ (GLB characters, animations, first-person arms)
  tools/         smoke.mjs, playthrough.mjs, shots.mjs, bench.mjs, assets/ (texture + character generators)
  tests/         vitest unit tests
  docs/          history research, asset contract, performance, previews, screenshots
```

## Testing

```bash
npm test                                   # vitest unit tests (missions, facts, nav, controller, presets, stats)
npm run dev &                               # then, in another shell:
node tools/playthrough.mjs                 # full automated playthrough of the WW1 chapter (49 checks)
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

Last result: `tests/playthrough-result.json`.

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
- **Fiction:** the units, people, trench and farm names, the diary and all objectives are fiction.
- **Research files:** [`docs/history/ww1_somme_1916.md`](docs/history/ww1_somme_1916.md) and
  `.json` hold 46 facts and 14 scanner entries, with 56 sources (Imperial War Museums, National Army
  Museum, Western Front Association and others).
- **Corrections adopted from research:** the message form is Army Form C.2121, in Army Book 153. The
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

- **Only one historical chapter is playable.** The seven other destinations are not implemented (see
  the table above). Hiroshima in particular has only research and depiction guidance.
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
- **NPC navigation:**
  - NPCs follow authored waypoint graphs built from the trench centrelines. There is no general navmesh.
  - In narrow trenches NPCs wait for the player rather than squeezing past.
