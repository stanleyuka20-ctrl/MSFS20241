/**
 * Fictional East End street near the docks, a night in late September 1940 (during the 57
 * consecutive nights of raids that began on 7 September). Axes: +x east, −z north, y up, ground 0.
 *
 * Cable Row runs east–west. Terraces of two-storey houses line both sides, with back yards and an
 * alley behind them. Dock Lane crosses at x = 20: north to the High Street and the Underground
 * station, south towards the burning docks.
 */
export const ROAD_HALF = 3.6;
export const PAVEMENT = 2.2;
export const FRONT = ROAD_HALF + PAVEMENT; // house fronts at z = ±FRONT
export const HOUSE_W = 5.0;
export const HOUSE_D = 7.5;
export const YARD_D = 9.5;
export const ALLEY_W = 2.4;
export const ROW_X0 = -60;
export const ROW_X1 = 60;
export const DOCK_LANE_X = 20;
export const DOCK_LANE_HALF = 4.2;

export interface HouseDef {
  id: string;
  number: number;
  side: 'north' | 'south';
  x: number; // centre of frontage
  /** 0 intact, 1 facade blown off (doll's-house), 2 collapsed shell, 3 rubble */
  damage: 0 | 1 | 2 | 3;
  /** Interior built (enterable ground floor). */
  interior?: boolean;
  paint: number; // door/frame colour index
}

/** Terraces: frontages every HOUSE_W from ROW_X0, skipping the Dock Lane junction. */
export function terraces(): HouseDef[] {
  const out: HouseDef[] = [];
  let numN = 1;
  let numS = 2;
  for (let x = ROW_X0 + HOUSE_W / 2; x < ROW_X1; x += HOUSE_W) {
    if (Math.abs(x - DOCK_LANE_X) < DOCK_LANE_HALF + HOUSE_W / 2) continue;
    out.push({ id: `n${numN}`, number: numN, side: 'north', x, damage: 0, paint: (numN * 7) % 5 });
    out.push({ id: `s${numS}`, number: numS, side: 'south', x, damage: 0, paint: (numS * 3) % 5 });
    numN += 2;
    numS += 2;
  }
  // story houses and earlier bomb damage (the raids have been going on for weeks)
  const set = (id: string, patch: Partial<HouseDef>): void => {
    const h = out.find((o) => o.id === id);
    if (h) Object.assign(h, patch);
  };
  set('n9', { interior: true }); // the Hartleys
  set('s14', { interior: true }); // Mr Moss — hit during the raid (scripted)
  set('s22', { damage: 3 }); // destroyed last week: a gap site with rubble
  set('n27', { damage: 1 });
  set('s30', { damage: 2 });
  return out;
}

export const HIGH_STREET_Z = -46;
/** Station building: front flush with the north shopfronts (z = HIGH_STREET_Z − 6). */
export const STATION = { x: DOCK_LANE_X + 9, z: HIGH_STREET_Z - 6 - 4.5, w: 12, d: 9 };
/** Underground: stairs from the booking hall down to a platform tunnel (y < 0). */
export const TUBE = {
  depth: 9,
  platform: { x0: DOCK_LANE_X - 22, x1: DOCK_LANE_X + 40, z: STATION.z - 14, width: 3.6 },
};
export const WARDEN_POST = { x: DOCK_LANE_X - 6.2, z: -FRONT + 1.0 };
export const FIRST_AID_POST = { x: -8, z: HIGH_STREET_Z - 3.8 - 2.2 - 5, w: 12, d: 10 };
export const DEPOT = { x: -40, z: HIGH_STREET_Z + 3.8 + 2.2 + 4, w: 8, d: 8 };
/** Dock Lane south is blocked by a crater and a burst main; the rescue lorry waits beyond it. */
export const CRATER = { x: DOCK_LANE_X, z: 33.5, r: 5.5 };
export const RESCUE_LORRY = { x: DOCK_LANE_X + 1.5, z: 44 };
/** Back alley gate the rescue party can use instead (south alley). */
export const ALLEY_GATE = { x: DOCK_LANE_X + 11, z: FRONT + HOUSE_D + YARD_D + ALLEY_W + 0.24 };
export const BOUNDS = { minX: -64, maxX: 64, minZ: -76, maxZ: 52 };

/** High Street shop terraces: [x0, x1] spans on each side, leaving room for the station, FAP and depot. */
export const SHOPS_NORTH: [number, number][] = [[-62, -14.5], [-1.5, 22.5], [35.5, 62]];
export const SHOPS_SOUTH: [number, number][] = [[-62, -44.5], [-35.5, 15.8], [24.2, 62]];
export const WVS_VAN = { x: 6, z: HIGH_STREET_Z + 2.0 };
export const AFS_PUMP = { x: 42, z: HIGH_STREET_Z + 2.4 };
