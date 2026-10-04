import * as THREE from 'three';
import { GeoBatch } from './geo';

/**
 * Architectural builder: accumulates boxes, sloped quads and walls with openings in a local frame,
 * with world-scale UVs (metres / tile), into per-material batches. Used for buildings whose parts are
 * axis-aligned in their own frame (terraces, stations, interiors).
 */
export interface Collider {
  c: THREE.Vector3;
  s: THREE.Vector3;
  r: number;
}

export interface Rect {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

export class Builder {
  readonly batches = new Map<string, GeoBatch>();
  readonly colliders: Collider[] = [];
  /** Local → world transform (rotation about Y + translation). */
  matrix = new THREE.Matrix4();
  rotY = 0;
  private readonly tiles: Record<string, number>;
  /** Material key → texture set name (for tile size lookup). */
  private readonly setOf: Record<string, string>;

  constructor(tiles: Record<string, number>, setOf: Record<string, string>) {
    this.tiles = tiles;
    this.setOf = setOf;
  }

  setFrame(x: number, z: number, rotY: number, y = 0): void {
    this.rotY = rotY;
    this.matrix.makeRotationY(rotY).setPosition(x, y, z);
  }

  /** Texture tile size (metres) for a material key. */
  tileOf(key: string): number {
    return this.tile(key);
  }

  private tile(key: string): number {
    return this.tiles[this.setOf[key] ?? key] ?? 1;
  }

  private batch(key: string): GeoBatch {
    let b = this.batches.get(key);
    if (!b) this.batches.set(key, (b = new GeoBatch()));
    return b;
  }

  /** Axis-aligned box in local space with world-scale UVs on every face. */
  box(key: string, x0: number, x1: number, y0: number, y1: number, z0: number, z1: number, collide = false, uOff = 0): void {
    // accept corners in either order (mirrored layouts compute them as wall ± offset)
    if (x0 > x1) [x0, x1] = [x1, x0];
    if (y0 > y1) [y0, y1] = [y1, y0];
    if (z0 > z1) [z0, z1] = [z1, z0];
    const w = x1 - x0;
    const h = y1 - y0;
    const d = z1 - z0;
    if (w <= 1e-4 || h <= 1e-4 || d <= 1e-4) return;
    const g = new THREE.BoxGeometry(w, h, d);
    const t = this.tile(key);
    const uv = g.attributes.uv as THREE.BufferAttribute;
    const n = g.attributes.normal as THREE.BufferAttribute;
    const p = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < uv.count; i++) {
      const lx = p.getX(i) + (x0 + x1) / 2;
      const ly = p.getY(i) + (y0 + y1) / 2;
      const lz = p.getZ(i) + (z0 + z1) / 2;
      const ax = Math.abs(n.getX(i));
      const ay = Math.abs(n.getY(i));
      if (ax > 0.5) uv.setXY(i, lz / t, ly / t);
      else if (ay > 0.5) uv.setXY(i, (lx + uOff) / t, lz / t);
      else uv.setXY(i, (lx + uOff) / t, ly / t);
    }
    g.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    this.batch(key).add(g, this.matrix);
    if (collide) this.collider(x0, x1, y0, y1, z0, z1);
  }

  /** Collision box in local space. */
  collider(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number): void {
    if (x0 > x1) [x0, x1] = [x1, x0];
    if (z0 > z1) [z0, z1] = [z1, z0];
    const c = new THREE.Vector3((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2).applyMatrix4(this.matrix);
    this.colliders.push({ c, s: new THREE.Vector3(x1 - x0, y1 - y0, z1 - z0), r: this.rotY });
  }

  /**
   * Wall in the local XY plane between z0 (outer face) and z1, from x0..x1 and y0..y1, with
   * rectangular openings that have real reveals. Optionally collidable (openings stay open).
   */
  wall(key: string, x0: number, x1: number, y0: number, y1: number, z0: number, z1: number, openings: Rect[], collide = true): void {
    const xs = new Set<number>([x0, x1]);
    for (const o of openings) {
      if (o.x0 > x0 && o.x0 < x1) xs.add(o.x0);
      if (o.x1 > x0 && o.x1 < x1) xs.add(o.x1);
    }
    const sorted = [...xs].sort((a, b) => a - b);
    for (let i = 0; i < sorted.length - 1; i++) {
      const xa = sorted[i];
      const xb = sorted[i + 1];
      const mid = (xa + xb) / 2;
      const cuts = openings.filter((o) => mid > o.x0 && mid < o.x1).sort((a, b) => a.y0 - b.y0);
      let y = y0;
      for (const c of cuts) {
        if (c.y0 > y) this.box(key, xa, xb, y, Math.min(c.y0, y1), Math.min(z0, z1), Math.max(z0, z1), collide);
        y = Math.max(y, c.y1);
      }
      if (y < y1) this.box(key, xa, xb, y, y1, Math.min(z0, z1), Math.max(z0, z1), collide);
    }
  }

  /** Quad from 4 local points (counter-clockwise seen from the front), UV by local axes u (along a) and v (along b). */
  quad(key: string, a: THREE.Vector3, b: THREE.Vector3, c: THREE.Vector3, d: THREE.Vector3, uLen?: number, vLen?: number): void {
    const t = this.tile(key);
    const ul = uLen ?? a.distanceTo(b);
    const vl = vLen ?? a.distanceTo(d);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute([a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z, a.x, a.y, a.z, c.x, c.y, c.z, d.x, d.y, d.z], 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, ul / t, 0, ul / t, vl / t, 0, 0, ul / t, vl / t, 0, vl / t], 2));
    g.computeVertexNormals();
    this.batch(key).add(g, this.matrix);
  }

  /** Arbitrary local-space geometry with a local transform. */
  geo(key: string, g: THREE.BufferGeometry, local?: THREE.Matrix4): void {
    if (local) g.applyMatrix4(local);
    this.batch(key).add(g, this.matrix);
  }

  /** World position of a local point. */
  world(x: number, y: number, z: number, out = new THREE.Vector3()): THREE.Vector3 {
    return out.set(x, y, z).applyMatrix4(this.matrix);
  }
}
