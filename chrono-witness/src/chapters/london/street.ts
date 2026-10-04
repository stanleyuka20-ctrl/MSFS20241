import * as THREE from 'three';
import { Builder } from '../common/builder';
import { canvasTexture } from '../common/geo';
import { Rng } from '../../core/Random';
import { ROAD_HALF, FRONT, PAVEMENT, ROW_X0, ROW_X1, DOCK_LANE_X, DOCK_LANE_HALF, HIGH_STREET_Z, HOUSE_D, YARD_D, ALLEY_W, CRATER, STATION, WARDEN_POST, FIRST_AID_POST, DEPOT, BOUNDS, ALLEY_GATE, SHOPS_NORTH, SHOPS_SOUTH } from './layout';

export const STREET_SETS: Record<string, string> = {
  road: 'tarmac_road',
  pave: 'pavement_flags',
  kerb: 'pavement_flags',
  kerbPaint: 'kerbPaint',
  iron: 'rusty_steel',
  ironPaint: 'ironPaint',
  sandbag: 'sandbag_dry',
  stucco: 'render_stucco',
  brick: 'london_stock_brick',
  brickDark: 'london_stock_brick',
  tile: 'tile_station',
  platform: 'concrete_platform',
  slate: 'slate_roof',
  earth: 'mud_wet',
  rubble: 'stone_rubble',
  timber: 'wood_beam',
  frame: 'painted_wood',
  glass: 'glass',
  red: 'red',
  corrugated: 'corrugated_iron',
  cobble: 'cobblestone_wet',
};

export interface StreetBuild {
  b: Builder;
  lampPosts: THREE.Vector3[];
  signs: { text: string; sub?: string; pos: THREE.Vector3; rotY: number; style: 'shelter' | 'enamel' | 'painted' }[];
  waterTanks: THREE.Vector3[];
  /** Ground is flat at y = 0 except the crater; player ground queries use this. */
  groundAt: (x: number, z: number) => number;
}

/**
 * Streets, pavements, kerbs (with white blackout paint), alleys, Dock Lane, the High Street,
 * street furniture and public buildings (warden's post, First Aid Post, ARP depot, station building).
 */
