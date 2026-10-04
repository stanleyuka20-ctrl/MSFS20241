import * as THREE from 'three';
import type { GameContext } from '../../core/GameContext';
import type { ChapterConfig, ChapterRuntime, LoadReporter } from '../types';
import type { EnvironmentConfig } from '../../render/Environment';
import { RuntimeBase, type CastSpec } from '../common/RuntimeBase';
import { Builder } from '../common/builder';
import { Puffs } from '../common/particles';
import { makeTree, leafTexture } from '../common/tree';
import { buildSkyline } from '../common/skyline';
import { buildBerlin, BERLIN_SETS, type BerlinWorld } from './world';
import { FRONT, ROAD_HALF, FLOOR_H, NO12, WING_STAIR, LENZ_FLAT, CELLAR, PUMP, LITFASS, GAP, UXB, RUBBLE_CHAIN, ANCHOR, BOUNDS, CROSS_X, FIREWALL } from './layout';

export function createRuntime(ctx: GameContext, cfg: ChapterConfig): ChapterRuntime {
  return new BerlinRuntime(ctx, cfg);
}

const SETS = [...new Set([...Object.values(BERLIN_SETS), 'stone_rubble', 'canvas_tent'])];

const DAY: EnvironmentConfig = {
  sky: { zenith: 0x5f86b8, horizon: 0xc9c2b2, ground: 0x6a6052, sunDirection: [0.45, 0.72, 0.35], sunColor: 0xfff0d8, sunIntensity: 2.6, sunDisc: 0.7, cloudCover: 0.32, cloudColor: 0xf1ede6, cloudShadow: 0x9a9890 },
  fogColor: 0xb9b2a4,
  fogDensity: 0.0068,
  hemiSky: 0xbcd0e6,
  hemiGround: 0x7a6a56,
  hemiIntensity: 0.55,
  envIntensity: 1.0,
  rain: 0,
  wetness: 0,
  wind: [0.8, 0.2],
};

const CAST: Record<string, CastSpec> = {
  brandt: { prefs: ['civilian_woman_1945', 'civilian_woman'], fallback: 'medic', tint: 0x5a5048, hide: ['helmet', 'gear'] },
  peter: { prefs: ['boy_1945', 'boy_1940'], fallback: 'soldier_c', tint: 0x4e4a44, scale: 0.66, hide: ['helmet', 'gear'] },
  lenz: { prefs: ['old_man_1945', 'old_man_1940'], fallback: 'wounded', tint: 0x55524c, hide: ['helmet', 'gear'] },
  lotte: { prefs: ['young_woman_1945', 'civilian_woman'], fallback: 'medic', tint: 0x6a5446, hide: ['helmet', 'gear'] },
  clerk: { prefs: ['civilian_woman_1945', 'civilian_woman'], fallback: 'officer', tint: 0x48443e, hide: ['cap', 'helmet', 'gear'] },
  q1: { prefs: ['civilian_woman_1945', 'civilian_oldwoman'], fallback: 'medic', tint: 0x4c463e, hide: ['helmet', 'gear'] },
  q2: { prefs: ['civilian_oldwoman', 'civilian_woman'], fallback: 'soldier_a', tint: 0x5c544a, hide: ['helmet', 'gear'] },
  q3: { prefs: ['civilian_man', 'old_man_1940'], fallback: 'soldier_b', tint: 0x403e3a, hide: ['helmet', 'gear'] },
  o1: { prefs: ['civilian_woman'], fallback: 'medic', tint: 0x524a42, hide: ['helmet', 'gear'] },
  o2: { prefs: ['civilian_man'], fallback: 'soldier_c', tint: 0x3e3c38, hide: ['helmet', 'gear'] },
  c1: { prefs: ['civilian_woman_1945', 'civilian_woman'], fallback: 'medic', tint: 0x5a5248, hide: ['helmet', 'gear'] },
  c2: { prefs: ['civilian_woman'], fallback: 'soldier_a', tint: 0x4a4640, hide: ['helmet', 'gear'] },
  c3: { prefs: ['civilian_oldwoman', 'civilian_woman'], fallback: 'soldier_b', tint: 0x50483e, hide: ['helmet', 'gear'] },
  c4: { prefs: ['civilian_man', 'old_man_1940'], fallback: 'soldier_c', tint: 0x3c3a36, hide: ['helmet', 'gear'] },
  k1: { prefs: ['boy_1945', 'boy_1940'], fallback: 'soldier_a', tint: 0x4a463e, scale: 0.62, hide: ['helmet', 'gear'] },
  k2: { prefs: ['girl_1945', 'girl_1940'], fallback: 'soldier_c', tint: 0x5a4a44, scale: 0.66, hide: ['helmet', 'gear'] },
  k3: { prefs: ['boy_1945', 'boy_1940'], fallback: 'soldier_b', tint: 0x44403a, scale: 0.6, hide: ['helmet', 'gear'] },
  regulator: { prefs: ['soviet_regulator'], fallback: 'medic', tint: 0x6b6a48 },
  sapper: { prefs: ['soviet_soldier'], fallback: 'soldier_b', tint: 0x66654a },
  kaminski: { prefs: ['civilian_oldwoman', 'old_man_1940'], fallback: 'wounded', tint: 0x4a443c, hide: ['helmet', 'gear'] },
};

/**
 * Berlin, mid-May 1945, after the surrender. Builds Lindenhofstraße and No. 12 and scripts the
 * day: water from the street pump, the chalk messages, the papers from the broken stairs, the
 * ration-card office, the unexploded shell, the rubble chain and a reunion.
 */
class BerlinRuntime extends RuntimeBase {
  private w!: BerlinWorld;
  private dust!: Puffs;
  private planksGroup = new THREE.Group();
  private papersProp!: THREE.Object3D;
  private woodpile!: THREE.Object3D;
  private shellProp!: THREE.Object3D;
  private bucketsProp!: THREE.Object3D;
  private queueIds = ['q1', 'q2', 'q3'];
  private queueLeft = 3;
  private queueT = 0;
  private officeQueueT = 0;
  private chainCount = 0;
  private chainCue = -1;
  private chainT = 0;
  private shellState: 'none' | 'active' | 'prompt' | 'blast' | 'done' = 'none';
  private blastT = 0;
  private reunionStarted = false;

  constructor(ctx: GameContext, cfg: ChapterConfig) {
    super(ctx, cfg, 'berlin45', 1945);
  }

  private stage(): string | null {
    return this.stageOf('chalk');
  }

