import * as THREE from 'three';
import { Rng } from '../../core/Random';

/**
 * Night raid sky dressing: searchlight beams sweeping the clouds, anti-aircraft shell bursts,
 * barrage balloons and the silhouettes of dock cranes and warehouses against the glow of the fires.
 * Everything here is far away, unlit (basic/additive materials) and ignores fog, so it reads through
 * the smoke haze like the real thing.
 */
export class RaidSky {
  readonly group = new THREE.Group();
  private beams: { mesh: THREE.Mesh; base: number; speed: number; tilt: number; phase: number }[] = [];
  private beamMat: THREE.ShaderMaterial;
  private bursts: THREE.InstancedMesh;
  private burstLife: Float32Array;
  private burstPos: THREE.Vector3[] = [];
  private burstMat: THREE.ShaderMaterial;
  private dummy = new THREE.Object3D();
  private rng = new Rng(4011);
  private nextBurst = 0;
  /** 0..1 — fades beams and flak for dawn. */
  intensity = 1;
  /** Raid activity (flak rate). */
  activity = 1;
  onBurst: ((p: THREE.Vector3) => void) | null = null;

  constructor(track: <T extends { dispose(): void }>(x: T) => T) {
    this.group.name = 'raid-sky';
    // ---- searchlights: long cones, brightest at the source, soft edges
    this.beamMat = track(
      new THREE.ShaderMaterial({
        uniforms: { uI: { value: 1 } },
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
        fragmentShader: /* glsl */ `
          uniform float uI;
          varying vec2 vUv;
          void main() {
            float edge = sin(vUv.x * 3.14159);
            float along = pow(1.0 - vUv.y, 1.6) * 0.85 + 0.15;
            float a = edge * edge * along * 0.11 * uI;
            gl_FragColor = vec4(vec3(0.82, 0.86, 0.95) * a, a);
          }`,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        fog: false,
      }),
    );
    const beamGeo = track(new THREE.CylinderGeometry(9, 0.6, 520, 16, 1, true));
    beamGeo.translate(0, 260, 0);
    const srcs: [number, number][] = [
      [-260, 240],
      [140, 330],
      [380, -120],
      [-380, -260],
      [60, -420],
    ];
    srcs.forEach(([x, z], i) => {
      const m = new THREE.Mesh(beamGeo, this.beamMat);
      m.position.set(x, -20, z);
      m.frustumCulled = false;
      m.renderOrder = 4;
      this.group.add(m);
      this.beams.push({ mesh: m, base: this.rng.range(0, Math.PI * 2), speed: this.rng.range(0.05, 0.11) * (i % 2 ? 1 : -1), tilt: this.rng.range(0.35, 0.6), phase: this.rng.range(0, 10) });
    });

    // ---- flak bursts: brief flashes high up, followed by smoke smudges (handled via onBurst)
    this.burstMat = track(
      new THREE.ShaderMaterial({
        vertexShader: /* glsl */ `
          attribute float aLife;
          varying float vLife;
          varying vec2 vUv;
          void main() {
            vUv = uv; vLife = aLife;
            vec4 mv = modelViewMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
            float s = instanceMatrix[0][0];
            mv.xy += position.xy * s;
            gl_Position = projectionMatrix * mv;
          }`,
        fragmentShader: /* glsl */ `
          varying float vLife;
          varying vec2 vUv;
          void main() {
            float d = length(vUv - 0.5) * 2.0;
            float a = smoothstep(1.0, 0.0, d) * vLife;
            gl_FragColor = vec4(vec3(1.0, 0.86, 0.6) * a * 2.0, a);
          }`,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        fog: false,
      }),
    );
    const n = 24;
    const bg = track(new THREE.PlaneGeometry(1, 1));
    this.burstLife = new Float32Array(n);
    bg.setAttribute('aLife', new THREE.InstancedBufferAttribute(this.burstLife, 1));
    this.bursts = new THREE.InstancedMesh(bg, this.burstMat, n);
    this.bursts.frustumCulled = false;
    this.bursts.renderOrder = 5;
    for (let i = 0; i < n; i++) this.burstPos.push(new THREE.Vector3());
    this.group.add(this.bursts);

    // ---- barrage balloons: dark envelopes with three fins, tethered high over the docks
    const balloonMat = track(new THREE.MeshBasicMaterial({ color: 0x15151b, fog: false }));
    const env = track(new THREE.SphereGeometry(1, 16, 10));
    env.scale(7.5, 3.0, 3.0);
    const fin = track(new THREE.BoxGeometry(3.4, 0.15, 3.2));
    for (const [x, y, z, r] of [
      [-180, 260, 260, 0.4],
      [40, 300, 340, -0.3],
      [260, 280, 220, 1.2],
      [-320, 240, 80, 2.0],
      [180, 320, -280, 0.8],
    ] as [number, number, number, number][]) {
      const g = new THREE.Group();
      const e = new THREE.Mesh(env, balloonMat);
      g.add(e);
      for (const a of [0, Math.PI / 2, -Math.PI / 2]) {
        const f = new THREE.Mesh(fin, balloonMat);
        f.position.set(-7.2, 0, 0);
        f.rotation.x = a;
        f.position.y += Math.cos(a) * 1.6;
        f.position.z += Math.sin(a) * 1.6;
        g.add(f);
      }
      g.position.set(x, y, z);
      g.rotation.y = r;
      g.userData.bob = this.rng.range(0, 10);
      g.traverse((o) => (o.frustumCulled = false));
      this.group.add(g);
      this.balloons.push(g);
    }
  }

