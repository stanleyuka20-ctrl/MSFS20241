import * as THREE from 'three';
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { GraphicsSettings } from '../core/Settings';

export interface AssetIssue {
  url: string;
  message: string;
  fatal: boolean;
}

export interface PBRSet {
  map: THREE.Texture;
  normalMap: THREE.Texture;
  orm: THREE.Texture;
  tileMetres: number;
}

const BASE = `${import.meta.env.BASE_URL}assets/`;

/**
 * Loads textures and glTF models with caching, quality-based downscaling, progress reporting and
 * recoverable failures: a missing texture is replaced by a neutral fallback and reported as a
 * warning instead of aborting the chapter.
 */
export class Assets {
  private gltfLoader = new GLTFLoader();
  private textureCache = new Map<string, Promise<THREE.Texture>>();
  private gltfCache = new Map<string, Promise<GLTF>>();
  private manifest: Record<string, { tileMetres: number }> | null = null;
  readonly issues: AssetIssue[] = [];
  private fallbackTextures = new Map<string, THREE.Texture>();

  constructor(
    private readonly settings: GraphicsSettings,
    private readonly maxAnisotropy: number,
  ) {}

  url(path: string): string {
    return BASE + path;
  }

  async loadManifest(): Promise<void> {
    if (this.manifest) return;
    try {
      const r = await fetch(this.url('textures/manifest.json'));
      this.manifest = r.ok ? await r.json() : {};
    } catch {
      this.manifest = {};
    }
  }

  private maxTextureSize(): number {
    return [512, 1024, 4096][this.settings.textureQuality];
  }

  /** Load a texture (sRGB for colour maps). Never rejects: failures produce a fallback. */
  texture(path: string, colorSpace: THREE.ColorSpace = THREE.NoColorSpace, fallback: 'albedo' | 'normal' | 'orm' | 'white' = 'white'): Promise<THREE.Texture> {
    const key = `${path}|${colorSpace}|${this.settings.textureQuality}`;
    let p = this.textureCache.get(key);
    if (!p) {
      p = this.loadTexture(path, colorSpace).catch((e: unknown) => {
        this.issues.push({ url: path, message: String((e as Error)?.message ?? e), fatal: false });
        return this.fallback(fallback);
      });
      this.textureCache.set(key, p);
    }
    return p;
  }

  private async loadTexture(path: string, colorSpace: THREE.ColorSpace): Promise<THREE.Texture> {
    const res = await fetch(this.url(path));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const max = this.maxTextureSize();
    const probe = await createImageBitmap(blob);
    let w = probe.width;
    let h = probe.height;
    let bmp: ImageBitmap = probe;
    if (w > max || h > max) {
      const s = max / Math.max(w, h);
      w = Math.max(1, Math.round(w * s));
      h = Math.max(1, Math.round(h * s));
      probe.close();
      bmp = await createImageBitmap(blob, { resizeWidth: w, resizeHeight: h, resizeQuality: 'high' });
    }
    const tex = new THREE.Texture(bmp as unknown as HTMLImageElement);
    tex.flipY = false; // ImageBitmaps ignore flipY; our UVs follow the glTF convention
    tex.colorSpace = colorSpace;
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.anisotropy = Math.min(this.settings.anisotropy, this.maxAnisotropy);
    tex.generateMipmaps = true;
    tex.minFilter = THREE.LinearMipmapLinearFilter;
    tex.needsUpdate = true;
    return tex;
  }

  private fallback(kind: 'albedo' | 'normal' | 'orm' | 'white'): THREE.Texture {
    let t = this.fallbackTextures.get(kind);
    if (!t) {
      const color = { albedo: [128, 118, 104, 255], normal: [128, 128, 255, 255], orm: [255, 200, 0, 255], white: [255, 255, 255, 255] }[kind];
      const data = new Uint8Array(4 * 4 * 4);
      for (let i = 0; i < 16; i++) data.set(color, i * 4);
      t = new THREE.DataTexture(data, 4, 4);
      t.wrapS = t.wrapT = THREE.RepeatWrapping;
      if (kind === 'albedo') t.colorSpace = THREE.SRGBColorSpace;
      t.needsUpdate = true;
      this.fallbackTextures.set(kind, t);
    }
    return t;
  }

  /** Load a PBR set produced by the texture pipeline. */
  async pbr(set: string): Promise<PBRSet> {
    await this.loadManifest();
    const [map, normalMap, orm] = await Promise.all([
      this.texture(`textures/${set}/${set}_albedo.jpg`, THREE.SRGBColorSpace, 'albedo'),
      this.texture(`textures/${set}/${set}_normal.jpg`, THREE.NoColorSpace, 'normal'),
      this.texture(`textures/${set}/${set}_orm.jpg`, THREE.NoColorSpace, 'orm'),
    ]);
    return { map, normalMap, orm, tileMetres: this.manifest?.[set]?.tileMetres ?? 1 };
  }

  /** Load a glTF. Rejects on failure (caller decides whether it is fatal). */
  gltf(path: string, onProgress?: (f: number) => void): Promise<GLTF> {
    let p = this.gltfCache.get(path);
    if (!p) {
      p = new Promise<GLTF>((resolve, reject) => {
        this.gltfLoader.load(
          this.url(path),
          resolve,
          (e) => {
            if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
          },
          (err) => reject(err instanceof Error ? err : new Error(String(err))),
        );
      });
      p.catch(() => this.gltfCache.delete(path));
      this.gltfCache.set(path, p);
    }
    return p;
  }

  /** Optional glTF: returns null (and records an issue) on failure. */
  async gltfOptional(path: string, onProgress?: (f: number) => void): Promise<GLTF | null> {
    try {
      return await this.gltf(path, onProgress);
    } catch (e) {
      this.issues.push({ url: path, message: String((e as Error)?.message ?? e), fatal: false });
      return null;
    }
  }

  /** Release cached chapter resources. Shared fallbacks are kept. */
  async purge(): Promise<void> {
    for (const p of this.textureCache.values()) {
      const t = await p;
      if (![...this.fallbackTextures.values()].includes(t)) {
        // GPU memory is released by dispose(); the ImageBitmap is left to GC (closing it eagerly
        // can race with a final upload of a texture that is still referenced for one frame).
        t.dispose();
      }
    }
    this.textureCache.clear();
    for (const p of this.gltfCache.values()) {
      try {
        const g = await p;
        g.scene.traverse((o) => {
          const m = o as THREE.Mesh;
          m.geometry?.dispose();
          const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : [];
          for (const mat of mats) {
            for (const v of Object.values(mat)) if (v instanceof THREE.Texture) v.dispose();
            mat.dispose();
          }
        });
      } catch {
        /* failed load */
      }
    }
    this.gltfCache.clear();
    this.issues.length = 0;
  }
}