  // ======================================================================= build
  async build(report: LoadReporter): Promise<void> {
    const ctx = this.ctx;
    report(0.02, 'Textures');
    await this.loadSets(SETS, (f) => report(0.02 + f * 0.3, 'Textures'));
    this.buildMaterials();
    report(0.35, 'Lindenhofstraße');
    this.w = buildBerlin(this.tiles);
    for (const b of this.w.builders) this.addBuilder(b);
    this.addBuilder(this.w.planks, this.planksGroup, false);
    this.root.add(this.planksGroup);
    ctx.world.addDynamic('planks', this.ctx.tracker.track(this.w.plankRamp), new THREE.Matrix4(), false);
    report(0.55, 'Ground');
    this.buildGround();
    this.buildDetails();
    report(0.62, 'Daylight');
    await ctx.env.setup(DAY, ctx.render.renderer, await ctx.assets.texture('textures/fx/cloud_noise.png'));
    ctx.render.setGrade({ saturation: 0.82, contrast: 1.05, tint: 0xfff4e6, shadowTint: 0xe6ebf2, exposure: 1.05, vignette: 0.22, grain: 0.03 });
    const dustTex = await ctx.assets.texture('textures/fx/dust_puff.png', THREE.SRGBColorSpace);
    this.dust = ctx.tracker.track(new Puffs(140, dustTex));
    this.root.add(this.dust.mesh);
    this.makeLightPool(3, 9);
    for (const [i, p] of this.w.lamps.entries()) this.lights.push({ pos: p, intensity: i === 0 ? 4.5 : 2.2, color: 0xffc27a, flicker: this.rng.range(0, 9), distance: 8, when: () => this.ctx.camera.position.y < -0.5 || this.ctx.camera.position.y > 5 || Math.abs(this.ctx.camera.position.z - SCHOOL_HALL_Z) < 6 });
    report(0.72, 'People');
    await this.spawnPeople();
    this.buildInteractions();
    this.zones = [
      { id: 'pump_queue', test: (p) => Math.abs(p.x - (PUMP.x + 4.3)) < 1.6 && Math.abs(p.z - (PUMP.z + 0.2)) < 1.4, inside: false },
      { id: 'office', test: (p) => Math.abs(p.x) < 7 && p.z > FRONT + 0.6 && p.z < FRONT + 9, inside: false },
      { id: 'anchor', test: (p) => Math.hypot(p.x - ANCHOR.x, p.z - ANCHOR.z) < 2.2, when: () => this.stage() === 'return', inside: false },
    ];
    ctx.player.surfaceAt = (x, y, z) => ({ surface: y < -0.5 ? 'stone' : y > 2 ? 'wood' : Math.abs(z) < ROAD_HALF ? 'stone' : x < GAP.x1 && z < -FRONT ? 'rubble' : 'stone', speed: 1 });
    ctx.npcs.groundFn = (x, y, z) => ctx.world.groundHeight(x, y, z, 3);
    for (const n of ctx.npcs.npcs.values()) n.groundFn = ctx.npcs.groundFn;
    ctx.npcs.cullDistance = 80;
    report(0.94, 'Building collision');
    ctx.world.buildStatic('berlin45');
    report(1, 'Ready');
  }

  private buildMaterials(): void {
    const S = (set: string, o: Parameters<RuntimeBase['S']>[1] = {}) => this.S(set, o);
    this.M = {
      ...this.commonMaterials(),
      wall: S('berlin_render_facade'),
      wallGround: S('berlin_render_facade', { color: 0xb8b0a4 }),
      trim: S('render_stucco', { color: 0xc8c0b2 }),
      frame: S('painted_wood', { color: 0x8a8070 }),
      slab: S('concrete_board'),
      wallpaper: S('interior_wallpaper'),
      roof: S('roof_tiles', { color: 0x8a7a6e }),
      firewall: S('brick_french'),
      iron: S('pump_iron_green'),
      shutter: S('corrugated_iron'),
      charred: S('soot_scorch'),
      rubble: S('rubble_brick_plaster'),
      cobble: S('berlin_cobbles'),
      walk: S('berlin_sidewalk'),
      kerb: S('pavement_flags', { color: 0xa8a6a2 }),
      rail: S('rusty_steel', { metalness: 1 }),
      stair: S('terrazzo_stair'),
      whitewash: S('cellar_whitewash'),
      distemper: S('interior_paint_distemper'),
      parquet: S('parquet_oak'),
      timber: S('wood_beam'),
      planks: S('wood_planks'),
      schoolBrick: S('london_stock_brick', { color: 0xc89a82 }),
      earth: S('mud_wet', { color: 0x8c8274 }),
      metal: S('rusty_steel'),
      crate: S('crate_wood'),
      canvas: S('canvas_tent'),
      leaf: this.P({ color: 0x5f7d3a, roughness: 0.9, side: THREE.DoubleSide }),
      bark: this.P({ color: 0x4b3d30, roughness: 0.95 }),
    };
  }

  private buildGround(): void {
    const b = new Builder(this.tiles, BERLIN_SETS);
    // rubble ground under everything, with a hole for the cellar steps
    this.groundSlab(b, 'rubble', BOUNDS.minX - 40, BOUNDS.maxX + 40, BOUNDS.minZ - 30, BOUNDS.maxZ + 30, [{ x0: CELLAR.stairX - 0.95, x1: CELLAR.stairX + 0.95, z0: CELLAR.z0 - 0.5, z1: CELLAR.stairZ0 + 0.3 }]);
    // limits of the temporal field
    b.collider(BOUNDS.minX - 0.5, BOUNDS.minX, -3, 20, BOUNDS.minZ, BOUNDS.maxZ);
    b.collider(BOUNDS.maxX, BOUNDS.maxX + 0.5, -3, 20, BOUNDS.minZ, BOUNDS.maxZ);
    b.collider(BOUNDS.minX, BOUNDS.maxX, -3, 20, BOUNDS.maxZ - 0.5, BOUNDS.maxZ);
    b.collider(BOUNDS.minX, BOUNDS.maxX, -3, 20, BOUNDS.minZ, BOUNDS.minZ + 0.5);
    // blocked ends of the street: rubble barricades across the road (tram rails, paving, beams)
    for (const x of [BOUNDS.minX + 1.5, BOUNDS.maxX - 1.5]) {
      const m = new THREE.SphereGeometry(1, 14, 6, 0, Math.PI * 2, 0, Math.PI / 2);
      m.scale(2.6, 1.8, FRONT + 1);
      b.geo('rubble', m, new THREE.Matrix4().makeTranslation(x, -0.1, 0));
    }
    // Ackerweg north/south blocked by barricades too
    for (const z of [BOUNDS.minZ + 1.5, BOUNDS.maxZ - 1.5]) {
      const m = new THREE.SphereGeometry(1, 14, 6, 0, Math.PI * 2, 0, Math.PI / 2);
      m.scale(4.5, 1.6, 2.2);
      b.geo('rubble', m, new THREE.Matrix4().makeTranslation(CROSS_X, -0.1, z));
    }
    this.addBuilder(b);
  }

