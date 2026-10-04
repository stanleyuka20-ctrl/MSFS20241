import * as THREE from 'three';
import type { Game } from '../core/Game';
import { PerfStats } from '../render/PerfStats';

interface RouteDef {
  id: string;
  label: string;
  chapter: string;
  /** Route key inside the chapter runtime's benchmarkRoutes(). */
  route: string;
  /** Optional script hook name the chapter runs during the route (e.g. a barrage). */
  event?: string;
  travelLoop?: boolean;
}

const ROUTES: RouteDef[] = [
  { id: 'ww1_explore', label: 'Western Front — normal exploration (support line → village)', chapter: 'ww1_somme_1916', route: 'explore' },
  { id: 'ww1_crowd', label: 'Western Front — crowded trench (most NPCs on screen)', chapter: 'ww1_somme_1916', route: 'crowd' },
  { id: 'ww1_barrage', label: 'Western Front — major effect (bombardment sequence)', chapter: 'ww1_somme_1916', route: 'barrage', event: 'benchBarrage' },
  { id: 'ldn_street', label: 'London Blitz — night street exploration (Cable Row → High Street)', chapter: 'london_blitz_1940', route: 'street' },
  { id: 'ldn_tube', label: 'London Blitz — crowded Underground shelter', chapter: 'london_blitz_1940', route: 'tube' },
  { id: 'ldn_raid', label: 'London Blitz — major effect (fires, flak, bomb strike)', chapter: 'london_blitz_1940', route: 'raid', event: 'benchRaid' },
  { id: 'hq', label: 'Headquarters walkthrough', chapter: 'hq', route: 'hq' },
  { id: 'travel', label: 'Repeated travel: HQ ⇄ Western Front ×3 (load times, memory)', chapter: 'hq', route: 'hq', travelLoop: true },
];

/**
 * Scripted benchmark: flies the camera along a chapter route with the current settings and records
 * frame times. Results include environment details so every number is reproducible.
 */
export class Benchmark {
  private points: { pos: THREE.Vector3; look: THREE.Vector3 }[] = [];
  private t = 0;
  private duration = 30;
  private running = false;
  private stats = new PerfStats(20000);
  private resolveRun: (() => void) | null = null;
  private peakCalls = 0;
  private peakTris = 0;

  constructor(private readonly game: Game) {}

  static routes(): { id: string; label: string }[] {
    return ROUTES.map((r) => ({ id: r.id, label: r.label }));
  }

  async run(id: string, seconds: number): Promise<Record<string, unknown>> {
    const def = ROUTES.find((r) => r.id === id);
    if (!def) throw new Error(`unknown route ${id}`);
    const g = this.game;
    const loads: { chapter: string; ms: number; heapMB: number | null; geometries: number; textures: number }[] = [];
    if (def.travelLoop) {
      for (let i = 0; i < 3; i++) {
        for (const ch of ['ww1_somme_1916', 'hq']) {
          const t0 = performance.now();
          await g.loadForBenchmark(ch);
          const info = PerfStats.resourceInfo(g.render.renderer);
          loads.push({ chapter: ch, ms: Math.round(performance.now() - t0), heapMB: info.jsHeapMB, geometries: info.geometries, textures: info.textures });
        }
      }
    }
    const rt = await g.loadForBenchmark(def.chapter);
    const routes = rt?.benchmarkRoutes?.() ?? {};
    this.points = routes[def.route] ?? [{ pos: new THREE.Vector3(0, 2, 5), look: new THREE.Vector3(0, 1.5, 0) }];
    if (def.event) (rt as unknown as Record<string, () => void>)[def.event]?.();
    // warm-up: let shaders/textures settle for 2 s before measuring
    this.duration = 2;
    this.t = 0;
    this.running = true;
    await new Promise<void>((r) => (this.resolveRun = r));
    this.duration = seconds;
    this.t = 0;
    this.stats.reset();
    g.stats.reset();
    this.running = true;
    await new Promise<void>((r) => (this.resolveRun = r));
    const s = g.stats.summary(g.stats.totalFrames);
    const info = PerfStats.resourceInfo(g.render.renderer);
    const gl = g.render.renderer.getContext();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    const result = {
      route: def.label,
      measuredSeconds: seconds,
      frames: s.frames,
      avgFps: +s.avgFps.toFixed(1),
      low1Fps: +s.low1Fps.toFixed(1),
      avgFrameMs: +s.avgMs.toFixed(2),
      p99FrameMs: +s.p99Ms.toFixed(2),
      maxFrameMs: +s.maxMs.toFixed(1),
      spikes: s.spikes,
      peakDrawCalls: this.peakCalls,
      peakTriangles: this.peakTris,
      geometries: info.geometries,
      textures: info.textures,
      programs: info.programs,
      jsHeapMB: info.jsHeapMB,
      loads,
      environment: {
        userAgent: navigator.userAgent,
        gpu: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
        canvas: `${g.render.renderer.domElement.width}×${g.render.renderer.domElement.height}`,
        css: `${window.innerWidth}×${window.innerHeight}`,
        devicePixelRatio: window.devicePixelRatio,
        resolutionScale: g.render.resolutionScale,
        preset: g.settings.graphics.preset,
        graphics: { ...g.settings.graphics },
        hardwareConcurrency: navigator.hardwareConcurrency,
        date: new Date().toISOString(),
      },
    };
    (window as unknown as { __benchResult: unknown }).__benchResult = result;
    return result;
  }

  tick(dt: number): void {
    if (!this.running) return;
    this.t += dt;
    const n = this.points.length;
    const f = Math.min(1, this.t / this.duration) * (n - 1);
    const i = Math.min(n - 2, Math.floor(f));
    const k = f - i;
    if (n === 1) this.game.setBenchmarkCamera(this.points[0].pos, this.points[0].look);
    else {
      _p.lerpVectors(this.points[i].pos, this.points[i + 1].pos, k);
      _l.lerpVectors(this.points[i].look, this.points[i + 1].look, k);
      this.game.setBenchmarkCamera(_p, _l);
    }
    const r = this.game.render.renderer.info.render;
    this.peakCalls = Math.max(this.peakCalls, r.calls);
    this.peakTris = Math.max(this.peakTris, r.triangles);
    if (this.t >= this.duration) {
      this.running = false;
      this.resolveRun?.();
    }
  }

  static rows(r: Record<string, unknown>): [string, string][] {
    const env = r.environment as Record<string, unknown>;
    return [
      ['Route', String(r.route)],
      ['Average FPS', String(r.avgFps)],
      ['1% low FPS', String(r.low1Fps)],
      ['Average / p99 / max frame time', `${r.avgFrameMs} / ${r.p99FrameMs} / ${r.maxFrameMs} ms`],
      ['Frame-time spikes', String(r.spikes)],
      ['Peak draw calls / triangles', `${r.peakDrawCalls} / ${r.peakTriangles}`],
      ['Geometries / textures / programs', `${r.geometries} / ${r.textures} / ${r.programs}`],
      ['JS heap', r.jsHeapMB === null ? 'n/a (browser does not report)' : `${r.jsHeapMB} MB`],
      ['GPU', String(env.gpu)],
      ['Canvas (render) size', String(env.canvas)],
      ['Preset / resolution scale', `${env.preset} / ${env.resolutionScale}`],
      ['Browser', String(env.userAgent)],
    ];
  }
}

const _p = new THREE.Vector3();
const _l = new THREE.Vector3();
