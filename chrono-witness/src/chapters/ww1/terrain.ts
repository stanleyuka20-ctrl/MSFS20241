import * as THREE from 'three';
import { Noise2D, Rng, clamp, smoothstep } from '../../core/Random';
import { TRENCHES, DUGOUTS, CRATERS, BUILDINGS, FARM, VILLAGE_ROAD_Z, FLOODED, type TrenchDef } from './layout';

interface Seg {
  ax: number;
  az: number;
  bx: number;
  bz: number;
  len: number;
  tx: number;
  tz: number;
  /** Arc length at segment start along its polyline. */
  s0: number;
  trench: TrenchDef;
  totalLen: number;
  bay: boolean;
}

export interface TrenchHit {
  trench: TrenchDef;
  dist: number;
  /** Signed lateral offset: positive = north side. */
  side: number;
  seg: Seg;
  along: number;
}

const CELL = 8;
const INFLUENCE = 6.5;

/**
 * Heightfield for the sector: gentle chalk-upland base, churned ground between the lines, craters,
 * trenches (with fire steps, parapet/parados spoil), dugout and cellar excavations, building pads
 * and the village road. Queries are accelerated with a uniform grid of trench segments.
 */
export class Terrain {
  readonly noise = new Noise2D(1916);
  private noise2 = new Noise2D(77);
  private segs: Seg[] = [];
  private grid = new Map<number, Seg[]>();
  readonly craters: { x: number; z: number; r: number; depth: number; water?: number }[] = [];
  private craterGrid = new Map<number, number[]>();

  constructor() {
    for (const t of TRENCHES) {
      let s = 0;
      const total = t.points.reduce((acc, p, i) => (i ? acc + Math.hypot(p[0] - t.points[i - 1][0], p[1] - t.points[i - 1][1]) : 0), 0);
      for (let i = 1; i < t.points.length; i++) {
        const [ax, az] = t.points[i - 1];
        const [bx, bz] = t.points[i];
        const len = Math.hypot(bx - ax, bz - az);
        if (len < 1e-3) continue;
        const tx = (bx - ax) / len;
        const tz = (bz - az) / len;
        const seg: Seg = { ax, az, bx, bz, len, tx, tz, s0: s, trench: t, totalLen: total, bay: t.fireStep && Math.abs(tx) > 0.9 && len > 5 };
        s += len;
        this.segs.push(seg);
        const minX = Math.min(ax, bx) - INFLUENCE;
        const maxX = Math.max(ax, bx) + INFLUENCE;
        const minZ = Math.min(az, bz) - INFLUENCE;
        const maxZ = Math.max(az, bz) + INFLUENCE;
        for (let cx = Math.floor(minX / CELL); cx <= Math.floor(maxX / CELL); cx++)
          for (let cz = Math.floor(minZ / CELL); cz <= Math.floor(maxZ / CELL); cz++) {
            const k = key(cx, cz);
            let l = this.grid.get(k);
            if (!l) this.grid.set(k, (l = []));
            l.push(seg);
          }
      }
    }
    // craters: authored + scattered (no man's land dense, between lines moderate, rear sparse)
    for (const c of CRATERS) this.craters.push({ ...c });
    const rng = new Rng(4242);
    const tryAdd = (x: number, z: number, r: number, depth: number, water?: number): void => {
      if (this.nearTrench(x, z, r + 2.2)) return;
      for (const b of BUILDINGS) if (Math.abs(x - b.x) < b.w / 2 + r + 2 && Math.abs(z - b.z) < b.d / 2 + r + 2) return;
      if (Math.abs(z - VILLAGE_ROAD_Z) < r + 3) return;
      if (x > -38 && x < -12 && z > 58 && z < 86) return; // farm
      this.craters.push({ x, z, r, depth, water });
    };
    for (let i = 0; i < 420; i++) {
      const x = rng.range(-110, 110);
      const z = rng.range(-170, -64);
      const r = rng.range(1.5, 4.8);
      tryAdd(x, z, r, r * rng.range(0.32, 0.5), rng.chance(0.35) ? -r * 0.32 : undefined);
    }
    for (let i = 0; i < 90; i++) {
      const r = rng.range(1.2, 3.6);
      tryAdd(rng.range(-80, 80), rng.range(-56, 0), r, r * rng.range(0.3, 0.45), rng.chance(0.3) ? -r * 0.3 : undefined);
    }
    for (let i = 0; i < 70; i++) {
      const r = rng.range(1.2, 3.2);
      tryAdd(rng.range(-90, 90), rng.range(10, 110), r, r * rng.range(0.25, 0.4), rng.chance(0.2) ? -r * 0.28 : undefined);
    }
    this.craters.forEach((c, i) => {
      for (let cx = Math.floor((c.x - c.r * 1.5) / CELL); cx <= Math.floor((c.x + c.r * 1.5) / CELL); cx++)
        for (let cz = Math.floor((c.z - c.r * 1.5) / CELL); cz <= Math.floor((c.z + c.r * 1.5) / CELL); cz++) {
          const k = key(cx, cz);
          let l = this.craterGrid.get(k);
          if (!l) this.craterGrid.set(k, (l = []));
          l.push(i);
        }
    });
  }

