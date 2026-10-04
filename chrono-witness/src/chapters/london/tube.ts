import * as THREE from 'three';
import { Builder } from '../common/builder';
import { STATION, TUBE } from './layout';

export interface TubeBuild {
  /** Platform walkable area (for placing shelterers). */
  platform: { x0: number; x1: number; zBack: number; zEdge: number; y: number };
  stairBottom: THREE.Vector3;
  passageEnd: THREE.Vector3;
  lampPositions: THREE.Vector3[];
  box: THREE.Box3; // underground volume (indoor lighting)
  stairs: THREE.Vector3[]; // nav points top → bottom → platform
}

/**
 * Underground station shelter: two straight stair flights from the booking hall, a tiled cross
 * passage and a platform tunnel (tiled vault, platform, track bed). Built in world space.
 */
export function buildTube(b: Builder): TubeBuild {
  b.setFrame(0, 0, 0);
  const sx = STATION.x;
  const zTop = STATION.z + 1.6; // stair head (south end of the booking-hall opening)
  const rise = 0.25;
  const run = 0.3;
  const half = 1.25; // stair half-width
  const flight = 18;
  let y = 0.12;
  let z = zTop;
  const navStairs: THREE.Vector3[] = [new THREE.Vector3(sx, 0.12, zTop + 0.8)];
  const slope = rise / run;
  const headroom = 2.25; // vertical clearance above the nosing line
  // underside of the booking hall floor slab ends where the stair opening ends
  const holeNorth = STATION.z - 2.2;
  const stairFlight = (first: boolean): void => {
    for (let i = 0; i < flight; i++) {
      b.box('platform', sx - half, sx + half, y - rise * (i + 1) - 0.25, y - rise * (i + 1), z - run * (i + 1), z - run * i, true);
    }
    const zEnd = z - run * flight;
    // side walls (the first flight's stop at the booking hall floor; parapets continue above)
    const top = first ? 0.12 : y + headroom + 0.4;
    b.box('tile', sx - half - 0.3, sx - half, y - rise * flight - 0.3, top, zEnd, z, true);
    b.box('tile', sx + half, sx + half + 0.3, y - rise * flight - 0.3, top, zEnd, z, true);
    // sloped tiled soffit parallel to the stairs (from under the hall floor for the first flight)
    const za = first ? holeNorth : z;
    const ya = y - (z - za) * slope + headroom;
    const yb = y - rise * flight + headroom;
    const A = (xx: number, yy: number, zz: number): THREE.Vector3 => new THREE.Vector3(xx, yy, zz);
    b.quad('tile', A(sx + half, ya, za), A(sx - half, ya, za), A(sx - half, yb, zEnd), A(sx + half, yb, zEnd));
    // tiled header from the hall floor slab down to the soffit
    if (first) b.box('tile', sx - half - 0.3, sx + half + 0.3, ya, -0.2, za - 0.3, za);
    // stepped colliders under the soffit so a jump cannot leave the shaft
    for (let zz = za; zz > zEnd; zz -= 1.0) {
      const yy = y - (z - zz) * slope + headroom;
      b.collider(sx - half, sx + half, yy - 0.05, yy + 0.4, zz - 1.0, zz);
    }
    // handrails
    for (const sd of [-1, 1]) {
      const len = Math.hypot(run * flight, rise * flight);
      const rail = new THREE.CylinderGeometry(0.025, 0.025, len, 6);
      rail.rotateX(Math.atan2(run * flight, rise * flight));
      b.geo('brass', rail, new THREE.Matrix4().makeTranslation(sx + sd * (half - 0.08), y - (rise * flight) / 2 + 0.9, z - (run * flight) / 2));
    }
    y -= rise * flight;
    z = zEnd;
    navStairs.push(new THREE.Vector3(sx, y, z - 0.4));
  };
  // the opening in the booking hall floor has a low tiled parapet on three sides
  b.box('tile', sx - half - 0.3, sx + half + 0.3, 0.12, 1.05, holeNorth - 0.3, holeNorth, true);
  b.box('tile', sx - half - 0.3, sx - half, 0.12, 1.05, holeNorth - 0.3, zTop, true);
  b.box('tile', sx + half, sx + half + 0.3, 0.12, 1.05, holeNorth - 0.3, zTop, true);
  stairFlight(true);
  // landing
  b.box('platform', sx - half, sx + half, y - 0.25, y, z - 1.6, z, true);
  b.box('tile', sx - half - 0.3, sx - half, y - 0.3, y + headroom + 0.4, z - 1.6, z, true);
  b.box('tile', sx + half, sx + half + 0.3, y - 0.3, y + headroom + 0.4, z - 1.6, z, true);
  b.box('tile', sx - half - 0.3, sx + half + 0.3, y + headroom, y + headroom + 0.3, z - 1.6, z, true);
  // end wall of the landing above the second flight's head
  b.box('tile', sx - half - 0.3, sx + half + 0.3, y + headroom, y + headroom + 4.6, z + 0.0, z + 0.3);
  z -= 1.6;
  stairFlight(false);
  const stairBottom = new THREE.Vector3(sx, y, z);
  // cross passage north into the platform tunnel
  const tz = TUBE.platform.z; // tunnel axis z
  const R = 3.6;
  const yc = y + 1.0; // tunnel centre height (platform at y)
  const backZ = tz + Math.sqrt(R * R - 1.0); // where the platform meets the vault (south side)
  const portalZ = tz + 1.9; // passage walls run into the tunnel to here
  const passH = 2.8;
  // step from the soffit down to the passage ceiling, then the passage itself
  b.box('tile', sx - half - 0.3, sx + half + 0.3, y + passH, y + headroom + 0.3, z - 0.3, z);
  b.box('platform', sx - half, sx + half, y - 0.25, y, portalZ, z, true);
  b.box('tile', sx - half - 0.3, sx - half, y, y + passH, portalZ, z, true);
  b.box('tile', sx + half, sx + half + 0.3, y, y + passH, portalZ, z, true);
  b.box('tile', sx - half - 0.3, sx + half + 0.3, y + passH, y + passH + 0.3, portalZ, z, true);
  // header over the portal fills the cut in the vault above the passage
  b.box('tile', sx - half - 0.3, sx + half + 0.3, y + passH, yc + R - 0.6, portalZ, tz + R + 0.2);
  navStairs.push(new THREE.Vector3(sx, y, backZ - 0.8));
  // platform tunnel: inner tiled vault (cylinder shell along x), platform slab, track bed
  const { x0, x1 } = TUBE.platform;
  const cutX0 = sx - half - 0.3;
  const cutX1 = sx + half + 0.3;
  const vaultPiece = (xa: number, xb: number, cut: boolean): void => {
    const l = xb - xa;
    if (l <= 0.01) return;
    const v = new THREE.CylinderGeometry(R, R, l, 40, 1, true).toNonIndexed();
    v.rotateZ(Math.PI / 2);
    const pos = v.attributes.position as THREE.BufferAttribute;
    const uvA = v.attributes.uv as THREE.BufferAttribute;
    // flip winding so the tiles face inward; world-scale UVs (around, along)
    const tile = b.tileOf('tile');
    for (let i = 0; i < pos.count; i++) uvA.setXY(i, (uvA.getX(i) * Math.PI * 2 * R) / tile, (pos.getX(i) + xa + l / 2) / tile);
    for (let i = 0; i < pos.count; i += 3) {
      for (const a of [pos, uvA]) {
        for (let c = 0; c < a.itemSize; c++) {
          const t = a.getComponent(i + 1, c);
          a.setComponent(i + 1, c, a.getComponent(i + 2, c));
          a.setComponent(i + 2, c, t);
        }
      }
    }
    if (cut) {
      // drop the triangles where the cross passage enters (south wall, below the header)
      const keepPos: number[] = [];
      const keepUv: number[] = [];
      for (let i = 0; i < pos.count; i += 3) {
        const cy = (pos.getY(i) + pos.getY(i + 1) + pos.getY(i + 2)) / 3;
        const cz = (pos.getZ(i) + pos.getZ(i + 1) + pos.getZ(i + 2)) / 3;
        if (cz > 1.9 && cy < 2.3) continue;
        for (const k of [0, 1, 2]) {
          keepPos.push(pos.getX(i + k), pos.getY(i + k), pos.getZ(i + k));
          keepUv.push(uvA.getX(i + k), uvA.getY(i + k));
        }
      }
      v.setAttribute('position', new THREE.Float32BufferAttribute(keepPos, 3));
      v.setAttribute('uv', new THREE.Float32BufferAttribute(keepUv, 2));
    }
    v.deleteAttribute('normal');
    v.computeVertexNormals();
    b.geo('tile', v, new THREE.Matrix4().makeTranslation((xa + xb) / 2, yc, tz));
  };
  vaultPiece(x0, cutX0, false);
  vaultPiece(cutX0, cutX1, true);
  vaultPiece(cutX1, x1, false);
  // platform slab (south half) and its edge
  const edgeZ = tz - 0.2;
  b.box('platform', x0, x1, y - 1.0, y, edgeZ, backZ + 0.05, true);
  b.box('paint', x0, x1, y + 0.001, y + 0.004, edgeZ, edgeZ + 0.25); // painted platform edge
  // track bed and rails (north half, lower)
  const trackY = y - 1.05;
  b.box('ballast', x0, x1, trackY - 0.2, trackY, tz - R + 0.2, edgeZ, true);
  for (const dz of [-0.72, 0.72, -1.6]) b.box('metal', x0, x1, trackY, trackY + 0.15, tz - 1.2 + dz - 0.04, tz - 1.2 + dz + 0.04);
  for (let x = x0; x < x1; x += 0.7) b.box('timber', x, x + 0.25, trackY - 0.02, trackY + 0.04, tz - R + 0.8, edgeZ - 0.3);
  // keep shelterers and the player on the platform (current was off at night, but the track is out of bounds)
  b.collider(x0, x1, y, y + 2.2, edgeZ - 0.15, edgeZ);
  // tunnel ends: blank tiled walls with dark tunnel mouths
  for (const xe of [x0, x1]) {
    b.box('tile', xe - 0.3, xe, y - 1.3, yc + R, tz - R, tz + R, true);
  }
  // lamps along the vault crown (dimmed shelter lighting)
  const lamps: THREE.Vector3[] = [];
  for (let x = x0 + 4; x < x1 - 2; x += 9) lamps.push(new THREE.Vector3(x, yc + R - 0.5, tz + 1.0));
  return {
    platform: { x0: x0 + 1, x1: x1 - 1, zBack: backZ - 0.35, zEdge: edgeZ + 0.6, y },
    stairBottom,
    passageEnd: new THREE.Vector3(sx, y, backZ - 0.5),
    lampPositions: lamps,
    box: new THREE.Box3(new THREE.Vector3(x0 - 1, y - 2, tz - R - 1), new THREE.Vector3(Math.max(x1, sx + 3) + 1, -0.3, zTop + 0.5)),
    stairs: navStairs,
  };
}