  private buildDetails(): void {
    const ctx = this.ctx;
    const tr = ctx.tracker;
    const B = new Builder(this.tiles, BERLIN_SETS);
    // the yard chestnut in new leaf (May)
    const ch = this.w.at.chestnut;
    const leafMat = tr.track(new THREE.MeshStandardMaterial({ map: leafTexture((x) => tr.track(x), 'spring'), alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.85 }));
    const tree = makeTree({ height: 11, crown: 4.2, seed: 12, leafMat, barkMat: this.M.bark, cards: 80 });
    tree.position.set(ch.x, 0.05, ch.z);
    tree.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) tr.track(m.geometry);
    });
    this.root.add(tree);
    B.collider(ch.x - 0.32, ch.x + 0.32, 0, 3, ch.z - 0.32, ch.z + 0.32);
    // the rest of the city: ruined blocks fading into the haze
    buildSkyline(this.root, (x) => tr.track(x), { center: new THREE.Vector2(4, -8), rMin: 105, rMax: 260, count: 140, hMin: 10, hMax: 24, color: 0x9a9286, ruined: 0.55, seed: 45 });
    // white sheets hung from windows on No. 14 and the corner house (surrender, early May)
    for (const [x, f] of [[17.6, 2], [24.0, 3], [30.2, 1], [42.5, 2], [51.8, 4]] as const) {
      const y = f * FLOOR_H + 0.8;
      const m = new THREE.PlaneGeometry(1.1, 1.8, 3, 4);
      const p = m.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < p.count; i++) p.setZ(i, Math.sin(p.getY(i) * 2 + p.getX(i)) * 0.06);
      m.computeVertexNormals();
      B.geo('sheet', m, new THREE.Matrix4().makeTranslation(x, y, -FRONT + 0.12));
    }
    // woodpile in the yard (planks for the stairs, firewood)
    const wp = new THREE.Vector3(-10.4, 0.05, -24.0);
    for (let k = 0; k < 7; k++) B.box('planks', wp.x - 0.15, wp.x + 0.15 + (k % 2) * 0.1, wp.y + k * 0.06, wp.y + k * 0.06 + 0.05, wp.z - 1.8, wp.z + 1.8, k === 0);
    this.w.at.woodpile = wp.clone().setY(0.5);
    // zinc tub by the cellar table, card boxes, buckets in the queue
    const t = this.w.at.cellarTable;
    B.geo('zinc', new THREE.CylinderGeometry(0.35, 0.3, 0.32, 16, 1, true), new THREE.Matrix4().makeTranslation(t.x + 1.0, t.y + 0.16, t.z));
    for (const dx of [0.9, 2.0, 3.1]) {
      B.geo('zinc', new THREE.CylinderGeometry(0.16, 0.13, 0.3, 12, 1, true), new THREE.Matrix4().makeTranslation(PUMP.x + 0.6 + dx + 0.3, 0.28, PUMP.z + 0.45));
    }
    // handcart left by the gateway
    B.box('timber', 3.0, 4.6, 0.45, 0.55, -FRONT + 1.2, -FRONT + 2.1, true);
    for (const z of [-FRONT + 1.15, -FRONT + 2.15]) B.geo('timber', new THREE.CylinderGeometry(0.42, 0.42, 0.06, 14).rotateX(Math.PI / 2), new THREE.Matrix4().makeTranslation(3.8, 0.42, z));
    B.box('timber', 4.6, 5.8, 0.5, 0.55, -FRONT + 1.6, -FRONT + 1.7);
    this.addBuilder(B);

    // chalk messages on the walls
    const messages = [
      'Familie Kuhn — alle leben!\nJetzt bei Schröder, Ackerweg 9',
      'Wer weiß etwas von\nErna Paulsen geb. Witt?',
      'Lotte Lenz lebt!\nSuche Vater (Lindenhofstr. 12)\nKomme Sonntag wieder',
      'Hausgemeinschaft Nr. 10\nim Keller Nr. 14',
      'Haus geräumt',
    ];
    this.w.chalkWalls.forEach((cw, i) => {
      const lines = i === 0 ? messages.slice(0, 3).join('\n\n') : messages[3 + ((i - 1) % 2)];
      const m = this.sign((c, w, h) => {
        c.clearRect(0, 0, w, h);
        c.fillStyle = 'rgba(238,236,228,0.88)';
        c.font = `${i === 0 ? 30 : 46}px "Segoe Script", "Brush Script MT", cursive`;
        let y = 52;
        for (const ln of lines.split('\n')) {
          c.save();
          c.translate(30 + Math.random() * 10, y);
          c.rotate((Math.random() - 0.5) * 0.06);
          c.fillText(ln, 0, 0);
          c.restore();
          y += i === 0 ? 36 : 52;
        }
      }, cw.w, cw.h, 768, 0.95);
      m.position.copy(cw.pos);
      m.rotation.y = cw.rotY;
      this.root.add(m);
    });
    this.w.at.chalkWall = this.w.chalkWalls[0].pos.clone();
    // Lenz's reply (written by the player)
    const reply = this.sign((c, w, h) => {
      c.clearRect(0, 0, w, h);
      c.fillStyle = 'rgba(240,238,230,0.9)';
      c.font = '40px "Segoe Script", "Brush Script MT", cursive';
      c.fillText('Lotte — Vater lebt!', 24, 56);
      c.fillText('Keller Lindenhofstr. 12', 24, 110);
    }, 2.4, 0.8, 512, 0.95);
    reply.position.copy(this.w.chalkWalls[0].pos).add(new THREE.Vector3(-0.01, -1.4, 2.4));
    reply.rotation.y = -Math.PI / 2;
    reply.visible = false;
    reply.name = 'chalk-reply';
    this.root.add(reply);
    // posters on the advertising pillar: orders of the city commandant, a search notice
    for (let k = 0; k < 4; k++) {
      const a = (k / 4) * Math.PI * 2 + 0.4;
      const m = this.sign((c, w, h) => {
        c.fillStyle = k % 2 ? '#e7e2d2' : '#ede9dd';
        c.fillRect(0, 0, w, h);
        c.fillStyle = '#1b1b1b';
        c.font = 'bold 34px Georgia, serif';
        c.textAlign = 'center';
        c.fillText(k === 0 ? 'BEKANNTMACHUNG' : k === 1 ? 'ПРИКАЗ' : k === 2 ? 'BEFEHL' : 'GESUCHT', w / 2, 52);
        c.font = '18px Georgia, serif';
        for (let l = 0; l < 14; l++) c.fillRect(30, 84 + l * 22, w - 60 - ((l * 37) % 90), 6);
      }, 0.9, 1.25, 320, 0.9);
      m.position.set(LITFASS.x + Math.sin(a) * 0.73, 2.0, LITFASS.z + Math.cos(a) * 0.73);
      m.rotation.y = a;
      this.root.add(m);
    }
    // a Cyrillic street sign at the crossing (direction board)
    const rs = this.sign((c, w, h) => {
      c.fillStyle = '#d9d2b8';
      c.fillRect(0, 0, w, h);
      c.strokeStyle = '#222';
      c.lineWidth = 5;
      c.strokeRect(5, 5, w - 10, h - 10);
      c.fillStyle = '#1a1a1a';
      c.font = 'bold 54px Arial, sans-serif';
      c.textAlign = 'center';
      c.fillText('КОМЕНДАТУРА →', w / 2, h / 2 + 18);
    }, 1.6, 0.38, 512, 0.9);
    rs.position.set(CROSS_X - 4.6, 2.4, ROAD_HALF + 1.2);
    rs.rotation.y = -Math.PI / 2;
    this.root.add(rs);
    const post = new THREE.Mesh(tr.track(new THREE.CylinderGeometry(0.05, 0.05, 2.6, 8)), this.M.timber);
    post.position.set(CROSS_X - 4.6, 1.3, ROAD_HALF + 1.2);
    this.root.add(post);

    // cellar details: shelter arrow at the steps, a hand pump and sand bucket, the radio on the table
    const ss = this.sign((c, w, h) => {
      c.fillStyle = '#e9e5da';
      c.fillRect(0, 0, w, h);
      c.fillStyle = '#141414';
      c.font = 'bold 64px Arial, sans-serif';
      c.textAlign = 'center';
      c.fillText('LSR', w / 2 - 60, h / 2 + 22);
      c.beginPath();
      c.moveTo(w - 150, h / 2 - 30);
      c.lineTo(w - 40, h / 2);
      c.lineTo(w - 150, h / 2 + 30);
      c.fill();
      c.fillRect(w - 230, h / 2 - 10, 90, 20);
    }, 0.7, 0.3, 512, 0.9);
    ss.position.set(CELLAR.stairX - 0.94, 0.55, CELLAR.stairZ0 - 1.0);
    ss.rotation.y = Math.PI / 2;
    this.root.add(ss);
    this.w.at.shelterSign = ss.position.clone();
    const sp = new THREE.Vector3(CELLAR.stairX + 0.4, CELLAR.floorY, CELLAR.z0 - 0.9);
    const red = this.P({ color: 0x7a1b14, roughness: 0.5 });
    const pail = new THREE.Mesh(tr.track(new THREE.CylinderGeometry(0.15, 0.12, 0.3, 12)), red);
    pail.position.copy(sp).setY(sp.y + 0.15);
    const pumpRod = new THREE.Mesh(tr.track(new THREE.CylinderGeometry(0.02, 0.02, 0.8, 8)), this.M.zinc);
    pumpRod.position.copy(sp).setY(sp.y + 0.55);
    const sand = new THREE.Mesh(tr.track(new THREE.CylinderGeometry(0.15, 0.12, 0.3, 12)), red);
    sand.position.copy(sp).add(new THREE.Vector3(0.4, 0.15, 0));
    this.root.add(pail, pumpRod, sand);
    this.w.at.stirrup = sp.clone().setY(sp.y + 0.5);
    const radio = new THREE.Group();
    const cab = new THREE.Mesh(tr.track(new THREE.BoxGeometry(0.28, 0.32, 0.18)), this.P({ color: 0x24201c, roughness: 0.4 }));
    const grille = new THREE.Mesh(tr.track(new THREE.CircleGeometry(0.08, 16)), this.P({ color: 0x8a7a5a, roughness: 0.9 }));
    grille.position.set(0, 0.04, 0.091);
    radio.add(cab, grille);
    radio.position.copy(this.w.at.cellarTable).add(new THREE.Vector3(0.25, 0.92, 0));
    this.root.add(radio);
    this.w.at.radio = radio.position.clone();
    // movable props
    const tin = new THREE.Mesh(tr.track(new THREE.BoxGeometry(0.26, 0.1, 0.18)), this.M.zinc);
    tin.position.copy(this.w.at.papers);
    tin.castShadow = true;
    this.root.add(tin);
    this.papersProp = tin;
    const wood = new THREE.Group();
    for (let k = 0; k < 3; k++) {
      const m = new THREE.Mesh(tr.track(new THREE.BoxGeometry(0.24, 0.05, 2.0)), this.M.planks);
      m.position.set((k - 1) * 0.26, 0.4, 0);
      wood.add(m);
    }
    wood.position.copy(this.w.at.woodpile).setY(0.05);
    wood.position.x += 0.8;
    this.root.add(wood);
    this.woodpile = wood;
    // the unexploded shell, half buried in rubble
    const shell = new THREE.Group();
    const body = new THREE.Mesh(tr.track(new THREE.CylinderGeometry(0.075, 0.075, 0.55, 14)), this.M.metal);
    const nose = new THREE.Mesh(tr.track(new THREE.ConeGeometry(0.075, 0.2, 14)), this.M.metal);
    nose.position.y = 0.37;
    shell.add(body, nose);
    shell.rotation.z = 1.2;
    shell.position.set(UXB.x, 0.25, UXB.z);
    this.root.add(shell);
    this.shellProp = shell;
    // two buckets that go with the player (shown at the cellar table once delivered)
    const buckets = new THREE.Group();
    for (const dx of [-0.25, 0.25]) {
      const m = new THREE.Mesh(tr.track(new THREE.CylinderGeometry(0.16, 0.13, 0.3, 12, 1, true)), this.M.zinc);
      m.position.set(dx, 0.15, 0);
      buckets.add(m);
    }
    buckets.position.copy(this.w.at.cellarTable).add(new THREE.Vector3(1.7, 0, 0.4));
    buckets.visible = false;
    this.root.add(buckets);
    this.bucketsProp = buckets;
  }

  // ======================================================================= people
  private async spawnPeople(): Promise<void> {
    await this.loadCast(CAST);
    const V = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
    const sp = (id: string, name: string, p: THREE.Vector3, yaw: number, pose = 'idle', extra: { attentive?: boolean; walkSpeed?: number } = {}) => this.spawnCast(id, name, CAST[id], p, yaw, pose, extra);
    const cb = this.w.at.cellarBottom;
    sp('brandt', 'Frau Brandt', V(-1.2, 0.05, -23.6), 0.2, 'idle');
    sp('peter', 'Peter', V(-3.6, 0.05, -26.8), 1.2, this.clip('sit_ground', 'idle'), { walkSpeed: 1.8 });
    sp('lenz', 'Herr Lenz', V(this.w.at.cellarTable.x - 0.9, CELLAR.floorY, this.w.at.cellarTable.z + 0.2), Math.PI / 2, 'idle');
    sp('lotte', 'Lotte Lenz', V(CROSS_X - 2, 0.13, -FRONT + 2), -Math.PI / 2, 'idle', { walkSpeed: 1.5 });
    sp('clerk', 'Clerk', this.w.at.clerk.clone(), Math.PI, 'idle');
    // queue at the pump (facing the pump, westwards along the pavement)
    this.queueIds.forEach((id, i) => sp(id, 'Woman in the queue', V(PUMP.x + 0.9 + i * 1.1, 0.13, PUMP.z + 0.25), -Math.PI / 2, i === 0 ? 'kneel_work' : 'idle', { attentive: i > 0 }));
    // office queue
    sp('o1', 'Waiting', V(-0.6, 0.15, FRONT + 3.2), 0, 'idle');
    sp('o2', 'Waiting', V(0.6, 0.15, FRONT + 4.1), 0.2, 'idle_alt');
    // bucket chain at No. 10
    ['c1', 'c2', 'c3', 'c4'].forEach((id, i) => sp(id, 'Neighbour clearing rubble', V(RUBBLE_CHAIN.x + i * 1.3, 0.13, RUBBLE_CHAIN.z + (i % 2) * 0.3), Math.PI / 2, i === 0 ? 'kneel_work' : 'idle', { attentive: false }));
    // children in the bombed gap
    sp('k1', 'Boy', V(UXB.x + 1.2, 0.3, UXB.z + 0.8), -2.2, 'kneel_work', { walkSpeed: 1.8 });
    sp('k2', 'Girl', V(UXB.x - 1.0, 0.3, UXB.z + 1.4), 2.6, 'idle', { walkSpeed: 1.7 });
    sp('k3', 'Boy', V(UXB.x + 0.2, 0.3, UXB.z + 2.2), Math.PI, this.clip('point', 'idle'), { walkSpeed: 1.8 });
    sp('regulator', 'Soviet traffic regulator', V(CROSS_X, 0.02, 0), -Math.PI / 2, this.clip('point', 'idle'));
    sp('sapper', 'Soviet sapper', V(CROSS_X + 1.5, 0.02, -8), -Math.PI / 2, 'idle', { walkSpeed: 1.5 });
    sp('kaminski', 'Frau Kaminski', V(10.2, 0.05, -24.8), -Math.PI / 2, 'idle');
    void cb;
  }

  // ======================================================================= interactions
  private buildInteractions(): void {
    const ctx = this.ctx;
    const I = ctx.interactions;
    const f = (k: string): boolean => this.f(k);
    this.talk('brandt', 'brandt', 'Talk to Frau Brandt');
    this.talk('lenz', 'lenz', 'Talk to Herr Lenz');
    this.talk('clerk', 'clerk', 'Speak to the clerk', () => f('event.office_turn'));
    this.talk('peter', 'peter', 'Talk to Peter');
    this.talk('lotte', 'lotte', 'Talk to Lotte', () => f('event.lotte_arrived'));
    this.talk('regulator', 'regulator', 'Speak to the traffic regulator', () => this.shellState === 'active');
    this.talk('sapper', 'sapper', 'Talk to the sapper', () => f('event.sapper_called'));
    this.talk('kaminski', 'kaminski', 'Talk to Frau Kaminski');
    this.talk('q3', 'queue', 'Talk to the people in the queue', () => this.queueLeft > 0);
    // the pump: only when it is your turn
    I.add({
      id: 'pump',
      position: this.w.at.pump.clone(),
      radius: 0.5,
      range: 2.4,
      holdTime: 3.0,
      prompt: () => (!ctx.facts.hasItem('buckets') ? 'You have no buckets' : this.queueLeft > 0 ? 'Wait your turn in the queue' : 'Work the pump handle to fill the buckets'),
      enabled: () => (this.stage() === 'water' || ctx.missions.state.get('kettle')?.state === 'active') && !ctx.player.carrying,
      onInteract: () => {
        if (!ctx.facts.hasItem('buckets') || this.queueLeft > 0) return;
        ctx.facts.removeItem('buckets');
        ctx.missions.runEffect({ giveItem: 'water' });
        ctx.player.carrying = true;
        ctx.facts.set(this.stage() === 'water' ? 'event.water_pumped' : 'event.kettle_pumped');
        ctx.events.emit('soundCue', { id: 'pump', label: 'Pump handle squeaking, water splashing', intensity: 0.4 });
        ctx.events.emit('notify', { text: 'Carrying two full buckets: you cannot run or climb.', kind: 'info' });
      },
    });
    // set the water down at the cellar table (or at Frau Kaminski's door)
    I.add({
      id: 'deliver_water',
      position: this.w.at.cellarTable.clone().add(new THREE.Vector3(1.4, 0.8, 0)),
      radius: 0.6,
      range: 2.6,
      prompt: 'Set the buckets down by the table',
      enabled: () => ctx.player.carrying && ctx.facts.hasItem('water') && f('event.water_pumped') && !f('event.water_delivered'),
      onInteract: () => {
        ctx.facts.removeItem('water');
        ctx.player.carrying = false;
        this.bucketsProp.visible = true;
        ctx.facts.set('event.water_delivered');
        ctx.missions.runEffect({ giveItem: 'buckets' });
      },
    });
    I.add({
      id: 'kaminski_water',
      position: new THREE.Vector3(),
      object: this.npc.kaminski?.root,
      offsetY: 1.0,
      radius: 0.6,
      range: 2.6,
      prompt: 'Give Frau Kaminski the water',
      enabled: () => ctx.player.carrying && ctx.facts.hasItem('water') && f('event.kettle_pumped'),
      onInteract: () => {
        ctx.facts.removeItem('water');
        ctx.player.carrying = false;
        ctx.facts.set('event.kaminski_water');
      },
    });
    // the chalk wall
    I.add({
      id: 'read_wall',
      position: this.w.at.chalkWall.clone(),
      radius: 1.6,
      range: 3.5,
      prompt: 'Read the messages chalked on the wall',
      onInteract: () => {
        ctx.facts.set('event.read_wall');
        ctx.readDocument('Messages on the firewall', 'Familie Kuhn — alle leben! Jetzt bei Schröder, Ackerweg 9.\n(The Kuhn family — all alive! Now with Schröder, Ackerweg 9.)\n\nWer weiß etwas von Erna Paulsen geb. Witt?\n(Does anyone know anything of Erna Paulsen, née Witt?)\n\nLotte Lenz lebt! Suche Vater (Lindenhofstr. 12). Komme Sonntag wieder.\n(Lotte Lenz is alive! Looking for my father (Lindenhofstr. 12). Will come back on Sunday.)\n\nThe people and messages are fiction. Chalked messages like these were written on ruins across Berlin.');
      },
    });
    I.add({
      id: 'write_chalk',
      position: this.w.at.chalkWall.clone().add(new THREE.Vector3(0, -1.0, 2.4)),
      radius: 0.9,
      range: 3.0,
      holdTime: 2.0,
      prompt: 'Chalk Herr Lenz’s answer under Lotte’s message',
      enabled: () => f('event.read_wall') && f('dlg.lenz.walls') && !f('event.chalk_written'),
      onInteract: () => {
        ctx.facts.set('event.chalk_written');
        const r = this.root.getObjectByName('chalk-reply');
        if (r) r.visible = true;
      },
    });
    // planks for the stairs
    I.add({
      id: 'take_planks',
      position: new THREE.Vector3(),
      object: this.woodpile,
      offsetY: 0.5,
      radius: 0.8,
      range: 2.6,
      prompt: 'Take three planks',
      enabled: () => this.woodpile.visible && f('dlg.lenz.papers') && !ctx.player.carrying,
      onInteract: () => {
        this.woodpile.visible = false;
        ctx.player.carrying = true;
        ctx.facts.set('event.planks_taken');
      },
    });
    I.add({
      id: 'place_planks',
      position: this.w.at.brokenLow.clone().add(new THREE.Vector3(0, 0.3, 0)),
      radius: 0.7,
      range: 2.8,
      holdTime: 1.5,
      prompt: () => (ctx.player.carrying && f('event.planks_taken') ? 'Lay the planks across the gap' : 'Steps are missing here. Planks might bridge the gap'),
      enabled: () => !f('event.planks_placed'),
      onInteract: () => {
        if (!(ctx.player.carrying && f('event.planks_taken'))) return;
        ctx.player.carrying = false;
        this.setPlanks(true);
        ctx.facts.set('event.planks_placed');
      },
    });
    I.add({
      id: 'papers',
      position: new THREE.Vector3(),
      object: this.papersProp,
      offsetY: 0.05,
      radius: 0.3,
      range: 2.4,
      prompt: 'Take the tin box with the Lenz family papers',
      enabled: () => this.papersProp.visible,
      onInteract: () => {
        this.papersProp.visible = false;
        ctx.missions.runEffect({ giveItem: 'papers' });
      },
    });
    // the unexploded shell: send the children away
    (['k1', 'k2', 'k3'] as const).forEach((id, i) => {
      const n = this.npc[id];
      I.add({
        id: `send_${id}`,
        position: new THREE.Vector3(),
        object: n?.root,
        offsetY: 1.0,
        radius: 0.5,
        range: 2.8,
        prompt: 'Send the child away from the shell',
        enabled: () => this.shellState === 'active' && !f(`event.kid_${i + 1}`) && !!n,
        onInteract: () => {
          ctx.facts.set(`event.kid_${i + 1}`);
          n?.walkPath([new THREE.Vector3(GAP.x1 + 4, 0.13, -FRONT + 1.5), new THREE.Vector3(NO12.gate.x0 + 1.8, 0.13, -FRONT + 0.6), new THREE.Vector3(-2 + i, 0.05, -25 - i)], () => n.setPose('idle'));
          ctx.events.emit('subtitle', { speaker: n?.name ?? 'Child', text: ['But we found it!', 'All right, all right…', 'Can we watch from the gate?'][i], duration: 2.5 });
        },
      });
    });
    // the rubble chain
    I.add({
      id: 'chain',
      position: new THREE.Vector3(RUBBLE_CHAIN.x - 1.0, 1.2, RUBBLE_CHAIN.z + 0.3),
      radius: 0.7,
      range: 2.4,
      prompt: () => (this.chainCue >= 0 ? 'Take the bucket and pass it on' : 'Join the chain (wait for the next bucket)'),
      enabled: () => this.stage() === 'chain' && this.chainCount < 5,
      onInteract: () => {
        if (this.chainCue >= 0) {
          this.chainCount++;
          this.chainCue = -1;
          this.chainT = 1.2;
          this.npc.c1?.play('kneel_work', 0.2);
          this.dust.burst(new THREE.Vector3(RUBBLE_CHAIN.x - 2.2, 0.4, RUBBLE_CHAIN.z - 1.2), 3, 0.8, 0.4, 2, 0.4, 0xb0a594, 0.3);
          if (this.chainCount >= 5) {
            ctx.facts.set('event.chain_done');
            ctx.events.emit('subtitle', { speaker: 'Neighbour', text: 'That’ll do for now. Thank you. The doorway is clear.', duration: 3.5 });
          }
        }
      },
    });
    // optional firewood: three pieces in the rubble of No. 10
    for (let i = 1; i <= 3; i++) {
      const p = new THREE.Vector3(-33 + i * 3.2, 0.25, -FRONT + 1.0 + (i % 2) * 0.6);
      const m = new THREE.Mesh(this.ctx.tracker.track(new THREE.BoxGeometry(0.9, 0.09, 0.12)), this.M.timber);
      m.position.copy(p);
      m.rotation.y = i;
      this.root.add(m);
      I.add({
        id: `wood_${i}`,
        position: p.clone(),
        radius: 0.45,
        range: 2.4,
        prompt: 'Pick up a piece of broken timber (firewood)',
        enabled: () => ctx.missions.state.get('firewood')?.state === 'active' && !f(`event.wood_${i}`),
        onInteract: () => {
          ctx.facts.set(`event.wood_${i}`);
          m.visible = false;
        },
      });
    }
    I.add({
      id: 'stove',
      position: new THREE.Vector3(CELLAR.stairX - 2.0, CELLAR.floorY + 0.6, CELLAR.z1 + 0.9),
      radius: 0.5,
      range: 2.4,
      prompt: 'Stack the firewood by the stove',
      enabled: () => f('event.wood_1') && f('event.wood_2') && f('event.wood_3') && !f('event.wood_delivered'),
      onInteract: () => ctx.facts.set('event.wood_delivered'),
    });
    // scanner targets (ids must match the chapter config)
    const at = this.w.at;
    this.scanPoint('obj_pump', 'scan_street_pump', at.pump.clone(), 0.5);
    this.scanPoint('obj_buckets', 'scan_water_buckets', new THREE.Vector3(PUMP.x + 2.5, 0.35, PUMP.z + 0.45), 0.6);
    this.scanPoint('obj_chalk', 'scan_chalk_messages', at.chalkWall.clone(), 1.4);
    this.scanPoint('obj_litfass', 'scan_kommandantura_notice', at.litfass.clone(), 0.8);
    this.scanPoint('obj_tram', 'scan_tram', at.tram.clone(), 1.5);
    this.scanPoint('obj_shelter_sign', 'scan_shelter_sign', at.shelterSign.clone(), 0.5);
    this.scanPoint('obj_stirrup_pump', 'scan_stirrup_pump', at.stirrup.clone(), 0.4);
    this.scanPoint('obj_radio', 'scan_volksempfaenger', at.radio.clone(), 0.3);
    this.scanPoint('obj_armband', 'scan_white_armband', new THREE.Vector3(), 0.3, this.npc.lenz?.root, 1.3);
    this.scanPoint('obj_cyrillic', 'scan_cyrillic_sign', new THREE.Vector3(CROSS_X - 4.6, 2.4, ROAD_HALF + 1.2), 0.8);
    this.scanPoint('obj_handcart', 'scan_handcart', new THREE.Vector3(4.0, 0.6, -FRONT + 1.65), 0.8);
    this.scanPoint('obj_stove', 'scan_coal_stove', new THREE.Vector3(LENZ_FLAT.x1 - 0.4, LENZ_FLAT.floor * FLOOR_H + 0.9, LENZ_FLAT.z1 - 0.75), 0.5);
    this.scanPoint('obj_ration_cards', 'scan_ration_card', at.counter.clone(), 0.5);
  }

  private setPlanks(on: boolean): void {
    this.planksGroup.visible = on;
    this.ctx.world.setEnabled('planks', on);
  }

  // ======================================================================= checkpoints
  readonly killY = -12;
  readonly visibilityLimit = 600;

  resolveSpawnHeight(x: number, z: number): number {
    return (this.ctx.world.groundHeight(x, 2.5, z, 10) ?? 0.13) + 0.05;
  }

  applyCheckpoint(id: string, script: Record<string, unknown>): void {
    void script;
    void id;
    const ctx = this.ctx;
    const f = (k: string): boolean => this.f(k);
    this.timers.length = 0;
    ctx.setDanger(null);
    ctx.player.carrying = false;
    ctx.facts.set('sequence.active', false);
    this.completed = false;
    if (ctx.facts.hasItem('water')) ctx.facts.removeItem('water');
    if (f('event.water_pumped') && !f('event.water_delivered')) ctx.facts.set('event.water_pumped', false);
    if (!f('event.water_delivered') && !ctx.facts.hasItem('buckets') && f('dlg.brandt.water')) ctx.missions.runEffect({ giveItem: 'buckets' });
    this.bucketsProp.visible = f('event.water_delivered');
    this.setPlanks(f('event.planks_placed'));
    this.woodpile.visible = !f('event.planks_taken') || f('event.planks_placed') ? !f('event.planks_taken') : true;
    if (f('event.planks_taken') && !f('event.planks_placed')) {
      ctx.facts.set('event.planks_taken', false);
      this.woodpile.visible = true;
    }
    this.papersProp.visible = !ctx.facts.hasItem('papers') && !f('item.papers');
    const reply = this.root.getObjectByName('chalk-reply');
    if (reply) reply.visible = f('event.chalk_written');
    // the pump queue resets unless the water was already fetched
    this.queueLeft = f('event.water_pumped') || f('event.water_delivered') ? 0 : 3;
    this.queueT = 0;
    this.queueIds.forEach((qid, i) => {
      const gone = i < 3 - this.queueLeft;
      this.place(qid, new THREE.Vector3(PUMP.x + 0.9 + i * 1.1, 0.13, PUMP.z + 0.25), -Math.PI / 2, i === 0 ? 'kneel_work' : 'idle', !gone);
    });
    if (this.queueLeft === 0) this.queueLeft = 0;
    // office queue
    this.officeQueueT = 0;
    if (!f('event.office_turn')) {
      this.place('o1', new THREE.Vector3(-0.6, 0.15, FRONT + 3.2), 0, 'idle');
      this.place('o2', new THREE.Vector3(0.6, 0.15, FRONT + 4.1), 0.2, 'idle_alt');
    }
    // the shell
    const cleared = f('event.shell_cleared');
    this.shellState = cleared ? 'done' : 'none';
    this.shellProp.visible = !cleared;
    const kidsHome = cleared || f('event.kid_1');
    ['k1', 'k2', 'k3'].forEach((kid, i) => {
      if (cleared || f(`event.kid_${i + 1}`)) this.place(kid, new THREE.Vector3(-2 + i, 0.05, -25 - i), 0, 'idle');
      else this.place(kid, new THREE.Vector3(UXB.x + [1.2, -1.0, 0.2][i], 0.3, UXB.z + [0.8, 1.4, 2.2][i]), [-2.2, 2.6, Math.PI][i], ['kneel_work', 'idle', this.clip('point', 'idle')][i]);
    });
    void kidsHome;
    this.place('sapper', new THREE.Vector3(CROSS_X + 1.5, 0.02, -8), -Math.PI / 2, 'idle', f('event.sapper_called') && !cleared);
    this.place('regulator', new THREE.Vector3(CROSS_X, 0.02, 0), -Math.PI / 2, this.clip('point', 'idle'));
    // chain
    this.chainCount = f('event.chain_done') ? 5 : 0;
    this.chainCue = -1;
    this.chainT = 2;
    // reunion
    this.reunionStarted = false;
    if (f('event.lotte_arrived')) this.place('lotte', new THREE.Vector3(this.w.at.cellarTable.x + 0.3, CELLAR.floorY, this.w.at.cellarTable.z - 0.8), Math.PI / 2, 'talk');
    else this.place('lotte', new THREE.Vector3(CROSS_X - 2, 0.13, -FRONT + 2), -Math.PI / 2, 'idle', false);
    ctx.audio.setLoop('wind', 'wind', 0.14);
  }

  // ======================================================================= update
  update(dt: number, time: number): void {
    const ctx = this.ctx;
    this.time += dt;
    this.tickTimers(dt);
    const p = ctx.player.position;
    this.tickZones(p);
    const cam = ctx.camera.position;
    const inCellar = cam.y < -0.4 && cam.z < CELLAR.z0 + 0.5;
    const inStair = cam.x > WING_STAIR.x0 - 0.1 && cam.x < LENZ_FLAT.x1 && cam.z > WING_STAIR.z0 && cam.z < WING_STAIR.z1 + 0.2;
    const inOffice = Math.abs(cam.x) < 7 && cam.z > FRONT + 0.4 && cam.z < FRONT + 9.5;
    ctx.env.setIndoor(inCellar ? 1 : inStair || inOffice ? 0.7 : 0);
    ctx.audio.muffled = inCellar ? 1 : 0;
    this.updateScript(dt);
    this.tickLights(time);
    this.updateMarkers();
    this.dust.update(dt, ctx.camera);
    this.boundary(p, (q) => q.x > BOUNDS.minX + 2 && q.x < BOUNDS.maxX - 2 && q.z < BOUNDS.maxZ - 2 && q.z > BOUNDS.minZ + 2);
    this.tickCompletion();
  }

  private updateScript(dt: number): void {
    const ctx = this.ctx;
    const f = (k: string): boolean => this.f(k);
    const st = this.stage();
    const kettle = ctx.missions.state.get('kettle')?.state === 'active';
    // ---- pump queue: while you wait in line, the people ahead take their turn and leave
    if ((st === 'water' || kettle) && this.queueLeft > 0 && f('zone.pump_queue') && this.zones.find((z) => z.id === 'pump_queue')?.inside) {
      this.queueT += dt;
      if (this.queueT > 5) {
        this.queueT = 0;
        const idx = 3 - this.queueLeft;
        const n = this.npc[this.queueIds[idx]];
        n?.walkPath([new THREE.Vector3(PUMP.x - 3, 0.13, PUMP.z + 0.5), new THREE.Vector3(PUMP.x - 14, 0.13, PUMP.z + 1.2)], () => n.setVisible(false));
        this.queueLeft--;
        // the next in line steps up to the pump
        const next = this.npc[this.queueIds[idx + 1]];
        if (next) {
          next.walkPath([new THREE.Vector3(PUMP.x + 0.9, 0.13, PUMP.z + 0.25)], () => {
            next.faceTowards(new THREE.Vector3(PUMP.x, 0, PUMP.z));
            next.setPose('kneel_work');
          });
        }
        ctx.events.emit('soundCue', { id: 'pump', label: 'Pump handle squeaking', intensity: 0.3 });
        if (this.queueLeft === 0) ctx.events.emit('notify', { text: 'Your turn at the pump.', kind: 'info' });
      }
    }
    // a second trip for Frau Kaminski uses the same queue (already empty) — give buckets back
    // ---- office queue: wait your turn in the corridor
    if (st === 'cards' && !f('event.office_turn') && this.zones.find((z) => z.id === 'office')?.inside) {
      this.officeQueueT += dt;
      if (this.officeQueueT > 6) {
        ctx.facts.set('event.office_turn');
        for (const id of ['o1', 'o2']) {
          const n = this.npc[id];
          n?.walkPath([new THREE.Vector3(id === 'o1' ? -3 : 3, 0.15, FRONT + 2), new THREE.Vector3(id === 'o1' ? -3 : 3, 0.13, FRONT - 2)], () => n.setVisible(false));
        }
        ctx.events.emit('subtitle', { speaker: 'Clerk', text: 'Next, please.', duration: 2 });
      }
    }
    // ---- the shell: starts when you come back up the street with the new cards
    if (st === 'shell' && this.shellState === 'none' && ctx.player.position.y > -0.5 && ctx.player.position.z > -FRONT - 1) {
      this.shellState = 'active';
      const peter = this.npc.peter;
      if (peter) {
        peter.teleport(new THREE.Vector3(GAP.x1 + 6, 0.13, -FRONT + 1.2));
        peter.walkPath([ctx.player.position.clone().add(new THREE.Vector3(1.2, 0, 0.6))], () => peter.setPose('idle'));
      }
      ctx.events.emit('subtitle', { speaker: 'Peter', text: 'Come quick! The Krüger boys have found a shell in the rubble at the end of the street. They’re poking it with sticks!', duration: 5 });
    }
    // the regulator sends for a sapper, who walks down from the crossing
    if (this.shellState === 'active' && f('event.sapper_called') && this.npc.sapper && !this.npc.sapper.visible) {
      const sp = this.npc.sapper;
      sp.setVisible(true);
      sp.teleport(new THREE.Vector3(CROSS_X + 1.5, 0.02, -2));
      sp.walkPath([new THREE.Vector3(CROSS_X - 3, 0.02, 0.5), new THREE.Vector3(GAP.x1 + 3, 0.02, -2.0), new THREE.Vector3(GAP.x1 + 1.5, 0.13, -FRONT + 1.4)], () => sp.faceTowards(new THREE.Vector3(UXB.x, 0, UXB.z)));
    }
    if (this.shellState === 'active' && f('event.kid_1') && f('event.kid_2') && f('event.kid_3') && f('event.sapper_called') && f('dlg.sapper.ready') && !f('event.shell_cleared') && !ctx.ui.dialogueOpen) {
      this.shellState = 'prompt';
      void ctx
        .confirmIntense('Controlled demolition', 'The sapper blows the shell up where it lies. You will hear a loud explosion and see a cloud of dust from a safe distance, with some camera shake (your shake and flash settings apply). No one is hurt.\n\nYou can skip it. The mission continues with the shell made safe.')
        .then((r) => (r === 'skip' ? this.skipSequence() : this.startBlast()));
    }
    if (this.shellState === 'blast') {
      this.blastT += dt;
      if (this.blastT > 3 && this.blastT - dt <= 3) {
        const pos = new THREE.Vector3(UXB.x, 0.3, UXB.z);
        const d = pos.distanceTo(ctx.player.position);
        ctx.audio.impact(pos.x, pos.z, d, 'Controlled explosion');
        ctx.env.triggerFlash(pos.clone().sub(ctx.player.position).setY(0.3).normalize(), 0.25, 0xffd2a0, 5);
        ctx.player.addTrauma(Math.max(0.1, 0.5 - d / 80));
        this.dust.burst(pos.clone().setY(1), 22, 6, 6, 6, 2.6, 0xa89c8a, 0.5);
        this.shellProp.visible = false;
      }
      if (this.blastT > 6) this.finishShell();
    }
    // ---- rubble chain rhythm: a bucket arrives every few seconds
    if (st === 'chain' && this.chainCount < 5) {
      this.chainT -= dt;
      if (this.chainCue < 0 && this.chainT <= 0) {
        this.chainCue = 1;
        this.npc.c2?.play('carry_walk', 0.2, 0.01);
        ctx.events.emit('soundCue', { id: 'bucket', label: 'Bucket of rubble handed to you', intensity: 0.3 });
      }
    }
    // ---- reunion: Lotte comes back to look for her father once the answer is on the wall
    if (st === 'reunion' && !this.reunionStarted && !f('event.lotte_arrived')) {
      this.reunionStarted = true;
      const lotte = this.npc.lotte;
      if (lotte) {
        lotte.setVisible(true);
        lotte.teleport(new THREE.Vector3(FIREWALL.x + 3, 0.13, -FRONT + 1.5), -Math.PI / 2);
        lotte.walkPath(
          [new THREE.Vector3(NO12.gate.x0 + 1.8, 0.13, -FRONT + 1.0), new THREE.Vector3(0, 0.05, -FRONT - 6), new THREE.Vector3(CELLAR.stairX, 0.05, CELLAR.stairZ0 + 0.8), new THREE.Vector3(CELLAR.stairX, CELLAR.floorY, CELLAR.z0 - 1.2), new THREE.Vector3(this.w.at.cellarTable.x + 0.3, CELLAR.floorY, this.w.at.cellarTable.z - 0.8)],
          () => {
            ctx.facts.set('event.lotte_arrived');
            lotte.faceTowards(this.npc.lenz?.root.position ?? lotte.root.position);
            lotte.setPose('talk');
            ctx.events.emit('subtitle', { speaker: 'Lotte Lenz', text: 'Papa! I saw it on the wall. I saw your answer!', duration: 4 });
          },
        );
      }
    }
  }

  private startBlast(): void {
    this.shellState = 'blast';
    this.blastT = 0;
    this.ctx.facts.set('sequence.active');
    this.ctx.events.emit('subtitle', { speaker: 'Soviet sapper', text: 'Внимание! Achtung! Weg, weg!', duration: 2.6 });
  }

  private finishShell(): void {
    this.shellState = 'done';
    this.ctx.facts.set('event.shell_cleared');
    this.ctx.facts.set('sequence.active', false);
    this.npc.sapper?.walkPath([new THREE.Vector3(CROSS_X + 1.5, 0.02, -8)], () => this.npc.sapper?.setVisible(false));
  }

  skipSequence(): void {
    this.shellProp.visible = false;
    this.finishShell();
    this.ctx.events.emit('notify', { text: 'The sapper has blown up the shell where it lay.', kind: 'info' });
  }

  private updateMarkers(): void {
    const ctx = this.ctx;
    const cur = ctx.missions.currentObjective();
    const id = cur?.objective.marker;
    if (!id) return ctx.setMarker('objective', null);
    const p = ctx.player.position;
    const at = this.w.at;
    const cellar = at.cellarTable.clone().setY(CELLAR.floorY + 1.8);
    const toCellar = p.y > -0.5 ? at.cellarStairTop.clone().setY(1.6) : cellar;
    const yard = new THREE.Vector3(0, 2.6, -FRONT - 2);
    const inYard = p.z < -FRONT - 12 || p.y < -0.5;
    let pos: THREE.Vector3 | null = null;
    let label = '';
    switch (id) {
      case 'brandt':
        pos = this.npc.brandt?.root.position.clone().setY(2.1) ?? yard;
        label = 'Frau Brandt';
        break;
      case 'pump':
        pos = at.pump.clone().setY(2.4);
        label = this.queueLeft > 0 ? 'Queue at the pump' : 'Street pump';
        break;
      case 'cellar':
      case 'lenz':
        pos = inYard ? toCellar : yard;
        label = id === 'lenz' ? 'Herr Lenz (cellar)' : 'Cellar';
        break;
      case 'wall':
        pos = at.chalkWall.clone().setY(3);
        label = 'Chalk messages';
        break;
      case 'papers':
        if (!this.f('event.planks_placed')) {
          pos = ctx.player.carrying ? at.brokenLow.clone().setY(at.brokenLow.y + 1.2) : at.woodpile.clone().setY(1.6);
          label = ctx.player.carrying ? 'Broken stairs' : 'Woodpile (planks)';
          if (!inYard && !ctx.player.carrying) pos = yard;
        } else {
          pos = at.papers.clone().setY(at.papers.y + 0.6);
          label = 'The Lenz flat (second floor)';
          if (p.y < FLOOR_H * 2 - 1) pos = new THREE.Vector3(NO12.wing.x0, 2.6, WING_STAIR.doorZ);
        }
        break;
      case 'office':
        pos = new THREE.Vector3(0, 2.8, FRONT);
        label = 'Ration-card office (school)';
        break;
      case 'shell':
        pos = new THREE.Vector3(UXB.x, 1.6, UXB.z);
        label = 'Children and the shell';
        if (this.f('event.kid_1') && this.f('event.kid_2') && this.f('event.kid_3') && !this.f('event.sapper_called')) {
          pos = this.npc.regulator?.root.position.clone().setY(2.2) ?? pos;
          label = 'Traffic regulator';
        }
        break;
      case 'chain':
        pos = new THREE.Vector3(RUBBLE_CHAIN.x - 1, 2.2, RUBBLE_CHAIN.z);
        label = 'Rubble chain';
        break;
      case 'anchor':
        pos = new THREE.Vector3(ANCHOR.x, 1.4, ANCHOR.z);
        label = 'Anchor point';
        break;
    }
    ctx.setMarker('objective', pos, label);
  }

  benchmarkRoutes(): Record<string, { pos: THREE.Vector3; look: THREE.Vector3 }[]> {
    const V = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
    const pts = [V(48, 1.7, 1), V(30, 1.7, 2), V(10, 1.7, -2), V(0, 1.7, -8), V(0, 1.7, -18), V(-4, 1.7, -28), V(-6, 1.0, -33), V(-20, 1.7, -2), V(-45, 1.7, -4)];
    return { street: pts.map((p, i) => ({ pos: p, look: (pts[i + 1] ?? V(-55, 1.7, -10)).clone() })) };
  }

  override dispose(): void {
    super.dispose();
  }
}

const SCHOOL_HALL_Z = FRONT + 5;
