import type { MissionRuntimeState } from '../missions/types';
import { safeStorage } from '../core/Settings';

export interface CheckpointSnapshot {
  id: string;
  savedAt: string;
  flags: Record<string, boolean>;
  inventory: string[];
  missions: Record<string, MissionRuntimeState>;
  scanned: string[];
  journal: string[];
  /** Chapter-specific script state (e.g. which scripted events already ran). */
  script: Record<string, unknown>;
}

export interface ChapterProgress {
  status: 'not-started' | 'in-progress' | 'completed';
  checkpoint: CheckpointSnapshot | null;
  timesCompleted: number;
  bestTimeSec: number | null;
  playTimeSec: number;
  /** Optional tasks completed in any run (for the selector summary). */
  optionalDone: string[];
}

export interface SaveData {
  version: 1;
  createdAt: string;
  updatedAt: string;
  chapters: Record<string, ChapterProgress>;
  /** Artifacts recovered (shown in the headquarters gallery). */
  artifacts: string[];
  /** Historical record entries unlocked across all chapters. */
  records: string[];
  seenIntro: Record<string, boolean>;
}

const KEY = 'chrono-witness.save.v1';

export function emptySave(): SaveData {
  const now = new Date().toISOString();
  return { version: 1, createdAt: now, updatedAt: now, chapters: {}, artifacts: [], records: [], seenIntro: {} };
}

export function emptyProgress(): ChapterProgress {
  return { status: 'not-started', checkpoint: null, timesCompleted: 0, bestTimeSec: null, playTimeSec: 0, optionalDone: [] };
}

/**
 * Persistent progress in localStorage (falls back to memory when storage is unavailable).
 * Writes are versioned and validated so a corrupted save never prevents the game from starting.
 */
export class SaveSystem {
  data: SaveData;
  private storage = safeStorage();
  readonly persistent: boolean;

  constructor() {
    this.persistent = this.storage !== null;
    this.data = this.read() ?? emptySave();
  }

  private read(): SaveData | null {
    try {
      const raw = this.storage?.getItem(KEY);
      if (!raw) return null;
      const d = JSON.parse(raw) as SaveData;
      if (d.version !== 1 || typeof d.chapters !== 'object') return null;
      d.artifacts ??= [];
      d.records ??= [];
      d.seenIntro ??= {};
      return d;
    } catch {
      return null;
    }
  }

  write(): void {
    this.data.updatedAt = new Date().toISOString();
    try {
      this.storage?.setItem(KEY, JSON.stringify(this.data));
    } catch {
      /* quota / private mode — keep in memory */
    }
  }

  chapter(id: string): ChapterProgress {
    let p = this.data.chapters[id];
    if (!p) {
      p = emptyProgress();
      this.data.chapters[id] = p;
    }
    return p;
  }

  saveCheckpoint(chapterId: string, snap: CheckpointSnapshot): void {
    const p = this.chapter(chapterId);
    p.status = 'in-progress';
    p.checkpoint = snap;
    this.write();
  }

  completeChapter(chapterId: string, runTimeSec: number, optionalDone: string[], artifacts: string[], records: string[]): void {
    const p = this.chapter(chapterId);
    p.status = 'completed';
    p.timesCompleted++;
    p.checkpoint = null;
    p.bestTimeSec = p.bestTimeSec === null ? runTimeSec : Math.min(p.bestTimeSec, runTimeSec);
    for (const o of optionalDone) if (!p.optionalDone.includes(o)) p.optionalDone.push(o);
    for (const a of artifacts) if (!this.data.artifacts.includes(a)) this.data.artifacts.push(a);
    this.addRecords(records);
    this.write();
  }

  addRecords(ids: string[]): void {
    for (const r of ids) if (!this.data.records.includes(r)) this.data.records.push(r);
  }

  addArtifact(id: string): void {
    if (!this.data.artifacts.includes(id)) this.data.artifacts.push(id);
    this.write();
  }

  clearCheckpoint(chapterId: string): void {
    const p = this.chapter(chapterId);
    p.checkpoint = null;
    if (p.status === 'in-progress') p.status = p.timesCompleted > 0 ? 'completed' : 'not-started';
    this.write();
  }

  resetAll(): void {
    this.data = emptySave();
    this.write();
  }
}