export function buildStreets(tiles: Record<string, number>): StreetBuild {
  const b = new Builder(tiles, STREET_SETS);
  const rng = new Rng(1940);
  const out: StreetBuild = { b, lampPosts: [], signs: [], waterTanks: [], groundAt: () => 0 };
  const y0 = -0.3; // slab bottom

  // --- Cable Row: road, kerbs (white blackout paint), pavements — split at the Dock Lane junction
  const dl0 = DOCK_LANE_X - DOCK_LANE_HALF + 2.0;
  const dl1 = DOCK_LANE_X + DOCK_LANE_HALF - 2.0;
  const spans: [number, number][] = [
    [ROW_X0 - 4, dl0 - 2.0],
    [dl1 + 2.0, ROW_X1 + 4],
  ];
  b.box('road', ROW_X0 - 4, ROW_X1 + 4, y0, 0.0, -ROAD_HALF, ROAD_HALF, true);
  b.box('road', dl0, dl1, y0, 0.0, -FRONT - 0.5, -ROAD_HALF, true);
  b.box('road', dl0, dl1, y0, 0.0, ROAD_HALF, FRONT + 0.5, true);
  for (const [xa, xb] of spans) {
    for (const s of [-1, 1]) {
      const zk0 = s * ROAD_HALF;
      const zk1 = s * (ROAD_HALF + 0.25);
      b.box('kerb', xa, xb, y0, 0.13, Math.min(zk0, zk1), Math.max(zk0, zk1), true);
      for (let x = xa + 0.4; x < xb - 0.9; x += 1.8) b.box('kerbPaint', x, x + 0.9, 0.131, 0.135, Math.min(zk0, zk1) + 0.01, Math.max(zk0, zk1) - 0.01);
      const zp0 = s * (ROAD_HALF + 0.25);
      const zp1 = s * FRONT;
      b.box('pave', xa, xb, y0, 0.12, Math.min(zp0, zp1), Math.max(zp0, zp1), true);
    }
  }
  // back alleys (cobbled) behind the yards
  for (const s of [-1, 1]) {
    const za = s * (FRONT + HOUSE_D + YARD_D);
    const zb = s * (FRONT + HOUSE_D + YARD_D + ALLEY_W);
    b.box('cobble', ROW_X0 - 4, ROW_X1 + 4, y0, 0.02, Math.min(za, zb), Math.max(za, zb), true);
    // far alley wall (backs of the next street's yards), open at Dock Lane; the south wall has a gate
    const zw = s * (FRONT + HOUSE_D + YARD_D + ALLEY_W + 0.12);
    const segs: [number, number][] = s < 0 ? [[ROW_X0 - 4, dl0 - 2.0], [dl1 + 2.0, ROW_X1 + 4]] : [[ROW_X0 - 4, dl0 - 2.0], [dl1 + 2.0, ALLEY_GATE.x - 0.6], [ALLEY_GATE.x + 0.6, ROW_X1 + 4]];
    for (const [xa, xb] of segs) b.box('brickDark', xa, xb, 0, 2.0, Math.min(zw, zw + s * 0.24), Math.max(zw, zw + s * 0.24), true);
  }
  // yards ground (beaten earth / old flags), either side of the junction
  for (const s of [-1, 1]) {
    const za = s * (FRONT + 0.3);
    const zb = s * (FRONT + HOUSE_D + YARD_D);
    for (const [xa, xb] of [[ROW_X0, dl0 - 2.0], [dl1 + 2.0, ROW_X1]] as const) b.box('earth', xa, xb, y0, -0.005, Math.min(za, zb), Math.max(za, zb), true);
  }
  // rough ground beyond the south alley gate (a cleared bomb site the rescue party crosses)
  b.box('rubble', dl1 + 2.0, ROW_X1, y0, 0.0, FRONT + HOUSE_D + YARD_D + ALLEY_W + 0.36, BOUNDS.maxZ, true);

  // --- Dock Lane (north to the High Street, south to the docks), with the crater blocking it south
  b.box('road', dl0, dl1, y0, 0.0, HIGH_STREET_Z, -ROAD_HALF, true);
  b.box('road', dl0, dl1, y0, 0.0, ROAD_HALF, CRATER.z - CRATER.r, true);
  b.box('road', dl0, dl1, y0, 0.0, CRATER.z + CRATER.r, BOUNDS.maxZ, true);
  for (const x of [dl0 - 2.0, dl1]) {
    b.box('pave', x, x + 2.0, y0, 0.12, HIGH_STREET_Z, -ROAD_HALF - 0.25, true);
    // south of Cable Row the pavements stop at the crater's broken edge
    b.box('pave', x, x + 2.0, y0, 0.12, ROAD_HALF + 0.25, CRATER.z - CRATER.r - 0.6, true);
    b.box('pave', x, x + 2.0, y0, 0.12, CRATER.z + CRATER.r + 0.6, BOUNDS.maxZ, true);
  }
  // crater bowl with a burst water main (ring of rubble, flooded bottom)
  const bowl = new THREE.SphereGeometry(CRATER.r, 24, 10, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2);
  bowl.scale(1, 0.45, 1);
  const idx = bowl.index!.array as Uint16Array;
  for (let i = 0; i < idx.length; i += 3) {
    const t = idx[i + 1];
    idx[i + 1] = idx[i + 2];
    idx[i + 2] = t;
  }
  bowl.computeVertexNormals();
  b.geo('earth', bowl, new THREE.Matrix4().makeTranslation(CRATER.x, 0.02, CRATER.z));
  const rim = new THREE.TorusGeometry(CRATER.r, 0.9, 8, 28);
  rim.rotateX(Math.PI / 2);
  rim.scale(1, 1, 0.5);
  b.geo('rubble', rim, new THREE.Matrix4().makeTranslation(CRATER.x, 0.15, CRATER.z));
  // the crater blocks the lane: collision ring + bowl
  for (let a = 0; a < Math.PI * 2; a += Math.PI / 10) b.collider(CRATER.x + Math.cos(a) * CRATER.r - 0.8, CRATER.x + Math.cos(a) * CRATER.r + 0.8, 0, 2.0, CRATER.z + Math.sin(a) * CRATER.r - 0.8, CRATER.z + Math.sin(a) * CRATER.r + 0.8);
  // the lane south of the alley is closed off by wreckage on both sides up to the crater, so the only
  // link between the bombed ground (where the rescue lorry waits) and the alley is the gate
  const zFar = FRONT + HOUSE_D + YARD_D + ALLEY_W + 0.36;
  for (const xw of [dl0 - 2.3, dl1 + 2.0]) {
    b.box('rubble', xw, xw + 0.3, 0, 1.4, zFar, CRATER.z - CRATER.r + 0.8, true);
    b.collider(xw, xw + 0.3, 0, 3, zFar, CRATER.z + CRATER.r);
  }

  // --- High Street (north): road, pavements, shopfront terrace with the station building
  b.box('road', ROW_X0 - 4, ROW_X1 + 4, y0, 0.0, HIGH_STREET_Z - 3.8, HIGH_STREET_Z + 3.8, true);
  b.box('pave', ROW_X0 - 4, ROW_X1 + 4, y0, 0.12, HIGH_STREET_Z + 3.8, HIGH_STREET_Z + 3.8 + PAVEMENT, true);
  b.box('pave', ROW_X0 - 4, ROW_X1 + 4, y0, 0.12, HIGH_STREET_Z - 3.8 - PAVEMENT, HIGH_STREET_Z - 3.8, true);
  // Dock Lane side pavements between Cable Row and the High Street are bounded by the terrace ends' walls
  for (const x of [DOCK_LANE_X - DOCK_LANE_HALF - 0.3, DOCK_LANE_X + DOCK_LANE_HALF + 0.05]) {
    b.box('brickDark', x, x + 0.25, 0, 2.2, HIGH_STREET_Z + 3.8 + PAVEMENT, -FRONT - HOUSE_D - YARD_D - ALLEY_W - 0.4, true);
  }

  // --- lamp posts (unlit: blackout) with white-painted bands, along both pavements
  for (let x = ROW_X0 + 6; x < ROW_X1; x += 18) {
    for (const s of [-1, 1]) {
      if (Math.abs(x - DOCK_LANE_X) < DOCK_LANE_HALF + 2) continue;
      const p = new THREE.Vector3(x + (s > 0 ? 9 : 0), 0, s * (ROAD_HALF + 0.65));
      out.lampPosts.push(p);
      b.geo('ironPaint', new THREE.CylinderGeometry(0.07, 0.11, 3.6, 10), new THREE.Matrix4().makeTranslation(p.x, 1.92, p.z));
      b.geo('kerbPaint', new THREE.CylinderGeometry(0.115, 0.115, 0.45, 10), new THREE.Matrix4().makeTranslation(p.x, 0.65, p.z));
      b.geo('kerbPaint', new THREE.CylinderGeometry(0.112, 0.112, 0.25, 10), new THREE.Matrix4().makeTranslation(p.x, 1.25, p.z));
      b.geo('ironPaint', new THREE.CylinderGeometry(0.17, 0.12, 0.45, 8), new THREE.Matrix4().makeTranslation(p.x, 3.95, p.z));
      b.geo('ironPaint', new THREE.ConeGeometry(0.24, 0.18, 8), new THREE.Matrix4().makeTranslation(p.x, 4.27, p.z));
      b.collider(p.x - 0.12, p.x + 0.12, 0, 3, p.z - 0.12, p.z + 0.12);
    }
  }
  // --- pillar box
  const pb = new THREE.Vector3(-12, 0, ROAD_HALF + 0.75);
  b.geo('red', new THREE.CylinderGeometry(0.3, 0.32, 1.4, 16), new THREE.Matrix4().makeTranslation(pb.x, 0.82, pb.z));
  b.geo('red', new THREE.SphereGeometry(0.3, 16, 6, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.Matrix4().makeTranslation(pb.x, 1.52, pb.z));
  b.collider(pb.x - 0.32, pb.x + 0.32, 0, 1.6, pb.z - 0.32, pb.z + 0.32);
  // (no static water tanks: research shows most were built in 1941–42)

  // --- ARP warden's post: sandbag walls around a small brick hut on the corner
  const wp = WARDEN_POST;
  b.box('brick', wp.x - 1.6, wp.x + 1.6, 0.12, 2.4, wp.z - 1.4, wp.z + 1.0, true);
  b.box('slate', wp.x - 1.8, wp.x + 1.8, 2.4, 2.55, wp.z - 1.6, wp.z + 1.2, true);
  // blast wall in front of the door, open at the west end
  sandbagWall(b, wp.x - 1.4, wp.x + 2.0, wp.z + 1.25, 1.5, rng);
  b.box('frame', wp.x - 0.45, wp.x + 0.45, 0.12, 2.05, wp.z + 1.0, wp.z + 1.05);
  out.signs.push({ text: 'A.R.P.', sub: 'WARDEN POST', pos: new THREE.Vector3(wp.x, 2.05, wp.z + 1.06), rotY: 0, style: 'enamel' });

  // --- First Aid Post (church hall, stucco, sandbagged entrance) on the north side of the High Street
  const fa = FIRST_AID_POST;
  publicBuilding(b, fa.x, fa.z, fa.w, fa.d, 'stucco', rng, 'south');
  sandbagWall(b, fa.x - 2.6, fa.x + 2.6, fa.z + fa.d / 2 + 0.9, 1.6, rng);
  out.signs.push({ text: 'FIRST AID POST', pos: new THREE.Vector3(fa.x, 3.1, fa.z + fa.d / 2 + 0.03), rotY: 0, style: 'enamel' });
  // --- ARP depot (stores) on the south side of the High Street
  const dp = DEPOT;
  publicBuilding(b, dp.x, dp.z, dp.w, dp.d, 'brick', rng, 'north');
  out.signs.push({ text: 'A.R.P. DEPOT', pos: new THREE.Vector3(dp.x, 2.9, dp.z - dp.d / 2 - 0.03), rotY: Math.PI, style: 'enamel' });
  // --- High Street shop terraces (both sides)
  for (const [x0, x1] of SHOPS_NORTH) shopTerrace(b, x0, x1, HIGH_STREET_Z - 3.8 - PAVEMENT, -1, rng);
  for (const [x0, x1] of SHOPS_SOUTH) shopTerrace(b, x0, x1, HIGH_STREET_Z + 3.8 + PAVEMENT, 1, rng);
  // --- station building on the High Street
  const st = STATION;
  stationBuilding(b, st.x, st.z, st.w, st.d);
  out.signs.push({ text: 'MORLEY ROAD', sub: 'STATION · PUBLIC SHELTER', pos: new THREE.Vector3(st.x, 3.9, st.z + st.d / 2 + 0.05), rotY: 0, style: 'enamel' });
  out.signs.push({ text: 'S', sub: 'SHELTER →', pos: new THREE.Vector3(DOCK_LANE_X - 2.4, 2.4, -FRONT - 0.4), rotY: Math.PI / 2, style: 'shelter' });
  out.signs.push({ text: 'S', sub: 'SHELTER ↑', pos: new THREE.Vector3(DOCK_LANE_X + 2.4, 2.4, HIGH_STREET_Z + 6.5), rotY: -Math.PI / 2, style: 'shelter' });
  out.signs.push({ text: 'CABLE ROW', sub: 'E.14', pos: new THREE.Vector3(DOCK_LANE_X - DOCK_LANE_HALF - 0.32, 2.6, -FRONT - 2), rotY: Math.PI / 2, style: 'enamel' });
  return out;
}

/** A wall of filled sandbags (instanced later as boxes with the hessian texture). */
export function sandbagWall(b: Builder, x0: number, x1: number, z: number, h: number, rng: Rng): void {
  const courses = Math.round(h / 0.15);
  for (let c = 0; c < courses; c++) {
    const off = c % 2 ? 0.24 : 0;
    for (let x = x0 + off; x < x1 - 0.1; x += 0.48) {
      const g = new THREE.BoxGeometry(0.46, 0.14, 0.3, 2, 1, 1);
      const p = g.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < p.count; i++) {
        const ux = (2 * p.getX(i)) / 0.46;
        p.setY(i, p.getY(i) * (1 - Math.abs(ux) ** 3 * 0.35));
      }
      g.computeVertexNormals();
      b.geo('sandbag', g, new THREE.Matrix4().makeRotationY((rng.next() - 0.5) * 0.08).setPosition(x + 0.23, 0.12 + 0.07 + c * 0.145, z + (rng.next() - 0.5) * 0.04));
    }
  }
  b.collider(x0, x1, 0, h + 0.12, z - 0.16, z + 0.16);
}

