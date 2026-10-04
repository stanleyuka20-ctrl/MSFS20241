import * as THREE from 'three';
import type { GameContext } from '../../core/GameContext';
import type { LoadReporter } from '../types';
import { Terrain, buildChunk, buildOuterRing } from './terrain';
import { buildDressing, sandbagGeometry, duckboardGeometry, type Dressing } from './dressing';
import { buildDugouts, type DugoutBuild } from './dugouts';
import { buildVillage, type VillageBuild } from './village';
import { terrainMaterial, standardFromSet, applyWetness, WeatherUniforms } from '../../render/Materials';
import { Rng } from '../../core/Random';
import { FRONT_Z, BOUNDS, NO_GROUND_ZONE, CRATER_CROSSING } from './layout';
import { makePropMaterials, type PropMaterials } from './props';

const SETS = [
  'mud_wet', 'earth_wall', 'chalk_spoil', 'grass_dead', 'wood_planks', 'wood_beam', 'sandbag', 'corrugated_iron', 'wicker_hurdle',
  'brick_french', 'plaster_damaged', 'roof_tiles', 'cobblestone_wet', 'stone_rubble', 'canvas_tent', 'rusty_steel', 'crate_wood',
] as const;

export interface WW1World {
  terrain: Terrain;
  dressing: Dressing;
  dugouts: DugoutBuild[];
  village: VillageBuild;
  mats: Record<string, THREE.MeshStandardMaterial>;
  props: PropMaterials;
  tiles: Record<string, number>;
  waterMat: THREE.MeshStandardMaterial;
  lods: CellLOD[];
}

/** A spatial cell with a detailed and a simplified instanced mesh, switched by camera distance. */
export interface CellLOD {
  center: THREE.Vector3;
  hi: THREE.InstancedMesh;
  lo: THREE.InstancedMesh | null;
}

/** Switch cell LODs (call a few times per second). */
export function updateCellLODs(lods: CellLOD[], cam: THREE.Vector3, hiDist: number): void {
  const h2 = hiDist * hiDist;
  for (const l of lods) {
    if (!l.lo) continue;
    const near = l.center.distanceToSquared(cam) < h2;
    l.hi.visible = near;
    l.lo.visible = !near;
  }
}

function duckboardLow(tile: number): THREE.BufferGeometry {
  const g = new THREE.BoxGeometry(0.5, 0.05, 1.5);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * 0.5) / tile, (uv.getY(i) * 1.5) / tile);
  return g;
}

const yieldFrame = (): Promise<void> => new Promise((r) => setTimeout(r, 0));

