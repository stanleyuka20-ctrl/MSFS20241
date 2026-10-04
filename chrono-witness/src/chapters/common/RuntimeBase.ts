import * as THREE from 'three';
import type { GameContext } from '../../core/GameContext';
import type { ChapterConfig, ChapterRuntime, LoadReporter } from '../types';
import type { PBRSet } from '../../render/Assets';
import { standardFromSet, type StandardOpts } from '../../render/Materials';
import { Builder, type Collider } from './builder';
import { GeoBatch, canvasTexture } from './geo';
import type { NPC } from '../../npc/NPC';
import { Rng } from '../../core/Random';

export interface Zone {
  id: string;
  test: (p: THREE.Vector3) => boolean;
  when?: () => boolean;
  inside: boolean;
}

export interface LightSource {
  pos: THREE.Vector3;
  intensity: number;
  color: number;
  flicker: number;
  distance: number;
  /** Follows a 0..1 intensity source (e.g. a fire). */
  level?: () => number;
  when?: () => boolean;
}

/** Character ids preferred for a role, with a recoloured stand-in when none of them exists yet. */
export interface CastSpec {
  prefs: string[];
  fallback: string;
  tint?: number;
  scale?: number;
  hide?: string[];
}

/**
 * Shared plumbing for chapter runtimes: PBR material sets, builder → mesh batching with colliders,
 * a fixed pool of point lights moved to the nearest light sources, a game-time scheduler, zones,
 * stand-in characters, markers and completion. Chapters implement build/applyCheckpoint/update.
 */
export abstract class RuntimeBase implements ChapterRuntime {
  readonly root = new THREE.Group();
  protected rng: Rng;
  protected M: Record<string, THREE.Material> = {};
  protected tiles: Record<string, number> = {};
  protected sets: Record<string, PBRSet> = {};
  protected lights: LightSource[] = [];
  protected lightPool: THREE.PointLight[] = [];
  protected zones: Zone[] = [];
  protected npc: Record<string, NPC | undefined> = {};
  protected timers: { t: number; fn: () => void }[] = [];
  protected completed = false;
  protected time = 0;
  protected charOk: Record<string, boolean> = {};
  protected boundaryMsgT = 0;
  protected markerPos = new THREE.Vector3();

  constructor(
    protected readonly ctx: GameContext,
    protected readonly cfg: ChapterConfig,
    name: string,
    seed: number,
  ) {
    this.root.name = name;
    this.rng = new Rng(seed);
  }

  abstract build(report: LoadReporter): Promise<void>;
  abstract applyCheckpoint(id: string, script: Record<string, unknown>): void;
  abstract update(dt: number, time: number): void;

  scriptState(): Record<string, unknown> {
    return {};
  }

  // ------------------------------------------------------------------ helpers
  protected f(k: string): boolean {
    return this.ctx.facts.get(k);
  }

  protected stageOf(mission: string): string | null {
    return this.ctx.missions.state.get(mission)?.stage ?? null;
  }

  /** Game-time scheduler (pauses with the game). Delay in seconds. */
  protected after(fn: () => void, s: number): void {
    this.timers.push({ t: s, fn });
  }

  protected tickTimers(dt: number): void {
    for (let i = this.timers.length - 1; i >= 0; i--) {
      const tm = this.timers[i];
      tm.t -= dt;
      if (tm.t <= 0) {
        this.timers.splice(i, 1);
        tm.fn();
      }
    }
  }

  protected tickZones(p: THREE.Vector3): void {
    for (const z of this.zones) {
      const ins = (!z.when || z.when()) && z.test(p);
      if (ins && !z.inside) this.ctx.events.emit('enterZone', { id: z.id });
      z.inside = ins;
    }
  }

  protected tickCompletion(): void {
    if (!this.completed && this.f('event.chapter_complete')) {
      this.completed = true;
      this.after(() => this.ctx.completeChapter(), 0.6);
    }
  }

  protected ground(x: number, z: number, from = 3): number {
    return this.ctx.world.groundHeight(x, from, z, from + 6) ?? 0;
  }

  // ------------------------------------------------------------------ materials
  protected async loadSets(names: string[], report?: (f: number) => void): Promise<void> {
    let i = 0;
    for (const s of names) {
      this.sets[s] = await this.ctx.assets.pbr(s);
      this.tiles[s] = this.sets[s].tileMetres;
      report?.(++i / names.length);
    }
  }

  /** Standard PBR material from a loaded set. */
  protected S(set: string, o: StandardOpts = {}): THREE.MeshStandardMaterial {
    return this.ctx.tracker.track(standardFromSet(this.sets[set], o));
  }

  /** Plain material. */
  protected P(o: THREE.MeshStandardMaterialParameters): THREE.MeshStandardMaterial {
    return this.ctx.tracker.track(new THREE.MeshStandardMaterial(o));
  }

  protected basic(color: number): THREE.MeshBasicMaterial {
    return this.ctx.tracker.track(new THREE.MeshBasicMaterial({ color }));
  }

