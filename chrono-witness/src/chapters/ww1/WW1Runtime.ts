import * as THREE from 'three';
import type { GameContext } from '../../core/GameContext';
import type { ChapterConfig, ChapterRuntime, LoadReporter } from '../types';
import { buildWorld, type WW1World } from './world';
import { NavGraph } from '../../npc/NavGraph';
import type { NPC } from '../../npc/NPC';
import { TRENCHES, DUGOUTS, ANCHOR, BARRAGE_TRIGGER, COLLAPSE, FARM, SUPPORT_Z, FRONT_Z, OLD_BOOT_BLOCK, CRATER_CROSSING, BOUNDS } from './layout';
import * as P from './props';
import { signMesh } from './dressing';
import { Puffs } from '../common/particles';
import { Rng } from '../../core/Random';

export function createRuntime(ctx: GameContext, cfg: ChapterConfig): ChapterRuntime {
  return new WW1Runtime(ctx, cfg);
}

type BarragePhase = 'none' | 'prompt' | 'exposed' | 'sheltered' | 'done';

interface Zone {
  id: string;
  test: (p: THREE.Vector3) => boolean;
  when?: () => boolean;
  inside: boolean;
}

interface Lamp {
  pos: THREE.Vector3;
  intensity: number;
  color: number;
  flicker: number;
}

/**
 * The Somme, October 1916. Builds the sector, populates it, and scripts the mission beats:
 * bombardment + collapse, the farm cellar rescue, the stretcher carry, echoes and ambience.
 */
class WW1Runtime implements ChapterRuntime {
  readonly root = new THREE.Group();
  private w!: WW1World;
  private nav = new NavGraph();
  private zones: Zone[] = [];
  private npc: Record<string, NPC | undefined> = {};
  private echoes: NPC[] = [];
  private puffs!: Puffs;
  private smoke!: Puffs;
  private rng = new Rng(1916);
  private lamps: Lamp[] = [];
  private lampLights: THREE.PointLight[] = [];
  private collapse = new THREE.Group();
  private beam!: THREE.Mesh;
  private beamT = -1;
  private crowbarProp!: THREE.Object3D;
  private diaryProp!: THREE.Object3D;
  private cable!: { broken: THREE.Mesh; fixed: THREE.Mesh };
  private stretcher!: THREE.Group;
  private carryActive = false;
  private carryWaitTimer = 0;
  private hazard: { t: number; total: number; pos: THREE.Vector3 } | null = null;
  private hazardPoints: THREE.Vector3[] = [];
  private barrage: BarragePhase = 'none';
  private barrageT = 0;
  private barrageTimer = 0;
  private nextShell = 0;
  private pendingShells: { t: number; pos: THREE.Vector3 }[] = [];
  private collapsed = false;
  private outsideShelterT = 0;
  private gunTimer = 4;
  private time = 0;
  private braziers: THREE.Vector3[] = [];
  private smokeTimer = 0;
  private boundaryMsgT = 0;
  private completed = false;
  private benchBarrageLoop = false;

  constructor(
    private readonly ctx: GameContext,
    private readonly cfg: ChapterConfig,
  ) {
    this.root.name = 'ww1';
  }

  // ======================================================================= build
  async build(report: LoadReporter): Promise<void> {
    const ctx = this.ctx;
    this.w = await buildWorld(ctx, this.root, (f, l) => report(f * 0.8, l));
    const { terrain, props: M } = this.w;

    report(0.82, 'Atmosphere');
    await ctx.env.setup(
      {
        sky: { zenith: 0x56606a, horizon: 0x9aa2a8, ground: 0x3a342d, sunDirection: [0.55, 0.42, -0.25], sunColor: 0xdcd6cc, sunIntensity: 0.75, sunDisc: 0, cloudCover: 0.93, cloudColor: 0xa2a7ab, cloudShadow: 0x585e64 },
        fogColor: 0x8d9398,
        fogDensity: 0.0062,
        hemiSky: 0xb7c0c7,
        hemiGround: 0x4a4037,
        hemiIntensity: 0.22,
        envIntensity: 0.95,
        rain: 0.85,
        wetness: 0.9,
        wind: [1.3, 0.5],
      },
      ctx.render.renderer,
      await ctx.assets.texture('textures/fx/cloud_noise.png'),
    );
    ctx.render.setGrade({ saturation: 0.84, contrast: 1.07, tint: 0xf4f1ea, shadowTint: 0xe8edf4, exposure: 1.08, vignette: 0.24, grain: 0.028 });
    ctx.audio.setLoop('rain', 'rain', 0.42);
    ctx.audio.setLoop('wind', 'wind', 0.2);

    const smokeTex = await ctx.assets.texture('textures/fx/smoke_puff.png', THREE.SRGBColorSpace);
    const dustTex = await ctx.assets.texture('textures/fx/dust_puff.png', THREE.SRGBColorSpace);
    this.puffs = ctx.tracker.track(new Puffs(220, dustTex));
    this.smoke = ctx.tracker.track(new Puffs(90, smokeTex));
    this.root.add(this.puffs.mesh, this.smoke.mesh);

    report(0.85, 'Props and signs');
    this.placeProps(M);
    this.placeSigns();
    this.buildCable();
    this.buildCollapse();
    for (const l of this.w.dressing.ladders) ctx.player.controller.ladders.push({ id: l.id, bottom: l.bottom, top: l.top, exit: l.exit, normal: l.normal });

    // interior lamp pool: fixed light count (no shader recompiles when lamps change)
    for (let i = 0; i < 3; i++) {
      const l = new THREE.PointLight(0xffb36b, 0, 6, 2);
      this.lampLights.push(l);
      this.root.add(l);
    }

    report(0.88, 'Navigation');
    this.buildNav();
    report(0.9, 'People');
    await this.spawnPeople();
    this.buildZones();
    this.buildInteractions();
    ctx.player.surfaceAt = (x, y, z) => terrain.surface(x, y, z);
    ctx.npcs.groundFn = (x, y, z) => ctx.world.groundHeight(x, y, z, 3);
    for (const n of ctx.npcs.npcs.values()) n.groundFn = ctx.npcs.groundFn;
    ctx.npcs.nav = this.nav;
    report(0.96, 'Building collision');
    ctx.world.buildStatic('ww1');
    report(1, 'Ready');
  }

