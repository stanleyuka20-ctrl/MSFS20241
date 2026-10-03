import * as THREE from 'three';
import { GeoBatch, canvasTexture } from '../common/geo';

/**
 * Period props built procedurally (lathe/box/tube primitives with PBR materials). Each factory
 * returns a fresh Object3D sharing materials from `PropMaterials`.
 */
export interface PropMaterials {
  crate: THREE.Material;
  beam: THREE.Material;
  planks: THREE.Material;
  steel: THREE.Material;
  canvas: THREE.Material;
  sandbag: THREE.Material;
  helmetPaint: THREE.MeshStandardMaterial;
  leather: THREE.MeshStandardMaterial;
  stoneware: THREE.MeshStandardMaterial;
  stonewareDark: THREE.MeshStandardMaterial;
  tin: THREE.MeshStandardMaterial;
  blanket: THREE.MeshStandardMaterial;
  paper: THREE.MeshStandardMaterial;
  glass: THREE.MeshStandardMaterial;
  flame: THREE.MeshStandardMaterial;
  coals: THREE.MeshStandardMaterial;
  wool: THREE.MeshStandardMaterial;
  whiteCloth: THREE.MeshStandardMaterial;
}

export function makePropMaterials(base: { crate: THREE.Material; beam: THREE.Material; planks: THREE.Material; steel: THREE.Material; canvas: THREE.Material; sandbag: THREE.Material }): PropMaterials {
  return {
    ...base,
    helmetPaint: new THREE.MeshStandardMaterial({ name: 'helmet-paint', color: 0x4d4a33, roughness: 0.62, metalness: 0.35 }),
    leather: new THREE.MeshStandardMaterial({ name: 'leather', color: 0x4b3222, roughness: 0.62, metalness: 0 }),
    stoneware: new THREE.MeshStandardMaterial({ name: 'stoneware', color: 0xc9b99a, roughness: 0.35, metalness: 0 }),
    stonewareDark: new THREE.MeshStandardMaterial({ name: 'stoneware-dark', color: 0x5a3a22, roughness: 0.3, metalness: 0 }),
    tin: new THREE.MeshStandardMaterial({ name: 'tin', color: 0x8a8577, roughness: 0.45, metalness: 0.8 }),
    blanket: new THREE.MeshStandardMaterial({ name: 'blanket', color: 0x4f4537, roughness: 0.95, metalness: 0, side: THREE.DoubleSide }),
    paper: new THREE.MeshStandardMaterial({ name: 'paper', color: 0xd8cfb6, roughness: 0.85 }),
    glass: new THREE.MeshStandardMaterial({ name: 'lamp-glass', color: 0xfff1d6, roughness: 0.1, metalness: 0, transparent: true, opacity: 0.35, emissive: 0xffb45c, emissiveIntensity: 0.6 }),
    flame: new THREE.MeshStandardMaterial({ name: 'flame', color: 0x000000, emissive: 0xffa040, emissiveIntensity: 6 }),
    coals: new THREE.MeshStandardMaterial({ name: 'coals', color: 0x1a0d08, emissive: 0xff5a1e, emissiveIntensity: 1.6, roughness: 0.9 }),
    wool: new THREE.MeshStandardMaterial({ name: 'wool-blanket', color: 0x5b5244, roughness: 1, side: THREE.DoubleSide }),
    whiteCloth: new THREE.MeshStandardMaterial({ name: 'white-cloth', color: 0xd9d6cc, roughness: 0.95 }),
  };
}

function boxT(w: number, h: number, d: number, tile = 1): THREE.BoxGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.attributes.uv as THREE.BufferAttribute;
  const n = g.attributes.normal as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) {
    const ax = Math.abs(n.getX(i));
    const ay = Math.abs(n.getY(i));
    const sx = ax > 0.5 ? d : w;
    const sy = ay > 0.5 ? d : h;
    uv.setXY(i, (uv.getX(i) * sx) / tile, (uv.getY(i) * sy) / tile);
  }
  return g;
}

function mesh(g: THREE.BufferGeometry, m: THREE.Material, cast = true): THREE.Mesh {
  const x = new THREE.Mesh(g, m);
  x.castShadow = cast;
  x.receiveShadow = true;
  return x;
}

