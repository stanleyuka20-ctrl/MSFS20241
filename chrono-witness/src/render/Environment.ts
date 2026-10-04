import * as THREE from 'three';
import { WeatherUniforms } from './Materials';
import { Rain } from './Rain';
import type { Settings } from '../core/Settings';
import { damp } from '../core/Random';

export interface SkyConfig {
  zenith: THREE.ColorRepresentation;
  horizon: THREE.ColorRepresentation;
  ground: THREE.ColorRepresentation;
  sunDirection: [number, number, number];
  sunColor: THREE.ColorRepresentation;
  /** Direct sun intensity (overcast ≈ 0.4–1.2, clear ≈ 3+). */
  sunIntensity: number;
  /** Sun disc visibility 0..1 (overcast = 0). */
  sunDisc: number;
  cloudCover: number;
  cloudColor: THREE.ColorRepresentation;
  cloudShadow: THREE.ColorRepresentation;
}

export interface EnvironmentConfig {
  sky: SkyConfig;
  fogColor: THREE.ColorRepresentation;
  fogDensity: number;
  hemiSky: THREE.ColorRepresentation;
  hemiGround: THREE.ColorRepresentation;
  hemiIntensity: number;
  envIntensity: number;
  rain: number;
  wetness: number;
  wind: [number, number];
  /** Indoor scenes (HQ) skip the sky dome and rain entirely. */
  indoor?: boolean;
  background?: THREE.ColorRepresentation;
}

const SkyShader = {
  uniforms: {
    uZenith: { value: new THREE.Color() },
    uHorizon: { value: new THREE.Color() },
    uGround: { value: new THREE.Color() },
    uSunDir: { value: new THREE.Vector3(0, 1, 0) },
    uSunColor: { value: new THREE.Color() },
    uSunDisc: { value: 0 },
    uCloudCover: { value: 0.8 },
    uCloudColor: { value: new THREE.Color() },
    uCloudShadow: { value: new THREE.Color() },
    uTime: { value: 0 },
    uFlash: { value: 0 },
    uFlashDir: { value: new THREE.Vector3(0, 0.1, -1) },
    uFlashColor: { value: new THREE.Color(1, 0.8, 0.6) },
    uGlow: { value: 0 },
    uGlowDir: { value: new THREE.Vector3(0, 0, 1) },
    uGlowColor: { value: new THREE.Color(1, 0.45, 0.15) },
    tNoise: { value: null as THREE.Texture | null },
    uHasNoise: { value: 0 },
  },
  vertexShader: /* glsl */ `
    varying vec3 vDir;
    void main() {
      vDir = normalize(position);
      vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      gl_Position = p.xyww;
    }
  `,
  fragmentShader: /* glsl */ `
    uniform vec3 uZenith, uHorizon, uGround, uSunDir, uSunColor, uCloudColor, uCloudShadow, uFlashDir, uFlashColor, uGlowDir, uGlowColor;
    uniform float uSunDisc, uCloudCover, uTime, uFlash, uHasNoise, uGlow;
    uniform sampler2D tNoise;
    varying vec3 vDir;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float vnoise(vec2 p) {
      vec2 i = floor(p), f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
    }
    float fbm(vec2 p) {
      if (uHasNoise > 0.5) {
        return texture2D(tNoise, p * 0.11).r * 0.55 + texture2D(tNoise, p * 0.27 + 0.3).g * 0.3 + texture2D(tNoise, p * 0.71 + 0.7).b * 0.15;
      }
      float s = 0.0, a = 0.5;
      for (int i = 0; i < 5; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; }
      return s;
    }
    void main() {
      vec3 d = normalize(vDir);
      float h = d.y;
      vec3 col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.55));
      col = mix(col, uGround, smoothstep(0.0, -0.08, h));
      // cloud layer projected on a plane
      if (h > -0.02) {
        vec2 uv = d.xz / (h + 0.12) * 1.6 + vec2(uTime * 0.012, uTime * 0.004);
        float n = fbm(uv);
        float n2 = fbm(uv * 2.7 + 4.0);
        float cov = smoothstep(1.0 - uCloudCover - 0.15, 1.0 - uCloudCover + 0.35, n * 0.75 + n2 * 0.35);
        vec3 cc = mix(uCloudShadow, uCloudColor, smoothstep(0.25, 0.85, n2 + (1.0 - n) * 0.3));
        float fade = smoothstep(-0.02, 0.18, h);
        col = mix(col, cc, cov * fade);
      }
      float sd = max(dot(d, uSunDir), 0.0);
      col += uSunColor * (pow(sd, 900.0) * 30.0 * uSunDisc + pow(sd, 12.0) * 0.25 * (0.3 + uSunDisc));
      // distant artillery/flare flash lighting the cloud base near the horizon
      float fd = max(dot(normalize(vec3(d.x, max(d.y, 0.0) * 0.4, d.z)), normalize(vec3(uFlashDir.x, 0.0, uFlashDir.z))), 0.0);
      col += uFlashColor * uFlash * pow(fd, 6.0) * smoothstep(0.45, 0.0, h) * 2.0;
      // persistent glow on the cloud base from distant fires
      float gd = max(dot(normalize(vec3(d.x, 0.0, d.z)), normalize(vec3(uGlowDir.x, 0.0, uGlowDir.z))), 0.0);
      col += uGlowColor * uGlow * pow(gd, 3.0) * smoothstep(0.55, 0.0, h) * (0.6 + 0.4 * sin(uTime * 0.7 + d.x * 3.0));
      gl_FragColor = vec4(col, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }
  `,
};

