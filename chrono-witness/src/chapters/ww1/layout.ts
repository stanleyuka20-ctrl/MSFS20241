/**
 * Level layout for the fictional Somme sector (October 1916). Shared by the chapter config
 * (checkpoints, markers) and the runtime (terrain carving, trench dressing, NPC placement).
 *
 * Axes: +x east, −z north (towards the German lines), y up. Ground ≈ 0.
 * Dimensions follow the reconstruction values in docs/history/ww1_somme_1916.md
 * (floor ~1.1–1.3 m wide for playability, 2.0–2.3 m deep plus parapet).
 */
export type Revet = 'planks' | 'sandbags' | 'corrugated' | 'hurdle' | 'bare' | 'mixed';

export interface TrenchDef {
  id: string;
  name: string;
  points: [number, number][];
  depth: number;
  floorWidth: number;
  /** Horizontal extent of the wall slope (smaller = more vertical). */
  batter: number;
  revet: Revet;
  /** Parapet mound height on the north (enemy) side and parados on the south. */
  parapet: number;
  parados: number;
  fireStep: boolean;
  duckboards: boolean;
  /** Irregular / shell-hole character (0..1). */
  rough: number;
  /** Depth taper at the start/end (metres over which depth goes to 0), for ramps. */
  rampStart?: number;
  rampEnd?: number;
}

/**
 * Crenellated fire-trench trace: straight bays, with the trench detouring rearward (south)
 * around each traverse. Traverse centres are explicit so junctions, dugout entrances and other
 * gameplay points always fall inside a bay.
 */
function crenellated(x0: number, x1: number, z: number, traverses: number[], trav: number, jog: number): [number, number][] {
  const pts: [number, number][] = [[x0, z]];
  for (const c of traverses) {
    pts.push([c - trav / 2, z]);
    pts.push([c - trav / 2 + 0.8, z + jog]);
    pts.push([c + trav / 2 - 0.8, z + jog]);
    pts.push([c + trav / 2, z]);
  }
  pts.push([x1, z]);
  return pts;
}

export const FRONT_Z = -60;
export const SUPPORT_Z = 4;

