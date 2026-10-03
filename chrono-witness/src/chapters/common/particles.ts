import * as THREE from 'three';

/**
 * Pooled soft particles (dust, smoke, dirt) rendered as one instanced, camera-facing quad mesh.
 * Capacity is fixed, so effects can never spawn unbounded particles.
 */
export class Puffs {
  readonly mesh: THREE.InstancedMesh;
  private pos: Float32Array;
  private vel: Float32Array;
  private life: Float32Array;
  private maxLife: Float32Array;
  private size: Float32Array;
  private grow: Float32Array;
  private alpha: THREE.InstancedBufferAttribute;
  private tint: THREE.InstancedBufferAttribute;
  private next = 0;
  private dummy = new THREE.Object3D();
  private q = new THREE.Quaternion();

  constructor(readonly capacity: number, texture: THREE.Texture | null) {
    const geo = new THREE.PlaneGeometry(1, 1);
    const mat = new THREE.MeshStandardMaterial({ map: texture ?? undefined, transparent: true, depthWrite: false, roughness: 1, metalness: 0, color: 0xffffff });
    this.alpha = new THREE.InstancedBufferAttribute(new Float32Array(capacity), 1);
    this.tint = new THREE.InstancedBufferAttribute(new Float32Array(capacity * 3).fill(1), 3);
    geo.setAttribute('aAlpha', this.alpha);
    geo.setAttribute('aTint', this.tint);
    mat.onBeforeCompile = (sh) => {
      sh.vertexShader = sh.vertexShader
        .replace('#include <common>', '#include <common>\nattribute float aAlpha;\nattribute vec3 aTint;\nvarying float vAlpha;\nvarying vec3 vTint;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nvAlpha = aAlpha;\nvTint = aTint;');
      sh.fragmentShader = sh.fragmentShader
        .replace('#include <common>', '#include <common>\nvarying float vAlpha;\nvarying vec3 vTint;')
        .replace('#include <map_fragment>', texture ? '#include <map_fragment>\ndiffuseColor.rgb *= vTint;\ndiffuseColor.a *= vAlpha;' : 'float dd = length(vMapUv - 0.5) * 2.0; diffuseColor.rgb *= vTint; diffuseColor.a *= vAlpha * smoothstep(1.0, 0.2, dd);');
    };
    mat.customProgramCacheKey = () => `puffs-${!!texture}`;
    this.mesh = new THREE.InstancedMesh(geo, mat, capacity);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 5;
    this.pos = new Float32Array(capacity * 3);
    this.vel = new Float32Array(capacity * 3);
    this.life = new Float32Array(capacity);
    this.maxLife = new Float32Array(capacity);
    this.size = new Float32Array(capacity);
    this.grow = new Float32Array(capacity);
    for (let i = 0; i < capacity; i++) {
      this.dummy.scale.setScalar(0);
      this.dummy.updateMatrix();
      this.mesh.setMatrixAt(i, this.dummy.matrix);
    }
  }

  emit(p: THREE.Vector3, v: THREE.Vector3, life: number, size: number, grow: number, tint: THREE.ColorRepresentation = 0xffffff, alpha = 0.6): void {
    const i = this.next;
    this.next = (this.next + 1) % this.capacity;
    this.pos.set([p.x, p.y, p.z], i * 3);
    this.vel.set([v.x, v.y, v.z], i * 3);
    this.life[i] = life;
    this.maxLife[i] = life;
    this.size[i] = size;
    this.grow[i] = grow;
    const c = _c.set(tint);
    this.tint.setXYZ(i, c.r, c.g, c.b);
    this.alpha.setX(i, alpha);
    (this.alpha as unknown as { base?: Float32Array }).base ??= new Float32Array(this.capacity);
    (this.alpha as unknown as { base: Float32Array }).base[i] = alpha;
  }

  burst(center: THREE.Vector3, count: number, spread: number, up: number, life: number, size: number, tint: THREE.ColorRepresentation, alpha = 0.55): void {
    for (let k = 0; k < count; k++) {
      _v.set((Math.random() - 0.5) * spread, Math.random() * up, (Math.random() - 0.5) * spread);
      _p.copy(center).addScaledVector(_v, 0.15);
      this.emit(_p, _v, life * (0.7 + Math.random() * 0.6), size * (0.6 + Math.random() * 0.8), size * 0.6, tint, alpha);
    }
  }

  update(dt: number, camera: THREE.Camera): void {
    camera.getWorldQuaternion(this.q);
    const base = (this.alpha as unknown as { base?: Float32Array }).base;
    for (let i = 0; i < this.capacity; i++) {
      if (this.life[i] <= 0) continue;
      this.life[i] -= dt;
      const k = Math.max(0, this.life[i] / this.maxLife[i]);
      const o = i * 3;
      this.vel[o + 1] -= dt * 0.6;
      this.vel[o] *= 1 - dt * 0.8;
      this.vel[o + 1] *= 1 - dt * 0.5;
      this.vel[o + 2] *= 1 - dt * 0.8;
      this.pos[o] += this.vel[o] * dt;
      this.pos[o + 1] += this.vel[o + 1] * dt;
      this.pos[o + 2] += this.vel[o + 2] * dt;
      const s = this.size[i] + this.grow[i] * (1 - k);
      this.dummy.position.set(this.pos[o], this.pos[o + 1], this.pos[o + 2]);
      this.dummy.quaternion.copy(this.q);
      this.dummy.scale.setScalar(this.life[i] > 0 ? s : 0);
      this.dummy.updateMatrix();
      this.mesh.setMatrixAt(i, this.dummy.matrix);
      this.alpha.setX(i, (base ? base[i] : 0.5) * Math.min(1, k * 3) * Math.min(1, (1 - k) * 8 + 0.2));
    }
    this.mesh.instanceMatrix.needsUpdate = true;
    this.alpha.needsUpdate = true;
    this.tint.needsUpdate = true;
  }

  dispose(): void {
    this.mesh.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
  }
}

const _c = new THREE.Color();
const _v = new THREE.Vector3();
const _p = new THREE.Vector3();