/**
 * Sky, lights, fog, rain and flash lighting for a chapter. The sky is also rendered once into a
 * PMREM cube map for image-based lighting, so ambient light matches the visible sky.
 */
export class Environment {
  readonly group = new THREE.Group();
  readonly sun = new THREE.DirectionalLight(0xffffff, 1);
  readonly hemi = new THREE.HemisphereLight(0xffffff, 0x444444, 0.3);
  readonly flashLight = new THREE.DirectionalLight(0xffd9b0, 0);
  private skyMesh: THREE.Mesh | null = null;
  private skyMat: THREE.ShaderMaterial | null = null;
  private envRT: THREE.WebGLRenderTarget | null = null;
  rain: Rain | null = null;
  config!: EnvironmentConfig;
  /** 0..1 indoor factor (dugouts): hides rain, reduces wetness response, muffles. */
  indoor = 0;
  private indoorTarget = 0;
  private flash = 0;
  private flashDecay = 6;
  readonly sunDir = new THREE.Vector3(0, 1, 0);
  private shadowSize = 0;
  /** How much sky/IBL light is removed when indoors (0..1). */
  indoorDim = 0.75;

  constructor(
    private readonly scene: THREE.Scene,
    private readonly settings: Settings,
  ) {
    this.group.name = 'environment';
    this.sun.castShadow = true;
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.035;
    this.group.add(this.sun, this.sun.target, this.hemi, this.flashLight, this.flashLight.target);
  }

  async setup(cfg: EnvironmentConfig, renderer: THREE.WebGLRenderer, noise: THREE.Texture | null): Promise<void> {
    this.config = cfg;
    const s = cfg.sky;
    this.sunDir.set(...s.sunDirection).normalize();
    this.sun.color.set(s.sunColor);
    this.sun.intensity = s.sunIntensity;
    this.hemi.color.set(cfg.hemiSky);
    this.hemi.groundColor.set(cfg.hemiGround);
    this.hemi.intensity = cfg.hemiIntensity;
    this.scene.fog = new THREE.FogExp2(new THREE.Color(cfg.fogColor).getHex(), cfg.fogDensity);
    WeatherUniforms.uWetness.value = cfg.wetness;
    WeatherUniforms.uRain.value = cfg.rain;

    if (!cfg.indoor) {
      const mat = new THREE.ShaderMaterial({
        uniforms: THREE.UniformsUtils.clone(SkyShader.uniforms),
        vertexShader: SkyShader.vertexShader,
        fragmentShader: SkyShader.fragmentShader,
        side: THREE.BackSide,
        depthWrite: false,
        fog: false,
      });
      const u = mat.uniforms;
      u.uZenith.value.set(s.zenith);
      u.uHorizon.value.set(s.horizon);
      u.uGround.value.set(s.ground);
      u.uSunDir.value.copy(this.sunDir);
      u.uSunColor.value.set(s.sunColor);
      u.uSunDisc.value = s.sunDisc;
      u.uCloudCover.value = s.cloudCover;
      u.uCloudColor.value.set(s.cloudColor);
      u.uCloudShadow.value.set(s.cloudShadow);
      if (noise) {
        u.tNoise.value = noise;
        u.uHasNoise.value = 1;
      }
      this.skyMat = mat;
      this.skyMesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), mat);
      this.skyMesh.scale.setScalar(1800);
      this.skyMesh.frustumCulled = false;
      this.skyMesh.renderOrder = -10;
      this.group.add(this.skyMesh);