  /** Common plain materials every chapter can use. */
  protected commonMaterials(): Record<string, THREE.Material> {
    return {
      glass: this.P({ color: 0x0b0d10, roughness: 0.06, metalness: 0, envMapIntensity: 1.6 }),
      void: this.basic(0x07080a),
      grey: this.P({ color: 0x5c5f60, roughness: 0.6, metalness: 0.3 }),
      black: this.P({ color: 0x111214, roughness: 0.45, metalness: 0.3 }),
      paint: this.P({ color: 0xe6e1d6, roughness: 0.7 }),
      card: this.P({ color: 0x8b7355, roughness: 0.95 }),
      bulb: this.basic(0xffd9a0),
      sheet: this.ctx.tracker.track(new THREE.MeshStandardMaterial({ color: 0xe9e6de, roughness: 0.95, side: THREE.DoubleSide })),
      zinc: this.P({ color: 0x9aa0a3, roughness: 0.45, metalness: 0.8 }),
      water: this.P({ color: 0x0a0d10, roughness: 0.04, metalness: 0.1, envMapIntensity: 1.8 }),
    };
  }

  /** Builder batches → meshes (one per material key); boxes → static colliders. */
  protected addBuilder(b: Builder, parent: THREE.Object3D = this.root, collide = true): THREE.Mesh[] {
    const out: THREE.Mesh[] = [];
    for (const [key, batch] of b.batches) {
      if (batch.empty) continue;
      const mat = this.M[key] ?? this.M.grey;
      const g = this.ctx.tracker.track(batch.build());
      const m = new THREE.Mesh(g, mat);
      m.name = key;
      const noShadow = key === 'glass' || key === 'bulb' || key === 'void' || key === 'tape';
      m.castShadow = !noShadow;
      m.receiveShadow = !noShadow && key !== 'void';
      parent.add(m);
      out.push(m);
    }
    if (collide) for (const c of b.colliders) this.ctx.world.addStaticBox(c.c, c.s, c.r);
    return out;
  }

  /** Box colliders merged into one triangle mesh (for collision that is switched on and off). */
  protected colliderGeometry(cs: Collider[]): THREE.BufferGeometry {
    const gb = new GeoBatch();
    for (const c of cs) gb.add(new THREE.BoxGeometry(c.s.x, c.s.y, c.s.z), new THREE.Matrix4().makeRotationY(c.r).setPosition(c.c));
    return this.ctx.tracker.track(gb.build());
  }

  /** Ground slab over a rectangle, with rectangular holes (stairwells, craters). */
  protected groundSlab(b: Builder, key: string, x0: number, x1: number, z0: number, z1: number, holes: { x0: number; x1: number; z0: number; z1: number }[], top = -0.02): void {
    let rects = [{ x0, x1, z0, z1 }];
    for (const h of holes) {
      const next: typeof rects = [];
      for (const r of rects) {
        if (h.x1 <= r.x0 || h.x0 >= r.x1 || h.z1 <= r.z0 || h.z0 >= r.z1) {
          next.push(r);
          continue;
        }
        if (h.z0 > r.z0) next.push({ ...r, z1: h.z0 });
        if (h.z1 < r.z1) next.push({ ...r, z0: h.z1 });
        const za = Math.max(r.z0, h.z0);
        const zb = Math.min(r.z1, h.z1);
        if (h.x0 > r.x0) next.push({ x0: r.x0, x1: h.x0, z0: za, z1: zb });
        if (h.x1 < r.x1) next.push({ x0: h.x1, x1: r.x1, z0: za, z1: zb });
      }
      rects = next;
    }
    for (const r of rects) b.box(key, r.x0, r.x1, top - 0.3, top, r.z0, r.z1, true);
  }

  // ------------------------------------------------------------------ lights
  protected makeLightPool(n: number, distance = 12): void {
    for (let k = 0; k < n; k++) {
      const l = new THREE.PointLight(0xffc58a, 0, distance, 2);
      this.lightPool.push(l);
      this.root.add(l);
    }
  }

  protected tickLights(time: number, maxDist = 40): void {
    const cam = this.ctx.camera.position;
    const cand = this.lights
      .filter((l) => (!l.level || l.level() > 0.02) && (!l.when || l.when()))
      .map((l) => ({ l, d: l.pos.distanceToSquared(cam) }))
      .sort((a, b) => a.d - b.d);
    for (let i = 0; i < this.lightPool.length; i++) {
      const L = this.lightPool[i];
      const c = cand[i];
      if (!c || c.d > maxDist * maxDist) {
        L.intensity = 0;
        continue;
      }
      const fl = c.l.flicker > 0 ? 0.82 + Math.sin(time * 11 + c.l.flicker) * 0.09 + Math.sin(time * 27 + c.l.flicker * 2) * 0.07 : 1;
      L.position.copy(c.l.pos);
      L.color.setHex(c.l.color);
      L.distance = c.l.distance;
      L.intensity = c.l.intensity * fl * (c.l.level ? c.l.level() : 1);
    }
  }

