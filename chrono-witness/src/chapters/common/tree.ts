import * as THREE from 'three';
import { canvasTexture } from './geo';
import { Rng } from '../../core/Random';

/**
 * Broadleaf tree: tapered trunk with a few limbs and a crown of crossed leaf cards (alpha-tested
 * canvas texture of leaf clusters). Reads as a real tree at street distances without a
 * texture asset. Returns a group; materials are tracked by the caller via `track`.
 */
export function leafTexture(track: <T extends { dispose(): void }>(x: T) => T, season: 'spring' | 'summer' = 'spring'): THREE.Texture {
  const rng = new Rng(77);
  const tex = track(
    canvasTexture(256, 256, (c) => {
      c.clearRect(0, 0, 256, 256);
      const base = season === 'spring' ? [96, 138, 52] : [62, 98, 40];
      for (let i = 0; i < 140; i++) {
        const x = 20 + rng.next() * 216;
        const y = 20 + rng.next() * 216;
        const dx = x - 128;
        const dy = y - 128;
        if (dx * dx + dy * dy > 115 * 115) continue;
        const s = 7 + rng.next() * 9;
        const a = rng.next() * Math.PI * 2;
        const k = 0.75 + rng.next() * 0.5;
        c.fillStyle = `rgb(${Math.round(base[0] * k)},${Math.round(base[1] * k)},${Math.round(base[2] * k)})`;
        c.beginPath();
        c.ellipse(x, y, s, s * 0.55, a, 0, Math.PI * 2);
        c.fill();
      }
    }),
  );
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function makeTree(opts: { height: number; crown: number; seed: number; leafMat: THREE.Material; barkMat: THREE.Material; cards?: number }): THREE.Group {
  const rng = new Rng(opts.seed);
  const g = new THREE.Group();
  const H = opts.height;
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.3, H * 0.55, 10), opts.barkMat);
  trunk.position.y = H * 0.275;
  trunk.castShadow = true;
  g.add(trunk);
  for (let i = 0; i < 4; i++) {
    const len = H * (0.25 + rng.next() * 0.15);
    const limb = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.12, len, 6), opts.barkMat);
    const a = (i / 4) * Math.PI * 2 + rng.next();
    limb.position.set(Math.cos(a) * len * 0.3, H * 0.55 + len * 0.35, Math.sin(a) * len * 0.3);
    limb.rotation.set(Math.sin(a) * 0.6, 0, -Math.cos(a) * 0.6);
    limb.castShadow = true;
    g.add(limb);
  }
  // crown: crossed cards scattered in an ellipsoid
  const n = opts.cards ?? 70;
  const geos: THREE.BufferGeometry[] = [];
  for (let i = 0; i < n; i++) {
    const u = rng.next() * Math.PI * 2;
    const v = Math.acos(2 * rng.next() - 1);
    const r = Math.cbrt(rng.next()) * opts.crown;
    const p = new THREE.Vector3(Math.sin(v) * Math.cos(u) * r, Math.cos(v) * r * 0.7 + H * 0.72, Math.sin(v) * Math.sin(u) * r);
    const s = 1.1 + rng.next() * 0.9;
    for (const rot of [0, Math.PI / 2]) {
      const q = new THREE.PlaneGeometry(s, s);
      q.rotateY(rot + rng.next());
      q.rotateX((rng.next() - 0.5) * 0.8);
      q.translate(p.x, p.y, p.z);
      // normals pointing outwards from the crown centre: soft, volumetric shading
      const nrm = q.attributes.normal as THREE.BufferAttribute;
      const out = p.clone().sub(new THREE.Vector3(0, H * 0.72, 0)).normalize();
      for (let k = 0; k < nrm.count; k++) nrm.setXYZ(k, out.x, out.y * 0.5 + 0.5, out.z);
      geos.push(q);
    }
  }
  const pos: number[] = [];
  const nor: number[] = [];
  const uv: number[] = [];
  for (const q of geos) {
    const qi = q.toNonIndexed();
    pos.push(...(qi.attributes.position.array as Float32Array));
    nor.push(...(qi.attributes.normal.array as Float32Array));
    uv.push(...(qi.attributes.uv.array as Float32Array));
    q.dispose();
    qi.dispose();
  }
  const cg = new THREE.BufferGeometry();
  cg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  cg.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  cg.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  const crown = new THREE.Mesh(cg, opts.leafMat);
  crown.castShadow = true;
  crown.receiveShadow = true;
  g.add(crown);
  return g;
}
