/**
 * Data model for missions, dialogue, items and historical journal entries.
 * Everything here is plain serialisable data so chapters can be authored as configuration.
 */

/** Conditions are evaluated against the chapter's fact store (flags + inventory). */
export type Condition =
  | { flag: string }
  | { notFlag: string }
  | { item: string }
  | { count: { flags: string[]; atLeast: number } }
  | { all: Condition[] }
  | { any: Condition[] };

/** Effects run when stages/objectives complete, dialogue nodes are reached, etc. */
export type Effect =
  | { setFlag: string; value?: boolean }
  | { giveItem: string }
  | { takeItem: string }
  | { checkpoint: string }
  | { notify: string; kind?: 'info' | 'journal' | 'item' | 'warning' | 'checkpoint' }
  | { journal: string }
  | { activateMission: string }
  | { completeMission: string }
  | { failMission: string; reason: string }
  | { artifact: string }
  | { event: string };

export type MissionState = 'unavailable' | 'active' | 'completed' | 'failed';
export type ObjectiveState = 'inactive' | 'active' | 'completed' | 'failed';

export interface ObjectiveDef {
  id: string;
  text: string;
  /** Longer written instruction shown in the journal (accessibility: no audio-only info). */
  detail?: string;
  optional?: boolean;
  complete: Condition;
  fail?: Condition;
  /** World marker id shown as a subtle waypoint when markers are enabled. */
  marker?: string;
  /** Progress display: flags counted toward "n / total". */
  progress?: { flags: string[]; total: number };
  onComplete?: Effect[];
}

export interface StageDef {
  id: string;
  title: string;
  objectives: ObjectiveDef[];
  onEnter?: Effect[];
  onComplete?: Effect[];
  /** Id of the next stage; omitted = mission completes after this stage. */
  next?: string;
}

export interface MissionDef {
  id: string;
  title: string;
  kind: 'main' | 'optional';
  summary: string;
  /** When omitted, the mission starts active (main) or becomes active on activateMission. */
  availableWhen?: Condition;
  stages: StageDef[];
  onComplete?: Effect[];
}

export interface MissionRuntimeState {
  state: MissionState;
  stage: string | null;
  objectives: Record<string, ObjectiveState>;
  failReason?: string;
}

export interface DialogueChoice {
  text: string;
  next?: string;
  condition?: Condition;
  effects?: Effect[];
}

export interface DialogueNode {
  speaker: string;
  text: string;
  next?: string;
  choices?: DialogueChoice[];
  effects?: Effect[];
}

export interface DialogueDef {
  id: string;
  /** First matching entry picks the start node. */
  entries: { condition?: Condition; node: string }[];
  nodes: Record<string, DialogueNode>;
}

export interface ItemDef {
  id: string;
  name: string;
  description: string;
  kind: 'mission' | 'document' | 'supply' | 'tool';
  /** Optional readable text (documents). Fiction must be labelled in the text itself. */
  readable?: string;
}

export type HistoricalStatus = 'documented' | 'reconstruction' | 'fiction';

export interface SourceRef {
  title: string;
  publisher: string;
  url?: string;
  accessed?: string;
}

export interface JournalEntry {
  id: string;
  title: string;
  text: string;
  status: HistoricalStatus;
  sources?: string[];
  /** Entries unlocked from the start (chapter briefing) vs discovered in play. */
  initiallyKnown?: boolean;
}

export interface ScanEntry extends JournalEntry {
  /** Interaction target id of the object in the world. */
  target: string;
}