  private balloons: THREE.Object3D[] = [];

  update(dt: number, time: number, camera: THREE.Camera): void {
    this.beamMat.uniforms.uI.value = this.intensity;
    for (const b of this.beams) {
      const yaw = b.base + time * b.speed + Math.sin(time * 0.13 + b.phase) * 0.4;
      const tilt = b.tilt + Math.sin(time * 0.21 + b.phase) * 0.12;
      b.mesh.rotation.set(0, 0, 0);
      b.mesh.rotateY(yaw);
      b.mesh.rotateX(tilt);
      b.mesh.visible = this.intensity > 0.02;
    }
    for (const g of this.balloons) g.position.y += Math.sin(time * 0.3 + g.userData.bob) * dt * 0.4;
    // bursts
    this.nextBurst -= dt;
    if (this.nextBurst <= 0 && this.intensity > 0.3 && this.activity > 0) {
      this.nextBurst = this.rng.range(0.25, 1.4) / this.activity;
      const i = this.burstLife.indexOf(Math.min(...this.burstLife));
      const ang = this.rng.range(-1.3, 1.3);
      const d = this.rng.range(250, 520);
      // mostly over the docks (south) and the river
      this.burstPos[i].set(Math.sin(ang) * d, this.rng.range(160, 330), Math.cos(ang) * d);
      this.burstLife[i] = 1;
      this.onBurst?.(this.burstPos[i]);
    }
    const q = camera.quaternion;
    for (let i = 0; i < this.burstLife.length; i++) {
      this.burstLife[i] = Math.max(0, this.burstLife[i] - dt * 5);
      this.dummy.position.copy(this.burstPos[i]);
      this.dummy.quaternion.copy(q);
      this.dummy.scale.setScalar(this.burstLife[i] > 0 ? 9 + (1 - this.burstLife[i]) * 6 : 0.0001);
      this.dummy.updateMatrix();
      this.bursts.setMatrixAt(i, this.dummy.matrix);
    }
    this.bursts.instanceMatrix.needsUpdate = true;
    (this.bursts.geometry.attributes.aLife as THREE.BufferAttribute).needsUpdate = true;
  }
}

/**
 * Dockland silhouettes to the south: warehouses, cranes and chimneys, dark against the glow.
 * Returns positions where large fires burn (for the fire system).
 */