  /** Undisturbed ground (no trenches/craters): low-frequency chalk upland. */
  base(x: number, z: number): number {
    let h = this.noise.fbm(x * 0.006, z * 0.006, 3) * 2.2 + this.noise.fbm(x * 0.03 + 11, z * 0.03, 2) * 0.35;
    // churned ground between and in front of the lines
    const churn = smoothstep(14, -6, z) * (0.6 + 0.4 * smoothstep(-60, -80, z));
    h += churn * (this.noise2.fbm(x * 0.22, z * 0.22, 3) * 0.22 + this.noise2.get(x * 0.07, z * 0.07) * 0.25);
    // village sits slightly higher
    h += smoothstep(30, 55, z) * 0.6;
    return h;
  }

  /** True if any trench centreline lies within r of (x, z) (searches all grid cells the radius covers). */
  nearTrench(x: number, z: number, r: number): boolean {
    const c0x = Math.floor((x - r) / CELL);
    const c1x = Math.floor((x + r) / CELL);
    const c0z = Math.floor((z - r) / CELL);
    const c1z = Math.floor((z + r) / CELL);
    for (let cx = c0x; cx <= c1x; cx++)
      for (let cz = c0z; cz <= c1z; cz++) {
        const l = this.grid.get(key(cx, cz));
        if (!l) continue;
        for (const s of l) if (segDist(s, x, z).d < r) return true;
      }
    return false;
  }

  /** Nearest trench segment info (for placement and gameplay queries). */
  trenchAt(x: number, z: number, maxDist = INFLUENCE): TrenchHit | null {
    const l = this.grid.get(key(Math.floor(x / CELL), Math.floor(z / CELL)));
    if (!l) return null;
    let best: TrenchHit | null = null;
    for (const s of l) {
      const r = segDist(s, x, z);
      if (r.d < maxDist && (!best || r.d < best.dist)) {
        // side: positive when the point lies to the north (smaller z) of an east–west segment
        const lateral = s.tx * (z - s.az) - s.tz * (x - s.ax);
        const north = Math.abs(s.tx) > 0.3 ? lateral * Math.sign(s.tx) < 0 : lateral * Math.sign(s.tz) > 0;
        best = { trench: s.trench, dist: r.d, side: north ? r.d : -r.d, seg: s, along: s.s0 + r.t * s.len };
      }
    }
    return best;
  }

