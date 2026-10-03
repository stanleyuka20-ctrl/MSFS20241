import * as THREE from 'three';

/**
 * Linear-HDR grading pass applied before tone mapping: per-chapter colour balance, temporal
 * observation look, transition distortion, screen fades and (clamped) flash exposure. Kept in one
 * pass so the cost is a single full-screen fetch.
 */
export const GradeShader = {
  name: 'GradeShader',
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    uTime: { value: 0 },
    uSaturation: { value: 1 },
    uContrast: { value: 1 },
    uTint: { value: new THREE.Color(1, 1, 1) },
    uShadowTint: { value: new THREE.Color(1, 1, 1) },
    uObserve: { value: 0 },
    uTransition: { value: 0 },
    uFade: { value: 0 },
    uFadeColor: { value: new THREE.Color(0, 0, 0) },
    uFlash: { value: 0 },
    uVignette: { value: 0.22 },
    uGrain: { value: 0.025 },
    uAspect: { value: 1.7778 },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
  `,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uTime, uSaturation, uContrast, uObserve, uTransition, uFade, uFlash, uVignette, uGrain, uAspect;
    uniform vec3 uTint, uShadowTint, uFadeColor;
    varying vec2 vUv;

    float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }

    void main() {
      vec2 uv = vUv;
      vec2 c = uv - 0.5;
      c.x *= uAspect;
      float r = length(c);
      // temporal transition: concentric refraction ripple moving outwards
      if (uTransition > 0.001) {
        float wave = sin(r * 38.0 - uTime * 9.0) * 0.006 * uTransition;
        uv += normalize(c + 1e-5) * wave * smoothstep(0.0, 0.6, r);
      }
      vec3 col = texture2D(tDiffuse, uv).rgb;

      float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
      // colour balance: shadow tint below mid grey, highlight tint above
      float t = smoothstep(0.0, 0.35, lum);
      col *= mix(uShadowTint, uTint, t);
      col = mix(vec3(lum), col, uSaturation);
      col = max(vec3(0.0), (col - 0.18) * uContrast + 0.18);

      // temporal observation mode: cool desaturated present, warm highlights for echoes
      if (uObserve > 0.001) {
        float l2 = dot(col, vec3(0.2126, 0.7152, 0.0722));
        vec3 obs = vec3(l2) * vec3(0.78, 0.92, 1.08);
        col = mix(col, obs, uObserve * 0.85);
        col *= 1.0 - uObserve * 0.35 * smoothstep(0.35, 0.95, r);
      }

      col += vec3(uFlash);
      col = mix(col, col * (1.0 - smoothstep(0.45, 1.05, r)), uVignette);
      col += (hash(vUv * 1000.0 + fract(uTime)) - 0.5) * uGrain * (0.25 + lum);
      col = mix(col, uFadeColor, uFade);
      if (uTransition > 0.001) col = mix(col, vec3(0.75, 0.88, 1.0) * 1.6, uTransition * uTransition * 0.65);
      gl_FragColor = vec4(col, 1.0);
    }
  `,
};