export const TRENCHES: TrenchDef[] = [
  {
    id: 'front_w',
    name: 'Cheapside Trench (front line)',
    points: crenellated(-74, 6, FRONT_Z, [-64, -53, -40, -31, -19, -6], 4, 3.6),
    depth: 2.1,
    floorWidth: 1.15,
    batter: 0.22,
    revet: 'mixed',
    parapet: 0.75,
    parados: 0.45,
    fireStep: true,
    duckboards: true,
    rough: 0.15,
  },
  {
    id: 'front_e',
    name: 'Cheapside Trench (linked shell holes)',
    points: [[6, FRONT_Z], [11, FRONT_Z - 0.8], [16, FRONT_Z + 0.6], [21, FRONT_Z - 0.5], [24, FRONT_Z], [29, FRONT_Z + 1.2], [35, FRONT_Z - 0.6], [41, FRONT_Z + 0.4], [48, FRONT_Z - 1], [56, FRONT_Z], [66, FRONT_Z + 0.8], [76, FRONT_Z]],
    depth: 1.85,
    floorWidth: 1.4,
    batter: 0.45,
    revet: 'bare',
    parapet: 0.55,
    parados: 0.3,
    fireStep: true,
    duckboards: false,
    rough: 0.85,
  },
  {
    id: 'support',
    name: 'Fleet Street (support line)',
    points: crenellated(-66, 62, SUPPORT_Z, [-58, -45, -36, -15, 13, 25, 41, 52], 3.5, 2.6),
    depth: 2.15,
    floorWidth: 1.25,
    batter: 0.2,
    revet: 'mixed',
    parapet: 0.6,
    parados: 0.5,
    fireStep: true,
    duckboards: true,
    rough: 0.1,
  },
  {
    id: 'pall_mall',
    name: 'Pall Mall (communication trench)',
    points: [[-6, 4.5], [-6, -2], [-9, -8], [-7, -14], [-10, -20], [-8.4, -26], [-10.6, -31], [-9.6, -38], [-12, -44], [-10, -50], [-12, -56], [-12.5, -60]],
    depth: 2.05,
    floorWidth: 1.15,
    batter: 0.22,
    revet: 'planks',
    parapet: 0.35,
    parados: 0.35,
    fireStep: false,
    duckboards: true,
    rough: 0.1,
  },
  {
    id: 'sap',
    name: 'Tottenham Sap',
    points: [[-10.4, -30.5], [-3, -29.2], [6, -30.8], [15, -29.4], [22, -30.4], [28, -30]],
    depth: 1.95,
    floorWidth: 1.05,
    batter: 0.3,
    revet: 'hurdle',
    parapet: 0.35,
    parados: 0.25,
    fireStep: false,
    duckboards: true,
    rough: 0.3,
  },
  {
    id: 'old_boot_s',
    name: 'Old Boot Alley (disused German trench)',
    points: [[32, 4.5], [34, -4], [30, -12], [33, -20], [28.5, -27.5], [28, -30], [29.2, -36.6]],
    depth: 2.2,
    floorWidth: 1.3,
    batter: 0.5,
    revet: 'bare',
    parapet: 0.25,
    parados: 0.55,
    fireStep: false,
    duckboards: true,
    rough: 0.6,
  },
  {
    id: 'old_boot_n',
    name: 'Old Boot Alley (north)',
    points: [[27.4, -48.2], [30, -53], [27, -57], [24, -60]],
    depth: 2.1,
    floorWidth: 1.3,
    batter: 0.45,
    revet: 'bare',
    parapet: 0.25,
    parados: 0.45,
    fireStep: false,
    duckboards: false,
    rough: 0.6,
  },
  {
    id: 'haymarket',
    name: 'Haymarket (communication trench to the rear)',
    points: [[2, 4.5], [3, 10], [0, 16], [2, 22], [-1, 28], [1, 34], [0, 43]],
    depth: 2.0,
    floorWidth: 1.2,
    batter: 0.22,
    revet: 'corrugated',
    parapet: 0.3,
    parados: 0.3,
    fireStep: false,
    duckboards: true,
    rough: 0.1,
    rampEnd: 9,
  },
];

/** Cut-and-cover shelters / dugouts: an entrance notch from the trench wall into a covered room. */
export interface DugoutDef {
  id: string;
  name: string;
  /** Room centre (floor), size along x/z, floor depth below local ground. */
  room: [number, number];
  size: [number, number];
  depth: number;
  /** Entrance passage from the trench floor to the room: start, end. */
  entrance: [[number, number], [number, number]];
  sign?: string;
}

export const DUGOUTS: DugoutDef[] = [
  { id: 'coy_hq', name: 'Company HQ dugout', room: [-4, 8.6], size: [3.6, 2.8], depth: 2.55, entrance: [[-4, 4.9], [-4, 7.2]], sign: 'B COY H.Q.' },
  { id: 'signals', name: 'Signals dugout', room: [8, 8.4], size: [3.0, 2.6], depth: 2.5, entrance: [[8, 4.9], [8, 7.1]], sign: 'SIGNALS' },
  { id: 'rap', name: 'Regimental Aid Post', room: [18, 9.0], size: [4.6, 3.2], depth: 2.6, entrance: [[18, 4.9], [18, 7.4]], sign: 'R.A.P.' },
  { id: 'shelter', name: 'Pall Mall shelter', room: [-4.6, -26.3], size: [3.2, 2.6], depth: 2.55, entrance: [[-7.6, -26.2], [-6.2, -26.3]] },
  { id: 'front_hq', name: 'Front-line company dugout', room: [-25.5, -56.3], size: [3.4, 2.6], depth: 2.5, entrance: [[-25.5, -59.4], [-25.5, -57.6]], sign: 'COY H.Q.' },
];