/** Builds all static content of the Somme sector into `root` and the collision world. */
export async function buildWorld(ctx: GameContext, root: THREE.Group, report: LoadReporter): Promise<WW1World> {
  const A = ctx.assets;
  const g = ctx.settings.graphics;
  report(0.0, 'Loading materials');
  const sets: Record<string, Awaited<ReturnType<typeof A.pbr>>> = {};
  let loaded = 0;
  await Promise.all(
    SETS.map(async (s) => {
      sets[s] = await A.pbr(s);
      report((++loaded / SETS.length) * 0.18, 'Loading materials');
    }),
  );
  const fx = {
    macro: await A.texture('textures/fx/cloud_noise.png', THREE.NoColorSpace),
    ripples: await A.texture('textures/fx/rain_ripples_normal.png', THREE.NoColorSpace, 'normal'),
    water: await A.texture('textures/fx/water_normal.png', THREE.NoColorSpace, 'normal'),
    grass: await A.texture('textures/fx/grass_blade_atlas.png', THREE.SRGBColorSpace),
  };
  WeatherUniforms.uRipples.value = fx.ripples;
  const tiles: Record<string, number> = {};
  for (const s of SETS) tiles[s] = sets[s].tileMetres;

  // ---------------------------------------------------------------- materials
  const tm = terrainMaterial({ mud: sets.mud_wet, earth: sets.earth_wall, grass: sets.grass_dead, chalk: sets.chalk_spoil }, fx.macro);
  const S = (set: string, o: Parameters<typeof standardFromSet>[1] = {}): THREE.MeshStandardMaterial => ctx.tracker.track(standardFromSet(sets[set], { vertexColors: true, ...o }));
  const mats: Record<string, THREE.MeshStandardMaterial> = {
    terrain: ctx.tracker.track(tm),
    planks: S('wood_planks', { porosity: 0.8, side: THREE.DoubleSide }),
    planks_solid: S('wood_planks', { porosity: 0.8 }),
    beam: S('wood_beam', { porosity: 0.7 }),
    corrugated: S('corrugated_iron', { porosity: 0.3, side: THREE.DoubleSide }),
    corrugated_solid: S('corrugated_iron', { porosity: 0.3 }),
    hurdle: S('wicker_hurdle', { porosity: 0.8, side: THREE.DoubleSide }),
    steel: S('rusty_steel', { porosity: 0.3 }),
    sandbag: S('sandbag', { porosity: 0.9, vertexColors: false }),
    spoil: S('chalk_spoil', { porosity: 0.8 }),
    brick: S('brick_french', { porosity: 0.7 }),
    plaster: S('plaster_damaged', { porosity: 0.7 }),
    rubble: S('stone_rubble', { porosity: 0.7 }),
    cobble: S('cobblestone_wet', { porosity: 0.95 }),
    charred: S('wood_beam', { color: 0x4a4038, porosity: 0.5 }),
    bark: S('wood_beam', { color: 0xb3a596, porosity: 0.6 }),
    tiles: S('roof_tiles', { porosity: 0.7, vertexColors: false }),
    canvas: S('canvas_tent', { porosity: 0.6, vertexColors: false }),
    crate: S('crate_wood', { porosity: 0.6, vertexColors: false }),
  };
  const props = makePropMaterials({ crate: mats.crate, beam: mats.beam, planks: mats.planks_solid, steel: mats.steel, canvas: mats.canvas, sandbag: mats.sandbag });
  for (const m of Object.values(props)) if (m instanceof THREE.Material) ctx.tracker.track(m);
  applyWetness(props.helmetPaint, 0.3);
  const waterMat = ctx.tracker.track(new THREE.MeshStandardMaterial({ name: 'water', color: 0x2e2a24, roughness: 0.06, metalness: 0.0, normalMap: fx.water, envMapIntensity: 1.2 }));
  waterMat.normalScale.setScalar(0.35);

  // ---------------------------------------------------------------- terrain
  report(0.2, 'Shaping terrain');
  const terrain = new Terrain();
  const chunkSize = 32;
  const inner = { minX: -96, maxX: 96, minZ: -176, maxZ: 112 };
  const chunks: { x0: number; z0: number; seg: number }[] = [];
  for (let z0 = inner.minZ; z0 < inner.maxZ; z0 += chunkSize)
    for (let x0 = inner.minX; x0 < inner.maxX; x0 += chunkSize) {
      const cx = x0 + chunkSize / 2;
      const cz = z0 + chunkSize / 2;
      const trench = terrain.nearTrench(cx, cz, chunkSize * 0.72 + 6.5);
      const playable = cx > BOUNDS.minX - 20 && cx < BOUNDS.maxX + 20 && cz > -100 && cz < BOUNDS.maxZ + 16;
      const seg = trench ? 96 : playable ? 32 : 16;
      chunks.push({ x0, z0, seg: cz > 40 && cz < 100 && cx > -50 && cx < 0 ? Math.max(seg, 64) : seg });
    }
  const terrainGroup = new THREE.Group();
  terrainGroup.name = 'terrain';
  root.add(terrainGroup);
  for (let i = 0; i < chunks.length; i++) {
    const c = chunks[i];
    const geo = buildChunk(terrain, { x0: c.x0, z0: c.z0, size: chunkSize, seg: c.seg });
    ctx.tracker.track(geo);
    const m = new THREE.Mesh(geo, tm);
    m.receiveShadow = true;
    m.castShadow = c.seg >= 64;
    m.matrixAutoUpdate = false;
    if (c.seg >= 64) {
      // detailed trench chunks get a coarser distant LOD (skirts hide the seams; haze hides the rest)
      const lo = new THREE.Mesh(ctx.tracker.track(buildChunk(terrain, { x0: c.x0, z0: c.z0, size: chunkSize, seg: Math.round(c.seg / 3) })), tm);
      lo.receiveShadow = true;
      lo.matrixAutoUpdate = false;
      const lod = new THREE.LOD();
      lod.position.set(c.x0 + chunkSize / 2, 0, c.z0 + chunkSize / 2);
      m.position.set(-(c.x0 + chunkSize / 2), 0, -(c.z0 + chunkSize / 2));
      lo.position.copy(m.position);
      m.updateMatrix();
      lo.updateMatrix();
      lod.addLevel(m, 0);
      lod.addLevel(lo, 72);
      terrainGroup.add(lod);
      lod.updateMatrixWorld(true);
    } else terrainGroup.add(m);
    if (c.seg >= 32) ctx.world.addStaticMesh(m);
    if (i % 2 === 0) {
      report(0.2 + (i / chunks.length) * 0.45, 'Shaping terrain');
      await yieldFrame();
    }
  }
  const ringA = buildOuterRing(terrain, inner, 420, 6);
  const ringB = buildOuterRing(terrain, { minX: -420, maxX: 420, minZ: -420, maxZ: 420 }, 1800, 40);
  for (const rg of [ringA, ringB]) {
    ctx.tracker.track(rg);
    const m = new THREE.Mesh(rg, tm);
    m.receiveShadow = true;
    m.matrixAutoUpdate = false;
    terrainGroup.add(m);
  }

  // ---------------------------------------------------------------- dressing
  report(0.67, 'Revetting trenches');
  await yieldFrame();
  const dressing = buildDressing(terrain, tiles, g.detailDensity);
  report(0.72, 'Building dugouts');
  await yieldFrame();
  const dugouts = buildDugouts(terrain, dressing.batches, tiles);
  report(0.75, 'Ruined village');
  await yieldFrame();
  const village = buildVillage(terrain, dressing.batches, tiles);

  // batches → meshes
  for (const [key, batch] of dressing.batches.entries()) {
    const matKey = key.split('|')[0];
    const mat = mats[matKey] ?? mats.beam;
    const geo = ctx.tracker.track(batch.build(true));
    const m = new THREE.Mesh(geo, mat);
    m.castShadow = matKey !== 'cobble';
    m.receiveShadow = true;
    m.matrixAutoUpdate = false;
    root.add(m);
    if (['beam', 'brick', 'plaster', 'rubble', 'spoil', 'corrugated_solid', 'planks_solid'].includes(matKey) && false) ctx.world.addStaticMesh(m);
  }
  report(0.8, 'Sandbags and duckboards');
  const lods: CellLOD[] = [];
  lods.push(...instanced(ctx, root, sandbagGeometry(tiles.sandbag), mats.sandbag, dressing.sandbags, 24, true, sandbagGeometry(tiles.sandbag, true)));
  lods.push(...instanced(ctx, root, duckboardGeometry(tiles.wood_planks), mats.planks_solid, dressing.duckboards, 32, true, duckboardLow(tiles.wood_planks)));
  // rubble mounds, bricks, roof tiles, stumps
  for (const geo of village.rubbleMounds) {
    ctx.tracker.track(geo);
    const m = new THREE.Mesh(geo, mats.rubble);
    m.castShadow = m.receiveShadow = true;
    root.add(m);
    ctx.world.addStaticMesh(m);
  }
  const brickGeo = new THREE.BoxGeometry(0.22, 0.065, 0.105);
  instanced(ctx, root, brickGeo, mats.brick, village.bricks, 48, false);
  const tileGeo = new THREE.BoxGeometry(0.26, 0.015, 0.4);
  instanced(ctx, root, tileGeo, mats.tiles, village.tiles, 48, false);
  if (village.stumps.length) {
    const sb = new (await import('../common/geo')).GeoBatch();
    for (const s of village.stumps) sb.add(s);
    const sg = ctx.tracker.track(sb.build());
    const m = new THREE.Mesh(sg, mats.bark);
    m.castShadow = true;
    m.receiveShadow = true;
    root.add(m);
  }
  // water: every pond and the flooded trench in one draw call
  {
    const wb = new (await import('../common/geo')).GeoBatch();
    for (const w of dressing.waters) wb.add(w);
    const wg = ctx.tracker.track(wb.build());
    const m = new THREE.Mesh(wg, waterMat);
    m.receiveShadow = true;
    root.add(m);
  }

  // ---------------------------------------------------------------- wire belts in no man's land
  report(0.84, 'Barbed wire');
  wireBelts(ctx, root, terrain, mats.steel);

  // ---------------------------------------------------------------- grass tufts
  report(0.87, 'Vegetation');
  // grass cards need the atlas; skip (rather than draw untextured cards) if it failed to load
  if (fx.grass.image && (fx.grass.image as { width: number }).width > 4) grass(ctx, root, terrain, fx.grass, g.detailDensity);

  // ---------------------------------------------------------------- collisions
  report(0.9, 'Collision');
  for (const c of [...dressing.colliders, ...village.colliders, ...dugouts.flatMap((d) => d.colliders)]) ctx.world.addStaticBox(c.c, c.s, c.r);
  boundaries(ctx, terrain);

  return { terrain, dressing, dugouts, village, mats, props, tiles, waterMat, lods };
}

