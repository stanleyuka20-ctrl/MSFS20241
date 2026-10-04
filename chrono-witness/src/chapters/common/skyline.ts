import * as THREE from 'three';
import { Rng } from '../../core/Random';

/**
 * Distant city blocks around the playable area: simple boxes with jagged (ruined) or flat tops,
 * window holes suggested by darker bands, fading into the haze. One draw call.
 */
export function buildSkyline(
  parent: THREE.Object3D,
  track: <T extends { dispose(): void }>(x: T) => T,
  opts: { center: THREE.Vector2; rMin: number; rMax: number; count: number; hMin: number; hMax: number; color: number; ruined?: number; seed?: number; exclude?: (x: number, z: number) => boolean },
): THREE.Mesh {
  const rng = new Rng(opts.seed ?? 9);
  const parts: THREE.BufferGeometry[] = [];
  for (let i = 0; i < opts.count; i++) {
    const a = rng.next() * Math.PI * 2;
    const d = opts.rMin + rng.next() * (opts.rMax - opts.rMin);
    const x = opts.center.x + Math.cos(a) * d;
    const z = opts.center.y + Math.sin(a) * d;
    if (opts.exclude?.(x, z)) continue;
    const w = 10 + rng.next() * 26;
    const h = opts.hMin + rng.next() * (opts.hMax - opts.hMin);
    const ruined = rng.chance(opts.ruined ?? 0);
    const segs = ruined ? 6 : 1;
    const g = new THREE.BoxGeometry(w, h, 10, segs, 1, 1);
    if (ruined) {
      const p = g.attributes.position as THREE.BufferAttribute;
      for (let k = 0; k < p.count; k++) if (p.getY(k) > 0) p.setY(k, p.getY(k) - rng.next() * h * 0.45);
    }
    g.translate(0, h / 2 - 0.5, 0);
    g.rotateY(-a + Math.PI / 2 + (rng.next() - 0.5) * 0.3);
    g.translate(x, 0, z);
    const ng = g.toNonIndexed();
    g.dispose();
    parts.push(ng);
  }
  const n = parts.reduce((s, p) => s + p.attributes.position.count, 0);
  const pos = new Float32Array(n * 3);
  const nor = new Float32Array(n * 3);
  let o = 0;
  for (const p of parts) {
    pos.set(p.attributes.position.array as Float32Array, o);
    nor.set(p.attributes.normal.array as Float32Array, o);
    o += p.attributes.position.array.length;
    p.dispose();
  }
  const geo = track(new THREE.BufferGeometry());
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  const mat = track(new THREE.MeshLambertMaterial({ color: opts.color }));
  const m = new THREE.Mesh(geo, mat);
  m.name = 'skyline';
  parent.add(m);
  return m;
}