      // PMREM environment from the sky (tone mapping disabled for the capture)
      const pm = new THREE.PMREMGenerator(renderer);
      const envScene = new THREE.Scene();
      const capMat = mat.clone();
      capMat.uniforms = mat.uniforms;
      capMat.toneMapped = false;
      const capSky = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), capMat);
      capSky.scale.setScalar(100);
      envScene.add(capSky);
      // ground bounce plane colour so the lower hemisphere isn't black
      const groundPlane = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), new THREE.MeshBasicMaterial({ color: new THREE.Color(cfg.sky.ground), side: THREE.DoubleSide }));
      groundPlane.rotation.x = -Math.PI / 2;
      groundPlane.position.y = -2;
      envScene.add(groundPlane);
      this.envRT = pm.fromScene(envScene, 0.02, 0.1, 200);
      capSky.geometry.dispose();
      capMat.dispose();
      groundPlane.geometry.dispose();
      (groundPlane.material as THREE.Material).dispose();
      pm.dispose();
      this.scene.environment = this.envRT.texture;
      this.scene.background = null;
      this.scene.environmentIntensity = cfg.envIntensity;
      this.baseEnvIntensity = cfg.envIntensity;
    } else {
      this.scene.background = new THREE.Color(cfg.background ?? 0x101012);
      this.scene.environmentIntensity = cfg.envIntensity;
    }

    if (cfg.rain > 0) {
      this.rain = new Rain(this.settings.graphics.rainDensity);
      this.rain.setWind(cfg.wind[0], cfg.wind[1]);
      this.group.add(this.rain.mesh);
    }
    this.applyShadowSettings(2048, this.settings.graphics.shadowDistance);
  }

  /** Persistent horizon glow (e.g. the docks burning). */
  setGlow(dir: THREE.Vector3, color: THREE.ColorRepresentation, intensity: number): void {
    if (!this.skyMat) return;
    this.skyMat.uniforms.uGlowDir.value.copy(dir);
    this.skyMat.uniforms.uGlowColor.value.set(color);
    this.skyMat.uniforms.uGlow.value = intensity;
  }

  /**
   * Blend sky colours and light levels towards another configuration (time-of-day change, e.g. dawn).
   * The baked environment map is kept; its intensity follows the blend.
   */
  blend(a: EnvironmentConfig, b: EnvironmentConfig, k: number): void {
    const c = (x: THREE.ColorRepresentation, y: THREE.ColorRepresentation): THREE.Color => new THREE.Color(x).lerp(new THREE.Color(y), k);
    const L = (x: number, y: number): number => x + (y - x) * k;
    if (this.skyMat) {
      const u = this.skyMat.uniforms;
      u.uZenith.value.copy(c(a.sky.zenith, b.sky.zenith));
      u.uHorizon.value.copy(c(a.sky.horizon, b.sky.horizon));
      u.uGround.value.copy(c(a.sky.ground, b.sky.ground));
      u.uCloudColor.value.copy(c(a.sky.cloudColor, b.sky.cloudColor));
      u.uCloudShadow.value.copy(c(a.sky.cloudShadow, b.sky.cloudShadow));
      u.uCloudCover.value = L(a.sky.cloudCover, b.sky.cloudCover);
      u.uSunColor.value.copy(c(a.sky.sunColor, b.sky.sunColor));
      const sd = new THREE.Vector3(...a.sky.sunDirection).normalize().lerp(new THREE.Vector3(...b.sky.sunDirection).normalize(), k).normalize();
      u.uSunDir.value.copy(sd);
      this.sunDir.copy(sd);
    }
    this.sun.color.copy(c(a.sky.sunColor, b.sky.sunColor));
    this.sun.intensity = L(a.sky.sunIntensity, b.sky.sunIntensity);
    this.hemi.color.copy(c(a.hemiSky, b.hemiSky));
    this.hemi.groundColor.copy(c(a.hemiGround, b.hemiGround));
    this.hemi.intensity = L(a.hemiIntensity, b.hemiIntensity);
    this.baseEnvIntensity = L(a.envIntensity, b.envIntensity);
    if (this.scene.fog instanceof THREE.FogExp2) {
      this.scene.fog.color.copy(c(a.fogColor, b.fogColor));
      this.scene.fog.density = L(a.fogDensity, b.fogDensity);
    }
  }

  baseEnvIntensity = 1;

  /** Assign an externally generated environment map (e.g. HQ room environment). */
  setEnvironmentMap(tex: THREE.Texture, intensity: number): void {
    this.scene.environment = tex;
    this.scene.environmentIntensity = intensity;
  }

  applyShadowSettings(mapSize: number, distance: number): void {
    const sh = this.sun.shadow;
    this.sun.castShadow = mapSize > 0;
    if (mapSize > 0 && this.shadowSize !== mapSize) {
      sh.mapSize.set(mapSize, mapSize);
      sh.map?.dispose();
      sh.map = null;
      this.shadowSize = mapSize;
    }
    const cam = sh.camera;
    cam.left = -distance;
    cam.right = distance;
    cam.top = distance;
    cam.bottom = -distance;
    cam.near = 1;
    cam.far = 260;
    cam.updateProjectionMatrix();
  }

  setIndoor(v: number): void {
    this.indoorTarget = v;
  }

  /** Trigger a flash (artillery, flare). Reduced-flash mode caps brightness and slows the onset. */
  triggerFlash(dir: THREE.Vector3, strength: number, color: THREE.ColorRepresentation = 0xffc890, decay = 6): void {
    const reduced = this.settings.accessibility.reducedFlash;
    const s = reduced ? Math.min(strength, 0.25) * 0.5 : strength;
    this.flash = Math.max(this.flash, s);
    this.flashDecay = reduced ? Math.min(decay, 2.5) : decay;
    this.flashLight.color.set(color);
    this.flashLight.position.copy(dir).normalize().multiplyScalar(100);
    if (this.skyMat) {
      this.skyMat.uniforms.uFlashDir.value.copy(dir).normalize();
      this.skyMat.uniforms.uFlashColor.value.set(color);
    }
  }

  get flashLevel(): number {
    return this.flash;
  }

  update(dt: number, time: number, focus: THREE.Vector3, camera: THREE.Camera): void {
    WeatherUniforms.uTime.value = time;
    this.indoor += (this.indoorTarget - this.indoor) * damp(3, dt);
    // interiors: sky light falls off (dugouts, cellars, tunnels are lit by their own lamps)
    if (!this.config.indoor) this.scene.environmentIntensity = this.baseEnvIntensity * (1 - this.indoor * this.indoorDim);
    if (this.skyMesh) this.skyMesh.position.copy(_c.setFromMatrixPosition(camera.matrixWorld));
    if (this.skyMat) {
      this.skyMat.uniforms.uTime.value = time;
      this.skyMat.uniforms.uFlash.value = this.flash;
    }
    this.flash = Math.max(0, this.flash - dt * this.flashDecay * Math.max(0.2, this.flash));
    this.flashLight.intensity = this.flash * 2.5 * (1 - this.indoor * 0.85);
    this.flashLight.target.position.copy(focus);
    this.flashLight.position.add(focus);

    // sun follows the focus point; snap to shadow texels to avoid shimmering
    const sh = this.sun.shadow;
    const extent = sh.camera.right - sh.camera.left;
    const texel = extent / Math.max(1, sh.mapSize.x);
    _lp.copy(focus);
    // project focus onto light space axes and snap
    _m.lookAt(_zero, this.sunDir, _upv);
    _inv.copy(_m).invert();
    _lp.applyMatrix4(_inv);
    _lp.x = Math.round(_lp.x / texel) * texel;
    _lp.y = Math.round(_lp.y / texel) * texel;
    _lp.applyMatrix4(_m);
    this.sun.target.position.copy(_lp);
    this.sun.position.copy(_lp).addScaledVector(this.sunDir, 120);

    if (this.rain) {
      this.rain.update(camera, this.config.rain * (1 - this.indoor));
    }
    WeatherUniforms.uRain.value = this.config.rain;
  }

  dispose(): void {
    this.skyMesh?.geometry.dispose();
    this.skyMat?.dispose();
    this.envRT?.dispose();
    this.rain?.dispose();
    this.sun.shadow.map?.dispose();
    this.sun.shadow.map = null;
    this.shadowSize = 0;
    this.group.removeFromParent();
    this.scene.environment = null;
    this.scene.fog = null;
  }
}

const _c = new THREE.Vector3();
const _lp = new THREE.Vector3();
const _m = new THREE.Matrix4();
const _inv = new THREE.Matrix4();
const _zero = new THREE.Vector3();
const _upv = new THREE.Vector3(0, 1, 0);