  /** Trench carve depth and spoil berm height at a point. */
  private trenchProfile(x: number, z: number): { carve: number; berm: number; floor: number; wall: number } {
    const l = this.grid.get(key(Math.floor(x / CELL), Math.floor(z / CELL)));
    let carve = 0;
    let berm = 0;
    let floor = 0;
    let wall = 0;
    if (!l) return { carve, berm, floor, wall };
    for (const s of l) {
      const t = s.trench;
      const r = segDist(s, x, z);
      let d = r.d;
      if (d > INFLUENCE) continue;
      const n = t.rough > 0 ? this.noise.get(x * 0.35, z * 0.35) : 0;
      d += n * t.rough * 0.35;
      let depth = t.depth * (1 + n * 0.1 * t.rough);
      // ramps at polyline ends
      const along = s.s0 + r.t * s.len;
      if (t.rampStart) depth *= smoothstep(0, t.rampStart, along);
      if (t.rampEnd) depth *= smoothstep(s.totalLen, s.totalLen - t.rampEnd, along);
      const hf = t.floorWidth / 2;
      const lateral = s.tx * (z - s.az) - s.tz * (x - s.ax);
      const isNorth = Math.abs(s.tx) > 0.3 && lateral * Math.sign(s.tx) < 0;
      const step = s.bay && isNorth ? 0.5 : 0;
      let c = 0;
      if (d <= hf) {
        c = depth;
        floor = Math.max(floor, 1 - d / hf);
      } else if (step > 0 && d <= hf + step) {
        c = depth - 0.47;
      } else {
        const dw = d - hf - step;
        if (dw < t.batter) {
          const k = dw / t.batter;
          c = (step > 0 ? depth - 0.47 : depth) * (1 - k);
          c -= smoothstep(0.75, 1, k) * 0.02;
          wall = Math.max(wall, 1);
        }
      }
      carve = Math.max(carve, c);
      const hw = hf + step + t.batter;
      const bh = isNorth ? t.parapet : t.parados;
      const bump = bh * smoothstep(hw - 0.05, hw + 0.55, d) * (1 - smoothstep(hw + 1.1, hw + 3.6, d)) * (t.rampEnd || t.rampStart ? depth / t.depth : 1);
      berm = Math.max(berm, bump);
    }
    return { carve, berm, floor, wall };
  }

  private craterProfile(x: number, z: number): { h: number; bowl: number } {
    const l = this.craterGrid.get(key(Math.floor(x / CELL), Math.floor(z / CELL)));
    let h = 0;
    let bowl = 0;
    if (!l) return { h, bowl };
    for (const i of l) {
      const c = this.craters[i];
      const d = Math.hypot(x - c.x, z - c.z) / c.r;
      if (d > 1.5) continue;
      if (d < 1) {
        const v = -c.depth * (1 - d * d) * (1 - d * d * 0.3) + c.depth * 0.18 * smoothstep(0.7, 1, d);
        if (v < h) h = v;
        bowl = Math.max(bowl, 1 - d);
      } else {
        h += c.depth * 0.18 * (1 - smoothstep(1, 1.5, d));
      }
    }
    return { h, bowl };
  }

  private boxCarve(x: number, z: number): number {
    let c = 0;
    for (const dg of DUGOUTS) {
      const [rx, rz] = dg.room;
      const [sx, sz] = dg.size;
      if (Math.abs(x - rx) <= sx / 2 && Math.abs(z - rz) <= sz / 2) c = Math.max(c, dg.depth);
      // entrance passage (0.95 m wide), floor sloping from trench floor to room floor
      const [[ex0, ez0], [ex1, ez1]] = dg.entrance;
      const len = Math.hypot(ex1 - ex0, ez1 - ez0);
      const tx = (ex1 - ex0) / len;
      const tz = (ez1 - ez0) / len;
      const px = x - ex0;
      const pz = z - ez0;
      const along = px * tx + pz * tz;
      const lat = Math.abs(-px * tz + pz * tx);
      if (along > -0.25 && along < len + 0.2 && lat < 0.78) c = Math.max(c, dg.depth - 0.12 - clamp(1 - along / 1.0, 0, 1) * 0.3);
    }
    // farm cellar + stairs
    const [cx, cz] = FARM.cellarRoom;
    const [csx, csz] = FARM.cellarSize;
    if (Math.abs(x - cx) <= csx / 2 && Math.abs(z - cz) <= csz / 2) c = Math.max(c, FARM.cellarDepth);
    const [s0x, s0z] = FARM.cellarStairTop;
    const [s1x] = FARM.cellarStairBottom;
    if (x <= s0x + 0.2 && x >= s1x - 0.2 && Math.abs(z - s0z) < 0.8) {
      const k = clamp((s0x - x) / (s0x - s1x), 0, 1);
      c = Math.max(c, Math.floor(k * 8) / 8 * FARM.cellarDepth);
    }
    return c;
  }