export function crate(M: PropMaterials, w = 0.62, h = 0.36, d = 0.42): THREE.Group {
  const g = new THREE.Group();
  g.add(mesh(boxT(w, h, d), M.crate));
  // battens on the ends
  const b = new GeoBatch();
  for (const sx of [-1, 1]) b.add(boxT(0.025, h + 0.01, d + 0.02), new THREE.Matrix4().makeTranslation((sx * (w - 0.04)) / 2, 0, 0));
  g.add(mesh(b.build(), M.beam));
  return g;
}

/** SRD stoneware rum jar: cream body, brown shoulders. */
export function rumJar(M: PropMaterials, tracker: { track: <T extends { dispose(): void }>(x: T) => T }): THREE.Group {
  const pts: THREE.Vector2[] = [];
  const prof = [[0, 0], [0.09, 0], [0.105, 0.02], [0.112, 0.12], [0.11, 0.2], [0.095, 0.26], [0.06, 0.3], [0.03, 0.31], [0.028, 0.35], [0.034, 0.36], [0, 0.36]];
  for (const [r, y] of prof) pts.push(new THREE.Vector2(r, y));
  const lower = new THREE.LatheGeometry(pts.slice(0, 5), 20);
  const upper = new THREE.LatheGeometry(pts.slice(4), 20);
  const g = new THREE.Group();
  const label = tracker.track(
    canvasTexture(256, 128, (c) => {
      c.fillStyle = '#c9b99a';
      c.fillRect(0, 0, 256, 128);
      c.fillStyle = '#3a2c20';
      c.font = 'bold 60px Georgia, serif';
      c.textAlign = 'center';
      c.fillText('S.R.D.', 128, 84);
    }),
  );
  const body = new THREE.MeshStandardMaterial({ map: label, roughness: 0.35 });
  g.add(mesh(lower, body), mesh(upper, M.stonewareDark));
  return g;
}

/** Brodie Mk I steel helmet: shallow bowl with wide flat brim. */
export function brodieHelmet(M: PropMaterials): THREE.Mesh {
  const pts: THREE.Vector2[] = [];
  const prof = [[0, 0.115], [0.04, 0.113], [0.08, 0.103], [0.11, 0.085], [0.13, 0.062], [0.14, 0.04], [0.145, 0.025], [0.15, 0.02], [0.175, 0.012], [0.19, 0.006], [0.192, 0.0], [0.188, -0.004], [0.17, 0.004], [0.148, 0.012], [0.14, 0.03], [0.128, 0.058], [0.105, 0.08], [0.075, 0.097], [0.035, 0.106], [0, 0.108]];
  for (const [r, y] of prof) pts.push(new THREE.Vector2(r, y));
  const g = new THREE.LatheGeometry(pts, 36);
  g.scale(1, 1, 0.88); // slightly oval
  g.computeVertexNormals();
  return mesh(g, M.helmetPaint);
}

export function fieldTelephone(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const caseM = mesh(boxT(0.26, 0.16, 0.12), M.leather);
  caseM.position.y = 0.08;
  const lid = mesh(boxT(0.26, 0.012, 0.12), M.leather);
  lid.position.set(0, 0.17, -0.07);
  lid.rotation.x = -1.2;
  const hand = mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.2, 10), M.stonewareDark);
  hand.rotation.z = Math.PI / 2;
  hand.position.set(0.02, 0.175, 0.01);
  const ear = mesh(new THREE.CylinderGeometry(0.025, 0.02, 0.04, 12), M.stonewareDark);
  ear.position.set(-0.09, 0.175, 0.01);
  g.add(caseM, lid, hand, ear);
  return g;
}

export function boxPeriscope(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const body = mesh(boxT(0.11, 0.95, 0.09), M.crate);
  body.position.y = 0.475;
  const mirrorTop = mesh(new THREE.PlaneGeometry(0.08, 0.07), M.glass);
  mirrorTop.position.set(0, 0.9, -0.046);
  mirrorTop.rotation.y = Math.PI;
  const mirrorBot = mesh(new THREE.PlaneGeometry(0.08, 0.07), M.glass);
  mirrorBot.position.set(0, 0.1, 0.046);
  g.add(body, mirrorTop, mirrorBot);
  return g;
}

