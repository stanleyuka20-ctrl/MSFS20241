import type { ChapterConfig } from '../types';
import type { JournalEntry, ScanEntry, SourceRef } from '../../missions/types';
import history from '../../../docs/history/berlin_1945.json';
import { ANCHOR, CELLAR, FRONT, GAP } from './layout';

interface HistoryFile {
  sources: Record<string, SourceRef>;
  facts: { id: string; text: string; status: 'documented' | 'reconstruction' | 'fiction'; sources: string[] }[];
  scanEntries: { id: string; title: string; text: string; status: 'documented' | 'reconstruction' | 'fiction'; sources: string[] }[];
}
const H = history as unknown as HistoryFile;
const fact = (id: string, title: string, initiallyKnown = false): JournalEntry => {
  const f = H.facts.find((x) => x.id === id);
  if (!f) throw new Error(`missing fact ${id}`);
  return { id: `fact_${id}`, title, text: f.text, status: f.status, sources: f.sources, initiallyKnown };
};
/** Scanner entry → interactable id placed by the runtime. */
const SCAN_TARGETS: Record<string, string> = {
  scan_street_pump: 'obj_pump',
  scan_water_buckets: 'obj_buckets',
  scan_ration_card: 'obj_ration_cards',
  scan_kommandantura_notice: 'obj_litfass',
  scan_white_armband: 'obj_armband',
  scan_tram: 'obj_tram',
  scan_chalk_messages: 'obj_chalk',
  scan_volksempfaenger: 'obj_radio',
  scan_shelter_sign: 'obj_shelter_sign',
  scan_stirrup_pump: 'obj_stirrup_pump',
  scan_handcart: 'obj_handcart',
  scan_cyrillic_sign: 'obj_cyrillic',
  scan_coal_stove: 'obj_stove',
};
const scans: ScanEntry[] = H.scanEntries.filter((s) => SCAN_TARGETS[s.id]).map((s) => ({ ...s, target: SCAN_TARGETS[s.id] }));
const scanFlags = scans.map((s) => `scan.${s.id}`);

