import * as THREE from 'three';
import { h, clear } from './dom';
import type { Settings } from '../core/Settings';

interface Cue {
  el: HTMLElement;
  until: number;
}

/**
 * In-game HUD: destination/date, current objective, crosshair + interaction prompt, subtitles,
 * notifications, danger indicator, directional visual sound cues, objective markers and scanner
 * brackets. Updates touch the DOM only when values change.
 */
export class HUD {
  readonly el = h('div.hud');
  private locDest = h('div.dest');
  private locDate = h('div.date');
  private objWrap = h('div.hud-objective');
  private objLabel = h('div.label', null, 'Objective');
  private objText = h('div.text');
  private objProgress = h('div.progress');
  private crosshair = h('div.crosshair');
  private prompt = h('div.prompt.hidden');
  private subs = h('div.subtitles');
  private toasts = h('div.toasts');
  private danger = h('div.danger.hidden');
  private dangerText = h('div.danger-text.hidden');
  private cues = h('div.cues');
  private markers = h('div.markers');
  private brackets = h('div.brackets');
  private deviceBar = h('div.device-bar');
  private energyFill = h('div');
  private modeLabel = h('div.mode-label.hidden');
  private fps = h('div.fps.hidden');
  private lastObjective = '';
  private lastPrompt = '';
  private cueList: Cue[] = [];
  private markerEls = new Map<string, HTMLElement>();
  private bracketEls = new Map<string, HTMLElement>();
  private holdRing: SVGCircleElement | null = null;

  constructor(private readonly settings: Settings) {
    this.objWrap.append(this.objLabel, this.objText, this.objProgress);
    this.deviceBar.append(h('span', null, h('span.key', null, 'Q'), ' Scanner'), h('span', null, h('span.key', null, 'F'), ' Observe'), h('div.energy', null, this.energyFill), h('span', null, h('span.key', null, 'J'), ' Journal'));
    this.el.append(
      h('div.hud-location', null, this.locDest, this.locDate),
      this.objWrap,
      this.markers,
      this.brackets,
      this.crosshair,
      this.prompt,
      this.danger,
      this.dangerText,
      this.cues,
      this.subs,
      this.toasts,
      this.deviceBar,
      this.modeLabel,
      this.fps,
    );
  }

  setLocation(dest: string, date: string): void {
    this.locDest.textContent = dest;
    this.locDate.textContent = date;
  }

  setObjective(text: string | null, progress?: string, label = 'Objective'): void {
    const key = `${label}|${text}|${progress}`;
    if (key === this.lastObjective) return;
    const changed = text !== null && !this.lastObjective.includes(`|${text}|`);
    this.lastObjective = key;
    this.objWrap.classList.toggle('hidden', !text);
    this.objLabel.textContent = label;
    this.objText.textContent = text ?? '';
    this.objProgress.textContent = progress ?? '';
    if (changed) {
      this.objWrap.classList.remove('flash');
      void this.objWrap.offsetWidth;
      this.objWrap.classList.add('flash');
    }
  }

  setPrompt(key: string | null, text = '', hold = 0, holdProgress = 0): void {
    const id = `${key}|${text}|${hold > 0}`;
    if (id !== this.lastPrompt) {
      this.lastPrompt = id;
      clear(this.prompt);
      this.holdRing = null;
      this.prompt.classList.toggle('hidden', !key);
      this.prompt.classList.toggle('high-contrast', this.settings.accessibility.highContrastPrompts);
      this.crosshair.classList.toggle('focus', !!key);
      if (key) {
        if (hold > 0) {
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('viewBox', '0 0 20 20');
          svg.classList.add('hold-ring');
          const bg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          bg.setAttribute('cx', '10');
          bg.setAttribute('cy', '10');
          bg.setAttribute('r', '8');
          bg.setAttribute('fill', 'none');
          bg.setAttribute('stroke', 'rgba(255,255,255,.25)');
          bg.setAttribute('stroke-width', '2');
          const fg = bg.cloneNode() as SVGCircleElement;
          fg.setAttribute('stroke', '#d8b46a');
          fg.setAttribute('stroke-dasharray', '50.3');
          fg.setAttribute('transform', 'rotate(-90 10 10)');
          svg.append(bg, fg);
          this.holdRing = fg;
          this.prompt.append(svg);
        }
        this.prompt.append(h('span.key', null, key), h('span', null, hold > 0 ? `Hold — ${text}` : text));
      }
    }
    if (this.holdRing) this.holdRing.setAttribute('stroke-dashoffset', String(50.3 * (1 - holdProgress)));
  }

  subtitle(speaker: string, text: string, duration: number, sfx = false): void {
    const a = this.settings.accessibility;
    if (!a.subtitles && !sfx) return;
    const el = h('div.subtitle', null, a.speakerLabels && speaker ? h('span.speaker', null, `${speaker}:`) : null, text);
    if (sfx) el.classList.add('sfx');
    this.subs.append(el);
    while (this.subs.children.length > 3) this.subs.firstElementChild?.remove();
    window.setTimeout(() => el.remove(), duration * 1000);
  }

  toast(text: string, kind = 'info'): void {
    const el = h(`div.toast.${kind}` as 'div', null, text);
    this.toasts.append(el);
    while (this.toasts.children.length > 4) this.toasts.firstElementChild?.remove();
    window.setTimeout(() => el.remove(), 4800);
  }

  setDanger(text: string | null, seconds?: number): void {
    const on = !!text;
    this.danger.classList.toggle('hidden', !on);
    this.danger.classList.toggle('reduced', this.settings.accessibility.reducedFlash);
    this.dangerText.classList.toggle('hidden', !on);
    if (on) {
      clear(this.dangerText);
      this.dangerText.append(text!);
      if (seconds !== undefined) this.dangerText.append(h('span.timer', null, `${Math.max(0, seconds).toFixed(0)} s`));
    }
  }

