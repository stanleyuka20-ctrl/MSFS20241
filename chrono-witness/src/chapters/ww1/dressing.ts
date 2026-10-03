import * as THREE from 'three';
import { Rng, Noise2D } from '../../core/Random';
import { TRENCHES, DUGOUTS, FLOODED, CRATER_CROSSING, type Revet } from './layout';
import type { Terrain } from './terrain';
import { GeoBatch, canvasTexture } from '../common/geo';

/** Geometry batches grouped by material key and 32 m spatial cell (keeps frustum culling effective). */
export class CellBatches {
  private map = new Map<string, GeoBatch>();
  constructor(readonly cell = 32) {}
  get(mat: string, x: number, z: number): GeoBatch {
    const k = `${mat}|${Math.floor(x / this.cell)}|${Math.floor(z / this.cell)}`;
    let b = this.map.get(k);
    if (!b) this.map.set(k, (b = new GeoBatch()));
    return b;
  }
  entries(): [string, GeoBatch][] {
    return [...this.map.entries()];
  }
}

/** Placement records consumed by the runtime (instancing, interactables, colliders). */
export interface Dressing {
  batches: CellBatches;
  sandbags: THREE.Matrix4[];
  duckboards: THREE.Matrix4[];
  /** Static collision boxes (centre, size, rotY). */
  colliders: { c: THREE.Vector3; s: THREE.Vector3; r: number }[];
  signs: THREE.Mesh[];
  ladders: { bottom: THREE.Vector3; top: THREE.Vector3; exit: THREE.Vector3; normal: THREE.Vector3; id: string }[];
  waters: THREE.BufferGeometry[];
  /** Points along walls useful for props (x, y, z, inward normal). */
  wallSpots: { p: THREE.Vector3; n: THREE.Vector3; trench: string }[];
  firestepSpots: { p: THREE.Vector3; n: THREE.Vector3 }[];
  /** Telephone cable path along Pall Mall's west wall. */
  cablePath: THREE.Vector3[];
}

/** Revetment style per trench segment (mixed sectors vary deterministically). */
function styleFor(rev: Revet, rng: Rng): Exclude<Revet, 'mixed'> {
  if (rev !== 'mixed') return rev;
  const r = rng.next();
  return r < 0.38 ? 'planks' : r < 0.68 ? 'corrugated' : r < 0.84 ? 'hurdle' : 'bare';
}

/** An interval along a trench segment wall that must stay open (junction or dugout door). */
interface Opening {
  trench: string;
  seg: number;
  side: 1 | -1;
  s0: number;
  s1: number;
}

/**
 * Find where other trenches and dugout entrances meet each trench wall, so revetments, fire steps
 * and parapet bags leave those openings clear.
 */
function computeOpenings(): Opening[] {
  const out: Opening[] = [];
  const samples: { x: number; z: number; half: number; trench: string }[] = [];
  for (const u of TRENCHES) {
    for (let i = 1; i < u.points.length; i++) {
      const [ax, az] = u.points[i - 1];
      const [bx, bz] = u.points[i];
      const len = Math.hypot(bx - ax, bz - az);
      for (let s = 0; s <= len; s += 0.4) samples.push({ x: ax + ((bx - ax) * s) / len, z: az + ((bz - az) * s) / len, half: u.floorWidth / 2 + 0.35, trench: u.id });
    }
  }
  for (const d of DUGOUTS) {
    const [[ex0, ez0], [ex1, ez1]] = d.entrance;
    for (let k = -1; k <= 4; k++) {
      const f = k / 4;
      samples.push({ x: ex0 + (ex1 - ex0) * f, z: ez0 + (ez1 - ez0) * f, half: 0.85, trench: `dug:${d.id}` });
    }
  }
  for (const t of TRENCHES) {
    const hf = t.floorWidth / 2;
    for (let i = 1; i < t.points.length; i++) {
      const [ax, az] = t.points[i - 1];
      const [bx, bz] = t.points[i];
      const len = Math.hypot(bx - ax, bz - az);
      if (len < 0.3) continue;
      const tx = (bx - ax) / len;
      const tz = (bz - az) / len;
      for (const p of samples) {
        if (p.trench === t.id) continue;
        const px = p.x - ax;
        const pz = p.z - az;
        const along = px * tx + pz * tz;
        if (along < -1 || along > len + 1) continue;
        const lat = -px * tz + pz * tx; // positive = left side (nx, nz) = (-tz, tx)
        const a = Math.abs(lat);
        if (a < hf - 0.05 || a > hf + t.batter + 1.4) continue;
        out.push({ trench: t.id, seg: i, side: lat > 0 ? 1 : -1, s0: along - p.half, s1: along + p.half });
      }
    }
  }
  return out;
}

