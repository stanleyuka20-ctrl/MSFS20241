import type { ChapterConfig } from '../types';
import type { JournalEntry, ScanEntry, SourceRef } from '../../missions/types';
import history from '../../../docs/history/london_blitz_1940.json';
import { WARDEN_POST, STATION } from './layout';

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
const SCAN_TARGETS: Record<string, string> = {
  scan_warden_helmet: 'obj_warden_helmet',
  scan_stirrup_pump: 'obj_stirrup_pump',
  scan_incendiary: 'obj_incendiary',
  scan_redhill: 'obj_redhill',
  scan_gasmask_box: 'obj_gasmask_box',
  scan_anderson: 'obj_anderson',
  scan_taped_windows: 'obj_taped_window',
  scan_blackout_lamppost: 'obj_lamppost',
  scan_arp_post: 'obj_arp_post',
  scan_tube_shelter: 'obj_tube_shelter',
  scan_first_aid_post: 'obj_first_aid_post',
  scan_ration_book: 'obj_ration_book',
  scan_afs_pump: 'obj_afs_pump',
};
// static water tanks were mostly built in 1941–42 and are left out of this street (see research notes)
const scans: ScanEntry[] = H.scanEntries.filter((s) => SCAN_TARGETS[s.id]).map((s) => ({ ...s, target: SCAN_TARGETS[s.id] }));
const scanFlags = scans.map((s) => `scan.${s.id}`);

