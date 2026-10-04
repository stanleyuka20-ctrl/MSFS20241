import * as THREE from 'three';
import { Builder } from '../common/builder';
import { block, type BlockSpec } from '../common/urban';
import { Rng } from '../../core/Random';
import { ROAD_HALF, FRONT, FLOOR_H, FLOORS, STREET_X0, STREET_X1, CROSS_X, CROSS_HALF, NO12, WING_STAIR, LENZ_FLAT, CELLAR, PUMP, LITFASS, SCHOOL, TRAM_WRECK, TRUCK, GAP, FIREWALL, BOUNDS } from './layout';

/** Material key → texture set. Keys without a set use plain materials made by the runtime. */
export const BERLIN_SETS: Record<string, string> = {
  wall: 'berlin_render_facade',
  wallGround: 'berlin_render_facade',
  trim: 'render_stucco',
  frame: 'painted_wood',
  slab: 'concrete_board',
  wallpaper: 'interior_wallpaper',
  roof: 'roof_tiles',
  firewall: 'brick_french',
  iron: 'pump_iron_green',
  shutter: 'corrugated_iron',
  charred: 'soot_scorch',
  rubble: 'rubble_brick_plaster',
  cobble: 'berlin_cobbles',
  walk: 'berlin_sidewalk',
  kerb: 'pavement_flags',
  rail: 'rusty_steel',
  stair: 'terrazzo_stair',
  whitewash: 'cellar_whitewash',
  distemper: 'interior_paint_distemper',
  parquet: 'parquet_oak',
  timber: 'wood_beam',
  planks: 'wood_planks',
  schoolBrick: 'london_stock_brick',
  earth: 'mud_wet',
  metal: 'rusty_steel',
  crate: 'crate_wood',
};

export interface BerlinWorld {
  builders: Builder[];
  /** Planks that bridge the broken flight (hidden until placed). */
  planks: Builder;
  /** Walkable floor of the broken flight once planked (collision mesh). */
  plankRamp: THREE.BufferGeometry;
  lamps: THREE.Vector3[];
  chalkWalls: { pos: THREE.Vector3; rotY: number; w: number; h: number }[];
  /** World positions of interest. */
  at: Record<string, THREE.Vector3>;
}

