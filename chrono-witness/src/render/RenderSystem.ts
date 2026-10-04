import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/examples/jsm/postprocessing/SMAAPass.js';
import { FXAAPass } from 'three/examples/jsm/postprocessing/FXAAPass.js';
import { GTAOPass } from 'three/examples/jsm/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import type { GraphicsSettings } from '../core/Settings';
import { GradeShader } from './GradeShader';

export interface GradeParams {
  saturation: number;
  contrast: number;
  tint: THREE.ColorRepresentation;
  shadowTint: THREE.ColorRepresentation;
  exposure: number;
  vignette: number;
  grain: number;
}

/**
 * Owns the WebGL renderer and post-processing chain:
 *   scene → [GTAO] → first-person overlay → [bloom] → grade → output (AgX + sRGB) → [SMAA|FXAA]
 * Expensive stages are toggled by graphics settings; resolution scale is applied to the drawing buffer.
 */
export class RenderSystem {
  readonly renderer: THREE.WebGLRenderer;
  private composer!: EffectComposer;
  private renderPass!: RenderPass;
  private overlayPass!: RenderPass;
  private gtao: GTAOPass | null = null;
  private bloom: UnrealBloomPass | null = null;
  private aa: SMAAPass | FXAAPass | null = null;
  readonly grade = new ShaderPass(GradeShader);
  private output = new OutputPass();
  private width = 1;
  private height = 1;
  private scale = 1;
  private settings!: GraphicsSettings;
  private msaa = false;
  /** Scene + camera for the first-person hands, drawn after the world with cleared depth. */
  readonly overlayScene = new THREE.Scene();
  overlayCamera: THREE.PerspectiveCamera;

  constructor(
    private readonly canvas: HTMLCanvasElement,
    public scene: THREE.Scene,
    public camera: THREE.PerspectiveCamera,
  ) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: false,
      powerPreference: 'high-performance',
      stencil: false,
      depth: true,
      preserveDrawingBuffer: false,
    });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.AgXToneMapping;
    this.renderer.toneMappingExposure = 1;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.info.autoReset = false;
    this.overlayCamera = new THREE.PerspectiveCamera(60, 1, 0.01, 10);
  }

  get maxAnisotropy(): number {
    return this.renderer.capabilities.getMaxAnisotropy();
  }

  apply(settings: GraphicsSettings): void {
    this.settings = settings;
    const shadowSizes = [0, 1024, 2048, 4096];
    this.renderer.shadowMap.enabled = settings.shadowQuality > 0;
    this.shadowMapSize = shadowSizes[settings.shadowQuality];
    this.scale = settings.resolutionScale;
    this.shadowInterval = settings.preset === 'low' ? 2 : 1;
    this.rebuildComposer();
    this.resize(this.width, this.height);
  }

  /** Current sun shadow map size requested by settings (0 = off). Lights read this. */
  shadowMapSize = 2048;

  setResolutionScale(s: number): void {
    if (Math.abs(s - this.scale) < 0.01) return;
    this.scale = s;
    this.resize(this.width, this.height);
  }

  get resolutionScale(): number {
    return this.scale;
  }

  private rebuildComposer(): void {
    const s = this.settings;
    this.composer?.dispose();
    this.gtao?.dispose();
    this.bloom?.dispose();
    (this.aa as unknown as { dispose?: () => void })?.dispose?.();
    this.msaa = s.antialiasing === 'msaa' && this.renderer.capabilities.isWebGL2;
    const rt = new THREE.WebGLRenderTarget(1, 1, {
      type: THREE.HalfFloatType,
      samples: this.msaa ? 4 : 0,
    });
    this.composer = new EffectComposer(this.renderer, rt);
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.composer.addPass(this.renderPass);

    this.gtao = null;
    if (s.ambientOcclusion) {
      this.gtao = new GTAOPass(this.scene, this.camera, 1, 1);
      this.gtao.output = GTAOPass.OUTPUT.Default;
      this.gtao.blendIntensity = 0.85;
      this.gtao.updateGtaoMaterial({ radius: 0.6, distanceExponent: 1.4, thickness: 1.2, scale: 1, samples: 12, distanceFallOff: 1, screenSpaceRadius: false });
      this.gtao.updatePdMaterial({ lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 6, rings: 2, samples: 12 });
      this.composer.addPass(this.gtao);
    }

    this.overlayPass = new RenderPass(this.overlayScene, this.overlayCamera);
    this.overlayPass.clear = false;
    this.overlayPass.clearDepth = true;
    this.composer.addPass(this.overlayPass);

    this.bloom = null;
    if (s.bloom) {
      // Restrained: only very bright sources (lamps, flares, emissive screens) bloom.
      this.bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.18, 0.35, 2.2);
      this.composer.addPass(this.bloom);
    }
    this.composer.addPass(this.grade);
    this.composer.addPass(this.output);
    this.aa = null;
    if (s.antialiasing === 'smaa') this.aa = new SMAAPass();
    else if (s.antialiasing === 'fxaa') this.aa = new FXAAPass();
    if (this.aa) this.composer.addPass(this.aa);
  }

  resize(w: number, h: number): void {
    this.width = Math.max(1, w);
    this.height = Math.max(1, h);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const pr = dpr * this.scale;
    this.renderer.setPixelRatio(pr);
    this.renderer.setSize(this.width, this.height, false);
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.composer.setPixelRatio(pr);
    this.composer.setSize(this.width, this.height);
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    this.overlayCamera.aspect = this.camera.aspect;
    this.overlayCamera.updateProjectionMatrix();
    this.grade.uniforms.uAspect.value = this.camera.aspect;
  }

  setGrade(p: GradeParams): void {
    const u = this.grade.uniforms;
    u.uSaturation.value = p.saturation;
    u.uContrast.value = p.contrast;
    (u.uTint.value as THREE.Color).set(p.tint);
    (u.uShadowTint.value as THREE.Color).set(p.shadowTint);
    u.uVignette.value = p.vignette;
    u.uGrain.value = p.grain;
    this.renderer.toneMappingExposure = p.exposure;
  }

  setScene(scene: THREE.Scene, camera: THREE.PerspectiveCamera): void {
    this.scene = scene;
    this.camera = camera;
    this.renderPass.scene = scene;
    this.renderPass.camera = camera;
    if (this.gtao) {
      this.gtao.scene = scene;
      this.gtao.camera = camera;
    }
  }

  /** Render the sun shadow map every Nth frame (Low preset uses 2; the light only follows the player). */
  shadowInterval = 1;
  private frameNo = 0;

  render(time: number): void {
    this.renderer.info.reset();
    this.frameNo++;
    this.renderer.shadowMap.autoUpdate = false;
    this.renderer.shadowMap.needsUpdate = this.frameNo % this.shadowInterval === 0;
    this.grade.uniforms.uTime.value = time;
    this.overlayCamera.fov = this.camera.fov;
    this.overlayCamera.updateProjectionMatrix();
    this.composer.render();
  }

  /** Compile all materials in a scene up front (avoids shader-compile hitches during play). */
  async precompile(scene: THREE.Scene, camera: THREE.Camera): Promise<void> {
    const r = this.renderer as THREE.WebGLRenderer & { compileAsync?: (s: THREE.Object3D, c: THREE.Camera, t?: THREE.Scene) => Promise<unknown> };
    if (r.compileAsync) await r.compileAsync(scene, camera);
    else r.compile(scene, camera);
  }

  dispose(): void {
    this.composer.dispose();
    this.gtao?.dispose();
    this.bloom?.dispose();
    this.renderer.dispose();
  }
}
