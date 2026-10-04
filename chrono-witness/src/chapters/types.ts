import type * as THREE from 'three';
import type { DialogueDef, ItemDef, JournalEntry, MissionDef, ScanEntry, SourceRef } from '../missions/types';

export interface CheckpointDef {
  label: string;
  position: [number, number, number];
  yaw: number;
}

export interface CinematicShot {
  /** Caption text (subtitled; never audio-only). */
  caption: string;
  kicker?: string;
  duration: number;
  /** Camera path for this shot (world space). */
  from?: { pos: [number, number, number]; look: [number, number, number] };
  to?: { pos: [number, number, number]; look: [number, number, number] };
}

export interface ArtifactDef {
  id: string;
  name: string;
  description: string;
  status: 'documented' | 'reconstruction' | 'fiction';
}

export interface ChapterConfig {
  id: string;
  /** Mission/chapter title. */
  title: string;
  destination: string;
  dateLabel: string;
  year: number;
  status: 'playable' | 'in-development';
  tagline: string;
  overview: string;
  contentNotes?: string;
  /** Outline of planned missions for chapters still in development (honest roadmap). */
  plannedMissions?: string[];
  missions: MissionDef[];
  dialogues: DialogueDef[];
  items: ItemDef[];
  journal: JournalEntry[];
  scans: ScanEntry[];
  sources: Record<string, SourceRef>;
  artifacts: ArtifactDef[];
  checkpoints: Record<string, CheckpointDef>;
  startCheckpoint: string;
  intro?: CinematicShot[];
  outro?: CinematicShot[];
  loadingFacts?: string[];
  /** Dynamic import of the runtime (keeps every era out of memory until selected). */
  load?: () => Promise<{ createRuntime: ChapterRuntimeFactory }>;
}

export interface LoadReporter {
  (fraction: number, label: string): void;
}

export type ChapterRuntimeFactory = (ctx: import('../core/GameContext').GameContext, config: ChapterConfig) => ChapterRuntime;

export interface ChapterRuntime {
  /** Build environment, NPCs, interactions. Report progress; throw only on unrecoverable errors. */
  build(report: LoadReporter): Promise<void>;
  /** Called after build and whenever a checkpoint is restored (positions NPCs/props for that state). */
  applyCheckpoint(id: string, script: Record<string, unknown>): void;
  update(dt: number, time: number): void;
  /** Serialisable script state stored with checkpoints. */
  scriptState(): Record<string, unknown>;
  /** Objects for shader precompilation. */
  readonly root: THREE.Object3D;
  /** Optional benchmark camera route (world-space points). */
  benchmarkRoutes?(): Record<string, { pos: THREE.Vector3; look: THREE.Vector3 }[]>;
  /** Ground height for spawning at (x, z) — avoids guessing heights in checkpoint data. */
  resolveSpawnHeight?(x: number, z: number): number;
  /** World y below which the player is considered lost (safety net returns them to safe ground). */
  readonly killY?: number;
  /** Optional cap for the camera far plane (fog/haze makes geometry beyond invisible). */
  readonly visibilityLimit?: number;
  /** Skip an intense scripted sequence while preserving mission progress. */
  skipSequence?(): void;
  dispose(): void;
}
