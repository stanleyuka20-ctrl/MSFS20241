import type { EventBus, GameEvents } from '../core/Events';
import type { Settings } from '../core/Settings';

type Bus = 'effects' | 'ambience' | 'ui';

/**
 * Procedural WebAudio sound: no audio files are required. Every gameplay-relevant sound also
 * emits a `soundCue` event so the HUD can show a visual equivalent (direction + label), keeping
 * every mission completable without hearing.
 */
export class AudioSystem {
  ctx: AudioContext | null = null;
  private master!: GainNode;
  private buses!: Record<Bus, GainNode>;
  private noiseBuf!: AudioBuffer;
  private brownBuf!: AudioBuffer;
  private reverb!: ConvolverNode;
  private reverbSend!: GainNode;
  private loops = new Map<string, { src: AudioBufferSourceNode; gain: GainNode; filter: BiquadFilterNode }>();
  /** Listener yaw (radians) for computing cue directions. */
  listenerYaw = 0;
  listenerX = 0;
  listenerZ = 0;
  muffled = 0;

  constructor(
    private readonly settings: Settings,
    private readonly events: EventBus<GameEvents>,
  ) {}

  /** Must be called from a user gesture. */
  unlock(): void {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') void this.ctx.resume();
      return;
    }
    try {
      this.ctx = new AudioContext();
    } catch {
      return;
    }
    const ctx = this.ctx;
    this.master = ctx.createGain();
    this.master.connect(ctx.destination);
    this.buses = { effects: ctx.createGain(), ambience: ctx.createGain(), ui: ctx.createGain() };
    for (const b of Object.values(this.buses)) b.connect(this.master);
    // white + brown noise buffers
    const len = ctx.sampleRate * 3;
    this.noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    this.brownBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    const w = this.noiseBuf.getChannelData(0);
    const br = this.brownBuf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++) {
      w[i] = Math.random() * 2 - 1;
      last = (last + 0.02 * w[i]) / 1.02;
      br[i] = last * 3.5;
    }
    // simple generated reverb impulse
    const irLen = ctx.sampleRate * 2.2;
    const ir = ctx.createBuffer(2, irLen, ctx.sampleRate);
    for (let c = 0; c < 2; c++) {
      const d = ir.getChannelData(c);
      for (let i = 0; i < irLen; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / irLen, 3.2);
    }
    this.reverb = ctx.createConvolver();
    this.reverb.buffer = ir;
    this.reverbSend = ctx.createGain();
    this.reverbSend.gain.value = 0.35;
    this.reverbSend.connect(this.reverb);
    this.reverb.connect(this.buses.effects);
    this.applyVolumes();
  }

  applyVolumes(): void {
    if (!this.ctx) return;
    const a = this.settings.audio;
    this.master.gain.value = a.master;
    this.buses.effects.gain.value = a.effects;
    this.buses.ambience.gain.value = a.ambience;
    this.buses.ui.gain.value = a.ui;
  }

  /** Relative direction (radians, 0 = ahead, +right) from listener to a world point. */
  directionTo(x: number, z: number): number {
    const dx = x - this.listenerX;
    const dz = z - this.listenerZ;
    const s = Math.sin(this.listenerYaw);
    const c = Math.cos(this.listenerYaw);
    // forward = (-sin, -cos), right = (cos, -sin)
    return Math.atan2(dx * c - dz * s, -dx * s - dz * c);
  }

  // -------------------------------------------------------------- loops
  setLoop(id: string, kind: 'rain' | 'wind' | 'hum' | 'room', level: number, bus: Bus = 'ambience'): void {
    if (!this.ctx) return;
    let l = this.loops.get(id);
    if (!l) {
      const ctx = this.ctx;
      const src = ctx.createBufferSource();
      src.buffer = kind === 'wind' || kind === 'room' ? this.brownBuf : this.noiseBuf;
      src.loop = true;
      const filter = ctx.createBiquadFilter();
      const gain = ctx.createGain();
      gain.gain.value = 0;
      if (kind === 'rain') {
        filter.type = 'bandpass';
        filter.frequency.value = 2400;
        filter.Q.value = 0.35;
      } else if (kind === 'wind') {
        filter.type = 'lowpass';
        filter.frequency.value = 520;
      } else if (kind === 'hum') {
        filter.type = 'lowpass';
        filter.frequency.value = 180;
      } else {
        filter.type = 'lowpass';
        filter.frequency.value = 300;
      }
      src.connect(filter).connect(gain).connect(this.buses[bus]);
      src.start();
      l = { src, gain, filter };
      this.loops.set(id, l);
    }
    l.gain.gain.setTargetAtTime(level, this.ctx.currentTime, 0.6);
    if (kind === 'rain') l.filter.frequency.setTargetAtTime(this.muffled > 0.5 ? 700 : 2400, this.ctx.currentTime, 0.3);
  }

  stopAllLoops(): void {
    for (const l of this.loops.values()) {
      try {
        l.src.stop();
      } catch {
        /* already stopped */
      }
      l.src.disconnect();
    }
    this.loops.clear();
  }

  // -------------------------------------------------------------- one-shots
  private burst(opts: { buf?: AudioBuffer; type: BiquadFilterType; freq: number; q?: number; gain: number; attack: number; decay: number; bus?: Bus; reverb?: number; freqEnd?: number; rate?: number; delay?: number }): void {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const t0 = ctx.currentTime + (opts.delay ?? 0);
    const src = ctx.createBufferSource();
    src.buffer = opts.buf ?? this.noiseBuf;
    src.playbackRate.value = opts.rate ?? 1;
    const f = ctx.createBiquadFilter();
    f.type = opts.type;
    f.frequency.setValueAtTime(opts.freq, t0);
    if (opts.freqEnd) f.frequency.exponentialRampToValueAtTime(opts.freqEnd, t0 + opts.attack + opts.decay);
    f.Q.value = opts.q ?? 0.8;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002, opts.gain), t0 + opts.attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + opts.attack + opts.decay);
    src.connect(f).connect(g).connect(this.buses[opts.bus ?? 'effects']);
    if (opts.reverb) {
      const s = ctx.createGain();
      s.gain.value = opts.reverb;
      g.connect(s).connect(this.reverbSend);
    }
    src.start(t0, Math.random() * 2);
    src.stop(t0 + opts.attack + opts.decay + 0.05);
  }

  footstep(surface: string, intensity: number): void {
    const v = 0.12 + intensity * 0.14;
    switch (surface) {
      case 'mud':
      case 'water':
        this.burst({ type: 'lowpass', freq: 900, gain: v * 1.3, attack: 0.02, decay: 0.22, freqEnd: 260 });
        this.burst({ type: 'bandpass', freq: 2600, q: 2, gain: v * 0.35, attack: 0.03, decay: 0.12, delay: 0.05 });
        break;
      case 'wood':
      case 'ladder':
        this.burst({ type: 'bandpass', freq: 420, q: 1.6, gain: v * 1.4, attack: 0.004, decay: 0.09 });
        this.burst({ type: 'bandpass', freq: 1500, q: 3, gain: v * 0.5, attack: 0.002, decay: 0.05 });
        break;
      case 'stone':
      case 'rubble':
        this.burst({ type: 'highpass', freq: 1800, gain: v * 0.9, attack: 0.003, decay: 0.08 });
        break;
      case 'metal':
      case 'hq':
        this.burst({ type: 'bandpass', freq: 1200, q: 1.2, gain: v * 0.7, attack: 0.003, decay: 0.07 });
        break;
      default:
        this.burst({ type: 'lowpass', freq: 1300, gain: v, attack: 0.008, decay: 0.12 });
    }
  }

  /** Distant artillery: low rumble with delay proportional to distance. Emits a visual cue. */
  distantGun(x: number, z: number, distance: number, label = 'Artillery fire — distant'): void {
    const gain = Math.min(0.9, 2.4 / (1 + distance / 400));
    this.burst({ buf: this.brownBuf, type: 'lowpass', freq: 220, gain, attack: 0.03, decay: 2.2, reverb: 0.7, freqEnd: 60 });
    this.events.emit('soundCue', { id: 'gun', label, direction: this.directionTo(x, z), intensity: gain });
  }

  /** Incoming shell: descending whistle then impact. */
  shellWhistle(x: number, z: number, duration: number): void {
    if (this.ctx) {
      const ctx = this.ctx;
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      const t0 = ctx.currentTime;
      o.type = 'sine';
      o.frequency.setValueAtTime(1500, t0);
      o.frequency.exponentialRampToValueAtTime(380, t0 + duration);
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.08, t0 + duration * 0.8);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      o.connect(g).connect(this.buses.effects);
      o.start(t0);
      o.stop(t0 + duration + 0.05);
    }
    this.events.emit('soundCue', { id: 'whistle', label: 'Shell incoming', direction: this.directionTo(x, z), intensity: 0.9, danger: true });
  }

  impact(x: number, z: number, distance: number): void {
    const near = Math.max(0, 1 - distance / 60);
    const gain = Math.min(1.2, 0.25 + near * 1.1);
    this.burst({ buf: this.brownBuf, type: 'lowpass', freq: 900 * (0.4 + near), gain, attack: 0.005, decay: 1.6 + near, reverb: 0.8, freqEnd: 70 });
    this.burst({ type: 'lowpass', freq: 3000, gain: gain * 0.4 * near, attack: 0.002, decay: 0.4, delay: 0.02 });
    // debris patter
    if (near > 0.3) this.burst({ type: 'highpass', freq: 2500, gain: 0.08 * near, attack: 0.2, decay: 1.2, delay: 0.3 });
    this.events.emit('soundCue', { id: 'impact', label: near > 0.4 ? 'Shell impact — close' : 'Shell impact', direction: this.directionTo(x, z), intensity: gain, danger: near > 0.4 });
  }

  thunderOrFlare(label: string): void {
    this.burst({ type: 'bandpass', freq: 1800, q: 4, gain: 0.08, attack: 0.01, decay: 0.6 });
    this.events.emit('soundCue', { id: 'flare', label, intensity: 0.3 });
  }

  ui(kind: 'click' | 'confirm' | 'scan' | 'journal' | 'checkpoint' | 'warn'): void {
    if (!this.ctx) return;
    const ctx = this.ctx;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    const t0 = ctx.currentTime;
    const freq = { click: 900, confirm: 660, scan: 1320, journal: 520, checkpoint: 440, warn: 220 }[kind];
    o.type = kind === 'warn' ? 'square' : 'sine';
    o.frequency.setValueAtTime(freq, t0);
    if (kind === 'scan') o.frequency.exponentialRampToValueAtTime(1980, t0 + 0.18);
    if (kind === 'confirm' || kind === 'journal') o.frequency.setValueAtTime(freq * 1.5, t0 + 0.08);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(kind === 'warn' ? 0.05 : 0.07, t0 + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + (kind === 'scan' ? 0.25 : 0.16));
    o.connect(g).connect(this.buses.ui);
    o.start(t0);
    o.stop(t0 + 0.3);
  }

  temporalWhoosh(): void {
    this.burst({ type: 'bandpass', freq: 300, q: 0.7, gain: 0.35, attack: 0.6, decay: 1.4, freqEnd: 3200, reverb: 0.6 });
    this.events.emit('soundCue', { id: 'temporal', label: 'Temporal field', intensity: 0.4 });
  }

  creak(x: number, z: number, label = 'Timber creaking'): void {
    this.burst({ type: 'bandpass', freq: 380, q: 9, gain: 0.12, attack: 0.15, decay: 0.6, freqEnd: 300 });
    this.events.emit('soundCue', { id: 'creak', label, direction: this.directionTo(x, z), intensity: 0.4 });
  }

  dispose(): void {
    this.stopAllLoops();
    void this.ctx?.close();
    this.ctx = null;
  }
}