/** Split [s0, s1] removing opening intervals; returns remaining pieces. */
function openPieces(s0: number, s1: number, ops: Opening[]): [number, number][] {
  let pieces: [number, number][] = [[s0, s1]];
  for (const o of ops) {
    const next: [number, number][] = [];
    for (const [a, b] of pieces) {
      if (o.s1 <= a || o.s0 >= b) next.push([a, b]);
      else {
        if (o.s0 > a) next.push([a, o.s0]);
        if (o.s1 < b) next.push([o.s1, b]);
      }
    }
    pieces = next;
  }
  return pieces.filter(([a, b]) => b - a > 0.35);
}

export function buildDressing(t: Terrain, tiles: Record<string, number>, density: number): Dressing {
  const rng = new Rng(1916_10);
  const openings = computeOpenings();
  const noise = new Noise2D(5);
  const d: Dressing = { batches: new CellBatches(), sandbags: [], duckboards: [], colliders: [], signs: [], ladders: [], waters: [], wallSpots: [], firestepSpots: [], cablePath: [] };

  for (const tr of TRENCHES) {
    const hf = tr.floorWidth / 2;
    for (let i = 1; i < tr.points.length; i++) {
      const [ax, az] = tr.points[i - 1];
      const [bx, bz] = tr.points[i];
      const len = Math.hypot(bx - ax, bz - az);
      if (len < 0.4) continue;
      const tx = (bx - ax) / len;
      const tz = (bz - az) / len;
      // left normal (pointing to the left of travel direction)
      const nx = -tz;
      const nz = tx;
      const isBay = tr.fireStep && Math.abs(tx) > 0.9 && len > 5;
      for (const sideSign of [1, -1] as const) {
        const ox = nx * sideSign;
        const oz = nz * sideSign;
        const north = Math.abs(tx) > 0.3 ? (oz < 0) : false;
        const step = isBay && north ? 0.5 : 0;
        const style = styleFor(tr.revet, rng);
        const ops = openings.filter((o) => o.trench === tr.id && o.seg === i && o.side === sideSign);
        const wantBags = (tr.fireStep && north) || (!tr.fireStep && rng.chance(0.25)) || (tr.fireStep && !north && rng.chance(0.4));
        const courses = north && tr.fireStep ? 3 : rng.int(1, 2);
        for (const [p0, p1] of openPieces(0, len, ops)) {
          const sx = ax + tx * p0;
          const sz = az + tz * p0;
          const plen = p1 - p0;
          if (style !== 'bare' || tr.rough < 0.5) wallStrip(t, d, tiles, sx, sz, tx, tz, ox, oz, plen, hf + step, tr.batter, style, rng, tr.id);
          if (step > 0) fireStep(t, d, tiles, sx, sz, tx, tz, ox, oz, plen, hf, tr.depth);
          if (wantBags && tr.rough < 0.7) parapetBags(t, d, sx, sz, tx, tz, ox, oz, plen, hf + step + tr.batter + 0.15, courses, rng);
          else if (wantBags) scatteredBags(t, d, sx, sz, tx, tz, ox, oz, plen, hf + step + tr.batter + 0.1, rng);
        }
      }
      if (tr.duckboards) duckboards(t, d, ax, az, tx, tz, len, rng, tr.id);
      if (isBay) d.firestepSpots.push({ p: new THREE.Vector3(ax + tx * len * 0.5 - nz * 0 + 0, 0, az + tz * len * 0.5), n: new THREE.Vector3(0, 0, 1) });
    }
  }

  // Pall Mall telephone cable: along the west wall (left side going north = −x side)
  const pm = TRENCHES.find((x) => x.id === 'pall_mall')!;
  for (let i = 0; i < pm.points.length; i++) {
    const [x, z] = pm.points[i];
    const off = -(pm.floorWidth / 2 + 0.06);
    const y = t.height(x + off, z) + 1.25;
    d.cablePath.push(new THREE.Vector3(x + off, y, z));
  }

  // flooded section water
  const ob = TRENCHES.find((x) => x.id === 'old_boot_s')!;
  const water = new GeoBatch();
  for (let i = 1; i < ob.points.length; i++) {
    const [ax, az] = ob.points[i - 1];
    const [bx, bz] = ob.points[i];
    const zMid = (az + bz) / 2;
    if (zMid > FLOODED.from[1] + 2 || zMid < FLOODED.to[1] - 2) continue;
    const len = Math.hypot(bx - ax, bz - az);
    const y = Math.min(t.height(ax, az), t.height(bx, bz)) + FLOODED.level;
    const g = new THREE.PlaneGeometry(len + 0.6, ob.floorWidth + 0.9);
    g.rotateX(-Math.PI / 2);
    g.rotateY(-Math.atan2(bz - az, bx - ax));
    g.translate((ax + bx) / 2, y, (az + bz) / 2);
    water.add(g);
  }
  if (!water.empty) d.waters.push(water.build());

  // crater ponds
  for (const c of t.craters) {
    if (c.water === undefined) continue;
    const y = t.base(c.x, c.z) + c.water;
    const g = new THREE.CircleGeometry(c.r * 0.92, 28);
    g.rotateX(-Math.PI / 2);
    g.translate(c.x, y, c.z);
    d.waters.push(g);
  }

  // crater crossing: ladder out of the trench + duckboard bridge
  const [lx, lz] = CRATER_CROSSING.ladderBottom;
  const ly = t.height(lx, lz);
  const topY = t.base(lx, lz - 0.9) + 0.05;
  const lnormal = new THREE.Vector3(0, 0, 1); // climber stands south of the ladder, ladder leans on the north wall
  ladder(d, tiles, new THREE.Vector3(lx, ly, lz - 0.35), topY - ly, lnormal);
  const [bfx, bfz] = CRATER_CROSSING.bridgeFrom;
  d.ladders.push({ id: 'crater_ladder', bottom: new THREE.Vector3(lx, ly, lz - 0.1), top: new THREE.Vector3(lx, topY, lz), exit: new THREE.Vector3(bfx, t.base(bfx, bfz) + 0.25, bfz - 0.35), normal: lnormal });
  // north ladder: from the start of Old Boot Alley (north) up onto the far end of the bridge
  const [nx2, nz2] = CRATER_CROSSING.ladderNorth;
  const ny2 = t.height(nx2, nz2 - 0.3);
  const ntop = t.base(nx2, nz2 + 0.9) + 0.05;
  const nnormal = new THREE.Vector3(0, 0, -1);
  ladder(d, tiles, new THREE.Vector3(nx2, ny2, nz2 + 0.35), ntop - ny2, nnormal);
  const [btx, btz] = CRATER_CROSSING.bridgeTo;
  d.ladders.push({ id: 'crater_ladder_n', bottom: new THREE.Vector3(nx2, ny2, nz2 + 0.1), top: new THREE.Vector3(nx2, ntop, nz2), exit: new THREE.Vector3(btx, t.base(btx, btz) + 0.25, btz + 0.35), normal: nnormal });
  bridge(t, d, tiles, CRATER_CROSSING.bridgeFrom, CRATER_CROSSING.bridgeTo);

  void noise;
  void density;
  return d;
}

