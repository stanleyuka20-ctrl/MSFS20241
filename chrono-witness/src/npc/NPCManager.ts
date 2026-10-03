import * as THREE from 'three';
import { NPC, type NPCOptions } from './NPC';
import type { CharacterLibrary } from './CharacterLibrary';
import type { NavGraph } from './NavGraph';

/**
 * Owns all NPCs of the active chapter: updates with frustum-aware animation throttling, keeps the
 * player from walking through characters, and toggles shadow casting by distance.
 */
export class NPCManager {
  readonly npcs = new Map<string, NPC>();
  readonly group = new THREE.Group();
  nav: NavGraph | null = null;
  private frustum = new THREE.Frustum();
  private projScreen = new THREE.Matrix4();
  private sphere = new THREE.Sphere(new THREE.Vector3(), 1.2);
  groundFn: ((x: number, y: number, z: number) => number | null) | null = null;
  shadowDistance = 30;
  animLodDistance = 30;

  constructor(private readonly lib: CharacterLibrary) {
    this.group.name = 'npcs';
  }

  spawn(opts: NPCOptions): NPC {
    const n = new NPC(opts, this.lib);
    n.groundFn = this.groundFn;
    this.npcs.set(n.id, n);
    this.group.add(n.root);
    return n;
  }

  get(id: string): NPC {
    const n = this.npcs.get(id);
    if (!n) throw new Error(`NPC ${id} not found`);
    return n;
  }

  update(dt: number, camera: THREE.Camera, playerPos: THREE.Vector3): void {
    this.projScreen.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.projScreen);
    const camPos = _cam.setFromMatrixPosition(camera.matrixWorld);
    for (const n of this.npcs.values()) {
      if (!n.visible) continue;
      this.sphere.center.copy(n.root.position).y += 0.9;
      const inView = this.frustum.intersectsSphere(this.sphere);
      n.update(dt, camPos, playerPos, this.animLodDistance, inView);
      const cast = n.root.position.distanceTo(camPos) < this.shadowDistance;
      if (n.model && n.model.userData.castShadow !== cast) {
        n.model.userData.castShadow = cast;
        n.model.traverse((o) => {
          if ((o as THREE.Mesh).isMesh) o.castShadow = cast;
        });
      }
    }
  }

  /** Push the player capsule (feet position, radius) out of NPC bodies (2D circles). */
  resolvePlayer(p: THREE.Vector3, radius: number): void {
    for (const n of this.npcs.values()) {
      if (!n.visible || n.root.userData.noCollide) continue;
      const np = n.root.position;
      if (Math.abs(np.y - p.y) > 1.5) continue;
      const dx = p.x - np.x;
      const dz = p.z - np.z;
      const r = radius + (n.root.userData.radius ?? 0.28);
      const d2 = dx * dx + dz * dz;
      if (d2 < r * r && d2 > 1e-6) {
        const d = Math.sqrt(d2);
        p.x = np.x + (dx / d) * r;
        p.z = np.z + (dz / d) * r;
      }
    }
  }

  nearest(p: THREE.Vector3, maxDist: number): NPC | null {
    let best: NPC | null = null;
    let bd = maxDist;
    for (const n of this.npcs.values()) {
      const d = n.root.position.distanceTo(p);
      if (d < bd) {
        bd = d;
        best = n;
      }
    }
    return best;
  }

  dispose(): void {
    for (const n of this.npcs.values()) n.dispose();
    this.npcs.clear();
    this.group.removeFromParent();
  }
}

const _cam = new THREE.Vector3();
