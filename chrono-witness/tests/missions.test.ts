import { describe, it, expect } from 'vitest';
import { EventBus, type GameEvents } from '../src/core/Events';
import { FactStore } from '../src/missions/FactStore';
import { MissionSystem } from '../src/missions/MissionSystem';
import type { MissionDef } from '../src/missions/types';

const missions: MissionDef[] = [
  {
    id: 'main',
    title: 'Main',
    kind: 'main',
    summary: '',
    stages: [
      { id: 'a', title: 'A', objectives: [{ id: 'talk', text: 'Talk', complete: { flag: 'dlg.x.done' } }], onComplete: [{ giveItem: 'note' }], next: 'b' },
      {
        id: 'b',
        title: 'B',
        objectives: [
          { id: 'go', text: 'Go', complete: { flag: 'zone.z' }, fail: { flag: 'downed' } },
          { id: 'opt', text: 'Optional', optional: true, complete: { flag: 'extra' } },
        ],
      },
    ],
  },
  { id: 'side', title: 'Side', kind: 'optional', summary: '', availableWhen: { item: 'kit' }, stages: [{ id: 's', title: 'S', objectives: [{ id: 'n', text: 'n', complete: { count: { flags: ['scan.a', 'scan.b', 'scan.c'], atLeast: 2 } } }] }] },
];

function setup() {
  const ev = new EventBus<GameEvents>();
  const facts = new FactStore();
  const ms = new MissionSystem(facts, ev);
  facts.onChange = () => ms.evaluate();
  ms.load(missions);
  ms.start();
  return { ev, facts, ms };
}

describe('MissionSystem', () => {
  it('starts main missions active and optional ones unavailable', () => {
    const { ms } = setup();
    expect(ms.state.get('main')!.state).toBe('active');
    expect(ms.state.get('side')!.state).toBe('unavailable');
    expect(ms.currentObjective()!.objective.id).toBe('talk');
  });

  it('only advances when the condition fact is set by an action', () => {
    const { ms, facts } = setup();
    ms.evaluate();
    expect(ms.state.get('main')!.stage).toBe('a');
    facts.set('dlg.x.done');
    expect(ms.state.get('main')!.stage).toBe('b');
    expect(facts.hasItem('note')).toBe(true);
  });

  it('completes the mission when required objectives complete (optional not required)', () => {
    const { ms, facts } = setup();
    facts.set('dlg.x.done');
    facts.set('zone.z');
    expect(ms.state.get('main')!.state).toBe('completed');
  });

  it('fails the mission on a fail condition and restores from snapshot', () => {
    const { ms, facts } = setup();
    facts.set('dlg.x.done');
    const snap = ms.snapshot();
    const fsnap = facts.snapshot();
    facts.set('downed');
    expect(ms.state.get('main')!.state).toBe('failed');
    facts.restore(fsnap);
    ms.restore(snap);
    expect(ms.state.get('main')!.state).toBe('active');
    expect(ms.state.get('main')!.stage).toBe('b');
  });

  it('activates optional missions from conditions and counts progress', () => {
    const { ms, facts } = setup();
    facts.addItem('kit');
    expect(ms.state.get('side')!.state).toBe('active');
    facts.set('scan.a');
    expect(ms.state.get('side')!.state).toBe('active');
    facts.set('scan.c');
    expect(ms.state.get('side')!.state).toBe('completed');
  });
});

describe('FactStore', () => {
  it('evaluates nested conditions', () => {
    const f = new FactStore();
    f.set('a');
    f.addItem('x');
    expect(f.test({ all: [{ flag: 'a' }, { item: 'x' }, { notFlag: 'b' }] })).toBe(true);
    expect(f.test({ any: [{ flag: 'b' }, { flag: 'c' }] })).toBe(false);
  });
});