/** A revetment wall section: textured strip from trench floor to ground level, with posts. */
function wallStrip(t: Terrain, d: Dressing, tiles: Record<string, number>, ax: number, az: number, tx: number, tz: number, ox: number, oz: number, len: number, inner: number, batter: number, style: Exclude<Revet, 'mixed'>, rng: Rng, trench: string): void {
  if (style === 'bare' || style === 'sandbags') return;
  const matKey = style === 'planks' ? 'planks' : style === 'corrugated' ? 'corrugated' : 'hurdle';
  const tile = tiles[style === 'planks' ? 'wood_planks' : style === 'corrugated' ? 'corrugated_iron' : 'wicker_hurdle'] ?? 1;
  // shorten slightly at both ends so corners overlap less
  const s0 = 0.05;
  const s1 = len - 0.05;
  const steps = Math.max(1, Math.ceil((s1 - s0) / 0.8));
  const pos: number[] = [];
  const uv: number[] = [];
  const col: number[] = [];
  const idx: number[] = [];
  const lean = batter * 0.85;
  for (let k = 0; k <= steps; k++) {
    const s = s0 + ((s1 - s0) * k) / steps;
    const cx = ax + tx * s;
    const cz = az + tz * s;
    const bx = cx + ox * (inner - 0.02);
    const bz = cz + oz * (inner - 0.02);
    const by = t.height(cx + ox * (inner - 0.08), cz + oz * (inner - 0.08)) - 0.05;
    const topx = cx + ox * (inner + lean);
    const topz = cz + oz * (inner + lean);
    let ty = t.height(cx + ox * (inner + batter + 0.12), cz + oz * (inner + batter + 0.12));
    // ragged top for corrugated/hurdle
    ty += style === 'planks' ? 0.02 : rng.range(-0.12, 0.04);
    ty = Math.max(ty, by + 0.4);
    pos.push(bx, by, bz, topx, ty, topz);
    uv.push(s / tile, 0, s / tile, (ty - by) / tile);
    const aoB = Math.min(1, t.aoAt(bx - ox * 0.1, by + 0.15, bz - oz * 0.1) * 1.15);
    const aoT = Math.min(1, t.aoAt(topx - ox * 0.1, ty - 0.1, topz - oz * 0.1) * 1.1);
    col.push(aoB, aoB, aoB, aoT, aoT, aoT);
    if (k > 0) {
      const a = (k - 1) * 2;
      // face toward trench interior (−o direction)
      idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  // winding: ensure normal points toward the trench centre
  g.computeVertexNormals();
  const n = g.attributes.normal;
  if (n.getX(0) * ox + n.getZ(0) * oz > 0) {
    const ix = g.index!.array as Uint16Array | Uint32Array;
    for (let i = 0; i < ix.length; i += 3) {
      const tmp = ix[i + 1];
      ix[i + 1] = ix[i + 2];
      ix[i + 2] = tmp;
    }
    g.computeVertexNormals();
  }
  const mx = ax + tx * len * 0.5;
  const mz = az + tz * len * 0.5;
  d.batches.get(matKey, mx, mz).add(g);
  if (len > 2) d.wallSpots.push({ p: new THREE.Vector3(mx + ox * inner, t.height(mx, mz), mz + oz * inner), n: new THREE.Vector3(-ox, 0, -oz), trench });

  // posts / pickets
  const postTile = tiles.wood_beam ?? 1;
  const spacing = style === 'corrugated' ? 1.6 : 1.25;
  for (let s = 0.4; s < len - 0.2; s += spacing) {
    const cx = ax + tx * s;
    const cz = az + tz * s;
    const by = t.height(cx + ox * (inner - 0.1), cz + oz * (inner - 0.1)) - 0.1;
    const ty = t.height(cx + ox * (inner + batter + 0.1), cz + oz * (inner + batter + 0.1)) + (style === 'hurdle' ? 0.1 : 0.15);
    const h = Math.max(0.5, ty - by);
    const isPicket = style === 'corrugated';
    const w = isPicket ? 0.05 : 0.11;
    const g2 = new THREE.BoxGeometry(w, h, w);
    remapUV(g2, w, h, postTile);
    const m = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(tz * -ox + 0, 0, tx * ox).normalize().lengthSq() > 0 ? new THREE.Vector3(-oz, 0, ox) : new THREE.Vector3(1, 0, 0), -Math.atan2(batter * 0.85, h));
    m.setPosition(cx + ox * (inner + 0.03 + batter * 0.42), by + h / 2, cz + oz * (inner + 0.03 + batter * 0.42));
    d.batches.get(isPicket ? 'steel' : 'beam', cx, cz).add(g2, m);
  }
}

function remapUV(g: THREE.BufferGeometry, w: number, h: number, tile: number): void {
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * w * 4) / tile, (uv.getY(i) * h) / tile);
}