  // ======================================================================= props
  private placeProps(M: P.PropMaterials): void {
    const ctx = this.ctx;
    const t = this.w.terrain;
    const tr = ctx.tracker;
    const put = (o: THREE.Object3D, x: number, z: number, rotY = 0, yOff = 0, onFloor = true): THREE.Object3D => {
      const y = onFloor ? (ctx.world.groundHeight(x, t.height(x, z) + 1.2, z, 3) ?? t.height(x, z)) : t.height(x, z);
      o.position.set(x, y + yOff, z);
      o.rotation.y = rotY;
      this.root.add(o);
      return o;
    };
    const dug = (id: string) => DUGOUTS.find((d) => d.id === id)!;
    const roomFloor = (id: string): number => t.base(dug(id).room[0], dug(id).room[1]) - dug(id).depth + 0.04;
    const inRoom = (id: string, o: THREE.Object3D, dx: number, dz: number, rotY = 0, y = 0): THREE.Object3D => {
      const d = dug(id);
      o.position.set(d.room[0] + dx, roomFloor(id) + y, d.room[1] + dz);
      o.rotation.y = rotY;
      this.root.add(o);
      return o;
    };
    const scan = (id: string, scanId: string, pos: THREE.Vector3, r = 0.4): void => {
      ctx.interactions.add({ id, position: pos, radius: r, range: 3.2, scanId, scanOnly: true, prompt: 'Scan', onInteract: () => undefined });
    };
    const lamp = (pos: THREE.Vector3, intensity = 2.2): void => {
      this.lamps.push({ pos, intensity, color: 0xffb36b, flicker: this.rng.range(0, 10) });
    };

    // ---- Company HQ dugout (Hollis): table, map, message pad, candle, bunk
    const hqT = inRoom('coy_hq', P.table(M), 0.6, 0.5, 0.1);
    const pad = P.messagePad(M);
    pad.position.set(hqT.position.x - 0.25, hqT.position.y + 0.76, hqT.position.z + 0.05);
    this.root.add(pad);
    scan('obj_message_pad', 'scan_message_form', pad.position.clone().setY(pad.position.y + 0.05), 0.25);
    const map = P.mapSheet(M, tr);
    map.position.set(hqT.position.x + 0.2, hqT.position.y + 0.765, hqT.position.z);
    this.root.add(map);
    const c1 = P.candle(M);
    c1.position.set(hqT.position.x + 0.45, hqT.position.y + 0.76, hqT.position.z - 0.2);
    this.root.add(c1);
    lamp(c1.position.clone().setY(c1.position.y + 0.3), 1.6);
    inRoom('coy_hq', P.bunk(M, tr), -1.2, 0.1, 0);
    // gas curtain at the HQ entrance
    const ent = dug('coy_hq').entrance;
    const curtain = P.gasCurtain(M, 1.0, 1.85);
    curtain.position.set(ent[0][0], t.height(ent[0][0], ent[0][1] + 0.9) + 0.92, ent[0][1] + 0.95);
    curtain.rotation.y = Math.PI;
    curtain.scale.x = 0.55; // drawn back to one side
    curtain.position.x -= 0.25;
    this.root.add(curtain);
    scan('obj_gas_curtain', 'scan_gas_curtain', curtain.position.clone(), 0.5);
    // helmet on a hook outside the HQ, rum jar inside
    const helmet = P.brodieHelmet(M);
    put(helmet, -2.9, SUPPORT_Z - 0.35, 0.4, 1.35, false);
    helmet.position.y = t.height(-2.9, SUPPORT_Z) + 1.4;
    helmet.rotation.x = 0.9;
    scan('obj_helmet', 'scan_brodie_helmet', helmet.position.clone(), 0.3);
    const jar = inRoom('coy_hq', P.rumJar(M, tr), -0.3, -0.9, 0.3);
    scan('obj_rum_jar', 'scan_rum_jar', jar.position.clone().setY(jar.position.y + 0.18), 0.25);

    // ---- Signals dugout (Kemp): table + D Mk III telephone
    const sigT = inRoom('signals', P.table(M), 0, 0.55, 0);
    const phone = P.fieldTelephone(M);
    phone.position.set(sigT.position.x - 0.1, sigT.position.y + 0.76, sigT.position.z);
    phone.rotation.y = -0.2;
    this.root.add(phone);
    scan('obj_telephone', 'scan_field_telephone', phone.position.clone().setY(phone.position.y + 0.1), 0.3);
    const lan = P.lantern(M);
    lan.position.set(sigT.position.x + 0.4, sigT.position.y + 0.76, sigT.position.z + 0.1);
    this.root.add(lan);
    lamp(lan.position.clone().setY(lan.position.y + 0.25), 2.0);
    const pad2 = P.messagePad(M);
    pad2.position.set(sigT.position.x + 0.1, sigT.position.y + 0.765, sigT.position.z - 0.15);
    this.root.add(pad2);

    // ---- RAP: trestles, stretcher, medical boxes, lantern
    for (const dz of [-0.6, 0.6]) {
      const tres = P.table(M);
      tres.scale.set(0.5, 0.75, 0.9);
      inRoom('rap', tres, -0.6, dz * 1.4, Math.PI / 2);
    }
    const rapStretcher = P.stretcher(M);
    inRoom('rap', rapStretcher, -0.6, 0, 0, 0.42);
    scan('obj_stretcher', 'scan_stretcher', rapStretcher.position.clone().setY(rapStretcher.position.y + 0.2), 0.6);
    this.root.userData.rapStretcherPos = rapStretcher.position.clone();
    rapStretcher.visible = false; // occupied by Whitlow after delivery; the scannable stretcher is at the farm
    for (let i = 0; i < 3; i++) inRoom('rap', P.crate(M, 0.5, 0.3, 0.35), 1.6, -1.1 + i * 0.4, 0.1 * i, 0.15);
    const rl = P.lantern(M);
    inRoom('rap', rl, 1.2, 0.9, 0, 0.6);
    lamp(rl.position.clone().setY(rl.position.y + 0.3), 2.8);
    const rapDoor = dug('rap').entrance[0];
    scan('obj_rap', 'scan_rap', new THREE.Vector3(rapDoor[0], t.height(rapDoor[0], rapDoor[1]) + 1.6, rapDoor[1] + 0.4), 0.5);

    // ---- Pall Mall shelter: lantern, sandbag bench
    const sl = P.lantern(M);
    inRoom('shelter', sl, 0.9, -0.8, 0, 0.0);
    sl.position.y += 1.55;
    lamp(sl.position.clone(), 1.8);
    this.root.userData.shelterLamp = sl;
    inRoom('shelter', P.crate(M), -0.9, 0.7, 0.3);

    // ---- Front-line company dugout (Ward)
    const fT = inRoom('front_hq', P.table(M), 0.5, 0.4, 0);
    const fc = P.candle(M);
    fc.position.set(fT.position.x, fT.position.y + 0.76, fT.position.z);
    this.root.add(fc);
    lamp(fc.position.clone().setY(fc.position.y + 0.3), 1.5);
    const fmap = P.mapSheet(M, tr);
    fmap.position.set(fT.position.x - 0.2, fT.position.y + 0.765, fT.position.z + 0.05);
    this.root.add(fmap);

    // ---- fire bays: periscope, Very pistol, gas bag, parapet scan point
    const bays = this.w.dressing.firestepSpots.filter((s) => s.p.z < FRONT_Z + 1 && s.p.z > FRONT_Z - 1.5 && s.p.y !== 0);
    const bayNear = (x: number): (typeof bays)[number] => bays.reduce((a, b) => (Math.abs(b.p.x - x) < Math.abs(a.p.x - x) ? b : a), bays[0]);
    if (bays.length) {
      const b1 = bayNear(-10);
      const peri = P.boxPeriscope(M);
      peri.position.set(b1.p.x + 1.2, b1.p.y + 0.02, b1.p.z - 0.12);
      peri.rotation.y = 0;
      this.root.add(peri);
      scan('obj_periscope', 'scan_periscope', peri.position.clone().setY(peri.position.y + 0.8), 0.35);
      const b2 = bayNear(-36);
      const vp = P.crate(M, 0.5, 0.3, 0.35);
      vp.position.set(b2.p.x - 1.5, b2.p.y + 0.17, b2.p.z);
      this.root.add(vp);
      const pistol = P.veryPistol(M);
      pistol.position.set(vp.position.x, vp.position.y + 0.16, vp.position.z);
      pistol.rotation.y = 0.8;
      this.root.add(pistol);
      scan('obj_very_pistol', 'scan_very_pistol', pistol.position.clone(), 0.25);
      const bag = P.gasBag(M);
      bag.position.set(b2.p.x + 1.8, b2.p.y + 0.02, b2.p.z - 0.05);
      bag.rotation.y = 0.3;
      this.root.add(bag);
      scan('obj_gas_helmet', 'scan_ph_helmet', bag.position.clone().setY(bag.position.y + 0.12), 0.25);
      const b3 = bayNear(-50);
      scan('obj_parapet', 'scan_sandbag_parapet', new THREE.Vector3(b3.p.x, t.base(b3.p.x, FRONT_Z - 1.4) + 0.3, FRONT_Z - 1.2), 0.9);
      // diary on the fire step (optional task)
      const b4 = bayNear(-44);
      const diary = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.022, 0.15), M.leather);
      diary.position.set(b4.p.x + 0.6, b4.p.y + 0.04, b4.p.z + 0.05);
      diary.rotation.y = 0.5;
      diary.castShadow = true;
      this.root.add(diary);
      this.diaryProp = diary;
      ctx.interactions.add({ id: 'diary', position: diary.position.clone().setY(diary.position.y + 0.05), radius: 0.25, range: 2.4, prompt: 'Pick up the pocket diary', enabled: () => !ctx.facts.get('item.diary') && !ctx.facts.get('dlg.whitlow.diary'), onInteract: () => {
        ctx.missions.runEffect({ giveItem: 'diary' });
        diary.visible = false;
        ctx.readDocument('Pocket diary', this.cfg.items.find((i) => i.id === 'diary')!.readable!);
      } });
      // brazier + sitting men in the support line, sentries on fire steps
      this.braziers.push(new THREE.Vector3(b1.p.x - 3, b1.p.y - 0.47, b1.p.z + 0.6));
    }
    // braziers in Fleet Street
    for (const x of [-34, 24]) {
      const hit = t.trenchAt(x, SUPPORT_Z, 3);
      const z = hit ? SUPPORT_Z : SUPPORT_Z;
      const br = P.brazier(M);
      put(br, x, z + 0.25, 0);
      this.braziers.push(br.position.clone().setY(br.position.y + 0.55));
      lamp(br.position.clone().setY(br.position.y + 0.7), 1.2);
    }
    // corrugated revetment scan point + screw picket bundle + spare duckboard in Fleet Street
    const rev = this.w.dressing.wallSpots.find((s) => s.trench === 'support' && Math.abs(s.p.x + 12) < 6) ?? this.w.dressing.wallSpots[0];
    scan('obj_revetment', 'scan_corrugated_revetment', rev.p.clone().setY(rev.p.y + 1.1), 0.7);
    for (let i = 0; i < 5; i++) {
      const pk = P.screwPicket(M, 1.3);
      pk.position.set(10.5 + i * 0.06, t.height(10.5, SUPPORT_Z + 0.4) + 0.7, SUPPORT_Z + 0.42);
      pk.rotation.z = 1.25 + i * 0.03;
      this.root.add(pk);
    }
    scan('obj_picket', 'scan_screw_picket', new THREE.Vector3(10.6, t.height(10.5, SUPPORT_Z) + 0.8, SUPPORT_Z + 0.4), 0.4);
    const db = new THREE.Mesh((this.root.children.find((c) => (c as THREE.InstancedMesh).isInstancedMesh && (c as THREE.InstancedMesh).count > 0 && (c as THREE.Mesh).geometry.attributes.position.count > 200 && (c as THREE.Mesh).geometry.attributes.position.count < 400) as THREE.Mesh | undefined)?.geometry ?? new THREE.BoxGeometry(0.5, 0.05, 1.5), this.w.mats.planks_solid);
    db.position.set(-14.5, t.height(-14.5, SUPPORT_Z) + 0.85, SUPPORT_Z - 0.55);
    db.rotation.set(-1.15, 0, 0);
    db.castShadow = true;
    this.root.add(db);
    scan('obj_duckboard', 'scan_duckboard', db.position.clone(), 0.6);
    // crates & tins along Fleet Street
    for (const [x, rot] of [[-27, 0.1], [-8.5, -0.2], [13.5, 0.3], [30, 0]] as const) {
      put(P.crate(M), x, SUPPORT_Z + 0.35, rot, 0.18);
      put(P.tins(M, 3), x + 0.5, SUPPORT_Z + 0.3, 0);
    }
    // Old Boot Alley barricade (closed: flooded) — knife rest of wire + sign
    const [bx, bz] = OLD_BOOT_BLOCK;
    const kr = new THREE.Group();
    for (const sx of [-0.55, 0.55]) {
      const x1 = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.3, 0.06), M.beam);
      x1.rotation.z = 0.5;
      x1.position.set(sx, 0.55, 0);
      const x2 = x1.clone();
      x2.rotation.z = -0.5;
      kr.add(x1, x2);
    }
    const bar = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.06, 0.06), M.beam);
    bar.position.y = 0.95;
    kr.add(bar);
    put(kr, bx, bz, 0.2);
    ctx.world.addStaticBox(new THREE.Vector3(bx, t.height(bx, bz) + 1.1, bz), new THREE.Vector3(2.2, 2.2, 0.4), 0.2);

    // ---- Farm: dropped stretcher (evidence), RE dump with crowbar, timber stacks
    const st = P.stretcher(M);
    put(st, -21.2, 69.5, 0.9, 0.02);
    st.rotation.z = 0.08;
    scan('obj_stretcher', 'scan_stretcher', st.position.clone().setY(st.position.y + 0.2), 0.7);
    ctx.interactions.add({ id: 'farm_stretcher', position: st.position.clone().setY(st.position.y + 0.3), radius: 0.6, range: 2.6, prompt: 'Examine the dropped stretcher', enabled: () => !ctx.facts.get('event.avery_found'), onInteract: () => {
      ctx.events.emit('subtitle', { speaker: 'You', text: 'A stretcher, dropped in a hurry. Fresh boot prints lead towards the farmhouse.', duration: 5 });
      ctx.facts.set('clue.stretcher');
    } });
    const [dx, dz] = FARM.dump;
    for (let i = 0; i < 6; i++) {
      const beamM = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.15, 2.6), M.beam);
      beamM.position.set(dx - 0.6 + (i % 3) * 0.18, t.height(dx, dz) + 0.08 + Math.floor(i / 3) * 0.15, dz + 1.2);
      beamM.castShadow = beamM.receiveShadow = true;
      this.root.add(beamM);
    }
    ctx.world.addStaticBox(new THREE.Vector3(dx - 0.4, t.height(dx, dz) + 0.2, dz + 1.2), new THREE.Vector3(0.7, 0.4, 2.6));
    put(P.crate(M), dx + 0.5, dz - 0.6, 0.2, 0.18);
    put(P.crate(M), dx + 0.6, dz - 0.6, -0.1, 0.54);
    const bar2 = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 1.5, 8), new THREE.MeshStandardMaterial({ color: 0x2b2b2a, metalness: 0.9, roughness: 0.5 }));
    bar2.position.set(dx + 0.95, t.height(dx, dz) + 0.72, dz - 0.15);
    bar2.rotation.z = 0.25;
    bar2.castShadow = true;
    this.root.add(bar2);
    this.crowbarProp = bar2;
    ctx.interactions.add({ id: 'crowbar', position: bar2.position.clone(), radius: 0.4, range: 2.6, prompt: 'Take the crowbar', enabled: () => !ctx.facts.hasItem('crowbar') && !ctx.facts.get('event.beam_moved'), onInteract: () => {
      ctx.missions.runEffect({ giveItem: 'crowbar' });
      bar2.visible = false;
    } });

    // fallen beam across the cellar steps
    this.beam = P.fallenBeam(M, 3.4);
    this.beam.position.copy(this.w.village.beamPos);
    this.beam.rotation.set(0.15, Math.PI / 2 + 0.12, 0.62);
    this.root.add(this.beam);
    const bp = this.w.village.beamPos;
    const beamGeo = new THREE.BoxGeometry(2.6, 2.4, 1.3);
    ctx.world.addDynamic('beam', beamGeo, new THREE.Matrix4().makeTranslation(bp.x + 0.3, bp.y - 0.2, bp.z));
    beamGeo.dispose();
  }

  private placeSigns(): void {
    const t = this.w.terrain;
    const mat = this.w.mats.beam;
    const signs: [string, string | null, number, number, number][] = [
      ['PALL MALL', '↑ CHEAPSIDE', -7.1, 5.3, Math.PI],
      ['FLEET ST', null, -12, 5.0, Math.PI],
      ['HAYMARKET', '↓ VILLAGE', 3.2, 5.2, Math.PI],
      ['R.A.P.', '→', 15, 5.0, Math.PI],
      ['TOTTENHAM SAP', '→ OLD BOOT ALLEY', -9.4, -29.5, -Math.PI / 2],
      ['OLD BOOT ALLEY', 'CLOSED — FLOODED', 31.6, 3.2, Math.PI],
      ['CHEAPSIDE', null, 23, -58.6, 0],
      ['MOULIN FARM', '←', -8, 47.8, 0],
    ];
    for (const [a, b, x, z, r] of signs) {
      const s = signMesh(a, b, mat, this.ctx.tracker);
      const y = this.ctx.world.colliders.length ? t.height(x, z) : t.height(x, z);
      s.position.set(x, y - 0.05, z);
      s.rotation.y = r;
      this.root.add(s);
    }
  }

  private buildCable(): void {
    const pts = this.w.dressing.cablePath;
    // sagging cable between hooks with a break between points 2 and 3 (near z ≈ −9)
    const makeTube = (from: number, to: number, gapStart: boolean, gapEnd: boolean): THREE.BufferGeometry => {
      const p: THREE.Vector3[] = [];
      for (let i = from; i < to; i++) {
        const a = pts[i];
        const b = pts[i + 1];
        for (let k = 0; k < 6; k++) {
          const s = k / 6;
          p.push(new THREE.Vector3().lerpVectors(a, b, s).add(new THREE.Vector3(0, -Math.sin(s * Math.PI) * 0.12, 0)));
        }
      }
      p.push(pts[to].clone());
      if (gapStart) p[0].add(new THREE.Vector3(0.05, -0.7, 0.3));
      if (gapEnd) p[p.length - 1].add(new THREE.Vector3(0.05, -0.8, -0.3));
      return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(p), p.length * 2, 0.006, 4, false);
    };
    const mat = new THREE.MeshStandardMaterial({ color: 0x1f1d1a, roughness: 0.6 });
    this.ctx.tracker.track(mat);
    const broken = new THREE.Group();
    const a = makeTube(0, 2, false, true);
    const b = makeTube(3, pts.length - 1, true, false);
    const brokenMesh = new THREE.Mesh(mergeTwo(a, b), mat);
    const fixedMesh = new THREE.Mesh(makeTube(0, pts.length - 1, false, false), mat);
    broken.add(brokenMesh);
    this.root.add(brokenMesh, fixedMesh);
    this.cable = { broken: brokenMesh, fixed: fixedMesh };
    fixedMesh.visible = false;
    const breakPos = new THREE.Vector3().lerpVectors(pts[2], pts[3], 0.5).add(new THREE.Vector3(0.1, -0.85, 0));
    const ctx = this.ctx;
    ctx.interactions.add({
      id: 'cable_break',
      position: breakPos,
      radius: 0.45,
      range: 2.6,
      scanId: undefined,
      prompt: () => (ctx.facts.hasItem('splice_kit') && ctx.facts.get('event.break_found') ? 'Splice the cut cable' : 'Examine the cut cable'),
      holdTime: 0,
      enabled: () => !ctx.facts.get('event.line_repaired'),
      onInteract: () => {
        if (!ctx.facts.get('event.break_found')) {
          ctx.facts.set('event.break_found');
          ctx.events.emit('subtitle', { speaker: 'You', text: ctx.facts.hasItem('splice_kit') ? 'Both cut ends. A shell splinter, by the look of it. Time to splice.' : 'The telephone cable has been cut through here.', duration: 4.5 });
          return;
        }
        if (!ctx.facts.hasItem('splice_kit')) {
          ctx.events.emit('notify', { text: 'You need a repair kit. Signaller Kemp in the signals dugout has one.', kind: 'info' });
          return;
        }
        this.spliceProgress();
      },
    });
  }

  private splicing = 0;
  private spliceProgress(): void {
    // a short timed task: hands grip, three twists
    const ctx = this.ctx;
    this.splicing = 2.4;
    ctx.hands.setPose('fp_grip_two');
    ctx.events.emit('subtitle', { speaker: 'You', text: 'Strip, twist, tape…', duration: 2.4 });
  }

  private buildCollapse(): void {
    const t = this.w.terrain;
    const [ax, az] = COLLAPSE.from;
    const [bx, bz] = COLLAPSE.to;
    const g = new THREE.Group();
    const rng = new Rng(55);
    const n = 9;
    for (let i = 0; i < n; i++) {
      const s = i / (n - 1);
      const x = ax + (bx - ax) * s + rng.range(-0.3, 0.3);
      const z = az + (bz - az) * s;
      const base = t.base(x, z);
      const floorY = t.height(x, z);
      const h = base - floorY + rng.range(-0.2, 0.35);
      const geo = new THREE.SphereGeometry(1, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2);
      const p = geo.attributes.position as THREE.BufferAttribute;
      for (let k = 0; k < p.count; k++) p.setXYZ(k, p.getX(k) * rng.range(1.2, 1.7), p.getY(k) * (h + 0.2) * rng.range(0.9, 1.1), p.getZ(k) * rng.range(1.1, 1.5));
      geo.computeVertexNormals();
      const m = new THREE.Mesh(geo, this.w.mats.spoil);
      m.position.set(x, floorY - 0.1, z);
      m.castShadow = m.receiveShadow = true;
      g.add(m);
    }
    // broken revetment boards and a splintered duckboard poking out
    for (let i = 0; i < 6; i++) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.025, rng.range(0.8, 1.6)), this.w.mats.planks_solid);
      b.position.set(ax + (bx - ax) * rng.next() + rng.range(-0.4, 0.4), t.height(ax, az) + rng.range(0.5, 1.6), az + (bz - az) * rng.next());
      b.rotation.set(rng.range(-1, 1), rng.range(0, 3), rng.range(-1, 1));
      b.castShadow = true;
      g.add(b);
    }
    g.visible = false;
    this.collapse = g;
    this.root.add(g);
    const len = Math.hypot(bx - ax, bz - az);
    const box = new THREE.BoxGeometry(3.4, 3.2, len + 0.6);
    const mid = new THREE.Vector3((ax + bx) / 2, t.base((ax + bx) / 2, (az + bz) / 2) - 1.0, (az + bz) / 2);
    this.ctx.world.addDynamic('collapse', box, new THREE.Matrix4().makeRotationY(Math.atan2(bx - ax, bz - az)).setPosition(mid), false);
    box.dispose();
  }

  // ======================================================================= navigation
  private buildNav(): void {
    const t = this.w.terrain;
    const nav = this.nav;
    const trenchNodes: { id: number; trench: string }[] = [];
    for (const tr of TRENCHES) {
      if (tr.id === 'old_boot_n' || tr.id === 'front_e') continue;
      let prev = -1;
      for (let i = 1; i < tr.points.length; i++) {
        const [ax, az] = tr.points[i - 1];
        const [bx, bz] = tr.points[i];
        const len = Math.hypot(bx - ax, bz - az);
        const steps = Math.max(1, Math.round(len / 1.6));
        for (let k = i === 1 ? 0 : 1; k <= steps; k++) {
          const s = k / steps;
          const x = ax + (bx - ax) * s;
          const z = az + (bz - az) * s;
          const id = nav.add(new THREE.Vector3(x, t.height(x, z) + 0.05, z), tr.id);
          trenchNodes.push({ id, trench: tr.id });
          if (prev >= 0) nav.link(prev, id);
          prev = id;
        }
      }
    }
    // junctions between trenches
    for (const a of trenchNodes)
      for (const b of trenchNodes) {
        if (a.trench === b.trench || a.id >= b.id) continue;
        if (nav.nodes[a.id].pos.distanceTo(nav.nodes[b.id].pos) < 1.9) nav.link(a.id, b.id);
      }
    // dugouts: entrance → room
    for (const d of DUGOUTS) {
      const [[ex0, ez0], [ex1, ez1]] = d.entrance;
      const door = nav.add(new THREE.Vector3(ex0, t.height(ex0, ez0) + 0.05, ez0), `door:${d.id}`);
      const inner = nav.add(new THREE.Vector3(ex1, t.height(ex1, ez1) + 0.05, ez1), `in:${d.id}`);
      const room = nav.add(new THREE.Vector3(d.room[0], t.height(d.room[0], d.room[1]) + 0.06, d.room[1]), `room:${d.id}`);
      nav.link(door, inner);
      nav.link(inner, room);
      const near = nav.nearest(new THREE.Vector3(ex0, 0, ez0).setY(t.height(ex0, ez0)), 3);
      if (near >= 0 && near !== door) nav.link(near, door);
    }
    // village path from the Haymarket ramp to the farm cellar steps
    const vp: [number, number][] = [[0, 43], [-1, 46.5], [-6, 49.6], [-14, 50.6], [-20.5, 54], [-22, 58.5], [-22, 62], [-21.5, 66], [-19.5, 71], [-17.2, 75.2], [-16.6, 77.4]];
    const vids = nav.addPath(vp.map(([x, z]) => new THREE.Vector3(x, t.height(x, z) + 0.05, z)), 'village');
    const hayEnd = nav.nearest(new THREE.Vector3(0, t.height(0, 42.5), 42.5), 3);
    if (hayEnd >= 0) nav.link(hayEnd, vids[0]);
  }

  // ======================================================================= people
  private async spawnPeople(): Promise<void> {
    const ctx = this.ctx;
    const lib = ctx.characters;
    const ids = ['soldier_a', 'soldier_b', 'soldier_c', 'officer', 'medic', 'wounded'];
    const ok: Record<string, boolean> = {};
    for (const id of ids) ok[id] = await lib.loadCharacter(id);
    const pick = (id: string): string | null => (ok[id] ? id : ok.soldier_a ? 'soldier_a' : null);
    const t = this.w.terrain;
    const floor = (x: number, z: number): THREE.Vector3 => new THREE.Vector3(x, ctx.world.colliders.length ? t.height(x, z) : t.height(x, z), z);
    const spawn = (id: string, name: string, ch: string, p: THREE.Vector3, yaw: number, pose = 'idle', extra: Partial<Parameters<typeof ctx.npcs.spawn>[0]> = {}): NPC | undefined => {
      const c = pick(ch);
      if (!c) return undefined;
      const n = ctx.npcs.spawn({ id, name, character: c, position: p, yaw, pose, ...extra });
      this.npc[id] = n;
      return n;
    };
    const dug = (id: string) => DUGOUTS.find((d) => d.id === id)!;
    const roomPos = (id: string, dx = 0, dz = 0): THREE.Vector3 => {
      const d = dug(id);
      return new THREE.Vector3(d.room[0] + dx, t.base(d.room[0], d.room[1]) - d.depth + 0.05, d.room[1] + dz);
    };
    // support line
    spawn('hollis', 'Sgt. Hollis', 'soldier_b', floor(-4.7, SUPPORT_Z + 0.35), Math.PI * 0.95, 'idle');
    spawn('kemp', 'Signaller Kemp', 'soldier_a', roomPos('signals', -0.1, 0.05), Math.PI, 'kneel_work');
    spawn('sentry1', 'Sentry', 'soldier_c', floor(-30, SUPPORT_Z - 0.75).add(new THREE.Vector3(0, 0.47, 0)), Math.PI, 'idle_alt', { attentive: false });
    spawn('sit1', 'Soldier', 'soldier_a', floor(-33.2, SUPPORT_Z + 0.55), Math.PI * 0.9, 'sit_ground', { attentive: false });
    spawn('sit2', 'Soldier', 'soldier_c', floor(-35.6, SUPPORT_Z + 0.5), Math.PI * 1.15, 'sit_ground', { attentive: true });
    spawn('sit3', 'Soldier', 'soldier_b', floor(23, SUPPORT_Z + 0.55), Math.PI * 1.05, 'sit_ground');
    const carrierA = spawn('carrier1', 'Ration party', 'soldier_b', floor(-44, SUPPORT_Z), Math.PI / 2, 'idle');
    const carrierB = spawn('carrier2', 'Ration party', 'soldier_c', floor(-46, SUPPORT_Z), Math.PI / 2, 'idle');
    // Pall Mall shelter
    spawn('ellis', 'Pte. Ellis', 'soldier_a', roomPos('shelter', 0.6, 0.5), -Math.PI / 2, 'sit_ground');
    // front line
    spawn('ward', 'Capt. Ward', 'officer', roomPos('front_hq', -0.6, -0.2), Math.PI, 'idle');
    spawn('sentry2', 'Sentry', 'soldier_b', floor(-15.5, FRONT_Z - 0.85).add(new THREE.Vector3(0, 0.47, 0)), Math.PI, 'idle_alt', { attentive: false });
    spawn('sentry3', 'Sentry', 'soldier_c', floor(-41.5, FRONT_Z - 0.85).add(new THREE.Vector3(0, 0.47, 0)), Math.PI, 'idle_alt', { attentive: false });
    spawn('front_sit', 'Soldier', 'soldier_a', floor(-28.5, FRONT_Z + 0.4), 0.1, 'sit_ground');
    spawn('front_sit2', 'Soldier', 'soldier_b', floor(12, FRONT_Z + 0.2), -0.3, 'sit_ground');
    // RAP
    spawn('laird', 'Capt. Laird', 'officer', roomPos('rap', 0.9, -0.6), -Math.PI / 2, 'idle', { hideMeshes: ['helmet'] });
    spawn('orderly', 'Orderly', 'medic', roomPos('rap', 1.4, 0.7), -Math.PI * 0.6, 'kneel_work');
    // farm (hidden until freed)
    const avery = spawn('avery', 'Pte. Avery', 'medic', floor(-16.4, 76.2), -Math.PI / 2, 'idle');
    const whitlow = spawn('whitlow', 'Pte. Whitlow', 'wounded', floor(-15.4, 74.8), 0, 'lie_supine', { attentive: true });
    if (avery) avery.root.userData.radius = 0.3;
    if (whitlow) whitlow.root.userData.noCollide = true;

    // ration party walks Fleet Street back and forth
    const patrol = (n: NPC | undefined, a: THREE.Vector3, b: THREE.Vector3): void => {
      if (!n) return;
      const go = (to: THREE.Vector3, back: THREE.Vector3): void => {
        n.walkTo(this.nav, to, () => window.setTimeout(() => go(back, to), 2500 + Math.random() * 3000));
      };
      go(b, a);
    };
    patrol(carrierA, floor(-44, SUPPORT_Z), floor(44, SUPPORT_Z));
    window.setTimeout(() => patrol(carrierB, floor(-46, SUPPORT_Z), floor(42, SUPPORT_Z)), 1600);

    // stretcher used for the carry (Whitlow lies on it)
    this.stretcher = P.stretcher(this.w.props);
    this.stretcher.visible = false;
    this.root.add(this.stretcher);

    // temporal echoes (only visible in observation mode)
    await this.buildEchoes(pick);
  }

  private async buildEchoes(pick: (id: string) => string | null): Promise<void> {
    const ctx = this.ctx;
    const t = this.w.terrain;
    const ghostMat = ctx.tracker.track(new THREE.MeshStandardMaterial({ color: 0x0a1218, emissive: 0x7fb6d8, emissiveIntensity: 0.65, transparent: true, opacity: 0.32, depthWrite: false, roughness: 1 }));
    const mk = (id: string, ch: string, path: [number, number][], clip: string, speed: number): void => {
      const c = pick(ch);
      if (!c) return;
      const n = ctx.npcs.spawn({ id, name: 'Echo', character: c, position: new THREE.Vector3(path[0][0], t.height(path[0][0], path[0][1]), path[0][1]), pose: 'idle', attentive: false, walkSpeed: speed });
      n.model?.traverse((o) => {
        if ((o as THREE.Mesh).isMesh) {
          (o as THREE.Mesh).material = ghostMat;
          o.castShadow = false;
        }
      });
      n.root.userData.noCollide = true;
      n.locomotionClip = clip;
      n.yieldToPlayer = false;
      n.setVisible(false);
      const pts = path.map(([x, z]) => new THREE.Vector3(x, t.height(x, z) + 0.05, z));
      const loop = (): void => {
        n.teleport(pts[0]);
        n.walkPath(pts.slice(1), () => window.setTimeout(loop, 1500));
      };
      loop();
      this.echoes.push(n);
    };
    // Avery supporting the limping Whitlow from the gate to the cellar steps during the barrage
    mk('echo_avery', 'medic', [[-22, 60.5], [-21.5, 66], [-19.5, 71], [-17.4, 75.6], [-17.0, 77.4]], 'walk', 0.85);
    mk('echo_whitlow', 'wounded', [[-22.6, 60.2], [-22.1, 65.8], [-20.1, 70.8], [-17.9, 75.4], [-17.4, 77.1]], 'limp_walk', 0.85);
    // Whitlow writing on the fire step the night before (points to the diary)
    const bay = this.diaryProp?.position;
    if (bay) {
      const c = pick('wounded');
      if (c) {
        const n = ctx.npcs.spawn({ id: 'echo_diary', name: 'Echo', character: c, position: new THREE.Vector3(bay.x - 0.3, bay.y - 0.02, bay.z + 0.35), yaw: Math.PI, pose: 'sit_ground', attentive: false });
        n.model?.traverse((o) => {
          if ((o as THREE.Mesh).isMesh) {
            (o as THREE.Mesh).material = ghostMat;
            o.castShadow = false;
          }
        });
        n.root.userData.noCollide = true;
        n.setVisible(false);
        this.echoes.push(n);
      }
    }
  }

  // ======================================================================= zones & interactions
  private stage(): string | null {
    return this.ctx.missions.state.get('runner')?.stage ?? null;
  }

  private buildZones(): void {
    const near = (x: number, z: number, r: number) => (p: THREE.Vector3) => (p.x - x) ** 2 + (p.z - z) ** 2 < r * r;
    const shelter = DUGOUTS.find((d) => d.id === 'shelter')!;
    const inBox = (d: (typeof DUGOUTS)[number]) => (p: THREE.Vector3) => Math.abs(p.x - d.room[0]) < d.size[0] / 2 + 0.1 && Math.abs(p.z - d.room[1]) < d.size[1] / 2 + 0.1;
    this.zones = [
      { id: 'pall_mall_mid', test: near(BARRAGE_TRIGGER[0], BARRAGE_TRIGGER[1], 2.2), when: () => this.stage() === 'carry', inside: false },
      { id: 'shelter', test: inBox(shelter), when: () => this.stage() === 'barrage', inside: false },
      { id: 'front_line', test: (p) => p.z < FRONT_Z + 4.2 && p.y < this.w.terrain.base(p.x, p.z) - 0.8, when: () => this.stage() === 'reroute', inside: false },
      { id: 'farm', test: (p) => p.x > -36 && p.x < -12 && p.z > 58 && p.z < 84, inside: false },
      { id: 'anchor', test: near(ANCHOR[0], ANCHOR[1], 2.2), when: () => this.stage() === 'return', inside: false },
    ];
  }

  private buildInteractions(): void {
    const ctx = this.ctx;
    const talk = (id: string, dialogue: string, prompt: string, enabled?: () => boolean): void => {
      const n = this.npc[id];
      const pos = n ? n.root.position.clone() : new THREE.Vector3();
      ctx.interactions.add({ id: `talk_${id}`, position: pos, object: n?.root, offsetY: 1.5, radius: 0.5, range: 2.8, prompt, enabled, onInteract: () => ctx.startDialogue(dialogue, n) });
    };
    // NPCs may be missing if character assets failed; interactions fall back to fixed positions
    const fallback = (id: string, p: THREE.Vector3): void => {
      if (!this.npc[id]) {
        const it = ctx.interactions.items.get(`talk_${id}`);
        if (it) {
          it.object = undefined;
          it.position.copy(p);
        }
      }
    };
    const t = this.w.terrain;
    talk('hollis', 'hollis', 'Talk to Sergeant Hollis');
    fallback('hollis', new THREE.Vector3(-4.7, t.height(-4.7, SUPPORT_Z) + 1.5, SUPPORT_Z + 0.35));
    talk('kemp', 'kemp', 'Talk to Signaller Kemp');
    talk('ellis', 'ellis', 'Talk to Private Ellis');
    talk('ward', 'ward', 'Talk to Captain Ward');
    talk('laird', 'laird', 'Talk to the medical officer', () => ctx.facts.get('event.whitlow_delivered'));
    talk('avery', 'avery', 'Talk to Private Avery', () => ctx.facts.get('event.beam_moved'));
    talk('whitlow', 'whitlow', 'Talk to Private Whitlow', () => ctx.facts.get('event.beam_moved') && !this.carryActive);
    for (const id of ['hollis', 'kemp', 'ellis', 'ward', 'laird', 'avery', 'whitlow']) {
      const n = this.npc[id];
      if (!n) {
        const d = { kemp: 'signals', ellis: 'shelter', ward: 'front_hq', laird: 'rap' }[id as 'kemp'];
        if (d) {
          const dd = DUGOUTS.find((x) => x.id === d)!;
          fallback(id, new THREE.Vector3(dd.room[0], t.base(dd.room[0], dd.room[1]) - dd.depth + 1.5, dd.room[1]));
        }
      }
    }
    // the gap by the fallen beam: call down, then lever
    const bp = this.w.village.beamPos;
    ctx.interactions.add({
      id: 'beam',
      position: new THREE.Vector3(FARM.cellarStairTop[0] - 0.5, bp.y + 0.6, FARM.cellarStairTop[1]),
      radius: 0.7,
      range: 3,
      prompt: () => (!ctx.facts.get('event.avery_found') ? 'Call down through the gap' : ctx.facts.hasItem('crowbar') ? 'Lever the beam with the crowbar' : 'The beam is too heavy to lift by hand'),
      holdTime: 0,
      enabled: () => !ctx.facts.get('event.beam_moved'),
      onInteract: () => {
        if (!ctx.facts.get('event.avery_found')) ctx.startDialogue('avery_gap');
        else if (ctx.facts.hasItem('crowbar')) this.startLever();
        else ctx.startDialogue('avery_gap');
      },
    });
    // stretcher handles (start carrying)
    ctx.interactions.add({
      id: 'stretcher_handles',
      position: new THREE.Vector3(),
      object: this.stretcher,
      offsetY: 0.4,
      radius: 0.7,
      range: 2.6,
      prompt: 'Take the rear handles',
      enabled: () => ctx.facts.get('carry.ready') && !this.carryActive && !ctx.facts.get('event.whitlow_delivered'),
      onInteract: () => this.startCarry(),
    });
  }

  private leverT = 0;
  private startLever(): void {
    const ctx = this.ctx;
    this.leverT = 2.8;
    ctx.player.movementLocked = true;
    ctx.hands.setPose('fp_grip_two');
    ctx.audio.creak(this.beam.position.x, this.beam.position.z, 'Timber groaning');
    ctx.events.emit('subtitle', { speaker: 'You', text: 'Get the bar under it… and heave.', duration: 2.5 });
  }

  // ======================================================================= checkpoints
  applyCheckpoint(id: string, script: Record<string, unknown>): void {
    const ctx = this.ctx;
    const f = (k: string): boolean => ctx.facts.get(k);
    void script;
    void id;
    this.stopHazards();
    // world state from facts
    this.setCollapse(f('event.barrage_done'));
    this.barrage = f('event.barrage_done') ? 'done' : 'none';
    this.beamT = -1;
    this.leverT = 0;
    this.splicing = 0;
    ctx.player.movementLocked = false;
    const moved = f('event.beam_moved');
    this.beam.visible = !moved;
    ctx.world.setEnabled('beam', !moved);
    if (!moved) {
      this.beam.position.copy(this.w.village.beamPos);
      this.beam.rotation.set(0.15, Math.PI / 2 + 0.12, 0.62);
    }
    this.crowbarProp.visible = !ctx.facts.hasItem('crowbar') && !moved;
    if (this.diaryProp) this.diaryProp.visible = !f('item.diary') && !f('dlg.whitlow.diary');
    this.cable.broken.visible = !f('event.line_repaired');
    this.cable.fixed.visible = f('event.line_repaired');
    ctx.hands.setPose('hidden');
    // Avery & Whitlow
    const avery = this.npc.avery;
    const whitlow = this.npc.whitlow;
    const t = this.w.terrain;
    this.carryActive = false;
    ctx.player.carrying = false;
    this.stretcher.visible = false;
    if (f('event.whitlow_delivered')) {
      const rp = this.root.userData.rapStretcherPos as THREE.Vector3;
      this.placeStretcher(rp.clone(), Math.PI / 2 + Math.PI / 2);
      avery?.setVisible(true);
      avery?.teleport(new THREE.Vector3(rp.x + 0.9, rp.y - 0.42, rp.z + 0.9), -Math.PI / 2);
      avery?.stop();
    } else if (moved) {
      avery?.setVisible(true);
      avery?.teleport(new THREE.Vector3(-17.8, t.height(-17.8, 74.6), 74.6), Math.PI * 0.8);
      avery?.setPose('idle');
      avery?.stop();
      this.placeStretcher(new THREE.Vector3(-15.6, t.height(-15.6, 74.4) + 0.02, 74.4), 0.25);
    } else {
      avery?.setVisible(false);
      whitlow?.setVisible(false);
    }
    // Ellis and the barrage
    const ellis = this.npc.ellis;
    if (ellis) ellis.setPose('sit_ground');
    ctx.setDanger(null);
    ctx.facts.set('barrage.active', false);
    ctx.facts.set('sequence.active', false);
    this.completed = false;
  }

  private placeStretcher(p: THREE.Vector3, yaw: number): void {
    this.stretcher.visible = true;
    this.stretcher.position.copy(p);
    this.stretcher.rotation.set(0, yaw, 0);
    const w = this.npc.whitlow;
    if (w) {
      w.setVisible(true);
      w.teleport(new THREE.Vector3(p.x, p.y + 0.17, p.z), yaw);
      w.setPose('lie_supine');
      w.groundFn = null;
    }
  }

  private setCollapse(on: boolean): void {
    this.collapsed = on;
    this.collapse.visible = on;
    this.ctx.world.setEnabled('collapse', on);
    const mid = new THREE.Vector3((COLLAPSE.from[0] + COLLAPSE.to[0]) / 2, 0, (COLLAPSE.from[1] + COLLAPSE.to[1]) / 2);
    for (const n of this.nav.nodes) if (Math.hypot(n.pos.x - mid.x, n.pos.z - mid.z) < 3.8) n.blocked = on;
  }

  scriptState(): Record<string, unknown> {
    return { barrage: this.barrage };
  }

  // ======================================================================= update
  update(dt: number, time: number): void {
    const ctx = this.ctx;
    this.time += dt;
    const p = ctx.player.position;
    // zones (events only for gated, newly entered zones)
    for (const z of this.zones) {
      const ins = (!z.when || z.when()) && z.test(p);
      if (ins && !z.inside) ctx.events.emit('enterZone', { id: z.id });
      z.inside = ins;
    }
    // indoor lighting factor (dugouts / cellar)
    const cam = ctx.camera.position;
    let indoor = 0;
    for (const d of this.w.dugouts) if (d.box.containsPoint(cam)) indoor = 1;
    const [cx, cz] = FARM.cellarRoom;
    if (Math.abs(cam.x - cx) < FARM.cellarSize[0] / 2 + 0.5 && Math.abs(cam.z - cz) < FARM.cellarSize[1] / 2 + 0.3 && cam.y < this.w.terrain.base(cx, cz) - 0.3) indoor = 1;
    ctx.env.setIndoor(indoor);

    this.updateMarkers();
    this.updateLamps(time);
    this.updateAmbience(dt);
    this.updateBarrage(dt);
    this.updateFarm(dt);
    this.updateCarry(dt);
    this.updateEchoes();
    this.puffs.update(dt, ctx.camera);
    this.smoke.update(dt, ctx.camera);

    // optional: splice timer
    if (this.splicing > 0) {
      this.splicing -= dt;
      if (this.splicing <= 0) {
        ctx.facts.set('event.line_repaired');
        this.cable.broken.visible = false;
        this.cable.fixed.visible = true;
        ctx.hands.setPose('hidden');
        ctx.audio.ui('confirm');
      }
    }
    // boundary feedback
    this.boundaryMsgT -= dt;
    if (this.boundaryMsgT <= 0 && (p.x < BOUNDS.minX + 1 || p.x > BOUNDS.maxX - 1 || p.z > BOUNDS.maxZ - 1 || p.z < BOUNDS.minZ + 0.8)) {
      ctx.events.emit('notify', { text: p.z < BOUNDS.minZ + 2 ? 'No man’s land. Going over the top is not part of this assignment.' : 'The temporal field ends here.', kind: 'warning' });
      this.boundaryMsgT = 6;
    }
    // completion
    if (!this.completed && ctx.facts.get('event.chapter_complete')) {
      this.completed = true;
      window.setTimeout(() => ctx.completeChapter(), 600);
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
    const t = this.w.terrain;
    const p = ctx.player.position;
    const at = (x: number, z: number, dy = 1.6): THREE.Vector3 => this.markerPos.set(x, t.height(x, z) + dy, z);
    const dugDoor = (dId: string): THREE.Vector3 => {
      const d = DUGOUTS.find((x) => x.id === dId)!;
      return at(d.entrance[0][0], d.entrance[0][1]);
    };
    let pos: THREE.Vector3 | null = null;
    let label = '';
    switch (id) {
      case 'hollis':
        pos = at(-4.7, SUPPORT_Z + 0.35, 2.0);
        label = 'Sgt. Hollis';
        break;
      case 'pall_mall':
        pos = at(-6.2, 3.0);
        label = 'Pall Mall';
        if (p.z < 2) pos = at(BARRAGE_TRIGGER[0], BARRAGE_TRIGGER[1]);
        break;
      case 'shelter':
        pos = dugDoor('shelter');
        label = 'Shelter';
        break;
      case 'reroute':
        if (p.x < 20 && p.z > -33) {
          pos = at(-9.6, -30.2);
          label = 'Tottenham Sap';
          if (p.x > -6) pos = at(27.5, -30.5);
        } else if (p.z > -37.5) {
          pos = at(CRATER_CROSSING.ladderBottom[0], CRATER_CROSSING.ladderBottom[1], 2.2);
          label = 'Ladder';
        } else {
          pos = at(24, FRONT_Z);
          label = 'Front line';
        }
        break;
      case 'ward':
        pos = dugDoor('front_hq');
        label = 'Capt. Ward';
        break;
      case 'farm':
        pos = at(FARM.gate[0], FARM.gate[1], 2.2);
        label = 'Moulin Farm';
        if (p.z > 58) pos = at(FARM.cellarStairTop[0], FARM.cellarStairTop[1], 1.2);
        break;
      case 'dump':
        pos = at(FARM.dump[0] + 0.9, FARM.dump[1] - 0.2, 1.2);
        label = 'Engineers’ store';
        break;
      case 'beam':
        pos = at(FARM.cellarStairTop[0] - 0.5, FARM.cellarStairTop[1], 0.8);
        label = 'Fallen beam';
        break;
      case 'rap':
        pos = dugDoor('rap');
        label = 'R.A.P.';
        break;
      case 'laird':
        pos = dugDoor('rap');
        label = 'Medical officer';
        break;
      case 'anchor':
        pos = at(ANCHOR[0], ANCHOR[1], 1.4);
        label = 'Anchor point';
        break;
    }
    ctx.setMarker('objective', pos, label);
  }

  private updateLamps(time: number): void {
    const cam = this.ctx.camera.position;
    // choose the nearest lamps for the fixed light pool
    const sorted = this.lamps.map((l) => ({ l, d: l.pos.distanceToSquared(cam) })).sort((a, b) => a.d - b.d);
    for (let i = 0; i < this.lampLights.length; i++) {
      const L = this.lampLights[i];
      const s = sorted[i];
      if (!s || s.d > 30 * 30) {
        L.intensity = 0;
        continue;
      }
      const fl = 0.85 + Math.sin(time * 13 + s.l.flicker) * 0.06 + Math.sin(time * 31 + s.l.flicker * 2) * 0.05 + (this.barrage === 'sheltered' ? Math.sin(time * 47) * 0.15 : 0);
      L.position.copy(s.l.pos);
      L.intensity = s.l.intensity * fl;
    }
  }

  private updateAmbience(dt: number): void {
    const ctx = this.ctx;
    // distant guns: flashes on the horizon, rumble arriving later
    this.gunTimer -= dt;
    if (this.gunTimer <= 0 && this.barrage !== 'exposed' && this.barrage !== 'sheltered') {
      this.gunTimer = this.rng.range(4, 14);
      const ang = this.rng.range(-1.1, 1.1);
      const dist = this.rng.range(1500, 6000);
      const dir = new THREE.Vector3(Math.sin(ang), 0.08, -Math.cos(ang));
      ctx.env.triggerFlash(dir, this.rng.range(0.15, 0.4), 0xffc69a, 5);
      const delay = dist / 343;
      window.setTimeout(() => ctx.audio.distantGun(dir.x * 1000, dir.z * 1000, dist), Math.min(9000, delay * 1000));
    }
    // brazier smoke
    this.smokeTimer -= dt;
    if (this.smokeTimer <= 0) {
      this.smokeTimer = 0.35;
      for (const b of this.braziers) {
        if (b.distanceToSquared(ctx.camera.position) > 60 * 60) continue;
        this.smoke.emit(b.clone().add(new THREE.Vector3((Math.random() - 0.5) * 0.15, 0.1, (Math.random() - 0.5) * 0.15)), new THREE.Vector3(0.25 + Math.random() * 0.1, 0.55, 0.08), 4.5, 0.25, 1.4, 0x8a8781, 0.32);
      }
    }
  }

  // ---------------------------------------------------------------- bombardment
  private updateBarrage(dt: number): void {
    const ctx = this.ctx;
    if (this.barrage === 'none' && this.stage() === 'barrage') {
      this.barrage = 'prompt';
      void ctx
        .confirmIntense('Bombardment', 'An artillery bombardment begins. It brings loud impacts, camera shake and flashes, and your accessibility settings for camera shake and flashing apply.\n\nYou can skip it. The mission continues as if you had sheltered.')
        .then((r) => (r === 'skip' ? this.skipSequence() : this.startBarrage()));
    }
    // scheduled impacts
    for (let i = this.pendingShells.length - 1; i >= 0; i--) {
      const s = this.pendingShells[i];
      s.t -= dt;
      if (s.t <= 0) {
        this.impact(s.pos);
        this.pendingShells.splice(i, 1);
      }
    }
    if (this.barrage !== 'exposed' && this.barrage !== 'sheltered') return;
    this.barrageT += dt;
    const p = ctx.player.position;
    if (this.barrage === 'exposed') {
      this.barrageTimer -= dt;
      ctx.setDanger('Bombardment — take cover in the shelter', this.barrageTimer);
      if (ctx.facts.get('zone.shelter')) {
        this.barrage = 'sheltered';
        this.barrageT = 0;
        ctx.setDanger('Shelling — stay in the shelter');
        this.npc.ellis?.setPose('crouch_cover');
        ctx.events.emit('subtitle', { speaker: 'Pte. Ellis', text: 'In you come! Back against the wall. That’s it.', duration: 4 });
      } else if (this.barrageTimer <= 0) {
        this.impact(p.clone().add(new THREE.Vector3(1.5, 0, -1)));
        this.stopHazards();
        ctx.missions.fail('runner', 'Caught in the open during the bombardment');
        ctx.downPlayer('You did not reach cover before the shells reached you.');
        return;
      }
    } else {
      // sheltered: keep the player inside until it ends
      const sh = this.w.dugouts.find((d) => d.def.id === 'shelter')!;
      if (!sh.box.containsPoint(ctx.camera.position)) {
        this.outsideShelterT += dt;
        if (this.outsideShelterT > 0.2 && this.outsideShelterT < 0.3) ctx.events.emit('notify', { text: 'Get back into the shelter until the shelling stops.', kind: 'warning' });
        if (this.outsideShelterT > 7 * ctx.settings.accessibility.hazardTimeMultiplier) {
          this.stopHazards();
          ctx.missions.fail('runner', 'Left the shelter during the bombardment');
          ctx.downPlayer('You left the shelter while shells were still falling.');
          return;
        }
      } else this.outsideShelterT = 0;
      // dust sifting down from the roof with each heavy impact
      if (Math.random() < dt * 3) this.puffs.emit(new THREE.Vector3(sh.floor.x + (Math.random() - 0.5) * 2.4, sh.ceilingY - 0.1, sh.floor.z + (Math.random() - 0.5) * 2), new THREE.Vector3(0, -0.3, 0), 2.5, 0.12, 0.4, 0xb5ab9a, 0.35);
      if (!this.collapsed && this.barrageT > 9) {
        const mid = new THREE.Vector3((COLLAPSE.from[0] + COLLAPSE.to[0]) / 2, 0, (COLLAPSE.from[1] + COLLAPSE.to[1]) / 2);
        mid.y = this.w.terrain.base(mid.x, mid.z);
        this.impact(mid, 1.6);
        this.setCollapse(true);
        ctx.player.addTrauma(0.55);
        ctx.events.emit('subtitle', { speaker: 'Pte. Ellis', text: 'That was Pall Mall. Fallen right in, I’d bet.', duration: 4 });
      }
      if (this.barrageT > 13 && this.barrageT - dt <= 13) ctx.events.emit('subtitle', { speaker: 'Pte. Ellis', text: 'Twenty-six… twenty-seven… further off now. Getting further off.', duration: 4.5 });
      if (this.barrageT > 24) return this.endBarrage();
    }
    // schedule shells
    this.nextShell -= dt;
    if (this.nextShell <= 0) {
      this.nextShell = this.barrage === 'exposed' ? this.rng.range(1.3, 2.2) : this.rng.range(1.6, 3.2) * (this.barrageT > 16 ? 1.8 : 1);
      // land along Pall Mall / around the shelter, never directly on the player during the exposed phase
      const ang = this.rng.range(0, Math.PI * 2);
      const dist = this.barrage === 'exposed' ? this.rng.range(14, 34) * Math.max(0.55, this.barrageTimer / 22) : this.rng.range(6, 22);
      const pos = new THREE.Vector3(p.x + Math.cos(ang) * dist, 0, p.z + Math.sin(ang) * dist);
      pos.y = this.w.terrain.height(pos.x, pos.z);
      ctx.audio.shellWhistle(pos.x, pos.z, 1.1);
      this.pendingShells.push({ t: 1.1, pos });
    }
  }

  private startBarrage(): void {
    const ctx = this.ctx;
    this.barrage = 'exposed';
    this.barrageT = 0;
    this.barrageTimer = 22 * ctx.settings.accessibility.hazardTimeMultiplier;
    this.nextShell = 0.6;
    this.outsideShelterT = 0;
    ctx.facts.set('barrage.active');
    ctx.facts.set('sequence.active');
    ctx.events.emit('subtitle', { speaker: 'Distant voice', text: 'Whizz-bangs! Get under cover!', duration: 3 });
  }

  private endBarrage(): void {
    const ctx = this.ctx;
    this.barrage = 'done';
    this.pendingShells.length = 0;
    ctx.setDanger(null);
    ctx.facts.set('barrage.active', false);
    ctx.facts.set('sequence.active', false);
    ctx.facts.set('event.barrage_done');
    this.npc.ellis?.setPose('sit_ground');
    ctx.events.emit('notify', { text: 'The shelling has stopped.', kind: 'info' });
    ctx.events.emit('subtitle', { speaker: 'Pte. Ellis', text: 'That’s it, I think. Talk to me before you go. Pall Mall won’t be passable now.', duration: 5 });
  }

  /** Skip the intense sequence: same end state as sheltering through it. */
  skipSequence(): void {
    const ctx = this.ctx;
    const sh = this.w.dugouts.find((d) => d.def.id === 'shelter')!;
    this.stopHazards();
    ctx.player.spawn(sh.floor.clone().add(new THREE.Vector3(-0.3, 0.1, 0)), Math.PI / 2);
    ctx.facts.set('zone.shelter');
    this.setCollapse(true);
    this.endBarrage();
    ctx.events.emit('notify', { text: 'Sequence skipped. The bombardment has passed and Pall Mall has collapsed further up.', kind: 'info' });
  }

  /** Test hook for the benchmark: run an endless barrage around the camera. */
  benchBarrage(): void {
    this.benchBarrageLoop = true;
    this.barrage = 'sheltered';
    this.barrageT = 0;
    this.nextShell = 0;
    this.ctx.facts.set('zone.shelter');
  }

  private impact(pos: THREE.Vector3, scale = 1): void {
    const ctx = this.ctx;
    const d = pos.distanceTo(ctx.player.position);
    ctx.audio.impact(pos.x, pos.z, d);
    this.puffs.burst(pos.clone().setY(pos.y + 0.4), Math.round(14 * scale), 3 * scale, 4 * scale, 2.6, 0.9 * scale, 0x6b5f50, 0.65);
    this.puffs.burst(pos.clone().setY(pos.y + 0.8), Math.round(6 * scale), 1.5, 7 * scale, 1.4, 0.4, 0x3d342b, 0.8);
    const dir = pos.clone().sub(ctx.player.position).setY(0.3).normalize();
    ctx.env.triggerFlash(dir, Math.max(0.1, 0.7 - d / 60) * scale, 0xffb070, 9);
    ctx.player.addTrauma(Math.max(0, 0.75 - d / 40) * scale);
    if (this.benchBarrageLoop) this.barrageT = Math.min(this.barrageT, 5);
  }

  private stopHazards(): void {
    this.pendingShells.length = 0;
    this.hazard = null;
    if (this.barrage === 'exposed' || this.barrage === 'sheltered' || this.barrage === 'prompt') this.barrage = this.ctx.facts.get('event.barrage_done') ? 'done' : 'none';
    this.ctx.setDanger(null);
    this.ctx.facts.set('barrage.active', false);
    this.ctx.facts.set('sequence.active', false);
  }

  // ---------------------------------------------------------------- farm, lever, carry
  private updateFarm(dt: number): void {
    const ctx = this.ctx;
    if (this.leverT > 0) {
      this.leverT -= dt;
      ctx.player.addTrauma(dt * 0.15);
      if (this.leverT <= 0) {
        ctx.player.movementLocked = false;
        ctx.hands.setPose('hidden');
        ctx.facts.set('event.beam_moved');
        this.beamT = 0;
        ctx.world.setEnabled('beam', false);
        ctx.audio.impact(this.beam.position.x, this.beam.position.z, 8);
        this.puffs.burst(this.beam.position.clone(), 18, 2, 1.2, 3, 0.7, 0x9a8e7c, 0.5);
        // Avery climbs out and the stretcher is brought up
        window.setTimeout(() => this.applyCheckpointPartialFreed(), 1200);
      }
    }
    if (this.beamT >= 0 && this.beamT < 1) {
      this.beamT += dt * 1.6;
      const k = Math.min(1, this.beamT);
      this.beam.rotation.z = 0.62 + k * 0.9;
      this.beam.position.y = this.w.village.beamPos.y + k * 0.25;
      this.beam.position.z = this.w.village.beamPos.z + k * 1.1;
      if (k >= 1) this.beam.visible = true;
    }
  }

  private applyCheckpointPartialFreed(): void {
    const avery = this.npc.avery;
    const t = this.w.terrain;
    if (avery) {
      avery.setVisible(true);
      avery.teleport(new THREE.Vector3(FARM.cellarStairBottom[0] + 0.6, t.height(FARM.cellarStairBottom[0] + 0.6, FARM.cellarStairTop[1]) + 0.2, FARM.cellarStairTop[1]), Math.PI / 2);
      avery.walkPath([new THREE.Vector3(-16.6, t.height(-16.6, 77.4), 77.4), new THREE.Vector3(-17.8, t.height(-17.8, 74.6), 74.6)], () => {
        avery.faceTowards(this.ctx.player.position);
        this.ctx.startDialogue('avery', avery);
      });
    } else this.ctx.startDialogue('avery');
    this.placeStretcher(new THREE.Vector3(-15.6, t.height(-15.6, 74.4) + 0.02, 74.4), 0.25);
    this.ctx.events.emit('subtitle', { speaker: 'Pte. Avery', text: 'It’s moving! Mind your feet. Coming up!', duration: 3 });
  }

  private startCarry(): void {
    const ctx = this.ctx;
    const avery = this.npc.avery;
    const rap = DUGOUTS.find((d) => d.id === 'rap')!;
    const t = this.w.terrain;
    const dest = new THREE.Vector3(rap.room[0] - 0.6, t.base(rap.room[0], rap.room[1]) - rap.depth + 0.05, rap.room[1] + 0.9);
    this.carryActive = true;
    ctx.player.carrying = true;
    (ctx as unknown as { handsHolding: boolean }).handsHolding = false;
    ctx.hands.setPose('fp_grip_two');
    // hazards: two shells on the way (village road, Haymarket ramp)
    this.hazardPoints = [new THREE.Vector3(-12, 0, 50.5), new THREE.Vector3(0.5, 0, 36)];
    if (avery) {
      avery.locomotionClip = 'carry_walk';
      avery.yieldToPlayer = false;
      avery.walkSpeed = 1.15;
      const ok = avery.walkTo(this.nav, dest, () => this.deliver());
      if (!ok) this.deliver();
    } else {
      // no NPC model available: the carry still requires the player to walk the route
      this.root.userData.carryDest = dest;
    }
    ctx.events.emit('subtitle', { speaker: 'Pte. Avery', text: 'On three. One, two, three, lift! Steady. Follow me.', duration: 4 });
  }

  private updateCarry(dt: number): void {
    if (!this.carryActive) return;
    const ctx = this.ctx;
    const avery = this.npc.avery;
    const p = ctx.player.position;
    if (!avery) {
      const dest = this.root.userData.carryDest as THREE.Vector3;
      this.placeStretcherBetween(p.clone().add(ctx.player.forward.clone().setY(0).normalize().multiplyScalar(2.6)), p);
      if (dest && p.distanceTo(dest) < 2) this.deliver();
      return;
    }
    // leash: Avery waits for the player; the player cannot wander away from the stretcher
    const fwd = new THREE.Vector3(Math.sin(avery.yaw), 0, Math.cos(avery.yaw));
    const rear = avery.root.position.clone().addScaledVector(fwd, -2.55);
    const dist = Math.hypot(p.x - rear.x, p.z - rear.z);
    if (this.hazard) avery.walkSpeed = 0;
    else avery.walkSpeed = dist > 1.0 ? 0 : 1.15;
    if (avery.walkSpeed === 0 && !this.hazard) {
      this.carryWaitTimer += dt;
      if (this.carryWaitTimer > 6) {
        this.carryWaitTimer = 0;
        ctx.events.emit('subtitle', { speaker: 'Pte. Avery', text: 'Stay with me. Keep hold of those handles.', duration: 3 });
      }
    } else this.carryWaitTimer = 0;
    if (dist > 1.4) {
      // pull the player back toward the handles (they are holding a loaded stretcher)
      const k = 1.4 / dist;
      p.x = rear.x + (p.x - rear.x) * k;
      p.z = rear.z + (p.z - rear.z) * k;
    }
    const front = avery.root.position.clone().addScaledVector(fwd, -0.35);
    const back = p.clone().addScaledVector(new THREE.Vector3(front.x - p.x, 0, front.z - p.z).normalize(), 0.45);
    this.placeStretcherBetween(front, back);
    // hazards
    if (!this.hazard) {
      for (let i = this.hazardPoints.length - 1; i >= 0; i--) {
        const hp = this.hazardPoints[i];
        if (Math.hypot(avery.root.position.x - hp.x, avery.root.position.z - hp.z) < 2.5) {
          this.hazardPoints.splice(i, 1);
          const total = 2.6 * ctx.settings.accessibility.hazardTimeMultiplier;
          const land = avery.root.position.clone().add(new THREE.Vector3(9, 0, -6));
          land.y = this.w.terrain.height(land.x, land.z);
          this.hazard = { t: total, total, pos: land };
          avery.play('crouch_cover', 0.25);
          ctx.audio.shellWhistle(land.x, land.z, total);
          ctx.events.emit('subtitle', { speaker: 'Pte. Avery', text: 'Down! Get down!', duration: 2.2 });
        }
      }
    } else {
      this.hazard.t -= dt;
      ctx.setDanger('Shell incoming — crouch (C)', this.hazard.t);
      if (this.hazard.t <= 0) {
        const h = this.hazard;
        this.hazard = null;
        ctx.setDanger(null);
        this.impact(h.pos);
        if (!ctx.player.controller.crouching) {
          ctx.missions.fail('runner', 'Did not take cover from a shell during the carry');
          this.carryActive = false;
          ctx.player.carrying = false;
          ctx.downPlayer('You stayed upright when the shell came over. Crouch when you are warned.');
          return;
        }
        ctx.events.emit('subtitle', { speaker: 'Pte. Avery', text: 'Missed us. Up, up, keep going.', duration: 3 });
        avery.play('carry_walk', 0.3);
      }
    }
  }

  private placeStretcherBetween(front: THREE.Vector3, back: THREE.Vector3): void {
    const mid = new THREE.Vector3().addVectors(front, back).multiplyScalar(0.5);
    const yaw = Math.atan2(front.x - back.x, front.z - back.z);
    this.stretcher.visible = true;
    this.stretcher.position.set(mid.x, Math.min(front.y, back.y) + 0.62, mid.z);
    this.stretcher.rotation.set(0, yaw, 0);
    const w = this.npc.whitlow;
    if (w) {
      w.root.position.set(mid.x, this.stretcher.position.y + 0.17, mid.z);
      w.root.rotation.y = yaw;
      w.yaw = yaw;
    }
  }

  private deliver(): void {
    const ctx = this.ctx;
    this.carryActive = false;
    ctx.player.carrying = false;
    ctx.hands.setPose('hidden');
    ctx.setDanger(null);
    const avery = this.npc.avery;
    if (avery) {
      avery.locomotionClip = 'walk';
      avery.walkSpeed = 1.35;
      avery.setPose('idle');
      avery.stop();
    }
    const rp = this.root.userData.rapStretcherPos as THREE.Vector3;
    this.placeStretcher(rp.clone(), Math.PI);
    ctx.facts.set('event.whitlow_delivered');
    ctx.events.emit('subtitle', { speaker: 'Capt. Laird, R.A.M.C.', text: 'Bring him in. Gently does it.', duration: 3 });
  }

  // ---------------------------------------------------------------- echoes
  private updateEchoes(): void {
    const ctx = this.ctx;
    const show = ctx.observing;
    for (const e of this.echoes) {
      e.setVisible(show);
      if (show && e.root.position.distanceTo(ctx.player.position) < 16 && e.id !== 'echo_diary') ctx.facts.set('event.echo_seen');
    }
  }

  benchmarkRoutes(): Record<string, { pos: THREE.Vector3; look: THREE.Vector3 }[]> {
    const t = this.w.terrain;
    const at = (x: number, z: number, dy = 1.62): THREE.Vector3 => new THREE.Vector3(x, t.height(x, z) + dy, z);
    return {
      explore: [at(-21, SUPPORT_Z), at(-10, SUPPORT_Z), at(-6, 0), at(-8, -12), at(-6, 0), at(2, 8), at(0, 20), at(0.5, 38), at(-6, 49.6), at(-20, 56), at(-22, 66), at(-18, 74)].map((p, i, arr) => ({ pos: p, look: (arr[i + 1] ?? at(-25, 80)).clone().setY(p.y - 0.1) })),
      crowd: [at(-48, SUPPORT_Z), at(-38, SUPPORT_Z), at(-30, SUPPORT_Z), at(-20, SUPPORT_Z), at(-10, SUPPORT_Z), at(0, SUPPORT_Z), at(14, SUPPORT_Z), at(24, SUPPORT_Z)].map((p, i, arr) => ({ pos: p, look: (arr[i + 1] ?? at(40, SUPPORT_Z)).clone() })),
      barrage: [at(-6.4, -26.3), at(-5.2, -26.3, 1.4), at(-4.0, -26.0, 1.5), at(-6.6, -26.2)].map((p) => ({ pos: p, look: at(-9.5, -24) })),
    };
  }

  dispose(): void {
    this.stopHazards();
    for (const e of this.echoes) e.dispose();
    this.ctx.player.controller.ladders = [];
  }
}

function mergeTwo(a: THREE.BufferGeometry, b: THREE.BufferGeometry): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry();
  const pa = a.attributes.position.array as Float32Array;
  const pb = b.attributes.position.array as Float32Array;
  const na = a.attributes.normal.array as Float32Array;
  const nb = b.attributes.normal.array as Float32Array;
  const pos = new Float32Array(pa.length + pb.length);
  pos.set(pa);
  pos.set(pb, pa.length);
  const nor = new Float32Array(na.length + nb.length);
  nor.set(na);
  nor.set(nb, na.length);
  const ia = a.index!.array;
  const ib = b.index!.array;
  const idx = new Uint32Array(ia.length + ib.length);
  idx.set(ia);
  const off = pa.length / 3;
  for (let i = 0; i < ib.length; i++) idx[ia.length + i] = ib[i] + off;
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  a.dispose();
  b.dispose();
  return g;
}
