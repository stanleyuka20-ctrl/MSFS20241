import * as THREE from 'three';
import { Builder, type Rect } from '../common/builder';
import { Rng } from '../../core/Random';
import { FRONT, HOUSE_W, HOUSE_D, YARD_D, ALLEY_W, type HouseDef } from './layout';

/** Material keys used by the terrace builder → texture set names. */
export const LONDON_SETS: Record<string, string> = {
  brick: 'london_stock_brick',
  brickDark: 'london_stock_brick',
  stucco: 'render_stucco',
  slate: 'slate_roof',
  frame: 'painted_wood',
  door: 'painted_wood',
  wallpaper: 'interior_wallpaper',
  floor: 'floorboards_interior',
  ceiling: 'render_stucco',
  stone: 'pavement_flags',
  rubble: 'stone_rubble',
  timber: 'wood_beam',
  charred: 'soot_scorch',
  corrugated: 'corrugated_iron',
  earth: 'mud_wet',
  glass: 'glass',
  curtain: 'curtain',
  pot: 'pot',
  tape: 'tape',
  metal: 'rusty_steel',
};

export const GF = 2.9; // ground floor height
export const FF = 2.75; // first floor height
export const EAVES = GF + FF + 0.25;
const WALL_T = 0.34;
const PARTY_T = 0.22;

export interface HouseBuild {
  def: HouseDef;
  /** World positions of interest. */
  door: THREE.Vector3;
  doorOutside: THREE.Vector3;
  understairs?: THREE.Vector3;
  interiorBox?: THREE.Box3;
  /** For houses with a scripted damage state: separate builders for the intact and damaged versions. */
  intact?: Builder;
  damaged?: Builder;
}

/**
 * Build one terraced house into `b` (frame already set at the frontage centre). Local frame:
 * x along the frontage (−W/2..W/2), y up, z = 0 front face, house occupies z ∈ [−D, 0], the yard
 * continues to z = −(D + YARD_D), the alley behind.
 */
