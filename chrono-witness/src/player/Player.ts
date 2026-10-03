import * as THREE from 'three';
import { CharacterController, type MoveInput } from '../physics/CharacterController';
import type { CollisionWorld } from '../physics/CollisionWorld';
import type { Input } from '../core/Input';
import type { Settings } from '../core/Settings';
import { clamp, damp } from '../core/Random';

export type SurfaceFn = (x: number, y: number, z: number) => { surface: string; speed: number };

/**
 * First-person player: maps input to the capsule controller and drives the camera with
 * restrained, setting-scaled head bob, landing dip, crouch easing and trauma-based shake.
 */
export class Player {
  readonly camera: THREE.PerspectiveCamera;
  readonly controller: CharacterController;
  yaw = 0;
  pitch = 0;
  /** 0..1 camera shake energy; decays over time. */
  trauma = 0;
  private bobPhase = 0;
  private bobAmount = 0;
  private landDip = 0;
  private eyeSmoothed = 1.64;
  private lastStride = 0;
  private sprintToggle = false;
  private crouchToggle = false;
  carrying = false;
  /** Locks movement (dialogue, cinematics) while keeping the camera alive. */
  movementLocked = false;
  lookLocked = false;
  surfaceAt: SurfaceFn | null = null;
  currentSurface = 'default';
  onFootstep: ((surface: string, intensity: number) => void) | null = null;
  onLand: ((surface: string, speed: number) => void) | null = null;
  readonly forward = new THREE.Vector3();
  private readonly moveInput: MoveInput = { wishX: 0, wishZ: 0, sprint: false, crouch: false, jump: false, forwardX: 0, forwardZ: -1 };
  private shakeTime = 0;
  /** Extra external speed multiplier (scripted: wading, exhaustion). */
  scriptSpeed = 1;

  constructor(world: CollisionWorld, private readonly settings: Settings) {
    this.camera = new THREE.PerspectiveCamera(settings.controls.fov, 16 / 9, 0.05, 2000);
    this.camera.rotation.order = 'YXZ';
    this.controller = new CharacterController(world);
    this.controller.onLanded = (v) => {
      if (v > 3) {
        this.landDip = Math.min(0.18, (v - 3) * 0.025);
        this.onLand?.(this.currentSurface, v);
      }
    };
  }

  get position(): THREE.Vector3 {
    return this.controller.position;
  }

  spawn(pos: THREE.Vector3, yaw: number): void {
    this.controller.teleport(pos);
    this.yaw = yaw;
    this.pitch = 0;
    this.trauma = 0;
    this.eyeSmoothed = this.controller.eyeHeight;
    this.updateCamera(0);
  }

  addTrauma(amount: number): void {
    this.trauma = Math.min(1, this.trauma + amount);
  }

