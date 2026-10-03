import type { EventBus, GameEvents } from '../core/Events';
import type { FactStore } from './FactStore';
import type { Effect, MissionDef, MissionRuntimeState, ObjectiveDef, StageDef } from './types';

export interface EffectHandler {
  (effect: Effect): boolean; // return true if handled
}

/**
 * Runs mission state machines. Objectives complete only when their condition becomes true on the
 * fact store, which in turn only changes in response to player actions (interactions, zones,
 * dialogue choices, scans, items) or chapter scripts reacting to them.
 */
export class MissionSystem {
  readonly defs = new Map<string, MissionDef>();
  readonly state = new Map<string, MissionRuntimeState>();
  private evaluating = false;
  private dirty = false;
  /** Extra effect handlers registered by the chapter / game (checkpoint, artifact, event…). */
  externalEffects: EffectHandler | null = null;

  constructor(
    private readonly facts: FactStore,
    private readonly events: EventBus<GameEvents>,
  ) {}

  load(missions: MissionDef[]): void {
    this.defs.clear();
    this.state.clear();
    for (const m of missions) {
      this.defs.set(m.id, m);
      this.state.set(m.id, { state: 'unavailable', stage: null, objectives: {} });
    }
  }

  /** Activate main missions without conditions and evaluate everything. */
  start(): void {
    for (const m of this.defs.values()) {
      if (m.kind === 'main' && !m.availableWhen && this.state.get(m.id)!.state === 'unavailable') this.activate(m.id);
    }
    this.evaluate();
  }

  activate(id: string): void {
    const def = this.defs.get(id);
    const st = this.state.get(id);
    if (!def || !st || st.state !== 'unavailable') return;
    st.state = 'active';
    this.enterStage(def, def.stages[0]);
    this.events.emit('missionUpdated', { missionId: id });
    if (def.kind === 'optional') this.events.emit('notify', { text: `New task: ${def.title}`, kind: 'journal' });
  }

  private enterStage(def: MissionDef, stage: StageDef): void {
    const st = this.state.get(def.id)!;
    st.stage = stage.id;
    for (const o of stage.objectives) st.objectives[o.id] = 'active';
    this.runEffects(stage.onEnter);
  }

  fail(id: string, reason: string): void {
    const st = this.state.get(id);
    if (!st || st.state !== 'active') return;
    st.state = 'failed';
    st.failReason = reason;
    this.events.emit('missionUpdated', { missionId: id });
  }

  complete(id: string): void {
    const st = this.state.get(id);
    const def = this.defs.get(id);
    if (!st || !def || st.state === 'completed') return;
    st.state = 'completed';
    st.stage = null;
    this.events.emit('missionUpdated', { missionId: id });
    this.events.emit('notify', { text: `${def.kind === 'main' ? 'Mission' : 'Task'} complete: ${def.title}`, kind: 'journal' });
    this.runEffects(def.onComplete);
  }

  /** Re-evaluate all conditions. Safe to call often; re-entrant calls are coalesced. */
  evaluate(): void {
    if (this.evaluating) {
      this.dirty = true;
      return;
    }
    this.evaluating = true;
    let guard = 0;
    do {
      this.dirty = false;
      for (const def of this.defs.values()) this.evaluateMission(def);
    } while (this.dirty && ++guard < 20);
    this.evaluating = false;
  }

  private evaluateMission(def: MissionDef): void {
    const st = this.state.get(def.id)!;
    if (st.state === 'unavailable') {
      if (def.availableWhen && this.facts.test(def.availableWhen)) this.activate(def.id);
      return;
    }
    if (st.state !== 'active' || !st.stage) return;
    const stage = def.stages.find((s) => s.id === st.stage);
    if (!stage) return;
    let allRequired = true;
    for (const o of stage.objectives) {
      const os = st.objectives[o.id];
      if (os === 'active') {
        if (o.fail && this.facts.test(o.fail)) {
          st.objectives[o.id] = 'failed';
          this.events.emit('objectiveUpdated', { missionId: def.id, objectiveId: o.id });
          if (!o.optional) {
            this.fail(def.id, o.text);
            return;
          }
        } else if (this.facts.test(o.complete)) {
          st.objectives[o.id] = 'completed';
          this.events.emit('objectiveUpdated', { missionId: def.id, objectiveId: o.id });
          this.runEffects(o.onComplete);
        }
      }
      if (!o.optional && st.objectives[o.id] !== 'completed') allRequired = false;
    }
    if (allRequired) {
      this.runEffects(stage.onComplete);
      if (stage.next) {
        const next = def.stages.find((s) => s.id === stage.next);
        if (next) {
          // optional objectives left active in the old stage are carried over as inactive
          for (const o of stage.objectives) if (st.objectives[o.id] === 'active') st.objectives[o.id] = 'inactive';
          this.enterStage(def, next);
          this.events.emit('missionUpdated', { missionId: def.id });
          this.dirty = true;
          return;
        }
      }
      this.complete(def.id);
      this.dirty = true;
    }
  }

  runEffects(effects: Effect[] | undefined): void {
    if (!effects) return;
    for (const e of effects) this.runEffect(e);
  }

  runEffect(e: Effect): void {
    if (this.externalEffects?.(e)) return;
    if ('setFlag' in e) this.facts.set(e.setFlag, e.value ?? true);
    else if ('giveItem' in e) {
      if (this.facts.addItem(e.giveItem)) this.events.emit('itemAdded', { id: e.giveItem });
    } else if ('takeItem' in e) {
      if (this.facts.removeItem(e.takeItem)) this.events.emit('itemRemoved', { id: e.takeItem });
    } else if ('notify' in e) this.events.emit('notify', { text: e.notify, kind: e.kind ?? 'info' });
    else if ('activateMission' in e) this.activate(e.activateMission);
    else if ('completeMission' in e) this.complete(e.completeMission);
    else if ('failMission' in e) this.fail(e.failMission, e.reason);
  }

  // ---------------------------------------------------------------- queries for UI
  /** The current required objective of the first active main mission (for the HUD). */
  currentObjective(): { mission: MissionDef; objective: ObjectiveDef; stage: StageDef } | null {
    for (const def of this.defs.values()) {
      if (def.kind !== 'main') continue;
      const st = this.state.get(def.id)!;
      if (st.state !== 'active' || !st.stage) continue;
      const stage = def.stages.find((s) => s.id === st.stage)!;
      const o = stage.objectives.find((x) => !x.optional && st.objectives[x.id] === 'active');
      if (o) return { mission: def, objective: o, stage };
    }
    return null;
  }

  activeObjectives(): { mission: MissionDef; objective: ObjectiveDef; state: string }[] {
    const out: { mission: MissionDef; objective: ObjectiveDef; state: string }[] = [];
    for (const def of this.defs.values()) {
      const st = this.state.get(def.id)!;
      if (st.state !== 'active' || !st.stage) continue;
      const stage = def.stages.find((s) => s.id === st.stage)!;
      for (const o of stage.objectives) if (st.objectives[o.id] === 'active') out.push({ mission: def, objective: o, state: 'active' });
    }
    return out;
  }

  snapshot(): Record<string, MissionRuntimeState> {
    const o: Record<string, MissionRuntimeState> = {};
    for (const [k, v] of this.state) o[k] = structuredClone(v);
    return o;
  }

  restore(s: Record<string, MissionRuntimeState>): void {
    for (const [k, v] of Object.entries(s)) if (this.state.has(k)) this.state.set(k, structuredClone(v));
    for (const id of this.defs.keys()) this.events.emit('missionUpdated', { missionId: id });
  }
}