export function buildHouse(b: Builder, def: HouseDef, rng: Rng, opts: { damage: 0 | 1 | 2 | 3; interior: boolean; anderson: boolean; ruin?: boolean; closeRight?: boolean }): void {
  const hw = HOUSE_W / 2;
  const D = HOUSE_D;
  const dmg = opts.damage;
  // door on the left or right (alternating, mirrored pairs as in real terraces)
  const doorLeft = def.number % 4 < 2;
  const doorX0 = doorLeft ? -hw + 0.45 : hw - 0.45 - 1.0;
  const doorX1 = doorX0 + 1.0;
  const winX0 = doorLeft ? doorX1 + 0.55 : -hw + 0.5;
  const winX1 = doorLeft ? hw - 0.5 : doorX0 - 0.55;
  const ff1: Rect = { x0: -hw + 0.6, x1: -hw + 1.55, y0: GF + 0.75, y1: GF + 2.25 };
  const ff2: Rect = { x0: hw - 1.55, x1: hw - 0.6, y0: GF + 0.75, y1: GF + 2.25 };
  const doorR: Rect = { x0: doorX0, x1: doorX1, y0: 0.18, y1: 2.45 };
  const gWin: Rect = { x0: winX0, x1: winX1, y0: 0.85, y1: 2.45 };

  if (dmg === 3) {
    // gap site: low wall stubs and rubble (rubble mounds are added by the caller)
    b.box('brick', -hw, hw, 0, 0.5 + rng.next() * 0.6, -WALL_T, 0, true);
    b.box('brick', -hw, -hw + PARTY_T, 0, 1.2, -D, 0, true);
    return;
  }

  // --- front wall
  const frontTop = dmg === 0 ? EAVES : dmg === 1 ? GF + 0.3 : GF * 0.8;
  b.wall('brick', -hw, hw, 0, frontTop, -WALL_T, 0, dmg === 0 ? [doorR, gWin, ff1, ff2] : [doorR, gWin], !opts.interior || true);
  // ragged remains above the blown-out section
  if (dmg === 2) for (let x = -hw; x < hw - 0.3; x += 0.3) if (x + 0.3 < doorX0 || x > doorX1) b.box('brick', x, x + 0.3, frontTop, frontTop + rng.next() * rng.next() * 1.6, -WALL_T, 0);
  if (dmg === 1) for (let x = -hw; x < hw - 0.3; x += 0.3) b.box('brick', x, x + 0.3, frontTop, frontTop + rng.next() * 0.9, -WALL_T, 0);
  // stucco details: lintels, sills, plinth, string course
  b.box('stucco', -hw, hw, 0, 0.18, -WALL_T - 0.02, 0.03); // plinth
  for (const r of dmg === 0 ? [gWin, ff1, ff2] : [gWin]) {
    b.box('stucco', r.x0 - 0.1, r.x1 + 0.1, r.y1, r.y1 + 0.22, -0.06, 0.03); // lintel
    b.box('stucco', r.x0 - 0.06, r.x1 + 0.06, r.y0 - 0.07, r.y0, -0.12, 0.06); // sill
    window(b, r, -0.11, rng, true);
  }
  if (dmg === 0) b.box('stucco', -hw, hw, GF - 0.1, GF + 0.05, -0.05, 0.035); // string course
  // door: recessed leaf, fanlight, step
  b.box('stucco', doorX0 - 0.1, doorX1 + 0.1, doorR.y1, doorR.y1 + 0.26, -0.06, 0.03);
  b.box('stone', doorX0 - 0.05, doorX1 + 0.05, 0, 0.18, 0, 0.32, true);
  if (!opts.interior && !opts.ruin) {
    b.box('door', doorX0 + 0.04, doorX1 - 0.04, 0.18, 2.12, -0.24, -0.2, true);
    b.box('glass', doorX0 + 0.08, doorX1 - 0.08, 2.15, 2.4, -0.2, -0.19);
  }
  // glazed openings are not walkable
  for (const r of dmg === 0 ? [gWin, ff1, ff2] : [gWin]) b.collider(r.x0, r.x1, r.y0, r.y1, -WALL_T, -0.05);

  // --- party walls and rear
  const partyTop = dmg === 2 ? GF * 0.9 : EAVES + 0.2;
  b.box('brick', -hw, -hw + PARTY_T / 2, 0, partyTop, -D, 0, true);
  b.box('brick', hw - PARTY_T / 2, hw, 0, partyTop, -D, 0, true);
  const backOpen: Rect[] = [
    { x0: -hw + 0.7, x1: -hw + 1.6, y0: 0.9, y1: 2.3 },
    { x0: hw - 1.5, x1: hw - 0.7, y0: GF + 0.8, y1: GF + 2.2 },
  ];
  b.wall('brick', -hw, hw, 0, dmg === 2 ? GF * 0.7 : EAVES, -D, -D + WALL_T, backOpen, true);
  for (const r of backOpen) if (dmg === 0 || r.y1 < GF) window(b, r, -D + WALL_T - 0.1, rng, false);

  // --- roof (pitched, ridge parallel to the street) with chimney stack on the party wall
  if (dmg === 0) {
    const rise = 2.1;
    const ridgeZ = -D / 2;
    const ov = 0.25;
    const A = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
    b.quad('slate', A(-hw, EAVES, ov), A(hw, EAVES, ov), A(hw, EAVES + rise, ridgeZ), A(-hw, EAVES + rise, ridgeZ));
    b.quad('slate', A(hw, EAVES, -D - ov), A(-hw, EAVES, -D - ov), A(-hw, EAVES + rise, ridgeZ), A(hw, EAVES + rise, ridgeZ));
    // gable infill between party walls under the roof (hidden in a terrace, closes the ends)
    gable(b, -hw, -hw + PARTY_T / 2, -D, 0, EAVES, EAVES + rise);
    if (opts.closeRight) gable(b, hw - PARTY_T / 2, hw, -D, 0, EAVES, EAVES + rise);
    b.box('slate', -hw, hw, EAVES + rise - 0.06, EAVES + rise + 0.07, ridgeZ - 0.12, ridgeZ + 0.12); // ridge
    // gutters and downpipe
    const gutter = new THREE.CylinderGeometry(0.06, 0.06, HOUSE_W, 8, 1, true, 0, Math.PI);
    gutter.rotateZ(Math.PI / 2);
    b.geo('metal', gutter, new THREE.Matrix4().makeTranslation(0, EAVES - 0.02, ov + 0.02));
    if (def.number % 2 === 0) b.geo('metal', new THREE.CylinderGeometry(0.04, 0.04, EAVES, 6), new THREE.Matrix4().makeTranslation(hw - 0.05, EAVES / 2, 0.08));
    // chimney stack straddling the party wall at the ridge
    const cx = hw;
    b.box('brick', cx - 0.45, cx + 0.45, EAVES + rise - 0.4, EAVES + rise + 1.15, ridgeZ - 0.35, ridgeZ + 0.35);
    b.box('stucco', cx - 0.5, cx + 0.5, EAVES + rise + 1.15, EAVES + rise + 1.25, ridgeZ - 0.4, ridgeZ + 0.4);
    for (let i = 0; i < 4; i++) {
      const pot = new THREE.CylinderGeometry(0.1, 0.12, 0.45 + (i % 2) * 0.12, 10);
      b.geo('pot', pot, new THREE.Matrix4().makeTranslation(cx - 0.33 + i * 0.22, EAVES + rise + 1.48, ridgeZ));
    }
  } else if (dmg === 1) {
    // a few rafters and the back roof slope survive
    const rise = 2.1;
    const A = (x: number, y: number, z: number): THREE.Vector3 => new THREE.Vector3(x, y, z);
    b.quad('slate', A(hw, EAVES, -D - 0.25), A(-hw, EAVES, -D - 0.25), A(-hw, EAVES + rise, -D / 2), A(hw, EAVES + rise, -D / 2));
    for (let i = 0; i < 4; i++) b.box('timber', -hw + 0.6 + i * 1.2, -hw + 0.72 + i * 1.2, EAVES - 0.4, EAVES + 0.1, -D / 2, -0.1 - rng.next() * 1.5);
    // exposed first floor: joists, floor, wallpapered party walls (the "doll's house")
    b.box('floor', -hw + 0.1, hw - 0.1, GF, GF + 0.08, -D + 0.4, -0.2 - rng.next() * 0.6);
    b.box('wallpaper', -hw + PARTY_T / 2, -hw + PARTY_T / 2 + 0.01, GF + 0.08, GF + FF, -D + 0.4, -0.3);
    b.box('wallpaper', hw - PARTY_T / 2 - 0.01, hw - PARTY_T / 2, GF + 0.08, GF + FF, -D + 0.4, -0.3);
    // a bed frame hanging over the edge
    b.box('metal', -1.2, 0.3, GF + 0.3, GF + 0.36, -1.6, -0.1);
  }

  // --- back extension (scullery) with mono-pitch roof
  const extW = 2.4;
  const ex0 = doorLeft ? hw - extW : -hw;
  const ex1 = ex0 + extW;
  if (dmg !== 2) {
    b.box('brick', ex0, ex0 + 0.22, 0, 2.6, -D - 3.2, -D, true);
    b.box('brick', ex1 - 0.22, ex1, 0, 2.6, -D - 3.2, -D, true);
    b.wall('brick', ex0, ex1, 0, 2.6, -D - 3.2, -D - 3.0, [{ x0: ex0 + 0.6, x1: ex0 + 1.4, y0: 1.0, y1: 2.0 }], true);
    b.quad('slate', new THREE.Vector3(ex0, 2.6, -D - 3.35), new THREE.Vector3(ex1, 2.6, -D - 3.35), new THREE.Vector3(ex1, 3.3, -D), new THREE.Vector3(ex0, 3.3, -D));
  }

  // --- yard: walls, gate to the alley, outhouse, dustbin, Anderson shelter, washing line
  const yz0 = -D;
  const yz1 = -D - YARD_D;
  b.box('brickDark', -hw, -hw + 0.11, 0, 1.8, yz1, yz0, true);
  // end of a terrace run: close the yard on the other side too
  if (opts.closeRight) b.box('brickDark', hw - 0.11, hw, 0, 1.8, yz1, yz0, true);
  // the yard gate is on the opposite side from the outhouse
  const gx0 = doorLeft ? hw - 1.3 : -hw + 0.4;
  b.wall('brickDark', -hw, hw, 0, 1.8, yz1, yz1 + 0.22, [{ x0: gx0, x1: gx0 + 0.9, y0: 0, y1: 2.0 }], true);
  b.box('frame', gx0 + 0.02, gx0 + 0.88, 0.05, 1.75, yz1 + 0.04, yz1 + 0.09, false); // yard gate leaf (open, against the wall)
  // outhouse (WC) in the back corner
  const ox0 = doorLeft ? -hw + 0.1 : hw - 1.4;
  b.box('brick', ox0, ox0 + 1.3, 0, 2.1, yz1 + 0.22, yz1 + 1.6, true);
  b.box('door', ox0 + 0.25, ox0 + 1.0, 0.05, 1.85, yz1 + 1.6, yz1 + 1.64);
  b.box('slate', ox0 - 0.05, ox0 + 1.35, 2.1, 2.16, yz1 + 0.15, yz1 + 1.7);
  if (opts.anderson) anderson(b, 0, yz0 - YARD_D * 0.55);
  // washing line between wall hooks
  b.geo('metal', new THREE.CylinderGeometry(0.004, 0.004, YARD_D * 0.8, 4).rotateX(Math.PI / 2), new THREE.Matrix4().makeTranslation(doorLeft ? hw - 0.6 : -hw + 0.6, 2.0, yz0 - YARD_D * 0.45));
  b.geo('metal', new THREE.CylinderGeometry(0.24, 0.22, 0.7, 12), new THREE.Matrix4().makeTranslation(ex0 + extW / 2, 0.35, yz0 - 3.6)); // dustbin

  // --- interior (enterable ground floor): hall, stairs, cupboard under the stairs, front room
  if (opts.interior) interior(b, def, doorX0, doorX1, doorLeft, rng);
  if (opts.ruin) ruin(b, doorLeft, rng);
}

