/**
 * Adaptive quality: lowers render resolution when frame time exceeds the target, raises it again
 * when there is sustained headroom. Hysteresis and cooldowns prevent visible oscillation.
 */
export class AdaptiveQuality {
  private acc = 0;
  private frames = 0;
  private cooldown = 0;
  private goodStreak = 0;
  enabled = true;
  minScale = 0.6;

  constructor(
    private readonly getScale: () => number,
    private readonly setScale: (s: number) => void,
    public maxScale: number,
    public targetFps: number,
  ) {}

  update(frameMs: number, dt: number): void {
    if (!this.enabled) return;
    this.cooldown -= dt;
    this.acc += frameMs;
    this.frames++;
    if (this.acc < 1500) return; // evaluate every ~1.5 s
    const avg = this.acc / this.frames;
    this.acc = 0;
    this.frames = 0;
    if (this.cooldown > 0) return;
    const target = 1000 / this.targetFps;
    const s = this.getScale();
    if (avg > target * 1.12 && s > this.minScale) {
      this.setScale(Math.max(this.minScale, s - 0.08));
      this.cooldown = 2;
      this.goodStreak = 0;
    } else if (avg < target * 0.72 && s < this.maxScale) {
      if (++this.goodStreak >= 3) {
        this.setScale(Math.min(this.maxScale, s + 0.05));
        this.cooldown = 3;
        this.goodStreak = 0;
      }
    } else {
      this.goodStreak = 0;
    }
  }
}
