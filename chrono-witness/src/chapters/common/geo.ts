import * as THREE from 'three';

/** Box geometry whose UVs are in tiles (metres / tileMetres) on every face, so textures keep real-world scale. */
export function boxUV(w: number, h: number, d: number, tile = 1): THREE.BoxGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  const n = g.attributes.normal as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) {
    const nx = Math.abs(n.getX(i));
    const ny = Math.abs(n.getY(i));
    let sx: number;
    let sy: number;
    if (nx > 0.5) {
      sx = d;
      sy = h;
    } else if (ny > 0.5) {
      sx = w;
      sy = d;
    } else {
      sx = w;
      sy = h;
    }
    uv.setXY(i, (uv.getX(i) * sx) / tile, (uv.getY(i) * sy) / tile);
  }
  g.setAttribute('uv1', uv.clone());
  return g;
}

export function planeUV(w: number, h: number, tile = 1, segX = 1, segY = 1): THREE.PlaneGeometry {
  const g = new THREE.PlaneGeometry(w, h, segX, segY);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * w) / tile, (uv.getY(i) * h) / tile);
  return g;
}

/** Cylinder with UVs in tiles around the circumference and along the height. */
export function cylinderUV(rTop: number, rBot: number, h: number, seg: number, tile = 1, open = false): THREE.CylinderGeometry {
  const g = new THREE.CylinderGeometry(rTop, rBot, h, seg, 1, open);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  const circ = Math.PI * 2 * Math.max(rTop, rBot);
  for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * circ) / tile, (uv.getY(i) * h) / tile);
  return g;
}

/** Merge transformed geometries that share a material into one (fewer draw calls). */
export class GeoBatch {
  private parts: THREE.BufferGeometry[] = [];
  add(g: THREE.BufferGeometry, m?: THREE.Matrix4): this {
    const c = g.index ? g.toNonIndexed() : g.clone();
    if (m) c.applyMatrix4(m);
    // ensure consistent attributes
    if (!c.attributes.uv) c.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(c.attributes.position.count * 2), 2));
    for (const k of Object.keys(c.attributes)) if (k !== 'position' && k !== 'normal' && k !== 'uv' && k !== 'color') c.deleteAttribute(k);
    this.parts.push(c);
    if (c !== g) g.dispose();
    return this;
  }
  get empty(): boolean {
    return this.parts.length === 0;
  }
  build(withColor = false): THREE.BufferGeometry {
    const n = this.parts.reduce((a, p) => a + p.attributes.position.count, 0);
    const pos = new Float32Array(n * 3);
    const nor = new Float32Array(n * 3);
    const uv = new Float32Array(n * 2);
    const col = withColor ? new Float32Array(n * 3) : null;
    let o = 0;
    for (const p of this.parts) {
      const c = p.attributes.position.count;
      pos.set(p.attributes.position.array as Float32Array, o * 3);
      if (!p.attributes.normal) p.computeVertexNormals();
      nor.set(p.attributes.normal.array as Float32Array, o * 3);
      uv.set(p.attributes.uv.array as Float32Array, o * 2);
      if (col) {
        if (p.attributes.color) col.set(p.attributes.color.array as Float32Array, o * 3);
        else col.fill(1, o * 3, (o + c) * 3);
      }
      o += c;
      p.dispose();
    }
    this.parts = [];
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    if (col) g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    g.computeBoundingSphere();
    g.computeBoundingBox();
    return g;
  }
}

export function mat4(x: number, y: number, z: number, ry = 0, rx = 0, rz = 0, s: number | [number, number, number] = 1): THREE.Matrix4 {
  const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(rx, ry, rz, 'YXZ'));
  const sc = typeof s === 'number' ? new THREE.Vector3(s, s, s) : new THREE.Vector3(...s);
  return new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), q, sc);
}

/** Canvas texture helper for in-world screens, signs and labels. */
export function canvasTexture(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d')!;
  draw(ctx);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}
