import * as THREE from 'three';
import { Builder, type Rect } from './builder';
import { Rng } from '../../core/Random';

/**
 * Kit for multi-storey city blocks (Wilhelmine tenements, shop terraces): street facades with real
 * window and door openings, cornices, window surrounds, balconies, roofs, dark "rooms" behind the
 * windows, and damage states (blown-out windows, burnt-out roofless shells, sheared-off sections that
 * expose the floors, firewalls where a neighbour is gone).
 *
 * Local frame: the facade runs along x from x0 to x1 at z = 0 and faces +z (the street); the block
 * extends to z = −depth. Material keys: wall, wallGround, trim, frame, glass, void, slab, wallpaper,
 * roof, firewall, iron, shutter, charred.
 */
export interface BlockSpec {
  x0: number;
  x1: number;
  depth: number;
  floors: number;
  floorH: number;
  /** Window bay spacing (m). */
  bay?: number;
  /** Ground-floor openings: 'windows', 'shops', or none. */
  ground?: 'windows' | 'shops';
  /** Carriage gateway through the ground floor (x range). */
  gate?: { x0: number; x1: number; h: number };
  /** Street door (x range). */
  door?: { x0: number; x1: number };
  roof?: 'pitched' | 'flat' | 'none';
  /** 0 intact … 1 every window blown. */
  blown?: number;
  /** Burnt-out shell: no roof, no floors, charred openings; sky visible through the windows. */
  burnt?: boolean;
  /** Sections where the facade (and floors behind it) collapsed down to height `top`. */
  collapsed?: { x0: number; x1: number; top: number }[];
  /** Expose the left (x0) / right (x1) side as a firewall (neighbour gone). */
  firewall?: { left?: boolean; right?: boolean };
  balconies?: boolean;
  /** Rear facade windows (courtyard side). */
  rear?: boolean;
  /** Skip the "rooms" behind windows (for interiors that are modelled). */
  noVoidRanges?: { x0: number; x1: number; floor: number }[];
  /** Remap material keys (e.g. a brick school uses its own wall material). */
  keys?: Partial<Record<'wall' | 'wallGround' | 'trim' | 'roof', string>>;
}

