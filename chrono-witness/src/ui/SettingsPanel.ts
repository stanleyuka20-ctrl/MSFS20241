import { h, clear } from './dom';
import { applyPreset, type Settings, type PresetName } from '../core/Settings';

type Getter = () => number | string | boolean;
type Setter = (v: number | string | boolean) => void;

interface Row {
  label: string;
  note?: string;
  kind: 'range' | 'select' | 'toggle';
  min?: number;
  max?: number;
  step?: number;
  options?: [string, string][];
  get: Getter;
  set: Setter;
  format?: (v: number) => string;
  graphics?: boolean;
}

/**
 * Settings UI: Graphics (presets + custom), Controls, Accessibility, Audio. Any manual change to a
 * graphics option switches the preset to Custom.
 */
export function buildSettingsPanel(s: Settings, onChange: (graphicsChanged: boolean) => void, onClose: () => void, initialTab = 'graphics'): HTMLElement {
  const g = s.graphics;
  const c = s.controls;
  const a = s.accessibility;
  const au = s.audio;
  const pct = (v: number): string => `${Math.round(v * 100)}%`;
  const gfx = (key: keyof typeof g) => (v: number | string | boolean) => {
    (g as unknown as Record<string, unknown>)[key] = v;
    g.preset = 'custom';
  };
  const tabs: Record<string, Row[]> = {
    graphics: [
      { label: 'Preset', kind: 'select', options: [['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['custom', 'Custom']], get: () => g.preset, set: (v) => applyPreset(g, v as PresetName), graphics: true, note: 'Low keeps the art direction by reducing shadows, AO, distant detail and resolution first.' },
      { label: 'Resolution scale', kind: 'range', min: 0.5, max: 1, step: 0.05, get: () => g.resolutionScale, set: gfx('resolutionScale'), format: pct, graphics: true },
      { label: 'Frame-rate cap', kind: 'select', options: [['0', 'Display refresh (V-Sync)'], ['30', '30'], ['60', '60'], ['120', '120'], ['144', '144']], get: () => String(g.fpsCap), set: (v) => (g.fpsCap = Number(v) as Settings['graphics']['fpsCap']), graphics: false, note: 'Higher caps need a high-refresh display and a capable GPU.' },
      { label: 'Adaptive quality', kind: 'toggle', get: () => g.adaptiveQuality, set: (v) => (g.adaptiveQuality = Boolean(v)), note: 'Lowers render resolution temporarily when frame time exceeds the target.' },
      { label: 'Adaptive target', kind: 'select', options: [['60', '60 fps'], ['120', '120 fps'], ['144', '144 fps']], get: () => String(g.adaptiveTarget), set: (v) => (g.adaptiveTarget = Number(v) as 60 | 120 | 144) },
      { label: 'Shadows', kind: 'select', options: [['0', 'Off'], ['1', 'Low (1024)'], ['2', 'Medium (2048)'], ['3', 'High (4096)']], get: () => String(g.shadowQuality), set: (v) => gfx('shadowQuality')(Number(v)), graphics: true },
      { label: 'Shadow distance', kind: 'range', min: 15, max: 70, step: 5, get: () => g.shadowDistance, set: gfx('shadowDistance'), format: (v) => `${v} m`, graphics: true },
      { label: 'Ambient occlusion (GTAO)', kind: 'toggle', get: () => g.ambientOcclusion, set: gfx('ambientOcclusion'), graphics: true },
      { label: 'Anti-aliasing', kind: 'select', options: [['off', 'Off'], ['fxaa', 'FXAA'], ['smaa', 'SMAA'], ['msaa', 'MSAA 4×']], get: () => g.antialiasing, set: gfx('antialiasing'), graphics: true },
      { label: 'Texture quality', kind: 'select', options: [['0', 'Low (512)'], ['1', 'Medium (1024)'], ['2', 'High (full)']], get: () => String(g.textureQuality), set: (v) => gfx('textureQuality')(Number(v)), graphics: true, note: 'Applies on next destination load.' },
      { label: 'Anisotropic filtering', kind: 'select', options: [['1', 'Off'], ['4', '4×'], ['8', '8×'], ['16', '16×']], get: () => String(g.anisotropy), set: (v) => gfx('anisotropy')(Number(v)), graphics: true },
      { label: 'Draw distance', kind: 'range', min: 300, max: 1600, step: 100, get: () => g.drawDistance, set: gfx('drawDistance'), format: (v) => `${v} m`, graphics: true },
      { label: 'Detail density', kind: 'range', min: 0.2, max: 1, step: 0.1, get: () => g.detailDensity, set: gfx('detailDensity'), format: pct, graphics: true, note: 'Grass, debris and small props. Applies on next load.' },
      { label: 'Rain density', kind: 'range', min: 0.2, max: 1, step: 0.1, get: () => g.rainDensity, set: gfx('rainDensity'), format: pct, graphics: true },
      { label: 'Subtle bloom', kind: 'toggle', get: () => g.bloom, set: gfx('bloom'), graphics: true },
    ],
    controls: [
      { label: 'Mouse sensitivity', kind: 'range', min: 0.2, max: 3, step: 0.05, get: () => c.mouseSensitivity, set: (v) => (c.mouseSensitivity = Number(v)), format: (v) => v.toFixed(2) },
      { label: 'Invert vertical look', kind: 'toggle', get: () => c.invertY, set: (v) => (c.invertY = Boolean(v)) },
      { label: 'Field of view (vertical)', kind: 'range', min: 60, max: 95, step: 1, get: () => c.fov, set: (v) => (c.fov = Number(v)), format: (v) => `${v}°` },
      { label: 'Toggle crouch', kind: 'toggle', get: () => c.toggleCrouch, set: (v) => (c.toggleCrouch = Boolean(v)) },
      { label: 'Toggle sprint', kind: 'toggle', get: () => c.toggleSprint, set: (v) => (c.toggleSprint = Boolean(v)) },
    ],
    accessibility: [
      { label: 'Text size', kind: 'range', min: 0.85, max: 1.6, step: 0.05, get: () => a.textScale, set: (v) => (a.textScale = Number(v)), format: pct },
      { label: 'Subtitles', kind: 'toggle', get: () => a.subtitles, set: (v) => (a.subtitles = Boolean(v)) },
      { label: 'Speaker labels', kind: 'toggle', get: () => a.speakerLabels, set: (v) => (a.speakerLabels = Boolean(v)) },
      { label: 'Subtitle background', kind: 'range', min: 0, max: 1, step: 0.05, get: () => a.subtitleBackground, set: (v) => (a.subtitleBackground = Number(v)), format: pct },
      { label: 'Visual sound cues', kind: 'toggle', get: () => a.soundCueIndicators, set: (v) => (a.soundCueIndicators = Boolean(v)), note: 'Danger cues are always shown.' },
      { label: 'Camera shake', kind: 'range', min: 0, max: 1, step: 0.05, get: () => a.cameraShake, set: (v) => (a.cameraShake = Number(v)), format: pct },
      { label: 'Head bob', kind: 'range', min: 0, max: 1, step: 0.05, get: () => a.headBob, set: (v) => (a.headBob = Number(v)), format: pct },
      { label: 'Motion effects', kind: 'range', min: 0, max: 1, step: 0.05, get: () => a.motionEffects, set: (v) => (a.motionEffects = Number(v)), format: pct, note: 'Hand sway, temporal distortion, camera roll.' },
      { label: 'Reduced flashing', kind: 'toggle', get: () => a.reducedFlash, set: (v) => (a.reducedFlash = Boolean(v)), note: 'Caps the brightness and onset speed of artillery flashes, flares, lightning and temporal transitions.' },
      { label: 'High-contrast prompts', kind: 'toggle', get: () => a.highContrastPrompts, set: (v) => (a.highContrastPrompts = Boolean(v)) },
      { label: 'Time allowed for timed hazards', kind: 'range', min: 1, max: 3, step: 0.25, get: () => a.hazardTimeMultiplier, set: (v) => (a.hazardTimeMultiplier = Number(v)), format: (v) => `${v.toFixed(2)}×` },
      { label: 'Ask before intense sequences', kind: 'toggle', get: () => a.intenseSequencePrompt, set: (v) => (a.intenseSequencePrompt = Boolean(v)), note: 'Offers a skip that keeps mission progress.' },
    ],
    audio: [
      { label: 'Master volume', kind: 'range', min: 0, max: 1, step: 0.05, get: () => au.master, set: (v) => (au.master = Number(v)), format: pct },
      { label: 'Effects', kind: 'range', min: 0, max: 1, step: 0.05, get: () => au.effects, set: (v) => (au.effects = Number(v)), format: pct },
      { label: 'Ambience', kind: 'range', min: 0, max: 1, step: 0.05, get: () => au.ambience, set: (v) => (au.ambience = Number(v)), format: pct },
      { label: 'Interface', kind: 'range', min: 0, max: 1, step: 0.05, get: () => au.ui, set: (v) => (au.ui = Number(v)), format: pct },
    ],
  };
  const labels: Record<string, string> = { graphics: 'Graphics', controls: 'Controls', accessibility: 'Accessibility', audio: 'Audio' };
  const panel = h('div.panel', { style: { width: 'min(92vw, 860px)' } });
  const tabBar = h('div.tabs');
  const body = h('div');
  let current = initialTab;
  const render = (): void => {
    clear(tabBar);
    for (const k of Object.keys(tabs)) {
      tabBar.append(h('button', { class: k === current ? 'active' : '', onclick: () => ((current = k), render()) }, labels[k]));
    }
    clear(body);
    for (const r of tabs[current]) body.append(row(r));
  };
  const row = (r: Row): HTMLElement => {
    const val = h('span.val');
    let input: HTMLElement;
    const update = (v: number | string | boolean): void => {
      r.set(v);
      onChange(!!r.graphics);
      if (r.label === 'Preset' || r.graphics) setTimeout(render, 0);
    };
    if (r.kind === 'range') {
      const el = h('input', { type: 'range', min: r.min, max: r.max, step: r.step, value: String(r.get()) }) as HTMLInputElement;
      val.textContent = r.format ? r.format(Number(r.get())) : String(r.get());
      el.addEventListener('input', () => {
        val.textContent = r.format ? r.format(Number(el.value)) : el.value;
      });
      el.addEventListener('change', () => update(Number(el.value)));
      input = el;
    } else if (r.kind === 'select') {
      const el = h('select', null, ...r.options!.map(([v, l]) => h('option', { value: v, selected: String(r.get()) === v }, l))) as HTMLSelectElement;
      el.addEventListener('change', () => update(el.value));
      input = el;
    } else {
      const el = h('input', { type: 'checkbox', checked: Boolean(r.get()) }) as HTMLInputElement;
      el.addEventListener('change', () => update(el.checked));
      input = el;
      val.textContent = '';
    }
    const wrap = h('div.setting', null, h('label', null, r.label), input, val);
    if (r.note) return h('div', null, wrap, h('div.note', { style: { margin: '-2px 0 6px' } }, r.note));
    return wrap;
  };
  render();
  panel.append(h('h2', null, 'Settings'), tabBar, body, h('div.row', { style: { marginTop: '18px', justifyContent: 'flex-end' } }, h('button.primary', { onclick: onClose }, 'Done')));
  return panel;
}