/** Local position of the cupboard under the stairs (where Mr Moss shelters). */
export function understairsLocal(def: HouseDef): THREE.Vector3 {
  const hw = HOUSE_W / 2;
  const doorLeft = def.number % 4 < 2;
  const sx = doorLeft ? -hw + PARTY_T / 2 + 0.46 : hw - PARTY_T / 2 - 0.46;
  return new THREE.Vector3(sx, 0.2, -WALL_T - 1.4 - 2.2);
}

/** Door centre in the local frame (front face). */
export function doorLocal(def: HouseDef): THREE.Vector3 {
  const hw = HOUSE_W / 2;
  const doorLeft = def.number % 4 < 2;
  const x0 = doorLeft ? -hw + 0.45 : hw - 0.45 - 1.0;
  return new THREE.Vector3(x0 + 0.5, 0.18, 0);
}

/**
 * Inside of a house hit by a high-explosive bomb: the roof and first floor have come down into the
 * ground floor. Joists and floorboards lie at angles over a mound of brick and plaster; the stair
 * carriage still stands at the party wall and has kept a pocket open beneath it. No people are
 * visible; the occupant is reached by the rescue party.
 */
function ruin(b: Builder, doorLeft: boolean, rng: Rng): void {
  const hw = HOUSE_W / 2;
  const D = HOUSE_D;
  const stairX = doorLeft ? -hw + PARTY_T / 2 + 0.46 : hw - PARTY_T / 2 - 0.46;
  const s = doorLeft ? 1 : -1; // direction from the stair wall into the room
  // main debris mound (towards the back, highest in the middle) — visual and blocking
  const mound = new THREE.SphereGeometry(1, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2);
  const mp = mound.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < mp.count; i++) {
    const n = 1 + (rng.next() - 0.5) * 0.25;
    mp.setXYZ(i, mp.getX(i) * n, mp.getY(i) * n, mp.getZ(i) * n);
  }
  mound.scale(hw - 0.2, 1.7, D * 0.42);
  b.geo('rubble', mound, new THREE.Matrix4().makeTranslation(-s * 0.3, -0.1, -D * 0.58));
  b.collider(-hw + 0.2, hw - 0.2, 0, 1.6, -D + 0.4, -D * 0.38);
  // lower spill towards the front room window
  const spill = new THREE.SphereGeometry(1, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2);
  spill.scale(1.5, 0.55, 1.6);
  b.geo('rubble', spill, new THREE.Matrix4().makeTranslation(-s * 1.0, -0.05, -2.2));
  b.collider(-s * 1.0 - 1.1, -s * 1.0 + 1.1, 0, 0.35, -3.4, -1.0);
  // fallen joists and floorboards at angles
  for (let i = 0; i < 7; i++) {
    const len = 2.4 + rng.next() * 2.2;
    const j = new THREE.BoxGeometry(0.075, 0.2, len);
    const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rng.range(-0.55, 0.35), rng.range(-0.6, 0.6), rng.range(-0.3, 0.3))).setPosition(rng.range(-hw + 0.5, hw - 0.5), 0.5 + rng.next() * 1.3, -D * 0.5 + rng.range(-1.6, 1.6));
    b.geo(i % 3 === 0 ? 'charred' : 'timber', j, m);
  }
  for (let i = 0; i < 4; i++) {
    const p = new THREE.BoxGeometry(0.9 + rng.next(), 0.025, 1.6 + rng.next());
    b.geo('floor', p, new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rng.range(-0.5, 0.5), rng.range(0, 3), rng.range(-0.4, 0.4))).setPosition(rng.range(-hw + 0.8, hw - 0.8), 1.0 + rng.next(), -D * 0.55 + rng.range(-1.2, 1.2)));
  }
  // the stair carriage: strings still up against the party wall, treads broken, a pocket beneath
  const steps = 13;
  const run = 0.24;
  const rise = (GF - 0.18) / steps;
  const sz0 = -WALL_T - 1.4;
  for (let i = 0; i < steps; i++) if (i < 3 || i > 5) b.box('floor', stairX - 0.44, stairX + 0.44, 0.18 + i * rise, 0.18 + (i + 1) * rise, sz0 - (i + 1) * run, sz0 - i * run, i < 3);
  b.box('timber', stairX - s * 0.44, stairX - s * 0.4, 0.18, GF, sz0 - steps * run, sz0);
  // stair-side panelling blown in, leaning; the opening of the cupboard is half buried
  b.geo('door', new THREE.BoxGeometry(0.04, 1.3, 1.1), new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(0.15, 0, s * 0.45)).setPosition(stairX + s * 0.75, 0.6, sz0 - 2.5));
  b.collider(stairX + s * 0.46, stairX + s * 1.1, 0, 1.2, sz0 - 3.2, sz0 - 1.4);
  // wallpaper still on the party walls, plaster fallen in sheets
  b.box('wallpaper', -hw + PARTY_T / 2, -hw + PARTY_T / 2 + 0.01, 0.3, GF * 0.85, -D + 0.6, -WALL_T - 0.2);
  b.box('wallpaper', hw - PARTY_T / 2 - 0.01, hw - PARTY_T / 2, 0.3, GF * 0.85, -D + 0.6, -WALL_T - 0.2);
  for (let i = 0; i < 18; i++) {
    const br = new THREE.BoxGeometry(0.22, 0.07, 0.1);
    b.geo(i % 4 === 0 ? 'stucco' : 'brick', br, new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rng.next() * 3, rng.next() * 3, rng.next() * 3)).setPosition(rng.range(-hw + 0.3, hw - 0.3), 0.06, rng.range(-1.2, 1.6)));
  }
}

