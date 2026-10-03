import * as THREE from 'three';
import * as SkeletonUtils from 'three/examples/jsm/utils/SkeletonUtils.js';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { Assets } from '../render/Assets';

export interface ClipMeta {
  duration: number;
  loop: boolean;
  speed: number;
}

/**
 * Loads character GLBs and the shared humanoid animation set. Characters are cloned with
 * SkeletonUtils so every NPC gets its own skeleton while geometry, materials and textures are shared.
 */
export class CharacterLibrary {
  readonly clips = new Map<string, THREE.AnimationClip>();
  meta: Record<string, ClipMeta> = {};
  private templates = new Map<string, GLTF>();
  available = false;

  constructor(private readonly assets: Assets) {}

  async loadAnimations(): Promise<void> {
    const g = await this.assets.gltfOptional('characters/anims_humanoid.glb');
    if (!g) return;
    for (const c of g.animations) this.clips.set(c.name, c);
    try {
      const r = await fetch(this.assets.url('characters/anims_humanoid.json'));
      if (r.ok) this.meta = await r.json();
    } catch {
      /* metadata optional */
    }
    this.available = this.clips.size > 0;
  }

  async loadCharacter(id: string): Promise<boolean> {
    if (this.templates.has(id)) return true;
    const g = await this.assets.gltfOptional(`characters/${id}.glb`);
    if (!g) return false;
    g.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        m.receiveShadow = true;
        m.frustumCulled = false; // skinned bounds are unreliable; NPC root is culled instead
        const mats = Array.isArray(m.material) ? m.material : [m.material];
        for (const mat of mats) (mat as THREE.MeshStandardMaterial).envMapIntensity = 0.9;
      }
    });
    this.templates.set(id, g);
    return true;
  }

  has(id: string): boolean {
    return this.templates.has(id);
  }

  instantiate(id: string): THREE.Object3D | null {
    const t = this.templates.get(id);
    if (!t) return null;
    return SkeletonUtils.clone(t.scene);
  }

  clipSpeed(name: string): number {
    return this.meta[name]?.speed ?? (name === 'run' ? 3.6 : name === 'walk' || name === 'carry_walk' ? 1.4 : name === 'limp_walk' ? 0.8 : 0);
  }
}
