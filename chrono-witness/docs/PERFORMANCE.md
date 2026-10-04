# Performance

Performance is an acceptance requirement for CHRONO WITNESS. This document defines the target, the
reference system, how to measure, the budgets the content is built to, and every result measured so far,
with its environment.

> **Honest status:** the development environment for this slice is a cloud container **without a GPU**.
> Chromium there renders with **SwiftShader**, a CPU implementation of Vulkan/GL, at roughly 0.5–3 fps for
> any 3D scene. Those numbers are recorded below to show the tooling works, and to record
> hardware-independent metrics (draw calls, triangles, memory, load times). They say **nothing**
> about frame rate on real hardware. **No FPS result on real hardware has been measured yet.** The
> 60 fps target is unverified until the procedure below is run on the reference system.

## Target and reference system

| | |
|---|---|
| Target | 60 fps average at 1920 × 1080, Medium preset, 1% lows ≥ 50 fps, no recurring frame-time spikes |
| Optional | 120/144 fps cap and adaptive target for high-refresh displays (High preset or reduced resolution scale) |
| Reference desktop | Windows 11, Google Chrome (current stable), AMD Ryzen 5 5600X (6C/12T), NVIDIA GeForce RTX 3060 12 GB, 16 GB DDR4, 1920 × 1080 @ 60 Hz display, power plan "Balanced" |
| Minimum class (expected to need Low) | 4-core CPU, GTX 1050 Ti / Radeon RX 560 / recent integrated graphics (Intel Iris Xe, Radeon 680M) |

## How to measure (reference system)

In-game benchmark:
1. Main menu → **Performance Benchmark**.
2. Choose a route. Each route runs 30 s after a 2 s warm-up, using the current settings.
3. The result screen shows average FPS, 1% lows, average/p99/max frame time, spike count, peak draw
   calls and triangles, geometries/textures/programs, JS heap, the GPU string, canvas size and preset.
4. **Download JSON** saves the full record.

Routes:

| Route | What it stresses |
|---|---|
| `ww1_explore` | Normal exploration: Fleet Street → Pall Mall → Haymarket → village → farm |
| `ww1_crowd` | The densest NPC section: ration party, sentries and sitting soldiers in Fleet Street |
| `ww1_barrage` | The major effect: a sustained bombardment around the shelter (impacts, particles, flashes, camera shake) |
| `hq` | Headquarters walkthrough |
| `travel` | HQ ⇄ Western Front three times, measuring load times, then exploring HQ (to catch leaks: heap, geometries and textures should return to a stable baseline) |

Automated, from a shell:

```bash
npm run dev
node tools/bench.mjs http://localhost:5173/ 1920 1080 medium 30 ww1_explore,ww1_crowd,ww1_barrage,hq,travel --gpu
```

`--gpu` launches Chromium with hardware acceleration. The JSON written to `bench-results/` records the
environment (user agent, GPU renderer string, canvas size, DPR, preset and all graphics settings).
Record with every result: browser and version, CPU, GPU and driver version, RAM, resolution, preset
and route.

The **F3** overlay shows live FPS, 1% low, frame time, draw calls, triangles and the current
resolution scale during normal play.

## Budgets the content is built to

These are hardware-independent and were measured in this repository with `renderer.info`.

Western Front, Fleet Street view, Low preset:

| Pass | Draw calls | Triangles |
|---|---|---|
| Main pass | 307 | 497 k |
| Including the sun shadow pass | 474 | 863 k |

Main-pass breakdown for that view:

| Content | Draw calls | Triangles |
|---|---|---|
| Terrain | 26 | 214 k |
| Visible characters (LOD0/LOD1, frustum-culled) | 46 | 99 k |
| Trench dressing batches and props | 106 | 81 k |
| Instanced sandbags and duckboards | 28 | 64 k |

Optimisations applied after measuring. Before these changes, the same view drew 626 calls and 1.13 M
triangles.

| Change | Effect |
|---|---|
| Skinned characters frustum-culled per NPC; character LOD1 detection fixed | 186 → 46 draws, 456 k → 99 k triangles |
| 195 crater-pond water meshes merged into one | 195 → 1 draws |
| Terrain in 32 m chunks with a ⅓-resolution LOD beyond 72 m | — |
| Sandbag and duckboard instancing in 24–32 m cells, with low-poly LODs beyond 38 m | — |
| Dressing batched per material in 48 m cells | — |
| Camera far plane clamped to the haze visibility limit (460 m on the Western Front) | — |
| Low preset refreshes the sun shadow map every other frame | — |
| NPC animation updates throttled beyond the animation-LOD distance and when off-screen; NPCs culled beyond 90 m | — |

Other measures:

| Area | Measures |
|---|---|
| Loading and memory | Only the active destination is resident. Leaving a chapter disposes its geometry, materials, textures, render targets and colliders. Shaders are precompiled during loading (`compileAsync`). |
| Lights | Interior lamps use a fixed pool of point lights moved to the nearest lamps (3 on the Western Front, 5 in London for fires, shelter lamps and incendiaries), so the light count never changes and shaders never recompile at runtime. The HQ uses 2 real-time point lights plus emissive surfaces. |
| Effects | Rain is fully GPU-animated (2.5k–12k instanced streaks, scaled by preset). Particles come from fixed pools (220 dust, 90 smoke). |
| Textures | 1024² JPEG PBR sets. The Low preset downsamples to 512² at load, and anisotropy follows the preset. |

## Measured results

### Software rendering (SwiftShader). Not representative of any real GPU.

Environment for every row below:

| | |
|---|---|
| Browser | Headless Chromium 141 (Playwright build 1194), `--use-angle=swiftshader` |
| GPU string | `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)` |
| Hardware | Cloud container, 4 vCPU, 15 GB RAM, no GPU |
| Settings | Adaptive quality off, FPS cap off; resolution and preset as listed |

Low preset, 960×540 window (720×405 render at 0.75 resolution scale), 10 measured seconds per route.
Source files: `bench-results/bench-low-960x540-*.json` (latest run used for the Western Front rows;
the HQ row is from the first run, 2026-10-04 00:17 UTC).

| Route | Avg fps | 1% low | p99 frame | Peak draw calls | Peak triangles | JS heap |
|---|---|---|---|---|---|---|
| Western Front — exploration | 0.8 | 0.5 | 1833 ms | 648 | 1.17 M | 96 MB |
| Western Front — crowded trench | 0.6 | 0.5 | 1967 ms | 673 | 1.21 M | 134 MB |
| Headquarters walkthrough | 2.6 | 0.9 | 850 ms | 389 | 0.67 M | 96 MB |

Every frame counts as a spike on software rendering, so the spike counts are meaningless here and
are omitted. Peak triangles include the shadow pass.

**1920×1080 attempts failed.** A Medium run at 1080p measured 0.2 fps on the exploration route
(569 draw calls, 0.95 M triangles), then the headless browser lost its page; the Low and High runs
at 1080p also ended with the page closing before any route completed. No 1080p result exists.

**London (Blitz) and the bombardment / travel routes have not been measured** in this environment
yet. Their routes exist (`ldn_street`, `ldn_tube`, `ldn_raid`, `ww1_barrage`, `travel`).

What the software numbers do show:

- Draw calls and triangles per route, which carry over to real hardware.
- JS heap stays around 95–135 MB in the Western Front chapter.
- The repeated-travel memory check has **not** completed in this environment, so leaks across loads
  are not ruled out by measurement (the disposal code is in `src/render/Disposal.ts`).

### Reference system

**Not measured yet.** Run the procedure above and add a table with the full environment for each run.
