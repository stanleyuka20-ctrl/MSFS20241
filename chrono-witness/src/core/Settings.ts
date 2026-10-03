/**
 * Player settings: graphics (with Low/Medium/High/Custom presets), controls, accessibility.
 * Persisted in localStorage. Presets reduce expensive effects first so the art direction holds at Low.
 */
export type PresetName = 'low' | 'medium' | 'high' | 'custom';

export interface GraphicsSettings {
  preset: PresetName;
  /** Internal render resolution as a fraction of the canvas size. */
  resolutionScale: number;
  /** 0 = follow display refresh (vsync), otherwise a frame cap. */
  fpsCap: 0 | 30 | 60 | 120 | 144;
  adaptiveQuality: boolean;
  /** Frame-time target used by adaptive quality (fps). */
  adaptiveTarget: 60 | 120 | 144;
  shadowQuality: 0 | 1 | 2 | 3; // off, 1024, 2048, 4096
  shadowDistance: number; // metres covered by the sun shadow map
  ambientOcclusion: boolean;
  antialiasing: 'off' | 'fxaa' | 'smaa' | 'msaa';
  textureQuality: 0 | 1 | 2; // 512, 1024, full
  anisotropy: 1 | 4 | 8 | 16;
  drawDistance: number; // metres
  detailDensity: number; // 0..1 multiplier for grass/debris instancing
  rainDensity: number; // 0..1 multiplier for rain particles
  npcAnimLodDistance: number; // beyond this NPC animation updates are throttled
  bloom: boolean;
}

export interface ControlSettings {
  mouseSensitivity: number; // 0.2 .. 3
  invertY: boolean;
  fov: number; // vertical, 60..95
  toggleCrouch: boolean;
  toggleSprint: boolean;
}

export interface AccessibilitySettings {
  textScale: number; // 0.85 .. 1.6
  subtitles: boolean;
  speakerLabels: boolean;
  subtitleBackground: number; // 0..1 opacity
  soundCueIndicators: boolean;
  cameraShake: number; // 0..1
  headBob: number; // 0..1
  motionEffects: number; // 0..1 (temporal distortion, sway)
  reducedFlash: boolean;
  highContrastPrompts: boolean;
  /** Extra time for timed hazards (multiplier, 1 = default). */
  hazardTimeMultiplier: number;
  /** Ask before intense scripted sequences, offering a skip that preserves progress. */
  intenseSequencePrompt: boolean;
}

export interface AudioSettings {
  master: number;
  effects: number;
  ambience: number;
  ui: number;
}

export interface Settings {
  version: number;
  graphics: GraphicsSettings;
  controls: ControlSettings;
  accessibility: AccessibilitySettings;
  audio: AudioSettings;
}

export const PRESETS: Record<Exclude<PresetName, 'custom'>, Omit<GraphicsSettings, 'preset' | 'fpsCap' | 'adaptiveQuality' | 'adaptiveTarget'>> = {
  low: {
    resolutionScale: 0.75,
    shadowQuality: 1,
    shadowDistance: 24,
    ambientOcclusion: false,
    antialiasing: 'fxaa',
    textureQuality: 0,
    anisotropy: 4,
    drawDistance: 450,
    detailDensity: 0.4,
    rainDensity: 0.45,
    npcAnimLodDistance: 18,
    bloom: false,
  },
  medium: {
    resolutionScale: 0.9,
    shadowQuality: 2,
    shadowDistance: 36,
    ambientOcclusion: false,
    antialiasing: 'smaa',
    textureQuality: 1,
    anisotropy: 8,
    drawDistance: 800,
    detailDensity: 0.7,
    rainDensity: 0.7,
    npcAnimLodDistance: 28,
    bloom: false,
  },
  high: {
    resolutionScale: 1,
    shadowQuality: 3,
    shadowDistance: 50,
    ambientOcclusion: true,
    antialiasing: 'smaa',
    textureQuality: 2,
    anisotropy: 16,
    drawDistance: 1400,
    detailDensity: 1,
    rainDensity: 1,
    npcAnimLodDistance: 40,
    bloom: true,
  },
};

export function defaultSettings(): Settings {
  return {
    version: 2,
    graphics: { preset: 'medium', fpsCap: 0, adaptiveQuality: true, adaptiveTarget: 60, ...PRESETS.medium },
    controls: { mouseSensitivity: 1, invertY: false, fov: 72, toggleCrouch: false, toggleSprint: false },
    accessibility: {
      textScale: 1,
      subtitles: true,
      speakerLabels: true,
      subtitleBackground: 0.55,
      soundCueIndicators: true,
      cameraShake: 0.6,
      headBob: 0.6,
      motionEffects: 1,
      reducedFlash: false,
      highContrastPrompts: false,
      hazardTimeMultiplier: 1,
      intenseSequencePrompt: true,
    },
    audio: { master: 0.8, effects: 0.9, ambience: 0.8, ui: 0.7 },
  };
}

const KEY = 'chrono-witness.settings';

export function applyPreset(g: GraphicsSettings, preset: PresetName): void {
  g.preset = preset;
  if (preset !== 'custom') Object.assign(g, PRESETS[preset]);
}

export function loadSettings(storage: Storage | null = safeStorage()): Settings {
  const def = defaultSettings();
  if (!storage) return def;
  try {
    const raw = storage.getItem(KEY);
    if (!raw) return def;
    const parsed = JSON.parse(raw) as Partial<Settings>;
    return {
      version: def.version,
      graphics: { ...def.graphics, ...(parsed.graphics ?? {}) },
      controls: { ...def.controls, ...(parsed.controls ?? {}) },
      accessibility: { ...def.accessibility, ...(parsed.accessibility ?? {}) },
      audio: { ...def.audio, ...(parsed.audio ?? {}) },
    };
  } catch {
    return def;
  }
}

export function saveSettings(s: Settings, storage: Storage | null = safeStorage()): void {
  try {
    storage?.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable (private mode) — settings stay in memory */
  }
}

export function safeStorage(): Storage | null {
  try {
    const s = globalThis.localStorage;
    const k = '__cw_probe';
    s.setItem(k, '1');
    s.removeItem(k);
    return s;
  } catch {
    return null;
  }
}
