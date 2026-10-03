import type * as THREE from 'three';
import type { EventBus, GameEvents } from './Events';
import type { Settings } from './Settings';
import type { RenderSystem } from '../render/RenderSystem';
import type { CollisionWorld } from '../physics/CollisionWorld';
import type { Player } from '../player/Player';
import type { FirstPersonHands } from '../player/FirstPersonHands';
import type { NPCManager } from '../npc/NPCManager';
import type { NPC } from '../npc/NPC';
import type { CharacterLibrary } from '../npc/CharacterLibrary';
import type { InteractionSystem } from '../player/Interaction';
import type { MissionSystem } from '../missions/MissionSystem';
import type { FactStore } from '../missions/FactStore';
import type { AudioSystem } from '../audio/AudioSystem';
import type { Assets } from '../render/Assets';
import type { MaterialLibrary } from '../render/Materials';
import type { SaveSystem } from '../save/SaveSystem';
import type { Environment } from '../render/Environment';
import type { ResourceTracker } from '../render/Disposal';
import type { ChapterConfig, CinematicShot } from '../chapters/types';
import type { UI } from '../ui/UI';

/** Everything a chapter runtime may use. Chapters never reach into Game internals directly. */
export interface GameContext {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  render: RenderSystem;
  world: CollisionWorld;
  player: Player;
  hands: FirstPersonHands;
  npcs: NPCManager;
  characters: CharacterLibrary;
  interactions: InteractionSystem;
  missions: MissionSystem;
  facts: FactStore;
  events: EventBus<GameEvents>;
  settings: Settings;
  audio: AudioSystem;
  assets: Assets;
  materials: MaterialLibrary;
  save: SaveSystem;
  env: Environment;
  tracker: ResourceTracker;
  ui: UI;
  chapters: ChapterConfig[];

  startDialogue(id: string, npc?: NPC): void;
  checkpoint(id: string): void;
  downPlayer(reason: string): void;
  playCinematic(shots: CinematicShot[], onDone: () => void): void;
  completeChapter(): void;
  returnToHQ(): void;
  travelTo(chapterId: string, resume: boolean): void;
  setDanger(text: string | null, secondsLeft?: number): void;
  setMarker(id: string, pos: THREE.Vector3 | null, label?: string): void;
  /** Ask the player whether to experience or skip an intense scripted sequence. */
  confirmIntense(title: string, description: string): Promise<'play' | 'skip'>;
  readDocument(title: string, text: string): void;
  pause(showMenu?: boolean): void;
  resume(): void;
  openSelector(): void;
  readonly observing: boolean;
  /** World time scale (temporal observation slows the world). */
  readonly timeScale: number;
}
