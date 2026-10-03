import * as THREE from 'three';
import type { CollisionWorld } from './CollisionWorld';
import { damp } from '../core/Random';

export interface MoveInput {
  /** Desired horizontal move direction in world space (length 0..1). */
  wishX: number;
  wishZ: number;
  sprint: boolean;
  crouch: boolean;
  jump: boolean;
  /** Facing (for mantle/ladder detection). */
  forwardX: number;
  forwardZ: number;
}

export interface Ladder {
  id: string;
  /** Bottom centre of the ladder on the ground, top position where the player exits. */
  bottom: THREE.Vector3;
  top: THREE.Vector3;
  exit: THREE.Vector3;
  /** Unit vector pointing from the ladder towards where the climber stands (into the climbable side). */
  normal: THREE.Vector3;
}

export type MoveState = 'ground' | 'air' | 'mantle' | 'ladder';

/**
 * Capsule character controller for first-person movement. Handles walking, sprinting, crouching
 * with headroom checks, small jumps, gravity, slope limits, step-up via capsule resolution,
 * ground snapping on descent, contextual mantling onto ledges up to ~1.4 m and ladder climbing.
 */
export class CharacterController {
  readonly position = new THREE.Vector3(); // feet
  readonly velocity = new THREE.Vector3();
  radius = 0.3;
  standHeight = 1.78;
  crouchHeight = 1.15;
  height = 1.78;
  walkSpeed = 3.0;
  sprintSpeed = 5.0;
  crouchSpeed = 1.5;
  /** Multiplier from environment (mud, water, carrying). */
  speedMultiplier = 1;
  sprintAllowed = true;
  climbAllowed = true;
  gravity = 15.5;
  jumpSpeed = 4.2;
  state: MoveState = 'ground';
  grounded = true;
  crouching = false;
  readonly groundNormal = new THREE.Vector3(0, 1, 0);
  /** Horizontal speed actually achieved (for head bob / footsteps). */
  horizontalSpeed = 0;
  /** Distance travelled on ground, for footstep cadence. */
  strideDistance = 0;
  ladders: Ladder[] = [];
  private activeLadder: Ladder | null = null;
  private mantleFrom = new THREE.Vector3();
  private mantleTo = new THREE.Vector3();
  private mantleT = 0;
  private mantleDuration = 0.55;
  private coyote = 0;
  onLanded: ((fallSpeed: number) => void) | null = null;
  onMantle: (() => void) | null = null;

  constructor(private readonly world: CollisionWorld) {}

  teleport(p: THREE.Vector3): void {
    this.position.copy(p);
    this.velocity.set(0, 0, 0);
    this.state = 'air';
    this.activeLadder = null;
  }

  get eyeHeight(): number {
    return this.height - 0.14;
  }

  update(dt: number, input: MoveInput): void {
    // Sub-step to keep collision robust at low frame rates.
    const steps = Math.min(6, Math.max(1, Math.ceil(dt / (1 / 90))));
    const h = dt / steps;
    for (let i = 0; i < steps; i++) this.step(h, input, i === 0);
  }