export function block(b0: Builder, s: BlockSpec, rng: Rng): void {
  const km = s.keys ?? {};
  // remapping proxy: same builder, translated material keys
  const k = (key: string): string => (km as Record<string, string | undefined>)[key] ?? key;
  const b = {
    box: (key: string, ...a: Parameters<Builder['box']> extends [string, ...infer R] ? R : never) => b0.box(k(key), ...a),
    wall: (key: string, ...a: Parameters<Builder['wall']> extends [string, ...infer R] ? R : never) => b0.wall(k(key), ...a),
    quad: (key: string, ...a: Parameters<Builder['quad']> extends [string, ...infer R] ? R : never) => b0.quad(k(key), ...a),
    geo: (key: string, ...a: Parameters<Builder['geo']> extends [string, ...infer R] ? R : never) => b0.geo(k(key), ...a),
    collider: (...a: Parameters<Builder['collider']>) => b0.collider(...a),
  } as unknown as Builder;
  const bay = s.bay ?? 3.1;
  const H = s.floors * s.floorH;
  const T = 0.5; // facade thickness
  const winW = 1.25;
  const winH = 2.15;
  const sill = 0.95;
  const top = (x: number): number => {
    let t = H;
    for (const c of s.collapsed ?? []) if (x > c.x0 - 0.01 && x < c.x1 + 0.01) t = Math.min(t, c.top);
    return t;
  };
  // window centres along the facade
  const n = Math.max(1, Math.floor((s.x1 - s.x0) / bay));
  const pad = (s.x1 - s.x0 - n * bay) / 2;
  const centres: number[] = [];
  for (let i = 0; i < n; i++) centres.push(s.x0 + pad + bay * (i + 0.5));
  const inGate = (x: number): boolean => !!s.gate && x > s.gate.x0 - 0.8 && x < s.gate.x1 + 0.8;
  const inDoor = (x: number): boolean => !!s.door && x > s.door.x0 - 0.7 && x < s.door.x1 + 0.7;

  // ---- openings per floor
  const openings: Rect[] = [];
  const windows: { r: Rect; floor: number; blown: boolean }[] = [];
  for (let f = 0; f < s.floors; f++) {
    const y0 = f * s.floorH;
    for (const cx of centres) {
      if (f === 0) {
        if (inGate(cx) || inDoor(cx)) continue;
        if (s.ground === 'shops') {
          const r = { x0: cx - bay / 2 + 0.35, x1: cx + bay / 2 - 0.35, y0: 0.45, y1: 3.0 };
          openings.push(r);
          windows.push({ r, floor: 0, blown: rng.chance(s.blown ?? 0) });
          continue;
        }
        if (s.ground !== 'windows') continue;
      }
      const r = { x0: cx - winW / 2, x1: cx + winW / 2, y0: y0 + sill + (f === 0 ? 0.4 : 0), y1: y0 + sill + winH + (f === 0 ? 0.2 : 0) };
      if (r.y1 > top(cx) - 0.2) continue;
      openings.push(r);
      windows.push({ r, floor: f, blown: s.burnt || rng.chance(s.blown ?? 0) });
    }
  }
  if (s.gate) openings.push({ x0: s.gate.x0, x1: s.gate.x1, y0: 0, y1: s.gate.h });
  if (s.door) openings.push({ x0: s.door.x0, x1: s.door.x1, y0: 0.15, y1: 2.6 });

  // ---- facade wall, split into vertical strips so collapsed sections can stop low
  const cuts = new Set<number>([s.x0, s.x1]);
  for (const c of s.collapsed ?? []) {
    cuts.add(Math.max(s.x0, c.x0));
    cuts.add(Math.min(s.x1, c.x1));
  }
  const xs = [...cuts].sort((a, b) => a - b);
  for (let i = 0; i < xs.length - 1; i++) {
    const xa = xs[i];
    const xb = xs[i + 1];
    const t = top((xa + xb) / 2);
    const ops = openings.filter((o) => o.x1 > xa && o.x0 < xb).map((o) => ({ ...o, x0: Math.max(o.x0, xa), x1: Math.min(o.x1, xb) }));
    // ground floor in a darker, rusticated render
    b.wall('wallGround', xa, xb, 0, Math.min(t, s.floorH), -T, 0, ops, true);
    if (t > s.floorH) b.wall('wall', xa, xb, s.floorH, t, -T, 0, ops, true);
    // broken, ragged top on collapsed strips
    if (t < H - 0.1) {
      for (let x = xa; x < xb - 0.2; x += 0.35) {
        const hh = rng.next() * rng.next() * 2.2;
        if (hh > 0.08) b.box(t > s.floorH ? 'wall' : 'wallGround', x, Math.min(xb, x + 0.35), t, t + hh, -T, 0);
      }
    }
  }

  // ---- facade detail: plinth, string courses, main cornice, window surrounds
  b.box('trim', s.x0, s.x1, 0, 0.45, 0, 0.06);
  for (let f = 1; f <= s.floors; f++) {
    const y = f * s.floorH;
    const last = f === s.floors;
    // spans not collapsed
    for (let i = 0; i < xs.length - 1; i++) {
      if (top((xs[i] + xs[i + 1]) / 2) < y - 0.01) continue;
      if (last) {
        b.box('trim', xs[i], xs[i + 1], y - 0.25, y + 0.25, 0, 0.5); // main cornice
        b.box('trim', xs[i], xs[i + 1], y - 0.55, y - 0.25, 0, 0.18); // frieze
      } else b.box('trim', xs[i], xs[i + 1], y - 0.12, y + 0.08, 0, f === 1 ? 0.22 : 0.12);
    }
  }
  for (const w of windows) {
    const r = w.r;
    const shop = w.floor === 0 && s.ground === 'shops';
    if (!shop) {
      // lintel cornice (pedimented on the first floor) and sill
      b.box('trim', r.x0 - 0.18, r.x1 + 0.18, r.y1, r.y1 + (w.floor === 1 ? 0.32 : 0.18), 0, w.floor === 1 ? 0.18 : 0.1);
      b.box('trim', r.x0 - 0.12, r.x1 + 0.12, r.y0 - 0.1, r.y0, 0, 0.12);
      if (w.floor === 1) for (const px of [r.x0 - 0.18, r.x1 + 0.06]) b.box('trim', px, px + 0.12, r.y0, r.y1, 0, 0.08);
    } else {
      b.box('frame', r.x0 - 0.2, r.x1 + 0.2, r.y1 + 0.05, r.y1 + 0.55, 0, 0.1); // shop fascia
    }
    windowUnit(b, r, -0.18, w.blown, shop, rng);
    if (w.blown && !shop && w.floor > 0) b.box('charred', r.x0 - 0.05, r.x1 + 0.05, r.y1 + 0.02, r.y1 + 0.5 + rng.next() * 0.5, 0.005, 0.012);
    // glazed or shuttered openings are not walkable
    b.collider(r.x0, r.x1, r.y0, r.y1, -T, -0.05);
  }
  // ---- balconies on the middle bays of floors 1–3
  if (s.balconies && centres.length >= 3) {
    const mids = centres.length >= 5 ? [centres[1], centres[centres.length - 2]] : [centres[Math.floor(centres.length / 2)]];
    for (let f = 1; f <= Math.min(3, s.floors - 1); f++) {
      for (const cx of mids) {
        const y = f * s.floorH;
        if (top(cx) < y + 1.2) continue;
        b.box('trim', cx - 1.2, cx + 1.2, y - 0.18, y + 0.02, 0, 0.95);
        for (let k = 0; k <= 12; k++) b.box('iron', cx - 1.15 + k * 0.19, cx - 1.13 + k * 0.19, y + 0.02, y + 1.0, 0.86, 0.88);
        b.box('iron', cx - 1.2, cx + 1.2, y + 0.98, y + 1.03, 0.84, 0.9);
      }
    }
  }

  // ---- dark rooms behind intact facades (cheap: one box per floor, set back from the openings)
  if (!s.burnt) {
    for (let f = 0; f < s.floors; f++) {
      const y0 = f * s.floorH;
      for (let i = 0; i < xs.length - 1; i++) {
        const xa0 = xs[i] + 0.25;
        const xb0 = xs[i + 1] - 0.25;
        if (top((xa0 + xb0) / 2) < y0 + s.floorH - 0.01) continue;
        // subtract modelled interiors and the gateway from the strip
        let segs: [number, number][] = [[xa0, xb0]];
        const cutOut = (c0: number, c1: number): void => {
          const next: [number, number][] = [];
          for (const [a0, a1] of segs) {
            if (c1 <= a0 || c0 >= a1) next.push([a0, a1]);
            else {
              if (c0 > a0) next.push([a0, c0]);
              if (c1 < a1) next.push([c1, a1]);
            }
          }
          segs = next;
        };
        for (const nv of s.noVoidRanges ?? []) if (nv.floor === f) cutOut(nv.x0, nv.x1);
        if (f === 0 && s.gate) cutOut(s.gate.x0 - 0.3, s.gate.x1 + 0.3);
        for (const [xa, xb] of segs) {
          if (xb - xa < 0.3) continue;
          b.box('void', xa, xb, y0 + 0.05, y0 + s.floorH - 0.05, -T - 3.2, -T - 2.8);
          b.box('void', xa, xb, y0 + s.floorH - 0.25, y0 + s.floorH - 0.05, -T - 2.8, -T); // ceiling inside
          b.box('void', xa, xb, y0 + 0.05, y0 + 0.2, -T - 2.8, -T); // floor inside
          // closing side panels so the "room" has no open ends seen at an angle
          b.box('void', xa - 0.05, xa, y0 + 0.05, y0 + s.floorH - 0.05, -T - 3.2, -T);
          b.box('void', xb, xb + 0.05, y0 + 0.05, y0 + s.floorH - 0.05, -T - 3.2, -T);
        }
      }
    }
  }
  // ---- collapsed sections: broken floor slabs sticking out, papered walls, rubble at the foot
  for (const c of s.collapsed ?? []) {
    for (let f = 1; f < s.floors; f++) {
      const y = f * s.floorH;
      if (y <= c.top + 0.3) continue;
      // remains of each floor hang from the back wall
      const len = s.depth * (0.25 + rng.next() * 0.35);
      for (let x = c.x0 + 0.2; x < c.x1 - 0.2; x += 1.4) {
        const droop = rng.range(-0.25, 0.05);
        const g = new THREE.BoxGeometry(1.35, 0.28, len);
        b.geo('slab', g, new THREE.Matrix4().makeRotationX(droop).setPosition(x + 0.7, y - 0.14 - Math.abs(droop) * len * 0.3, -s.depth + len / 2 + 0.3));
      }
      b.box('wallpaper', c.x0 + 0.1, c.x1 - 0.1, y, y + s.floorH - 0.3, -s.depth + 0.36, -s.depth + 0.4);
    }
    const mound = new THREE.SphereGeometry(1, 18, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    const mp = mound.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < mp.count; i++) {
      const k = 1 + (rng.next() - 0.5) * 0.3;
      mp.setXYZ(i, mp.getX(i) * k, mp.getY(i) * k, mp.getZ(i) * k);
    }
    const w = (c.x1 - c.x0) / 2;
    const mh = Math.min(5.5, (H - c.top) * 0.28 + 1.2);
    mound.scale(w + 0.8, mh, s.depth * 0.45 + 1.4);
    b.geo('rubble', mound, new THREE.Matrix4().makeTranslation((c.x0 + c.x1) / 2, -0.2, -s.depth * 0.45));
    // solid core (the slopes stay walkable only at the toe, spilling ~1 m past the facade)
    b.collider(c.x0 + 0.3, c.x1 - 0.3, 0, mh * 0.75, -s.depth + 0.5, -0.4);
  }

  // ---- side walls, back wall, roof
  const sideKey = (exposed?: boolean): string => (exposed ? 'firewall' : 'wall');
  b.box(sideKey(s.firewall?.left), s.x0, s.x0 + 0.4, 0, top(s.x0 + 0.2), -s.depth, -T, true);
  b.box(sideKey(s.firewall?.right), s.x1 - 0.4, s.x1, 0, top(s.x1 - 0.2), -s.depth, -T, true);
  const backOps: Rect[] = [];
  if (s.rear) {
    for (let f = 0; f < s.floors; f++) for (const cx of centres) if (!(f === 0 && inGate(cx))) backOps.push({ x0: cx - 0.6, x1: cx + 0.6, y0: f * s.floorH + 1.0, y1: f * s.floorH + 3.0 });
  }
  if (s.gate) backOps.push({ x0: s.gate.x0, x1: s.gate.x1, y0: 0, y1: s.gate.h });
  b.wall('wall', s.x0, s.x1, 0, H, -s.depth, -s.depth + 0.45, backOps, true);
  if (s.gate) {
    // carriage way: vaulted passage walls and ceiling
    b.box('wallGround', s.gate.x0 - 0.3, s.gate.x0, 0, s.gate.h, -s.depth + 0.45, -T, true);
    b.box('wallGround', s.gate.x1, s.gate.x1 + 0.3, 0, s.gate.h, -s.depth + 0.45, -T, true);
    b.box('wallGround', s.gate.x0 - 0.3, s.gate.x1 + 0.3, s.gate.h, s.gate.h + 0.4, -s.depth + 0.45, -T);
  }
  if (s.burnt) {
    // the inside of a burnt-out shell: charred inner faces, no floors, sky above
    b.box('charred', s.x0 + 0.4, s.x1 - 0.4, 0.3, H * 0.9, -T - 0.01, -T);
    return;
  }
  const roof = s.roof ?? 'pitched';
  for (let i = 0; i < xs.length - 1; i++) {
    if (top((xs[i] + xs[i + 1]) / 2) < H - 0.01) continue;
    const xa = xs[i];
    const xb = xs[i + 1];
    if (roof === 'flat') b.box('roof', xa, xb, H, H + 0.3, -s.depth, 0.2);
    else if (roof === 'pitched') {
      const rise = s.depth * 0.32;
      const A = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
      b.quad('roof', A(xa, H + 0.2, 0.35), A(xb, H + 0.2, 0.35), A(xb, H + rise, -s.depth / 2), A(xa, H + rise, -s.depth / 2));
      b.quad('roof', A(xb, H + 0.2, -s.depth - 0.3), A(xa, H + 0.2, -s.depth - 0.3), A(xa, H + rise, -s.depth / 2), A(xb, H + rise, -s.depth / 2));
      // gable infill at both ends of each span (hidden in a terrace, closes exposed ends)
      for (const gx of [xa, xb]) gableTri(b, gx, -s.depth, 0, H + 0.2, H + rise);
      // chimneys on the ridge
      for (let x = xa + 2.5; x < xb - 1; x += 6.5) b.box('firewall', x - 0.4, x + 0.4, H + rise - 0.8, H + rise + 1.2, -s.depth / 2 - 0.4, -s.depth / 2 + 0.4);
    }
  }
}