export function stretcher(M: PropMaterials, withCanvas = true): THREE.Group {
  const g = new THREE.Group();
  const b = new GeoBatch();
  for (const x of [-0.27, 0.27]) {
    const pole = new THREE.CylinderGeometry(0.02, 0.02, 2.3, 8);
    pole.rotateX(Math.PI / 2);
    b.add(pole, new THREE.Matrix4().makeTranslation(x, 0.14, 0));
  }
  for (const z of [-0.75, 0.75]) {
    const stirrup = new THREE.TorusGeometry(0.07, 0.012, 6, 12, Math.PI);
    stirrup.rotateY(Math.PI / 2);
    b.add(stirrup, new THREE.Matrix4().makeTranslation(-0.27, 0.07, z));
    const stirrup2 = stirrup.clone();
    b.add(stirrup2, new THREE.Matrix4().makeTranslation(0.27, 0.07, z));
    const spreader = new THREE.CylinderGeometry(0.01, 0.01, 0.54, 6);
    spreader.rotateZ(Math.PI / 2);
    b.add(spreader, new THREE.Matrix4().makeTranslation(0, 0.12, z));
  }
  g.add(mesh(b.build(), M.beam));
  if (withCanvas) {
    const bed = new THREE.PlaneGeometry(0.54, 1.82, 4, 8);
    const p = bed.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < p.count; i++) p.setZ(i, -Math.cos((p.getX(i) / 0.27) * Math.PI * 0.5) * 0.03);
    bed.rotateX(-Math.PI / 2);
    bed.translate(0, 0.15, 0);
    bed.computeVertexNormals();
    const cm = mesh(bed, M.canvas);
    (cm.material as THREE.Material).side = THREE.DoubleSide;
    g.add(cm);
  }
  return g;
}

export function lantern(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const base = mesh(new THREE.CylinderGeometry(0.06, 0.065, 0.06, 14), M.tin);
  base.position.y = 0.03;
  const glass = mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.12, 14, 1, true), M.glass, false);
  glass.position.y = 0.12;
  const top = mesh(new THREE.ConeGeometry(0.06, 0.06, 14), M.tin);
  top.position.y = 0.21;
  const flame = mesh(new THREE.SphereGeometry(0.012, 8, 6), M.flame, false);
  flame.scale.y = 2;
  flame.position.y = 0.11;
  const handle = mesh(new THREE.TorusGeometry(0.05, 0.004, 4, 16, Math.PI), M.tin);
  handle.position.y = 0.24;
  g.add(base, glass, top, flame, handle);
  return g;
}

export function candle(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const c = mesh(new THREE.CylinderGeometry(0.012, 0.013, 0.09, 10), M.whiteCloth);
  c.position.y = 0.045;
  const f = mesh(new THREE.SphereGeometry(0.006, 6, 6), M.flame, false);
  f.scale.y = 2.4;
  f.position.y = 0.105;
  const tin = mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.012, 14), M.tin);
  g.add(tin, c, f);
  return g;
}

export function brazier(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const b = new GeoBatch();
  // perforated bucket approximated by vertical straps and rings
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    b.add(new THREE.BoxGeometry(0.03, 0.34, 0.008), new THREE.Matrix4().makeRotationY(-a).setPosition(Math.cos(a) * 0.17, 0.42, Math.sin(a) * 0.17));
  }
  for (const y of [0.27, 0.58]) {
    const r = new THREE.TorusGeometry(0.17, 0.01, 4, 24);
    r.rotateX(Math.PI / 2);
    b.add(r, new THREE.Matrix4().makeTranslation(0, y, 0));
  }
  for (let i = 0; i < 3; i++) {
    const a = (i / 3) * Math.PI * 2;
    const leg = new THREE.CylinderGeometry(0.01, 0.01, 0.3, 5);
    b.add(leg, new THREE.Matrix4().makeRotationZ(0.2).premultiply(new THREE.Matrix4().makeRotationY(a)).setPosition(Math.cos(a) * 0.15, 0.13, Math.sin(a) * 0.15));
  }
  g.add(mesh(b.build(), M.steel));
  const coals = mesh(new THREE.CylinderGeometry(0.16, 0.14, 0.18, 16), M.coals, false);
  coals.position.y = 0.45;
  g.add(coals);
  return g;
}