  /** Full terrain height. */
  height(x: number, z: number): number {
    let h = this.base(x, z);
    // building pads
    for (const b of BUILDINGS) {
      const dx = Math.abs(x - b.x) - b.w / 2 - 0.6;
      const dz = Math.abs(z - b.z) - b.d / 2 - 0.6;
      const k = 1 - smoothstep(0, 3, Math.max(dx, dz));
      if (k > 0) h = h * (1 - k) + this.base(b.x, b.z) * k;
    }
    // road
    const rd = Math.abs(z - VILLAGE_ROAD_Z);
    if (rd < 6) {
      const k = 1 - smoothstep(2.6, 6, rd);
      h = h * (1 - k) + (this.base(x, VILLAGE_ROAD_Z) + 0.06 - rd * rd * 0.006) * k;
    }
    const cp = this.craterProfile(x, z);
    const tp = this.trenchProfile(x, z);
    h += cp.h * (1 - clamp(tp.carve, 0, 1));
    h += tp.berm * (1 - clamp(tp.carve / 0.3, 0, 1));
    h -= tp.carve;
    const bc = this.boxCarve(x, z);
    if (bc > 0) h = Math.min(h, this.base(x, z) - bc);
    return h;
  }

  /** Material weights: x = mud, y = grass, z = chalk, w = puddle-ability. */
  blend(x: number, z: number, h: number, out: THREE.Vector4): THREE.Vector4 {
    const tp = this.trenchProfile(x, z);
    const cp = this.craterProfile(x, z);
    const n = this.noise2.get(x * 0.11, z * 0.11);
    const n2 = this.noise.get(x * 0.5 + 3, z * 0.5);
    const between = smoothstep(14, 4, z);
    let mud = clamp(tp.floor * 1.6 + between * (0.45 + n * 0.35) + cp.bowl * 0.8, 0, 1);
    const roadD = Math.abs(z - VILLAGE_ROAD_Z);
    if (roadD < 3.4) mud = Math.max(mud, 0.75 + n2 * 0.25);
    let grass = clamp(smoothstep(8, 22, z) * (0.75 + n * 0.4) * (1 - mud), 0, 1);
    grass = Math.max(grass, clamp((1 - between) * 0.0 + smoothstep(-64, -90, z) * (0.25 + n * 0.3), 0, 0.6) * (1 - cp.bowl));
    const chalk = clamp(tp.berm * 0.85 * (0.45 + n2 * 0.5) + (cp.h > 0 ? cp.h * 2.0 : 0) * 0.45, 0, 0.7);
    let pud = clamp(tp.floor * 1.3 + cp.bowl * 1.2 + (roadD < 3 ? 0.6 : 0) + between * 0.25, 0, 1);
    if (h > this.base(x, z) + 0.05) pud *= 0.2;
    out.set(mud, grass * (1 - chalk), chalk, pud);
    return out;
  }

  /**
   * Precomputed ambient occlusion from the heightfield: fraction of the sky hemisphere not blocked
   * by surrounding terrain (8 directions × 3 distances).
   */
  aoAt(x: number, y: number, z: number): number {
    let occ = 0;
    const dirs = 8;
    for (let i = 0; i < dirs; i++) {
      const a = (i / dirs) * Math.PI * 2;
      const dx = Math.cos(a);
      const dz = Math.sin(a);
      let maxSlope = 0;
      for (const r of [0.6, 1.4, 3.0]) {
        const hh = this.height(x + dx * r, z + dz * r) - y;
        maxSlope = Math.max(maxSlope, hh / r);
      }
      occ += Math.sin(Math.atan(maxSlope));
    }
    return clamp(1 - (occ / dirs) * 0.95, 0.12, 1);
  }