function publicBuilding(b: Builder, x: number, z: number, w: number, d: number, mat: string, rng: Rng, facing: 'north' | 'south'): void {
  const h = 4.2;
  const hw = w / 2;
  const hd = d / 2;
  const doorFront = facing === 'north' ? z - hd : z + hd; // faces the street
  const door = { x0: x - 0.9, x1: x + 0.9, y0: 0.12, y1: 2.6 };
  const wins = [-hw + 1.4, -hw + 3.6, hw - 3.6, hw - 1.4].filter((ox) => Math.abs(ox) > 1.7).map((ox) => ({ x0: x + ox - 0.6, x1: x + ox + 0.6, y0: 1.0, y1: 2.9 }));
  const zf0 = facing === 'north' ? doorFront : doorFront - 0.35;
  b.wall(mat, x - hw, x + hw, 0, h, zf0, zf0 + 0.35, [door, ...wins], true);
  for (const r of wins) {
    b.box('frame', r.x0, r.x1, r.y0, r.y1, zf0 + 0.15, zf0 + 0.2);
    b.collider(r.x0, r.x1, r.y0, r.y1, zf0, zf0 + 0.35);
  }
  const zb = facing === 'north' ? z + hd - 0.35 : z - hd;
  b.box(mat, x - hw, x + hw, 0, h, zb, zb + 0.35, true);
  b.box(mat, x - hw, x - hw + 0.35, 0, h, z - hd, z + hd, true);
  b.box(mat, x + hw - 0.35, x + hw, 0, h, z - hd, z + hd, true);
  b.box('slate', x - hw - 0.2, x + hw + 0.2, h, h + 0.25, z - hd - 0.2, z + hd + 0.2, true);
  b.box('stucco', x - hw, x + hw, h - 0.4, h, (facing === 'north' ? zf0 : zf0 + 0.35) - 0.05, (facing === 'north' ? zf0 : zf0 + 0.35) + 0.05);
  void rng;
}