/** Triangular gable infill between the roof slopes (party wall above the eaves). */
function gable(b: Builder, x0: number, x1: number, zb: number, zf: number, y0: number, y1: number): void {
  const zm = (zb + zf) / 2;
  // outer face at x0 looks towards −x, the one at x1 towards +x (wound accordingly)
  const pos = [x0, y0, zf, x0, y1, zm, x0, y0, zb, x1, y0, zb, x1, y1, zm, x1, y0, zf];
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  const uv: number[] = [];
  for (let i = 0; i < pos.length; i += 3) uv.push(pos[i + 2], pos[i + 1]);
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  b.geo('brick', g);
}

/** Sash window: frame, meeting rail, glazing bars, dark glass with anti-blast tape, blackout curtain behind. */
function window(b: Builder, r: Rect, z: number, rng: Rng, front: boolean): void {
  const ft = 0.06;
  b.box('frame', r.x0, r.x1, r.y0, r.y0 + ft, z - 0.06, z);
  b.box('frame', r.x0, r.x1, r.y1 - ft, r.y1, z - 0.06, z);
  b.box('frame', r.x0, r.x0 + ft, r.y0, r.y1, z - 0.06, z);
  b.box('frame', r.x1 - ft, r.x1, r.y0, r.y1, z - 0.06, z);
  const my = (r.y0 + r.y1) / 2;
  b.box('frame', r.x0, r.x1, my - 0.03, my + 0.03, z - 0.08, z + 0.01); // meeting rails
  const cx = (r.x0 + r.x1) / 2;
  b.box('frame', cx - 0.015, cx + 0.015, r.y0, r.y1, z - 0.045, z - 0.025); // glazing bar
  // glass panes (slightly broken in some windows: missing pane)
  const missing = rng.chance(0.08);
  if (!missing) b.box('glass', r.x0 + ft, r.x1 - ft, r.y0 + ft, r.y1 - ft, z - 0.04, z - 0.035);
  if (front && !missing) {
    // gummed paper tape across each pane (one texture = one pane)
    const zt = z - 0.033;
    for (const [xa, xb] of [[r.x0 + ft, cx - 0.015], [cx + 0.015, r.x1 - ft]]) {
      for (const [ya, yb] of [[r.y0 + ft, my - 0.03], [my + 0.03, r.y1 - ft]]) {
        b.quad('tape', new THREE.Vector3(xa, ya, zt), new THREE.Vector3(xb, ya, zt), new THREE.Vector3(xb, yb, zt), new THREE.Vector3(xa, yb, zt), 1, 1);
      }
    }
  }
  // blackout curtain behind
  b.box('curtain', r.x0 - 0.05, r.x1 + 0.05, r.y0, r.y1 + 0.05, z - 0.2, z - 0.18);
}