export interface CraterDef {
  x: number;
  z: number;
  r: number;
  depth: number;
  water?: number; // water level relative to ground (negative)
}

export const CRATERS: CraterDef[] = [
  // the crater that destroyed Old Boot Alley (crossed on a duckboard bridge)
  { x: 28.2, z: -42.4, r: 6.2, depth: 3.1, water: -2.4 },
];

/** Crossing over the big crater: ladder out of the trench, bridge, steps down. */
export const CRATER_CROSSING = {
  ladderBottom: [29.3, -36.9] as [number, number],
  /** Second ladder at the north end (start of Old Boot Alley north), climber faces south. */
  ladderNorth: [27.42, -47.95] as [number, number],
  bridgeFrom: [28.9, -37.6] as [number, number],
  bridgeTo: [27.6, -47.4] as [number, number],
};

/** Section of Pall Mall that collapses in the bombardment. */
export const COLLAPSE = { from: [-10.6, -33.5] as [number, number], to: [-10.2, -40.5] as [number, number] };
export const BARRAGE_TRIGGER: [number, number] = [-9.4, -21.5];
export const FLOODED: { from: [number, number]; to: [number, number]; level: number } = { from: [31, -10], to: [31, -22], level: 0.32 };
export const OLD_BOOT_BLOCK: [number, number] = [33.2, -1.5];

export const ANCHOR: [number, number] = [-24, SUPPORT_Z];

/** Ruined buildings: footprint centre, size, rotation, storeys, damage 0..1, material. */
export interface BuildingDef {
  id: string;
  x: number;
  z: number;
  w: number;
  d: number;
  rot: number;
  height: number;
  damage: number;
  material: 'brick' | 'plaster';
  cellar?: boolean;
}

export const VILLAGE_ROAD_Z = 50;
export const BUILDINGS: BuildingDef[] = [
  { id: 'farmhouse', x: -25, z: 79.5, w: 14, d: 6.5, rot: 0, height: 5.6, damage: 0.65, material: 'brick', cellar: true },
  { id: 'barn', x: -33, z: 69, w: 6, d: 13, rot: 0, height: 6.2, damage: 0.75, material: 'plaster' },
  { id: 'h1', x: -52, z: 58, w: 9, d: 6, rot: 0.05, height: 6, damage: 0.8, material: 'brick' },
  { id: 'h2', x: -42, z: 41, w: 8, d: 6, rot: -0.04, height: 5.5, damage: 0.7, material: 'plaster' },
  { id: 'h3', x: 14, z: 59, w: 10, d: 6.5, rot: 0.02, height: 6.4, damage: 0.6, material: 'brick' },
  { id: 'h4', x: 27, z: 58.5, w: 8, d: 6, rot: -0.03, height: 5.4, damage: 0.85, material: 'plaster' },
  { id: 'h5', x: 22, z: 41.5, w: 9, d: 5.5, rot: 0.06, height: 5.8, damage: 0.75, material: 'brick' },
  { id: 'h6', x: 42, z: 42, w: 7, d: 6, rot: 0, height: 5, damage: 0.9, material: 'brick' },
  { id: 'church', x: 34, z: 74, w: 7, d: 16, rot: 0.02, height: 9.5, damage: 0.7, material: 'brick' },
];

export const FARM = {
  courtyard: [-24, 68] as [number, number],
  cellarStairTop: [-17.2, 77.4] as [number, number],
  cellarStairBottom: [-20.6, 77.4] as [number, number],
  cellarRoom: [-24.5, 79.6] as [number, number],
  cellarSize: [7.2, 3.6] as [number, number],
  cellarDepth: 2.6,
  dump: [-32.2, 66] as [number, number],
  gate: [-22, 61.5] as [number, number],
};

/** Playable bounds (soft walls with a message). */
export const BOUNDS = { minX: -72, maxX: 72, minZ: -63.2, maxZ: 96 };
/** Ground between the support and front lines is too exposed to walk on (except the crater crossing). */
export const NO_GROUND_ZONE = { minZ: -62, maxZ: 6 };