/**
 * Three-storey shop terrace: shopfronts with taped or boarded glass, fascias, upper sash windows,
 * parapet with chimney stacks. `s` = −1 for the north side (front faces +z), +1 for the south side.
 */
function shopTerrace(b: Builder, x0: number, x1: number, zFront: number, s: number, rng: Rng): void {
  const depth = 9;
  const h = 9.2;
  const unit = 6;
  const z0 = zFront; // front face
  const zIn = zFront + s * -0.35; // inner face of the front wall... (s=-1: inward is −z)
  const zb = zFront - s * -depth;
  void zIn;
  const fz0 = s < 0 ? z0 - 0.35 : z0;
  const fz1 = s < 0 ? z0 : z0 + 0.35;
  for (let x = x0; x < x1 - 0.5; x += unit) {
    const xa = x;
    const xb = Math.min(x1, x + unit);
    const shop = { x0: xa + 0.6, x1: xb - 1.7, y0: 0.5, y1: 3.0 };
    const door = { x0: xb - 1.5, x1: xb - 0.5, y0: 0.12, y1: 2.6 };
    const w1 = { x0: xa + 0.9, x1: xa + 2.1, y0: 4.6, y1: 6.2 };
    const w2 = { x0: xb - 2.1, x1: xb - 0.9, y0: 4.6, y1: 6.2 };
    const w3 = { x0: xa + 0.9, x1: xa + 2.1, y0: 7.2, y1: 8.4 };
    const w4 = { x0: xb - 2.1, x1: xb - 0.9, y0: 7.2, y1: 8.4 };
    b.wall('brick', xa, xb, 0, h, fz0, fz1, [shop, door, w1, w2, w3, w4], true);
    const fasZ = s < 0 ? z0 + 0.12 : z0 - 0.12;
    b.box('frame', xa + 0.3, xb - 0.3, 3.05, 3.65, Math.min(fasZ, z0), Math.max(fasZ, z0)); // fascia board
    const boarded = rng.chance(0.35);
    const gz = s < 0 ? z0 - 0.2 : z0 + 0.2;
    b.box(boarded ? 'timber' : 'glass', shop.x0, shop.x1, shop.y0, shop.y1, Math.min(gz, gz + 0.03), Math.max(gz, gz + 0.03));
    b.collider(shop.x0, shop.x1, shop.y0 - 0.4, shop.y1, fz0, fz1);
    b.box('frame', door.x0, door.x1, door.y0, door.y1, Math.min(gz, gz + 0.05), Math.max(gz, gz + 0.05), true);
    b.box('stucco', shop.x0 - 0.1, shop.x1 + 0.1, 0.12, 0.5, Math.min(z0, z0 - s * -0.08), Math.max(z0, z0 - s * -0.08));
    for (const r of [w1, w2, w3, w4]) {
      b.box('glass', r.x0, r.x1, r.y0, r.y1, Math.min(gz, gz + 0.02), Math.max(gz, gz + 0.02));
      b.box('frame', r.x0, r.x1, (r.y0 + r.y1) / 2 - 0.03, (r.y0 + r.y1) / 2 + 0.03, Math.min(gz, gz + 0.05), Math.max(gz, gz + 0.05));
      b.collider(r.x0, r.x1, r.y0, r.y1, fz0, fz1);
    }
    // chimney stack on the parapet
    const cz = (z0 + zb) / 2;
    b.box('brick', xb - 0.5, xb + 0.5, h, h + 1.4, cz - 0.4, cz + 0.4);
  }
  // party/end walls, back wall, roof slab and parapet coping
  b.box('brick', x0, x0 + 0.3, 0, h, Math.min(z0, zb), Math.max(z0, zb), true);
  b.box('brick', x1 - 0.3, x1, 0, h, Math.min(z0, zb), Math.max(z0, zb), true);
  b.box('brick', x0, x1, 0, h, Math.min(zb, zb + s * 0.3), Math.max(zb, zb + s * 0.3), true);
  b.box('slate', x0, x1, h - 0.3, h - 0.05, Math.min(z0, zb), Math.max(z0, zb));
  b.box('stucco', x0, x1, h, h + 0.25, Math.min(fz0, fz1) - 0.05, Math.max(fz0, fz1) + 0.05);
}