export const LONDON_CONFIG: ChapterConfig = {
  id: 'london_blitz_1940',
  title: 'Blackout',
  destination: 'London during the Blitz',
  dateLabel: 'Late September 1940',
  year: 1940,
  status: 'playable',
  tagline: 'The siren goes at dusk. The street has to be emptied before the bombers come.',
  overview:
    'In September 1940 London was bombed night after night. On a fictional terraced street in the East End near the burning docks, you help a volunteer air raid warden through one long night: guiding a family to the Underground shelter, putting out incendiaries, finding a deaf neighbour after his house is hit, opening a way for the Heavy Rescue party, and carrying supplies, until the "Raiders Passed" signal at dawn.',
  contentNotes: 'Air raid at night with bomb explosions and fires; a trapped elderly civilian is rescued. No graphic injuries. The bomb-strike sequence can be skipped while keeping progress.',
  loadingFacts: [
    'London was bombed on 57 consecutive nights from 7 September 1940. [documented]',
    'In September 1940 the official name was still ARP (Air Raid Precautions); "Civil Defence" came in 1941. [documented]',
    'The government at first discouraged sheltering in the Underground, then accepted it. In September 1940 there were no bunks yet. [documented]',
    'Incendiary bombs were smothered with sand, or tackled with stirrup pumps. [documented]',
  ],
  sources: H.sources,
  scans,
  journal: [
    { id: 'brief_fiction', title: 'About this assignment', text: 'Cable Row, Morley Road station, the warden, the Hartley family, Mr Moss, the rescue party and the nurse are inventions. The setting (the autumn 1940 night raids, ARP services, blackout, incendiary drill, Tube sheltering and rescue work) is based on the documented sources cited in each record.', status: 'fiction', initiallyKnown: true },
    fact('blitz_dates', 'The Blitz', true),
    fact('blitz_bombs', 'High explosive and incendiaries', true),
    fact('term_arp', 'ARP, not yet "Civil Defence"', true),
    fact('terraces', 'East End terraces', true),
    fact('docks_poverty', 'The docks', true),
    fact('warden_duties', 'Air raid wardens'),
    fact('warden_helmet', 'The warden’s helmet'),
    fact('warden_kit', 'Warden kit'),
    fact('warden_posts', 'Wardens’ posts'),
    fact('women_wardens', 'Women wardens'),
    fact('signals', 'Siren signals'),
    fact('signals_correction', '“Raiders Passed”'),
    fact('blackout', 'The blackout'),
    fact('incendiary', 'Incendiary bombs'),
    fact('incendiary_drill', 'Dealing with incendiaries'),
    fact('fire_watching', 'Fire-watching in 1940'),
    fact('afs', 'The Auxiliary Fire Service'),
    fact('heavy_rescue', 'Heavy Rescue'),
    fact('rescue_silence', 'Listening for the trapped'),
    fact('under_stairs', 'Under the stairs'),
    fact('anderson', 'Anderson shelters'),
    fact('anderson_east_end', 'Small yards, public shelters'),
    fact('tube_policy', 'Sheltering in the Tube'),
    fact('tube_numbers', '120,000 underground'),
    fact('tube_conditions', 'Platforms in September 1940'),
    fact('first_aid', 'Casualty services'),
    fact('wvs_canteen', 'WVS canteens'),
    fact('gas_masks', 'Gas masks'),
    fact('window_tape', 'Taped windows'),
    fact('rationing', 'Rationing'),
    fact('business_as_usual', 'Business as usual'),
  ],
  items: [
    { id: 'sand_bucket', name: 'Bucket of sand and scoop', kind: 'tool', description: 'From the warden’s post: dry sand to smother incendiary bombs before they take hold.' },
    { id: 'gasmask_box', name: 'Joan’s gas-mask box', kind: 'supply', description: 'A cardboard box on a string, with JOAN H. written on the lid.' },
    { id: 'dressings', name: 'Box of dressings', kind: 'supply', description: 'Field dressings, splints and blankets from the ARP depot, for the First Aid Post nurse at the incident.' },
    { id: 'tea', name: 'Mugs of tea', kind: 'supply', description: 'Hot sweet tea from the WVS canteen van, for the rescue party.' },
  ],
  artifacts: [
    { id: 'ldn_log_page', name: 'Warden’s log page (replica)', description: 'A page in the style of a wardens’ post log book, with the night’s incidents. The log-book practice is documented; the entries are fiction.', status: 'fiction' },
    { id: 'ldn_w_helmet', name: 'Black warden’s helmet with white “W” (replica)', description: 'Wardens’ helmets were painted black with white lettering from August 1939.', status: 'documented' },
  ],
  missions: [
    {
      id: 'blackout',
      title: 'Blackout',
      kind: 'main',
      summary: 'One night on Cable Row: get people to shelter, find the missing, and see the street through to the “Raiders Passed”.',
      stages: [
        {
          id: 'report',
          title: 'The siren',
          onEnter: [{ activateMission: 'witness_ldn' }],
          objectives: [{ id: 'talk_pike', text: 'Report to Warden Pike at the ARP post', detail: 'The sandbagged warden’s post is at the corner of Cable Row and Dock Lane, on the north pavement.', complete: { flag: 'dlg.pike.give' }, marker: 'pike' }],
          onComplete: [{ checkpoint: 'post' }, { journal: 'fact_warden_duties' }, { journal: 'fact_women_wardens' }, { journal: 'fact_signals' }],
          next: 'family',
        },
        {
          id: 'family',
          title: 'The Hartleys',
          objectives: [
            { id: 'knock', text: 'Knock at No. 9 and fetch the Hartleys', detail: 'No. 9 is on the north side of Cable Row, west of the warden’s post.', complete: { flag: 'dlg.ivy.go' }, marker: 'n9' },
            { id: 'gasmask', text: 'Find Joan’s gas-mask box in the front room', detail: 'Ivy won’t leave without it. It is somewhere in the front room of No. 9.', complete: { item: 'gasmask_box' }, marker: 'gasmask' },
          ],
          next: 'escort',
        },
        {
          id: 'escort',
          title: 'To the shelter',
          objectives: [
            { id: 'incendiaries', text: 'Smother the incendiaries on the street', detail: 'Incendiary bombs are burning on the road. Hold E at each with the sand bucket. The family waits in a doorway.', complete: { count: { flags: ['event.incendiary_a', 'event.incendiary_b'], atLeast: 2 } }, progress: { flags: ['event.incendiary_a', 'event.incendiary_b'], total: 2 }, fail: { flag: 'event.fire_spread' } },
            { id: 'shelter', text: 'Lead the Hartleys down to the platform at Morley Road station', detail: 'North up Dock Lane to the High Street. The station entrance is on the north side; the shelterers are on the platform below.', complete: { flag: 'event.family_sheltered' }, marker: 'station' },
          ],
          onComplete: [{ checkpoint: 'station' }, { journal: 'fact_tube_policy' }, { journal: 'fact_tube_conditions' }, { journal: 'fact_tube_numbers' }],
          next: 'moss',
        },
        {
          id: 'moss',
          title: 'Mr Moss',
          objectives: [{ id: 'find_moss', text: 'Go back to Cable Row and check on Mr Moss at No. 14', detail: 'Ivy says Mr Moss at No. 14 (south side) is deaf and never hears the siren.', complete: { flag: 'event.moss_located' }, marker: 's14' }],
          onComplete: [{ checkpoint: 'incident' }, { journal: 'fact_under_stairs' }],
          next: 'route',
        },
        {
          id: 'route',
          title: 'A way through',
          objectives: [
            { id: 'tell_pike', text: 'Report the incident to Warden Pike', complete: { flag: 'dlg.pike.incident' }, marker: 'pike' },
            { id: 'gate', text: 'Open the back-alley gate so the rescue party can get round the crater', detail: 'Dock Lane is blocked by a crater and a burst main. Their lorry is beyond it. The south back alley has a gate in its far wall, east of Dock Lane: clear the fallen bricks and draw the bolt.', complete: { flag: 'event.gate_open' }, marker: 'gate' },
          ],
          onComplete: [{ journal: 'fact_heavy_rescue' }],
          next: 'supplies',
        },
        {
          id: 'supplies',
          title: 'Dressings',
          objectives: [{ id: 'dressings', text: 'Carry dressings from the ARP depot to the nurse at No. 14', detail: 'The depot is at the west end of Cable Row, north side. The box is heavy: you can’t run while carrying it.', complete: { flag: 'event.dressings_delivered' }, marker: 'depot' }],
          onComplete: [{ checkpoint: 'rescue' }, { journal: 'fact_first_aid' }],
          next: 'listen',
        },
        {
          id: 'listen',
          title: 'Silence',
          objectives: [{ id: 'locate', text: 'During the silence, find where the tapping comes from', detail: 'Mr Carver calls for silence. Stand still and watch for the tapping marks, then point out the spot (E) where it is strongest.', complete: { flag: 'event.tapping_located' } }],
          onComplete: [{ journal: 'fact_rescue_silence' }],
          next: 'free',
        },
        {
          id: 'free',
          title: 'Dawn',
          objectives: [{ id: 'help_dig', text: 'Help the rescue party reach Mr Moss', detail: 'Pass timbers to the rescuers (E at the timber pile) while they tunnel in.', complete: { flag: 'event.moss_freed' }, marker: 'timber' }],
          onComplete: [{ journal: 'fact_signals_correction' }, { journal: 'fact_business_as_usual' }],
          next: 'return',
        },
        {
          id: 'return',
          title: 'Recall',
          onEnter: [{ setFlag: 'zone.anchor', value: false }],
          objectives: [{ id: 'go_anchor', text: 'Return to the temporal anchor point', detail: 'The anchor is where you arrived, at the west end of Cable Row.', complete: { flag: 'zone.anchor' }, marker: 'anchor' }],
        },
      ],
      onComplete: [{ artifact: 'ldn_log_page' }, { artifact: 'ldn_w_helmet' }, { event: 'chapter_complete' }],
    },
    {
      id: 'firewatch',
      title: 'Fire-Watch',
      kind: 'optional',
      summary: 'Fire-watching was voluntary in 1940. More incendiaries have fallen in the back yards: put them out before they set a house alight.',
      availableWhen: { flag: 'item.sand_bucket' },
      stages: [{ id: 'yards', title: 'Yards', objectives: [{ id: 'yard_fires', text: 'Smother 3 incendiaries in the back yards', complete: { count: { flags: ['event.yard_fire_1', 'event.yard_fire_2', 'event.yard_fire_3'], atLeast: 3 } }, progress: { flags: ['event.yard_fire_1', 'event.yard_fire_2', 'event.yard_fire_3'], total: 3 } }] }],
      onComplete: [{ journal: 'fact_fire_watching' }],
    },
    {
      id: 'tea',
      title: 'Strong and Sweet',
      kind: 'optional',
      summary: 'The WVS canteen van on the High Street is serving tea. The rescue party could use some.',
      availableWhen: { flag: 'event.gate_open' },
      stages: [
        { id: 'fetch', title: 'Fetch', objectives: [{ id: 'get_tea', text: 'Collect tea from the WVS canteen on the High Street', complete: { item: 'tea' } }], next: 'give' },
        { id: 'give', title: 'Give', objectives: [{ id: 'give_tea', text: 'Bring the tea to the rescue party at No. 14', complete: { flag: 'event.tea_given' } }] },
      ],
      onComplete: [{ journal: 'fact_wvs_canteen' }],
    },
    {
      id: 'witness_ldn',
      title: 'Witness Record',
      kind: 'optional',
      summary: 'Record the street with the temporal scanner (Q, aim, hold E).',
      stages: [{ id: 'record', title: 'Record', objectives: [{ id: 'scan8', text: 'Record 8 historical objects with the scanner', complete: { count: { flags: scanFlags, atLeast: 8 } }, progress: { flags: scanFlags, total: 8 } }] }],
    },
  ],
  dialogues: [
    {
      id: 'pike',
      entries: [
        { condition: { all: [{ flag: 'event.moss_located' }, { notFlag: 'dlg.pike.incident' }] }, node: 'incident' },
        { condition: { flag: 'dlg.pike.incident' }, node: 'incident_after' },
        { condition: { flag: 'dlg.pike.give' }, node: 'after' },
        { node: 'start' },
      ],
      nodes: {
        start: { speaker: 'Warden Pike', text: 'There you are. You’re the volunteer from Stepney? Good. That’s the warning, the warbling one. They’ll be over the docks again inside the hour.', choices: [
          { text: 'Tell me what to do.', next: 'task' },
          { text: 'How do you know where they’re headed?', next: 'docks' },
        ] },
        docks: { speaker: 'Warden Pike', text: 'Every night since the seventh it’s been the docks. And when they miss the docks, they hit us.', next: 'task' },
        task: { speaker: 'Warden Pike', text: 'The Hartleys at No. 9: Ivy and the two kiddies. Their yard’s too small for an Anderson, and I want them down Morley Road station before the bombs start. Knock them up and take them.', next: 'give' },
        give: { speaker: 'Warden Pike', text: 'And take this, a bucket of sand and the scoop. If an incendiary comes down, smother it quick, before it gets into a house. Don’t you dare throw water on it.', effects: [{ giveItem: 'sand_bucket' }], choices: [{ text: 'Why not water?', next: 'water' }, { text: 'Right. No. 9.' }] },
        water: { speaker: 'Warden Pike', text: 'A jet of water on a burning one makes it spit and flare. Sand first, or a stirrup pump with a spray. Go on.' },
        after: { speaker: 'Warden Pike', text: 'No. 9, then the station. Keep the little ones close.' },
        incident: { speaker: 'Warden Pike', text: 'No. 14? Oh, Albert. He’s under the stairs, you say, and tapping? Then he’s alive. I’ve sent for Heavy Rescue, but their lorry’s stuck the far side of that crater on Dock Lane.', choices: [{ text: 'Is there another way round?', next: 'way' }] },
        way: { speaker: 'Warden Pike', text: 'The back alley. There’s a gate through to the bombed ground behind, past Dock Lane, but it’s been bolted since a chimney came down on it. Open it up and I’ll send them round.', effects: [{ setFlag: 'dlg.pike.incident' }] },
        incident_after: { speaker: 'Warden Pike', text: 'The alley gate, east of Dock Lane, in the far wall. Quick as you can.' },
      },
    },
    {
      id: 'ivy',
      entries: [{ condition: { flag: 'dlg.ivy.go' }, node: 'after' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Ivy Hartley', text: 'Is it Mrs Pike sent you? We were just going. Joan, Billy, coats on. Joan! Where’s your gas mask?', next: 'mask' },
        mask: { speaker: 'Joan', text: 'It’s in the front room, Mum. I think.', next: 'ivy2' },
        ivy2: { speaker: 'Ivy Hartley', text: 'Would you fetch it, love? My hands are full with this one. We’ll be on the step.', effects: [{ setFlag: 'dlg.ivy.go' }] },
        after: { speaker: 'Ivy Hartley', text: 'Front room, by the sideboard I should think. Then we’ll go.' },
      },
    },
    {
      id: 'ivy_station',
      entries: [{ node: 'start' }],
      nodes: {
        start: { speaker: 'Ivy Hartley', text: 'Thank you. We’ll be all right down here, squashed as it is. Oh, Mr Moss! At No. 14. He’s deaf as a post, he’ll never have heard the siren. Would you look in on him?', effects: [{ setFlag: 'event.ivy_asked' }] },
      },
    },
    {
      id: 'moss_tap',
      entries: [{ node: 'start' }],
      nodes: {
        start: { speaker: 'You', text: 'Mr Moss? Can you hear me? A faint tapping answers from under the fallen stairs. He can’t hear me, but he’s alive.', effects: [{ setFlag: 'event.moss_located' }] },
      },
    },
    {
      id: 'carver',
      entries: [{ condition: { flag: 'event.moss_freed' }, node: 'done' }, { condition: { flag: 'event.tapping_located' }, node: 'dig' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Mr Carver (Heavy Rescue)', text: 'You opened that gate? Good work. Right: before we touch anything we listen. Everybody quiet!', next: 'silence' },
        silence: { speaker: 'Mr Carver (Heavy Rescue)', text: 'Silence, please! Watch the rubble. Where he’s tapping, that’s where we go in. Point me to it.', effects: [{ setFlag: 'event.silence' }] },
        dig: { speaker: 'Mr Carver (Heavy Rescue)', text: 'Under the stairs, like the leaflet said. Clever old boy. Pass us timbers from the pile as we go. We shore up as we tunnel.' },
        done: { speaker: 'Mr Carver (Heavy Rescue)', text: 'Out he comes. Dusty and cross, and asking for his teeth. That’s the best sort.' },
      },
    },
    {
      id: 'nurse',
      entries: [{ node: 'start' }],
      nodes: {
        start: { speaker: 'Nurse Bright', text: 'Dressings? Bless you. Put them down by me. I’ll want them when they get him out.' },
      },
    },
    {
      id: 'wvs',
      entries: [{ condition: { item: 'tea' }, node: 'has' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'WVS volunteer', text: 'Tea for the rescue boys? Here you are, four mugs, strong and sweet. Mind, it’s hot.', effects: [{ giveItem: 'tea' }] },
        has: { speaker: 'WVS volunteer', text: 'Get it to them while it’s hot, dear.' },
      },
    },
    {
      id: 'moss',
      entries: [{ node: 'start' }],
      nodes: {
        start: { speaker: 'Mr Moss', text: 'Hm? You’ll have to speak up. Everyone kept saying under the stairs, so under the stairs I went. Is the kettle all right?' },
      },
    },
  ],
  checkpoints: {
    start: { label: 'Cable Row — arrival', position: [-46, 0, -1], yaw: -Math.PI / 2 },
    post: { label: 'Warden’s post', position: [WARDEN_POST.x + 4.7, 0, -1.5], yaw: 0.56 },
    station: { label: 'Morley Road station', position: [STATION.x, 0, STATION.z + STATION.d / 2 + 2.4], yaw: Math.PI },
    incident: { label: 'No. 14', position: [-27.5, 0, 1.6], yaw: Math.PI },
    rescue: { label: 'Rescue at No. 14', position: [-24.2, 0, 2.6], yaw: Math.PI * 0.8 },
  },
  startCheckpoint: 'start',
  intro: [
    { kicker: 'London · September 1940', caption: 'For weeks the bombers have come every night. Tonight the siren sounds at dusk over the East End.', duration: 7, from: { pos: [-55, 16, 18], look: [10, 2, -10] }, to: { pos: [-40, 12, 14], look: [20, 2, -20] } },
    { kicker: 'Cable Row', caption: 'A fictional street of terraces near the docks. Blackout curtains are drawn. The warden’s post is on the corner.', duration: 6.5, from: { pos: [-48, 1.7, -1], look: [0, 1.6, -2] }, to: { pos: [-44, 1.7, -1], look: [10, 1.6, -3] } },
  ],
  outro: [
    { kicker: 'Dawn', caption: 'The steady note of the “Raiders Passed”. On the morning after, shops put up “Business as Usual” notices among the broken glass.', duration: 7, from: { pos: [-20, 6, 6], look: [0, 1, -2] }, to: { pos: [-28, 8, 8], look: [5, 1, -4] } },
    { kicker: 'London · 1940–41', caption: 'The documented history is unchanged. The raids went on until May 1941. Everyone you met tonight is fiction.', duration: 7, from: { pos: [0, 20, 20], look: [20, 0, -20] }, to: { pos: [10, 26, 30], look: [20, 0, -30] } },
  ],
  load: () => import('./LondonRuntime'),
};
