import type { WebGLRenderer } from 'three';

/**
 * Frame-time statistics: average FPS, 1% lows (from the 99th-percentile frame time),
 * spike counts and renderer resource metrics. Uses a preallocated ring buffer (no per-frame allocation).
 */
export class PerfStats {
  private readonly buf: Float32Array;
  private idx = 0;
  private count = 0;
  private scratch: Float32Array;
  totalFrames = 0;
  spikes = 0; // frames > 2.5× running median and > 25 ms
  private median = 16.7;

  constructor(capacity = 3600) {
    this.buf = new Float32Array(capacity);
    this.scratch = new Float32Array(capacity);
  }

  push(frameMs: number): void {
    this.buf[this.idx] = frameMs;
    this.idx = (this.idx + 1) % this.buf.length;
    if (this.count < this.buf.length) this.count++;
    this.totalFrames++;
    if (frameMs > 25 && frameMs > this.median * 2.5) this.spikes++;
    // cheap running median approximation
    this.median += Math.sign(frameMs - this.median) * 0.05 * Math.min(4, Math.abs(frameMs - this.median));
  }

  reset(): void {
    this.idx = 0;
    this.count = 0;
    this.totalFrames = 0;
    this.spikes = 0;
  }

  /** Summary over the most recent `window` frames (default all buffered). */
  summary(window = this.count): { frames: number; avgFps: number; avgMs: number; low1Fps: number; p99Ms: number; maxMs: number; spikes: number } {
    const n = Math.min(window, this.count);
    if (n === 0) return { frames: 0, avgFps: 0, avgMs: 0, low1Fps: 0, p99Ms: 0, maxMs: 0, spikes: 0 };
    let sum = 0;
    let max = 0;
    for (let i = 0; i < n; i++) {
      const v = this.buf[(this.idx - 1 - i + this.buf.length) % this.buf.length];
      this.scratch[i] = v;
      sum += v;
      if (v > max) max = v;
    }
    const sorted = this.scratch.subarray(0, n).sort();
    // 1% low = average of the slowest 1% of frames, expressed as FPS
    const k = Math.max(1, Math.floor(n * 0.01));
    let slow = 0;
    for (let i = n - k; i < n; i++) slow += sorted[i];
    const p99 = sorted[Math.min(n - 1, Math.floor(n * 0.99))];
    const avgMs = sum / n;
    return { frames: n, avgFps: 1000 / avgMs, avgMs, low1Fps: 1000 / (slow / k), p99Ms: p99, maxMs: max, spikes: this.spikes };
  }

  static resourceInfo(r: WebGLRenderer): { drawCalls: number; triangles: number; geometries: number; textures: number; programs: number; jsHeapMB: number | null } {
    const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory;
    return {
      drawCalls: r.info.render.calls,
      triangles: r.info.render.triangles,
      geometries: r.info.memory.geometries,
      textures: r.info.memory.textures,
      programs: r.info.programs?.length ?? 0,
      jsHeapMB: mem ? Math.round(mem.usedJSHeapSize / 1048576) : null,
    };
  }
}
