import type { ChapterConfig } from '../types';

export const HQ_CONFIG: ChapterConfig = {
  id: 'hq',
  title: 'The Meridian Archive',
  destination: 'Temporal Headquarters',
  dateLabel: 'Present day',
  year: 2100,
  status: 'playable',
  tagline: 'Where every assignment begins and ends.',
  overview: 'The agency’s headquarters: destination console, artifact gallery and historical records.',
  missions: [
    {
      id: 'hq_orientation',
      title: 'Orientation',
      kind: 'main',
      summary: 'Meet the archivist and choose your first destination.',
      stages: [
        {
          id: 'meet',
          title: 'Meet the archivist',
          objectives: [
            { id: 'talk_quill', text: 'Speak with Dr. Mara Quill', detail: 'The archivist is waiting beside the temporal console in the centre of the hall.', complete: { flag: 'dlgdone.quill_intro' }, marker: 'quill' },
          ],
          next: 'console',
        },
        {
          id: 'console',
          title: 'Choose a destination',
          objectives: [
            { id: 'use_console', text: 'Choose a destination at the temporal console', detail: 'The console in front of the gate lists every destination. Only destinations marked Available can be visited.', complete: { flag: 'interact.hq_console' }, marker: 'console' },
            { id: 'see_gallery', text: 'Look at the artifact gallery', optional: true, complete: { flag: 'interact.hq_gallery' } },
            { id: 'see_records', text: 'Browse the historical records terminal', optional: true, complete: { flag: 'interact.hq_records' } },
          ],
        },
      ],
    },
  ],
  dialogues: [
    {
      id: 'quill_intro',
      entries: [{ condition: { flag: 'dlgdone.quill_intro' }, node: 'again' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Dr. Mara Quill', text: 'You made it. Welcome to the Meridian Archive. I catalogue what our witnesses bring back. Before your first assignment, you need to know the rules.', next: 'rules' },
        rules: {
          speaker: 'Dr. Mara Quill',
          text: 'You can help the people you meet. Their personal stories are yours to change. The great events around them are not. The battle, the raid, the eruption: those end the way the record says they ended.',
          choices: [
            { text: 'Why can’t I change them?', next: 'why' },
            { text: 'What does the device on my wrist do?', next: 'device' },
            { text: 'Understood. Where do I start?', next: 'start_where' },
          ],
        },
        why: { speaker: 'Dr. Mara Quill', text: 'Call it the anchor rule. Push on a documented event and the device drags you home. We witness and we help. We don’t rewrite.', next: 'rules2' },
        device: { speaker: 'Dr. Mara Quill', text: 'Q opens the scanner: aim at an object and hold E to record what’s known about it. F is observation mode. It slows your perception and shows echoes of recent moments, but it drains quickly. J opens your journal.', next: 'rules2' },
        rules2: {
          speaker: 'Dr. Mara Quill',
          text: 'One more thing. The journal marks every record as documented, reconstruction or fiction. Read those tags. Our reconstructions are careful guesses, not facts.',
          choices: [
            { text: 'What does the device on my wrist do?', next: 'device', condition: { notFlag: 'dlg.quill_intro.device' } },
            { text: 'Where do I start?', next: 'start_where' },
          ],
        },
        start_where: { speaker: 'Dr. Mara Quill', text: 'The console. Only one destination is calibrated so far: the Somme, autumn 1916. A runner’s errand on a rain-soaked front line. The other destinations are still being researched; you’ll see them listed as in development.', effects: [{ setFlag: 'quill.briefed' }] },
        again: { speaker: 'Dr. Mara Quill', text: 'The console is ready when you are. The gallery behind you fills as you bring records home.' },
      },
    },
  ],
  items: [],
  journal: [],
  scans: [],
  sources: {},
  artifacts: [],
  checkpoints: { hq_start: { label: 'Headquarters', position: [0, 0, 9], yaw: 0 } },
  startCheckpoint: 'hq_start',
  load: () => import('./HQRuntime'),
};
