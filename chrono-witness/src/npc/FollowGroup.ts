import * as THREE from 'three';
import type { NPC } from './NPC';

/**
 * Escort helper: followers walk along the leader's recorded trail (breadcrumbs), each a fixed
 * distance further back, so they get through doors, round corners and down stairs exactly where the
 * player went — no navmesh needed. Followers stop when the leader stops.
 */
export class FollowGroup {
  private trail: THREE.Vector3[] = [];
  private trailLen: number[] = [0];
  private total = 0;
  active = false;
  /** Followers wait (e.g. in a doorway during a hazard) instead of following. */
  holding = false;

  constructor(
    readonly members: NPC[],
    readonly spacing = 1.5,
    readonly lead = 1.8,
  ) {}

  start(leader: THREE.Vector3): void {
    this.trail = [leader.clone()];
    this.trailLen = [0];
    this.total = 0;
    this.active = true;
    for (const m of this.members) {
      m.mode = 'scripted';
      m.yieldToPlayer = false;
    }
  }

  stop(): void {
    this.active = false;
    for (const m of this.members) {
      m.mode = 'idle';
      m.speed = 0;
      m.play(m.pose);
    }
  }

  /** Point on the trail `back` metres behind its newest end. */
  private pointBack(back: number, out: THREE.Vector3): THREE.Vector3 {
    const target = Math.max(0, this.total - back);
    let i = this.trailLen.length - 1;
    while (i > 0 && this.trailLen[i] > target) i--;
    if (i >= this.trail.length - 1) return out.copy(this.trail[this.trail.length - 1]);
    const a = this.trail[i];
    const b = this.trail[i + 1];
    const seg = this.trailLen[i + 1] - this.trailLen[i];
    const k = seg > 1e-6 ? (target - this.trailLen[i]) / seg : 0;
    return out.lerpVectors(a, b, k);
  }

  update(dt: number, leader: THREE.Vector3): void {
    if (!this.active) return;
    const last = this.trail[this.trail.length - 1];
    const d = Math.hypot(leader.x - last.x, leader.z - last.z);
    if (d > 0.35) {
      this.trail.push(leader.clone());
      this.total += d;
      this.trailLen.push(this.total);
      if (this.trail.length > 600) {
        this.trail.splice(0, 200);
        const base = this.trailLen[200];
        this.trailLen = this.trailLen.slice(200).map((v) => v - base);
        this.total -= base;
      }
    }
    this.members.forEach((m, i) => {
      const tgt = this.pointBack(this.lead + i * this.spacing, _t);
      const p = m.root.position;
      const dx = tgt.x - p.x;
      const dz = tgt.z - p.z;
      const dist = Math.hypot(dx, dz);
      const want = this.holding ? 0 : dist > 0.25 ? Math.min(dist > 4 ? 3.0 : 1.6, dist * 1.8) : 0;
      m.speed += (want - m.speed) * Math.min(1, dt * 5);
      if (m.speed > 0.05 && dist > 0.01) {
        const step = Math.min(dist, m.speed * dt);
        p.x += (dx / dist) * step;
        p.z += (dz / dist) * step;
        m.faceTowards(tgt);
        const clip = m.speed > 2.3 ? 'run' : m.locomotionClip;
        const cs = clip === 'run' ? 3.6 : 1.4;
        m.play(clip, 0.3, Math.max(0.35, m.speed / cs));
      } else if (m.currentClip === 'walk' || m.currentClip === 'run' || m.currentClip === m.locomotionClip) {
        m.play(this.holding ? 'idle' : m.pose, 0.4);
      }
      // height follows the trail point (stairs) unless the NPC has a ground function
      if (!m.groundFn) p.y += (tgt.y - p.y) * Math.min(1, dt * 8);
    });
  }

  /** All members within `r` of a point. */
  allWithin(p: THREE.Vector3, r: number): boolean {
    return this.members.every((m) => m.root.position.distanceTo(p) < r);
  }
}

const _t = new THREE.Vector3();