export function buildDocklands(group: THREE.Group, track: <T extends { dispose(): void }>(x: T) => T): THREE.Vector3[] {
  const rng = new Rng(1888);
  const mat = track(new THREE.MeshBasicMaterial({ color: 0x0d0b0d, fog: false }));
  const parts: THREE.BufferGeometry[] = [];
  const fires: THREE.Vector3[] = [];
  const add = (g: THREE.BufferGeometry, m: THREE.Matrix4): void => {
    const c = g.index ? g.toNonIndexed() : g;
    c.applyMatrix4(m);
    c.deleteAttribute('uv');
    c.deleteAttribute('normal');
    parts.push(c);
    if (c !== g) g.dispose();
  };
  // warehouse blocks along an arc to the south (z 150..320)
  for (let i = 0; i < 26; i++) {
    const a = -1.15 + (i / 25) * 2.3 + rng.range(-0.03, 0.03);
    const d = rng.range(170, 300);
    const w = rng.range(24, 60);
    const h = rng.range(14, 30);
    const x = Math.sin(a) * d;
    const z = Math.cos(a) * d;
    add(new THREE.BoxGeometry(w, h, rng.range(18, 30)), new THREE.Matrix4().makeRotationY(a + rng.range(-0.2, 0.2)).setPosition(x, h / 2 - 2, z));
    // gabled roofs on some
    if (rng.chance(0.5)) {
      const r = new THREE.CylinderGeometry(0.01, w * 0.55, 5, 4, 1);
      r.rotateY(Math.PI / 4);
      r.scale(1, 1, 0.5);
      add(r, new THREE.Matrix4().makeRotationY(a).setPosition(x, h - 2 + 2.5, z));
    }
    if (rng.chance(0.45)) fires.push(new THREE.Vector3(x + rng.range(-8, 8), h - 2, z));
  }
  // cranes (jib + tower) and chimneys
  for (let i = 0; i < 9; i++) {
    const a = -0.9 + (i / 8) * 1.8 + rng.range(-0.05, 0.05);
    const d = rng.range(210, 270);
    const x = Math.sin(a) * d;
    const z = Math.cos(a) * d;
    const h = rng.range(26, 38);
    add(new THREE.BoxGeometry(1.4, h, 1.4), new THREE.Matrix4().makeTranslation(x, h / 2, z));
    const jib = rng.range(18, 30);
    add(new THREE.BoxGeometry(jib, 1.0, 1.0), new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(0, rng.range(0, Math.PI), rng.range(0.1, 0.35))).setPosition(x, h + 1, z));
    add(new THREE.BoxGeometry(4, 3, 4), new THREE.Matrix4().makeTranslation(x, h - 1, z));
  }
  for (let i = 0; i < 6; i++) {
    const a = rng.range(-1.2, 1.2);
    const d = rng.range(160, 320);
    const h = rng.range(30, 50);
    add(new THREE.CylinderGeometry(1.6, 2.4, h, 8), new THREE.Matrix4().makeTranslation(Math.sin(a) * d, h / 2, Math.cos(a) * d));
  }
  // roofline of the streets in between (low terraces) all round
  for (let i = 0; i < 90; i++) {
    const a = rng.range(0, Math.PI * 2);
    const d = rng.range(95, 160);
    const h = rng.range(7, 12);
    const w = rng.range(14, 36);
    add(new THREE.BoxGeometry(w, h, 8), new THREE.Matrix4().makeRotationY(a + Math.PI / 2 + rng.range(-0.2, 0.2)).setPosition(Math.sin(a) * d, h / 2 - 1, Math.cos(a) * d));
  }
  // a church spire to the north-west for orientation
  add(new THREE.BoxGeometry(6, 26, 6), new THREE.Matrix4().makeTranslation(-110, 13, -150));
  add(new THREE.ConeGeometry(4, 22, 4), new THREE.Matrix4().makeRotationY(Math.PI / 4).setPosition(-110, 37, -150));
  const n = parts.reduce((a, p) => a + p.attributes.position.count, 0);
  const pos = new Float32Array(n * 3);
  let o = 0;
  for (const p of parts) {
    pos.set(p.attributes.position.array as Float32Array, o);
    o += p.attributes.position.array.length;
    p.dispose();
  }
  const g = track(new THREE.BufferGeometry());
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const m = new THREE.Mesh(g, mat);
  m.frustumCulled = false;
  m.name = 'docklands';
  group.add(m);
  return fires;
}
