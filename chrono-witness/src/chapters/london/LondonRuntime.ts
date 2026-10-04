import * as THREE from 'three';
import type { GameContext } from '../../core/GameContext';
import type { ChapterConfig, ChapterRuntime, LoadReporter } from '../types';
import type { EnvironmentConfig } from '../../render/Environment';
import type { PBRSet } from '../../render/Assets';
import { standardFromSet } from '../../render/Materials';
import { Builder, type Collider } from '../common/builder';
import { GeoBatch } from '../common/geo';
import { FireSystem, type FireSource } from '../common/fire';
import { Puffs } from '../common/particles';
import { FollowGroup } from '../../npc/FollowGroup';
import type { NPC } from '../../npc/NPC';
import { Rng } from '../../core/Random';
import { terraces, FRONT, HOUSE_D, YARD_D, ALLEY_W, DOCK_LANE_X, HIGH_STREET_Z, STATION, WARDEN_POST, FIRST_AID_POST, DEPOT, CRATER, RESCUE_LORRY, ALLEY_GATE, BOUNDS, WVS_VAN, AFS_PUMP, type HouseDef } from './layout';
import { LONDON_SETS, buildHouse, houseFrame, GF } from './houses';
import { STREET_SETS, buildStreets, signTexture, type StreetBuild } from './street';
import { buildTube, type TubeBuild } from './tube';
import { RaidSky, buildDocklands } from './sky';

export function createRuntime(ctx: GameContext, cfg: ChapterConfig): ChapterRuntime {
  return new LondonRuntime(ctx, cfg);
}

/** Texture sets used by this chapter (all procedural, see ASSETS.md). */
const SETS = [
  'london_stock_brick',
  'render_stucco',
  'slate_roof',
  'painted_wood',
  'interior_wallpaper',
  'floorboards_interior',
  'pavement_flags',
  'stone_rubble',
  'wood_beam',
  'soot_scorch',
  'corrugated_iron',
  'mud_wet',
  'rusty_steel',
  'tarmac_road',
  'sandbag_dry',
  'tile_station',
  'concrete_platform',
  'cobblestone_wet',
  'canvas_tent',
  'crate_wood',
];

/** Extra material keys for props and vehicles → texture set (or a plain material). */
const PROP_SETS: Record<string, string> = {
  ...STREET_SETS,
  ...LONDON_SETS,
  crate: 'crate_wood',
  canvas: 'canvas_tent',
};

const NIGHT: EnvironmentConfig = {
  sky: { zenith: 0x05070d, horizon: 0x221619, ground: 0x0c0a0a, sunDirection: [-0.35, 0.62, -0.45], sunColor: 0xa3b6dc, sunIntensity: 1.6, sunDisc: 0, cloudCover: 0.55, cloudColor: 0x3d2b27, cloudShadow: 0x120e10 },
  fogColor: 0x261c1d,
  fogDensity: 0.0072,
  hemiSky: 0x5a6c94,
  hemiGround: 0x5a3420,
  hemiIntensity: 1.15,
  envIntensity: 1.0,
  rain: 0,
  wetness: 0.12,
  wind: [0.6, 0.3],
};

const DAWN: EnvironmentConfig = {
  sky: { zenith: 0x4a5a74, horizon: 0xc4a08a, ground: 0x2e2a28, sunDirection: [0.75, 0.1, -0.3], sunColor: 0xffc69a, sunIntensity: 0.95, sunDisc: 0, cloudCover: 0.62, cloudColor: 0xb59a8e, cloudShadow: 0x4a4248 },
  fogColor: 0x8a7f7c,
  fogDensity: 0.006,
  hemiSky: 0x9aa6b8,
  hemiGround: 0x4a3c34,
  hemiIntensity: 0.36,
  envIntensity: 0.85,
  rain: 0,
  wetness: 0.12,
  wind: [0.6, 0.3],
};

interface Zone {
  id: string;
  test: (p: THREE.Vector3) => boolean;
  when?: () => boolean;
  inside: boolean;
}

interface LightSource {
  pos: THREE.Vector3;
  intensity: number;
  color: number;
  flicker: number;
  distance: number;
  /** Fire this light belongs to (follows its intensity). */
  fire?: FireSource;
  /** Only considered when this returns true. */
  when?: () => boolean;
}

interface Incendiary {
  id: string;
  fact: string;
  pos: THREE.Vector3;
  fire: FireSource | null;
  casing: THREE.Object3D;
}

/** Character ids for the London cast, with stand-ins used until the period models exist. */
interface CastSpec {
  prefs: string[];
  fallback: string;
  tint?: number;
  scale?: number;
  hide?: string[];
}

const CAST: Record<string, CastSpec> = {
  pike: { prefs: ['warden_woman'], fallback: 'officer', tint: 0x30343c },
  ivy: { prefs: ['mother_1940', 'civilian_woman'], fallback: 'medic', tint: 0x5e4a40, hide: ['helmet', 'gear'] },
  joan: { prefs: ['girl_1940'], fallback: 'soldier_a', tint: 0x6a4a44, scale: 0.72, hide: ['helmet', 'gear'] },
  billy: { prefs: ['boy_1940'], fallback: 'soldier_c', tint: 0x4c4a48, scale: 0.64, hide: ['helmet', 'gear'] },
  moss: { prefs: ['old_man_1940'], fallback: 'wounded', tint: 0x6c645a, hide: ['helmet', 'gear'] },
  carver: { prefs: ['rescue_man_a'], fallback: 'soldier_b', tint: 0x2a2c30 },
  rescuer1: { prefs: ['rescue_man_b', 'rescue_man_a'], fallback: 'soldier_c', tint: 0x2a2c30 },
  rescuer2: { prefs: ['rescue_man_a', 'rescue_man_b'], fallback: 'soldier_a', tint: 0x2a2c30 },
  nurse: { prefs: ['nurse_1940'], fallback: 'medic', tint: 0x26304a },
  wvs: { prefs: ['wvs_woman'], fallback: 'medic', tint: 0x4f5a4c, hide: ['helmet', 'gear'] },
  afs1: { prefs: ['afs_fireman'], fallback: 'soldier_b', tint: 0x23262c },
  afs2: { prefs: ['afs_fireman'], fallback: 'soldier_c', tint: 0x23262c },
};
const CROWD: string[][] = [['civilian_woman'], ['civilian_man'], ['civilian_oldwoman', 'civilian_woman'], ['civilian_man'], ['mother_1940', 'civilian_woman'], ['old_man_1940', 'civilian_man']];

/**
 * London, a night in late September 1940. Builds Cable Row, the High Street and Morley Road station,
 * populates them and scripts the night: the family escort through the incendiaries, the bomb on
 * No. 14, the alley gate, the dressings, the silence, and the rescue at dawn.
 */
class LondonRuntime implements ChapterRuntime {
  readonly root = new THREE.Group();
  private rng = new Rng(1940);
  private M: Record<string, THREE.Material> = {};
  private tiles: Record<string, number> = {};
  private street!: StreetBuild;
  private tube!: TubeBuild;
  private houses: HouseDef[] = [];
  private s14!: HouseDef;
  private n9!: HouseDef;
  private intactGroup = new THREE.Group();
  private ruinGroup = new THREE.Group();
  private fires!: FireSystem;
  private dust!: Puffs;
  private smoke!: Puffs;
  private sky!: RaidSky;
  private lights: LightSource[] = [];
  private lightPool: THREE.PointLight[] = [];
  /** Warm fill from the fires to the south (the sky glow lights the street faces). */
  private fireFill = new THREE.DirectionalLight(0xff7a3a, 0.8);
  private zones: Zone[] = [];
  private npc: Record<string, NPC | undefined> = {};
  private crowd: NPC[] = [];
  private family!: FollowGroup;
  private incendiaries: Incendiary[] = [];
  private yardFires: Incendiary[] = [];
  private gasmaskProp!: THREE.Object3D;
  private bricksProp!: THREE.Object3D;
  private gateLeaf!: THREE.Object3D;
  private gateT = -1;
  private timberProp!: THREE.Object3D;
  private pulses: THREE.Mesh[] = [];
  private pulseMat!: THREE.MeshBasicMaterial;
  private time = 0;
  private timers: { t: number; fn: () => void }[] = [];
  private completed = false;
  // script state
  private escortPending = false;
  private yardLit = false;
  private incendiariesLive = false;
  private fireTimer = 0;
  private heState: 'none' | 'prompt' | 'falling' | 'done' = 'none';
  private heT = 0;
  private rescuersMoving = false;
  private rescuersArrived = false;
  private stillT = 0;
  private tapTimer = 0;
  private dawnT = -1;
  private raidTimer = 3;
  private boundaryMsgT = 0;
  private lastPlayer = new THREE.Vector3();

  constructor(
    private readonly ctx: GameContext,
    private readonly cfg: ChapterConfig,
  ) {
    this.root.name = 'london';
    this.intactGroup.name = 's14-intact';
    this.ruinGroup.name = 's14-ruin';
    void this.cfg;
  }

  // ======================================================================= helpers
  private f(k: string): boolean {
    return this.ctx.facts.get(k);
  }

  private stage(): string | null {
    return this.ctx.missions.state.get('blackout')?.stage ?? null;
  }

  /** Local house coordinates → world. */
  private hw(def: HouseDef, lx: number, ly: number, lz: number, out = new THREE.Vector3()): THREE.Vector3 {
    const fr = houseFrame(def);
    return def.side === 'north' ? out.set(fr.x + lx, ly, fr.z + lz) : out.set(fr.x - lx, ly, fr.z - lz);
  }

  /** Game-time scheduler (pauses with the game). Delay in seconds. */
  private after(fn: () => void, s: number): void {
    this.timers.push({ t: s, fn });
  }

  private ground(x: number, z: number, from = 3): number {
    return this.ctx.world.groundHeight(x, from, z, from + 4) ?? 0.12;
  }