export function tins(M: PropMaterials, n = 4): THREE.Group {
  const g = new THREE.Group();
  for (let i = 0; i < n; i++) {
    const t = mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.11, 14), M.tin);
    t.position.set((i % 2) * 0.1 - 0.05, 0.055 + Math.floor(i / 2) * 0.112, (i % 3) * 0.02);
    g.add(t);
  }
  return g;
}

/** Haversack-style bag for the PH gas helmet. */
export function gasBag(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const bag = mesh(boxT(0.24, 0.2, 0.08), M.canvas);
  bag.position.y = 0.1;
  const flap = mesh(boxT(0.245, 0.09, 0.082), M.canvas);
  flap.position.set(0, 0.165, 0.002);
  const strap = mesh(new THREE.TorusGeometry(0.2, 0.012, 4, 20, Math.PI), M.canvas);
  strap.position.y = 0.2;
  g.add(bag, flap, strap);
  return g;
}

export function veryPistol(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const barrel = mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.2, 12), M.steel);
  barrel.rotation.z = Math.PI / 2;
  barrel.position.set(0.04, 0.04, 0);
  const grip = mesh(boxT(0.035, 0.11, 0.03), M.beam);
  grip.position.set(-0.07, 0.0, 0);
  grip.rotation.z = 0.35;
  g.add(barrel, grip);
  return g;
}

/** Steel corkscrew picket: a twisted rod with loops. */
export function screwPicket(M: PropMaterials, height = 1.4): THREE.Mesh {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= 30; i++) {
    const t = i / 30;
    const y = -0.35 + t * (height + 0.35);
    const r = y < 0 ? 0.035 * (1 - t * 2) : 0.012;
    const a = t * Math.PI * (y < 0 ? 14 : 2);
    pts.push(new THREE.Vector3(Math.cos(a) * r, y, Math.sin(a) * r));
  }
  const g = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, 0.011, 5, false);
  return mesh(g, M.steel);
}

/** Wire-netting bunk on a timber frame. */
export function bunk(M: PropMaterials, tracker: { track: <T extends { dispose(): void }>(x: T) => T }): THREE.Group {
  const g = new THREE.Group();
  const b = new GeoBatch();
  for (const [x, z] of [[-0.35, -0.95], [0.35, -0.95], [-0.35, 0.95], [0.35, 0.95]]) b.add(boxT(0.08, 0.5, 0.08), new THREE.Matrix4().makeTranslation(x, 0.25, z));
  for (const x of [-0.35, 0.35]) b.add(boxT(0.07, 0.07, 2.0), new THREE.Matrix4().makeTranslation(x, 0.45, 0));
  g.add(mesh(b.build(), M.beam));
  const net = tracker.track(
    canvasTexture(128, 128, (c) => {
      c.clearRect(0, 0, 128, 128);
      c.strokeStyle = 'rgba(120,110,95,1)';
      c.lineWidth = 3;
      for (let i = -128; i < 256; i += 16) {
        c.beginPath();
        c.moveTo(i, 0);
        c.lineTo(i + 128, 128);
        c.stroke();
        c.beginPath();
        c.moveTo(i + 128, 0);
        c.lineTo(i, 128);
        c.stroke();
      }
    }),
  );
  net.wrapS = net.wrapT = THREE.RepeatWrapping;
  net.repeat.set(3, 8);
  const mNet = new THREE.MeshStandardMaterial({ map: net, alphaTest: 0.5, transparent: false, metalness: 0.6, roughness: 0.6, side: THREE.DoubleSide });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 1.9), mNet);
  plane.rotation.x = -Math.PI / 2;
  plane.position.y = 0.44;
  g.add(plane);
  const blanket = mesh(new THREE.BoxGeometry(0.6, 0.04, 0.9), M.wool);
  blanket.position.set(0, 0.47, 0.4);
  blanket.rotation.y = 0.08;
  g.add(blanket);
  return g;
}

