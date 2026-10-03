import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import type { GameContext } from '../../core/GameContext';
import type { ChapterConfig, ChapterRuntime, LoadReporter } from '../types';
import { boxUV, planeUV, cylinderUV, GeoBatch, mat4, canvasTexture } from '../common/geo';
import type { NPC } from '../../npc/NPC';

export function createRuntime(ctx: GameContext, cfg: ChapterConfig): ChapterRuntime {
  return new HQRuntime(ctx, cfg);
}

/**
 * Temporal headquarters: an architectural hall (board-formed concrete, oak, brushed steel) with
 * the gate, destination console, artifact gallery and records terminal.
 */
class HQRuntime implements ChapterRuntime {
  readonly root = new THREE.Group();
  private ringGlow: THREE.MeshStandardMaterial | null = null;
  private quill: NPC | null = null;
  private envRT: THREE.WebGLRenderTarget | null = null;
  private screenTex: THREE.CanvasTexture | null = null;

  constructor(
    private readonly ctx: GameContext,
    private readonly cfg: ChapterConfig,
  ) {
    this.root.name = 'hq';
  }

  async build(report: LoadReporter): Promise<void> {
    const { ctx } = this;
    report(0.05, 'Headquarters: materials');
    const M = ctx.materials;
    const [floor, wall, steel, oak, fabric] = await Promise.all([
      M.get('hq-floor', 'concrete_polished', { roughnessScale: 0.9 }),
      M.get('hq-wall', 'concrete_board'),
      M.get('hq-steel', 'brushed_steel'),
      M.get('hq-oak', 'oak_veneer'),
      M.get('hq-fabric', 'acoustic_fabric'),
    ]);
    const tile = async (set: string): Promise<number> => (await ctx.assets.pbr(set)).tileMetres;
    const tFloor = await tile('concrete_polished');
    const tWall = await tile('concrete_board');
    const tSteel = await tile('brushed_steel');
    const tOak = await tile('oak_veneer');
    const tFab = await tile('acoustic_fabric');

    report(0.3, 'Headquarters: architecture');
    const W = 24;
    const D = 22;
    const H = 7.5;
    const z0 = -10;
    const z1 = 12;
    const world = ctx.world;
    const add = (g: THREE.BufferGeometry, m: THREE.Material, collide = true, cast = true): THREE.Mesh => {
      const mesh = new THREE.Mesh(g, m);
      mesh.castShadow = cast;
      mesh.receiveShadow = true;
      this.root.add(mesh);
      if (collide) world.addStaticMesh(mesh);
      return mesh;
    };

    // floor + ceiling
    const fl = planeUV(W, D, tFloor);
    fl.rotateX(-Math.PI / 2);
    fl.translate(0, 0, (z0 + z1) / 2);
    add(fl, floor, true, false);
    const ceilBatch = new GeoBatch();
    for (let x = -W / 2 + 1; x < W / 2; x += 2.0) {
      for (let z = z0 + 1; z < z1; z += 2.0) {
        if (Math.abs(x) < 2.2) continue; // skylight slot
        ceilBatch.add(boxUV(1.9, 0.08, 1.9, tFab), mat4(x, H - 0.25, z));
      }
    }
    add(ceilBatch.build(), fabric, false, false);
    const slab = boxUV(W, 0.3, D, tWall);
    slab.translate(0, H + 0.15, (z0 + z1) / 2);
    add(slab, wall, false, false);
    // skylight diffuser (emissive daylight panel)
    const sky = new THREE.Mesh(new THREE.PlaneGeometry(3.6, D - 2), new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0xdfe8f2, emissiveIntensity: 2.2, roughness: 1 }));
    sky.rotation.x = Math.PI / 2;
    sky.position.set(0, H - 0.05, (z0 + z1) / 2);
    this.root.add(sky);
    // steel beams across
    const beams = new GeoBatch();
    for (let z = z0 + 2; z < z1; z += 4) beams.add(boxUV(W, 0.35, 0.22, tSteel), mat4(0, H - 0.45, z));
    add(beams.build(), steel, false, true);

    // walls with oak wainscot and light coves
    const walls = new GeoBatch();
    const wains = new GeoBatch();
    const wallBox = (cx: number, cz: number, w: number, d: number): void => {
      walls.add(boxUV(w, H, d, tWall), mat4(cx, H / 2, cz));
      world.addStaticBox(new THREE.Vector3(cx, H / 2, cz), new THREE.Vector3(w, H, d));
    };
    wallBox(0, z0 - 0.2, W + 0.8, 0.4);
    wallBox(0, z1 + 0.2, W + 0.8, 0.4);
    wallBox(-W / 2 - 0.2, (z0 + z1) / 2, 0.4, D);
    wallBox(W / 2 + 0.2, (z0 + z1) / 2, 0.4, D);
    wains.add(boxUV(0.06, 2.4, D - 1, tOak), mat4(-W / 2 + 0.03, 1.2, (z0 + z1) / 2));
    wains.add(boxUV(0.06, 2.4, D - 1, tOak), mat4(W / 2 - 0.03, 1.2, (z0 + z1) / 2));
    wains.add(boxUV(W - 1, 2.4, 0.06, tOak), mat4(0, 1.2, z1 - 0.03));
    add(walls.build(), wall, false, true);
    add(wains.build(), oak, false, false);
    const coveMat = new THREE.MeshStandardMaterial({ color: 0x000000, emissive: 0xffd2a0, emissiveIntensity: 1.4 });
    const coves = new GeoBatch();
    coves.add(new THREE.BoxGeometry(0.04, 0.03, D - 1), mat4(-W / 2 + 0.07, 2.42, (z0 + z1) / 2));
    coves.add(new THREE.BoxGeometry(0.04, 0.03, D - 1), mat4(W / 2 - 0.07, 2.42, (z0 + z1) / 2));
    coves.add(new THREE.BoxGeometry(W - 1, 0.03, 0.04), mat4(0, 2.42, z1 - 0.07));
    add(coves.build(), coveMat, false, false);

    report(0.5, 'Headquarters: the gate');
    // gate platform + ring
    const plat = cylinderUV(3.2, 3.3, 0.22, 64, tSteel);
    plat.translate(0, 0.11, -6);
    add(plat, steel, true, false);
    const ring = new THREE.TorusGeometry(2.35, 0.17, 24, 96);
    const ringMesh = add(ring, steel, false, true);
    ringMesh.position.set(0, 2.75, -6);
    this.ringGlow = new THREE.MeshStandardMaterial({ color: 0x050607, emissive: 0x7fb6d8, emissiveIntensity: 0.6, roughness: 0.3, metalness: 0.2 });
    const inner = new THREE.Mesh(new THREE.TorusGeometry(2.17, 0.035, 12, 128), this.ringGlow);
    inner.position.copy(ringMesh.position);
    this.root.add(inner);
    const pylons = new GeoBatch();
    pylons.add(boxUV(0.3, 2.9, 0.5, tSteel), mat4(-2.55, 1.45, -6));
    pylons.add(boxUV(0.3, 2.9, 0.5, tSteel), mat4(2.55, 1.45, -6));
    add(pylons.build(), steel, true, true);

    // console
    const desk = new GeoBatch();
    desk.add(boxUV(2.6, 0.06, 0.9, tOak), mat4(0, 0.95, -1.6));
    desk.add(boxUV(2.4, 0.9, 0.08, tOak), mat4(0, 0.47, -1.25));
    add(desk.build(), oak, false, true);
    const deskLegs = new GeoBatch();
    deskLegs.add(boxUV(0.06, 0.92, 0.8, tSteel), mat4(-1.25, 0.46, -1.6));
    deskLegs.add(boxUV(0.06, 0.92, 0.8, tSteel), mat4(1.25, 0.46, -1.6));
    add(deskLegs.build(), steel, false, true);
    world.addStaticBox(new THREE.Vector3(0, 0.5, -1.6), new THREE.Vector3(2.6, 1, 0.9));
    this.screenTex = this.drawConsoleScreen();
    const screen = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.6), new THREE.MeshStandardMaterial({ map: this.screenTex, emissive: 0xffffff, emissiveMap: this.screenTex, emissiveIntensity: 0.9, roughness: 0.25 }));
    screen.position.set(0, 1.25, -1.85);
    screen.rotation.x = -0.35;
    this.root.add(screen);
    const bezel = add(boxUV(1.7, 0.7, 0.04, tSteel), steel, false, true);
    bezel.position.set(0, 1.245, -1.875);
    bezel.rotation.x = -0.35;

    report(0.65, 'Headquarters: gallery');
    // gallery vitrines along the left wall
    const owned = ctx.save.data.artifacts;
    const allArtifacts = ctx.chapters.flatMap((c) => c.artifacts.map((a) => ({ ...a, chapter: `${c.destination}, ${c.dateLabel}` })));
    const glass = new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.05, metalness: 0, transparent: true, opacity: 0.12, envMapIntensity: 1.5, depthWrite: false });
    const pedestals = new GeoBatch();
    for (let i = 0; i < 6; i++) {
      const z = -6 + i * 3;
      const x = -W / 2 + 1.4;
      pedestals.add(boxUV(0.9, 1.0, 0.9, tOak), mat4(x, 0.5, z));
      world.addStaticBox(new THREE.Vector3(x, 0.8, z), new THREE.Vector3(0.95, 1.6, 0.95));
      const case_ = new THREE.Mesh(new THREE.BoxGeometry(0.86, 0.6, 0.86), glass);
      case_.position.set(x, 1.31, z);
      case_.renderOrder = 2;
      this.root.add(case_);
      const art = allArtifacts[i];
      if (art && owned.includes(art.id)) {
        const obj = this.artifactModel(art.id);
        obj.position.set(x, 1.02, z);
        this.root.add(obj);
      }
      // vitrine downlight: an emissive strip in the case lid (no extra real-time light)
      const strip = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.015, 0.05), coveMat);
      strip.position.set(x, 1.6, z);
      this.root.add(strip);
    }
    add(pedestals.build(), oak, false, true);
    ctx.interactions.add({ id: 'hq_gallery', position: new THREE.Vector3(-W / 2 + 1.4, 1.3, 1.5), radius: 1.2, range: 3.5, prompt: 'View recovered artifacts', onInteract: () => {
      ctx.ui.artifacts(allArtifacts, ctx.save.data.artifacts, () => ctx.resume());
      ctx.pause(false);
    } });

    // records kiosk (right wall)
    const kiosk = new GeoBatch();
    kiosk.add(boxUV(0.7, 1.15, 0.5, tSteel), mat4(W / 2 - 1.2, 0.575, 1));
    add(kiosk.build(), steel, true, true);
    const ktex = canvasTexture(512, 320, (c) => {
      c.fillStyle = '#0b1218';
      c.fillRect(0, 0, 512, 320);
      c.fillStyle = '#8fc3d6';
      c.font = '600 30px system-ui, sans-serif';
      c.fillText('HISTORICAL RECORDS', 28, 60);
      c.fillStyle = '#c9d4da';
      c.font = '22px system-ui, sans-serif';
      ['Documented · Reconstruction · Fiction', `Records catalogued: ${ctx.save.data.records.length}`, 'Press E to browse'].forEach((t, i) => c.fillText(t, 28, 120 + i * 44));
    });
    this.ctx.tracker.track(ktex);
    const kscreen = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.39), new THREE.MeshStandardMaterial({ map: ktex, emissive: 0xffffff, emissiveMap: ktex, emissiveIntensity: 0.8 }));
    kscreen.position.set(W / 2 - 1.46, 1.3, 1);
    kscreen.rotation.y = -Math.PI / 2;
    kscreen.rotation.x = 0;
    this.root.add(kscreen);
    ctx.interactions.add({ id: 'hq_records', position: new THREE.Vector3(W / 2 - 1.4, 1.3, 1), radius: 0.5, range: 2.6, prompt: 'Browse historical records', onInteract: () => {
      ctx.pause(false);
      ctx.ui.records(ctx.chapters, ctx.save.data.records, () => ctx.resume());
    } });

    // benches
    const benches = new GeoBatch();
    for (const z of [5, 8]) {
      benches.add(boxUV(2.4, 0.08, 0.5, tOak), mat4(3.5, 0.45, z));
      benches.add(boxUV(2.4, 0.08, 0.5, tOak), mat4(-3.5, 0.45, z));
      world.addStaticBox(new THREE.Vector3(3.5, 0.24, z), new THREE.Vector3(2.4, 0.48, 0.5));
      world.addStaticBox(new THREE.Vector3(-3.5, 0.24, z), new THREE.Vector3(2.4, 0.48, 0.5));
    }
    add(benches.build(), oak, false, true);
    const benchLegs = new GeoBatch();
    for (const z of [5, 8]) for (const x of [-4.5, -2.5, 2.5, 4.5]) benchLegs.add(boxUV(0.06, 0.42, 0.42, tSteel), mat4(x, 0.21, z));
    add(benchLegs.build(), steel, false, true);

    // big timeline wall graphic behind the gate
    const tl = canvasTexture(2048, 512, (c) => this.drawTimeline(c));
    this.ctx.tracker.track(tl);
    const tlMesh = new THREE.Mesh(new THREE.PlaneGeometry(14, 3.5), new THREE.MeshStandardMaterial({ map: tl, roughness: 0.85 }));
    tlMesh.position.set(0, 4.6, z0 + 0.01);
    this.root.add(tlMesh);

    report(0.8, 'Headquarters: lighting');
    // lighting: room environment + daylight from the skylight + warm accents
    const pm = new THREE.PMREMGenerator(ctx.render.renderer);
    this.envRT = pm.fromScene(new RoomEnvironment(), 0.04);
    pm.dispose();
    await ctx.env.setup(
      {
        sky: { zenith: 0x9fb4c8, horizon: 0xd8dde2, ground: 0x6b665f, sunDirection: [0.25, 1, 0.15], sunColor: 0xf3f1ec, sunIntensity: 1.6, sunDisc: 0, cloudCover: 0, cloudColor: 0xffffff, cloudShadow: 0xffffff },
        fogColor: 0x1a1b1d,
        fogDensity: 0.0,
        hemiSky: 0xdfe6ee,
        hemiGround: 0x4a443c,
        hemiIntensity: 0.35,
        envIntensity: 0.55,
        rain: 0,
        wetness: 0,
        wind: [0, 0],
        indoor: true,
        background: 0x0d0e10,
      },
      ctx.render.renderer,
      null,
    );
    ctx.env.setEnvironmentMap(this.envRT.texture, 0.55);
    for (const [x, z] of [[-7, 1], [6, -3]] as const) {
      const p = new THREE.PointLight(0xffe0bd, 9, 14, 2);
      p.position.set(x, 5.5, z);
      this.root.add(p);
    }
    ctx.render.setGrade({ saturation: 1.0, contrast: 1.04, tint: 0xfff8f0, shadowTint: 0xf0f4ff, exposure: 1.0, vignette: 0.18, grain: 0.012 });

    // interactions
    ctx.interactions.add({ id: 'hq_console', position: new THREE.Vector3(0, 1.2, -1.7), radius: 0.9, range: 3, prompt: 'Open the destination selector', onInteract: () => ctx.openSelector() });
    ctx.interactions.add({ id: 'hq_gate', position: new THREE.Vector3(0, 2.6, -6), radius: 2.2, range: 6, prompt: 'Temporal gate — choose a destination at the console', enabled: () => true, onInteract: () => ctx.events.emit('notify', { text: 'The gate opens once a destination is chosen at the console.', kind: 'info' }) });
    ctx.setMarker('console', new THREE.Vector3(0, 1.6, -1.7), 'Console');

    report(0.9, 'Headquarters: staff');
    if (await ctx.characters.loadCharacter('archivist')) {
      this.quill = ctx.npcs.spawn({ id: 'quill', name: 'Dr. Mara Quill', character: 'archivist', position: new THREE.Vector3(1.9, 0, -0.6), yaw: Math.PI * 0.85, pose: 'idle' });
      this.quill.groundFn = () => 0;
    }
    ctx.interactions.add({
      id: 'quill',
      position: new THREE.Vector3(1.9, 1.6, -0.6),
      object: this.quill?.root,
      offsetY: 1.5,
      radius: 0.45,
      range: 3,
      prompt: 'Talk to Dr. Mara Quill',
      onInteract: () => ctx.startDialogue('quill_intro', this.quill ?? undefined),
    });
    ctx.world.buildStatic('hq');
    ctx.player.surfaceAt = () => ({ surface: 'hq', speed: 1 });
  }

  private drawConsoleScreen(): THREE.CanvasTexture {
    const chapters = this.ctx.chapters.filter((c) => c.id !== 'hq').sort((a, b) => a.year - b.year);
    const t = canvasTexture(1024, 384, (c) => {
      c.fillStyle = '#081016';
      c.fillRect(0, 0, 1024, 384);
      c.fillStyle = '#8fc3d6';
      c.font = '600 28px system-ui, sans-serif';
      c.fillText('TEMPORAL DESTINATIONS', 32, 50);
      c.font = '20px system-ui, sans-serif';
      chapters.forEach((ch, i) => {
        const y = 92 + i * 34;
        c.fillStyle = ch.status === 'playable' ? '#e8d6a8' : '#5d6b73';
        c.fillText(`${ch.year < 1000 ? 'AD ' + ch.year : ch.year}  ${ch.destination}`, 40, y);
        c.fillStyle = ch.status === 'playable' ? '#8cc48a' : '#5d6b73';
        c.fillText(ch.status === 'playable' ? 'AVAILABLE' : 'IN DEVELOPMENT', 760, y);
      });
    });
    this.ctx.tracker.track(t);
    return t;
  }

  private drawTimeline(c: CanvasRenderingContext2D): void {
    c.fillStyle = '#d9d4c7';
    c.fillRect(0, 0, 2048, 512);
    c.fillStyle = '#2b2a27';
    c.fillRect(100, 300, 1848, 4);
    c.font = '500 34px Georgia, serif';
    c.fillText('THE MERIDIAN ARCHIVE — WITNESS ASSIGNMENTS', 100, 110);
    const chapters = this.ctx.chapters.filter((x) => x.id !== 'hq').sort((a, b) => a.year - b.year);
    chapters.forEach((ch, i) => {
      const x = 140 + i * (1760 / Math.max(1, chapters.length - 1));
      c.fillStyle = ch.status === 'playable' ? '#7a5a1e' : '#6d6a63';
      c.beginPath();
      c.arc(x, 302, 12, 0, Math.PI * 2);
      c.fill();
      c.font = '600 30px Georgia, serif';
      c.fillText(ch.year < 1000 ? `AD ${ch.year}` : String(ch.year), x - 40, 260);
      c.font = '22px Georgia, serif';
      c.fillText(ch.destination, x - 60, 350);
    });
  }

  private artifactModel(id: string): THREE.Object3D {
    const g = new THREE.Group();
    const paper = new THREE.MeshStandardMaterial({ color: 0xd9cfb4, roughness: 0.85 });
    const leather = new THREE.MeshStandardMaterial({ color: 0x4a2f1f, roughness: 0.7 });
    if (id.includes('diary')) {
      const b = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.035, 0.22), leather);
      b.rotation.y = 0.3;
      g.add(b);
    } else if (id.includes('armband')) {
      const band = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.02, 8, 24), new THREE.MeshStandardMaterial({ color: 0xbfb8a4, roughness: 0.9 }));
      band.rotation.x = Math.PI / 2;
      band.position.y = 0.02;
      g.add(band);
    } else {
      const s = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.004, 0.13), paper);
      s.rotation.y = -0.2;
      g.add(s);
    }
    return g;
  }

  applyCheckpoint(): void {
    /* HQ has no checkpoints beyond the entrance */
  }

  update(_dt: number, time: number): void {
    if (this.ringGlow) this.ringGlow.emissiveIntensity = 0.55 + Math.sin(time * 1.3) * 0.12;
  }

  resolveSpawnHeight(): number {
    return 0.05;
  }

  scriptState(): Record<string, unknown> {
    return {};
  }

  benchmarkRoutes(): Record<string, { pos: THREE.Vector3; look: THREE.Vector3 }[]> {
    return {
      hq: [
        { pos: new THREE.Vector3(0, 1.65, 10), look: new THREE.Vector3(0, 2, -6) },
        { pos: new THREE.Vector3(-6, 1.65, 4), look: new THREE.Vector3(-11, 1.2, 0) },
        { pos: new THREE.Vector3(6, 1.65, -2), look: new THREE.Vector3(0, 2.7, -6) },
        { pos: new THREE.Vector3(0, 1.65, 9), look: new THREE.Vector3(0, 1.4, -2) },
      ],
    };
  }

  dispose(): void {
    this.envRT?.dispose();
    this.screenTex?.dispose();
    void this.cfg;
  }
}