  private step(dt: number, input: MoveInput, firstSubstep: boolean): void {
    if (this.state === 'mantle') return this.stepMantle(dt);
    if (this.state === 'ladder') return this.stepLadder(dt, input, firstSubstep);

    // --- crouch with headroom check
    const wantCrouch = input.crouch;
    if (wantCrouch && !this.crouching) this.crouching = true;
    else if (!wantCrouch && this.crouching && this.canStand()) this.crouching = false;
    const targetH = this.crouching ? this.crouchHeight : this.standHeight;
    this.height += (targetH - this.height) * damp(14, dt);

    // --- desired velocity
    let speed = this.crouching ? this.crouchSpeed : input.sprint && this.sprintAllowed ? this.sprintSpeed : this.walkSpeed;
    speed *= this.speedMultiplier;
    const wl = Math.hypot(input.wishX, input.wishZ);
    const wx = wl > 1 ? input.wishX / wl : input.wishX;
    const wz = wl > 1 ? input.wishZ / wl : input.wishZ;
    const accel = this.grounded ? 12 : 2.5;
    const k = damp(accel, dt);
    this.velocity.x += (wx * speed - this.velocity.x) * k;
    this.velocity.z += (wz * speed - this.velocity.z) * k;

    // --- jump / mantle / ladder entry
    if (firstSubstep && input.jump) {
      if (this.climbAllowed && this.tryLadder(input)) return;
      if (this.climbAllowed && this.tryMantle(input)) return;
      if (this.grounded || this.coyote > 0) {
        this.velocity.y = this.jumpSpeed;
        this.grounded = false;
        this.coyote = 0;
      }
    }
    // auto-grab ladders when walking into them
    if (firstSubstep && this.climbAllowed && wl > 0.5 && this.tryLadder(input, true)) return;

    // --- gravity
    if (!this.grounded) this.velocity.y -= this.gravity * dt;
    else this.velocity.y = Math.min(this.velocity.y, 0) - 2 * dt; // keep pressed onto ground

    const prevY = this.position.y;
    const wasGrounded = this.grounded;
    const fallSpeed = -this.velocity.y;
    // step-up: while grounded, lift the capsule by stepHeight before moving so low edges
    // (duckboards, rubble, stairs) are passed over instead of blocking; then snap back down.
    let stepping = wasGrounded && this.velocity.y <= 0.01;
    if (stepping) {
      // never lift into a low ceiling
      // never lift into a low ceiling — test where the capsule is about to move to
      this.buildSegment(_seg2);
      const mx = this.velocity.x * dt;
      const mz = this.velocity.z * dt;
      _seg2.start.set(_seg2.start.x + mx, _seg2.start.y + this.stepHeight + 0.05, _seg2.start.z + mz);
      _seg2.end.set(_seg2.end.x + mx, _seg2.end.y + this.stepHeight, _seg2.end.z + mz);
      if (this.world.capsuleOverlaps(_seg2, this.radius * 0.95)) stepping = false;
    }
    if (stepping) this.position.y += this.stepHeight;
    this.position.addScaledVector(this.velocity, dt);

    // --- collide
    this.buildSegment(_seg);
    const supported = this.world.resolveCapsule(_seg, this.radius, _gn);
    this.position.copy(_seg.start);
    this.position.y -= this.radius;

    if (stepping) {
      const g = this.probeGround(this.stepHeight + 0.12);
      if (g !== null && this.probeNormal.y > 0.62) {
        this.position.y = g;
        this.grounded = true;
        this.groundNormal.copy(this.probeNormal);
        if (this.velocity.y < 0) this.velocity.y = 0;
      } else {
        // walked off an edge: undo the lift and start falling
        this.position.y -= this.stepHeight;
        this.grounded = false;
      }
    } else if (supported && _gn.y > 0.62) {
      this.grounded = true;
      this.groundNormal.copy(_gn);
      if (this.velocity.y < 0) this.velocity.y = 0;
    } else {
      this.grounded = false;
      if (supported && _gn.y <= 0.62) this.velocity.y = Math.min(this.velocity.y, 0);
    }
    this.state = this.grounded ? 'ground' : 'air';
    if (this.grounded) this.coyote = 0.12;
    else this.coyote -= dt;

    // stop upward motion on ceilings
    if (this.position.y < prevY + this.velocity.y * dt - 0.001 && this.velocity.y > 0) this.velocity.y = 0;

    if (!wasGrounded && this.grounded && this.onLanded) this.onLanded(fallSpeed);

    this.horizontalSpeed = Math.hypot(this.velocity.x, this.velocity.z);
    if (this.grounded) this.strideDistance += this.horizontalSpeed * dt;
  }

  /** Maximum ledge height walked over without jumping. */
  stepHeight = 0.36;
  readonly probeNormal = new THREE.Vector3(0, 1, 0);