function stationBuilding(b: Builder, x: number, z: number, w: number, d: number): void {
  const h = 5.0;
  const hw = w / 2;
  const hd = d / 2;
  const front = z + hd; // faces south onto the High Street
  // tiled facade with three arched-height openings (the middle one is the entrance)
  const openings = [-3.4, 0, 3.4].map((ox) => ({ x0: x + ox - 1.1, x1: x + ox + 1.1, y0: 0.12, y1: 3.2 }));
  b.wall('tile', x - hw, x + hw, 0, h, front - 0.4, front, openings, true);
  // the side openings are gated (closed shutters)
  for (const o of [openings[0], openings[2]]) {
    b.box('iron', o.x0, o.x1, o.y0, o.y1, front - 0.3, front - 0.25, true);
  }
  b.box('stucco', x - hw - 0.1, x + hw + 0.1, h - 0.6, h, front - 0.45, front + 0.12);
  b.box('tile', x - hw, x - hw + 0.4, 0, h, z - hd, front, true);
  b.box('tile', x + hw - 0.4, x + hw, 0, h, z - hd, front, true);
  b.box('tile', x - hw, x + hw, 0, h, z - hd, z - hd + 0.4, true);
  b.box('slate', x - hw - 0.2, x + hw + 0.2, h, h + 0.3, z - hd - 0.2, front + 0.2, true);
  // booking hall floor around the stairwell (stairs are built by the tube builder)
  // (the stair opening is 3.8 m long so there is head clearance where the stairs pass under the floor)
  b.box('platform', x - hw + 0.4, x + hw - 0.4, -0.2, 0.12, z - hd + 0.4, z - 2.2, true);
  b.box('platform', x - hw + 0.4, x - 1.3, -0.2, 0.12, z - 2.2, front - 0.4, true);
  b.box('platform', x + 1.3, x + hw - 0.4, -0.2, 0.12, z - 2.2, front - 0.4, true);
  b.box('platform', x - 1.3, x + 1.3, -0.2, 0.12, z + 1.6, front - 0.4, true);
  b.box('stucco', x - hw + 0.4, x + hw - 0.4, h - 0.1, h - 0.02, z - hd + 0.4, front - 0.4);
}

