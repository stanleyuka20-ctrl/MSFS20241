import * as THREE from 'three';
import type { CharacterLibrary } from './CharacterLibrary';
import type { NavGraph } from './NavGraph';
import { damp } from '../core/Random';

export type NPCMode = 'idle' | 'path' | 'follow' | 'scripted';

export interface NPCOptions {
  id: string;
  name: string;
  character: string;
  position: THREE.Vector3;
  yaw?: number;
  /** Base idle clip (idle, sit_ground, kneel_work, lie_supine, talk…). */
  pose?: string;
  walkSpeed?: number;
  /** Look at the player when close. */
  attentive?: boolean;
  /** Hide the helmet/cap mesh by name, etc. */
  hideMeshes?: string[];
}

/**
 * Animated non-player character. Locomotion playback rate is matched to actual ground speed
 * (clip speed from metadata) so feet do not slide; turning is damped; the head turns towards the
 * player when nearby; animation updates are throttled with distance.
 */
export class NPC {
  readonly root = new THREE.Group();
  readonly id: string;
  name: string;
  model: THREE.Object3D | null = null;
  mixer: THREE.AnimationMixer | null = null;
  private actions = new Map<string, THREE.AnimationAction>();
  private current: THREE.AnimationAction | null = null;
  currentClip = '';
  mode: NPCMode = 'idle';
  pose: string;
  walkSpeed: number;
  speed = 0;
  yaw: number;
  private targetYaw: number;
  path: THREE.Vector3[] = [];
  private pathIndex = 0;
  followTarget: THREE.Vector3 | null = null;
  followDistance = 2.2;
  onArrive: (() => void) | null = null;
  attentive: boolean;
  private head: THREE.Bone | null = null;
  private neck: THREE.Bone | null = null;
  private lookWeight = 0;
  private animAccumulator = 0;
  private lod0: THREE.Object3D[] = [];
  private lod1: THREE.Object3D[] = [];
  private lodLevel = -1;
  /** Override locomotion clip (e.g. carry_walk, limp_walk). */
  locomotionClip = 'walk';
  /** Waits instead of walking into the player in narrow trenches. */
  yieldToPlayer = true;
  waiting = false;
  visible = true;
  readonly lookTarget = new THREE.Vector3();
  hasLookTarget = false;
  groundFn: ((x: number, y: number, z: number) => number | null) | null = null;
  private groundTimer = 0;

  constructor(
    opts: NPCOptions,
    private readonly lib: CharacterLibrary,
  ) {
    this.id = opts.id;
    this.name = opts.name;
    this.pose = opts.pose ?? 'idle';
    this.walkSpeed = opts.walkSpeed ?? 1.35;
    this.yaw = this.targetYaw = opts.yaw ?? 0;
    this.attentive = opts.attentive ?? true;
    this.root.position.copy(opts.position);
    this.root.rotation.y = this.yaw;
    this.root.name = `npc:${opts.id}`;
    const model = lib.instantiate(opts.character);
    if (model) {
      this.model = model;
      this.root.add(model);
      this.mixer = new THREE.AnimationMixer(model);
      model.traverse((o) => {
        if ((o as THREE.Bone).isBone) {
          const n = o.name.toLowerCase();
          if (!this.head && n.startsWith('head') && !n.includes('end')) this.head = o as THREE.Bone;
          if (!this.neck && n.startsWith('neck')) this.neck = o as THREE.Bone;
        }
        if ((o as THREE.Mesh).isMesh) {
          if (opts.hideMeshes?.some((h) => o.name.toLowerCase().includes(h))) o.visible = false;
          else if (isLod1(o)) this.lod1.push(o);
          else this.lod0.push(o);
        }
      });
      if (this.lod1.length === 0) this.lod1 = this.lod0;
    }
    this.play(this.pose, 0);
  }

  play(clip: string, fade = 0.35, timeScale = 1): void {
    if (!this.mixer) return;
    if (this.currentClip === clip && this.current) {
      this.current.timeScale = timeScale;
      return;
    }
    let a = this.actions.get(clip);
    if (!a) {
      const c = this.lib.clips.get(clip) ?? this.lib.clips.get('idle');
      if (!c) return;
      a = this.mixer.clipAction(c);
      const meta = this.lib.meta[clip];
      if (meta && !meta.loop) {
        a.setLoop(THREE.LoopOnce, 1);
        a.clampWhenFinished = true;
      }
      this.actions.set(clip, a);
    }
    a.reset();
    a.timeScale = timeScale;
    // desynchronise crowds
    if (this.lib.meta[clip]?.loop !== false) a.time = Math.random() * a.getClip().duration;
    a.play();
    if (this.current && fade > 0) this.current.crossFadeTo(a, fade, false);
    else if (this.current) this.current.stop();
    this.current = a;
    this.currentClip = clip;
  }

