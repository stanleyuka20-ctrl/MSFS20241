import * as THREE from 'three';
import type { Assets, PBRSet } from './Assets';

/** Uniforms shared by all weather-aware materials (one object, updated once per frame). */
export const WeatherUniforms = {
  uTime: { value: 0 },
  uWetness: { value: 0 },
  uRain: { value: 0 },
  uRipples: { value: null as THREE.Texture | null },
};

export interface StandardOpts {
  color?: THREE.ColorRepresentation;
  roughnessScale?: number;
  metalness?: number;
  normalScale?: number;
  envIntensity?: number;
  /** Rain makes upward-facing surfaces darker and glossier. 0 = never wet (interiors). */
  porosity?: number;
  side?: THREE.Side;
  aoIntensity?: number;
  vertexColors?: boolean;
  name?: string;
}

/** Build a MeshStandardMaterial from a PBR set. Geometry UVs are expected in "tiles" (metres / tileMetres). */
export function standardFromSet(set: PBRSet, o: StandardOpts = {}): THREE.MeshStandardMaterial {
  const m = new THREE.MeshStandardMaterial({
    name: o.name ?? 'pbr',
    map: set.map,
    normalMap: set.normalMap,
    roughnessMap: set.orm,
    metalnessMap: set.orm,
    aoMap: set.orm,
    aoMapIntensity: o.aoIntensity ?? 1,
    color: o.color ?? 0xffffff,
    roughness: o.roughnessScale ?? 1,
    metalness: o.metalness ?? 1,
    envMapIntensity: o.envIntensity ?? 1,
    side: o.side ?? THREE.FrontSide,
    vertexColors: o.vertexColors ?? false,
  });
  m.normalScale.setScalar(o.normalScale ?? 1);
  if ((o.porosity ?? 0) > 0) applyWetness(m, o.porosity!);
  return m;
}

/**
 * Wetness patch: surfaces facing the sky darken (porous) and lose roughness while it rains.
 * Implemented with onBeforeCompile so lighting, shadows and fog remain the stock PBR path.
 */
export function applyWetness(m: THREE.MeshStandardMaterial, porosity: number): void {
  const prev = m.onBeforeCompile;
  m.onBeforeCompile = (shader, renderer) => {
    prev?.call(m, shader, renderer);
    shader.uniforms.uWetness = WeatherUniforms.uWetness;
    shader.uniforms.uPorosity = { value: porosity };
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uWetness;\nuniform float uPorosity;')
      .replace(
        '#include <normal_fragment_maps>',
        `#include <normal_fragment_maps>
        {
          vec3 nW = inverseTransformDirection( normal, viewMatrix );
          float wet = uWetness * smoothstep( 0.15, 0.85, nW.y * 0.5 + 0.5 ) ;
          diffuseColor.rgb *= mix( 1.0, 0.62, wet * uPorosity );
          roughnessFactor = mix( roughnessFactor, roughnessFactor * 0.42, wet );
        }`,
      );
  };
  m.customProgramCacheKey = () => `wet-${porosity.toFixed(2)}`;
}

export interface TerrainSets {
  mud: PBRSet;
  earth: PBRSet;
  grass: PBRSet;
  chalk: PBRSet;
}

/**
 * Terrain shader: blends four PBR sets with per-vertex weights (attribute `blend`: x = mud,
 * y = grass, z = chalk, w = puddle-ability; earth is the remainder) using height-aware transitions.
 * Top-down projection for all sets, biplanar side projection for earth on steep trench walls,
 * macro-variation to break tiling, and puddles with animated rain-ripple normals.
 */
