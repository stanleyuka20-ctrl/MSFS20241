import * as THREE from 'three';
import { Noise2D, Rng } from '../../core/Random';
import { BUILDINGS, FARM, VILLAGE_ROAD_Z, type BuildingDef } from './layout';
import type { Terrain } from './terrain';
import type { CellBatches } from './dressing';

export interface VillageBuild {
  colliders: { c: THREE.Vector3; s: THREE.Vector3; r: number }[];
  rubbleMounds: THREE.BufferGeometry[];
  bricks: THREE.Matrix4[];
  tiles: THREE.Matrix4[];
  stumps: THREE.BufferGeometry[];
  /** Farmhouse cellar stair top (for the fallen beam). */
  beamPos: THREE.Vector3;
  cellarFloorY: number;
}

const COURSE = 0.075;

/**
 * Ruined Picardy village: brick and lime-plastered buildings shelled roofless, with openings that
 * have real depth, jagged brick-course tops, collapsed corners, rubble, fallen tiles and charred
 * rafters; a cobbled road; shattered tree stumps.
 */
export function buildVillage(t: Terrain, batches: CellBatches, tiles: Record<string, number>): VillageBuild {
  const rng = new Rng(79);
  const noise = new Noise2D(31);
  const out: VillageBuild = { colliders: [], rubbleMounds: [], bricks: [], tiles: [], stumps: [], beamPos: new THREE.Vector3(), cellarFloorY: 0 };
  for (const b of BUILDINGS) building(t, b, batches, tiles, out, rng, noise);

  // farmhouse ground floor over the cellar (rubble-strewn boards/brick) with the stair opening
  const fh = BUILDINGS.find((b) => b.id === 'farmhouse')!;
  const gy = t.base(fh.x, fh.z) + 0.02;
  const [cx, cz] = FARM.cellarRoom;
  const [csx, csz] = FARM.cellarSize;
  const [s0x, s0z] = FARM.cellarStairTop;
  const [s1x] = FARM.cellarStairBottom;
  const slabT = 0.24;
  const slabTile = tiles.stone_rubble ?? 2;
  // slab covering the cellar except the stairwell strip (z = s0z ± 0.62, x from s1x to s0x)
  const minX = cx - csx / 2 - 0.3;
  const maxX = Math.max(cx + csx / 2 + 0.3, s0x + 0.4);
  const minZ = cz - csz / 2 - 0.3;
  const maxZ = cz + csz / 2 + 0.3;
  const holeMinZ = s0z - 0.84;
  const holeMaxZ = s0z + 0.84;
  const holeMinX = s1x - 0.3;
  const holeMaxX = s0x + 0.3;
  const slabs: [number, number, number, number][] = [
    [minX, maxX, minZ, holeMinZ],
    [minX, maxX, holeMaxZ, maxZ],
    [minX, holeMinX, holeMinZ, holeMaxZ],
    [holeMaxX, maxX, holeMinZ, holeMaxZ],
  ];
  for (const [a, b2, c, d] of slabs) {
    if (b2 - a < 0.05 || d - c < 0.05) continue;
    const g = boxT(b2 - a, slabT, d - c, slabTile);
    const p = new THREE.Vector3((a + b2) / 2, gy - slabT / 2, (c + d) / 2);
    batches.get('rubble', p.x, p.z).add(g, new THREE.Matrix4().makeTranslation(p.x, p.y, p.z));
    out.colliders.push({ c: p, s: new THREE.Vector3(b2 - a, slabT, d - c), r: 0 });
  }
  // brick vault inside the cellar
  const cellarFloor = t.base(cx, cz) - FARM.cellarDepth;
  out.cellarFloorY = cellarFloor;
  const vault = new THREE.CylinderGeometry(csz / 2, csz / 2, csx, 20, 1, true, -Math.PI / 2, Math.PI);
  vault.rotateZ(Math.PI / 2);
  const vuv = vault.attributes.uv as THREE.BufferAttribute;
  const bt = tiles.brick_french ?? 1;
  for (let i = 0; i < vuv.count; i++) vuv.setXY(i, (vuv.getX(i) * Math.PI * csz) / 2 / bt, (vuv.getY(i) * csx) / bt);
  // flip normals inward
  const idx = vault.index!.array as Uint16Array;
  for (let i = 0; i < idx.length; i += 3) {
    const tmp = idx[i + 1];
    idx[i + 1] = idx[i + 2];
    idx[i + 2] = tmp;
  }
  vault.computeVertexNormals();
  const springY = cellarFloor + 1.35;
  batches.get('brick', cx, cz).add(vault, new THREE.Matrix4().makeTranslation(cx, springY, cz));
  // cellar walls below the springing line
  for (const sgn of [-1, 1]) {
    const g = boxT(csx, 1.4, 0.25, bt);
    batches.get('brick', cx, cz).add(g, new THREE.Matrix4().makeTranslation(cx, cellarFloor + 0.7, cz + sgn * (csz / 2 + 0.05)));
  }
  const endW = boxT(0.25, 2.6, csz, bt);
  batches.get('brick', cx, cz).add(endW, new THREE.Matrix4().makeTranslation(cx - csx / 2 - 0.05, cellarFloor + 1.3, cz));
  // stairs (brick steps following the carve)
  const steps = 8;
  for (let i = 0; i < steps; i++) {
    const k0 = i / steps;
    const x = s0x - (s0x - s1x) * (k0 + 0.5 / steps);
    const y = t.base(s0x, s0z) - (i + 1) * (FARM.cellarDepth / steps);
    const g = boxT((s0x - s1x) / steps + 0.02, 0.18, 1.55, bt);
    batches.get('brick', x, s0z).add(g, new THREE.Matrix4().makeTranslation(x, y + 0.09 - 0.18 + FARM.cellarDepth / steps, s0z));
  }
  // stairwell side walls
  for (const sgn of [-1, 1]) {
    const len = s0x - s1x + 0.6;
    const g = boxT(len, FARM.cellarDepth + 0.3, 0.2, bt);
    batches.get('brick', (s0x + s1x) / 2, s0z).add(g, new THREE.Matrix4().makeTranslation((s0x + s1x) / 2, t.base(s0x, s0z) - FARM.cellarDepth / 2 + 0.1, s0z + sgn * 0.86));
    out.colliders.push({ c: new THREE.Vector3((s0x + s1x) / 2, t.base(s0x, s0z) - FARM.cellarDepth / 2 + 0.1, s0z + sgn * 0.86), s: new THREE.Vector3(len, FARM.cellarDepth + 0.3, 0.2), r: 0 });
  }
  out.beamPos.set((s0x + s1x) / 2 + 0.4, t.base(s0x, s0z) - 0.7, s0z);

  // cobbled road strip
  road(t, batches, tiles);

  // shattered tree stumps (no foliage: woods here were shelled bare)
  for (let i = 0; i < 46; i++) {
    const x = rng.range(-85, 85);
    const z = rng.chance(0.6) ? rng.range(12, 100) : rng.range(-58, -2);
    if (t.nearTrench(x, z, 4)) continue;
    if (BUILDINGS.some((b) => Math.abs(x - b.x) < b.w / 2 + 3 && Math.abs(z - b.z) < b.d / 2 + 3)) continue;
    if (Math.abs(z - VILLAGE_ROAD_Z) < 4) continue;
    out.stumps.push(stump(t, x, z, rng));
  }
  // distant broken woods on the horizon (enemy side and flanks)
  for (let i = 0; i < 160; i++) {
    const a = rng.range(0, Math.PI * 2);
    const r = rng.range(170, 420);
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r - 40;
    out.stumps.push(stump(t, x, z, rng, rng.range(5, 12)));
  }
  return out;
}