  // ======================================================================= build
  async build(report: LoadReporter): Promise<void> {
    const ctx = this.ctx;
    report(0.02, 'Textures');
    const sets: Record<string, PBRSet> = {};
    let i = 0;
    for (const s of SETS) {
      sets[s] = await ctx.assets.pbr(s);
      this.tiles[s] = sets[s].tileMetres;
      report(0.02 + (0.3 * ++i) / SETS.length, 'Textures');
    }
    this.buildMaterials(sets, await ctx.assets.texture('textures/fx/window_tape.png', THREE.SRGBColorSpace));

    report(0.35, 'Terraces');
    this.buildHouses();
    report(0.5, 'Streets');
    this.street = buildStreets(this.tiles);
    this.addBuilder(this.street.b, this.root);
    this.buildSigns();
    report(0.56, 'Underground');
    const tb = new Builder(this.tiles, STREET_SETS);
    this.tube = buildTube(tb);
    this.addBuilder(tb, this.root);
    report(0.6, 'Surroundings');
    this.buildGroundAndBounds();
    this.buildBackdrop();
    this.buildProps();
    this.buildVehicles();

    report(0.66, 'Night sky');
    await ctx.env.setup(NIGHT, ctx.render.renderer, await ctx.assets.texture('textures/fx/cloud_noise.png'));
    ctx.env.setGlow(new THREE.Vector3(0.12, 0.03, 1).normalize(), 0xff5a1e, 0.9);
    ctx.render.setGrade({ saturation: 0.9, contrast: 1.06, tint: 0xfff2e6, shadowTint: 0xdfe6f4, exposure: 1.65, vignette: 0.26, grain: 0.032 });
    this.fireFill.position.set(30, 70, 220);
    this.fireFill.target.position.set(0, 0, 0);
    this.root.add(this.fireFill, this.fireFill.target);
    this.sky = new RaidSky((x) => ctx.tracker.track(x));
    this.root.add(this.sky.group);
    const dockFires = buildDocklands(this.root, (x) => ctx.tracker.track(x));
    this.sky.onBurst = (p) => {
      const d = p.length();
      this.after(() => ctx.audio.antiAircraft(p.x, p.z, d), Math.min(2.5, d / 343));
    };

    report(0.72, 'Fires');
    const fireTex = await ctx.assets.texture('textures/fx/fire_flipbook.png', THREE.SRGBColorSpace);
    this.fires = ctx.tracker.track(new FireSystem(72, fireTex));
    this.root.add(this.fires.mesh);
    for (const p of dockFires.slice(0, 14)) this.fires.add(p, this.rng.range(14, 26), 'distant');
    // the shell of No. 30, hit last week, is still smouldering
    const s30 = this.houses.find((h) => h.id === 's30')!;
    const smoulder = this.fires.add(this.hw(s30, 0.4, 0.3, -3.5), 1.1, 'house');
    this.lights.push({ pos: smoulder.pos.clone().setY(1.2), intensity: 3.2, color: 0xff7a32, flicker: 1.3, distance: 12, fire: smoulder });
    const dustTex = await ctx.assets.texture('textures/fx/dust_puff.png', THREE.SRGBColorSpace);
    const smokeTex = await ctx.assets.texture('textures/fx/smoke_dark.png', THREE.SRGBColorSpace);
    this.dust = ctx.tracker.track(new Puffs(160, dustTex));
    this.smoke = ctx.tracker.track(new Puffs(120, smokeTex));
    this.root.add(this.dust.mesh, this.smoke.mesh);
    for (let k = 0; k < 5; k++) {
      const l = new THREE.PointLight(0xff8a40, 0, 12, 2);
      this.lightPool.push(l);
      this.root.add(l);
    }
    // shelter lighting: lamps along the vault, on the stairs and in the booking hall
    const sx = STATION.x;
    const lampPts = [...this.tube.lampPositions, new THREE.Vector3(sx, 4.4, STATION.z + 1.5), new THREE.Vector3(sx, this.tube.stairs[1].y + 2.1, this.tube.stairs[1].z - 0.4), new THREE.Vector3(sx, this.tube.stairBottom.y + 2.4, this.tube.stairBottom.z - 1.0)];
    const bulbGeo = ctx.tracker.track(new THREE.SphereGeometry(0.09, 10, 6));
    const shadeGeo = ctx.tracker.track(new THREE.ConeGeometry(0.22, 0.14, 12, 1, true));
    for (const p of lampPts) {
      this.lights.push({ pos: p, intensity: 5.5, color: 0xffd2a0, flicker: this.rng.range(0, 9), distance: 15 });
      const bulb = new THREE.Mesh(bulbGeo, this.M.bulb);
      bulb.position.copy(p);
      const shade = new THREE.Mesh(shadeGeo, this.M.ironPaint);
      shade.position.copy(p).setY(p.y + 0.08);
      this.root.add(bulb, shade);
    }

    report(0.78, 'People');
    await this.spawnPeople();
    this.buildIncendiaries();
    this.buildInteractions();
    this.buildZones();
    ctx.player.surfaceAt = (x, y, z) => ({ surface: this.surfaceAt(x, y, z), speed: 1 });
    ctx.npcs.groundFn = (x, y, z) => ctx.world.groundHeight(x, y, z, 3);
    for (const n of ctx.npcs.npcs.values()) n.groundFn = ctx.npcs.groundFn;
    ctx.npcs.cullDistance = 70;
    report(0.94, 'Building collision');
    ctx.world.buildStatic('london');
    report(1, 'Ready');
  }

  private buildMaterials(sets: Record<string, PBRSet>, tapeTex: THREE.Texture): void {
    const tr = this.ctx.tracker;
    const S = (set: string, o: Parameters<typeof standardFromSet>[1] = {}): THREE.MeshStandardMaterial => tr.track(standardFromSet(sets[set], o));
    const P = (o: THREE.MeshStandardMaterialParameters): THREE.MeshStandardMaterial => tr.track(new THREE.MeshStandardMaterial(o));
    const brick = S('london_stock_brick', { porosity: 0.3 });
    const pave = S('pavement_flags', { porosity: 0.5 });
    const rubble = S('stone_rubble', { porosity: 0.3 });
    const timber = S('wood_beam');
    const paint = S('painted_wood');
    const stucco = S('render_stucco', { porosity: 0.2 });
    const metal = S('rusty_steel');
    const tile = S('tile_station', { envIntensity: 1.2 });
    const glass = P({ color: 0x0b0d10, roughness: 0.06, metalness: 0, envMapIntensity: 1.8 });
    tapeTex.colorSpace = THREE.SRGBColorSpace;
    this.M = {
      brick,
      brickDark: S('london_stock_brick', { color: 0x8c8782, porosity: 0.3 }),
      stucco,
      slate: S('slate_roof', { porosity: 0.6 }),
      frame: paint,
      door: S('painted_wood', { color: 0x5f6e60 }),
      wallpaper: S('interior_wallpaper'),
      floor: S('floorboards_interior'),
      ceiling: S('render_stucco', { color: 0xd8d2c4 }),
      stone: pave,
      rubble,
      timber,
      charred: S('soot_scorch'),
      corrugated: S('corrugated_iron', { side: THREE.DoubleSide }),
      earth: S('mud_wet', { color: 0x8a8278, porosity: 0.4 }),
      metal,
      road: S('tarmac_road', { porosity: 0.8 }),
      pave,
      kerb: S('pavement_flags', { color: 0xc2bdb5, porosity: 0.5 }),
      iron: metal,
      sandbag: S('sandbag_dry'),
      tile,
      platform: S('concrete_platform'),
      cobble: S('cobblestone_wet', { porosity: 0.8 }),
      ballast: S('stone_rubble', { color: 0x55524d }),
      crate: S('crate_wood'),
      canvas: S('canvas_tent'),
      curtain: S('canvas_tent', { color: 0x2a2520 }),
      glass,
      tape: tr.track(new THREE.MeshStandardMaterial({ map: tapeTex, transparent: true, alphaTest: 0.35, roughness: 0.9, metalness: 0, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1 })),
      pot: P({ color: 0x8a4a32, roughness: 0.85 }),
      kerbPaint: P({ color: 0xd9d4c8, roughness: 0.8 }),
      ironPaint: P({ color: 0x1d221d, roughness: 0.55, metalness: 0.4 }),
      red: P({ color: 0x7c1712, roughness: 0.35 }),
      brass: P({ color: 0xa8834a, roughness: 0.3, metalness: 1 }),
      paint: P({ color: 0xe6e1d6, roughness: 0.7 }),
      card: P({ color: 0x8b7355, roughness: 0.95 }),
      lorry: P({ color: 0x2b3326, roughness: 0.6, metalness: 0.2 }),
      black: P({ color: 0x111214, roughness: 0.45, metalness: 0.3 }),
      tyre: P({ color: 0x151515, roughness: 0.9 }),
      grey: P({ color: 0x5c5f60, roughness: 0.6, metalness: 0.3 }),
      bulb: tr.track(new THREE.MeshBasicMaterial({ color: 0xffd9a0 })),
      dimBulb: tr.track(new THREE.MeshBasicMaterial({ color: 0x6b5236 })),
      water: P({ color: 0x07090b, roughness: 0.03, metalness: 0.1, envMapIntensity: 2 }),
      blanket: S('canvas_tent', { color: 0x6a5a4a }),
    };
  }

  /** Turn a builder's batches into meshes (one per material) and its boxes into static colliders. */
  private addBuilder(b: Builder, parent: THREE.Object3D, collide = true): THREE.Mesh[] {
    const out: THREE.Mesh[] = [];
    for (const [key, batch] of b.batches) {
      if (batch.empty) continue;
      const mat = this.M[key] ?? this.M.grey;
      const g = this.ctx.tracker.track(batch.build());
      const m = new THREE.Mesh(g, mat);
      m.name = key;
      const transparentish = key === 'tape' || key === 'glass' || key === 'bulb' || key === 'dimBulb';
      m.castShadow = !transparentish;
      m.receiveShadow = !transparentish;
      if (key === 'tape') m.renderOrder = 2;
      parent.add(m);
      out.push(m);
    }
    if (collide) for (const c of b.colliders) this.ctx.world.addStaticBox(c.c, c.s, c.r);
    return out;
  }

  /** Merge box colliders into one triangle mesh (for collision that can be switched on and off). */
  private colliderGeometry(cs: Collider[]): THREE.BufferGeometry {
    const gb = new GeoBatch();
    for (const c of cs) gb.add(new THREE.BoxGeometry(c.s.x, c.s.y, c.s.z), new THREE.Matrix4().makeRotationY(c.r).setPosition(c.c));
    return this.ctx.tracker.track(gb.build());
  }

  // ------------------------------------------------------------------ houses
  private buildHouses(): void {
    this.houses = terraces();
    this.n9 = this.houses.find((h) => h.id === 'n9')!;
    this.s14 = this.houses.find((h) => h.id === 's14')!;
    const cells = new Map<string, Builder>();
    const cellOf = (h: HouseDef): Builder => {
      const k = `${h.side}:${Math.floor((h.x + 60) / 40)}`;
      let b = cells.get(k);
      if (!b) cells.set(k, (b = new Builder(this.tiles, LONDON_SETS)));
      return b;
    };
    const xs = new Set(this.houses.map((h) => `${h.side}:${h.x}`));
    const rng = new Rng(77);
    for (const h of this.houses) {
      const fr = houseFrame(h);
      // the "right" side in the local frame is +x (north) / −x in world (south)
      const rightNeighbour = `${h.side}:${h.side === 'north' ? h.x + 5 : h.x - 5}`;
      const closeRight = !xs.has(rightNeighbour);
      const anderson = h.damage === 0 && h.id !== 'n9' && ((h.number * 7) % 10 < 3 || h.id === 's16');
      if (h === this.s14) {
        const intact = new Builder(this.tiles, LONDON_SETS);
        intact.setFrame(fr.x, fr.z, fr.rot);
        buildHouse(intact, h, new Rng(14), { damage: 0, interior: false, anderson: false, closeRight });
        const ruin = new Builder(this.tiles, LONDON_SETS);
        ruin.setFrame(fr.x, fr.z, fr.rot);
        buildHouse(ruin, h, new Rng(14), { damage: 2, interior: false, anderson: false, ruin: true, closeRight });
        this.addBuilder(intact, this.intactGroup, false);
        this.addBuilder(ruin, this.ruinGroup, false);
        this.ctx.world.addDynamic('s14_intact', this.colliderGeometry(intact.colliders), new THREE.Matrix4(), true);
        this.ctx.world.addDynamic('s14_ruin', this.colliderGeometry(ruin.colliders), new THREE.Matrix4(), false);
        this.root.add(this.intactGroup, this.ruinGroup);
        continue;
      }
      const b = cellOf(h);
      b.setFrame(fr.x, fr.z, fr.rot);
      buildHouse(b, h, rng, { damage: h.damage, interior: !!h.interior, anderson, closeRight });
      if (h.damage === 3 || h.damage === 2) this.rubbleMound(b, h, rng);
    }
    for (const b of cells.values()) this.addBuilder(b, this.root);
  }