function gableTri(b: Builder, x: number, zb: number, zf: number, y0: number, y1: number): void {
  const zm = (zb + zf) / 2;
  const pos = [x, y0, zf, x, y1, zm, x, y0, zb, x, y0, zb, x, y1, zm, x, y0, zf];
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  const uv: number[] = [];
  for (let i = 0; i < pos.length; i += 3) uv.push(pos[i + 2], pos[i + 1]);
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  b.geo('firewall', g);
}

/** Casement window with transom (or a shop front), glazed or blown out. */
function windowUnit(b: Builder, r: Rect, z: number, blown: boolean, shop: boolean, rng: Rng): void {
  const ft = 0.07;
  if (shop) {
    b.box('frame', r.x0, r.x1, r.y0, r.y0 + 0.12, z - 0.05, z + 0.05);
    if (!blown) b.box('glass', r.x0 + 0.05, r.x1 - 0.05, r.y0 + 0.12, r.y1 - 0.05, z - 0.02, z);
    // roller shutter pulled half down
    const sh = r.y1 - (r.y1 - r.y0) * (0.25 + rng.next() * 0.5);
    b.box('shutter', r.x0, r.x1, sh, r.y1, z + 0.08, z + 0.12);
    return;
  }
  if (blown && rng.chance(0.6)) {
    // frame torn out, or a single hanging casement
    if (rng.chance(0.4)) b.geo('frame', new THREE.BoxGeometry(0.55, (r.y1 - r.y0) * 0.7, 0.05), new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(0, rng.range(0.5, 1.4), rng.range(-0.2, 0.2))).setPosition(r.x0 + 0.1, (r.y0 + r.y1) / 2 - 0.2, z + 0.25));
    return;
  }
  const ty = r.y1 - 0.55; // transom
  const cx = (r.x0 + r.x1) / 2;
  b.box('frame', r.x0, r.x1, r.y0, r.y0 + ft, z - 0.06, z);
  b.box('frame', r.x0, r.x1, r.y1 - ft, r.y1, z - 0.06, z);
  b.box('frame', r.x0, r.x0 + ft, r.y0, r.y1, z - 0.06, z);
  b.box('frame', r.x1 - ft, r.x1, r.y0, r.y1, z - 0.06, z);
  b.box('frame', r.x0, r.x1, ty - 0.03, ty + 0.03, z - 0.07, z + 0.01);
  b.box('frame', cx - 0.03, cx + 0.03, r.y0, ty, z - 0.07, z + 0.01);
  if (!blown) b.box('glass', r.x0 + ft, r.x1 - ft, r.y0 + ft, r.y1 - ft, z - 0.04, z - 0.035);
}

/** Pavement of large slabs with a strip of small setts (Berlin style), between z0 and z1 (world, axis-aligned). */
export function pavement(b: Builder, x0: number, x1: number, z0: number, z1: number, kerbKey = 'kerb', walkKey = 'walk'): void {
  const zk = z0 < z1 ? z0 : z1;
  const zf = z0 < z1 ? z1 : z0;
  const kerbAtLow = Math.abs(z0) < Math.abs(z1);
  // kerb stones on the road side
  if (kerbAtLow) b.box(kerbKey, x0, x1, -0.3, 0.14, zk, zk + 0.3, true);
  else b.box(kerbKey, x0, x1, -0.3, 0.14, zf - 0.3, zf, true);
  b.box(walkKey, x0, x1, -0.3, 0.13, kerbAtLow ? zk + 0.3 : zk, kerbAtLow ? zf : zf - 0.3, true);
}