  /** Visual sound cue at the screen edge in the sound's direction. */
  cue(label: string, direction: number | undefined, danger: boolean, now: number): void {
    if (!this.settings.accessibility.soundCueIndicators && !danger) return;
    // merge with an existing identical label
    for (const c of this.cueList) {
      if (c.el.dataset.label === label) {
        c.until = now + 2.6;
        this.placeCue(c.el, direction);
        return;
      }
    }
    const el = h('div.cue', { 'data-label': label });
    if (danger) el.classList.add('danger-cue');
    const arrow = direction === undefined ? '◆' : Math.abs(direction) < 0.5 ? '▲' : Math.abs(direction) > 2.6 ? '▼' : direction > 0 ? '▶' : '◀';
    el.append(h('span.arrow', null, arrow), label);
    this.placeCue(el, direction);
    this.cues.append(el);
    this.cueList.push({ el, until: now + 2.6 });
    if (this.cueList.length > 5) this.cueList.shift()!.el.remove();
  }

  private placeCue(el: HTMLElement, direction?: number): void {
    el.style.left = el.style.right = el.style.top = el.style.bottom = '';
    if (direction === undefined || Math.abs(direction) < 0.5) {
      el.style.left = '50%';
      el.style.top = '18%';
      el.style.transform = 'translateX(-50%)';
    } else if (Math.abs(direction) > 2.6) {
      el.style.left = '50%';
      el.style.top = '';
      el.style.bottom = '20%';
      el.style.transform = 'translateX(-50%)';
    } else if (direction > 0) {
      el.style.right = '3%';
      el.style.top = `${50 - Math.cos(direction) * 25}%`;
      el.style.transform = 'translateY(-50%)';
    } else {
      el.style.left = '3%';
      el.style.top = `${50 - Math.cos(direction) * 25}%`;
      el.style.transform = 'translateY(-50%)';
    }
  }

  updateCues(now: number): void {
    for (let i = this.cueList.length - 1; i >= 0; i--) {
      if (now > this.cueList[i].until) {
        this.cueList[i].el.remove();
        this.cueList.splice(i, 1);
      }
    }
  }

  /** Markers: world positions projected to screen; off-screen markers clamp to edges. */
  updateMarkers(items: Map<string, { pos: THREE.Vector3; label: string }>, camera: THREE.Camera, playerPos: THREE.Vector3, w: number, hgt: number): void {
    for (const [id, el] of this.markerEls) {
      if (!items.has(id)) {
        el.remove();
        this.markerEls.delete(id);
      }
    }
    for (const [id, m] of items) {
      let el = this.markerEls.get(id);
      if (!el) {
        el = h('div.marker', null, h('div.diamond'), h('span'));
        this.markers.append(el);
        this.markerEls.set(id, el);
      }
      _v.copy(m.pos).project(camera);
      const behind = _v.z > 1;
      let x = (_v.x * 0.5 + 0.5) * w;
      let y = (-_v.y * 0.5 + 0.5) * hgt;
      if (behind) {
        x = w - x;
        y = hgt - 40;
      }
      x = Math.min(w - 40, Math.max(40, x));
      y = Math.min(hgt - 60, Math.max(60, y));
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
      const d = m.pos.distanceTo(playerPos);
      (el.lastChild as HTMLElement).textContent = `${m.label} · ${d.toFixed(0)} m`;
      el.style.opacity = d < 3 ? '0' : '0.85';
    }
  }

  updateBrackets(items: { id: string; pos: THREE.Vector3; size: number; done: boolean; focus: boolean }[], camera: THREE.Camera, w: number, hgt: number): void {
    const seen = new Set<string>();
    for (const it of items) {
      _v.copy(it.pos).project(camera);
      if (_v.z > 1 || Math.abs(_v.x) > 1.1 || Math.abs(_v.y) > 1.1) continue;
      seen.add(it.id);
      let el = this.bracketEls.get(it.id);
      if (!el) {
        el = h('div.scan-bracket');
        this.brackets.append(el);
        this.bracketEls.set(it.id, el);
      }
      const dist = camera.position.distanceTo(it.pos);
      const px = Math.max(18, Math.min(220, ((it.size * 2) / Math.max(0.5, dist)) * hgt * 0.6));
      el.style.left = `${(_v.x * 0.5 + 0.5) * w}px`;
      el.style.top = `${(-_v.y * 0.5 + 0.5) * hgt}px`;
      el.style.width = el.style.height = `${px}px`;
      el.classList.toggle('done', it.done);
      el.classList.toggle('focus', it.focus);
    }
    for (const [id, el] of this.bracketEls) {
      if (!seen.has(id)) {
        el.remove();
        this.bracketEls.delete(id);
      }
    }
  }

  setEnergy(f: number): void {
    this.energyFill.style.width = `${Math.round(f * 100)}%`;
  }

  setMode(label: string | null): void {
    this.modeLabel.classList.toggle('hidden', !label);
    this.modeLabel.textContent = label ?? '';
  }

  showDeviceBar(v: boolean): void {
    this.deviceBar.classList.toggle('hidden', !v);
  }

  setFps(text: string | null): void {
    this.fps.classList.toggle('hidden', !text);
    if (text) this.fps.textContent = text;
  }

  clearTransient(): void {
    clear(this.subs);
    clear(this.toasts);
    for (const c of this.cueList) c.el.remove();
    this.cueList = [];
    this.setDanger(null);
    this.setPrompt(null);
    for (const el of this.markerEls.values()) el.remove();
    this.markerEls.clear();
    for (const el of this.bracketEls.values()) el.remove();
    this.bracketEls.clear();
  }
}

const _v = new THREE.Vector3();