function fireStep(t: Terrain, d: Dressing, tiles: Record<string, number>, ax: number, az: number, tx: number, tz: number, ox: number, oz: number, len: number, hf: number, depth: number): void {
  void depth;
  const tile = tiles.wood_planks ?? 1.2;
  const s0 = 0.6;
  const s1 = len - 0.6;
  if (s1 <= s0) return;
  const mid = (s0 + s1) / 2;
  const cx = ax + tx * mid + ox * (hf + 0.25);
  const cz = az + tz * mid + oz * (hf + 0.25);
  const y = t.height(cx, cz);
  const L = s1 - s0;
  // top boards
  const top = new THREE.BoxGeometry(L, 0.05, 0.5);
  const uv = top.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * L) / tile, uv.getY(i) * 0.5 / tile);
  const rot = -Math.atan2(tz, tx);
  const m = new THREE.Matrix4().makeRotationY(rot).setPosition(cx, y + 0.02, cz);
  d.batches.get('planks_solid', cx, cz).add(top, m);
  // riser boards
  const riser = new THREE.BoxGeometry(L, 0.48, 0.04);
  const uv2 = riser.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv2.count; i++) uv2.setXY(i, (uv2.getX(i) * L) / tile, uv2.getY(i) * 0.48 / tile);
  const m2 = new THREE.Matrix4().makeRotationY(rot).setPosition(cx - ox * 0.26, y - 0.22, cz - oz * 0.26);
  d.batches.get('planks_solid', cx, cz).add(riser, m2);
  d.colliders.push({ c: new THREE.Vector3(cx, y - 0.2, cz), s: new THREE.Vector3(L, 0.45, 0.52), r: rot });
  d.firestepSpots.push({ p: new THREE.Vector3(cx, y, cz), n: new THREE.Vector3(-ox, 0, -oz) });
}