function building(t: Terrain, b: BuildingDef, batches: CellBatches, tiles: Record<string, number>, out: VillageBuild, rng: Rng, noise: Noise2D): void {
  const mat = b.material === 'brick' ? 'brick' : 'plaster';
  const tile = b.material === 'brick' ? (tiles.brick_french ?? 1) : (tiles.plaster_damaged ?? 2);
  const gy = t.base(b.x, b.z);
  const thick = 0.45;
  const cos = Math.cos(b.rot);
  const sin = Math.sin(b.rot);
  const toWorld = (lx: number, lz: number): [number, number] => [b.x + lx * cos + lz * sin, b.z - lx * sin + lz * cos];
  // walls: [start local x/z, end local x/z, isGableEnd, hasDoor]
  const hw = b.w / 2;
  const hd = b.d / 2;
  const walls: { a: [number, number]; c: [number, number]; gable: boolean; door: boolean }[] = [
    { a: [-hw, -hd], c: [hw, -hd], gable: false, door: true },
    { a: [hw, hd], c: [-hw, hd], gable: false, door: b.id === 'church' },
    { a: [-hw, hd], c: [-hw, -hd], gable: true, door: false },
    { a: [hw, -hd], c: [hw, hd], gable: true, door: b.id === 'barn' },
  ];
  // one collapsed corner per building (damage)
  const collapseWall = rng.int(0, 3);
  const collapseAt = rng.range(0.15, 0.85);
  walls.forEach((w, wi) => {
    const lx0 = w.a[0];
    const lz0 = w.a[1];
    const lx1 = w.c[0];
    const lz1 = w.c[1];
    const len = Math.hypot(lx1 - lx0, lz1 - lz0);
    const dx = (lx1 - lx0) / len;
    const dz = (lz1 - lz0) / len;
    const colW = 0.5;
    const cols = Math.ceil(len / colW);
    // openings along the wall
    const openings: { s0: number; s1: number; y0: number; y1: number; door?: boolean }[] = [];
    if (w.door) openings.push({ s0: len / 2 - 0.6, s1: len / 2 + 0.6, y0: 0, y1: b.id === 'barn' ? 3.2 : 2.15, door: true });
    // farmhouse: external cellar doorway where the stairs pass under the east wall
    if (b.id === 'farmhouse' && wi === 3) {
      const sc = FARM.cellarStairTop[1] - (b.z - hd);
      openings.push({ s0: sc - 0.95, s1: sc + 0.95, y0: 0, y1: 1.75, door: true });
    }
    if (!w.gable || len > 7) {
      for (let s = 1.4; s < len - 1.2; s += 2.6) {
        if (openings.some((o) => s + 0.6 > o.s0 - 0.4 && s - 0.6 < o.s1 + 0.4)) continue;
        openings.push({ s0: s - 0.5, s1: s + 0.5, y0: 0.95, y1: 2.25 });
        if (b.height > 5) openings.push({ s0: s - 0.45, s1: s + 0.45, y0: 3.35, y1: 4.45 });
      }
    }
    for (let ci = 0; ci < cols; ci++) {
      const s0 = ci * colW;
      const s1 = Math.min(len, s0 + colW);
      const sMid = (s0 + s1) / 2;
      // ruined top height for this column
      const u = sMid / len;
      let top = b.height;
      if (w.gable) top += Math.max(0, 1 - Math.abs(u - 0.5) * 2) * (b.d * 0.45);
      const n = noise.fbm(sMid * 0.35 + wi * 10 + b.x, b.z * 0.1, 3);
      top *= 1 - b.damage * (0.35 + 0.45 * (n * 0.5 + 0.5));
      if (wi === collapseWall) top *= Math.min(1, 0.25 + Math.abs(u - collapseAt) * 2.2);
      top = Math.max(0.35, Math.round(top / COURSE) * COURSE);
      // solid vertical intervals (skip openings)
      const cuts = openings.filter((o) => sMid > o.s0 && sMid < o.s1).map((o) => [o.y0, o.y1] as [number, number]);
      let y = 0;
      const solids: [number, number][] = [];
      for (const [c0, c1] of cuts.sort((a, b2) => a[0] - b2[0])) {
        if (c0 > y) solids.push([y, Math.min(c0, top)]);
        y = Math.max(y, c1);
      }
      if (y < top) solids.push([y, top]);
      for (const [y0, y1] of solids) {
        if (y1 - y0 < 0.02) continue;
        const g = boxT(s1 - s0 + 0.002, y1 - y0, thick, tile, s0, y0);
        const [wx, wz] = toWorld(lx0 + dx * sMid, lz0 + dz * sMid);
        const rot = Math.atan2(-dz, dx) + b.rot; // local wall direction → world yaw
        const m = new THREE.Matrix4().makeRotationY(rot).setPosition(wx, gy + (y0 + y1) / 2 - 0.05, wz);
        batches.get(mat, wx, wz).add(g, m);
      }
      // colliders: one box per column for the full height
      if (top > 0.4) {
        const [wx, wz] = toWorld(lx0 + dx * sMid, lz0 + dz * sMid);
        const solidLow = cuts.some((c) => c[0] < 0.2) ? null : top;
        if (solidLow !== null) out.colliders.push({ c: new THREE.Vector3(wx, gy + top / 2, wz), s: new THREE.Vector3(s1 - s0, top, thick), r: Math.atan2(-dz, dx) + b.rot });
        else {
          const above = cuts.find((c) => c[0] < 0.2)![1];
          if (top > above) out.colliders.push({ c: new THREE.Vector3(wx, gy + (above + top) / 2, wz), s: new THREE.Vector3(s1 - s0, top - above, thick), r: Math.atan2(-dz, dx) + b.rot });
        }
      }
    }
    // lintels and sills
    for (const o of openings) {
      if (o.y1 > b.height * (1 - b.damage * 0.4)) continue;
      const sMid = (o.s0 + o.s1) / 2;
      const [wx, wz] = toWorld(lx0 + dx * sMid, lz0 + dz * sMid);
      const rot = Math.atan2(-dz, dx) + b.rot;
      const lin = boxT(o.s1 - o.s0 + 0.3, 0.16, thick + 0.02, tiles.wood_beam ?? 1);
      batches.get('beam', wx, wz).add(lin, new THREE.Matrix4().makeRotationY(rot).setPosition(wx, gy + o.y1 + 0.08, wz));
      if (!o.door) {
        const sill = boxT(o.s1 - o.s0 + 0.1, 0.06, thick + 0.06, tiles.stone_rubble ?? 2);
        batches.get('rubble', wx, wz).add(sill, new THREE.Matrix4().makeRotationY(rot).setPosition(wx, gy + o.y0 - 0.03, wz));
      }
    }
  });

  // rubble mounds inside and along walls
  const mounds = 3 + Math.floor(b.damage * 5);
  for (let i = 0; i < mounds; i++) {
    const lx = rng.range(-hw * 0.9, hw * 0.9);
    const lz = rng.range(-hd * 0.9, hd * 0.9);
    if (b.id === 'barn' && lx > -hw * 0.2) continue; // keep the store and the barn door clear
    if (b.id === 'farmhouse') {
      const [wx0, wz0] = toWorld(lx, lz);
      if (Math.abs(wz0 - FARM.cellarStairTop[1]) < 1.3 && wx0 > FARM.cellarStairBottom[0] - 1 && wx0 < FARM.cellarStairTop[0] + 1.2) continue;
    }
    const [wx, wz] = toWorld(lx, lz);
    const r = rng.range(0.9, 2.2);
    out.rubbleMounds.push(mound(wx, gy - 0.05, wz, r, rng.range(0.35, 0.9), rng));
    for (let k = 0; k < 14; k++) {
      const a = rng.range(0, Math.PI * 2);
      const rr = rng.range(r * 0.6, r * 1.4);
      out.bricks.push(new THREE.Matrix4().compose(new THREE.Vector3(wx + Math.cos(a) * rr, gy + 0.03, wz + Math.sin(a) * rr), new THREE.Quaternion().setFromEuler(new THREE.Euler(rng.range(-0.5, 0.5), rng.range(0, 6.28), rng.range(-0.5, 0.5))), new THREE.Vector3(1, 1, 1)));
    }
    for (let k = 0; k < 8; k++) {
      const a = rng.range(0, Math.PI * 2);
      const rr = rng.range(0, r * 1.2);
      out.tiles.push(new THREE.Matrix4().compose(new THREE.Vector3(wx + Math.cos(a) * rr, gy + 0.02 + rng.range(0, 0.25), wz + Math.sin(a) * rr), new THREE.Quaternion().setFromEuler(new THREE.Euler(rng.range(-0.7, 0.7), rng.range(0, 6.28), rng.range(-0.7, 0.7))), new THREE.Vector3(1, 1, 1)));
    }
  }
  // a few charred rafters still spanning / fallen
  const rafters = b.damage < 0.8 ? 3 : 1;
  for (let i = 0; i < rafters; i++) {
    const lx = -hw + 1 + (i + 0.5) * ((b.w - 2) / rafters);
    const fallen = rng.chance(0.5);
    const len = b.d + 0.6;
    const g = boxT(0.14, 0.18, len, tiles.wood_beam ?? 1);
    const [wx, wz] = toWorld(lx, 0);
    const m = fallen
      ? new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rng.range(0.25, 0.45), b.rot + rng.range(-0.2, 0.2), rng.range(-0.1, 0.1))).setPosition(wx, gy + 1.2, wz)
      : new THREE.Matrix4().makeRotationY(b.rot).setPosition(wx, gy + b.height * (1 - b.damage * 0.5) - 0.1, wz);
    batches.get('charred', wx, wz).add(g, m);
  }
  // church tower stump
  if (b.id === 'church') {
    const [tx, tz] = toWorld(0, -hd - 2);
    const towerH = 13;
    for (let side = 0; side < 4; side++) {
      const a = (side * Math.PI) / 2 + b.rot;
      const h = towerH * (side === 1 ? 0.55 : side === 3 ? 0.8 : 1);
      const g = boxT(4.2, h, 0.7, tile, 0, 0);
      const ox = Math.sin(a) * 1.75;
      const oz = Math.cos(a) * 1.75;
      batches.get(mat, tx + ox, tz + oz).add(g, new THREE.Matrix4().makeRotationY(a).setPosition(tx + ox, gy + h / 2, tz + oz));
      out.colliders.push({ c: new THREE.Vector3(tx + ox, gy + h / 2, tz + oz), s: new THREE.Vector3(4.2, h, 0.7), r: a });
    }
  }
}