/** Instanced meshes split into spatial cells so frustum culling still works; optional low-detail LOD. */
function instanced(ctx: GameContext, root: THREE.Group, geo: THREE.BufferGeometry, mat: THREE.Material, matrices: THREE.Matrix4[], cell: number, cast: boolean, lowGeo?: THREE.BufferGeometry): CellLOD[] {
  ctx.tracker.track(geo);
  if (lowGeo) ctx.tracker.track(lowGeo);
  const cells = new Map<string, THREE.Matrix4[]>();
  const p = new THREE.Vector3();
  for (const m of matrices) {
    p.setFromMatrixPosition(m);
    const k = `${Math.floor(p.x / cell)}|${Math.floor(p.z / cell)}`;
    let l = cells.get(k);
    if (!l) cells.set(k, (l = []));
    l.push(m);
  }
  const out: CellLOD[] = [];
  for (const list of cells.values()) {
    const mk = (g: THREE.BufferGeometry, shadow: boolean): THREE.InstancedMesh => {
      const im = new THREE.InstancedMesh(g, mat, list.length);
      list.forEach((m, i) => im.setMatrixAt(i, m));
      im.instanceMatrix.needsUpdate = true;
      im.computeBoundingSphere();
      im.castShadow = shadow;
      im.receiveShadow = true;
      root.add(im);
      return im;
    };
    const hi = mk(geo, cast);
    const lo = lowGeo ? mk(lowGeo, false) : null;
    if (lo) lo.visible = false;
    out.push({ center: hi.boundingSphere!.center.clone(), hi, lo });
  }
  return out;
}