function parapetBags(t: Terrain, d: Dressing, ax: number, az: number, tx: number, tz: number, ox: number, oz: number, len: number, off: number, courses: number, rng: Rng): void {
  const bagLen = 0.5;
  const rot = Math.atan2(tx, tz) + Math.PI / 2;
  for (let c = 0; c < courses; c++) {
    const stagger = c % 2 ? bagLen / 2 : 0;
    for (let s = 0.25 + stagger; s < len - 0.2; s += bagLen + rng.range(-0.02, 0.03)) {
      if (rng.chance(0.04)) continue; // occasional missing bag
      const back = c * 0.06; // courses step back slightly
      const x = ax + tx * s + ox * (off + back);
      const z = az + tz * s + oz * (off + back);
      const y = t.height(x, z) - 0.04 + c * 0.13;
      const m = new THREE.Matrix4().compose(
        new THREE.Vector3(x, y + 0.065, z),
        new THREE.Quaternion().setFromEuler(new THREE.Euler(rng.range(-0.06, 0.06), rot + rng.range(-0.08, 0.08), rng.range(-0.05, 0.05))),
        new THREE.Vector3(rng.range(0.92, 1.08), rng.range(0.85, 1.1), rng.range(0.92, 1.08)),
      );
      d.sandbags.push(m);
    }
  }
}

function scatteredBags(t: Terrain, d: Dressing, ax: number, az: number, tx: number, tz: number, ox: number, oz: number, len: number, off: number, rng: Rng): void {
  const rot = Math.atan2(tx, tz) + Math.PI / 2;
  const n = Math.floor(len / 2.5);
  for (let i = 0; i < n; i++) {
    const s = rng.range(0.3, len - 0.3);
    const x = ax + tx * s + ox * (off + rng.range(-0.1, 0.5));
    const z = az + tz * s + oz * (off + rng.range(-0.1, 0.5));
    const y = t.height(x, z);
    const m = new THREE.Matrix4().compose(new THREE.Vector3(x, y + 0.05, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(rng.range(-0.25, 0.25), rot + rng.range(-0.7, 0.7), rng.range(-0.2, 0.2))), new THREE.Vector3(1, rng.range(0.7, 1), 1));
    d.sandbags.push(m);
  }
}

function duckboards(t: Terrain, d: Dressing, ax: number, az: number, tx: number, tz: number, len: number, rng: Rng, trench: string): void {
  const L = 1.5;
  const rot = Math.atan2(tx, tz);
  const flooded = trench === 'old_boot_s';
  for (let s = L / 2 + 0.05; s < len - L / 2; s += L + 0.06) {
    const x = ax + tx * s;
    const z = az + tz * s;
    if (flooded && z < FLOODED.from[1] + 1 && z > FLOODED.to[1] - 1 && rng.chance(0.45)) continue; // sunk / floated away
    if (trench === 'old_boot_s' && rng.chance(0.25)) continue;
    const y0 = t.height(x - tx * 0.6, z - tz * 0.6);
    const y1 = t.height(x + tx * 0.6, z + tz * 0.6);
    const y = Math.max(t.height(x, z), (y0 + y1) / 2) + 0.06 + (flooded && z < FLOODED.from[1] && z > FLOODED.to[1] ? FLOODED.level - 0.08 : 0);
    const pitch = Math.atan2(y1 - y0, 1.2) * 0.8;
    const m = new THREE.Matrix4().compose(
      new THREE.Vector3(x, y, z),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(-pitch + rng.range(-0.02, 0.02), rot + rng.range(-0.03, 0.03), rng.range(-0.035, 0.035), 'YXZ')),
      new THREE.Vector3(1, 1, 1),
    );
    d.duckboards.push(m);
    d.colliders.push({ c: new THREE.Vector3(x, y - 0.02, z), s: new THREE.Vector3(0.5, 0.09, L), r: rot });
  }
}