  /**
   * Highest supporting surface under the capsule footprint (centre + 4 points at 0.6 r), searched
   * from just above the feet down to `maxDrop`. Several rays avoid dropping through gaps between boards.
   */
  private probeGround(maxDrop: number): number | null {
    let best: number | null = null;
    const r = this.radius * 0.6;
    for (let i = 0; i < 5; i++) {
      const ox = i === 0 ? 0 : i === 1 ? r : i === 2 ? -r : 0;
      const oz = i === 3 ? r : i === 4 ? -r : 0;
      _o.set(this.position.x + ox, this.position.y + 0.06, this.position.z + oz);
      const hit = this.world.raycast(_o, _d, maxDrop + 0.06, _hit);
      if (hit && (best === null || hit.point.y > best)) {
        best = hit.point.y;
        this.probeNormal.copy(hit.normal);
      }
    }
    return best;
  }

  private buildSegment(seg: THREE.Line3, height = this.height): void {
    seg.start.set(this.position.x, this.position.y + this.radius, this.position.z);
    seg.end.set(this.position.x, this.position.y + Math.max(this.radius, height - this.radius), this.position.z);
  }

  private canStand(): boolean {
    this.buildSegment(_seg2, this.standHeight);
    _seg2.start.y += 0.25; // ignore floor contact
    return !this.world.capsuleOverlaps(_seg2, this.radius * 0.95);
  }

  /** Contextual mantle: a ledge 0.45–1.45 m above the feet directly ahead with headroom on top. */
  canMantle(fx: number, fz: number, out?: THREE.Vector3): boolean {
    const fl = Math.hypot(fx, fz) || 1;
    _f.set(fx / fl, 0, fz / fl);
    // must be facing an obstacle at knee/chest height
    _o.copy(this.position).y += 0.5;
    const wall = this.world.raycast(_o, _f, this.radius + 0.55, _hit);
    if (!wall) return false;
    if (wall.normal.y > 0.5) return false; // that's a slope, not a wall
    // look down from above for the ledge top
    _o.copy(this.position).addScaledVector(_f, this.radius + 0.5);
    _o.y += 1.75;
    const top = this.world.raycast(_o, _d, 1.6, _hit2);
    if (!top || top.normal.y < 0.7) return false;
    const rise = top.point.y - this.position.y;
    if (rise < 0.4 || rise > 1.5) return false;
    // headroom on top (crouch height is enough)
    _seg2.start.set(top.point.x, top.point.y + this.radius + 0.05, top.point.z);
    _seg2.end.set(top.point.x, top.point.y + this.crouchHeight - this.radius, top.point.z);
    if (this.world.capsuleOverlaps(_seg2, this.radius * 0.9)) return false;
    if (out) out.copy(top.point);
    return true;
  }

  private tryMantle(input: MoveInput): boolean {
    if (!this.canMantle(input.forwardX, input.forwardZ, this.mantleTo)) return false;
    this.mantleFrom.copy(this.position);
    this.mantleT = 0;
    const rise = this.mantleTo.y - this.position.y;
    this.mantleDuration = 0.35 + rise * 0.3;
    this.state = 'mantle';
    this.velocity.set(0, 0, 0);
    this.onMantle?.();
    return true;
  }

  private stepMantle(dt: number): void {
    this.mantleT += dt / this.mantleDuration;
    const t = Math.min(1, this.mantleT);
    // rise first, then move over the edge
    const up = 1 - Math.pow(1 - Math.min(1, t * 1.6), 2);
    const fwd = t < 0.45 ? 0 : (t - 0.45) / 0.55;
    const fwdE = fwd * fwd * (3 - 2 * fwd);
    this.position.x = this.mantleFrom.x + (this.mantleTo.x - this.mantleFrom.x) * fwdE;
    this.position.z = this.mantleFrom.z + (this.mantleTo.z - this.mantleFrom.z) * fwdE;
    this.position.y = this.mantleFrom.y + (this.mantleTo.y + 0.02 - this.mantleFrom.y) * up;
    if (t >= 1) {
      this.state = 'ground';
      this.grounded = true;
      this.crouching = !this.canStand();
    }
  }