export function terrainMaterial(sets: TerrainSets, macro: THREE.Texture): THREE.MeshStandardMaterial {
  const m = new THREE.MeshStandardMaterial({ name: 'terrain', roughness: 1, metalness: 0, color: 0xffffff });
  // dummy maps so the right defines/varyings exist (USE_MAP etc. not needed; we sample ourselves)
  m.onBeforeCompile = (shader) => {
    const U = shader.uniforms;
    U.tMudA = { value: sets.mud.map };
    U.tMudN = { value: sets.mud.normalMap };
    U.tMudR = { value: sets.mud.orm };
    U.tEarthA = { value: sets.earth.map };
    U.tEarthN = { value: sets.earth.normalMap };
    U.tEarthR = { value: sets.earth.orm };
    U.tGrassA = { value: sets.grass.map };
    U.tGrassN = { value: sets.grass.normalMap };
    U.tGrassR = { value: sets.grass.orm };
    U.tChalkA = { value: sets.chalk.map };
    U.tChalkR = { value: sets.chalk.orm };
    U.tMacro = { value: macro };
    U.uTiles = { value: new THREE.Vector4(1 / sets.mud.tileMetres, 1 / sets.earth.tileMetres, 1 / sets.grass.tileMetres, 1 / sets.chalk.tileMetres) };
    U.uTime = WeatherUniforms.uTime;
    U.uWetness = WeatherUniforms.uWetness;
    U.uRain = WeatherUniforms.uRain;
    U.tRipples = WeatherUniforms.uRipples.value ? WeatherUniforms.uRipples : { value: sets.mud.normalMap };

    shader.vertexShader = shader.vertexShader
      .replace(
        '#include <common>',
        `#include <common>
        attribute vec4 blend;
        attribute float ao;
        varying float vAO;
        varying vec4 vBlend;
        varying vec3 vWPos;
        varying vec3 vWNormal;`,
      )
      .replace(
        '#include <worldpos_vertex>',
        `#include <worldpos_vertex>
        vBlend = blend;
        vAO = ao;
        vWPos = (modelMatrix * vec4(transformed, 1.0)).xyz;
        vWNormal = normalize(mat3(modelMatrix) * objectNormal);`,
      );

    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
        uniform sampler2D tMudA, tMudN, tMudR, tEarthA, tEarthN, tEarthR, tGrassA, tGrassN, tGrassR, tChalkA, tChalkR, tMacro, tRipples;
        uniform vec4 uTiles;
        uniform float uTime, uWetness, uRain;
        varying vec4 vBlend;
        varying float vAO;
        varying vec3 vWPos;
        varying vec3 vWNormal;
        vec3 tW_albedo; vec3 tW_orm; vec3 tW_normal;
        vec3 udn(vec3 n, vec2 d, vec3 t, vec3 b, float s) { return normalize(n + (t * d.x + b * d.y) * s); }
        vec2 nrm2(sampler2D tex, vec2 uv) { return texture2D(tex, uv).xy * 2.0 - 1.0; }
        vec2 rippleNormal(vec2 p) {
          float frame = floor(mod(uTime * 18.0, 16.0));
          vec2 cell = vec2(mod(frame, 4.0), floor(frame / 4.0));
          vec2 uv = (fract(p) + cell) / 4.0;
          return texture2D(tRipples, uv).xy * 2.0 - 1.0;
        }`,
      )
      .replace(
        '#include <map_fragment>',
        `
        {
          vec3 N = normalize(vWNormal);
          vec2 pXZ = vWPos.xz;
          float macroA = texture2D(tMacro, pXZ * 0.021).r;
          float macroB = texture2D(tMacro, pXZ * 0.0047 + 0.37).g;
          // offset/rotate second-scale sampling to hide repetition
          vec2 uvMud = pXZ * uTiles.x;
          vec2 uvGr = pXZ * uTiles.z;
          vec2 uvCh = pXZ * uTiles.w;
          vec2 uvEt = pXZ * uTiles.y;
          vec4 mudA = texture2D(tMudA, uvMud);
          vec3 mudR = texture2D(tMudR, uvMud).rgb;
          vec4 grA = texture2D(tGrassA, uvGr);
          vec3 grR = texture2D(tGrassR, uvGr).rgb;
          vec4 chA = texture2D(tChalkA, uvCh);
          vec3 chR = texture2D(tChalkR, uvCh).rgb;
          // earth: biplanar (top + dominant side axis)
          vec3 an = abs(N);
          float side = smoothstep(0.45, 0.85, 1.0 - an.y);
          vec2 uvSide = an.x > an.z ? vWPos.zy : vWPos.xy;
          uvSide *= uTiles.y;
          vec4 etTop = texture2D(tEarthA, uvEt);
          vec4 etSide = texture2D(tEarthA, uvSide);
          vec3 etRt = texture2D(tEarthR, uvEt).rgb;
          vec3 etRs = texture2D(tEarthR, uvSide).rgb;
          vec4 etA = mix(etTop, etSide, side);
          vec3 etR = mix(etRt, etRs, side);

          // height-aware weights (AO channel as height proxy)
          float wMud = vBlend.x * (1.0 - side * 0.8);
          float wGr = vBlend.y * (1.0 - side);
          float wCh = vBlend.z * (1.0 - side * 0.9);
          float wEt = max(0.0, 1.0 - wMud - wGr - wCh) + side * 0.6;
          float hM = mudR.r + wMud * 1.5, hG = grR.r + wGr * 1.5, hC = chR.r + wCh * 1.5, hE = etR.r + wEt * 1.5;
          float hmax = max(max(hM, hG), max(hC, hE)) - 0.35;
          vec4 w = max(vec4(hM, hG, hC, hE) - hmax, 0.0) * vec4(step(0.001, wMud), step(0.001, wGr), step(0.001, wCh), step(0.001, wEt));
          w /= max(1e-4, w.x + w.y + w.z + w.w);

          tW_albedo = mudA.rgb * w.x + grA.rgb * w.y + chA.rgb * w.z + etA.rgb * w.w;
          tW_orm = mudR * w.x + grR * w.y + chR * w.z + etR * w.w;
          tW_albedo *= mix(0.82, 1.12, macroA) * mix(0.9, 1.06, macroB);

          // normals (world space, UDN blend)
          vec3 T = vec3(1.0, 0.0, 0.0), B = vec3(0.0, 0.0, 1.0);
          vec2 dN = nrm2(tMudN, uvMud) * w.x + nrm2(tGrassN, uvGr) * w.y + nrm2(tEarthN, uvEt) * w.w * (1.0 - side);
          vec3 nTop = udn(N, dN, T, -B, 0.9);
          vec3 Ts = an.x > an.z ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0);
          vec3 nSide = udn(nTop, nrm2(tEarthN, uvSide) * w.w * side, Ts, vec3(0.0, 1.0, 0.0), 1.0);
          tW_normal = nSide;

          // puddles: flat, low areas flagged by vBlend.w
          float pud = smoothstep(0.52, 0.6, macroA * 0.7 + (1.0 - tW_orm.r) * 0.45) * vBlend.w * smoothstep(0.93, 0.99, N.y);
          pud *= smoothstep(0.1, 0.5, uWetness);
          vec3 water = mix(tW_albedo * 0.45, vec3(0.08, 0.075, 0.07), 0.55);
          tW_albedo = mix(tW_albedo, water, pud);
          // general wetness
          float wetGen = uWetness * (0.35 + 0.65 * N.y);
          tW_albedo *= mix(1.0, 0.7, wetGen * 0.6);
          tW_orm.g = mix(tW_orm.g, max(0.32, tW_orm.g * 0.72), wetGen);
          tW_orm.g = mix(tW_orm.g, 0.04, pud);
          vec2 rip = rippleNormal(pXZ * 0.9) * uRain;
          tW_normal = normalize(mix(tW_normal, normalize(N + vec3(rip.x, 0.0, rip.y) * 0.35), pud));
          diffuseColor.rgb *= tW_albedo;
        }
        `,
      )
      .replace('#include <roughnessmap_fragment>', 'float roughnessFactor = roughness * tW_orm.g;')
      .replace('#include <metalnessmap_fragment>', 'float metalnessFactor = 0.0;')
      .replace('#include <normal_fragment_maps>', 'normal = normalize((viewMatrix * vec4(tW_normal, 0.0)).xyz);')
      .replace(
        '#include <aomap_fragment>',
        `{
          float ao = mix(1.0, tW_orm.r, 0.9) * vAO;
          reflectedLight.indirectDiffuse *= ao;
          reflectedLight.indirectSpecular *= ao;
        }`,
      );
  };
  m.customProgramCacheKey = () => 'terrain-v4';
  return m;
}

/** Helper to load and cache standard materials by set name for a chapter. */
export class MaterialLibrary {
  private cache = new Map<string, Promise<THREE.MeshStandardMaterial>>();
  constructor(private readonly assets: Assets) {}

  get(key: string, set: string, opts: StandardOpts = {}): Promise<THREE.MeshStandardMaterial> {
    let p = this.cache.get(key);
    if (!p) {
      p = this.assets.pbr(set).then((s) => standardFromSet(s, { name: key, ...opts }));
      this.cache.set(key, p);
    }
    return p;
  }

  async all(): Promise<THREE.MeshStandardMaterial[]> {
    return Promise.all(this.cache.values());
  }

  dispose(): void {
    for (const p of this.cache.values()) p.then((m) => m.dispose());
    this.cache.clear();
  }
}