function mound(x: number, y: number, z: number, r: number, h: number, rng: Rng): THREE.BufferGeometry {
  const g = new THREE.SphereGeometry(1, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2);
  const p = g.attributes.position as THREE.BufferAttribute;
  const n = new Noise2D(rng.int(1, 9999));
  for (let i = 0; i < p.count; i++) {
    const px = p.getX(i);
    const pz = p.getZ(i);
    const py = p.getY(i);
    const k = 1 + n.get(px * 2.2, pz * 2.2) * 0.25 + n.get(px * 6, pz * 6) * 0.08;
    p.setXYZ(i, px * r * k, py * h * k, pz * r * k * rng.range(0.85, 1));
  }
  g.computeVertexNormals();
  g.translate(x, y, z);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (p.getX(i) - x) / 1.5, (p.getZ(i) - z) / 1.5);
  return g;
}

function road(t: Terrain, batches: CellBatches, tiles: Record<string, number>): void {
  const tile = tiles.cobblestone_wet ?? 2;
  const x0 = -66;
  const x1 = 66;
  const w = 4.6;
  const segX = 66;
  const segZ = 4;
  const pos: number[] = [];
  const uv: number[] = [];
  const col: number[] = [];
  const idx: number[] = [];
  for (let j = 0; j <= segZ; j++)
    for (let i = 0; i <= segX; i++) {
      const x = x0 + ((x1 - x0) * i) / segX;
      const z = VILLAGE_ROAD_Z - w / 2 + (w * j) / segZ;
      const y = t.height(x, z) + 0.035;
      pos.push(x, y, z);
      uv.push(x / tile, z / tile);
      const edge = Math.abs(j / segZ - 0.5) * 2;
      const c = 1 - edge * edge * 0.35;
      col.push(c, c, c);
    }
  for (let j = 0; j < segZ; j++)
    for (let i = 0; i < segX; i++) {
      const a = j * (segX + 1) + i;
      idx.push(a, a + segX + 1, a + 1, a + 1, a + segX + 1, a + segX + 2);
    }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  batches.get('cobble', 0, VILLAGE_ROAD_Z).add(g);
}