/** Belts of screw pickets and barbed wire in front of the front line (out of bounds; visual). */
function wireBelts(ctx: GameContext, root: THREE.Group, t: Terrain, mat: THREE.Material): void {
  const rng = new Rng(66);
  const pickets: THREE.Matrix4[] = [];
  const wirePts: THREE.Vector3[][] = [];
  for (const [zBase, gap] of [[FRONT_Z - 7, 2.6], [FRONT_Z - 12, 3.0], [FRONT_Z - 18, 3.2]] as const) {
    const row: THREE.Vector3[] = [];
    for (let x = -78; x < 80; x += gap + rng.range(-0.4, 0.4)) {
      const z = zBase + rng.range(-0.8, 0.8);
      if (rng.chance(0.08)) continue; // gaps blown in the wire
      const y = t.height(x, z);
      const h = rng.range(1.0, 1.35);
      pickets.push(new THREE.Matrix4().compose(new THREE.Vector3(x, y + h / 2 - 0.1, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(rng.range(-0.15, 0.15), 0, rng.range(-0.15, 0.15))), new THREE.Vector3(1, h, 1)));
      row.push(new THREE.Vector3(x, y, z));
      (row[row.length - 1] as THREE.Vector3 & { h?: number }).h = h;
    }
    // strands at three heights + diagonals
    for (const frac of [0.25, 0.6, 0.95]) {
      for (let i = 1; i < row.length; i++) {
        const a = row[i - 1];
        const b = row[i];
        if (a.distanceTo(b) > 5) continue;
        const ha = (a as THREE.Vector3 & { h?: number }).h ?? 1.2;
        const hb = (b as THREE.Vector3 & { h?: number }).h ?? 1.2;
        const pts: THREE.Vector3[] = [];
        for (let k = 0; k <= 6; k++) {
          const s = k / 6;
          const sag = Math.sin(s * Math.PI) * (0.08 + rng.range(0, 0.1));
          pts.push(new THREE.Vector3(a.x + (b.x - a.x) * s, a.y + (b.y - a.y) * s + (ha + (hb - ha) * s) * frac - sag, a.z + (b.z - a.z) * s));
        }
        wirePts.push(pts);
      }
    }
    for (let i = 1; i < row.length; i++) {
      const a = row[i - 1];
      const b = row[i];
      if (a.distanceTo(b) > 5) continue;
      wirePts.push([new THREE.Vector3(a.x, a.y + 0.1, a.z), new THREE.Vector3((a.x + b.x) / 2, (a.y + b.y) / 2 + 0.7, (a.z + b.z) / 2 + 0.3), new THREE.Vector3(b.x, b.y + 1.2, b.z)]);
    }
  }
  const pg = new THREE.CylinderGeometry(0.012, 0.014, 1, 5);
  const im = new THREE.InstancedMesh(ctx.tracker.track(pg), mat, pickets.length);
  pickets.forEach((m, i) => im.setMatrixAt(i, m));
  im.computeBoundingSphere();
  im.castShadow = true;
  root.add(im);
  // wire tubes merged (with tiny barb knots as thicker segments)
  const parts: THREE.BufferGeometry[] = [];
  for (const pts of wirePts) parts.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), pts.length * 2, 0.0035, 3, false));
  const merged = mergeSimple(parts);
  const wm = new THREE.Mesh(ctx.tracker.track(merged), mat);
  wm.castShadow = false;
  root.add(wm);
}