  setPose(clip: string): void {
    this.pose = clip;
    if (this.mode === 'idle') this.play(clip);
  }

  faceTowards(p: THREE.Vector3, immediate = false): void {
    this.targetYaw = Math.atan2(p.x - this.root.position.x, p.z - this.root.position.z);
    if (immediate) {
      this.yaw = this.targetYaw;
      this.root.rotation.y = this.yaw;
    }
  }

  walkPath(path: THREE.Vector3[], onArrive?: () => void): void {
    this.path = path;
    this.pathIndex = 0;
    this.mode = 'path';
    this.onArrive = onArrive ?? null;
  }

  walkTo(nav: NavGraph, target: THREE.Vector3, onArrive?: () => void): boolean {
    const p = nav.findPath(this.root.position, target);
    if (!p) return false;
    this.walkPath(p, onArrive);
    return true;
  }

  follow(target: THREE.Vector3, distance = 2.2): void {
    this.followTarget = target;
    this.followDistance = distance;
    this.mode = 'follow';
  }

  stop(): void {
    this.mode = 'idle';
    this.path = [];
    this.speed = 0;
    this.play(this.pose);
  }

  teleport(p: THREE.Vector3, yaw?: number): void {
    this.root.position.copy(p);
    if (yaw !== undefined) {
      this.yaw = this.targetYaw = yaw;
      this.root.rotation.y = yaw;
    }
  }

  update(dt: number, camPos: THREE.Vector3, playerPos: THREE.Vector3, animLodDist: number, inView: boolean): void {
    const pos = this.root.position;
    let desiredSpeed = 0;
    let moveX = 0;
    let moveZ = 0;
    this.waiting = false;

    if (this.mode === 'path' && this.path.length) {
      const target = this.path[this.pathIndex];
      const dx = target.x - pos.x;
      const dz = target.z - pos.z;
      const d = Math.hypot(dx, dz);
      const isLast = this.pathIndex === this.path.length - 1;
      if (d < (isLast ? 0.15 : 0.55)) {
        this.pathIndex++;
        if (this.pathIndex >= this.path.length) {
          this.mode = 'idle';
          this.path = [];
          this.play(this.pose);
          const cb = this.onArrive;
          this.onArrive = null;
          cb?.();
        }
      } else {
        desiredSpeed = isLast ? Math.min(this.walkSpeed, d * 1.2 + 0.3) : this.walkSpeed;
        moveX = dx / d;
        moveZ = dz / d;
      }
    } else if (this.mode === 'follow' && this.followTarget) {
      const dx = this.followTarget.x - pos.x;
      const dz = this.followTarget.z - pos.z;
      const d = Math.hypot(dx, dz);
      if (d > this.followDistance) {
        desiredSpeed = Math.min(this.walkSpeed * (d > this.followDistance + 4 ? 2.4 : 1), (d - this.followDistance) * 1.5 + 0.4);
        moveX = dx / d;
        moveZ = dz / d;
      }
    }

    // yield to the player blocking the way in narrow spaces
    if (desiredSpeed > 0 && this.yieldToPlayer && this.mode === 'path') {
      const px = playerPos.x - pos.x;
      const pz = playerPos.z - pos.z;
      const pd = Math.hypot(px, pz);
      if (pd < 1.1 && (px * moveX + pz * moveZ) / pd > 0.5) {
        desiredSpeed = 0;
        this.waiting = true;
      }
    }

    if (this.mode !== 'scripted') {
      this.speed += (desiredSpeed - this.speed) * damp(desiredSpeed > this.speed ? 4 : 7, dt);
      if (this.speed > 0.05) {
        pos.x += moveX * this.speed * dt;
        pos.z += moveZ * this.speed * dt;
        if (moveX || moveZ) this.targetYaw = Math.atan2(moveX, moveZ);
        const runClip = this.speed > 2.4 && this.lib.clips.has('run') && this.locomotionClip === 'walk' ? 'run' : this.locomotionClip;
        const clipSpeed = this.lib.clipSpeed(runClip) || 1.4;
        this.play(runClip, 0.3, Math.max(0.3, this.speed / clipSpeed));
      } else if ((this.currentClip === 'walk' || this.currentClip === 'run' || this.currentClip === this.locomotionClip)) {
        this.play(this.waiting ? 'idle' : this.pose, 0.4);
      }
    }
    // ground following (periodic raycast; cheap)
    this.groundTimer -= dt;
    if (this.groundFn && (this.speed > 0.05 || this.groundTimer < -2)) {
      if (this.groundTimer <= 0) {
        const g = this.groundFn(pos.x, pos.y + 0.8, pos.z);
        if (g !== null) this.groundY = g;
        this.groundTimer = this.speed > 0.05 ? 0.08 : 1.5;
      }
      pos.y += (this.groundY - pos.y) * damp(14, dt);
    }

    // turning
    let dy = this.targetYaw - this.yaw;
    while (dy > Math.PI) dy -= Math.PI * 2;
    while (dy < -Math.PI) dy += Math.PI * 2;
    this.yaw += dy * damp(this.speed > 0.1 ? 6 : 3.5, dt);
    this.root.rotation.y = this.yaw;

    // LOD + animation throttling
    const camDist = pos.distanceTo(camPos);
    const lod = camDist > 16 ? 1 : 0;
    if (lod !== this.lodLevel && this.lod1 !== this.lod0) {
      for (const m of this.lod0) m.visible = lod === 0;
      for (const m of this.lod1) m.visible = lod === 1;
      this.lodLevel = lod;
    }
    if (!this.mixer) return;
    this.animAccumulator += dt;
    const interval = !inView ? 0.25 : camDist > animLodDist ? 1 / 15 : 0;
    if (this.animAccumulator >= interval) {
      this.mixer.update(this.animAccumulator);
      this.animAccumulator = 0;
      if (inView && camDist < 8) this.applyLook(playerPos, camPos, dt);
    }
  }