function ladder(d: Dressing, tiles: Record<string, number>, base: THREE.Vector3, height: number, normal: THREE.Vector3): void {
  const tile = tiles.wood_beam ?? 1;
  const g = new GeoBatch();
  const h = height + 0.7;
  const lean = 0.25;
  const angle = Math.atan2(lean, h);
  for (const sx of [-0.22, 0.22]) {
    const rail = new THREE.BoxGeometry(0.06, h, 0.07);
    remapUV(rail, 0.06, h, tile);
    g.add(rail, new THREE.Matrix4().makeTranslation(sx, h / 2, 0));
  }
  for (let y = 0.28; y < h - 0.1; y += 0.3) {
    const rung = new THREE.CylinderGeometry(0.022, 0.022, 0.46, 8);
    rung.rotateZ(Math.PI / 2);
    g.add(rung, new THREE.Matrix4().makeTranslation(0, y, 0));
  }
  const geo = g.build();
  const rotY = Math.atan2(normal.x, normal.z);
  const m = new THREE.Matrix4().makeRotationY(rotY).multiply(new THREE.Matrix4().makeRotationX(angle));
  m.setPosition(base.x, base.y - 0.05, base.z);
  geo.applyMatrix4(m);
  d.batches.get('beam', base.x, base.z).add(geo);
}

function bridge(t: Terrain, d: Dressing, tiles: Record<string, number>, from: [number, number], to: [number, number]): void {
  const tile = tiles.wood_planks ?? 1.2;
  const [fx, fz] = from;
  const [tx2, tz2] = to;
  const len = Math.hypot(tx2 - fx, tz2 - fz);
  const dirX = (tx2 - fx) / len;
  const dirZ = (tz2 - fz) / len;
  const rot = Math.atan2(dirX, dirZ);
  const y0 = t.base(fx, fz) + 0.12;
  const y1 = t.base(tx2, tz2) + 0.12;
  // two duckboards end to end on cross-bearers + supporting baulks
  const n = Math.ceil(len / 1.5);
  for (let i = 0; i < n; i++) {
    const s = (i + 0.5) * (len / n);
    const x = fx + dirX * s;
    const z = fz + dirZ * s;
    const sag = Math.sin((s / len) * Math.PI) * 0.12;
    const y = y0 + (y1 - y0) * (s / len) - sag;
    d.duckboards.push(new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion().setFromEuler(new THREE.Euler(0, rot, (i % 2 ? 0.02 : -0.015), 'YXZ')), new THREE.Vector3(1.1, 1, len / n / 1.5)));
    d.colliders.push({ c: new THREE.Vector3(x, y - 0.02, z), s: new THREE.Vector3(0.6, 0.1, len / n), r: rot });
  }
  // baulks (long timbers) under the boards
  for (const off of [-0.32, 0.32]) {
    const b = new THREE.BoxGeometry(0.14, 0.14, len + 1.6);
    const uv = b.attributes.uv as THREE.BufferAttribute;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 0.14 / tile, (uv.getY(i) * (len + 1.6)) / tile);
    const m = new THREE.Matrix4().makeRotationY(rot);
    m.setPosition((fx + tx2) / 2 + Math.cos(rot) * off, (y0 + y1) / 2 - 0.16, (fz + tz2) / 2 - Math.sin(rot) * off);
    d.batches.get('beam', fx, fz).add(b, m);
  }
  // handrail-less: invisible guard colliders so the player does not slip into the crater by accident
  for (const off of [-0.55, 0.55]) {
    d.colliders.push({ c: new THREE.Vector3((fx + tx2) / 2 + Math.cos(rot) * off, (y0 + y1) / 2 + 0.6, (fz + tz2) / 2 - Math.sin(rot) * off), s: new THREE.Vector3(0.05, 1.2, len - 0.4), r: rot });
  }
}