  update(dt: number, input: Input, gameplay: boolean): void {
    const c = this.settings.controls;
    if (gameplay && !this.lookLocked) {
      const sens = 0.0022 * c.mouseSensitivity;
      this.yaw -= input.mouseDX * sens;
      this.pitch -= input.mouseDY * sens * (c.invertY ? -1 : 1);
      this.pitch = clamp(this.pitch, -1.48, 1.48);
    }
    // movement
    const mi = this.moveInput;
    const sinY = Math.sin(this.yaw);
    const cosY = Math.cos(this.yaw);
    mi.forwardX = -sinY;
    mi.forwardZ = -cosY;
    let f = 0;
    let s = 0;
    if (gameplay && !this.movementLocked) {
      if (input.isDown('forward')) f += 1;
      if (input.isDown('back')) f -= 1;
      if (input.isDown('right')) s += 1;
      if (input.isDown('left')) s -= 1;
      if (c.toggleSprint) {
        if (input.pressed('sprint')) this.sprintToggle = !this.sprintToggle;
        if (f <= 0) this.sprintToggle = false;
      }
      if (c.toggleCrouch) {
        if (input.pressed('crouch')) this.crouchToggle = !this.crouchToggle;
      }
      mi.sprint = (c.toggleSprint ? this.sprintToggle : input.isDown('sprint')) && f > 0 && !this.carrying;
      mi.crouch = c.toggleCrouch ? this.crouchToggle : input.isDown('crouch');
      mi.jump = input.pressed('jump') && !this.carrying;
    } else {
      mi.sprint = false;
      mi.jump = false;
    }
    mi.wishX = f * mi.forwardX + s * cosY;
    mi.wishZ = f * mi.forwardZ - s * sinY;

    // environment speed (mud, water) and carry state
    const ctl = this.controller;
    let envSpeed = 1;
    if (this.surfaceAt) {
      const si = this.surfaceAt(ctl.position.x, ctl.position.y, ctl.position.z);
      this.currentSurface = si.surface;
      envSpeed = si.speed;
    }
    ctl.speedMultiplier = envSpeed * (this.carrying ? 0.62 : 1) * this.scriptSpeed;
    ctl.sprintAllowed = !this.carrying;
    ctl.climbAllowed = !this.carrying;
    ctl.update(dt, mi);

    // footsteps
    if (ctl.grounded || ctl.onLadder) {
      const strideLen = ctl.onLadder ? 0.45 : mi.sprint ? 1.45 : ctl.crouching ? 0.7 : 1.1;
      if (ctl.strideDistance - this.lastStride > strideLen) {
        this.lastStride = ctl.strideDistance;
        this.onFootstep?.(ctl.onLadder ? 'ladder' : this.currentSurface, clamp(ctl.horizontalSpeed / 5, 0.25, 1));
      }
    }
    this.updateCamera(dt);
  }

  private updateCamera(dt: number): void {
    const a = this.settings.accessibility;
    const ctl = this.controller;
    const cam = this.camera;
    if (cam.fov !== this.settings.controls.fov) {
      cam.fov = this.settings.controls.fov;
      cam.updateProjectionMatrix();
    }
    // eye height eases with crouch
    this.eyeSmoothed += (ctl.eyeHeight - this.eyeSmoothed) * damp(12, dt);
    // head bob proportional to speed
    const moving = ctl.grounded && ctl.horizontalSpeed > 0.3;
    this.bobAmount += ((moving ? Math.min(1, ctl.horizontalSpeed / 4) : 0) - this.bobAmount) * damp(6, dt);
    this.bobPhase += dt * (ctl.horizontalSpeed > 4 ? 11 : 8.5) * (moving ? 1 : 0.3);
    const bob = a.headBob * this.bobAmount;
    const bobY = Math.abs(Math.sin(this.bobPhase)) * 0.035 * bob;
    const bobX = Math.cos(this.bobPhase) * 0.02 * bob;
    this.landDip += (0 - this.landDip) * damp(7, dt);

    // shake
    this.trauma = Math.max(0, this.trauma - dt * 0.7);
    this.shakeTime += dt;
    const sh = this.trauma * this.trauma * a.cameraShake;
    const t = this.shakeTime * 23;
    const shX = (Math.sin(t * 1.3) + Math.sin(t * 2.9) * 0.5) * 0.012 * sh;
    const shY = (Math.sin(t * 1.7 + 1.3) + Math.sin(t * 3.7) * 0.5) * 0.012 * sh;
    const shR = Math.sin(t * 1.1 + 0.7) * 0.02 * sh;

    const sinY = Math.sin(this.yaw);
    const cosY = Math.cos(this.yaw);
    cam.position.set(
      ctl.position.x + cosY * bobX,
      ctl.position.y + this.eyeSmoothed + bobY - this.landDip,
      ctl.position.z - sinY * bobX,
    );
    cam.rotation.set(this.pitch + shY, this.yaw + shX, shR + bobX * 0.15 * a.motionEffects);
    cam.updateMatrixWorld();
    this.forward.set(0, 0, -1).applyQuaternion(cam.quaternion);
  }
}