  private rubbleMound(b: Builder, h: HouseDef, rng: Rng): void {
    const big = h.damage === 3;
    const m = new THREE.SphereGeometry(1, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    const p = m.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) {
      const n = 1 + (rng.next() - 0.5) * 0.3;
      p.setXYZ(i, p.getX(i) * n, p.getY(i) * n, p.getZ(i) * n);
    }
    m.scale(2.3, big ? 1.5 : 1.1, HOUSE_D * 0.45);
    b.geo('rubble', m, new THREE.Matrix4().makeTranslation(0, -0.05, -HOUSE_D * 0.55));
    b.collider(-2.2, 2.2, 0, big ? 1.3 : 0.9, -HOUSE_D + 0.4, -1.2);
    for (let i = 0; i < 5; i++) {
      const j = new THREE.BoxGeometry(0.08, 0.2, 2.2 + rng.next() * 2);
      b.geo(i % 2 ? 'timber' : 'charred', j, new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rng.range(-0.5, 0.3), rng.range(-1, 1), rng.range(-0.3, 0.3))).setPosition(rng.range(-1.8, 1.8), 0.6 + rng.next(), -HOUSE_D * 0.5 + rng.range(-1.5, 1.5)));
    }
  }

  // ------------------------------------------------------------------ signs
  private buildSigns(): void {
    const tr = this.ctx.tracker;
    for (const s of this.street.signs) {
      const tex = signTexture(s.text, s.sub, s.style, (x) => tr.track(x));
      tex.colorSpace = THREE.SRGBColorSpace;
      const mat = tr.track(new THREE.MeshStandardMaterial({ map: tex, roughness: s.style === 'enamel' ? 0.35 : 0.8, metalness: 0 }));
      const w = s.style === 'shelter' ? 0.9 : 1.6;
      const m = new THREE.Mesh(tr.track(new THREE.PlaneGeometry(w, w * 0.375)), mat);
      m.position.copy(s.pos);
      m.rotation.y = s.rotY;
      this.root.add(m);
    }
  }

  // ------------------------------------------------------------------ ground, bounds, backdrop
  private buildGroundAndBounds(): void {
    const b = new Builder(this.tiles, STREET_SETS);
    const x0 = BOUNDS.minX - 40;
    const x1 = BOUNDS.maxX + 40;
    const z0 = BOUNDS.minZ - 30;
    const z1 = BOUNDS.maxZ + 40;
    // ground everywhere except over the station (stair shaft) and the crater
    const holes = [
      { x0: STATION.x - STATION.w / 2, x1: STATION.x + STATION.w / 2, z0: STATION.z - STATION.d / 2, z1: STATION.z + STATION.d / 2 },
      { x0: CRATER.x - CRATER.r, x1: CRATER.x + CRATER.r, z0: CRATER.z - CRATER.r, z1: CRATER.z + CRATER.r },
    ];
    const rects: { x0: number; x1: number; z0: number; z1: number }[] = [{ x0, x1, z0, z1 }];
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
      rects.length = 0;
      rects.push(...next);
    }
    for (const r of rects) b.box('rubble', r.x0, r.x1, -0.32, -0.02, r.z0, r.z1, true);
    // water in the bottom of the crater (burst main)
    const water = new THREE.CircleGeometry(4.1, 24);
    water.rotateX(-Math.PI / 2);
    b.geo('water', water, new THREE.Matrix4().makeTranslation(CRATER.x, -1.6, CRATER.z));
    // invisible limits of the temporal field (the visible reasons: barricades, walls, rubble)
    const L = 61.2;
    b.collider(-L - 0.5, -L, -1, 8, BOUNDS.minZ, BOUNDS.maxZ);
    b.collider(L, L + 0.5, -1, 8, BOUNDS.minZ, BOUNDS.maxZ);
    b.collider(-L, L, -1, 8, BOUNDS.maxZ - 0.5, BOUNDS.maxZ);
    this.addBuilder(b, this.root);
  }

  private buildBackdrop(): void {
    const b = new Builder(this.tiles, PROP_SETS);
    const rng = new Rng(55);
    // rear elevations of the next street south (behind the south alley wall), west of Dock Lane
    const zBack = FRONT + HOUSE_D + YARD_D + ALLEY_W + 0.4 + 8.5;
    for (let x = -62; x < 14; x += 5) {
      b.box('brickDark', x, x + 5, 0, 6.0, zBack, zBack + 7.5);
      const A = (xx: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(xx, y, z);
      b.quad('slate', A(x + 5, 6.0, zBack - 0.25), A(x, 6.0, zBack - 0.25), A(x, 8.1, zBack + 3.75), A(x + 5, 8.1, zBack + 3.75));
      b.box('brick', x + 4.55, x + 5.45, 7.6, 9.2, zBack + 3.4, zBack + 4.1);
      b.box('brickDark', x + (rng.chance(0.5) ? 0 : 2.6), x + (rng.chance(0.5) ? 2.4 : 5), 0, 2.6, zBack - 3.2, zBack);
      for (const wx of [x + 0.8, x + 3.4]) b.box('glass', wx, wx + 0.9, 3.6, 5.0, zBack - 0.03, zBack);
    }
    // yard walls of that street (seen over the alley wall)
    for (let x = -62; x < 14; x += 5) b.box('brickDark', x, x + 0.11, 0, 1.8, zBack - 8.5, zBack);
    // bombed ground east of Dock Lane: broken wall stubs and rubble mounds
    for (let i = 0; i < 14; i++) {
      const x = rng.range(27, 58);
      const z = rng.range(30, 49);
      if (Math.hypot(x - RESCUE_LORRY.x, z - RESCUE_LORRY.z) < 7) continue;
      if (Math.abs(x - ALLEY_GATE.x) < 4 && z < 34) continue;
      const m = new THREE.SphereGeometry(1, 12, 6, 0, Math.PI * 2, 0, Math.PI / 2);
      m.scale(rng.range(1.5, 3.5), rng.range(0.5, 1.3), rng.range(1.5, 3));
      b.geo('rubble', m, new THREE.Matrix4().makeTranslation(x, -0.1, z));
      if (rng.chance(0.5)) b.box('brick', x - 1.5, x + 1.5, 0, rng.range(0.8, 3.5), z - 0.12, z + 0.12, true);
    }
    // terrace shells beyond the barricades at both ends of Cable Row
    for (const side of [-1, 1]) {
      for (const zs of [-1, 1]) {
        for (let k = 0; k < 3; k++) {
          const x = side * (62 + k * 5);
          const zf = zs * FRONT;
          const xa = Math.min(x, x + side * 5);
          b.box('brick', xa, xa + 5, 0, 6.0, zs < 0 ? zf - HOUSE_D : zf, zs < 0 ? zf : zf + HOUSE_D);
          for (const wx of [xa + 0.7, xa + 3.3]) for (const wy of [0.9, 3.7]) b.box('glass', wx, wx + 0.95, wy, wy + 1.4, zs < 0 ? zf : zf - 0.03, zs < 0 ? zf + 0.03 : zf);
        }
      }
    }
    // barricades: rubble heaps and timber barriers across Cable Row and the High Street at both ends
    for (const side of [-1, 1]) {
      for (const zc of [0, HIGH_STREET_Z]) {
        const x = side * 60.6;
        const m = new THREE.SphereGeometry(1, 14, 6, 0, Math.PI * 2, 0, Math.PI / 2);
        m.scale(2.4, 1.5, 6.5);
        b.geo('rubble', m, new THREE.Matrix4().makeTranslation(x + side * 1.6, -0.1, zc));
        for (const dz of [-3.2, 0, 3.2]) {
          b.box('kerbPaint', x - 0.06, x + 0.06, 0.0, 0.95, zc + dz - 0.06, zc + dz + 0.06);
          b.box('kerbPaint', x - 0.04, x + 0.04, 0.8, 0.95, zc + dz - 1.6, zc + dz + 1.6);
          b.box('red', x - 0.045, x + 0.045, 0.82, 0.93, zc + dz - 0.4, zc + dz + 0.4);
        }
      }
      // alley ends bricked up
      for (const s of [-1, 1]) {
        const za = s * (FRONT + HOUSE_D + YARD_D);
        const zb = s * (FRONT + HOUSE_D + YARD_D + ALLEY_W);
        b.box('brickDark', side * 60.9 - 0.15, side * 60.9 + 0.15, 0, 2.2, Math.min(za, zb), Math.max(za, zb), true);
      }
    }
    this.street.signs.push(
      { text: 'DANGER', sub: 'UNEXPLODED BOMB', pos: new THREE.Vector3(60.4, 1.5, 0.0), rotY: -Math.PI / 2, style: 'painted' },
      { text: 'ROAD CLOSED', sub: 'DIVERSION', pos: new THREE.Vector3(-60.4, 1.5, 0.0), rotY: Math.PI / 2, style: 'painted' },
    );
    this.buildSignsFrom(this.street.signs.slice(-2));
    this.addBuilder(b, this.root);
  }

  private buildSignsFrom(list: StreetBuild['signs']): void {
    const saved = this.street.signs;
    this.street.signs = list;
    this.buildSigns();
    this.street.signs = saved;
  }

  // ------------------------------------------------------------------ props
  private propsBuilder = (): Builder => new Builder(this.tiles, PROP_SETS);
  private scanPoints: { id: string; scanId: string; pos: THREE.Vector3; r: number; object?: THREE.Object3D; offsetY?: number }[] = [];

  private buildProps(): void {
    const b = this.propsBuilder();
    const wp = WARDEN_POST;
    // stirrup pump in a bucket of water, red fire buckets and the Redhill container beside the post
    const pumpAt = new THREE.Vector3(11.6, 0.12, -4.75);
    b.geo('red', new THREE.CylinderGeometry(0.15, 0.12, 0.32, 14), new THREE.Matrix4().makeTranslation(pumpAt.x, pumpAt.y + 0.16, pumpAt.z));
    b.geo('brass', new THREE.CylinderGeometry(0.025, 0.025, 0.85, 8), new THREE.Matrix4().makeTranslation(pumpAt.x, pumpAt.y + 0.55, pumpAt.z));
    b.geo('metal', new THREE.CylinderGeometry(0.015, 0.015, 0.36, 6), new THREE.Matrix4().makeRotationZ(Math.PI / 2).setPosition(pumpAt.x, pumpAt.y + 0.98, pumpAt.z));
    b.geo('ironPaint', new THREE.TorusGeometry(0.22, 0.02, 6, 16), new THREE.Matrix4().makeRotationX(Math.PI / 2).setPosition(pumpAt.x + 0.32, pumpAt.y + 0.05, pumpAt.z + 0.1));
    for (let k = 0; k < 3; k++) b.geo('red', new THREE.CylinderGeometry(0.16, 0.12, 0.3, 12), new THREE.Matrix4().makeTranslation(wp.x - 1.25 + k * 0.38, 0.27, wp.z - 1.62));
    this.scanPoints.push({ id: 'obj_stirrup_pump', scanId: 'scan_stirrup_pump', pos: pumpAt.clone().setY(0.7), r: 0.35 });
    const rh = new THREE.Vector3(10.6, 0.12, -5.3);
    b.box('ironPaint', rh.x - 0.55, rh.x + 0.55, rh.y, rh.y + 0.35, rh.z - 0.18, rh.z + 0.18, true);
    b.box('timber', rh.x - 0.5, rh.x + 0.6, rh.y + 0.38, rh.y + 0.42, rh.z - 0.03, rh.z + 0.03); // long-handled scoop
    b.box('metal', rh.x + 0.55, rh.x + 0.82, rh.y + 0.36, rh.y + 0.44, rh.z - 0.1, rh.z + 0.1);
    this.scanPoints.push({ id: 'obj_redhill', scanId: 'scan_redhill', pos: rh.clone().setY(0.6), r: 0.45 });
    this.scanPoints.push({ id: 'obj_arp_post', scanId: 'scan_arp_post', pos: new THREE.Vector3(wp.x, 1.7, wp.z + 1.1), r: 0.6 });
    const lp = this.street.lampPosts[1] ?? this.street.lampPosts[0];
    if (lp) this.scanPoints.push({ id: 'obj_lamppost', scanId: 'scan_blackout_lamppost', pos: lp.clone().setY(1.0), r: 0.35 });
    // a taped front window at No. 7
    const n7 = this.houses.find((h) => h.id === 'n7');
    if (n7) this.scanPoints.push({ id: 'obj_taped_window', scanId: 'scan_taped_windows', pos: this.hw(n7, -0.75, 1.65, 0.05), r: 0.6 });
    // an Anderson shelter in the yard of No. 16
    const s16 = this.houses.find((h) => h.id === 's16');
    if (s16) this.scanPoints.push({ id: 'obj_anderson', scanId: 'scan_anderson', pos: this.hw(s16, 0, 0.8, -HOUSE_D - YARD_D * 0.55), r: 1.0 });
    this.scanPoints.push({ id: 'obj_first_aid_post', scanId: 'scan_first_aid_post', pos: new THREE.Vector3(FIRST_AID_POST.x, 3.1, FIRST_AID_POST.z + FIRST_AID_POST.d / 2 + 0.05), r: 0.8 });
    this.scanPoints.push({ id: 'obj_tube_shelter', scanId: 'scan_tube_shelter', pos: new THREE.Vector3(STATION.x - 6, this.tube.platform.y + 1.0, this.tube.platform.zBack - 0.4), r: 1.2 });

    // No. 9 front room: gas-mask box by the sideboard, ration book on the table, a lamp
    const n9 = this.n9;
    const card = (x: number, y: number, z: number, w: number, h: number, d: number, key = 'card'): void => b.box(key, x - w / 2, x + w / 2, y, y + h, z - d / 2, z + d / 2);
    const rb = this.hw(n9, 0.6, 0.78, -4.15);
    card(rb.x, rb.y, rb.z, 0.11, 0.012, 0.15, 'paint');
    b.box('card', rb.x - 0.05, rb.x + 0.05, rb.y + 0.012, rb.y + 0.014, rb.z - 0.07, rb.z + 0.07);
    this.scanPoints.push({ id: 'obj_ration_book', scanId: 'scan_ration_book', pos: rb.clone().setY(rb.y + 0.05), r: 0.2 });
    this.lights.push({ pos: this.hw(n9, 0.8, 2.2, -3.4), intensity: 1.6, color: 0xffc27a, flicker: 2, distance: 6 });
    b.geo('dimBulb', new THREE.SphereGeometry(0.06, 8, 6), new THREE.Matrix4().makeTranslation(...this.hw(n9, 0.8, 2.45, -3.4).toArray()));
    // sandbags and the stretcher stand at the First Aid Post, crates inside the depot
    for (let k = 0; k < 5; k++) card(DEPOT.x - 2.6 + (k % 3) * 0.8, 0.0 + Math.floor(k / 3) * 0.5, DEPOT.z + 2.4, 0.7, 0.5, 0.6, 'crate');
    for (let k = 0; k < 3; k++) card(DEPOT.x + 2.4, k * 0.42, DEPOT.z + 1.0 + (k % 2) * 0.1, 0.8, 0.42, 0.55, 'crate');
    b.collider(DEPOT.x - 3.0, DEPOT.x - 0.9, 0, 1.0, DEPOT.z + 2.0, DEPOT.z + 2.8);
    this.lights.push({ pos: new THREE.Vector3(DEPOT.x, 3.2, DEPOT.z), intensity: 2.0, color: 0xffd2a0, flicker: 4, distance: 9 });
    b.geo('bulb', new THREE.SphereGeometry(0.07, 8, 6), new THREE.Matrix4().makeTranslation(DEPOT.x, 3.6, DEPOT.z));
    // dressings box at the depot door (the one to carry)
    // timber pile for the rescue (on the pavement beside No. 14)
    const tp = this.hw(this.s14, -3.7, 0.12, 1.0);
    const timber = new THREE.Group();
    for (let k = 0; k < 9; k++) {
      const m = new THREE.Mesh(this.ctx.tracker.track(new THREE.BoxGeometry(0.15, 0.15, 2.4)), this.M.timber);
      m.position.set(((k % 3) - 1) * 0.17, 0.08 + Math.floor(k / 3) * 0.15, 0);
      m.rotation.y = Math.PI / 2 + (Math.random() - 0.5) * 0.05;
      m.castShadow = true;
      timber.add(m);
    }
    timber.position.copy(tp);
    timber.visible = false;
    this.root.add(timber);
    this.timberProp = timber;

    // Tube platform: blankets, bundles, suitcases among the shelterers
    const pf = this.tube.platform;
    for (let x = pf.x0 + 2; x < pf.x1 - 2; x += 2.2 + this.rng.next() * 1.5) {
      const z = pf.zBack - 0.35 - this.rng.next() * 0.6;
      b.box(this.rng.chance(0.5) ? 'blanket' : 'curtain', x - 0.6, x + 0.6, pf.y, pf.y + 0.05, z - 0.45, z + 0.45);
      if (this.rng.chance(0.5)) b.box('card', x + 0.65, x + 1.15, pf.y, pf.y + 0.32, z - 0.1, z + 0.12);
    }
    this.addBuilder(b, this.root);

    // the gas-mask box (a separate object: it is picked up)
    const gm = new THREE.Group();
    const box = new THREE.Mesh(this.ctx.tracker.track(new THREE.BoxGeometry(0.2, 0.16, 0.13)), this.M.card);
    box.position.y = 0.08;
    box.castShadow = true;
    const string = new THREE.Mesh(this.ctx.tracker.track(new THREE.TorusGeometry(0.12, 0.005, 4, 16, Math.PI)), this.M.timber);
    string.position.set(0, 0.16, 0);
    gm.add(box, string);
    gm.position.copy(this.hw(n9, 1.55, 0.18, -6.2));
    gm.rotation.y = 0.4;
    this.root.add(gm);
    this.gasmaskProp = gm;

    // the alley gate: a boarded leaf hinged on its west post, fallen bricks heaped against it
    const gz = ALLEY_GATE.z - 0.12; // centre of the wall line
    const leaf = new THREE.Group();
    const lb = new THREE.Mesh(this.ctx.tracker.track(new THREE.BoxGeometry(1.15, 1.85, 0.05)), this.M.door);
    lb.position.set(0.6, 0.98, 0);
    lb.castShadow = true;
    const bolt = new THREE.Mesh(this.ctx.tracker.track(new THREE.BoxGeometry(0.25, 0.04, 0.04)), this.M.metal);
    bolt.position.set(1.0, 1.0, -0.05);
    leaf.add(lb, bolt);
    leaf.position.set(ALLEY_GATE.x - 0.6, 0.02, gz);
    this.root.add(leaf);
    this.gateLeaf = leaf;
    this.ctx.world.addDynamic('gate', this.ctx.tracker.track(new THREE.BoxGeometry(1.2, 2.0, 0.2)), new THREE.Matrix4().makeTranslation(ALLEY_GATE.x, 1.0, gz), true);
    const bricks = new THREE.Group();
    const bgeo = this.ctx.tracker.track(new THREE.BoxGeometry(0.22, 0.07, 0.1));
    for (let k = 0; k < 40; k++) {
      const m = new THREE.Mesh(bgeo, this.M.brick);
      m.position.set((Math.random() - 0.5) * 1.3, Math.random() * 0.45 * (1 - Math.abs(m.position.x)), -0.35 - Math.random() * 0.6);
      m.rotation.set(Math.random() * 3, Math.random() * 3, Math.random() * 3);
      bricks.add(m);
    }
    const heap = new THREE.Mesh(this.ctx.tracker.track(new THREE.SphereGeometry(0.75, 10, 5, 0, Math.PI * 2, 0, Math.PI / 2)), this.M.rubble);
    heap.scale.set(1, 0.55, 0.7);
    heap.position.set(0, -0.02, -0.55);
    bricks.add(heap);
    bricks.position.set(ALLEY_GATE.x, 0.02, gz);
    this.root.add(bricks);
    this.bricksProp = bricks;

    // tapping pulses for the silence (rings that swell where the sound comes from)
    this.pulseMat = this.ctx.tracker.track(new THREE.MeshBasicMaterial({ color: 0xbfe3ff, transparent: true, opacity: 0, depthWrite: false, depthTest: false, side: THREE.DoubleSide, fog: false }));
    const ring = this.ctx.tracker.track(new THREE.RingGeometry(0.16, 0.2, 32));
    for (const s of this.tapSpots()) {
      const m = new THREE.Mesh(ring, this.pulseMat.clone());
      this.ctx.tracker.track(m.material as THREE.Material);
      m.position.copy(s.pos);
      m.renderOrder = 10;
      m.visible = false;
      this.root.add(m);
      this.pulses.push(m);
    }
  }

  /** Points around the ruin of No. 14 where tapping can seem to come from; index 1 is the real one. */
  private tapSpots(): { pos: THREE.Vector3; strength: number }[] {
    return [
      { pos: this.hw(this.s14, -1.4, 0.8, -3.0), strength: 0.35 },
      { pos: this.hw(this.s14, 1.6, 0.6, -3.1), strength: 1 },
      { pos: this.hw(this.s14, 0.2, 1.5, -4.6), strength: 0.5 },
    ];
  }

  private buildVehicles(): void {
    const b = this.propsBuilder();
    const tr = this.ctx.tracker;
    const wheel = (x: number, z: number, r = 0.42): void => {
      const w = new THREE.CylinderGeometry(r, r, 0.26, 14);
      w.rotateZ(Math.PI / 2);
      b.geo('tyre', w, new THREE.Matrix4().makeTranslation(x, r, z));
    };
    // Heavy Rescue lorry beyond the crater (facing north), ladders and timbers on the flatbed
    const lx = RESCUE_LORRY.x;
    const lz = RESCUE_LORRY.z;
    b.box('lorry', lx - 1.1, lx + 1.1, 0.75, 1.0, lz - 1.6, lz + 3.4, true); // flatbed
    b.box('lorry', lx - 1.1, lx + 1.1, 1.0, 1.45, lz + 3.3, lz + 3.4);
    b.box('lorry', lx - 1.1, lx - 1.0, 1.0, 1.45, lz - 1.6, lz + 3.4);
    b.box('lorry', lx + 1.0, lx + 1.1, 1.0, 1.45, lz - 1.6, lz + 3.4);
    b.box('lorry', lx - 1.0, lx + 1.0, 0.75, 2.45, lz - 3.4, lz - 1.6, true); // cab
    b.box('glass', lx - 0.9, lx + 0.9, 1.75, 2.25, lz - 3.42, lz - 3.4);
    b.box('lorry', lx - 0.85, lx + 0.85, 0.55, 1.35, lz - 4.6, lz - 3.4, true); // bonnet
    b.box('grey', lx - 0.7, lx + 0.7, 0.55, 1.3, lz - 4.65, lz - 4.6); // radiator
    for (const s of [-1, 1]) {
      b.geo('dimBulb', new THREE.CylinderGeometry(0.1, 0.1, 0.06, 12).rotateX(Math.PI / 2), new THREE.Matrix4().makeTranslation(lx + s * 0.75, 1.1, lz - 4.68)); // masked headlamps
      b.box('kerbPaint', lx + s * 1.0 - 0.08, lx + s * 1.0 + 0.08, 0.95, 1.05, lz - 4.2, lz - 3.4); // white-painted wing edges (blackout)
    }
    for (const z of [lz - 3.6, lz + 1.2, lz + 2.4]) for (const s of [-1, 1]) wheel(lx + s * 1.0, z);
    for (let k = 0; k < 6; k++) b.box('timber', lx - 0.9 + k * 0.3, lx - 0.75 + k * 0.3, 1.0, 1.15, lz - 1.4, lz + 3.2);
    b.box('timber', lx - 0.25, lx + 0.25, 1.15, 1.25, lz - 2.0, lz + 3.9); // ladder
    // WVS mobile canteen on the High Street, hatch open
    const vx = WVS_VAN.x;
    const vz = WVS_VAN.z;
    b.box('grey', vx - 2.6, vx + 2.6, 0.55, 2.7, vz - 1.05, vz + 1.05, true);
    b.box('black', vx - 3.6, vx - 2.6, 0.55, 1.6, vz - 0.95, vz + 0.95, true);
    b.box('glass', vx - 3.0, vx - 2.6, 1.6, 2.3, vz - 0.9, vz + 0.9);
    b.box('grey', vx - 2.4, vx + 1.8, 2.7, 2.78, vz - 1.85, vz - 1.05); // hatch flap
    b.box('timber', vx - 2.2, vx + 1.6, 1.15, 1.2, vz - 1.4, vz - 1.05); // counter
    b.geo('brass', new THREE.CylinderGeometry(0.2, 0.2, 0.55, 14), new THREE.Matrix4().makeTranslation(vx + 0.6, 1.5, vz - 0.6)); // urn
    for (let k = 0; k < 4; k++) b.geo('paint', new THREE.CylinderGeometry(0.045, 0.04, 0.1, 10), new THREE.Matrix4().makeTranslation(vx - 1.4 + k * 0.2, 1.25, vz - 1.22));
    for (const x of [vx - 2.0, vx + 1.8]) for (const s of [-1, 1]) wheel(x, vz + s * 0.95, 0.4);
    this.lights.push({ pos: new THREE.Vector3(vx - 0.3, 2.3, vz - 0.5), intensity: 1.8, color: 0xffcf96, flicker: 6, distance: 7 });
    // AFS: a London taxi towing a trailer pump (taxis were requisitioned for this)
    const ax = AFS_PUMP.x;
    const az = AFS_PUMP.z;
    b.box('black', ax - 3.4, ax - 1.0, 0.45, 1.25, az - 0.85, az + 0.85, true);
    b.box('black', ax - 2.9, ax - 1.3, 1.25, 2.0, az - 0.8, az + 0.8);
    b.box('glass', ax - 2.85, ax - 1.35, 1.35, 1.85, az - 0.81, az + 0.81);
    for (const x of [ax - 3.0, ax - 1.4]) for (const s of [-1, 1]) wheel(x, az + s * 0.8, 0.36);
    b.box('grey', ax + 0.2, ax + 2.0, 0.55, 1.45, az - 0.65, az + 0.65, true); // pump
    b.box('red', ax + 0.25, ax + 1.95, 1.45, 1.55, az - 0.6, az + 0.6);
    b.geo('canvas', new THREE.CylinderGeometry(0.35, 0.35, 0.3, 16).rotateX(Math.PI / 2), new THREE.Matrix4().makeTranslation(ax + 1.1, 1.95, az)); // hose drum
    for (const s of [-1, 1]) wheel(ax + 1.1, az + s * 0.75, 0.38);
    b.box('metal', ax - 1.0, ax + 0.2, 0.45, 0.5, az - 0.04, az + 0.04);
    // hose line laid along the gutter towards the docks
    const hose = new THREE.CylinderGeometry(0.04, 0.04, 24, 6);
    hose.rotateX(Math.PI / 2);
    b.geo('canvas', hose, new THREE.Matrix4().makeRotationY(Math.PI / 2).setPosition(ax + 14, 0.05, HIGH_STREET_Z + 3.5));
    this.scanPoints.push({ id: 'obj_afs_pump', scanId: 'scan_afs_pump', pos: new THREE.Vector3(ax + 1.1, 1.3, az), r: 0.7 });
    this.addBuilder(b, this.root);
    void tr;
  }

  // ------------------------------------------------------------------ people
  private charOk: Record<string, boolean> = {};

  private async spawnPeople(): Promise<void> {
    const ctx = this.ctx;
    const lib = ctx.characters;
    const ids = new Set<string>(['soldier_a', 'soldier_b', 'soldier_c', 'officer', 'medic', 'wounded']);
    for (const c of Object.values(CAST)) c.prefs.forEach((p) => ids.add(p));
    for (const c of CROWD) c.forEach((p) => ids.add(p));
    for (const id of ids) this.charOk[id] = await lib.loadCharacter(id);

    const clip = (name: string, fb: string): string => (lib.clips.has(name) ? name : fb);
    const spawn = (id: string, name: string, p: THREE.Vector3, yaw: number, pose = 'idle', extra: { attentive?: boolean; walkSpeed?: number } = {}): NPC | undefined => {
      const spec = CAST[id];
      const real = spec.prefs.find((c) => this.charOk[c]);
      const ch = real ?? (this.charOk[spec.fallback] ? spec.fallback : null);
      if (!ch) return undefined;
      const n = ctx.npcs.spawn({ id, name, character: ch, position: p, yaw, pose, hideMeshes: real ? undefined : spec.hide, ...extra });
      if (!real) this.standIn(n, spec);
      this.npc[id] = n;
      return n;
    };
    const P = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
    spawn('pike', 'Warden Pike', P(16.7, 0.12, -4.4), -0.5, 'idle');
    // the Hartleys: Ivy on the step, the children in the hall
    spawn('ivy', 'Ivy Hartley', this.hw(this.n9, -1.55, 0.18, 0.5), 0, 'idle');
    spawn('joan', 'Joan', this.hw(this.n9, -1.6, 0.18, -1.0), 0, 'idle', { walkSpeed: 1.2 });
    spawn('billy', 'Billy', this.hw(this.n9, -1.3, 0.18, -1.8), 0.3, 'idle', { walkSpeed: 1.1 });
    this.family = new FollowGroup([this.npc.ivy, this.npc.joan, this.npc.billy].filter((n): n is NPC => !!n), 1.2, 1.8);
    spawn('moss', 'Mr Moss', this.hw(this.s14, 1.0, 0.12, 1.2), Math.PI, clip('sit_huddle', 'sit_ground'), { attentive: true });
    // Heavy Rescue party at their lorry beyond the crater
    spawn('carver', 'Mr Carver', P(RESCUE_LORRY.x - 1.8, 0.02, RESCUE_LORRY.z - 2.2), Math.PI, 'idle', { walkSpeed: 1.45 });
    spawn('rescuer1', 'Rescue man', P(RESCUE_LORRY.x + 1.9, 0.02, RESCUE_LORRY.z - 0.5), -Math.PI / 2, 'idle_alt', { walkSpeed: 1.4 });
    spawn('rescuer2', 'Rescue man', P(RESCUE_LORRY.x - 1.7, 0.02, RESCUE_LORRY.z + 1.4), Math.PI * 0.7, 'idle', { walkSpeed: 1.4 });
    spawn('nurse', 'Nurse Bright', this.hw(this.s14, 1.7, 0.12, 1.4), Math.PI * 0.9, 'idle');
    spawn('wvs', 'WVS volunteer', P(WVS_VAN.x - 0.6, 0.12, WVS_VAN.z - 1.9), 0, 'idle');
    spawn('afs1', 'AFS fireman', P(AFS_PUMP.x + 1.1, 0.02, AFS_PUMP.z - 1.2), 0.4, 'kneel_work', { attentive: false });
    spawn('afs2', 'AFS fireman', P(AFS_PUMP.x + 3.4, 0.02, AFS_PUMP.z + 0.3), Math.PI / 2, 'idle_alt', { attentive: false });
    for (const id of ['carver', 'rescuer1', 'rescuer2']) {
      const n = this.npc[id];
      if (n) n.yieldToPlayer = false;
    }
    // shelterers on the platform
    const pf = this.tube.platform;
    const poses = [clip('sit_huddle', 'sit_ground'), 'sit_ground', clip('lie_sleep', 'lie_supine'), 'sit_ground', clip('talk_worried', 'talk')];
    let k = 0;
    for (let x = pf.x0 + 2.5; x < pf.x1 - 2; x += 3.4 + this.rng.next() * 1.6) {
      if (Math.abs(x - STATION.x) < 4.5) continue; // keep the way from the passage clear
      const prefs = CROWD[k % CROWD.length];
      const real = prefs.find((c) => this.charOk[c]);
      const fb = ['soldier_a', 'soldier_b', 'soldier_c', 'medic'][k % 4];
      const ch = real ?? (this.charOk[fb] ? fb : null);
      if (!ch) break;
      const pose = poses[k % poses.length];
      const lying = pose.startsWith('lie');
      const z = lying ? pf.zBack - 0.7 : pf.zBack - 0.15;
      const n = ctx.npcs.spawn({ id: `shelterer${k}`, name: 'Shelterer', character: ch, position: P(x, pf.y, z), yaw: lying ? Math.PI / 2 : Math.PI, pose, attentive: k % 3 === 0, hideMeshes: real ? undefined : ['helmet', 'gear'] });
      if (!real) this.standIn(n, { prefs, fallback: fb, tint: [0x4a4038, 0x3a3c40, 0x5a4c44, 0x3e3a34][k % 4], hide: ['helmet', 'gear'] });
      n.root.userData.noCollide = true;
      this.crowd.push(n);
      k++;
    }
  }

  /** Period models are not available yet: recolour the stand-in to civilian / ARP tones. */
  private standIn(n: NPC, spec: CastSpec): void {
    if (spec.scale) n.root.scale.setScalar(spec.scale);
    if (spec.tint === undefined) return;
    const tint = new THREE.Color(spec.tint);
    n.model?.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      const out = mats.map((mat) => {
        const c = (mat as THREE.MeshStandardMaterial).clone();
        const name = (mat.name || '').toLowerCase();
        if (!name.includes('skin') && !name.includes('eye') && !name.includes('hair')) c.color.lerp(tint, 0.55);
        this.ctx.tracker.track(c);
        return c;
      });
      m.material = Array.isArray(m.material) ? out : out[0];
    });
    n.root.userData.standIn = true;
  }

  // ------------------------------------------------------------------ incendiaries
  private buildIncendiaries(): void {
    const casingGeo = this.ctx.tracker.track(new THREE.CylinderGeometry(0.025, 0.025, 0.35, 8));
    const mk = (id: string, fact: string, pos: THREE.Vector3): Incendiary => {
      const c = new THREE.Mesh(casingGeo, this.M.metal);
      c.rotation.z = Math.PI / 2 - 0.2;
      c.rotation.y = Math.random() * 3;
      c.position.copy(pos).setY(pos.y + 0.03);
      c.visible = false;
      this.root.add(c);
      return { id, fact, pos, fire: null, casing: c };
    };
    this.incendiaries = [mk('incendiary_a', 'event.incendiary_a', new THREE.Vector3(-31, 0.02, 1.4)), mk('incendiary_b', 'event.incendiary_b', new THREE.Vector3(-23.5, 0.02, -1.6))];
    const yard = (id: string, n: number, def: HouseDef | undefined): void => {
      if (!def) return;
      const doorLeft = def.number % 4 < 2;
      this.yardFires.push(mk(id, `event.yard_fire_${n}`, this.hw(def, doorLeft ? -1.4 : 1.4, 0.02, -HOUSE_D - 1.6)));
    };
    yard('yard_fire_1', 1, this.houses.find((h) => h.id === 's6'));
    yard('yard_fire_2', 2, this.houses.find((h) => h.id === 'n19'));
    yard('yard_fire_3', 3, this.houses.find((h) => h.id === 's38'));
  }

  private ignite(inc: Incendiary): void {
    if (inc.fire) return;
    inc.fire = this.fires.add(inc.pos, 0.55, 'incendiary');
    inc.casing.visible = true;
    this.lights.push({ pos: inc.pos.clone().setY(0.5), intensity: 5, color: 0xfff0d8, flicker: Math.random() * 9, distance: 10, fire: inc.fire });
  }

  private smother(inc: Incendiary): void {
    if (!inc.fire) return;
    const f = inc.fire;
    this.ctx.audio.hiss(inc.pos.x, inc.pos.z, 'Incendiary smothered');
    this.smoke.burst(inc.pos.clone().setY(0.2), 6, 0.6, 0.8, 3, 0.5, 0x777068, 0.4);
    const fade = (): void => {
      f.intensity -= 0.25;
      if (f.intensity > 0) this.after(fade, 0.12);
      else {
        this.fires.remove(f);
        this.lights = this.lights.filter((l) => l.fire !== f);
      }
    };
    fade();
    inc.fire = null;
    this.ctx.facts.set(inc.fact);
  }

  private clearIncendiary(inc: Incendiary, burntOut: boolean): void {
    if (inc.fire) {
      this.fires.remove(inc.fire);
      const f = inc.fire;
      this.lights = this.lights.filter((l) => l.fire !== f);
    }
    inc.fire = null;
    inc.casing.visible = burntOut;
  }

  // ------------------------------------------------------------------ interactions
  private buildInteractions(): void {
    const ctx = this.ctx;
    const I = ctx.interactions;
    const talk = (id: string, dialogue: string | (() => string), prompt: string | (() => string), enabled?: () => boolean, fallback?: THREE.Vector3): void => {
      const n = this.npc[id];
      I.add({ id: `talk_${id}`, position: n ? n.root.position.clone() : (fallback ?? new THREE.Vector3()), object: n?.root, offsetY: n ? 1.45 * n.root.scale.y : 0, radius: 0.5, range: 2.8, prompt, enabled, onInteract: () => ctx.startDialogue(typeof dialogue === 'string' ? dialogue : dialogue(), n) });
    };
    talk('pike', 'pike', 'Talk to Warden Pike', undefined, new THREE.Vector3(16.7, 1.6, -4.4));
    talk('ivy', () => (this.f('event.family_sheltered') ? 'ivy_station' : 'ivy'), 'Talk to Ivy Hartley', () => !this.family.active || this.f('event.family_sheltered'));
    talk('carver', 'carver', 'Talk to Mr Carver', () => this.rescuersArrived && !(this.f('event.silence') && !this.f('event.tapping_located')));
    talk('nurse', 'nurse', () => (ctx.player.carrying ? 'Hand over the dressings' : 'Talk to Nurse Bright'), () => this.nurseOnScene());
    talk('wvs', 'wvs', 'Talk to the WVS volunteer');
    talk('moss', 'moss', 'Talk to Mr Moss', () => this.f('event.moss_freed'));
    // the nurse takes the dressings (overrides the plain talk)
    const nurseIt = I.items.get('talk_nurse');
    if (nurseIt) {
      nurseIt.onInteract = () => {
        if (ctx.player.carrying && ctx.facts.hasItem('dressings')) {
          ctx.facts.removeItem('dressings');
          ctx.player.carrying = false;
          ctx.facts.set('event.dressings_delivered');
          ctx.audio.ui('confirm');
        }
        ctx.startDialogue('nurse', this.npc.nurse);
      };
    }
    // tea for the rescue party
    I.add({
      id: 'give_tea',
      position: new THREE.Vector3(),
      object: this.npc.carver?.root,
      offsetY: 1.3,
      radius: 0.5,
      range: 2.8,
      prompt: 'Give the rescue party their tea',
      enabled: () => ctx.facts.hasItem('tea') && this.rescuersArrived,
      onInteract: () => {
        ctx.facts.removeItem('tea');
        ctx.facts.set('event.tea_given');
        ctx.events.emit('subtitle', { speaker: 'Rescue man', text: 'Oh, you beauty. Strong enough to stand the spoon up in.', duration: 4 });
      },
    });
    // gas-mask box
    I.add({
      id: 'gasmask',
      position: new THREE.Vector3(),
      object: this.gasmaskProp,
      offsetY: 0.1,
      radius: 0.3,
      range: 2.4,
      prompt: 'Take Joan’s gas-mask box',
      enabled: () => this.gasmaskProp.visible && this.f('dlg.ivy.go'),
      onInteract: () => {
        this.gasmaskProp.visible = false;
        ctx.missions.runEffect({ giveItem: 'gasmask_box' });
        this.escortPending = true;
      },
    });
    // incendiaries: hold E with the sand bucket
    for (const inc of [...this.incendiaries, ...this.yardFires]) {
      I.add({
        id: inc.id,
        position: inc.pos.clone().setY(0.3),
        radius: 0.5,
        range: 2.6,
        holdTime: 1.4,
        prompt: () => (ctx.facts.hasItem('sand_bucket') ? 'Smother the incendiary with sand' : 'You need sand to smother it'),
        enabled: () => !!inc.fire,
        onInteract: () => {
          if (ctx.facts.hasItem('sand_bucket')) this.smother(inc);
        },
      });
      ctx.interactions.add({ id: `scan_${inc.id}`, position: inc.pos.clone().setY(0.15), radius: 0.3, range: 3.2, scanId: inc.id === 'incendiary_a' ? 'scan_incendiary' : undefined, scanOnly: true, prompt: 'Scan', enabled: () => inc.id === 'incendiary_a' && inc.casing.visible, onInteract: () => undefined });
    }
    // calling to Mr Moss in the ruin
    const tap = this.tapSpots();
    I.add({
      id: 'moss_call',
      position: tap[1].pos.clone(),
      radius: 0.7,
      range: 3.2,
      prompt: 'Call out to Mr Moss',
      enabled: () => this.heState === 'done' && !this.f('event.moss_located'),
      onInteract: () => ctx.startDialogue('moss_tap'),
    });
    // the silence: point out where the tapping comes from
    tap.forEach((s, idx) =>
      I.add({
        id: `tap_spot_${idx}`,
        position: s.pos.clone(),
        radius: 0.6,
        range: 3.4,
        prompt: 'Point the rescuers here',
        enabled: () => this.f('event.silence') && !this.f('event.tapping_located'),
        onInteract: () => {
          if (idx === 1) {
            ctx.facts.set('event.tapping_located');
            ctx.events.emit('subtitle', { speaker: 'Mr Carver (Heavy Rescue)', text: 'There. Under the stairs. Right, lads, carefully now.', duration: 4 });
            this.endSilence();
          } else ctx.events.emit('subtitle', { speaker: 'Mr Carver (Heavy Rescue)', text: 'Not there, I don’t think. Keep still and watch again.', duration: 3.5 });
        },
      }),
    );
    // timber pile: pass timbers to the rescuers
    I.add({
      id: 'timber',
      position: new THREE.Vector3(),
      object: this.timberProp,
      offsetY: 0.6,
      radius: 0.8,
      range: 2.8,
      holdTime: 1.0,
      prompt: () => `Pass a timber to the rescuers (${this.timberCount()}/3)`,
      enabled: () => this.f('event.tapping_located') && !this.f('event.moss_freed') && this.timberCount() < 3 && this.dawnT < 0,
      onInteract: () => this.passTimber(),
    });
    // dressings at the depot
    I.add({
      id: 'dressings',
      position: new THREE.Vector3(DEPOT.x - 1.4, 1.0, DEPOT.z + 2.4),
      radius: 0.6,
      range: 3.0,
      prompt: 'Take a box of dressings',
      enabled: () => this.stage() === 'supplies' && !ctx.player.carrying && !this.f('event.dressings_delivered'),
      onInteract: () => {
        ctx.missions.runEffect({ giveItem: 'dressings' });
        ctx.player.carrying = true;
        ctx.events.emit('notify', { text: 'Carrying the dressings: you cannot run or climb.', kind: 'info' });
      },
    });
    // the alley gate: clear the bricks, then the bolt
    I.add({
      id: 'gate_bricks',
      position: new THREE.Vector3(ALLEY_GATE.x, 0.5, ALLEY_GATE.z - 0.8),
      radius: 0.7,
      range: 2.6,
      holdTime: 2.4,
      prompt: 'Clear the fallen bricks from the gate',
      enabled: () => this.f('event.moss_located') && !this.f('event.gate_bricks'),
      onInteract: () => {
        ctx.facts.set('event.gate_bricks');
        this.bricksProp.visible = false;
        this.dust.burst(new THREE.Vector3(ALLEY_GATE.x, 0.3, ALLEY_GATE.z - 0.6), 6, 1.2, 0.6, 2.5, 0.5, 0x9a9086, 0.4);
      },
    });
    I.add({
      id: 'gate_bolt',
      position: new THREE.Vector3(ALLEY_GATE.x + 0.4, 1.0, ALLEY_GATE.z - 0.3),
      radius: 0.4,
      range: 2.4,
      prompt: () => (this.f('event.gate_bricks') ? 'Draw the bolt and open the gate' : 'The gate is blocked by fallen bricks'),
      enabled: () => this.f('event.moss_located') && !this.f('event.gate_open'),
      onInteract: () => {
        if (!this.f('event.gate_bricks')) return;
        this.gateT = 0;
        ctx.audio.creak(ALLEY_GATE.x, ALLEY_GATE.z, 'Gate hinges creaking');
        ctx.world.setEnabled('gate', false);
        ctx.facts.set('event.gate_open');
      },
    });
    // scanner targets
    for (const s of this.scanPoints) I.add({ id: s.id, position: s.pos, object: s.object, offsetY: s.offsetY, radius: s.r, range: 3.4, scanId: s.scanId, scanOnly: true, prompt: 'Scan', onInteract: () => undefined });
    const pike = this.npc.pike;
    I.add({ id: 'obj_warden_helmet', position: new THREE.Vector3(16.7, 1.75, -4.4), object: pike?.root, offsetY: pike ? 1.72 : 0, radius: 0.25, range: 3.4, scanId: 'scan_warden_helmet', scanOnly: true, prompt: 'Scan', onInteract: () => undefined });
    const joan = this.npc.joan;
    I.add({ id: 'obj_gasmask_box', position: this.gasmaskProp.position.clone(), object: joan?.root ?? this.gasmaskProp, offsetY: joan ? 0.75 : 0.1, radius: 0.25, range: 3.4, scanId: 'scan_gasmask_box', scanOnly: true, prompt: 'Scan', onInteract: () => undefined });
  }

  private nurseOnScene(): boolean {
    return this.f('event.moss_located');
  }

  private timberCount(): number {
    return ['event.timber_1', 'event.timber_2', 'event.timber_3'].filter((k) => this.f(k)).length;
  }

  private passTimber(): void {
    const ctx = this.ctx;
    const n = this.timberCount() + 1;
    ctx.facts.set(`event.timber_${n}`);
    const p = this.hw(this.s14, 1.2, 0.4, -2.6);
    this.dust.burst(p, 5, 1.0, 0.6, 2.2, 0.4, 0xa09488, 0.35);
    ctx.audio.creak(p.x, p.z, 'Timber scraping');
    for (const id of ['rescuer1', 'rescuer2']) this.npc[id]?.play('kneel_work', 0.3);
    const lines = ['That’s it. Next one.', 'Lovely. Mind your fingers.', 'Last one. We can see his slippers!'];
    ctx.events.emit('subtitle', { speaker: 'Rescue man', text: lines[n - 1], duration: 3 });
    if (n >= 3) this.after(() => this.startDawn(), 2.5);
  }

  // ------------------------------------------------------------------ zones
  private buildZones(): void {
    const near = (x: number, z: number, r: number) => (p: THREE.Vector3) => (p.x - x) ** 2 + (p.z - z) ** 2 < r * r;
    this.zones = [{ id: 'anchor', test: near(-46, -1, 2.2), when: () => this.stage() === 'return', inside: false }];
  }

  private surfaceAt(x: number, y: number, z: number): string {
    if (y < -1) return 'stone';
    if (this.inN9(x, y, z)) return 'wood';
    if (z > FRONT + HOUSE_D + YARD_D + ALLEY_W + 0.3 && x > DOCK_LANE_X) return 'rubble';
    if (Math.abs(z) < FRONT || Math.abs(z - HIGH_STREET_Z) < 6.2 || Math.abs(x - DOCK_LANE_X) < 4.3) return 'stone';
    return 'default';
  }

  private inN9(x: number, y: number, z: number): boolean {
    return Math.abs(x - this.n9.x) < 2.4 && z < -FRONT && z > -FRONT - HOUSE_D && y < GF;
  }

  // ======================================================================= checkpoints
  readonly killY = -20;
  /** Smoke haze makes anything beyond this invisible at night. */
  readonly visibilityLimit = 520;

  resolveSpawnHeight(x: number, z: number): number {
    return (this.ctx.world.groundHeight(x, 6, z, 30) ?? 0.12) + 0.05;
  }

  scriptState(): Record<string, unknown> {
    return {};
  }

  applyCheckpoint(id: string, script: Record<string, unknown>): void {
    void script;
    const ctx = this.ctx;
    const f = (k: string): boolean => this.f(k);
    this.timers.length = 0;
    ctx.setDanger(null);
    ctx.player.carrying = false;
    ctx.player.movementLocked = false;
    ctx.facts.set('sequence.active', false);
    this.completed = false;
    this.escortPending = false;
    this.incendiariesLive = false;
    this.fireTimer = 0;
    this.dawnT = -1;
    if (ctx.facts.hasItem('dressings')) ctx.facts.removeItem('dressings');
    // the bomb on No. 14
    const hit = f('event.he_bomb');
    this.setRuin(hit);
    this.heState = hit ? 'done' : 'none';
    // gate
    this.bricksProp.visible = !f('event.gate_bricks');
    const open = f('event.gate_open');
    this.gateT = -1;
    this.gateLeaf.rotation.y = open ? -1.75 : 0;
    ctx.world.setEnabled('gate', !open);
    // gas mask
    this.gasmaskProp.visible = !ctx.facts.hasItem('gasmask_box') && !f('item.gasmask_box');
    // incendiaries
    for (const inc of this.incendiaries) this.clearIncendiary(inc, f(inc.fact));
    for (const inc of this.yardFires) this.clearIncendiary(inc, f(inc.fact));
    this.yardLit = false;
    // family
    this.placeFamily();
    // rescue party, nurse, Mr Moss
    this.rescuersMoving = false;
    this.rescuersArrived = false;
    if (f('event.gate_open') && f('dlg.pike.incident')) this.placeRescuersAtScene();
    else this.placeRescuersAtLorry();
    const nurse = this.npc.nurse;
    nurse?.setVisible(this.nurseOnScene());
    const moss = this.npc.moss;
    if (moss) {
      moss.setVisible(f('event.moss_freed'));
      moss.teleport(this.hw(this.s14, 1.0, 0.12, 1.25), Math.PI);
    }
    this.timberProp.visible = f('event.moss_located');
    for (const p of this.pulses) p.visible = false;
    // night or dawn
    const dawn = f('event.moss_freed');
    if (dawn) this.ctx.env.blend(NIGHT, DAWN, 1);
    else this.ctx.env.blend(NIGHT, DAWN, 0);
    this.sky.intensity = dawn ? 0 : 1;
    this.fireFill.intensity = dawn ? 0 : 0.8;
    this.ctx.env.setGlow(new THREE.Vector3(0.12, 0.03, 1).normalize(), 0xff5a1e, dawn ? 0.25 : 0.9);
    ctx.audio.setDrone(dawn ? 0 : 0.7);
    ctx.audio.setLoop('wind', 'wind', 0.12);
    ctx.audio.setLoop('fire', 'fire', dawn ? 0.02 : 0.06);
    if (id === this.cfg.startCheckpoint && !f('dlg.pike.give')) this.after(() => ctx.audio.siren('alert', 22), 1.0);
  }

  private setRuin(on: boolean): void {
    this.intactGroup.visible = !on;
    this.ruinGroup.visible = on;
    this.ctx.world.setEnabled('s14_intact', !on);
    this.ctx.world.setEnabled('s14_ruin', on);
  }

  private placeFamily(): void {
    const f = (k: string): boolean => this.f(k);
    const [ivy, joan, billy] = [this.npc.ivy, this.npc.joan, this.npc.billy];
    this.family.active = false;
    this.family.holding = false;
    for (const n of [ivy, joan, billy]) {
      if (!n) continue;
      n.mode = 'idle';
      n.speed = 0;
    }
    const set = (n: NPC | undefined, p: THREE.Vector3, yaw: number, pose: string): void => {
      if (!n) return;
      n.teleport(p, yaw);
      n.setPose(pose);
      n.stop();
    };
    if (f('event.family_sheltered')) {
      const pf = this.tube.platform;
      const sit = this.ctx.characters.clips.has('sit_huddle') ? 'sit_huddle' : 'sit_ground';
      set(ivy, new THREE.Vector3(STATION.x + 2.6, pf.y, pf.zBack - 0.15), Math.PI, 'sit_ground');
      set(joan, new THREE.Vector3(STATION.x + 3.4, pf.y, pf.zBack - 0.15), Math.PI, sit);
      set(billy, new THREE.Vector3(STATION.x + 4.1, pf.y, pf.zBack - 0.2), Math.PI * 1.1, sit);
    } else if (f('dlg.ivy.go')) {
      set(ivy, this.hw(this.n9, -1.9, 0.12, 1.1), 0.2, 'idle');
      set(joan, this.hw(this.n9, -0.9, 0.12, 0.9), -0.3, 'idle_alt');
      set(billy, this.hw(this.n9, -2.7, 0.12, 1.0), 0.5, 'idle');
      if (this.ctx.facts.hasItem('gasmask_box')) this.escortPending = true;
    } else {
      set(ivy, this.hw(this.n9, -1.55, 0.18, 0.5), 0, 'talk');
      set(joan, this.hw(this.n9, -1.6, 0.18, -1.0), 0, 'idle');
      set(billy, this.hw(this.n9, -1.3, 0.18, -1.8), 0.3, 'idle');
    }
  }

  // rescuers' route from the lorry through the gate to No. 14
  private rescueRoute(): THREE.Vector3[] {
    const P = (x: number, z: number): THREE.Vector3 => new THREE.Vector3(x, 0.1, z);
    const sceneFront = this.hw(this.s14, 0, 0.12, 2.4);
    return [P(25.5, 42.5), P(30.6, 33), P(31, 27.2), P(ALLEY_GATE.x, ALLEY_GATE.z - 0.1), P(31, 24.0), P(DOCK_LANE_X + 0.5, 24.0), P(DOCK_LANE_X + 0.5, 6.0), P(DOCK_LANE_X - 1.5, 2.2), P(sceneFront.x + 6, 2.2), sceneFront];
  }

  private sceneSpots(): { id: string; pos: THREE.Vector3; yaw: number; pose: string }[] {
    return [
      { id: 'carver', pos: this.hw(this.s14, 0.3, 0.12, 1.6), yaw: Math.PI * 0.95, pose: 'idle' },
      { id: 'rescuer1', pos: this.hw(this.s14, 1.0, 0.3, -1.4), yaw: 0, pose: 'kneel_work' },
      { id: 'rescuer2', pos: this.hw(this.s14, -0.9, 0.3, -1.7), yaw: 0.4, pose: 'idle_alt' },
    ];
  }

  private placeRescuersAtLorry(): void {
    const L = RESCUE_LORRY;
    const spots: [string, number, number, number, string][] = [
      ['carver', L.x - 1.8, L.z - 2.2, Math.PI, 'idle'],
      ['rescuer1', L.x + 1.9, L.z - 0.5, -Math.PI / 2, 'idle_alt'],
      ['rescuer2', L.x - 1.7, L.z + 1.4, Math.PI * 0.7, 'idle'],
    ];
    for (const [id, x, z, yaw, pose] of spots) {
      const n = this.npc[id];
      if (!n) continue;
      n.setVisible(true);
      n.teleport(new THREE.Vector3(x, this.ground(x, z), z), yaw);
      n.setPose(pose);
      n.stop();
    }
  }

  private placeRescuersAtScene(): void {
    for (const s of this.sceneSpots()) {
      const n = this.npc[s.id];
      if (!n) continue;
      n.setVisible(true);
      n.teleport(s.pos, s.yaw);
      n.setPose(s.pose);
      n.stop();
    }
    this.rescuersArrived = true;
  }

  private startRescuers(): void {
    this.rescuersMoving = true;
    const route = this.rescueRoute();
    let arrived = 0;
    const spots = this.sceneSpots();
    ['carver', 'rescuer1', 'rescuer2'].forEach((id, i) => {
      const n = this.npc[id];
      if (!n) {
        arrived++;
        return;
      }
      this.after(() => {
        const s = spots[i];
        n.walkPath([...route.slice(0, -1).map((p) => p.clone().add(new THREE.Vector3((i - 1) * 0.6, 0, 0))), s.pos.clone()], () => {
          n.faceTowards(this.hw(this.s14, 0, 1, -3), false);
          n.setPose(s.pose);
          if (++arrived >= 3) this.onRescuersArrived();
        });
      }, i * 1.4);
    });
    if (arrived >= 3) this.onRescuersArrived();
    this.ctx.events.emit('notify', { text: 'The Heavy Rescue party is on its way round by the alley.', kind: 'info' });
  }

  private onRescuersArrived(): void {
    this.rescuersArrived = true;
    this.rescuersMoving = false;
    this.ctx.events.emit('subtitle', { speaker: 'Mr Carver (Heavy Rescue)', text: 'Right, where’s this gentleman of yours?', duration: 3.5 });
  }

  // ======================================================================= update
  update(dt: number, time: number): void {
    const ctx = this.ctx;
    this.time += dt;
    for (let i = this.timers.length - 1; i >= 0; i--) {
      const tm = this.timers[i];
      tm.t -= dt;
      if (tm.t <= 0) {
        this.timers.splice(i, 1);
        tm.fn();
      }
    }
    const p = ctx.player.position;
    for (const z of this.zones) {
      const ins = (!z.when || z.when()) && z.test(p);
      if (ins && !z.inside) ctx.events.emit('enterZone', { id: z.id });
      z.inside = ins;
    }
    // indoor light level: Underground, the booking hall, inside No. 9
    const cam = ctx.camera.position;
    let indoor = 0;
    if (this.tube.box.containsPoint(cam)) indoor = 1;
    else if (Math.abs(cam.x - STATION.x) < STATION.w / 2 && Math.abs(cam.z - STATION.z) < STATION.d / 2 && cam.y < 5) indoor = 0.7;
    else if (this.inN9(cam.x, cam.y, cam.z)) indoor = 0.6;
    ctx.env.setIndoor(indoor);
    ctx.audio.muffled = indoor > 0.9 ? 1 : 0;

    this.updateScript(dt, time);
    this.updateRaid(dt);
    this.updateLights(time);
    this.updateMarkers();
    this.fires.update(time, ctx.camera);
    this.dust.update(dt, ctx.camera);
    this.smoke.update(dt, ctx.camera);
    this.sky.update(dt, time, ctx.camera);
    if (this.family.active) this.family.update(dt, p);

    // the gate swinging open
    if (this.gateT >= 0) {
      this.gateT = Math.min(1, this.gateT + dt * 0.9);
      this.gateLeaf.rotation.y = -1.75 * (1 - (1 - this.gateT) ** 2);
      if (this.gateT >= 1) this.gateT = -1;
    }
    // boundary feedback
    this.boundaryMsgT -= dt;
    if (this.boundaryMsgT <= 0 && (Math.abs(p.x) > 60 || p.z > BOUNDS.maxZ - 1.5)) {
      ctx.events.emit('notify', { text: 'The temporal field ends here.', kind: 'warning' });
      this.boundaryMsgT = 6;
    }
    if (!this.completed && this.f('event.chapter_complete')) {
      this.completed = true;
      this.after(() => ctx.completeChapter(), 0.6);
    }
    this.lastPlayer.copy(p);
  }

  private updateScript(dt: number, time: number): void {
    const ctx = this.ctx;
    const f = (k: string): boolean => this.f(k);
    const p = ctx.player.position;
    const stage = this.stage();

    // ---- optional fire-watch: incendiaries in the back yards once the task is taken on
    if (!this.yardLit && ctx.missions.state.get('firewatch')?.state === 'active') {
      this.yardLit = true;
      for (const inc of this.yardFires) if (!f(inc.fact)) this.ignite(inc);
    }
    // ---- family steps out after Ivy's dialogue
    if (f('dlg.ivy.go') && !this.family.active && !f('event.family_sheltered') && this.npc.ivy && this.npc.ivy.root.position.z < -FRONT + 0.6 && !this.escortPending) {
      this.placeFamily();
    }
    // ---- escort: incendiaries fall as soon as you step out with the gas mask
    if (this.escortPending && stage === 'escort' && p.z > -FRONT + 0.4 && !this.incendiariesLive && !f('event.incendiary_a') && !f('event.incendiary_b')) {
      this.escortPending = false;
      this.incendiariesLive = true;
      this.fireTimer = 45 * ctx.settings.accessibility.hazardTimeMultiplier;
      for (const inc of this.incendiaries) this.ignite(inc);
      ctx.audio.hiss(this.incendiaries[0].pos.x, this.incendiaries[0].pos.z, 'Incendiaries landing');
      ctx.env.triggerFlash(new THREE.Vector3(1, 0.1, 0.2), 0.25, 0xfff0d0, 4);
      ctx.events.emit('subtitle', { speaker: 'Ivy Hartley', text: 'Incendiaries! Kids, back in the doorway. We’ll wait here till you’ve put them out!', duration: 4.5 });
      this.family.holding = true;
    } else if (this.escortPending && stage === 'escort' && (f('event.incendiary_a') && f('event.incendiary_b'))) {
      this.escortPending = false;
      this.family.start(p);
    }
    if (this.incendiariesLive) {
      const left = this.incendiaries.filter((i) => i.fire).length;
      if (left === 0) {
        this.incendiariesLive = false;
        ctx.setDanger(null);
        ctx.events.emit('subtitle', { speaker: 'Ivy Hartley', text: 'Oh, well done. Come on, you two, hold my coat. Stay close.', duration: 4 });
        this.family.holding = false;
        this.family.start(p);
      } else {
        this.fireTimer -= dt;
        ctx.setDanger(`Incendiaries burning: ${left} left. Smother them with sand`, this.fireTimer);
        if (this.fireTimer <= 0) {
          this.incendiariesLive = false;
          ctx.setDanger(null);
          ctx.facts.set('event.fire_spread');
          ctx.downPlayer('An incendiary set light to the front of a house before it was put out. The fire spread along the terrace.', 'The fire took hold');
          return;
        }
      }
    }
    // ---- family reaches the platform
    if (this.family.active && !f('event.family_sheltered')) {
      const pf = this.tube.platform;
      const onPlatform = (v: THREE.Vector3): boolean => v.y < pf.y + 1.2 && v.z < pf.zBack + 0.5;
      if (onPlatform(p) && this.family.members.every((m) => onPlatform(m.root.position))) {
        this.family.stop();
        ctx.facts.set('event.family_sheltered');
        this.placeFamily();
        ctx.events.emit('subtitle', { speaker: 'Ivy Hartley', text: 'Here will do. Sit down, Billy. Thank you, love. Oh! Mr Moss, at No. 14. Would you look in on him?', duration: 6 });
      }
    }
    // ---- the bomb on No. 14 once you are back up in the street
    if (stage === 'moss' && this.heState === 'none' && p.y > -0.5 && p.z > HIGH_STREET_Z - 6) {
      this.heState = 'prompt';
      void ctx
        .confirmIntense('High-explosive bomb', 'A bomb falls on Cable Row while you are walking back. You will hear a loud explosion, and there is a bright flash and camera shake; your accessibility settings for shake and flashing apply. No one is shown injured.\n\nYou can skip it. The mission continues with the house already hit.')
        .then((r) => (r === 'skip' ? this.skipSequence() : this.startHE()));
    }
    if (this.heState === 'falling') {
      this.heT += dt;
      if (this.heT > 2.6 && this.heT - dt <= 2.6) this.heImpact();
      if (this.heT > 6) {
        this.heState = 'done';
        ctx.facts.set('sequence.active', false);
      }
    }
    // tapping cues near the ruin until he is found (and during the silence)
    if (this.heState === 'done' && !f('event.moss_freed')) {
      const spot = this.tapSpots()[1].pos;
      const d = Math.hypot(p.x - spot.x, p.z - spot.z);
      this.tapTimer -= dt;
      const listening = f('event.silence') && !f('event.tapping_located');
      if (this.tapTimer <= 0 && (d < 14 || listening) && (!f('event.moss_located') || listening)) {
        this.tapTimer = listening ? 2.6 : 4.5;
        ctx.audio.tap(spot.x, spot.z, 3);
        if (listening) this.pulseT = 0;
      }
    }
    // ---- rescue party sets off when Pike knows and the gate is open
    if (f('event.gate_open') && f('dlg.pike.incident') && !this.rescuersMoving && !this.rescuersArrived) this.startRescuers();
    // ---- the silence: rings over the rubble, strongest where he is
    this.updatePulses(dt);
    // ---- dawn
    if (this.dawnT >= 0) {
      this.dawnT += dt;
      const k = Math.min(1, this.dawnT / 22);
      ctx.env.blend(NIGHT, DAWN, k * k * (3 - 2 * k));
      this.sky.intensity = 1 - Math.min(1, this.dawnT / 10);
      ctx.env.setGlow(new THREE.Vector3(0.12, 0.03, 1).normalize(), 0xff5a1e, 0.9 - 0.65 * k);
      this.fireFill.intensity = 0.8 * (1 - k);
      if (this.dawnT >= 22) this.dawnT = -1;
    }
    void time;
  }

  private pulseT = -1;
  private updatePulses(dt: number): void {
    const ctx = this.ctx;
    const listening = this.f('event.silence') && !this.f('event.tapping_located');
    // marks show only while the player keeps still (the point of a rescue silence)
    const moved = ctx.player.position.distanceTo(this.lastPlayer) / Math.max(dt, 1e-4);
    this.stillT = moved < 0.3 ? this.stillT + dt : 0;
    const spots = this.tapSpots();
    this.pulses.forEach((m, i) => {
      m.visible = listening;
      if (!listening) return;
      if (this.pulseT >= 0) this.pulseT += dt / 3;
      const t = this.pulseT >= 0 ? Math.min(1, this.pulseT * 3 - i * 0.12) : 1;
      const s = 0.5 + Math.max(0, t) * 2.2 * spots[i].strength;
      m.scale.setScalar(s);
      m.quaternion.copy(ctx.camera.quaternion);
      const visible = this.stillT > 0.6 ? 1 : 0.15;
      (m.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 1 - Math.max(0, t)) * spots[i].strength * visible * 0.9;
    });
    if (this.pulseT > 1) this.pulseT = -1;
  }

  private startHE(): void {
    const ctx = this.ctx;
    this.heState = 'falling';
    this.heT = 0;
    ctx.facts.set('sequence.active');
    const t = this.hw(this.s14, 0, 0, -3.5);
    ctx.audio.setDrone(1);
    ctx.audio.bombWhistle(t.x, t.z, 2.6);
    ctx.events.emit('subtitle', { speaker: 'Warden Pike (shouting)', text: 'Down! Get down!', duration: 2.5 });
  }

  private heImpact(): void {
    const ctx = this.ctx;
    const t = this.hw(this.s14, 0, 1, -3.5);
    const d = t.distanceTo(ctx.player.position);
    ctx.audio.impact(t.x, t.z, d, 'Bomb explosion');
    ctx.env.triggerFlash(t.clone().sub(ctx.player.position).setY(0.4).normalize(), Math.max(0.2, 0.8 - d / 120), 0xffb070, 5);
    ctx.player.addTrauma(Math.max(0.15, 0.7 - d / 90));
    this.setRuin(true);
    ctx.facts.set('event.he_bomb');
    this.dust.burst(t.clone().setY(2), 24, 9, 6, 7, 3.2, 0x8f857a, 0.55);
    this.smoke.burst(t.clone().setY(4), 14, 6, 5, 9, 4, 0x5a524c, 0.45);
    this.after(() => ctx.events.emit('subtitle', { speaker: 'Warden Pike (distant)', text: 'That was Cable Row! South side!', duration: 4 }), 2.0);
    this.after(() => ctx.audio.setDrone(0.7), 4);
  }

  skipSequence(): void {
    const ctx = this.ctx;
    this.setRuin(true);
    ctx.facts.set('event.he_bomb');
    ctx.facts.set('sequence.active', false);
    this.heState = 'done';
    ctx.events.emit('notify', { text: 'A bomb has hit No. 14 Cable Row.', kind: 'warning' });
  }

  private endSilence(): void {
    for (const id of ['rescuer1', 'rescuer2']) this.npc[id]?.setPose('kneel_work');
    this.ctx.audio.setDrone(0.5);
  }

  private startDawn(): void {
    const ctx = this.ctx;
    this.dawnT = 0;
    ctx.audio.setDrone(0);
    this.sky.activity = 0;
    this.after(() => {
      ctx.audio.siren('clear', 18);
      ctx.events.emit('subtitle', { speaker: 'Siren', text: '(The steady note of the "Raiders Passed")', duration: 6 });
    }, 3);
    this.after(() => {
      const moss = this.npc.moss;
      if (moss) {
        moss.setVisible(true);
        moss.teleport(this.hw(this.s14, 1.0, 0.12, 1.25), Math.PI);
        moss.setPose(ctx.characters.clips.has('sit_huddle') ? 'sit_huddle' : 'sit_ground');
      }
      this.dust.burst(this.hw(this.s14, 1.2, 0.6, -1.5), 6, 1.2, 0.6, 2, 0.4, 0xa09488, 0.3);
      ctx.facts.set('event.moss_freed');
      ctx.events.emit('subtitle', { speaker: 'Mr Carver (Heavy Rescue)', text: 'Here he comes. Easy, easy. Blanket for the gentleman!', duration: 4 });
      ctx.audio.setLoop('fire', 'fire', 0.02);
    }, 9);
  }

  // ------------------------------------------------------------------ raid ambience
  private updateRaid(dt: number): void {
    const ctx = this.ctx;
    if (this.f('event.moss_freed') || this.dawnT >= 0) return;
    const quiet = this.f('event.silence') && !this.f('event.tapping_located');
    this.sky.activity = quiet ? 0.2 : 1;
    this.raidTimer -= dt;
    if (this.raidTimer <= 0) {
      this.raidTimer = this.rng.range(5, 13) * (quiet ? 2.5 : 1);
      // a stick of bombs on the docks: flash on the southern horizon, the crump arrives later
      const ang = this.rng.range(-0.9, 0.9);
      const dist = this.rng.range(500, 1600);
      const dir = new THREE.Vector3(Math.sin(ang), 0.06, Math.cos(ang));
      ctx.env.triggerFlash(dir, this.rng.range(0.12, 0.3), 0xffa060, 4);
      // (distance passed for loudness only: these are always far away)
      this.after(() => ctx.audio.impact(dir.x * 600, dir.z * 600, Math.max(48, dist / 20), 'Bombs falling on the docks'), Math.min(4, dist / 343));
    }
  }

  private updateLights(time: number): void {
    const cam = this.ctx.camera.position;
    const cand = this.lights
      .filter((l) => (!l.fire || l.fire.intensity > 0.02) && (!l.when || l.when()))
      .map((l) => ({ l, d: l.pos.distanceToSquared(cam) }))
      .sort((a, b) => a.d - b.d);
    for (let i = 0; i < this.lightPool.length; i++) {
      const L = this.lightPool[i];
      const c = cand[i];
      if (!c || c.d > 40 * 40) {
        L.intensity = 0;
        continue;
      }
      const fl = 0.8 + Math.sin(time * 11 + c.l.flicker) * 0.1 + Math.sin(time * 27 + c.l.flicker * 2) * 0.08;
      L.position.copy(c.l.pos);
      L.color.setHex(c.l.color);
      L.distance = c.l.distance;
      L.intensity = c.l.intensity * fl * (c.l.fire ? c.l.fire.intensity : 1);
    }
  }

  private markerPos = new THREE.Vector3();
  private updateMarkers(): void {
    const ctx = this.ctx;
    const cur = ctx.missions.currentObjective();
    const id = cur?.objective.marker;
    if (!id) {
      ctx.setMarker('objective', null);
      return;
    }
    const p = ctx.player.position;
    const at = (v: THREE.Vector3, dy = 0): THREE.Vector3 => this.markerPos.copy(v).setY(v.y + dy);
    const below = p.y < -1;
    const stationDoor = new THREE.Vector3(STATION.x, 2.4, STATION.z + STATION.d / 2);
    let pos: THREE.Vector3 | null = null;
    let label = '';
    switch (id) {
      case 'pike':
        pos = at(new THREE.Vector3(16.7, 2.0, -4.4));
        label = 'Warden Pike';
        if (below) pos = at(stationDoor);
        break;
      case 'n9':
        pos = at(this.hw(this.n9, -1.55, 2.4, 0.2));
        label = 'No. 9';
        break;
      case 'gasmask':
        pos = at(this.gasmaskProp.position, 0.5);
        label = 'Gas-mask box';
        break;
      case 'station':
        if (p.y > -0.5) {
          pos = at(stationDoor);
          label = 'Morley Road station';
        } else {
          pos = at(new THREE.Vector3(STATION.x + 3, this.tube.platform.y + 1.6, this.tube.platform.zBack - 0.5));
          label = 'Platform';
        }
        break;
      case 's14':
        pos = below ? at(stationDoor) : at(this.hw(this.s14, 0, 2.6, 0.2));
        label = 'No. 14';
        break;
      case 'gate':
        pos = at(new THREE.Vector3(ALLEY_GATE.x, 2.2, ALLEY_GATE.z - 0.5));
        label = 'Alley gate';
        if (p.z < FRONT + HOUSE_D + YARD_D - 0.5 && Math.abs(p.x - DOCK_LANE_X) > 4) {
          pos = at(new THREE.Vector3(DOCK_LANE_X, 2.2, FRONT + HOUSE_D + YARD_D + 1.2));
          label = 'Back alley (via Dock Lane)';
        }
        break;
      case 'depot':
        if (ctx.player.carrying) {
          pos = at(this.hw(this.s14, 1.7, 2.0, 1.4));
          label = 'Nurse Bright';
        } else {
          pos = at(new THREE.Vector3(DEPOT.x, 2.6, DEPOT.z - DEPOT.d / 2));
          label = 'ARP depot';
        }
        break;
      case 'timber':
        pos = at(this.timberProp.position, 1.2);
        label = 'Timber pile';
        break;
      case 'anchor':
        pos = at(new THREE.Vector3(-46, 1.4, -1));
        label = 'Anchor point';
        break;
    }
    ctx.setMarker('objective', pos, label);
  }

  // ======================================================================= benchmark
  benchmarkRoutes(): Record<string, { pos: THREE.Vector3; look: THREE.Vector3 }[]> {
    const V = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
    const path = (pts: THREE.Vector3[], end: THREE.Vector3) => pts.map((p, i, arr) => ({ pos: p, look: (arr[i + 1] ?? end).clone().setY(p.y - 0.05) }));
    const pf = this.tube.platform;
    return {
      street: path([V(-50, 1.7, -1), V(-35, 1.7, 0.5), V(-20, 1.7, -0.5), V(-5, 1.7, 1), V(12, 1.7, -1), V(20, 1.7, -10), V(20, 1.7, -30), V(20, 1.7, -44), V(10, 1.7, -46)], V(-10, 1.7, -46)),
      tube: path([V(STATION.x, 1.7, STATION.z + 3), V(STATION.x, 1.4, STATION.z - 2), V(STATION.x, pf.y + 1.6, pf.zBack - 0.6), V(STATION.x - 10, pf.y + 1.6, pf.zBack - 0.8), V(STATION.x - 25, pf.y + 1.6, pf.zBack - 0.8), V(STATION.x + 15, pf.y + 1.6, pf.zBack - 0.8)], V(STATION.x + 30, pf.y + 1.6, pf.zBack - 0.8)),
      raid: [V(DOCK_LANE_X, 1.7, 8), V(DOCK_LANE_X - 1, 1.7, 18), V(DOCK_LANE_X + 1, 1.7, 22)].map((p) => ({ pos: p, look: V(DOCK_LANE_X + 10, 18, 120) })),
    };
  }

  /** Benchmark hook: the heaviest effects at once (incendiaries, flak, bombs, the HE strike). */
  benchRaid(): void {
    this.sky.activity = 3;
    for (const inc of [...this.incendiaries, ...this.yardFires]) this.ignite(inc);
    this.raidTimer = 0;
    this.after(() => this.heImpact(), 1);
  }

  dispose(): void {
    this.ctx.audio.setDrone(0);
    this.ctx.setDanger(null);
    this.ctx.player.carrying = false;
    this.family.active = false;
  }
}