function mergeSimple(parts: THREE.BufferGeometry[]): THREE.BufferGeometry {
  let vCount = 0;
  let iCount = 0;
  for (const p of parts) {
    vCount += p.attributes.position.count;
    iCount += p.index!.count;
  }
  const pos = new Float32Array(vCount * 3);
  const nor = new Float32Array(vCount * 3);
  const uv = new Float32Array(vCount * 2);
  const idx = new Uint32Array(iCount);
  let vo = 0;
  let io = 0;
  for (const p of parts) {
    pos.set(p.attributes.position.array as Float32Array, vo * 3);
    nor.set(p.attributes.normal.array as Float32Array, vo * 3);
    uv.set(p.attributes.uv.array as Float32Array, vo * 2);
    const src = p.index!.array;
    for (let i = 0; i < src.length; i++) idx[io + i] = src[i] + vo;
    vo += p.attributes.position.count;
    io += src.length;
    p.dispose();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(new THREE.BufferAttribute(idx, 1));
  g.computeBoundingSphere();
  return g;
}

/** Alpha-tested grass tuft cards with wind sway (vertex shader), density from settings. */
function grass(ctx: GameContext, root: THREE.Group, t: Terrain, atlas: THREE.Texture, density: number): void {
  const rng = new Rng(808);
  const count = Math.floor(16000 * density);
  const mats: THREE.Matrix4[] = [];
  const atlasIdx: number[] = [];
  const b4 = new THREE.Vector4();
  let tries = 0;
  while (mats.length < count && tries < count * 6) {
    tries++;
    const x = rng.range(-80, 80);
    const z = rng.range(-110, 104);
    const h = t.height(x, z);
    t.blend(x, z, h, b4);
    if (b4.y < 0.35 || rng.next() > b4.y) continue;
    if (Math.abs(h - t.base(x, z)) > 0.3) continue; // not in trenches / craters
    const s = rng.range(0.45, 0.95);
    mats.push(new THREE.Matrix4().compose(new THREE.Vector3(x, h - 0.03, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(0, rng.range(0, Math.PI), 0)), new THREE.Vector3(s * rng.range(0.8, 1.25), s, s)));
    atlasIdx.push(rng.int(0, 7));
  }
  // two crossed quads
  // card aspect matches the atlas cells (0.3 × 0.6 m); normals point up so cards light like the ground
  const q1 = new THREE.PlaneGeometry(0.5, 1);
  q1.translate(0, 0.5, 0);
  const q2 = q1.clone().rotateY(Math.PI / 2);
  const geo = mergeSimple([q1, q2]);
  const nrm = geo.attributes.normal as THREE.BufferAttribute;
  for (let i = 0; i < nrm.count; i++) nrm.setXYZ(i, 0, 1, 0);
  geo.setAttribute('aAtlas', new THREE.InstancedBufferAttribute(new Float32Array(atlasIdx), 1));
  const mat = new THREE.MeshStandardMaterial({ map: atlas, alphaTest: 0.45, side: THREE.DoubleSide, roughness: 0.9, metalness: 0 });
  mat.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = WeatherUniforms.uTime;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float aAtlas;\nuniform float uTime;\nvarying float vAtlas;\nvarying float vGrassH;')
      .replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
        vAtlas = aAtlas;
        vec4 ip = instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
        float sway = sin(uTime * 1.6 + ip.x * 0.37 + ip.z * 0.21) * 0.08 + sin(uTime * 3.1 + ip.x) * 0.03;
        transformed.x += sway * uv.y * uv.y;
        transformed.z += sway * 0.6 * uv.y * uv.y;
        vGrassH = uv.y;`,
      )
      .replace('#include <uv_vertex>', '#include <uv_vertex>');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vAtlas;\nvarying float vGrassH;')
      .replace(
        '#include <map_fragment>',
        `vec2 cellUv = vec2((mod(vAtlas, 4.0) + vMapUv.x) / 4.0, (floor(vAtlas / 4.0) + 1.0 - vMapUv.y) / 2.0);
        vec4 sampledDiffuseColor = texture2D(map, cellUv);
        diffuseColor *= sampledDiffuseColor;
        diffuseColor.rgb *= mix(0.55, 1.0, vGrassH); // darker near the base (ground contact)`,
      );
  };
  mat.customProgramCacheKey = () => 'grass-v2';
  ctx.tracker.track(mat);
  ctx.tracker.track(geo);
  // spatial cells
  const cells = new Map<string, number[]>();
  const p = new THREE.Vector3();
  mats.forEach((m, i) => {
    p.setFromMatrixPosition(m);
    const k = `${Math.floor(p.x / 24)}|${Math.floor(p.z / 24)}`;
    let l = cells.get(k);
    if (!l) cells.set(k, (l = []));
    l.push(i);
  });
  for (const ids of cells.values()) {
    const g2 = geo.clone();
    g2.setAttribute('aAtlas', new THREE.InstancedBufferAttribute(new Float32Array(ids.map((i) => atlasIdx[i])), 1));
    ctx.tracker.track(g2);
    const im = new THREE.InstancedMesh(g2, mat, ids.length);
    ids.forEach((id, k) => im.setMatrixAt(k, mats[id]));
    im.computeBoundingSphere();
    im.receiveShadow = true;
    root.add(im);
  }
}

