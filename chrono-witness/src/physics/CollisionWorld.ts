import * as THREE from 'three';
import { MeshBVH, type ExtendedTriangle } from 'three-mesh-bvh';
import * as BufferGeometryUtils from 'three/examples/jsm/utils/BufferGeometryUtils.js';

/** A BVH collider. Static colliders have an identity matrix; dynamic ones (doors, debris) can move or be disabled. */
export interface Collider {
  id: string;
  bvh: MeshBVH;
  geometry: THREE.BufferGeometry;
  matrix: THREE.Matrix4;
  inverse: THREE.Matrix4;
  enabled: boolean;
  isStatic: boolean;
  /** Optional surface tag returned with raycast hits (e.g. 'wood', 'mud'). */
  surface?: string;
}

export interface RayHit {
  point: THREE.Vector3;
  normal: THREE.Vector3;
  distance: number;
  collider: Collider;
}

/**
 * Collision geometry gathered from chapter content. Geometry is merged into position-only
 * buffers per collider and accelerated with three-mesh-bvh. Supports capsule resolution, rays and
 * sphere overlap tests.
 */
export class CollisionWorld {
  readonly colliders: Collider[] = [];
  private builder: THREE.BufferGeometry[] = [];
  private builderSurface: string | undefined;

  /** Queue a mesh (world transform applied) for the next static collider build. */
  addStaticMesh(mesh: THREE.Mesh | THREE.BufferGeometry, matrix?: THREE.Matrix4): void {
    let g: THREE.BufferGeometry;
    if ((mesh as THREE.Mesh).isMesh) {
      const m = mesh as THREE.Mesh;
      m.updateWorldMatrix(true, false);
      g = toPositionOnly(m.geometry);
      g.applyMatrix4(matrix ?? m.matrixWorld);
    } else {
      g = toPositionOnly(mesh as THREE.BufferGeometry);
      if (matrix) g.applyMatrix4(matrix);
    }
    this.builder.push(g);
  }

  /** Axis-aligned or oriented box collider queued as static geometry. */
  addStaticBox(center: THREE.Vector3, size: THREE.Vector3, rotationY = 0): void {
    const g = new THREE.BoxGeometry(size.x, size.y, size.z);
    const m = new THREE.Matrix4().makeRotationY(rotationY).setPosition(center);
    this.addStaticMesh(g, m);
    g.dispose();
  }

  /** Build all queued geometry into one static collider. */
  buildStatic(id = 'static', surface?: string): Collider | null {
    if (this.builder.length === 0) return null;
    // all parts must agree on indexing for the merge
    for (const g of this.builder) {
      if (!g.index) {
        const n = g.attributes.position.count;
        const idx = n > 65535 ? new Uint32Array(n) : new Uint16Array(n);
        for (let i = 0; i < n; i++) idx[i] = i;
        g.setIndex(new THREE.BufferAttribute(idx, 1));
      }
    }
    const merged = BufferGeometryUtils.mergeGeometries(this.builder, false);
    for (const g of this.builder) g.dispose();
    this.builder = [];
    if (!merged) return null;
    const c = this.createCollider(id, merged, true, surface ?? this.builderSurface);
    return c;
  }

  /** Create a dynamic collider from geometry in local space. */
  addDynamic(id: string, geometry: THREE.BufferGeometry, matrix: THREE.Matrix4, enabled = true): Collider {
    const c = this.createCollider(id, toPositionOnly(geometry), false);
    c.matrix.copy(matrix);
    c.inverse.copy(matrix).invert();
    c.enabled = enabled;
    return c;
  }

  setEnabled(id: string, enabled: boolean): void {
    for (const c of this.colliders) if (c.id === id) c.enabled = enabled;
  }

  remove(id: string): void {
    for (let i = this.colliders.length - 1; i >= 0; i--) {
      if (this.colliders[i].id === id) {
        this.colliders[i].geometry.dispose();
        this.colliders.splice(i, 1);
      }
    }
  }

  private createCollider(id: string, geometry: THREE.BufferGeometry, isStatic: boolean, surface?: string): Collider {
    const bvh = new MeshBVH(geometry, { targetLeafSize: 12 } as never);
    const c: Collider = { id, bvh, geometry, matrix: new THREE.Matrix4(), inverse: new THREE.Matrix4(), enabled: true, isStatic, surface };
    this.colliders.push(c);
    return c;
  }

  // ---------------------------------------------------------------- queries
  private _ray = new THREE.Ray();
  private _localRay = new THREE.Ray();
  private _hitPoint = new THREE.Vector3();
  private _n = new THREE.Vector3();

  raycast(origin: THREE.Vector3, dir: THREE.Vector3, far: number, out?: RayHit): RayHit | null {
    let best: RayHit | null = null;
    let bestDist = far;
    this._ray.set(origin, dir);
    for (const c of this.colliders) {
      if (!c.enabled) continue;
      let ray = this._ray;
      if (!c.isStatic) {
        ray = this._localRay.copy(this._ray).applyMatrix4(c.inverse);
      }
      const hit = c.bvh.raycastFirst(ray, THREE.DoubleSide);
      if (!hit) continue;
      this._hitPoint.copy(hit.point);
      if (!c.isStatic) this._hitPoint.applyMatrix4(c.matrix);
      const d = this._hitPoint.distanceTo(origin);
      if (d < bestDist) {
        bestDist = d;
        best = out ?? best ?? { point: new THREE.Vector3(), normal: new THREE.Vector3(), distance: 0, collider: c };
        best.point.copy(this._hitPoint);
        if (hit.face) {
          this._n.copy(hit.face.normal);
          if (!c.isStatic) this._n.transformDirection(c.matrix);
          if (this._n.dot(dir) > 0) this._n.negate();
          best.normal.copy(this._n);
        } else best.normal.set(0, 1, 0);
        best.distance = d;
        best.collider = c;
      }
    }
    return best;
  }

