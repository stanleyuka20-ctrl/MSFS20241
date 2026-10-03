import * as THREE from 'three';
import { DUGOUTS, type DugoutDef } from './layout';
import type { Terrain } from './terrain';
import type { CellBatches } from './dressing';

export interface DugoutBuild {
  def: DugoutDef;
  /** Interior floor centre. */
  floor: THREE.Vector3;
  /** Point just inside the entrance, at trench floor level. */
  door: THREE.Vector3;
  /** Inward direction (from trench into dugout). */
  dir: THREE.Vector3;
  ceilingY: number;
  /** Interior volume for "indoor" detection. */
  box: THREE.Box3;
  colliders: { c: THREE.Vector3; s: THREE.Vector3; r: number }[];
}

/**
 * Cut-and-cover dugouts: timber-lined room and passage carved into the terrain (see Terrain.boxCarve),
 * roofed with baulks, corrugated iron and an earth/sandbag cover at ground level.
 */
export function buildDugouts(t: Terrain, batches: CellBatches, tiles: Record<string, number>): DugoutBuild[] {
  const out: DugoutBuild[] = [];
  for (const def of DUGOUTS) {
    const [rx, rz] = def.room;
    const [sx, sz] = def.size;
    const base = t.base(rx, rz);
    const floorY = base - def.depth;
    const ceilY = base - 0.22;
    const [[ex0, ez0], [ex1, ez1]] = def.entrance;
    const dir = new THREE.Vector3(ex1 - ex0, 0, ez1 - ez0).normalize();
    const colliders: DugoutBuild['colliders'] = [];
    const wallTile = tiles.wood_planks ?? 1.2;
    const beamTile = tiles.wood_beam ?? 1;
    const corrTile = tiles.corrugated_iron ?? 1;

    // --- interior plank lining (4 walls), slightly inset from the carve
    const inset = 0.08;
    const h = ceilY - floorY + 0.1;
    const walls: [number, number, number, number, number][] = [
      // cx, cz, length, rotY, which
      [rx, rz - sz / 2 + inset, sx, 0, 0],
      [rx, rz + sz / 2 - inset, sx, Math.PI, 1],
      [rx - sx / 2 + inset, rz, sz, Math.PI / 2, 2],
      [rx + sx / 2 - inset, rz, sz, -Math.PI / 2, 3],
    ];
    for (const [cx, cz, len, rot] of walls) {
      // leave a gap where the entrance passage meets the room
      const n = new THREE.Vector3(Math.sin(rot), 0, Math.cos(rot)); // inward normal
      const facingDoor = n.dot(dir) > 0.7; // wall whose inward normal matches passage direction = the wall with the door
      if (facingDoor) {
        // two panels either side of a 1.0 m opening
        const side = new THREE.Vector3(Math.cos(rot), 0, -Math.sin(rot));
        const doorOff = side.x * (ex1 - cx) + side.z * (ez1 - cz);
        const segs: [number, number][] = [
          [-len / 2, doorOff - 0.5],
          [doorOff + 0.5, len / 2],
        ];
        for (const [a, b] of segs) {
          if (b - a < 0.1) continue;
          const mid = (a + b) / 2;
          panel(batches, cx + side.x * mid, floorY, cz + side.z * mid, b - a, h, rot, wallTile);
        }
      } else panel(batches, cx, floorY, cz, len, h, rot, wallTile);
    }
    // corner posts + head beams
    for (const [px, pz] of [[rx - sx / 2 + 0.12, rz - sz / 2 + 0.12], [rx + sx / 2 - 0.12, rz - sz / 2 + 0.12], [rx - sx / 2 + 0.12, rz + sz / 2 - 0.12], [rx + sx / 2 - 0.12, rz + sz / 2 - 0.12]]) {
      const g = box(0.14, h, 0.14, beamTile);
      batches.get('beam', px, pz).add(g, new THREE.Matrix4().makeTranslation(px, floorY + h / 2, pz));
    }
    // ceiling: beams across + corrugated sheets visible from below
    const along = sx > sz;
    const span = along ? sz : sx;
    const run = along ? sx : sz;
    for (let s = -run / 2 + 0.3; s <= run / 2 - 0.2; s += 0.7) {
      const g = box(along ? 0.16 : span + 0.3, 0.16, along ? span + 0.3 : 0.16, beamTile);
      const px = along ? rx + s : rx;
      const pz = along ? rz : rz + s;
      batches.get('beam', px, pz).add(g, new THREE.Matrix4().makeTranslation(px, ceilY - 0.08, pz));
    }
    const sheet = box(sx + 0.2, 0.02, sz + 0.2, corrTile);
    batches.get('corrugated_solid', rx, rz).add(sheet, new THREE.Matrix4().makeTranslation(rx, ceilY + 0.01, rz));
    // floor boards
    const fl = box(sx - 0.15, 0.04, sz - 0.15, wallTile);
    batches.get('planks_solid', rx, rz).add(fl, new THREE.Matrix4().makeTranslation(rx, floorY + 0.02, rz));

    // --- entrance passage: frame sets (posts + cap) and roof
    const plen = Math.hypot(ex1 - ex0, ez1 - ez0);
    const rotP = Math.atan2(dir.x, dir.z);
    const right = new THREE.Vector3(dir.z, 0, -dir.x);
    const passageTop = ceilY;
    for (let s = 0; s <= plen + 0.01; s += Math.max(0.6, plen / 3)) {
      const px = ex0 + dir.x * s;
      const pz = ez0 + dir.z * s;
      const fy = t.height(px, pz);
      const ph = passageTop - fy;
      for (const sgn of [-1, 1]) {
        const g = box(0.13, ph, 0.13, beamTile);
        batches.get('beam', px, pz).add(g, new THREE.Matrix4().makeTranslation(px + right.x * 0.5 * sgn, fy + ph / 2, pz + right.z * 0.5 * sgn));
      }
      const cap = box(1.15, 0.15, 0.15, beamTile);
      batches.get('beam', px, pz).add(cap, new THREE.Matrix4().makeRotationY(rotP).setPosition(px, passageTop - 0.075, pz));
    }
    // passage side lining
    for (const sgn of [-1, 1]) {
      const cx = (ex0 + ex1) / 2 + right.x * 0.52 * sgn;
      const cz = (ez0 + ez1) / 2 + right.z * 0.52 * sgn;
      const fy = t.height((ex0 + ex1) / 2, (ez0 + ez1) / 2);
      panel(batches, cx, fy - 0.05, cz, plen + 0.2, passageTop - fy + 0.05, rotP + (sgn > 0 ? -Math.PI / 2 : Math.PI / 2), wallTile);
    }
    const proof = box(1.3, 0.04, plen + 0.4, corrTile);
    batches.get('corrugated_solid', ex0, ez0).add(proof, new THREE.Matrix4().makeRotationY(rotP).setPosition((ex0 + ex1) / 2, passageTop + 0.02, (ez0 + ez1) / 2));

    // --- cover on top: earth/chalk mound box at ground level (collider) over room + passage
    const coverH = 0.45;
    const cover = box(sx + 0.7, coverH, sz + 0.7, tiles.chalk_spoil ?? 2);
    batches.get('spoil', rx, rz).add(cover, new THREE.Matrix4().makeTranslation(rx, ceilY + 0.04 + coverH / 2, rz));
    colliders.push({ c: new THREE.Vector3(rx, ceilY + 0.04 + coverH / 2, rz), s: new THREE.Vector3(sx + 0.7, coverH, sz + 0.7), r: 0 });
    const pcover = box(1.6, coverH, plen + 0.5, tiles.chalk_spoil ?? 2);
    const pm = new THREE.Matrix4().makeRotationY(rotP).setPosition((ex0 + ex1) / 2, passageTop + 0.04 + coverH / 2, (ez0 + ez1) / 2);
    batches.get('spoil', ex0, ez0).add(pcover, pm);
    colliders.push({ c: new THREE.Vector3((ex0 + ex1) / 2, passageTop + 0.04 + coverH / 2, (ez0 + ez1) / 2), s: new THREE.Vector3(1.6, coverH, plen + 0.5), r: rotP });
    // ceiling collider (so the capsule never rises into the roof)
    colliders.push({ c: new THREE.Vector3(rx, ceilY + 0.06, rz), s: new THREE.Vector3(sx, 0.12, sz), r: 0 });

    const door = new THREE.Vector3(ex0, t.height(ex0, ez0), ez0);
    out.push({
      def,
      floor: new THREE.Vector3(rx, floorY, rz),
      door,
      dir,
      ceilingY: ceilY,
      box: new THREE.Box3(new THREE.Vector3(rx - sx / 2 - 0.2, floorY - 0.5, rz - sz / 2 - 0.2), new THREE.Vector3(rx + sx / 2 + 0.2, ceilY, rz + sz / 2 + 0.2)).union(new THREE.Box3().setFromPoints([new THREE.Vector3(ex0 + dir.x * 0.6, floorY - 0.5, ez0 + dir.z * 0.6), new THREE.Vector3(ex1, ceilY, ez1)]).expandByVector(new THREE.Vector3(0.5, 0, 0.5))),
      colliders,
    });
  }
  return out;
}

function box(w: number, h: number, d: number, tile: number): THREE.BoxGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  const n = g.attributes.normal as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) {
    const ax = Math.abs(n.getX(i));
    const ay = Math.abs(n.getY(i));
    const sx = ax > 0.5 ? d : w;
    const sy = ay > 0.5 ? d : h;
    uv.setXY(i, (uv.getX(i) * sx) / tile, (uv.getY(i) * sy) / tile);
  }
  return g;
}

/** Vertical plank panel; `rot` orients its inward-facing normal. */
function panel(batches: CellBatches, cx: number, floorY: number, cz: number, len: number, h: number, rot: number, tile: number): void {
  const g = new THREE.PlaneGeometry(len, h);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * len) / tile, (uv.getY(i) * h) / tile);
  const col = new Float32Array(uv.count * 3);
  for (let i = 0; i < uv.count; i++) {
    const v = uv.getY(i) * tile / h;
    const ao = 0.55 + 0.45 * Math.min(1, v * 1.4);
    col.set([ao, ao, ao], i * 3);
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  batches.get('planks', cx, cz).add(g, new THREE.Matrix4().makeRotationY(rot).setPosition(cx, floorY + h / 2, cz));
}