/** Build the whole street. Builders are in world space (frames set per element). */
export function buildBerlin(tiles: Record<string, number>): BerlinWorld {
  const rng = new Rng(1945);
  const B = (): Builder => new Builder(tiles, BERLIN_SETS);
  const north = B();
  const south = B();
  const street = B();
  const yard = B();
  const interior = B();
  const props = B();
  const planks = B();
  const at: Record<string, THREE.Vector3> = {};
  const lamps: THREE.Vector3[] = [];
  const chalkWalls: BerlinWorld['chalkWalls'] = [];
  const V = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);

  // ------------------------------------------------------------------ north side
  const placeN = (spec: BlockSpec): void => {
    north.setFrame(0, -FRONT, 0);
    block(north, spec, rng);
  };
  // No. 12 front building with the carriage gateway; the west part has come down
  placeN({ x0: NO12.x0, x1: NO12.x1, depth: NO12.frontDepth, floors: FLOORS, floorH: FLOOR_H, ground: 'windows', gate: NO12.gate, collapsed: [{ x0: NO12.collapsed.x0, x1: NO12.collapsed.x1, top: FLOOR_H }], blown: 0.55, balconies: true, rear: true });
  // No. 10: burnt-out shell, with a section fallen into the street (the bucket chain clears it)
  placeN({ x0: -36, x1: NO12.x0, depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', burnt: true, collapsed: [{ x0: -28, x1: -19, top: 3.5 }], firewall: { left: true } });
  // No. 14 and the corner house No. 16: standing, windows blown, white sheets hung out
  placeN({ x0: NO12.x1, x1: 36, depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', blown: 0.7, balconies: true });
  placeN({ x0: 36, x1: CROSS_X - CROSS_HALF - 0.2, depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', blown: 0.5, balconies: true, firewall: { right: true } });
  // across Ackerweg (scenery)
  placeN({ x0: CROSS_X + CROSS_HALF + 0.2, x1: CROSS_X + 30, depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', blown: 0.6 });

  // the yard of No. 12: side wing (east), rear building (north), the neighbour's firewall (west)
  north.setFrame(NO12.wing.x0, (NO12.yard.z0 + NO12.yard.z1) / 2, -Math.PI / 2);
  const wingHalf = (NO12.yard.z0 - NO12.yard.z1) / 2;
  const wz = (z: number): number => z - (NO12.yard.z0 + NO12.yard.z1) / 2; // world z → wing local x
  block(north, {
    x0: -wingHalf,
    x1: wingHalf,
    depth: NO12.wing.x1 - NO12.wing.x0,
    floors: FLOORS,
    floorH: FLOOR_H,
    ground: 'windows',
    door: { x0: wz(WING_STAIR.doorZ) - 0.55, x1: wz(WING_STAIR.doorZ) + 0.55 },
    blown: 0.4,
    roof: 'pitched',
    noVoidRanges: [0, 1, 2, 3, 4].map((f) => ({ x0: wz(WING_STAIR.z0) - 0.35, x1: wz(WING_STAIR.z1) + 0.35, floor: f })),
  }, rng);
  north.setFrame(0, NO12.rear.z0, 0);
  block(north, { x0: NO12.x0, x1: NO12.x1, depth: NO12.rear.z0 - NO12.rear.z1, floors: 4, floorH: FLOOR_H, ground: 'windows', blown: 0.3, roof: 'pitched' }, rng);
  north.setFrame(0, 0, 0);
  north.box('firewall', NO12.x0 - 0.4, NO12.x0, 0, FLOOR_H * 4.6, NO12.rear.z0, NO12.yard.z0, true);
  // the neighbours' firewall west of the bombed gap (chalk message wall)
  north.box('firewall', FIREWALL.x - 0.4, FIREWALL.x, 0, FLOOR_H * FLOORS, FIREWALL.z0, FIREWALL.z1 - 0.5, true);
  chalkWalls.push({ pos: V(FIREWALL.x - 0.41, 1.7, -FRONT - 4.5), rotY: -Math.PI / 2, w: 6.5, h: 2.4 });
  chalkWalls.push({ pos: V(-20, 1.6, -FRONT + 0.02), rotY: 0, w: 3.6, h: 1.4 });
  chalkWalls.push({ pos: V(NO12.x0 + 3.0, 1.0, -FRONT + 0.02), rotY: 0, w: 2.4, h: 1.0 });

  // backdrop: burnt rear buildings behind the bombed gap, ruins beyond the barricade at the west end
  north.setFrame(0, -FRONT - 22, 0);
  block(north, { x0: GAP.x0 - 6, x1: GAP.x1, depth: 10, floors: 4, floorH: FLOOR_H, ground: 'windows', burnt: true, collapsed: [{ x0: -52, x1: -44, top: 5 }] }, rng);
  placeN({ x0: STREET_X0 - 40, x1: STREET_X0 - 2, depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', burnt: true, collapsed: [{ x0: -90, x1: -78, top: 6 }] });
  // ------------------------------------------------------------------ south side (frame rotated: local x = −world x)
  const placeS = (wx0: number, wx1: number, spec: Omit<BlockSpec, 'x0' | 'x1'>): void => {
    south.setFrame(0, FRONT, Math.PI);
    block(south, { ...spec, x0: -wx1, x1: -wx0 }, rng);
  };
  placeS(STREET_X0 - 40, STREET_X0 + 3.8, { depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', burnt: true });
  placeS(STREET_X0 + 4, -40, { depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', burnt: true, collapsed: [{ x0: 44, x1: 58, top: 2.6 }] });
  placeS(-40, SCHOOL.x0 - 0.2, { depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', burnt: true });
  placeS(SCHOOL.x1 + 0.2, CROSS_X - CROSS_HALF - 0.2, { depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', blown: 0.6, balconies: true });
  placeS(CROSS_X + CROSS_HALF + 0.2, CROSS_X + 30, { depth: 12, floors: FLOORS, floorH: FLOOR_H, ground: 'shops', blown: 0.5 });
  // the school (district ration-card office): red-brown brick, four tall storeys, central door
  south.setFrame(0, FRONT, Math.PI);
  block(south, { x0: -SCHOOL.x1, x1: -SCHOOL.x0, depth: SCHOOL.depth, floors: 4, floorH: 4.1, ground: 'windows', door: { x0: -SCHOOL.door.x1, x1: -SCHOOL.door.x0 }, blown: 0.35, roof: 'pitched', bay: 3.4, noVoidRanges: [{ x0: -7.2, x1: 7.2, floor: 0 }], keys: { wall: 'schoolBrick', wallGround: 'schoolBrick' } }, rng);

  // ------------------------------------------------------------------ streets
  const y0 = -0.3;
  street.box('cobble', STREET_X0 - 6, STREET_X1 + 10, y0, 0.0, -ROAD_HALF, ROAD_HALF, true);
  // tram tracks: grooved rails flush with the setts, both directions
  for (const tz of [-1.6, 1.6]) for (const g of [-0.72, 0.72]) street.box('rail', STREET_X0 - 6, STREET_X1 + 10, -0.02, 0.012, tz + g - 0.035, tz + g + 0.035);
  for (const s of [-1, 1]) {
    const spans: [number, number][] = [[STREET_X0 - 6, CROSS_X - CROSS_HALF], [CROSS_X + CROSS_HALF, STREET_X1 + 10]];
    for (const [xa, xb] of spans) {
      const zk = s * ROAD_HALF;
      const zf = s * FRONT;
      street.box('kerb', xa, xb, y0, 0.14, Math.min(zk, zk + s * 0.3), Math.max(zk, zk + s * 0.3), true);
      street.box('walk', xa, xb, y0, 0.13, Math.min(zk + s * 0.3, zf), Math.max(zk + s * 0.3, zf), true);
    }
  }
  // Ackerweg crossing south and north
  street.box('cobble', CROSS_X - CROSS_HALF, CROSS_X + CROSS_HALF, y0, 0.0, BOUNDS.minZ - 20, BOUNDS.maxZ + 20, true);
  // yard: old setts and beaten earth; gateway passage
  const hole = { x0: CELLAR.stairX - 0.95, x1: CELLAR.stairX + 0.95, z0: NO12.yard.z1, z1: CELLAR.stairZ0 + 0.3 };
  yard.box('cobble', NO12.x0, hole.x0, y0, 0.05, NO12.yard.z1, NO12.yard.z0, true);
  yard.box('cobble', hole.x1, NO12.wing.x0, y0, 0.05, NO12.yard.z1, NO12.yard.z0, true);
  yard.box('cobble', hole.x0, hole.x1, y0, 0.05, hole.z1, NO12.yard.z0, true);
  yard.box('cobble', NO12.gate.x0, NO12.gate.x1, y0, 0.05, NO12.yard.z0, -FRONT, true);
  // trees: the yard's chestnut, in leaf (May)
  at.chestnut = V(-4.5, 0, -27.5);

  // ------------------------------------------------------------------ the side-wing stairwell (dogleg, terrazzo)
  const S = WING_STAIR;
  const rise = FLOOR_H / 20; // 0.18
  const run = 0.28;
  const landD = S.z1 - (S.z1 - 1.6); // floor landing depth 1.6
  const xMid = (S.x0 + S.x1) / 2;
  interior.setFrame(0, 0, 0);
  const brokenFrom = 1; // floor 1 → 2: the second flight lost its middle steps
  for (let f = 0; f < FLOORS - 1; f++) {
    const fy = f * FLOOR_H;
    // floor landing at the door end (z1 side)
    interior.box('stair', S.x0, S.x1, fy - 0.2, fy + 0.02, S.z1 - landD, S.z1, true);
    // flight A (west half) rising towards −z
    for (let i = 0; i < 10; i++) interior.box('stair', S.x0 + 0.05, xMid, fy + rise * (i + 1) - 0.18, fy + rise * (i + 1), S.z1 - landD - run * (i + 1), S.z1 - landD - run * i, true);
    // half landing
    const hz0 = S.z1 - landD - run * 10;
    interior.box('stair', S.x0, S.x1, fy + rise * 10 - 0.2, fy + rise * 10, S.z0, hz0, true);
    // flight B (east half) rising back towards +z
    for (let i = 0; i < 10; i++) {
      if (f === brokenFrom && i >= 3 && i <= 7) continue;
      interior.box('stair', xMid, S.x1 - 0.05, fy + rise * (10 + i + 1) - 0.18, fy + rise * (10 + i + 1), hz0 + run * i, hz0 + run * (i + 1), true);
    }
    // iron balustrade between the flights
    interior.box('iron', xMid - 0.02, xMid + 0.02, fy + 0.9, fy + 1.0 + FLOOR_H / 2, hz0, S.z1 - landD);
  }
  // top landing
  interior.box('stair', S.x0, S.x1, (FLOORS - 1) * FLOOR_H - 0.2, (FLOORS - 1) * FLOOR_H + 0.02, S.z1 - 1.6, S.z1, true);
  // stairwell walls (inner), distemper paint
  interior.box('distemper', S.x0 - 0.02, S.x0, 0, FLOORS * FLOOR_H, S.z0, S.z1);
  {
    const fyD = LENZ_FLAT.floor * FLOOR_H;
    const dz = S.z1 - 0.8;
    interior.box('distemper', S.x1, S.x1 + 0.2, 0, fyD, S.z0, S.z1, true);
    interior.box('distemper', S.x1, S.x1 + 0.2, fyD + 2.2, FLOORS * FLOOR_H, S.z0, S.z1, true);
    interior.box('distemper', S.x1, S.x1 + 0.2, fyD, fyD + 2.2, S.z0, dz - 0.5, true);
    interior.box('distemper', S.x1, S.x1 + 0.2, fyD, fyD + 2.2, dz + 0.5, S.z1, true);
  }
  interior.box('distemper', S.x0, S.x1, 0, FLOORS * FLOOR_H, S.z0 - 0.2, S.z0, true);
  interior.box('distemper', S.x0, S.x1, 0, FLOORS * FLOOR_H, S.z1, S.z1 + 0.2, true);
  // flat door on the second-floor landing (east wall), the opening cut by leaving a gap
  const fy2 = LENZ_FLAT.floor * FLOOR_H;
  at.flatDoor = V(S.x1 + 0.1, fy2, S.z1 - 0.8);
  // rubble on the broken flight; a gap the player bridges with planks from the yard
  const hz0b = S.z1 - landD - run * 10;
  const by = brokenFrom * FLOOR_H;
  at.brokenLow = V(xMid + 0.6, by + rise * 13, hz0b + run * 2.5);
  at.brokenHigh = V(xMid + 0.6, by + rise * 18, hz0b + run * 8.5);
  for (let k = 0; k < 6; k++) interior.geo('rubble', new THREE.SphereGeometry(0.25 + rng.next() * 0.2, 6, 4), new THREE.Matrix4().makeTranslation(xMid + 0.3 + rng.next() * 0.8, by + rise * 10 + 0.05, hz0b - 0.2 - rng.next() * 0.9));
  // planks bridging the gap: from the top of step 3 to the bottom of step 9
  const pA = V(xMid + 0.6, by + rise * 13, hz0b + run * 3);
  const pB = V(xMid + 0.6, by + rise * 18, hz0b + run * 8);
  const len = pA.distanceTo(pB) + 0.3;
  const ang = Math.atan2(pB.y - pA.y, pB.z - pA.z);
  for (const dx of [-0.28, 0.0, 0.28]) planks.geo('planks', new THREE.BoxGeometry(0.26, 0.05, len), new THREE.Matrix4().makeRotationX(-ang).setPosition(pA.x + dx, (pA.y + pB.y) / 2 + 0.03, (pA.z + pB.z) / 2));
  const ramp = new THREE.BoxGeometry(0.9, 0.06, len);
  ramp.applyMatrix4(new THREE.Matrix4().makeRotationX(-ang).setPosition(pA.x, (pA.y + pB.y) / 2 + 0.03, (pA.z + pB.z) / 2));

  // ------------------------------------------------------------------ the Lenz flat (second floor, side wing)
  const F = LENZ_FLAT;
  interior.box('parquet', F.x0, F.x1, fy2 - 0.2, fy2 + 0.02, F.z0, F.z1, true);
  interior.box('distemper', F.x0, F.x1, fy2 + FLOOR_H - 0.25, fy2 + FLOOR_H, F.z0, F.z1, true);
  // (the wall towards the landing is the stairwell's east wall, with the door gap)
  interior.box('wallpaper', F.x1 - 0.01, F.x1, fy2, fy2 + FLOOR_H, F.z0, F.z1);
  interior.box('distemper', F.x0, F.x1, fy2, fy2 + FLOOR_H, F.z1 - 0.01, F.z1);
  interior.box('distemper', F.x0, F.x1, fy2, fy2 + FLOOR_H, F.z0, F.z0 + 0.01);
  // furniture: bed, wardrobe (doors open), table and chair, stove; plaster fallen from the ceiling
  // a narrow room: furniture along the walls, a walkway down the middle
  interior.box('timber', F.x1 - 0.9, F.x1 - 0.05, fy2, fy2 + 0.55, F.z0 + 0.2, F.z0 + 2.2, true); // bed
  interior.box('crate', F.x1 - 0.85, F.x1 - 0.1, fy2 + 0.55, fy2 + 0.68, F.z0 + 0.25, F.z0 + 2.15); // bedding
  interior.box('timber', F.x1 - 0.6, F.x1 - 0.05, fy2, fy2 + 2.05, F.z0 + 2.8, F.z0 + 4.0, true); // wardrobe (doors open)
  interior.box('timber', F.x0 + 0.05, F.x0 + 0.75, fy2 + 0.74, fy2 + 0.78, F.z0 + 0.6, F.z0 + 1.6, true); // table by the west wall
  interior.box('metal', F.x1 - 0.65, F.x1 - 0.05, fy2, fy2 + 1.6, F.z1 - 0.95, F.z1 - 0.3, true); // tiled stove (Kachelofen) body
  at.papers = V(F.x1 - 0.32, fy2 + 1.15, F.z0 + 3.4); // tin box on the wardrobe shelf
  lamps.push(V((F.x0 + F.x1) / 2, fy2 + 2.6, (F.z0 + F.z1) / 2));
  for (let k = 0; k < 10; k++) interior.box('distemper', F.x0 + 0.3 + rng.next() * 1.2, F.x0 + 0.5 + rng.next() * 1.4, fy2 + 0.02, fy2 + 0.05, F.z0 + rng.next() * 8, F.z0 + 0.3 + rng.next() * 8);

  // ------------------------------------------------------------------ the cellar (air-raid shelter) under the rear building
  const C = CELLAR;
  const cy = C.floorY;
  // open steps down from the yard (Kellerhals), retaining walls and a low parapet
  const steps = 15;
  const crun = (C.stairZ0 - C.stairZ1) / steps;
  const crise = -cy / steps;
  for (let i = 0; i < steps; i++) yard.box('stair', C.stairX - 0.65, C.stairX + 0.65, -crise * (i + 1) - 0.25, -crise * (i + 1), C.stairZ0 - crun * (i + 1), C.stairZ0 - crun * i, true);
  yard.box('whitewash', C.stairX - 0.95, C.stairX - 0.65, cy - 0.2, 0.9, C.z0, C.stairZ0, true);
  yard.box('whitewash', C.stairX + 0.65, C.stairX + 0.95, cy - 0.2, 0.9, C.z0, C.stairZ0, true);
  yard.box('stair', C.stairX - 0.65, C.stairX + 0.65, cy - 0.25, cy, C.z0, C.stairZ1, true); // bottom landing
  yard.box('whitewash', C.stairX - 0.95, C.stairX + 0.95, -0.65, 0.0, C.z0 - 0.45, C.z0); // lintel under the wall
  // cellar shell: floor, vault-ish ceiling, walls
  interior.box('earth', C.x0, C.x1, cy - 0.3, cy, C.z1, C.z0, true);
  interior.box('whitewash', C.x0, C.x1, -0.62, -0.32, C.z1, C.z0 - 0.45, true);
  interior.box('whitewash', C.x0 - 0.4, C.x0, cy, -0.3, C.z1, C.z0, true);
  interior.box('whitewash', C.x1, C.x1 + 0.4, cy, -0.3, C.z1, C.z0, true);
  interior.box('whitewash', C.x0, C.x1, cy, -0.3, C.z1 - 0.4, C.z1, true);
  interior.box('whitewash', C.x0, C.stairX - 0.65, cy, -0.3, C.z0 - 0.45, C.z0, true);
  interior.box('whitewash', C.stairX + 0.65, C.x1, cy, -0.3, C.z0 - 0.45, C.z0, true);
  // corridor wall with openings to the shelter room (west) and storage compartments (east)
  const corrZ = C.z0 - 2.2;
  interior.box('whitewash', C.x0, C.stairX - 1.2, cy, -0.3, corrZ - 0.25, corrZ, true);
  interior.box('whitewash', C.stairX + 1.2, -1.5, cy, -0.3, corrZ - 0.25, corrZ, true);
  // slatted storage compartments (Kellerverschläge)
  for (let x = -1.2; x < C.x1 - 0.5; x += 1.8) {
    for (let k = 0; k < 9; k++) interior.box('planks', x + k * 0.2, x + k * 0.2 + 0.1, cy, cy + 2.0, corrZ - 0.04, corrZ);
    interior.box('planks', x, x + 0.06, cy, cy + 2.0, C.z1, corrZ);
  }
  // shelter room: benches, bunks, a stove, buckets
  for (const bz of [corrZ - 1.0, C.z1 + 0.6]) interior.box('timber', C.x0 + 0.4, C.stairX - 1.4, cy, cy + 0.45, bz - 0.25, bz + 0.25, true);
  interior.box('timber', C.x0 + 0.1, C.x0 + 1.0, cy, cy + 1.6, C.z1 + 1.4, C.z1 + 3.4, true); // bunk frame
  interior.box('crate', C.x0 + 0.15, C.x0 + 0.95, cy + 0.5, cy + 0.6, C.z1 + 1.45, C.z1 + 3.35);
  interior.box('crate', C.x0 + 0.15, C.x0 + 0.95, cy + 1.4, cy + 1.5, C.z1 + 1.45, C.z1 + 3.35);
  interior.geo('metal', new THREE.CylinderGeometry(0.28, 0.3, 0.8, 12), new THREE.Matrix4().makeTranslation(C.stairX - 2.0, cy + 0.4, C.z1 + 0.9)); // stove
  interior.geo('metal', new THREE.CylinderGeometry(0.05, 0.05, 2.1, 6), new THREE.Matrix4().makeTranslation(C.stairX - 2.0, cy + 1.6, C.z1 + 0.9));
  at.cellarTable = V(C.x0 + 3.2, cy, corrZ - 2.6);
  interior.box('timber', at.cellarTable.x - 0.5, at.cellarTable.x + 0.5, cy + 0.72, cy + 0.76, at.cellarTable.z - 0.4, at.cellarTable.z + 0.4, true);
  lamps.push(V(at.cellarTable.x, cy + 0.95, at.cellarTable.z), V(C.stairX, cy + 2.0, corrZ + 1.0));
  at.cellarStairTop = V(C.stairX, 0.05, C.stairZ0 + 0.6);
  at.cellarBottom = V(C.stairX, cy, C.z0 - 1.0);

  // ------------------------------------------------------------------ ration-card office (school ground floor)
  const sz = FRONT; // school front at z = +FRONT, facing north
  const hz = sz + 0.5;
  interior.box('stair', -7, 7, -0.2, 0.15, hz, hz + 9.0, true); // floor (terrazzo)
  interior.box('distemper', -7, 7, 3.9, 4.1, hz, hz + 9.0, true); // ceiling
  interior.box('distemper', -7.2, -7, 0, 4.1, hz, hz + 9.0, true);
  interior.box('distemper', 7, 7.2, 0, 4.1, hz, hz + 9.0, true);
  interior.box('distemper', -7, 7, 0, 4.1, hz + 9.0, hz + 9.2, true);
  // counter of tables where the clerks issue cards
  interior.box('timber', -4.5, 4.5, 0.72, 0.78, hz + 5.6, hz + 6.4, true);
  for (const x of [-4.2, -1.5, 1.5, 4.2]) interior.box('timber', x - 0.04, x + 0.04, 0.15, 0.72, hz + 5.7, hz + 6.3);
  interior.box('crate', 3.0, 4.2, 0.78, 0.95, hz + 5.8, hz + 6.2); // card boxes
  at.clerk = V(0.8, 0.15, hz + 7.1);
  at.counter = V(0.8, 0.95, hz + 6.0);
  lamps.push(V(0, 3.6, hz + 5));

  // ------------------------------------------------------------------ props: pump, pillar, tram, truck, catenary
  // street pump (cast-iron "Plumpe"): column, ornamental cap, lever, spout, drain
  const P = PUMP;
  props.geo('iron', new THREE.CylinderGeometry(0.17, 0.22, 1.9, 14), new THREE.Matrix4().makeTranslation(P.x, 0.95 + 0.13, P.z));
  props.geo('iron', new THREE.CylinderGeometry(0.26, 0.2, 0.25, 14), new THREE.Matrix4().makeTranslation(P.x, 2.1, P.z));
  props.geo('iron', new THREE.ConeGeometry(0.22, 0.45, 14), new THREE.Matrix4().makeTranslation(P.x, 2.45, P.z));
  props.geo('iron', new THREE.SphereGeometry(0.08, 10, 6), new THREE.Matrix4().makeTranslation(P.x, 2.72, P.z));
  props.geo('iron', new THREE.CylinderGeometry(0.05, 0.06, 0.45, 10).rotateX(Math.PI / 2 - 0.4), new THREE.Matrix4().makeTranslation(P.x, 1.0, P.z - 0.3)); // spout (towards the road)
  props.box('iron', P.x - 0.06, P.x + 0.06, 0.13, 0.15, P.z - 0.9, P.z - 0.4); // drain grate
  props.collider(P.x - 0.25, P.x + 0.25, 0, 2.4, P.z - 0.25, P.z + 0.25);
  at.pump = V(P.x, 1.2, P.z);
  at.pumpSpout = V(P.x, 0.65, P.z - 0.55);
  // Litfaß pillar (posters drawn by the runtime)
  const L = LITFASS;
  props.geo('iron', new THREE.CylinderGeometry(0.7, 0.72, 0.4, 20), new THREE.Matrix4().makeTranslation(L.x, 0.33, L.z));
  props.geo('iron', new THREE.CylinderGeometry(0.78, 0.7, 0.35, 20), new THREE.Matrix4().makeTranslation(L.x, 3.4, L.z));
  props.geo('iron', new THREE.SphereGeometry(0.72, 18, 8, 0, Math.PI * 2, 0, Math.PI / 2), new THREE.Matrix4().makeTranslation(L.x, 3.55, L.z));
  props.collider(L.x - 0.72, L.x + 0.72, 0, 3.6, L.z - 0.72, L.z + 0.72);
  at.litfass = V(L.x, 1.8, L.z);
  // wrecked tram, derailed and burnt, used as a barricade in the fighting
  const T = TRAM_WRECK;
  const tm = new THREE.Matrix4().makeRotationY(T.rot).setPosition(T.x, 0, T.z);
  const tramBox = (k: string, x0: number, x1: number, ya: number, yb: number, z0: number, z1: number): void => {
    const g = new THREE.BoxGeometry(x1 - x0, yb - ya, z1 - z0);
    g.translate((x0 + x1) / 2, (ya + yb) / 2, (z0 + z1) / 2);
    props.geo(k, g, tm.clone());
  };
  props.setFrame(0, 0, 0);
  tramBox('charred', -5.5, 5.5, 0.55, 1.4, -1.1, 1.1);
  for (let x = -5.2; x < 5.2; x += 1.15) {
    tramBox('charred', x, x + 0.18, 1.4, 2.7, -1.1, -1.0);
    tramBox('charred', x, x + 0.18, 1.4, 2.7, 1.0, 1.1);
  }
  tramBox('charred', -5.5, 5.5, 2.7, 3.0, -1.15, 1.15);
  tramBox('metal', -4.5, -2.5, 0.0, 0.6, -0.8, 0.8);
  tramBox('metal', 2.5, 4.5, 0.0, 0.6, -0.8, 0.8);
  tramBox('metal', -0.3, 0.3, 3.0, 3.6, -0.5, 0.5); // pantograph base
  const tc = new THREE.Vector3(T.x, 0, T.z);
  props.collider(tc.x - 5.6, tc.x + 5.6, 0, 3.0, tc.z - 1.6, tc.z + 1.6);
  at.tram = V(T.x, 1.6, T.z);
  // burnt-out lorry
  const K = TRUCK;
  const km = new THREE.Matrix4().makeRotationY(K.rot).setPosition(K.x, 0, K.z);
  const truckBox = (k: string, x0: number, x1: number, ya: number, yb: number, z0: number, z1: number): void => {
    const g = new THREE.BoxGeometry(x1 - x0, yb - ya, z1 - z0);
    g.translate((x0 + x1) / 2, (ya + yb) / 2, (z0 + z1) / 2);
    props.geo(k, g, km.clone());
  };
  truckBox('charred', -3.0, 2.2, 0.55, 0.85, -1.0, 1.0);
  truckBox('charred', 1.0, 2.6, 0.85, 2.2, -1.0, 1.0);
  truckBox('charred', 2.6, 3.5, 0.55, 1.4, -0.8, 0.8);
  for (const wx of [-2.2, 2.4]) for (const s of [-1, 1]) {
    const w = new THREE.CylinderGeometry(0.45, 0.45, 0.25, 12);
    w.rotateX(Math.PI / 2);
    w.translate(wx, 0.4, s * 0.95);
    props.geo('metal', w, km.clone());
  }
  props.collider(K.x - 3.2, K.x + 3.4, 0, 2.2, K.z - 1.3, K.z + 1.3);
  // tram catenary poles along the pavements; most wires down, some hanging
  for (let x = STREET_X0 + 6; x < STREET_X1; x += 28) {
    for (const s of [-1, 1]) {
      const z = s * (ROAD_HALF + 0.6);
      props.geo('iron', new THREE.CylinderGeometry(0.1, 0.14, 7.5, 10), new THREE.Matrix4().makeTranslation(x, 3.75, z));
      props.collider(x - 0.15, x + 0.15, 0, 4, z - 0.15, z + 0.15);
      if (s < 0) {
        // span wire sagging to the ground on one side
        const wire = new THREE.CylinderGeometry(0.012, 0.012, 2 * ROAD_HALF + 2, 4);
        wire.rotateX(Math.PI / 2);
        props.geo('metal', wire, new THREE.Matrix4().makeRotationX(rng.range(0.2, 0.6)).setPosition(x, 4.5, 0));
      }
    }
  }
  // the bombed gap: rubble field
  for (let i = 0; i < 16; i++) {
    const x = rng.range(GAP.x0 + 3, GAP.x1 - 4);
    const z = rng.range(-FRONT - 14, -FRONT - 1);
    const m = new THREE.SphereGeometry(1, 12, 6, 0, Math.PI * 2, 0, Math.PI / 2);
    m.scale(rng.range(1.5, 4), rng.range(0.4, 1.6), rng.range(1.5, 3.5));
    props.geo('rubble', m, new THREE.Matrix4().makeTranslation(x, -0.1, z));
  }

  return { builders: [north, south, street, yard, interior, props], planks, plankRamp: ramp, lamps, chalkWalls, at };
}
