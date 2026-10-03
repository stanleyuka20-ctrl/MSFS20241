import * as THREE from 'three';

/**
 * GPU rain: instanced camera-facing streaks animated entirely in the vertex shader inside a box
 * that follows the camera (no per-frame CPU work besides two uniforms). Density scales with settings.
 */
export class Rain {
  readonly mesh: THREE.Mesh;
  private mat: THREE.ShaderMaterial;
  private geo: THREE.InstancedBufferGeometry;
  readonly maxCount: number;

  constructor(density: number) {
    this.maxCount = Math.round(2500 + 9500 * density);
    const base = new THREE.PlaneGeometry(1, 1);
    this.geo = new THREE.InstancedBufferGeometry();
    this.geo.index = base.index;
    this.geo.setAttribute('position', base.attributes.position);
    this.geo.setAttribute('uv', base.attributes.uv);
    const offsets = new Float32Array(this.maxCount * 4);
    for (let i = 0; i < this.maxCount; i++) {
      offsets[i * 4] = Math.random();
      offsets[i * 4 + 1] = Math.random();
      offsets[i * 4 + 2] = Math.random();
      offsets[i * 4 + 3] = Math.random();
    }
    this.geo.setAttribute('aOffset', new THREE.InstancedBufferAttribute(offsets, 4));
    this.geo.instanceCount = this.maxCount;
    this.mat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uCam: { value: new THREE.Vector3() },
        uBox: { value: new THREE.Vector3(26, 16, 26) },
        uWind: { value: new THREE.Vector2(0.8, 0.3) },
        uIntensity: { value: 1 },
        uFogColor: { value: new THREE.Color(0x8a8f94) },
      },
      vertexShader: /* glsl */ `
        attribute vec4 aOffset;
        uniform float uTime, uIntensity;
        uniform vec3 uCam, uBox;
        uniform vec2 uWind;
        varying float vAlpha;
        varying vec2 vUv;
        void main() {
          float speed = 8.5 + aOffset.w * 2.5;
          vec3 vel = vec3(uWind.x, -speed, uWind.y);
          vec3 p = aOffset.xyz * uBox;
          p += vel * uTime;
          // wrap inside a box centred on the camera
          vec3 origin = uCam - uBox * 0.5;
          p = mod(p - origin, uBox) + origin;
          // streak oriented along velocity, facing the camera
          vec3 dir = normalize(vel);
          vec3 toCam = normalize(uCam - p);
          vec3 side = normalize(cross(dir, toCam));
          float len = 0.55 + aOffset.w * 0.25;
          float width = 0.0085;
          vec3 world = p + side * position.x * width + dir * position.y * len;
          vUv = uv;
          float dist = length(uCam - p);
          vAlpha = smoothstep(0.6, 2.0, dist) * (1.0 - smoothstep(9.0, 13.0, dist)) * step(aOffset.w, uIntensity);
          gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        varying float vAlpha;
        varying vec2 vUv;
        void main() {
          float a = (1.0 - abs(vUv.x - 0.5) * 2.0) * smoothstep(0.0, 0.25, vUv.y) * smoothstep(1.0, 0.6, vUv.y);
          gl_FragColor = vec4(vec3(0.72, 0.75, 0.78), a * vAlpha * 0.28);
        }
      `,
      transparent: true,
      depthWrite: false,
      fog: false,
    });
    this.mesh = new THREE.Mesh(this.geo, this.mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 10;
    this.mesh.name = 'rain';
  }

  setWind(x: number, z: number): void {
    (this.mat.uniforms.uWind.value as THREE.Vector2).set(x, z);
  }

  update(camera: THREE.Camera, intensity: number): void {
    this.mat.uniforms.uTime.value = performance.now() / 1000;
    (this.mat.uniforms.uCam.value as THREE.Vector3).setFromMatrixPosition(camera.matrixWorld);
    this.mat.uniforms.uIntensity.value = intensity;
    this.mesh.visible = intensity > 0.01;
  }

  dispose(): void {
    this.geo.dispose();
    this.mat.dispose();
  }
}