/** Painted trench sign on a post. */
export function signMesh(text: string, sub: string | null, mat: THREE.Material, tracker: { track: <T extends { dispose: () => void }>(x: T) => T }): THREE.Group {
  const tex = tracker.track(
    canvasTexture(512, 192, (c) => {
      c.fillStyle = '#5b4a36';
      c.fillRect(0, 0, 512, 192);
      // weathered board
      for (let i = 0; i < 1600; i++) {
        c.fillStyle = `rgba(${30 + Math.random() * 40},${25 + Math.random() * 30},${18 + Math.random() * 20},${Math.random() * 0.25})`;
        c.fillRect(Math.random() * 512, Math.random() * 192, Math.random() * 40, 1 + Math.random() * 2);
      }
      c.fillStyle = 'rgba(232,226,210,0.92)';
      c.font = 'bold 64px Georgia, serif';
      c.textAlign = 'center';
      c.fillText(text, 256, sub ? 95 : 120);
      if (sub) {
        c.font = 'bold 40px Georgia, serif';
        c.fillText(sub, 256, 158);
      }
      // drips / mud
      c.fillStyle = 'rgba(60,45,30,0.5)';
      for (let i = 0; i < 30; i++) c.fillRect(Math.random() * 512, 150 + Math.random() * 42, 2 + Math.random() * 5, Math.random() * 30);
    }),
  );
  const g = new THREE.Group();
  const board = new THREE.Mesh(new THREE.BoxGeometry(0.75, 0.28, 0.025), [mat, mat, mat, mat, new THREE.MeshStandardMaterial({ map: tex, roughness: 0.9 }), mat]);
  board.position.y = 1.5;
  board.castShadow = true;
  const post = new THREE.Mesh(new THREE.BoxGeometry(0.07, 1.6, 0.07), mat);
  post.position.y = 0.8;
  post.castShadow = true;
  g.add(board, post);
  return g;
}

/** Sandbag geometry: a lumpy filled sack (~100 triangles), UVs in tiles. */
export function sandbagGeometry(tile: number): THREE.BufferGeometry {
  const w = 0.48;
  const h = 0.13;
  const dpt = 0.26;
  const g = new THREE.BoxGeometry(w, h, dpt, 5, 2, 3);
  const p = g.attributes.position as THREE.BufferAttribute;
  const n = new Noise2D(9);
  for (let i = 0; i < p.count; i++) {
    let x = p.getX(i);
    let y = p.getY(i);
    let z = p.getZ(i);
    const ux = (2 * x) / w;
    const uz = (2 * z) / dpt;
    const uy = (2 * y) / h;
    // pillow: thinner towards edges, rounded sides
    const edge = Math.max(Math.abs(ux) ** 3, Math.abs(uz) ** 3);
    y *= 1 - edge * 0.45;
    x *= 1 - Math.abs(uy) ** 2 * 0.08;
    z *= 1 - Math.abs(uy) ** 2 * 0.12 - Math.abs(ux) ** 4 * 0.1;
    y += n.get(x * 18, z * 18) * 0.008;
    // tied end slightly pinched
    if (ux > 0.8) {
      y *= 0.85;
      z *= 0.88;
    }
    p.setXYZ(i, x, y, z);
  }
  g.computeVertexNormals();
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * 0.5) / tile, (uv.getY(i) * 0.3) / tile);
  return g;
}

/** Duckboard geometry: two runners and seven slats (~100 triangles). */
export function duckboardGeometry(tile: number): THREE.BufferGeometry {
  const b = new GeoBatch();
  for (const x of [-0.19, 0.19]) {
    const r = new THREE.BoxGeometry(0.06, 0.07, 1.5);
    const uv = r.attributes.uv as THREE.BufferAttribute;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * 0.08 / tile, (uv.getY(i) * 1.5) / tile);
    b.add(r, new THREE.Matrix4().makeTranslation(x, -0.03, 0));
  }
  for (let i = 0; i < 9; i++) {
    const s = new THREE.BoxGeometry(0.5, 0.024, 0.085);
    const uv = s.attributes.uv as THREE.BufferAttribute;
    for (let k = 0; k < uv.count; k++) uv.setXY(k, (uv.getX(k) * 0.5) / tile + i * 0.37, uv.getY(k) * 0.085 / tile);
    b.add(s, new THREE.Matrix4().makeRotationY((i % 3 - 1) * 0.02).setPosition(0, 0.012, -0.68 + i * 0.17));
  }
  return b.build();
}