  /** Height of the first surface below `pos` within `maxDrop`, or null. */
  groundHeight(x: number, y: number, z: number, maxDrop = 50): number | null {
    _o.set(x, y, z);
    const hit = this.raycast(_o, _down, maxDrop, _sharedHit);
    return hit ? hit.point.y : null;
  }

  /**
   * Resolve a capsule (segment start = bottom sphere centre, end = top sphere centre) against all
   * colliders. Mutates the segment; returns the accumulated ground normal y (0 when not supported).
   */
  resolveCapsule(segment: THREE.Line3, radius: number, groundNormal: THREE.Vector3): boolean {
    let grounded = false;
    groundNormal.set(0, 0, 0);
    for (let iter = 0; iter < 3; iter++) {
      let pushed = false;
      for (const c of this.colliders) {
        if (!c.enabled) continue;
        _seg.copy(segment);
        if (!c.isStatic) {
          _seg.start.applyMatrix4(c.inverse);
          _seg.end.applyMatrix4(c.inverse);
        }
        _box.makeEmpty();
        _box.expandByPoint(_seg.start);
        _box.expandByPoint(_seg.end);
        _box.min.addScalar(-radius);
        _box.max.addScalar(radius);
        const before = _tmp.copy(_seg.start);
        c.bvh.shapecast({
          intersectsBounds: (box) => box.intersectsBox(_box),
          intersectsTriangle: (tri: ExtendedTriangle) => {
            const d = tri.closestPointToSegment(_seg, _triPoint, _capPoint);
            if (d < radius) {
              let depth = radius - d;
              _dir.subVectors(_capPoint, _triPoint);
              if (_dir.lengthSq() < 1e-10) tri.getNormal(_dir);
              else _dir.normalize();
              // Walkable floors are one-sided: a capsule that ended up beneath one (deep
              // penetration, teleport, tunnelling) is pushed back up through it, never down.
              tri.getNormal(_tn);
              if (_tn.y > 0.6 && _dir.dot(_tn) < 0) {
                _dir.copy(_tn);
                depth = radius + d;
              }
              _seg.start.addScaledVector(_dir, depth);
              _seg.end.addScaledVector(_dir, depth);
              // support comes from individual upward-facing contacts, not the net push
              if (_dir.y > 0.55) {
                _contactN.copy(_dir);
                if (!c.isStatic) _contactN.transformDirection(c.matrix);
                groundNormal.add(_contactN);
                grounded = true;
              }
            }
            return false;
          },
        });
        _delta.subVectors(_seg.start, before);
        if (_delta.lengthSq() > 1e-12) {
          pushed = true;
          if (!c.isStatic) _delta.transformDirection(c.matrix).multiplyScalar(_seg.start.distanceTo(before));
          segment.start.add(_delta);
          segment.end.add(_delta);
        }
      }
      if (!pushed) break;
    }
    if (grounded) groundNormal.normalize();
    return grounded;
  }

  /** True when the capsule overlaps any geometry (used for crouch → stand headroom checks). */
  capsuleOverlaps(segment: THREE.Line3, radius: number): boolean {
    for (const c of this.colliders) {
      if (!c.enabled) continue;
      _seg.copy(segment);
      if (!c.isStatic) {
        _seg.start.applyMatrix4(c.inverse);
        _seg.end.applyMatrix4(c.inverse);
      }
      _box.makeEmpty();
      _box.expandByPoint(_seg.start);
      _box.expandByPoint(_seg.end);
      _box.min.addScalar(-radius);
      _box.max.addScalar(radius);
      const hit = c.bvh.shapecast({
        intersectsBounds: (box) => box.intersectsBox(_box),
        intersectsTriangle: (tri: ExtendedTriangle) => tri.closestPointToSegment(_seg, _triPoint, _capPoint) < radius,
      });
      if (hit) return true;
    }
    return false;
  }

  /** Clear line of sight between two points. */
  lineOfSight(a: THREE.Vector3, b: THREE.Vector3): boolean {
    _dir.subVectors(b, a);
    const len = _dir.length();
    if (len < 1e-4) return true;
    _dir.multiplyScalar(1 / len);
    return this.raycast(a, _dir, len - 0.05, _sharedHit) === null;
  }

  get triangleCount(): number {
    let n = 0;
    for (const c of this.colliders) n += (c.geometry.index ? c.geometry.index.count : c.geometry.attributes.position.count) / 3;
    return n;
  }

  dispose(): void {
    for (const c of this.colliders) c.geometry.dispose();
    this.colliders.length = 0;
    for (const g of this.builder) g.dispose();
    this.builder = [];
  }
}

function toPositionOnly(src: THREE.BufferGeometry): THREE.BufferGeometry {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', src.attributes.position.clone());
  if (src.index) g.setIndex(src.index.clone());
  return g;
}

const _o = new THREE.Vector3();
const _down = new THREE.Vector3(0, -1, 0);
const _sharedHit: RayHit = { point: new THREE.Vector3(), normal: new THREE.Vector3(), distance: 0, collider: null as unknown as Collider };
const _seg = new THREE.Line3();
const _box = new THREE.Box3();
const _triPoint = new THREE.Vector3();
const _capPoint = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _delta = new THREE.Vector3();
const _tmp = new THREE.Vector3();
const _tn = new THREE.Vector3();
const _contactN = new THREE.Vector3();
