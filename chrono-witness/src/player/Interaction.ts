import * as THREE from 'three';
import type { CollisionWorld } from '../physics/CollisionWorld';

export interface Interactable {
  id: string;
  /** World position used for targeting (updated each frame for moving objects via `object`). */
  position: THREE.Vector3;
  object?: THREE.Object3D;
  /** Height offset added to the object's position. */
  offsetY?: number;
  radius: number;
  /** Max distance from the camera. */
  range?: number;
  /** "Talk to Sergeant Hollis" — verb + name shown in the prompt. */
  prompt: string | (() => string);
  /** Seconds the interact key must be held (0 = press). */
  holdTime?: number;
  enabled?: () => boolean;
  onInteract: () => void;
  /** Scannable entry id (shown by the temporal scanner). */
  scanId?: string;
  /** Only targetable in temporal observation mode. */
  observeOnly?: boolean;
  /** Scanner-only targets (no E interaction). */
  scanOnly?: boolean;
}

/**
 * Finds the interactable under the crosshair: closest target whose bounding sphere the view ray
 * passes through, within range and with a clear line of sight.
 */
export class InteractionSystem {
  readonly items = new Map<string, Interactable>();
  focused: Interactable | null = null;
  holdProgress = 0;
  private _ray = new THREE.Ray();
  private _p = new THREE.Vector3();
  private _sphere = new THREE.Sphere();
  observeMode = false;
  scanMode = false;

  constructor(private readonly world: CollisionWorld) {}

  add(i: Interactable): Interactable {
    this.items.set(i.id, i);
    return i;
  }

  remove(id: string): void {
    this.items.delete(id);
    if (this.focused?.id === id) this.focused = null;
  }

  clear(): void {
    this.items.clear();
    this.focused = null;
  }

  worldPos(i: Interactable, out: THREE.Vector3): THREE.Vector3 {
    if (i.object) {
      i.object.getWorldPosition(out);
      out.y += i.offsetY ?? 0;
      i.position.copy(out);
    } else out.copy(i.position);
    return out;
  }

  update(camera: THREE.Camera, forward: THREE.Vector3): void {
    this._ray.origin.setFromMatrixPosition(camera.matrixWorld);
    this._ray.direction.copy(forward);
    let best: Interactable | null = null;
    let bestScore = Infinity;
    for (const i of this.items.values()) {
      if (i.enabled && !i.enabled()) continue;
      if (i.observeOnly && !this.observeMode) continue;
      if (i.scanOnly && !this.scanMode) continue;
      if (this.scanMode && !i.scanId) continue;
      const p = this.worldPos(i, this._p);
      const dist = p.distanceTo(this._ray.origin);
      const range = i.range ?? 2.6;
      if (dist > range + i.radius) continue;
      this._sphere.set(p, i.radius);
      if (!this._ray.intersectsSphere(this._sphere)) continue;
      // angular closeness to the crosshair favours the intended target
      const along = this._p.sub(this._ray.origin).dot(this._ray.direction);
      if (along < 0) continue;
      const perp = Math.sqrt(Math.max(0, dist * dist - along * along));
      const score = perp / i.radius + dist * 0.08;
      if (score < bestScore) {
        // line of sight (ignore last few cm near the target)
        const target = this.worldPos(i, _t);
        _dir.subVectors(target, this._ray.origin);
        const len = _dir.length();
        _dir.multiplyScalar(1 / len);
        const hit = this.world.raycast(this._ray.origin, _dir, Math.max(0, len - i.radius - 0.05), _hit);
        if (hit) continue;
        best = i;
        bestScore = score;
      }
    }
    if (best !== this.focused) this.holdProgress = 0;
    this.focused = best;
  }

  promptText(i: Interactable): string {
    return typeof i.prompt === 'function' ? i.prompt() : i.prompt;
  }
}

const _t = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _hit = { point: new THREE.Vector3(), normal: new THREE.Vector3(), distance: 0, collider: null as never };