/** Painted / enamel sign texture. */
export function signTexture(text: string, sub: string | undefined, style: 'shelter' | 'enamel' | 'painted', track: <T extends { dispose(): void }>(x: T) => T): THREE.CanvasTexture {
  return track(
    canvasTexture(512, 192, (c) => {
      const bg = style === 'shelter' ? '#f2efe6' : style === 'enamel' ? '#1d3e6e' : '#e8e3d4';
      const fg = style === 'shelter' ? '#151515' : style === 'enamel' ? '#f2efe6' : '#1b1b1b';
      c.fillStyle = bg;
      c.fillRect(0, 0, 512, 192);
      c.strokeStyle = fg;
      c.lineWidth = 6;
      c.strokeRect(8, 8, 496, 176);
      c.fillStyle = fg;
      c.textAlign = 'center';
      c.font = `bold ${style === 'shelter' ? 110 : 60}px Gill Sans, Helvetica, Arial, sans-serif`;
      c.fillText(text, 256, sub ? (style === 'shelter' ? 112 : 92) : 118);
      if (sub) {
        c.font = 'bold 34px Gill Sans, Helvetica, Arial, sans-serif';
        c.fillText(sub, 256, 162);
      }
      // grime
      for (let i = 0; i < 900; i++) {
        c.fillStyle = `rgba(40,35,30,${Math.random() * 0.12})`;
        c.fillRect(Math.random() * 512, Math.random() * 192, 1 + Math.random() * 3, 1 + Math.random() * 3);
      }
    }),
  );
}