export const BERLIN45_CONFIG: ChapterConfig = {
  id: 'berlin_1945',
  title: 'Chalk',
  destination: 'Berlin after the surrender',
  dateLabel: 'Friday 18 May 1945',
  year: 1945,
  status: 'playable',
  tagline: 'Ten days after the surrender. No water in the taps, no post, and messages chalked on the ruins.',
  overview:
    'Berlin has surrendered and the war in Europe is over. On a fictional street in an inner district, the people of No. 12 live in their cellar. You fetch water from the street pump, find a message from a missing daughter among the chalk notes on a firewall, climb the broken stairs for a neighbour’s papers, collect new ration cards, help clear the children away from an unexploded shell and join neighbours clearing rubble from a doorway.',
  contentNotes: 'The aftermath of the battle for Berlin: ruins, hunger, an unexploded shell made safe by a controlled explosion (skippable). No violence is shown. Sexual violence and suicides of that time are not depicted.',
  loadingFacts: [
    'The Berlin garrison surrendered on 2 May 1945; Germany’s unconditional surrender was signed in Berlin-Karlshorst on 8 May. [documented]',
    'With the mains broken, Berlin’s old cast-iron street pumps were often the only source of water. [documented]',
    'A five-group ration system began on 15 May 1945. [documented]',
    'Radio Berlin went back on the air on 13 May 1945. [documented]',
  ],
  sources: H.sources,
  scans,
  journal: [
    { id: 'brief_fiction', title: 'About this assignment', text: 'Lindenhofstraße, No. 12, Frau Brandt and Peter, Herr Lenz and Lotte, Frau Kaminski, the clerk, the children, the sapper and the traffic regulator are inventions, and so are all missions. The setting follows the documented sources cited in each record. Where the research could not confirm a detail it is marked reconstruction.', status: 'fiction', initiallyKnown: true },
    fact('chapter_date', 'The date', true),
    fact('berlin_surrender', 'The surrender of Berlin', true),
    fact('german_surrender', 'The end of the war in Europe', true),
    fact('bombing_history', 'A city in ruins', true),
    fact('utilities_down', 'No water, gas or power', true),
    fact('street_pumps', 'Street pumps'),
    fact('boil_water_disease', 'Boiling water'),
    fact('queues', 'Queues'),
    fact('daily_struggles', 'Daily struggles'),
    fact('tenement_block', 'The Mietskaserne'),
    fact('women_majority', 'A city of women'),
    fact('bersarin', 'The city commandant'),
    fact('order_no1', 'Order No. 1'),
    fact('district_kommandantura', 'District commandant’s offices'),
    fact('magistrat', 'A new city government'),
    fact('white_armbands', 'White armbands'),
    fact('white_flags', 'White sheets'),
    fact('moscow_time_order', 'Moscow time'),
    fact('clocks_on_chapter_date', 'What the clocks said'),
    fact('old_cards_invalid', 'Old ration cards'),
    fact('provisional_rations', 'Temporary rations'),
    fact('ration_cards_13may', 'New ration cards'),
    fact('five_tier_system', 'Five ration groups'),
    fact('card_distribution', 'Handing out the cards'),
    fact('soup_kitchens_trade', 'Soup kitchens'),
    fact('radio_berlin', 'Radio Berlin'),
    fact('newspapers', 'Newspapers'),
    fact('transport_state', 'Trams and U-Bahn'),
    fact('tram_restart', 'Repairing the trams'),
    fact('truemmer_myth', 'Who cleared the rubble'),
    fact('women_obligation', 'Compulsory rubble work'),
    fact('bucket_chain_mid_may', 'Clearing in mid-May'),
    fact('suchdienst_origin', 'Searching for the missing'),
    fact('chalk_messages', 'Messages in chalk'),
    fact('unexploded_shells', 'Unexploded shells'),
    fact('curfew', 'Curfew'),
    fact('sexual_violence_context', 'What the game does not show'),
  ],
  items: [
    { id: 'buckets', name: 'Two zinc buckets', kind: 'tool', description: 'Frau Brandt’s buckets, dented but watertight.' },
    { id: 'water', name: 'Two buckets of water', kind: 'supply', description: 'From the street pump. Heavy: you cannot run or climb while carrying them.' },
    { id: 'papers', name: 'Tin box of papers', kind: 'document', description: 'Herr Lenz’s identity card, his household registration and old ration papers.' },
    { id: 'ration_cards', name: 'New ration cards', kind: 'document', description: 'Cards for Herr Lenz under the new system that began on 15 May.' },
  ],
  artifacts: [
    { id: 'b45_chalk', name: 'Chalked message (photograph, replica)', description: 'A replica photograph of a chalked message on a ruin wall. Such messages are widely described in memoirs; this one is fiction.', status: 'reconstruction' },
    { id: 'b45_card', name: 'Ration card, May 1945 (replica)', description: 'A replica of a Berlin food ration card from the new system of May 1945. A real one is held by the Museum Berlin-Karlshorst.', status: 'documented' },
  ],
  missions: [
    {
      id: 'chalk',
      title: 'Chalk',
      kind: 'main',
      summary: 'One day at No. 12: water, a message from a missing daughter, papers, ration cards, and the rubble.',
      stages: [
        { id: 'arrive', title: 'No. 12', onEnter: [{ activateMission: 'witness_b45' }], objectives: [{ id: 'talk_brandt', text: 'Find Frau Brandt in the courtyard of No. 12', detail: 'Go through the carriage gateway of No. 12 on the north side of the street.', complete: { flag: 'dlg.brandt.give' }, marker: 'brandt' }], onComplete: [{ checkpoint: 'yard' }, { journal: 'fact_street_pumps' }, { journal: 'fact_utilities_down' }], next: 'water' },
        { id: 'water', title: 'The pump', objectives: [{ id: 'pump', text: 'Queue at the street pump and fill the buckets', detail: 'The pump is on the south pavement to the east. Join the end of the queue and wait your turn, then hold E at the pump.', complete: { flag: 'event.water_pumped' }, marker: 'pump' }], onComplete: [{ journal: 'fact_queues' }], next: 'carry' },
        { id: 'carry', title: 'Down to the cellar', objectives: [{ id: 'carry', text: 'Carry the water down to the cellar of No. 12', detail: 'The cellar steps are in the courtyard, in front of the rear building. You cannot run while carrying the buckets.', complete: { flag: 'event.water_delivered' }, marker: 'cellar' }], onComplete: [{ checkpoint: 'cellar' }, { journal: 'fact_boil_water_disease' }], next: 'lenz' },
        { id: 'lenz', title: 'Herr Lenz', objectives: [{ id: 'talk_lenz', text: 'Talk to Herr Lenz in the cellar', complete: { flag: 'dlg.lenz.walls' }, marker: 'lenz' }], next: 'messages' },
        {
          id: 'messages',
          title: 'Messages',
          objectives: [
            { id: 'read', text: 'Read the messages chalked on the firewall at the west end of the street', detail: 'Where the houses have gone, the bare side wall of the next block faces the bombed gap.', complete: { flag: 'event.read_wall' }, marker: 'wall' },
            { id: 'write', text: 'Chalk Herr Lenz’s answer under Lotte’s message', complete: { flag: 'event.chalk_written' }, marker: 'wall' },
          ],
          onComplete: [{ journal: 'fact_chalk_messages' }, { journal: 'fact_suchdienst_origin' }],
          next: 'report',
        },
        { id: 'report', title: 'Good news', objectives: [{ id: 'tell_lenz', text: 'Tell Herr Lenz', complete: { flag: 'dlg.lenz.papers' }, marker: 'lenz' }], next: 'papers' },
        { id: 'papers', title: 'The broken stairs', objectives: [{ id: 'papers', text: 'Fetch the Lenz family papers from their flat on the second floor of the side wing', detail: 'Steps are missing on the stairs between the first and second floors. There are planks on the woodpile in the courtyard.', complete: { item: 'papers' }, marker: 'papers' }], onComplete: [{ checkpoint: 'papers' }, { journal: 'fact_tenement_block' }], next: 'cards' },
        {
          id: 'cards',
          title: 'Ration cards',
          objectives: [
            { id: 'office', text: 'Collect Herr Lenz’s new ration cards at the office in the school', detail: 'The school across the street is being used as the district ration-card office. Wait your turn in the corridor.', complete: { item: 'ration_cards' }, marker: 'office' },
            { id: 'give_cards', text: 'Bring the cards to Herr Lenz', complete: { flag: 'dlg.lenz.cards' }, marker: 'lenz' },
          ],
          onComplete: [{ checkpoint: 'office' }, { journal: 'fact_five_tier_system' }, { journal: 'fact_ration_cards_13may' }, { journal: 'fact_old_cards_invalid' }],
          next: 'shell',
        },
        {
          id: 'shell',
          title: 'The shell',
          objectives: [
            { id: 'kids', text: 'Send the children away from the shell', detail: 'They are in the bombed gap at the west end of the street.', complete: { count: { flags: ['event.kid_1', 'event.kid_2', 'event.kid_3'], atLeast: 3 } }, progress: { flags: ['event.kid_1', 'event.kid_2', 'event.kid_3'], total: 3 }, marker: 'shell' },
            { id: 'call', text: 'Tell the Soviet traffic regulator at the crossing', complete: { flag: 'event.sapper_called' }, marker: 'shell' },
            { id: 'cleared', text: 'Stay back while the sapper makes the shell safe', detail: 'Speak to the sapper when he arrives, then keep clear.', complete: { flag: 'event.shell_cleared' }, marker: 'shell' },
          ],
          onComplete: [{ checkpoint: 'shell' }, { journal: 'fact_unexploded_shells' }],
          next: 'chain',
        },
        { id: 'chain', title: 'The doorway', objectives: [{ id: 'chain', text: 'Join the neighbours clearing the rubble from the doorway of No. 10', detail: 'Stand in the chain and pass on each bucket as it reaches you.', complete: { flag: 'event.chain_done' }, marker: 'chain' }], onComplete: [{ journal: 'fact_bucket_chain_mid_may' }, { journal: 'fact_truemmer_myth' }], next: 'reunion' },
        { id: 'reunion', title: 'Sunday came early', objectives: [{ id: 'lotte', text: 'Go back to the cellar', detail: 'Someone has come to No. 12.', complete: { flag: 'dlg.lotte.end' }, marker: 'lenz' }], next: 'return' },
        { id: 'return', title: 'Recall', onEnter: [{ setFlag: 'zone.anchor', value: false }], objectives: [{ id: 'go_anchor', text: 'Return to the temporal anchor point', detail: 'The anchor is where you arrived, at the east end of the street.', complete: { flag: 'zone.anchor' }, marker: 'anchor' }] },
      ],
      onComplete: [{ artifact: 'b45_chalk' }, { artifact: 'b45_card' }, { event: 'chapter_complete' }],
    },
    {
      id: 'kettle',
      title: 'Frau Kaminski',
      kind: 'optional',
      summary: 'Old Frau Kaminski in the side wing cannot carry water herself.',
      availableWhen: { flag: 'dlg.kaminski.ask' },
      stages: [
        { id: 'fetch', title: 'Another trip', objectives: [{ id: 'fetch', text: 'Fill the buckets again at the pump', complete: { flag: 'event.kettle_pumped' } }], next: 'give' },
        { id: 'give', title: 'Water', objectives: [{ id: 'give', text: 'Bring the water to Frau Kaminski in the courtyard', complete: { flag: 'event.kaminski_water' } }] },
      ],
    },
    {
      id: 'firewood',
      title: 'Firewood',
      kind: 'optional',
      summary: 'There is no coal. Broken timber from the ruins will boil the water.',
      availableWhen: { flag: 'dlg.brandt.wood' },
      stages: [
        { id: 'gather', title: 'Gather', objectives: [{ id: 'wood', text: 'Collect 3 pieces of broken timber from the rubble of No. 10', complete: { count: { flags: ['event.wood_1', 'event.wood_2', 'event.wood_3'], atLeast: 3 } }, progress: { flags: ['event.wood_1', 'event.wood_2', 'event.wood_3'], total: 3 } }], next: 'stove' },
        { id: 'stove', title: 'The stove', objectives: [{ id: 'stove', text: 'Stack the wood by the stove in the cellar', complete: { flag: 'event.wood_delivered' } }] },
      ],
    },
    {
      id: 'witness_b45',
      title: 'Witness Record',
      kind: 'optional',
      summary: 'Record the street with the temporal scanner (Q, aim, hold E).',
      stages: [{ id: 'record', title: 'Record', objectives: [{ id: 'scan8', text: 'Record 8 historical objects with the scanner', complete: { count: { flags: scanFlags, atLeast: 8 } }, progress: { flags: scanFlags, total: 8 } }] }],
    },
  ],
  dialogues: [
    {
      id: 'brandt',
      entries: [
        { condition: { all: [{ flag: 'event.water_delivered' }, { notFlag: 'dlg.brandt.wood' }] }, node: 'wood' },
        { condition: { flag: 'event.water_delivered' }, node: 'after_water' },
        { condition: { flag: 'dlg.brandt.give' }, node: 'waiting' },
        { node: 'start' },
      ],
      nodes: {
        start: { speaker: 'Frau Brandt', text: 'You’re not from round here. Never mind, nobody is anymore. We’re all in the cellar since the front house came down.', choices: [{ text: 'Can I help?', next: 'help' }, { text: 'Is everyone all right?', next: 'everyone' }] },
        everyone: { speaker: 'Frau Brandt', text: 'Peter and me, yes. Herr Lenz from the side wing is with us. He has not heard from his Lotte since April. That eats at him more than the hunger.', next: 'help' },
        help: { speaker: 'Frau Brandt', text: 'There’s no water in the taps, not since April. The pump out on the street works, but the queue… If you could take the buckets and fetch some, I could cook.', next: 'give' },
        give: { speaker: 'Frau Brandt', text: 'Here. Bring it down to the cellar, the steps are by the rear house. Mind, it must be boiled.', effects: [{ giveItem: 'buckets' }] },
        waiting: { speaker: 'Frau Brandt', text: 'The pump is along the street, on the other side. Get in the queue and don’t let anyone push in.' },
        wood: { speaker: 'Frau Brandt', text: 'Water! Thank you. Now I need something to burn under it. No coal anywhere. There’s broken timber in the rubble next door.', effects: [{ setFlag: 'dlg.brandt.wood' }] },
        after_water: { speaker: 'Frau Brandt', text: 'Go and sit with Herr Lenz a moment. He’d like a new face to talk to.' },
      },
    },
    {
      id: 'lenz',
      entries: [
        { condition: { flag: 'event.lotte_arrived' }, node: 'reunited' },
        { condition: { all: [{ item: 'ration_cards' }, { notFlag: 'dlg.lenz.cards' }] }, node: 'cards' },
        { condition: { flag: 'dlg.lenz.cards' }, node: 'after_cards' },
        { condition: { all: [{ flag: 'event.chalk_written' }, { notFlag: 'dlg.lenz.papers' }] }, node: 'news' },
        { condition: { flag: 'dlg.lenz.papers' }, node: 'papers_wait' },
        { condition: { flag: 'dlg.lenz.walls' }, node: 'walls_wait' },
        { condition: { flag: 'event.water_delivered' }, node: 'start' },
        { node: 'early' },
      ],
      nodes: {
        early: { speaker: 'Herr Lenz', text: 'Frau Brandt is in the courtyard, if you are looking for her.' },
        start: { speaker: 'Herr Lenz', text: 'Water. Good. Sit a moment. My daughter Lotte was a telephonist in Steglitz. The last I heard was a card in April. Since then, nothing.', choices: [{ text: 'How can people find each other now?', next: 'how' }, { text: 'Where should I look?', next: 'walls' }] },
        how: { speaker: 'Herr Lenz', text: 'No post, no telephone, no trams. People write on the walls. Where a house has gone, the next one’s side wall stands bare, and everybody chalks on it. We are alive. We are at such and such.', next: 'walls' },
        walls: { speaker: 'Herr Lenz', text: 'There is a big wall like that at the west end of the street. My legs won’t climb over the rubble. Would you look for her name? Lotte Lenz.' },
        walls_wait: { speaker: 'Herr Lenz', text: 'The firewall at the west end. Lotte Lenz. And if there is nothing, write that I am here.' },
        news: { speaker: 'Herr Lenz', text: 'She is alive? She wrote it herself? Coming back on Sunday… Then I must be here, and I must eat until then. For that I need ration cards, and for the cards I need my papers.', next: 'papers' },
        papers: { speaker: 'Herr Lenz', text: 'My papers are in a tin box on the wardrobe in my flat, second floor of the side wing. The stairs are broken above the first floor. Be careful.' },
        papers_wait: { speaker: 'Herr Lenz', text: 'The tin box on the wardrobe. Second floor, side wing. Then the office in the school across the street.' },
        cards: { speaker: 'Herr Lenz', text: 'New cards. Group five, I suppose, an old man without work. Still. It is bread. Thank you.' },
        after_cards: { speaker: 'Herr Lenz', text: 'Sunday. I keep saying it to myself. Sunday.' },
        reunited: { speaker: 'Herr Lenz', text: 'She is here. She is really here. I don’t know how to thank you, so I won’t try.' },
      },
    },
    {
      id: 'clerk',
      entries: [{ condition: { item: 'ration_cards' }, node: 'done' }, { condition: { item: 'papers' }, node: 'start' }, { node: 'nopapers' }],
      nodes: {
        nopapers: { speaker: 'Clerk', text: 'Identity papers and the old registration, please. Without them I can’t issue anything.' },
        start: { speaker: 'Clerk', text: 'Lenz, Wilhelm, Lindenhofstraße 12. Pensioner. That is the lowest group, I’m afraid. Bread, a little fat, a little sugar.', choices: [{ text: 'Is that enough to live on?', next: 'enough' }, { text: 'Thank you.', next: 'issue' }] },
        enough: { speaker: 'Clerk', text: 'It is what there is. The soup kitchens help. People trade what they have left.', next: 'issue' },
        issue: { speaker: 'Clerk', text: 'Here are his cards. Don’t lose them; there are no duplicates. Next!', effects: [{ giveItem: 'ration_cards' }] },
        done: { speaker: 'Clerk', text: 'You have his cards. Next, please.' },
      },
    },
    {
      id: 'peter',
      entries: [{ condition: { flag: 'event.shell_cleared' }, node: 'after' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Peter', text: 'Mum says I’m not allowed in the ruins. The Krüger boys go everywhere. They found a helmet yesterday.' },
        after: { speaker: 'Peter', text: 'Did you hear the bang? Mum gave the Krüger boys such a telling-off.' },
      },
    },
    {
      id: 'regulator',
      entries: [{ condition: { flag: 'event.sapper_called' }, node: 'after' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Traffic regulator', text: 'Что? A shell? Where? (You point down the street to the bombed gap.)', next: 'call' },
        call: { speaker: 'Traffic regulator', text: 'Хорошо. I send for the sapper. Keep the people away from it. Понятно? Understood?', effects: [{ setFlag: 'event.sapper_called' }] },
        after: { speaker: 'Traffic regulator', text: 'The sapper is coming. Keep people back.' },
      },
    },
    {
      id: 'sapper',
      entries: [{ node: 'start' }],
      nodes: {
        start: { speaker: 'Soviet sapper', text: '(He looks at the shell for a long time, then at you.) Nicht anfassen. Do not touch. I blow it here. Everybody back, behind the tram.', next: 'ready' },
        ready: { speaker: 'Soviet sapper', text: 'Back! Further! Gut.' },
      },
    },
    {
      id: 'lotte',
      entries: [{ node: 'start' }],
      nodes: {
        start: { speaker: 'Lotte Lenz', text: 'I walked from Steglitz. Three days, with the bridges down. I went past the wall again today, just in case, and there it was in chalk: Vater lebt.', next: 'end' },
        end: { speaker: 'Lotte Lenz', text: 'Whoever wrote it for him, thank you.' },
      },
    },
    {
      id: 'kaminski',
      entries: [{ condition: { flag: 'event.kaminski_water' }, node: 'thanks' }, { condition: { flag: 'event.water_delivered' }, node: 'ask' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Frau Kaminski', text: 'Good day. You are helping Frau Brandt? She is a good woman.' },
        ask: { speaker: 'Frau Kaminski', text: 'You fetched water? I can’t stand in that queue any more, my knees. If you had a moment…', choices: [{ text: 'I’ll fetch you some.', next: 'yes' }, { text: 'Not now, sorry.' }] },
        yes: { speaker: 'Frau Kaminski', text: 'God bless you. Frau Brandt has the buckets.', effects: [{ setFlag: 'dlg.kaminski.ask' }] },
        thanks: { speaker: 'Frau Kaminski', text: 'Now I can wash. You don’t know what that means.' },
      },
    },
    {
      id: 'queue',
      entries: [{ node: 'start' }],
      nodes: { start: { speaker: 'Man in the queue', text: 'End of the line is behind me. Everybody waits, the same as everybody.' } },
    },
  ],
  checkpoints: {
    start: { label: 'Lindenhofstraße — arrival', position: [ANCHOR.x, 0, ANCHOR.z], yaw: Math.PI / 2 },
    yard: { label: 'No. 12, courtyard', position: [0, 0, -FRONT - 7], yaw: 0 },
    cellar: { label: 'Cellar steps', position: [CELLAR.stairX + 1.6, 0, CELLAR.stairZ0 + 1.6], yaw: 0 },
    papers: { label: 'Side wing', position: [3.5, 0, -27], yaw: -Math.PI / 2 },
    office: { label: 'Ration-card office', position: [0, 0, FRONT - 1.5], yaw: Math.PI },
    shell: { label: 'West end', position: [GAP.x1 + 8, 0, -FRONT + 1.5], yaw: Math.PI / 2 },
  },
  startCheckpoint: 'start',
  intro: [
    { kicker: 'Berlin · Friday 18 May 1945', caption: 'Ten days after the surrender. The guns are silent; there is no water in the taps, no post and no trams.', duration: 7, from: { pos: [60, 18, 12], look: [0, 6, -12] }, to: { pos: [44, 14, 10], look: [-10, 5, -14] } },
    { kicker: 'Lindenhofstraße', caption: 'A fictional street in an inner district. The people of No. 12 live in the cellar.', duration: 6.5, from: { pos: [46, 1.7, 1], look: [10, 2, -6] }, to: { pos: [40, 1.7, 0], look: [0, 3, -9] } },
  ],
  outro: [
    { kicker: 'Berlin · summer 1945', caption: 'The trams returned line by line; dysentery and typhus came with the summer heat. Messages on the walls stayed for months.', duration: 7, from: { pos: [0, 8, 14], look: [0, 6, -12] }, to: { pos: [-20, 10, 16], look: [-36, 4, -14] } },
    { kicker: 'History unchanged', caption: 'Everyone you met at No. 12 is fiction. What the city went through is not.', duration: 6.5, from: { pos: [40, 30, 30], look: [0, 0, -10] }, to: { pos: [50, 36, 40], look: [0, 0, -14] } },
  ],
  load: () => import('./BerlinRuntime'),
};