  private groundY = this.root.position.y;

  private applyLook(playerPos: THREE.Vector3, camPos: THREE.Vector3, dt: number): void {
    if (!this.head) return;
    const target = this.hasLookTarget ? this.lookTarget : camPos;
    const wantLook = (this.attentive || this.hasLookTarget) && this.speed < 0.5 && (this.hasLookTarget || playerPos.distanceTo(this.root.position) < 4.5);
    // angle between facing and target
    const dx = target.x - this.root.position.x;
    const dz = target.z - this.root.position.z;
    let ang = Math.atan2(dx, dz) - this.yaw;
    while (ang > Math.PI) ang -= Math.PI * 2;
    while (ang < -Math.PI) ang += Math.PI * 2;
    const ok = wantLook && Math.abs(ang) < 1.6;
    this.lookWeight += ((ok ? 1 : 0) - this.lookWeight) * damp(4, dt);
    if (this.lookWeight < 0.01) return;
    const yawAmt = THREE.MathUtils.clamp(ang, -1.1, 1.1) * this.lookWeight;
    const headY = this.root.position.y + 1.6;
    const pitchAmt = THREE.MathUtils.clamp(Math.atan2(target.y - headY, Math.hypot(dx, dz)), -0.5, 0.5) * this.lookWeight;
    // distribute between neck and head, applied in world-ish space around the character's up axis
    if (this.neck) {
      rotateBoneWorld(this.neck, _up, yawAmt * 0.4, this.root);
      rotateBoneWorld(this.head, _up, yawAmt * 0.6, this.root);
    } else rotateBoneWorld(this.head, _up, yawAmt, this.root);
    rotateBoneWorldLocalRight(this.head, -pitchAmt * 0.7, this.root);
  }

  setVisible(v: boolean): void {
    this.visible = v;
    this.root.visible = v;
  }

  dispose(): void {
    this.mixer?.stopAllAction();
    if (this.model) this.mixer?.uncacheRoot(this.model);
    this.root.removeFromParent();
  }
}

/** LOD1 meshes are exported as `<id>_LOD1` nodes; multi-material meshes become children of that node. */
function isLod1(o: THREE.Object3D): boolean {
  for (let p: THREE.Object3D | null = o; p; p = p.parent) if (/lod1/i.test(p.name)) return true;
  return false;
}

const _up = new THREE.Vector3(0, 1, 0);
const _right = new THREE.Vector3(1, 0, 0);
const _q = new THREE.Quaternion();
const _qw = new THREE.Quaternion();
const _qp = new THREE.Quaternion();
const _axis = new THREE.Vector3();

/** Rotate a bone about an axis expressed in the character root's space (post-animation additive). */
function rotateBoneWorld(bone: THREE.Bone, axisRoot: THREE.Vector3, angle: number, root: THREE.Object3D): void {
  if (Math.abs(angle) < 1e-4) return;
  root.updateWorldMatrix(true, false);
  bone.parent!.updateWorldMatrix(true, false);
  _axis.copy(axisRoot).transformDirection(root.matrixWorld);
  bone.parent!.getWorldQuaternion(_qp);
  _axis.applyQuaternion(_qw.copy(_qp).invert());
  _q.setFromAxisAngle(_axis.normalize(), angle);
  bone.quaternion.premultiply(_q);
}

function rotateBoneWorldLocalRight(bone: THREE.Bone, angle: number, root: THREE.Object3D): void {
  if (Math.abs(angle) < 1e-4) return;
  rotateBoneWorld(bone, _right, angle, root);
}
