import * as THREE from 'three';

/** Recursively dispose geometries, materials and textures under an object. Shared resources can be protected. */
export function disposeObject(root: THREE.Object3D, keep?: Set<unknown>): void {
  const textures = new Set<THREE.Texture>();
  root.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.geometry && !keep?.has(mesh.geometry)) mesh.geometry.dispose();
    const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
    if (mat) {
      const mats = Array.isArray(mat) ? mat : [mat];
      for (const m of mats) {
        if (keep?.has(m)) continue;
        for (const v of Object.values(m)) if (v instanceof THREE.Texture && !keep?.has(v)) textures.add(v);
        m.dispose();
      }
    }
    const sk = (o as THREE.SkinnedMesh).skeleton;
    if (sk && (o as THREE.SkinnedMesh).isSkinnedMesh) sk.dispose();
  });
  for (const t of textures) t.dispose();
}

/** Tracks disposables created by a chapter so unloading releases everything. */
export class ResourceTracker {
  private items = new Set<{ dispose: () => void }>();
  track<T extends { dispose: () => void }>(r: T): T {
    this.items.add(r);
    return r;
  }
  disposeAll(): void {
    for (const r of this.items) {
      try {
        r.dispose();
      } catch {
        /* already disposed */
      }
    }
    this.items.clear();
  }
  get size(): number {
    return this.items.size;
  }
}
