import { describe, it, expect, beforeEach } from 'vitest';
import * as THREE from 'three';
import { NavGraph } from '../src/npc/NavGraph';
import { PerfStats } from '../src/render/PerfStats';
import { applyPreset, defaultSettings, PRESETS } from '../src/core/Settings';
import { Noise2D, Rng } from '../src/core/Random';
import { CollisionWorld } from '../src/physics/CollisionWorld';
import { CharacterController } from '../src/physics/CharacterController';

describe('NavGraph', () => {
  it('finds paths and respects blocked nodes', () => {
    const n = new NavGraph();
    const a = n.addPath([new THREE.Vector3(0, 0, 0), new THREE.Vector3(5, 0, 0), new THREE.Vector3(10, 0, 0)]);
    const b = n.addPath([new THREE.Vector3(0, 0, 0.1), new THREE.Vector3(5, 0, 6), new THREE.Vector3(10, 0, 0.1)]);
    n.link(a[0], b[0]);
    n.link(a[2], b[2]);
    expect(n.findPath(new THREE.Vector3(0, 0, 0), new THREE.Vector3(10, 0, 0))!.length).toBeGreaterThan(1);
    n.blockRadius(new THREE.Vector3(5, 0, 0), 1);
    const p = n.findPath(new THREE.Vector3(0, 0, 0), new THREE.Vector3(10, 0, 0))!;
    expect(p.some((v) => Math.abs(v.z - 6) < 0.01)).toBe(true);
  });
});

describe('PerfStats', () => {
  it('computes average fps and 1% lows from frame times', () => {
    const s = new PerfStats(1000);
    for (let i = 0; i < 990; i++) s.push(10);
    for (let i = 0; i < 10; i++) s.push(50);
    const r = s.summary();
    expect(r.frames).toBe(1000);
    expect(r.avgFps).toBeCloseTo(1000 / 10.4, 1);
    expect(r.low1Fps).toBeCloseTo(20, 1);
    expect(r.maxMs).toBe(50);
  });
});

describe('Settings presets', () => {
  it('low reduces expensive features before art direction', () => {
    const s = defaultSettings();
    applyPreset(s.graphics, 'low');
    expect(s.graphics.ambientOcclusion).toBe(false);
    expect(s.graphics.shadowQuality).toBeLessThan(PRESETS.high.shadowQuality);
    expect(s.graphics.resolutionScale).toBeLessThan(1);
    applyPreset(s.graphics, 'custom');
    expect(s.graphics.preset).toBe('custom');
  });
});

describe('Random', () => {
  it('is deterministic', () => {
    const a = new Rng(5);
    const b = new Rng(5);
    for (let i = 0; i < 10; i++) expect(a.next()).toBe(b.next());
    const n = new Noise2D(1);
    expect(n.get(1.3, 2.7)).toBe(new Noise2D(1).get(1.3, 2.7));
    expect(Math.abs(n.fbm(3, 4))).toBeLessThanOrEqual(1);
  });
});

describe('CharacterController', () => {
  let world: CollisionWorld;
  beforeEach(() => {
    world = new CollisionWorld();
    const floor = new THREE.PlaneGeometry(40, 40, 4, 4).rotateX(-Math.PI / 2);
    world.addStaticMesh(floor);
    // a 0.2 m step and a 2 m wall
    world.addStaticBox(new THREE.Vector3(0, 0.1, -3), new THREE.Vector3(4, 0.2, 2));
    world.addStaticBox(new THREE.Vector3(0, 1, -8), new THREE.Vector3(6, 2, 0.4));
    world.buildStatic();
  });
  const walk = (c: CharacterController, seconds: number) => {
    for (let i = 0; i < seconds * 60; i++) c.update(1 / 60, { wishX: 0, wishZ: -1, sprint: false, crouch: false, jump: false, forwardX: 0, forwardZ: -1 });
  };
  it('stands on the floor, steps up low ledges and is stopped by walls', () => {
    const c = new CharacterController(world);
    c.teleport(new THREE.Vector3(0, 0.5, 0));
    walk(c, 0.5);
    expect(c.position.y).toBeCloseTo(0, 1);
    walk(c, 0.5);
    expect(c.position.z).toBeLessThan(-2.1);
    expect(c.position.y).toBeGreaterThan(0.15); // on the step
    walk(c, 4);
    expect(c.position.z).toBeGreaterThan(-8 + 0.2 + 0.25); // wall blocks
    expect(c.position.y).toBeGreaterThan(-0.05); // never falls through
  });
  it('mantles onto a ledge when jumping at it', () => {
    world.addStaticBox(new THREE.Vector3(5, 0.5, -1), new THREE.Vector3(2, 1, 2));
    world.dispose();
    const w2 = new CollisionWorld();
    w2.addStaticMesh(new THREE.PlaneGeometry(40, 40).rotateX(-Math.PI / 2));
    w2.addStaticBox(new THREE.Vector3(0, 0.5, -2), new THREE.Vector3(4, 1, 2));
    w2.buildStatic();
    const c = new CharacterController(w2);
    c.teleport(new THREE.Vector3(0, 0.2, -0.6));
    for (let i = 0; i < 20; i++) c.update(1 / 60, { wishX: 0, wishZ: -1, sprint: false, crouch: false, jump: false, forwardX: 0, forwardZ: -1 });
    c.update(1 / 60, { wishX: 0, wishZ: -1, sprint: false, crouch: false, jump: true, forwardX: 0, forwardZ: -1 });
    for (let i = 0; i < 90; i++) c.update(1 / 60, { wishX: 0, wishZ: 0, sprint: false, crouch: false, jump: false, forwardX: 0, forwardZ: -1 });
    expect(c.position.y).toBeGreaterThan(0.9);
    expect(c.grounded).toBe(true);
  });
});
