import * as THREE from 'three';
import type { Assets } from '../render/Assets';
import { damp } from '../core/Random';

export type HandPose = 'hidden' | 'fp_idle' | 'fp_reach' | 'fp_hold' | 'fp_scan' | 'fp_grip_two' | 'fp_climb';

/**
 * First-person forearms/hands rendered in the overlay scene (own camera, depth cleared) so they
 * never clip into walls. Shown only when they communicate something: interacting, holding a
 * document, scanning, gripping, climbing. Includes subtle sway and the device screen glow.
 */
export class FirstPersonHands {
  readonly root = new THREE.Group();
  private model: THREE.Object3D | null = null;
  private mixer: THREE.AnimationMixer | null = null;
  private actions = new Map<string, THREE.AnimationAction>();
  private current: THREE.AnimationAction | null = null;
  pose: HandPose = 'hidden';
  private showAmount = 0;
  private swayX = 0;
  private swayY = 0;
  private screenMat: THREE.MeshStandardMaterial | null = null;
  private heldSlot = new THREE.Group();
  private held: THREE.Object3D | null = null;
  readonly light = new THREE.DirectionalLight(0xffffff, 1.2);
  readonly fill = new THREE.HemisphereLight(0xbfc7cf, 0x3a342c, 0.5);
  deviceGlow = 0.6;
  loaded = false;

  constructor(private readonly overlay: THREE.Scene) {
    this.root.name = 'fp-hands';
    overlay.add(this.root, this.light, this.light.target, this.fill);
    this.light.position.set(0.5, 1, 0.6);
  }

  async load(assets: Assets): Promise<void> {
    const g = await assets.gltfOptional('characters/fp_arms.glb');
    if (!g) return;
    this.model = g.scene;
    this.root.add(this.model);
    this.model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.frustumCulled = false;
        const mat = m.material as THREE.MeshStandardMaterial;
        if (mat?.name === 'device_screen') this.screenMat = mat;
      }
      if (o.name.toLowerCase().includes('hand_r') && o.name.toLowerCase().includes('hold')) o.add(this.heldSlot);
    });
    if (!this.heldSlot.parent) {
      // fall back: attach to the right-hand bone if present
      this.model.traverse((o) => {
        if (!this.heldSlot.parent && (o as THREE.Bone).isBone && /hand.*(r|right)$/i.test(o.name)) o.add(this.heldSlot);
      });
    }
    this.mixer = new THREE.AnimationMixer(this.model);
    for (const c of g.animations) {
      const a = this.mixer.clipAction(c);
      if (c.name === 'fp_reach') {
        a.setLoop(THREE.LoopOnce, 1);
        a.clampWhenFinished = true;
      }
      this.actions.set(c.name, a);
    }
    this.loaded = true;
    this.root.visible = false;
  }

  setPose(p: HandPose): void {
    if (p === this.pose) return;
    this.pose = p;
    if (p === 'hidden') return;
    const a = this.actions.get(p);
    if (!a) return;
    a.reset().play();
    if (this.current && this.current !== a) this.current.crossFadeTo(a, 0.22, false);
    this.current = a;
  }

  /** One-shot reach, then return to the previous pose. */
  reach(): void {
    const prev = this.pose;
    this.setPose('fp_reach');
    window.setTimeout(() => {
      if (this.pose === 'fp_reach') this.setPose(prev === 'fp_reach' ? 'hidden' : prev);
    }, 650);
  }

  /** Attach a small object (folded paper, tool) to the right hand. */
  hold(obj: THREE.Object3D | null): void {
    if (this.held) this.heldSlot.remove(this.held);
    this.held = obj;
    if (obj) this.heldSlot.add(obj);
  }

  update(dt: number, mouseDX: number, mouseDY: number, bob: number, motion: number): void {
    if (!this.loaded) return;
    const target = this.pose === 'hidden' ? 0 : 1;
    this.showAmount += (target - this.showAmount) * damp(9, dt);
    this.root.visible = this.showAmount > 0.01;
    if (!this.root.visible) return;
    this.mixer?.update(dt);
    this.swayX += (-mouseDX * 0.0006 * motion - this.swayX) * damp(8, dt);
    this.swayY += (mouseDY * 0.0006 * motion - this.swayY) * damp(8, dt);
    this.root.position.set(this.swayX, -0.35 * (1 - this.showAmount) + this.swayY - bob * 0.01, 0);
    this.root.rotation.set(this.swayY * 0.5, this.swayX * 0.6, 0);
    if (this.screenMat) this.screenMat.emissiveIntensity = 0.4 + this.deviceGlow * 1.6;
  }

  setEnvironment(env: THREE.Texture | null, intensity: number): void {
    this.overlay.environment = env;
    this.overlay.environmentIntensity = intensity;
  }

  dispose(): void {
    this.mixer?.stopAllAction();
    this.root.removeFromParent();
  }
}