  /** Surface type and movement speed multiplier for footsteps and wading. */
  surface(x: number, y: number, z: number): { surface: string; speed: number } {
    const fl = FLOODED;
    const tp = this.trenchAt(x, z, 1.2);
    if (tp && tp.trench.id === 'old_boot_s' && z < fl.from[1] && z > fl.to[1]) return { surface: 'water', speed: 0.55 };
    const roadD = Math.abs(z - VILLAGE_ROAD_Z);
    if (roadD < 2.8 && x > -60 && x < 60) return { surface: 'stone', speed: 1 };
    const g = this.height(x, z);
    if (y - g > 0.06) return { surface: 'wood', speed: 1 }; // standing on duckboards / props
    if (tp && tp.dist < tp.trench.floorWidth / 2 + 0.1) return { surface: 'mud', speed: tp.trench.duckboards ? 0.9 : 0.72 };
    if (z < 8) return { surface: 'mud', speed: 0.85 };
    return { surface: 'default', speed: 1 };
  }

  get segments(): readonly Seg[] {
    return this.segs;
  }
}

function key(cx: number, cz: number): number {
  return (cx + 1000) * 4096 + (cz + 1000);
}

function segDist(s: Seg, x: number, z: number): { d: number; t: number } {
  const px = x - s.ax;
  const pz = z - s.az;
  let t = (px * s.tx + pz * s.tz) / s.len;
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  const cx = s.ax + s.tx * s.len * t;
  const cz = s.az + s.tz * s.len * t;
  return { d: Math.hypot(x - cx, z - cz), t };
}

export interface ChunkSpec {
  x0: number;
  z0: number;
  size: number;
  seg: number;
}

/** Build one terrain chunk (with skirts) as geometry with blend + ao attributes. */
export function buildChunk(t: Terrain, c: ChunkSpec): THREE.BufferGeometry {
  const n = c.seg + 1;
  const step = c.size / c.seg;
  const vCount = n * n + 4 * n;
  const pos = new Float32Array(vCount * 3);
  const blend = new Float32Array(vCount * 4);
  const ao = new Float32Array(vCount);
  const heights = new Float32Array((n + 2) * (n + 2));
  // heights with a 1-sample border for normals
  for (let j = -1; j <= n; j++)
    for (let i = -1; i <= n; i++) heights[(j + 1) * (n + 2) + (i + 1)] = t.height(c.x0 + i * step, c.z0 + j * step);
  const H = (i: number, j: number): number => heights[(j + 1) * (n + 2) + (i + 1)];
  const normals = new Float32Array(vCount * 3);
  const b4 = new THREE.Vector4();
  let v = 0;
  for (let j = 0; j < n; j++)
    for (let i = 0; i < n; i++) {
      const x = c.x0 + i * step;
      const z = c.z0 + j * step;
      const y = H(i, j);
      pos.set([x, y, z], v * 3);
      const nx = H(i - 1, j) - H(i + 1, j);
      const nz = H(i, j - 1) - H(i, j + 1);
      const ny = 2 * step;
      const l = Math.hypot(nx, ny, nz);
      normals.set([nx / l, ny / l, nz / l], v * 3);
      t.blend(x, z, y, b4);
      blend.set([b4.x, b4.y, b4.z, b4.w], v * 4);
      // AO only where it matters (trenches, craters) — elsewhere cheap 1
      const needsAO = Math.abs(y - t.base(x, z)) > 0.25;
      ao[v] = needsAO ? t.aoAt(x, y + 0.05, z) : 1;
      v++;
    }
  // skirts: duplicate border vertices lowered
  const border: [number, number][] = [];
  for (let i = 0; i < n; i++) border.push([i, 0]);
  for (let j = 0; j < n; j++) border.push([n - 1, j]);
  for (let i = n - 1; i >= 0; i--) border.push([i, n - 1]);
  for (let j = n - 1; j >= 0; j--) border.push([0, j]);
  const skirtStart = v;
  for (const [i, j] of border) {
    const src = j * n + i;
    pos.set([pos[src * 3], pos[src * 3 + 1] - 0.6, pos[src * 3 + 2]], v * 3);
    normals.set(normals.subarray(src * 3, src * 3 + 3), v * 3);
    blend.set(blend.subarray(src * 4, src * 4 + 4), v * 4);
    ao[v] = ao[src] * 0.8;
    v++;
  }
  const idx: number[] = [];
  for (let j = 0; j < c.seg; j++)
    for (let i = 0; i < c.seg; i++) {
      const a = j * n + i;
      const b = a + 1;
      const d = a + n;
      const e = d + 1;
      // alternate diagonal to reduce directional artefacts
      if ((i + j) % 2 === 0) idx.push(a, d, b, b, d, e);
      else idx.push(a, d, e, a, e, b);
    }
  for (let k = 0; k < border.length - 1; k++) {
    const [i0, j0] = border[k];
    const [i1, j1] = border[k + 1];
    const a = j0 * n + i0;
    const b = j1 * n + i1;
    const sa = skirtStart + k;
    const sb = skirtStart + k + 1;
    idx.push(a, sa, b, b, sa, sb, a, b, sa, b, sb, sa);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos.subarray(0, v * 3), 3));
  g.setAttribute('normal', new THREE.BufferAttribute(normals.subarray(0, v * 3), 3));
  g.setAttribute('blend', new THREE.BufferAttribute(blend.subarray(0, v * 4), 4));
  g.setAttribute('ao', new THREE.BufferAttribute(ao.subarray(0, v), 1));
  g.setIndex(idx);
  g.computeBoundingBox();
  g.computeBoundingSphere();
  return g;
}