/** Anderson shelter: two curved corrugated sheets sunk in the yard and covered with earth. */
function anderson(b: Builder, x: number, z: number): void {
  const arc = new THREE.CylinderGeometry(1.0, 1.0, 1.95, 16, 1, true, -Math.PI / 2, Math.PI);
  arc.rotateZ(Math.PI / 2);
  arc.rotateY(Math.PI / 2);
  b.geo('corrugated', arc, new THREE.Matrix4().makeTranslation(x, 0.1, z));
  const mound = new THREE.SphereGeometry(1, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2);
  mound.scale(1.35, 1.25, 1.25);
  b.geo('earth', mound, new THREE.Matrix4().makeTranslation(x, -0.05, z - 0.35));
  b.collider(x - 1.3, x + 1.3, 0, 1.2, z - 1.5, z + 0.9);
}

function interior(b: Builder, def: HouseDef, doorX0: number, doorX1: number, doorLeft: boolean, rng: Rng): void {
  const hw = HOUSE_W / 2;
  const D = HOUSE_D;
  const hallX0 = doorLeft ? -hw + PARTY_T / 2 : doorX0 - 0.1;
  const hallX1 = doorLeft ? doorX1 + 0.1 : hw - PARTY_T / 2;
  const partX = doorLeft ? hallX1 : hallX0; // wall between hall and front room
  // floor and ceiling
  b.box('floor', -hw + PARTY_T / 2, hw - PARTY_T / 2, 0.1, 0.18, -D + WALL_T, -WALL_T, true);
  b.box('ceiling', -hw + PARTY_T / 2, hw - PARTY_T / 2, GF - 0.02, GF + 0.05, -D + WALL_T, -WALL_T, true);
  // wallpaper on the inner faces
  b.box('wallpaper', -hw + PARTY_T / 2, -hw + PARTY_T / 2 + 0.01, 0.18, GF - 0.02, -D + WALL_T, -WALL_T);
  b.box('wallpaper', hw - PARTY_T / 2 - 0.01, hw - PARTY_T / 2, 0.18, GF - 0.02, -D + WALL_T, -WALL_T);
  b.box('wallpaper', -hw + PARTY_T / 2, hw - PARTY_T / 2, 0.18, GF - 0.02, -WALL_T - 0.01, -WALL_T);
  // partition between hall and front room with a doorway
  // the partition runs along Z: built from boxes around a doorway
  const pz0 = -D + WALL_T;
  const pz1 = -WALL_T;
  // the front-room door opens off the hall just inside the street door, before the stairs
  b.box('wallpaper', partX - 0.06, partX + 0.06, 0.18, GF - 0.02, pz0, pz1 - 1.5, true);
  b.box('wallpaper', partX - 0.06, partX + 0.06, 0.18, GF - 0.02, pz1 - 0.45, pz1, true);
  b.box('wallpaper', partX - 0.06, partX + 0.06, 2.1, GF - 0.02, pz1 - 1.5, pz1 - 0.45);
  // stairs rising toward the back along the party wall of the hall
  const sx0 = doorLeft ? hallX0 + 0.02 : hallX1 - 0.9;
  const sx1 = sx0 + 0.88;
  const steps = 13;
  const run = 0.24;
  const rise = (GF - 0.18) / steps;
  const sz0 = -WALL_T - 1.4;
  for (let i = 0; i < steps; i++) b.box('floor', sx0, sx1, 0.18 + i * rise, 0.18 + (i + 1) * rise, sz0 - (i + 1) * run, sz0 - i * run, true);
  // cupboard under the stairs: panelled side with a small door
  const cz0 = sz0 - steps * run;
  const cz1 = sz0 - 1.2;
  b.box('door', doorLeft ? sx1 : sx0 - 0.04, doorLeft ? sx1 + 0.04 : sx0, 0.18, 1.6, cz0, cz1 - 0.65, true);
  b.box('door', doorLeft ? sx1 : sx0 - 0.04, doorLeft ? sx1 + 0.04 : sx0, 1.3, 1.6, cz1 - 0.65, cz1);
  // front room furniture: fireplace on the party wall, table, chairs, armchair, sideboard
  const rx = doorLeft ? (partX + hw) / 2 : (-hw + partX) / 2;
  const wallX = doorLeft ? hw - PARTY_T / 2 : -hw + PARTY_T / 2;
  const s = doorLeft ? -1 : 1;
  b.box('brickDark', wallX + s * 0.0, wallX + s * 0.35, 0.18, 1.2, -3.2, -2.0, true); // chimney breast
  b.box('timber', wallX + s * 0.0, wallX + s * 0.42, 1.18, 1.24, -3.3, -1.9); // mantel
  b.box('charred', wallX + s * 0.05, wallX + s * 0.36, 0.18, 0.75, -2.85, -2.35); // grate
  b.box('timber', rx - 0.55, rx + 0.55, 0.74, 0.78, -4.6, -3.8, true); // table top
  for (const [dx, dz] of [[-0.5, -0.36], [0.5, -0.36], [-0.5, 0.36], [0.5, 0.36]]) b.box('timber', rx + dx - 0.03, rx + dx + 0.03, 0.18, 0.74, -4.2 + dz - 0.03, -4.2 + dz + 0.03);
  for (const dz of [-0.75, 0.75]) {
    b.box('timber', rx - 0.2, rx + 0.2, 0.62, 0.66, -4.2 + dz - 0.2, -4.2 + dz + 0.2);
    b.box('timber', rx - 0.2, rx + 0.2, 0.66, 1.1, -4.2 + dz + (dz > 0 ? 0.17 : -0.2), -4.2 + dz + (dz > 0 ? 0.2 : -0.17));
  }
  // armchair by the fireplace, clear of the doorway
  const ax = doorLeft ? hw - 1.45 : -hw + 1.45;
  b.box('curtain', ax - 0.45, ax + 0.45, 0.18, 0.62, -2.2, -1.3, true);
  b.box('curtain', ax - 0.45, ax + 0.45, 0.62, 1.15, -2.2, -2.02);
  b.box('curtain', ax - 0.45, ax - 0.33, 0.62, 0.8, -2.2, -1.3);
  b.box('curtain', ax + 0.33, ax + 0.45, 0.62, 0.8, -2.2, -1.3);
  b.box('timber', wallX + s * 0.0, wallX + s * 0.48, 0.18, 0.95, -6.6, -5.2, true); // sideboard
  void def;
  void rng;
}

/** House frame origin for a terrace house. */
export function houseFrame(def: HouseDef): { x: number; z: number; rot: number } {
  return def.side === 'north' ? { x: def.x, z: -FRONT, rot: 0 } : { x: def.x, z: FRONT, rot: Math.PI };
}

export const ALLEY_Z = FRONT + HOUSE_D + YARD_D + ALLEY_W / 2;
