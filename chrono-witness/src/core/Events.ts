/** Minimal typed event bus. Handlers are stored per event key; emit never allocates arrays. */
export type Handler<T> = (payload: T) => void;

export class EventBus<EventMap extends object> {
  private handlers = new Map<keyof EventMap, Set<Handler<never>>>();

  on<K extends keyof EventMap>(type: K, handler: Handler<EventMap[K]>): () => void {
    let set = this.handlers.get(type);
    if (!set) {
      set = new Set();
      this.handlers.set(type, set);
    }
    set.add(handler as Handler<never>);
    return () => this.off(type, handler);
  }

  off<K extends keyof EventMap>(type: K, handler: Handler<EventMap[K]>): void {
    this.handlers.get(type)?.delete(handler as Handler<never>);
  }

  emit<K extends keyof EventMap>(type: K, payload: EventMap[K]): void {
    const set = this.handlers.get(type);
    if (!set) return;
    for (const h of set) (h as Handler<EventMap[K]>)(payload);
  }

  clear(): void {
    this.handlers.clear();
  }
}

/** Game-wide events. Gameplay systems communicate through these instead of direct references. */
export interface GameEvents {
  /** Player pressed interact on an interactable with this id. */
  interact: { id: string };
  /** Player entered a named trigger volume. */
  enterZone: { id: string };
  exitZone: { id: string };
  /** Player finished scanning an object. */
  scanned: { id: string };
  /** An item was added/removed from the inventory. */
  itemAdded: { id: string };
  itemRemoved: { id: string };
  /** A dialogue node with this id was reached / a choice was taken. */
  dialogueNode: { dialogue: string; node: string };
  dialogueEnded: { dialogue: string };
  /** Generic scripted flag set (used by chapter scripts and dialogue effects). */
  flag: { id: string; value: boolean };
  /** Mission state change notifications (for UI). */
  objectiveUpdated: { missionId: string; objectiveId: string };
  missionUpdated: { missionId: string };
  checkpoint: { id: string };
  /** The player was caught by a hazard and must retry from the last checkpoint. */
  playerDowned: { reason: string };
  /** Audio cue happened — UI shows a visual equivalent (accessibility). */
  soundCue: { id: string; label: string; direction?: number; intensity: number; danger?: boolean };
  subtitle: { speaker: string; text: string; duration: number };
  notify: { text: string; kind?: 'info' | 'journal' | 'item' | 'warning' | 'checkpoint' };
  settingsChanged: void;
}