  // ------------------------------------------------------------------ people
  protected async loadCast(cast: Record<string, CastSpec>, extra: string[] = []): Promise<void> {
    const ids = new Set<string>(['soldier_a', 'soldier_b', 'soldier_c', 'officer', 'medic', 'wounded', ...extra]);
    for (const c of Object.values(cast)) {
      c.prefs.forEach((p) => ids.add(p));
      ids.add(c.fallback);
    }
    for (const id of ids) this.charOk[id] = await this.ctx.characters.loadCharacter(id);
  }

  protected clip(name: string, fb: string): string {
    return this.ctx.characters.clips.has(name) ? name : fb;
  }

  protected spawnCast(id: string, name: string, spec: CastSpec, p: THREE.Vector3, yaw: number, pose = 'idle', extra: { attentive?: boolean; walkSpeed?: number } = {}): NPC | undefined {
    const real = spec.prefs.find((c) => this.charOk[c]);
    const ch = real ?? (this.charOk[spec.fallback] ? spec.fallback : null);
    if (!ch) return undefined;
    const n = this.ctx.npcs.spawn({ id, name, character: ch, position: p, yaw, pose, hideMeshes: real ? undefined : spec.hide, ...extra });
    if (!real) this.standIn(n, spec);
    this.npc[id] = n;
    return n;
  }

  /** Period model not available yet: recolour the stand-in and scale it (children). */
  protected standIn(n: NPC, spec: CastSpec): void {
    if (spec.scale) n.root.scale.setScalar(spec.scale);
    if (spec.tint === undefined) return;
    const tint = new THREE.Color(spec.tint);
    n.model?.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      const out = mats.map((mat) => {
        const c = (mat as THREE.MeshStandardMaterial).clone();
        const nm = (mat.name || '').toLowerCase();
        if (!nm.includes('skin') && !nm.includes('eye') && !nm.includes('hair')) c.color.lerp(tint, 0.55);
        this.ctx.tracker.track(c);
        return c;
      });
      m.material = Array.isArray(m.material) ? out : out[0];
    });
    n.root.userData.standIn = true;
  }

  protected place(id: string, p: THREE.Vector3, yaw: number, pose: string, visible = true): void {
    const n = this.npc[id];
    if (!n) return;
    n.setVisible(visible);
    n.teleport(p, yaw);
    n.setPose(pose);
    n.stop();
  }

  /** Talk interaction on an NPC (falls back to a fixed point if the NPC is missing). */
  protected talk(id: string, dialogue: string | (() => string), prompt: string | (() => string), enabled?: () => boolean, fallback?: THREE.Vector3): void {
    const n = this.npc[id];
    this.ctx.interactions.add({
      id: `talk_${id}`,
      position: n ? n.root.position.clone() : (fallback ?? new THREE.Vector3()),
      object: n?.root,
      offsetY: n ? 1.45 * n.root.scale.y : 0,
      radius: 0.5,
      range: 2.8,
      prompt,
      enabled: () => (!n || n.visible) && (!enabled || enabled()),
      onInteract: () => this.ctx.startDialogue(typeof dialogue === 'string' ? dialogue : dialogue(), n),
    });
  }

  protected scanPoint(id: string, scanId: string, pos: THREE.Vector3, r = 0.4, object?: THREE.Object3D, offsetY?: number): void {
    this.ctx.interactions.add({ id, position: pos, object, offsetY, radius: r, range: 3.4, scanId, scanOnly: true, prompt: 'Scan', onInteract: () => undefined });
  }

  // ------------------------------------------------------------------ signs
  /** Flat sign or poster drawn on a canvas. */
  protected sign(draw: (c: CanvasRenderingContext2D, w: number, h: number) => void, w: number, h: number, px = 512, rough = 0.8): THREE.Mesh {
    const ph = Math.round((px * h) / w);
    const tex = this.ctx.tracker.track(canvasTexture(px, ph, (c) => draw(c, px, ph)));
    tex.colorSpace = THREE.SRGBColorSpace;
    const mat = this.ctx.tracker.track(new THREE.MeshStandardMaterial({ map: tex, roughness: rough, metalness: 0, transparent: true, alphaTest: 0.05 }));
    return new THREE.Mesh(this.ctx.tracker.track(new THREE.PlaneGeometry(w, h)), mat);
  }

  protected boundary(p: THREE.Vector3, inside: (p: THREE.Vector3) => boolean, text = 'The temporal field ends here.'): void {
    this.boundaryMsgT -= 1 / 60;
    if (this.boundaryMsgT <= 0 && !inside(p)) {
      this.ctx.events.emit('notify', { text, kind: 'warning' });
      this.boundaryMsgT = 6;
    }
  }

  dispose(): void {
    this.ctx.setDanger(null);
    this.ctx.player.carrying = false;
    this.ctx.player.controller.ladders = [];
  }
}
