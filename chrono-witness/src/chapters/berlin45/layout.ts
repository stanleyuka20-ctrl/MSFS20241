/**
 * Fictional street in an inner Berlin district, mid-May 1945, a few days after the surrender.
 * Axes: +x east, −z north, y up, street level 0.
 *
 * Lindenhofstraße runs east–west with tram tracks. On the north side stands No. 12, a Wilhelmine
 * tenement: the front building (Vorderhaus) is partly collapsed, a gateway leads to the courtyard
 * (Hof) with a side wing (Seitenflügel) and a rear building (Quergebäude) whose cellar was the air-raid
 * shelter. Across the street is the school used as the district ration-card office. The street pump
 * stands on the south pavement. Ackerweg crosses at the east end.
 */
export const ROAD_HALF = 5.0;
export const WALK = 4.5;
export const FRONT = ROAD_HALF + WALK; // building fronts at z = ±FRONT
export const FLOOR_H = 3.6;
export const FLOORS = 5;
export const EAVES = FLOOR_H * FLOORS + 0.6;

export const STREET_X0 = -64;
export const STREET_X1 = 72;
export const CROSS_X = 66; // Ackerweg centre line
export const CROSS_HALF = 4.0;

/** No. 12: front building, courtyard, side wing, rear building. */
export const NO12 = {
  x0: -12,
  x1: 12,
  frontDepth: 12,
  gate: { x0: -1.8, x1: 1.8, h: 4.2 }, // Durchfahrt (carriage gateway)
  collapsed: { x0: -12, x1: -3.5 }, // west part of the front building is down to the first floor
  yard: { z0: -FRONT - 12, z1: -FRONT - 12 - 14 }, // z −21.5 … −35.5
  wing: { x0: 6.2, x1: 12 }, // side wing on the east of the yard
  rear: { z0: -FRONT - 26, z1: -FRONT - 36 }, // Quergebäude z −35.5 … −45.5
};
/** Side-wing stair door (from the yard) and the Lenz flat on the second floor ("2. Stock"). */
export const WING_STAIR = { x0: NO12.wing.x0 + 0.5, x1: 9.4, z0: -30.6, z1: -24.6, doorZ: -25.4 };
/** The Lenz flat: a long narrow room beside the stairwell on the second floor ("2. Stock"). */
export const LENZ_FLAT = { floor: 2, x0: 9.6, x1: NO12.wing.x1 - 0.45, z0: -30.6, z1: -24.6 };
/** Cellar under the rear building, entered down open steps in the yard (top at stairZ0). */
export const CELLAR = { x0: -10.5, x1: 4.5, z0: -35.95, z1: -44.8, floorY: -2.7, stairX: -6, stairZ0: -31.0, stairZ1: -35.05 };

export const PUMP = { x: 31, z: FRONT - 1.4 }; // street hand pump on the south pavement
export const LITFASS = { x: CROSS_X - CROSS_HALF - 2.4, z: -FRONT + 1.6 }; // advertising pillar
/** School used as the district ration-card office (Kartenstelle), south side. */
export const SCHOOL = { x0: -20, x1: 20, depth: 16, door: { x0: -1.6, x1: 1.6 } };
export const TRAM_WRECK = { x: -40, z: -1.2, rot: 0.18 };
export const TRUCK = { x: 15, z: 2.8, rot: -0.25 };
/** Bombed gap at the west end with a bare firewall (Brandmauer) covered in chalk messages. */
export const GAP = { x0: -64, x1: -36 };
export const FIREWALL = { x: -36.2, z0: -FRONT - 14, z1: -FRONT };
export const UXB = { x: -50, z: -16 }; // unexploded shell found by children in the bombed gap
export const RUBBLE_CHAIN = { x: -24, z: -FRONT + 2.4 }; // bucket chain clearing No. 10's collapse
export const ANCHOR = { x: 48, z: 1.0 };
export const BOUNDS = { minX: -62, maxX: 70, minZ: -46, maxZ: 26 };
