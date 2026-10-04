import * as THREE from 'three';

export interface FireSource {
  pos: THREE.Vector3;
  size: number;
  /** 0..1, fades flames in/out (e.g. an incendiary smothered with sand). */
  intensity: number;
  /** Incendiary magnesium fire burns white-hot; house fires are orange. */
  kind: 'incendiary' | 'house' | 'distant';
  seed: number;
}

/**
 * Fires drawn as camera-facing flipbook quads (8×8 atlas) with additive blending, plus the
 * information the runtime uses to drive a small pool of flickering point lights. Fixed capacity.
 */
export class FireSystem {
  readonly sources: FireSource[] = [];
  readonly mesh: THREE.InstancedMesh;
  private readonly mat: THREE.ShaderMaterial;
  private dummy = new THREE.Object3D();
  private q = new THREE.Quaternion();
  private frameAttr: THREE.InstancedBufferAttribute;
  private tintAttr: THREE.InstancedBufferAttribute;

  constructor(readonly capacity: number, atlas: THREE.Texture | null) {
    const geo = new THREE.PlaneGeometry(1, 1);
    geo.translate(0, 0.5, 0);
    this.frameAttr = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 2), 2);
    this.tintAttr = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 4), 4);
    geo.setAttribute('aFrame', this.frameAttr);
    geo.setAttribute('aTint', this.tintAttr);
    const hasAtlas = !!atlas && (atlas.image as { width?: number })?.width! > 8;
    this.mat = new THREE.ShaderMaterial({
      uniforms: { tAtlas: { value: atlas }, uHas: { value: hasAtlas ? 1 : 0 }, uTime: { value: 0 } },
      vertexShader: /* glsl */ `
        attribute vec2 aFrame;
        attribute vec4 aTint;
        varying vec2 vUv;
        varying vec4 vTint;
        varying float vBlend;
        varying vec2 vF;
        void main() {
          vUv = uv;
          vTint = aTint;
          vF = aFrame;
          gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform sampler2D tAtlas;
        uniform float uHas, uTime;
        varying vec2 vUv;
        varying vec4 vTint;
        varying vec2 vF;
        float hash(vec2 p) { return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5); }
        float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
          return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
        void main() {
          vec4 c;
          if (uHas > 0.5) {
            float fr = floor(vF.x);
            vec2 cell = vec2(mod(fr, 8.0), floor(fr / 8.0));
            vec2 uv = (cell + vec2(vUv.x, 1.0 - vUv.y)) / 8.0;
            c = texture2D(tAtlas, uv);
          } else {
            // procedural flame: tapered, turbulent, hotter at the base
            vec2 p = vUv;
            float n = noise(vec2(p.x * 6.0, p.y * 4.0 - uTime * 3.0 - vF.y)) * 0.6 + noise(vec2(p.x * 13.0, p.y * 9.0 - uTime * 5.0)) * 0.4;
            float width = (1.0 - p.y) * 0.45 + 0.05;
            float m = smoothstep(width, width * 0.3, abs(p.x - 0.5) + (n - 0.5) * 0.25) * smoothstep(1.0, 0.25, p.y + n * 0.3) * smoothstep(0.0, 0.06, p.y);
            vec3 col = mix(vec3(1.0, 0.85, 0.5), vec3(1.0, 0.35, 0.05), p.y + n * 0.3);
            c = vec4(col, m);
          }
          float a = c.a * vTint.a;
          gl_FragColor = vec4(c.rgb * vTint.rgb * a * 2.2, a);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      fog: false,
    });
    this.mesh = new THREE.InstancedMesh(geo, this.mat, capacity);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 6;
    this.mesh.count = 0;
  }

  add(pos: THREE.Vector3, size: number, kind: FireSource['kind']): FireSource {
    const s: FireSource = { pos: pos.clone(), size, intensity: 1, kind, seed: Math.random() * 100 };
    this.sources.push(s);
    return s;
  }

  remove(s: FireSource): void {
    const i = this.sources.indexOf(s);
    if (i >= 0) this.sources.splice(i, 1);
  }

  update(time: number, camera: THREE.Camera): void {
    camera.getWorldQuaternion(this.q);
    // cylindrical billboard: keep flames upright
    const e = new THREE.Euler().setFromQuaternion(this.q, 'YXZ');
    this.dummy.rotation.set(0, e.y, 0);
    this.mat.uniforms.uTime.value = time;
    let n = 0;
    for (const s of this.sources) {
      if (s.intensity <= 0.01) continue;
      const layers = s.kind === 'house' ? 3 : s.kind === 'distant' ? 2 : 2;
      for (let l = 0; l < layers && n < this.capacity; l++) {
        const flick = 0.85 + Math.sin(time * 9 + s.seed + l) * 0.08 + Math.sin(time * 23 + s.seed * 2) * 0.07;
        const sz = s.size * (1 - l * 0.22) * flick;
        this.dummy.position.set(s.pos.x + (l - 1) * s.size * 0.18, s.pos.y, s.pos.z + Math.sin(s.seed + l) * s.size * 0.1);
        this.dummy.scale.set(sz * 0.75, sz * (s.kind === 'incendiary' ? 0.9 : 1.3), 1);
        this.dummy.updateMatrix();
        this.mesh.setMatrixAt(n, this.dummy.matrix);
        this.frameAttr.setXY(n, Math.floor(time * 24 + s.seed * 7 + l * 21) % 64, s.seed + l);
        const t = s.kind === 'incendiary' ? [1.0, 0.95, 0.85] : [1.0, 0.62, 0.3];
        this.tintAttr.setXYZW(n, t[0], t[1], t[2], s.intensity * (s.kind === 'distant' ? 0.8 : 1));
        n++;
      }
    }
    this.mesh.count = n;
    this.mesh.instanceMatrix.needsUpdate = true;
    this.frameAttr.needsUpdate = true;
    this.tintAttr.needsUpdate = true;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    this.mat.dispose();
  }
}