/** Coarse outer terrain ring with a hole over the detailed area. */
export function buildOuterRing(t: Terrain, inner: { minX: number; maxX: number; minZ: number; maxZ: number }, extent: number, step: number, holeExtent?: number): THREE.BufferGeometry {
  const n = Math.floor((extent * 2) / step) + 1;
  const pos: number[] = [];
  const nor: number[] = [];
  const bl: number[] = [];
  const ao: number[] = [];
  const idx: number[] = [];
  const index = new Map<number, number>();
  const b4 = new THREE.Vector4();
  const vert = (i: number, j: number): number => {
    const k = j * n + i;
    let id = index.get(k);
    if (id !== undefined) return id;
    const x = -extent + i * step;
    const z = -extent + j * step;
    const y = t.base(x, z) - 0.04 - Math.max(0, Math.hypot(x, z) - 600) * 0.004;
    id = pos.length / 3;
    pos.push(x, y, z);
    const hx = t.base(x - step, z) - t.base(x + step, z);
    const hz = t.base(x, z - step) - t.base(x, z + step);
    const l = Math.hypot(hx, 2 * step, hz);
    nor.push(hx / l, (2 * step) / l, hz / l);
    t.blend(x, z, y, b4);
    bl.push(b4.x * 0.7, Math.max(b4.y, 0.3), b4.z * 0.3, 0);
    ao.push(1);
    index.set(k, id);
    return id;
  };
  for (let j = 0; j < n - 1; j++)
    for (let i = 0; i < n - 1; i++) {
      const x = -extent + i * step;
      const z = -extent + j * step;
      const cx = x + step / 2;
      const cz = z + step / 2;
      if (cx > inner.minX && cx < inner.maxX && cz > inner.minZ && cz < inner.maxZ) continue;
      if (holeExtent && Math.abs(cx) < holeExtent && Math.abs(cz) < holeExtent) continue;
      const a = vert(i, j);
      const b = vert(i + 1, j);
      const d = vert(i, j + 1);
      const e = vert(i + 1, j + 1);
      idx.push(a, d, b, b, d, e);
    }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('blend', new THREE.Float32BufferAttribute(bl, 4));
  g.setAttribute('ao', new THREE.Float32BufferAttribute(ao, 1));
  g.setIndex(idx);
  g.computeBoundingSphere();
  return g;
}