/** Hanging blanket (gas curtain) with gentle cloth folds. */
export function gasCurtain(M: PropMaterials, w = 1.0, h = 1.8): THREE.Mesh {
  const g = new THREE.PlaneGeometry(w, h, 10, 8);
  const p = g.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i);
    const y = p.getY(i);
    const t = (h / 2 - y) / h;
    p.setZ(i, Math.sin(x * 12) * 0.03 * (0.4 + t) + t * t * 0.05);
  }
  g.computeVertexNormals();
  return mesh(g, M.blanket);
}

export function table(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const top = mesh(boxT(1.1, 0.04, 0.6), M.planks);
  top.position.y = 0.74;
  g.add(top);
  const b = new GeoBatch();
  for (const [x, z] of [[-0.5, -0.25], [0.5, -0.25], [-0.5, 0.25], [0.5, 0.25]]) b.add(boxT(0.05, 0.72, 0.05), new THREE.Matrix4().makeTranslation(x, 0.36, z));
  g.add(mesh(b.build(), M.beam));
  return g;
}

export function mapSheet(M: PropMaterials, tracker: { track: <T extends { dispose(): void }>(x: T) => T }): THREE.Mesh {
  const tex = tracker.track(
    canvasTexture(256, 192, (c) => {
      c.fillStyle = '#d8cfb6';
      c.fillRect(0, 0, 256, 192);
      c.strokeStyle = '#6d5a3c';
      c.lineWidth = 1;
      for (let i = 0; i < 12; i++) {
        c.beginPath();
        c.moveTo(0, i * 16);
        c.bezierCurveTo(80, i * 16 + 8, 160, i * 16 - 8, 256, i * 16 + 4);
        c.stroke();
      }
      c.strokeStyle = '#9c2a1e';
      c.lineWidth = 3;
      c.beginPath();
      c.moveTo(10, 60);
      for (let x = 10; x < 250; x += 20) c.lineTo(x + 10, 60 + ((x / 20) % 2 ? 6 : 0));
      c.stroke();
      c.strokeStyle = '#2a3e7a';
      c.beginPath();
      c.moveTo(10, 140);
      for (let x = 10; x < 250; x += 20) c.lineTo(x + 10, 140 + ((x / 20) % 2 ? 5 : 0));
      c.stroke();
    }),
  );
  const m = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.38), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.9 }));
  m.rotation.x = -Math.PI / 2;
  void M;
  return m;
}

export function messagePad(M: PropMaterials): THREE.Group {
  const g = new THREE.Group();
  const pad = mesh(boxT(0.12, 0.012, 0.18), M.paper);
  pad.position.y = 0.006;
  const cover = mesh(boxT(0.125, 0.004, 0.185), M.leather);
  cover.position.set(0.13, 0.002, 0);
  const pencil = mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.15, 6), M.crate);
  pencil.rotation.z = Math.PI / 2;
  pencil.position.set(0, 0.016, 0.05);
  g.add(pad, cover, pencil);
  return g;
}

/** Corrugated-iron sheet section (scannable revetment example). */
export function shellCase(M: PropMaterials): THREE.Mesh {
  const g = new THREE.LatheGeometry([new THREE.Vector2(0, 0), new THREE.Vector2(0.055, 0), new THREE.Vector2(0.055, 0.02), new THREE.Vector2(0.05, 0.03), new THREE.Vector2(0.05, 0.38), new THREE.Vector2(0.046, 0.38)], 16);
  return mesh(g, new THREE.MeshStandardMaterial({ color: 0x8c6a3c, metalness: 0.9, roughness: 0.4 }));
  void M;
}

export function fallenBeam(M: PropMaterials, len = 3.2): THREE.Mesh {
  const g = boxT(0.24, 0.26, len);
  const p = g.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < p.count; i++) if (p.getZ(i) > len / 2 - 0.01) p.setY(i, p.getY(i) + (Math.random() - 0.5) * 0.08); // splintered end
  g.computeVertexNormals();
  return mesh(g, M.beam);
}