  nearbyLadder(maxDist = 1.0): Ladder | null {
    for (const l of this.ladders) {
      // distance from player to ladder's vertical line (horizontal) and within its height range
      const dx = this.position.x - l.bottom.x;
      const dz = this.position.z - l.bottom.z;
      const horiz = Math.hypot(dx, dz);
      if (horiz > maxDist) continue;
      if (this.position.y < l.bottom.y - 0.5 || this.position.y > l.top.y + 0.3) continue;
      return l;
    }
    return null;
  }

  private tryLadder(input: MoveInput, passive = false): boolean {
    // descending: standing at the top and walking off the edge towards the climbing side
    for (const lt of this.ladders) {
      const dxT = this.position.x - lt.exit.x;
      const dzT = this.position.z - lt.exit.z;
      if (Math.hypot(dxT, dzT) > 1.3 || Math.abs(this.position.y - lt.top.y) > 0.6) continue;
      const toward = input.wishX * lt.normal.x + input.wishZ * lt.normal.z;
      if (toward < 0.5) continue;
      this.activeLadder = lt;
      this.state = 'ladder';
      this.velocity.set(0, 0, 0);
      this.position.set(lt.bottom.x + lt.normal.x * (this.radius + 0.08), lt.top.y - 0.25, lt.bottom.z + lt.normal.z * (this.radius + 0.08));
      return true;
    }
    const l = this.nearbyLadder(passive ? 0.65 : 1.0);
    if (!l) return false;
    // must face the ladder: forward opposite to ladder normal
    const facing = -(input.forwardX * l.normal.x + input.forwardZ * l.normal.z);
    if (facing < (passive ? 0.6 : 0.3)) return false;
    if (passive) {
      const moving = -(input.wishX * l.normal.x + input.wishZ * l.normal.z);
      if (moving < 0.5) return false;
    }
    if (this.position.y > l.top.y - 0.2) return false; // already at top
    this.activeLadder = l;
    this.state = 'ladder';
    this.velocity.set(0, 0, 0);
    this.position.x = l.bottom.x + l.normal.x * (this.radius + 0.08);
    this.position.z = l.bottom.z + l.normal.z * (this.radius + 0.08);
    return true;
  }

  get onLadder(): boolean {
    return this.state === 'ladder';
  }

  private stepLadder(dt: number, input: MoveInput, first: boolean): void {
    const l = this.activeLadder!;
    // forward key climbs up, back climbs down (relative to facing ladder)
    const climb = -(input.wishX * l.normal.x + input.wishZ * l.normal.z);
    const vy = climb * 1.6;
    this.position.y += vy * dt;
    this.horizontalSpeed = Math.abs(vy);
    this.strideDistance += Math.abs(vy) * dt;
    if (this.position.y >= l.top.y - 0.05) {
      // exit onto top
      this.position.copy(l.exit);
      this.state = 'ground';
      this.grounded = true;
      this.activeLadder = null;
      return;
    }
    if (this.position.y <= l.bottom.y && climb < 0) {
      this.position.y = l.bottom.y;
      this.state = 'ground';
      this.activeLadder = null;
      return;
    }
    if (first && input.jump) {
      // let go
      this.state = 'air';
      this.grounded = false;
      this.velocity.set(l.normal.x * 2, 0, l.normal.z * 2);
      this.activeLadder = null;
    }
  }
}

const _seg = new THREE.Line3();
const _seg2 = new THREE.Line3();
const _gn = new THREE.Vector3();
const _f = new THREE.Vector3();
const _o = new THREE.Vector3();
const _d = new THREE.Vector3(0, -1, 0);
const _hit = { point: new THREE.Vector3(), normal: new THREE.Vector3(), distance: 0, collider: null as never };
const _hit2 = { point: new THREE.Vector3(), normal: new THREE.Vector3(), distance: 0, collider: null as never };