/** Invisible walls: map bounds and the exposed ground between the lines. */
function boundaries(ctx: GameContext, t: Terrain): void {
  const H = 6;
  const wall = (x0: number, z0: number, x1: number, z1: number, yBase = -4): void => {
    const len = Math.hypot(x1 - x0, z1 - z0);
    const c = new THREE.Vector3((x0 + x1) / 2, yBase + H / 2, (z0 + z1) / 2);
    ctx.world.addStaticBox(c, new THREE.Vector3(len, H + 6, 0.3), -Math.atan2(z1 - z0, x1 - x0));
  };
  const b = BOUNDS;
  wall(b.minX, b.minZ, b.maxX, b.minZ);
  wall(b.minX, b.maxZ, b.maxX, b.maxZ);
  wall(b.minX, b.minZ, b.minX, b.maxZ);
  wall(b.maxX, b.minZ, b.maxX, b.maxZ);
  // keep the player off the open ground between the lines: a "lid" a little above ground level over that band,
  // except a corridor around the crater crossing
  const cc = CRATER_CROSSING;
  const minCX = Math.min(cc.bridgeFrom[0], cc.bridgeTo[0]) - 1.2;
  const maxCX = Math.max(cc.bridgeFrom[0], cc.bridgeTo[0]) + 1.6;
  const minCZ = cc.bridgeTo[1] - 1.4;
  const maxCZ = cc.bridgeFrom[1] + 1.4;
  const zone = NO_GROUND_ZONE;
  const step = 8;
  for (let x = b.minX; x < b.maxX; x += step) {
    for (let z = zone.minZ; z < zone.maxZ; z += step) {
      const cx = x + step / 2;
      const cz = z + step / 2;
      if (cx + step / 2 > minCX && cx - step / 2 < maxCX && cz + step / 2 > minCZ && cz - step / 2 < maxCZ) {
        // around the crossing: walls instead of a lid
        continue;
      }
      const y = Math.max(t.base(cx, cz), t.base(x, z), t.base(x + step, z + step)) + 1.0;
      ctx.world.addStaticBox(new THREE.Vector3(cx, y + 0.5, cz), new THREE.Vector3(step, 0.2, step));
    }
  }
  // retaining wall inside the big crater (below ground level): the crater is crossed on the bridge,
  // not waded — its flooded bottom is deep, sucking mud
  for (const c of t.craters) {
    if (c.r < 6) continue;
    const base = t.base(c.x, c.z);
    const cyl = new THREE.CylinderGeometry(c.r * 0.86, c.r * 0.86, 5, 32, 1, true);
    cyl.translate(c.x, base - 0.35 - 2.5, c.z);
    ctx.world.addStaticMesh(cyl);
    cyl.dispose();
  }
  // walls around the crater corridor at ground level
  const gy = t.base(cc.bridgeFrom[0], cc.bridgeFrom[1]);
  wall(minCX, minCZ, minCX, maxCZ, gy);
  wall(maxCX, minCZ, maxCX, maxCZ, gy);
}
