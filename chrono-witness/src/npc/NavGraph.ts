import * as THREE from 'three';

export interface NavNode {
  id: number;
  pos: THREE.Vector3;
  links: number[];
  /** Optional tag (e.g. 'dugout', 'firestep') for scripting. */
  tag?: string;
  blocked?: boolean;
}

/**
 * Waypoint navigation graph. Chapters author it (or derive it from their level layout, e.g.
 * trench centrelines); NPCs path with A* and follow the polyline with corner smoothing.
 */
export class NavGraph {
  readonly nodes: NavNode[] = [];

  add(pos: THREE.Vector3, tag?: string): number {
    const id = this.nodes.length;
    this.nodes.push({ id, pos: pos.clone(), links: [], tag });
    return id;
  }

  link(a: number, b: number): void {
    if (a === b) return;
    if (!this.nodes[a].links.includes(b)) this.nodes[a].links.push(b);
    if (!this.nodes[b].links.includes(a)) this.nodes[b].links.push(a);
  }

  /** Add a polyline of nodes, linked in sequence; returns their ids. */
  addPath(points: THREE.Vector3[], tag?: string): number[] {
    const ids = points.map((p) => this.add(p, tag));
    for (let i = 1; i < ids.length; i++) this.link(ids[i - 1], ids[i]);
    return ids;
  }

  nearest(p: THREE.Vector3, maxDist = Infinity, ignoreBlocked = true): number {
    let best = -1;
    let bd = maxDist * maxDist;
    for (const n of this.nodes) {
      if (ignoreBlocked && n.blocked) continue;
      const d = n.pos.distanceToSquared(p);
      if (d < bd) {
        bd = d;
        best = n.id;
      }
    }
    return best;
  }

  /** Mark nodes within a radius as blocked (e.g. a collapsed trench section). */
  blockRadius(center: THREE.Vector3, radius: number, blocked = true): void {
    for (const n of this.nodes) if (n.pos.distanceTo(center) < radius) n.blocked = blocked;
  }

  findPath(from: THREE.Vector3, to: THREE.Vector3): THREE.Vector3[] | null {
    const s = this.nearest(from);
    const g = this.nearest(to);
    if (s < 0 || g < 0) return null;
    const open = new Set<number>([s]);
    const came = new Map<number, number>();
    const gScore = new Map<number, number>([[s, 0]]);
    const fScore = new Map<number, number>([[s, this.nodes[s].pos.distanceTo(this.nodes[g].pos)]]);
    while (open.size) {
      let cur = -1;
      let bf = Infinity;
      for (const n of open) {
        const f = fScore.get(n) ?? Infinity;
        if (f < bf) {
          bf = f;
          cur = n;
        }
      }
      if (cur === g) {
        const path: THREE.Vector3[] = [this.nodes[g].pos.clone()];
        let c = g;
        while (came.has(c)) {
          c = came.get(c)!;
          path.unshift(this.nodes[c].pos.clone());
        }
        path.push(to.clone());
        return path;
      }
      open.delete(cur);
      for (const nb of this.nodes[cur].links) {
        if (this.nodes[nb].blocked) continue;
        const t = (gScore.get(cur) ?? Infinity) + this.nodes[cur].pos.distanceTo(this.nodes[nb].pos);
        if (t < (gScore.get(nb) ?? Infinity)) {
          came.set(nb, cur);
          gScore.set(nb, t);
          fScore.set(nb, t + this.nodes[nb].pos.distanceTo(this.nodes[g].pos));
          open.add(nb);
        }
      }
    }
    return null;
  }
}