function stump(t: Terrain, x: number, z: number, rng: Rng, hMax = 6): THREE.BufferGeometry {
  const h = rng.range(1.2, hMax);
  const r = rng.range(0.12, 0.32);
  const g = new THREE.CylinderGeometry(r * 0.7, r, h, 9, 6, true);
  const p = g.attributes.position as THREE.BufferAttribute;
  const lean = rng.range(-0.12, 0.12);
  const lean2 = rng.range(-0.12, 0.12);
  for (let i = 0; i < p.count; i++) {
    let y = p.getY(i);
    const k = (y + h / 2) / h;
    // jagged splintered top
    if (k > 0.99) y -= rng.range(0, Math.min(1.2, h * 0.3));
    const bend = k * k;
    p.setXYZ(i, p.getX(i) * (1 + Math.sin(i) * 0.06) + lean * bend * h, y, p.getZ(i) * (1 + Math.cos(i * 1.7) * 0.06) + lean2 * bend * h);
  }
  g.computeVertexNormals();
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * r * 6, (uv.getY(i) * h) / 1.2);
  g.translate(x, t.height(x, z) + h / 2 - 0.2, z);
  return g;
}

/** Box with UVs aligned to world-scale tiles; offsets keep brick courses continuous along a wall. */
function boxT(w: number, h: number, d: number, tile: number, uOff = 0, vOff = 0): THREE.BoxGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  const n = g.attributes.normal as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) {
    const ax = Math.abs(n.getX(i));
    const ay = Math.abs(n.getY(i));
    let sx = w;
    let sy = h;
    let ou = uOff;
    let ov = vOff;
    if (ax > 0.5) {
      sx = d;
      ou = 0;
    } else if (ay > 0.5) {
      sy = d;
      ov = 0;
    }
    uv.setXY(i, (uv.getX(i) * sx + ou) / tile, (uv.getY(i) * sy + ov) / tile);
  }
  return g;
}
