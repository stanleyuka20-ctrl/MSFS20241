import type { ChapterConfig } from '../types';
import type { JournalEntry, ScanEntry, SourceRef } from '../../missions/types';
import history from '../../../docs/history/ww1_somme_1916.json';
import { ANCHOR, SUPPORT_Z } from './layout';

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

/** Scanner targets: scan entry id → world object id (placed by the runtime). */
const SCAN_TARGETS: Record<string, string> = {
  scan_brodie_helmet: 'obj_helmet',
  scan_duckboard: 'obj_duckboard',
  scan_field_telephone: 'obj_telephone',
  scan_message_form: 'obj_message_pad',
  scan_periscope: 'obj_periscope',
  scan_sandbag_parapet: 'obj_parapet',
  scan_ph_helmet: 'obj_gas_helmet',
  scan_screw_picket: 'obj_picket',
  scan_stretcher: 'obj_stretcher',
  scan_rap: 'obj_rap',
  scan_gas_curtain: 'obj_gas_curtain',
  scan_very_pistol: 'obj_very_pistol',
  scan_corrugated_revetment: 'obj_revetment',
  scan_rum_jar: 'obj_rum_jar',
};

const scans: ScanEntry[] = H.scanEntries.map((s) => ({ ...s, target: SCAN_TARGETS[s.id] ?? s.id }));
const scanFlags = scans.map((s) => `scan.${s.id}`);

const MESSAGE_TEXT = `ARMY FORM C.2121 — MESSAGES AND SIGNALS
(Game fiction: the unit, names and contents below are invented.)

TO:   O.C. "B" Coy, CHEAPSIDE
FROM: Adjt.

Sender's number: B.47      Day of month: 18

Relief by "D" Coy postponed 24 hours owing to state of
tracks. Ration party will come up PALL MALL at dusk.
Report on condition of trench and wire by 0600.

Telephone line to your H.Q. reported cut.
Acknowledge by runner.`;

const DIARY_TEXT = `(Game fiction — a pocket diary belonging to the invented character Pte D. Whitlow.)

"Property of Pte. D. Whitlow, B Coy. If found please return."

Oct 15 — Rain again. Mud up past the puttees in Fleet St. Got a parcel from Mum — socks, a cake gone to crumbs, and a letter from our Ellen about the allotment.

Oct 17 — Up to Cheapside tonight. Tom Avery says the trick with mud is to keep moving and never stand still long enough for it to know you're there. Wrote to Ellen. Didn't say much about here. What would I say?`;

export const WW1_CONFIG: ChapterConfig = {
  id: 'ww1_somme_1916',
  title: 'The Runner',
  destination: 'Western Front — Somme sector',
  dateLabel: 'October 1916',
  year: 1916,
  status: 'playable',
  tagline: 'Telephone lines are cut. A message must go forward on foot.',
  overview:
    'Autumn rain has turned the Somme battlefield to mud. In a fictional British company sector, the telephone line to the front line has been cut and a message must go forward by runner. You will move through support and communication trenches, live through a bombardment, search for a missing stretcher-bearer in a ruined farm and help carry a wounded man to the Regimental Aid Post.',
  contentNotes: 'Wartime setting with artillery fire and a wounded soldier. No combat for the player and no graphic injuries. The bombardment sequence can be skipped while keeping progress.',
  loadingFacts: [
    'In October 1916 heavy rain turned the shell-churned chalk and clay of the Somme into deep, sticky mud. [documented]',
    'When shellfire cut telephone lines, runners carrying written messages were often the most reliable way to communicate. [documented]',
    'Regimental stretcher-bearers wore a white armband marked “SB” in red. [documented]',
    'Trench names in this sector are invented, but British units really did name trenches after London streets. [reconstruction]',
  ],
  sources: H.sources,
  scans,
  journal: [
    { id: 'brief_fiction', title: 'About this assignment', text: 'The battalion, its sector, the trench and farm names, the characters, the diary and every mission objective are inventions. The setting (the Somme in October 1916, trench layout, kit, communications and medical evacuation) is based on the documented sources listed with each record.', status: 'fiction', initiallyKnown: true },
    fact('somme_dates', 'The Battle of the Somme', true),
    fact('oct_1916_weather', 'Rain and mud, October 1916', true),
    fact('somme_final_phase', 'The final phase', true),
    fact('trench_lines', 'Front, support and reserve lines', true),
    fact('trench_size', 'Trench dimensions used in this reconstruction', true),
    fact('runners', 'Runners'),
    fact('message_form', 'The message form'),
    fact('field_telephone', 'Field telephones'),
    fact('line_repair', 'Repairing cut lines'),
    fact('bombardment_experience', 'Living through a bombardment'),
    fact('whizz_bang', '“Whizz-bangs”'),
    fact('dugouts', 'Dugouts and shelters'),
    fact('dugout_gas_curtain', 'Gas curtains'),
    fact('traverses', 'Traverses and fire bays'),
    fact('fire_step', 'The fire step'),
    fact('parapet_parados', 'Parapet and parados'),
    fact('somme_geology', 'Somme chalk'),
    fact('spoil_visual', 'How the spoil is shown here'),
    fact('evac_chain', 'The medical evacuation chain'),
    fact('stretcher_bearers', 'Stretcher-bearers'),
    fact('stretcher_carry', 'Carrying stretchers in trenches'),
    fact('oct_1916_stretcher_bearing', 'Stretcher-bearing in October 1916'),
    fact('village_destruction', 'Villages in the battle zone'),
    fact('picardy_buildings', 'Picardy farm buildings'),
    fact('farm_cellar_scene', 'The farm cellar'),
    fact('routine', 'Daily routine'),
    fact('trench_foot', 'Trench foot'),
    fact('food', 'Rations'),
    fact('kit_uniform_webbing', 'Uniform and equipment'),
    fact('brodie_timeline', 'The steel helmet in 1916'),
    fact('gas_timeline', 'Gas helmets in 1916'),
    fact('wire_pickets', 'Barbed wire and screw pickets'),
    fact('civilians', 'No civilians in the forward zone'),
    fact('fiction_time_traveller', 'The anchor rule'),
  ],
  items: [
    { id: 'message', name: 'Field message (Army Form C.2121)', kind: 'document', description: 'A pencilled message for the officer commanding B Company in the front line. The company’s telephone line is cut.', readable: MESSAGE_TEXT },
    { id: 'splice_kit', name: 'Signaller’s repair kit', kind: 'tool', description: 'A coil of insulated cable, tape and pliers from Signaller Kemp, for joining a cut telephone line.' },
    { id: 'crowbar', name: 'Crowbar', kind: 'tool', description: 'A heavy steel bar from the Royal Engineers’ store in the farm barn. Long enough to lever timber.' },
    { id: 'diary', name: 'Pocket diary', kind: 'document', description: 'A small rain-spotted diary found in a fire bay. The flyleaf names its owner.', readable: DIARY_TEXT },
  ],
  artifacts: [
    { id: 'ww1_message_form', name: 'Message form counterfoil (replica)', description: 'A replica of the carbon counterfoil of the message you carried. The form type, Army Form C.2121, is documented; the message itself is game fiction.', status: 'fiction' },
    { id: 'ww1_sb_armband', name: '“SB” armband (replica)', description: 'A white armband with “SB” in red, as worn by regimental stretcher-bearers. Avery gave you his spare. The armband design is documented.', status: 'documented' },
    { id: 'ww1_diary_sketch', name: 'Sketch from a soldier’s diary', description: 'Whitlow’s pencil sketch of the ruined farm, given to you after you returned his diary. Fiction.', status: 'fiction' },
  ],
  missions: [
    {
      id: 'runner',
      title: 'The Runner',
      kind: 'main',
      summary: 'The telephone line to the front line is cut. Carry the message forward, then help find the missing stretcher-bearer.',
      stages: [
        {
          id: 'report',
          title: 'Report in',
          onEnter: [{ activateMission: 'witness' }],
          objectives: [{ id: 'talk_hollis', text: 'Report to Sergeant Hollis at the company dugout', detail: 'Follow Fleet Street (the support trench) east from where you arrived. The company dugout has a painted “B COY H.Q.” sign.', complete: { flag: 'dlg.hollis.give' }, marker: 'hollis' }],
          onComplete: [{ checkpoint: 'support_line' }, { journal: 'fact_runners' }, { journal: 'fact_message_form' }],
          next: 'carry',
        },
        {
          id: 'carry',
          title: 'Up Pall Mall',
          objectives: [{ id: 'go_pall_mall', text: 'Take the message up Pall Mall towards the front line', detail: 'Pall Mall is the communication trench leading north from Fleet Street, just west of the company dugout. Signboards mark the junctions.', complete: { flag: 'zone.pall_mall_mid' }, marker: 'pall_mall' }],
          next: 'barrage',
        },
        {
          id: 'barrage',
          title: 'Bombardment',
          objectives: [
            { id: 'take_cover', text: 'Take cover in the shelter', detail: 'Shells are falling on Pall Mall. The covered shelter entrance is a few metres further up the trench, on the right (east) side.', complete: { flag: 'zone.shelter' }, marker: 'shelter' },
            { id: 'wait_out', text: 'Wait out the bombardment', detail: 'Stay inside the shelter until the shelling stops.', complete: { flag: 'event.barrage_done' } },
          ],
          onComplete: [{ checkpoint: 'shelter' }, { journal: 'fact_bombardment_experience' }, { journal: 'fact_whizz_bang' }, { journal: 'fact_dugouts' }],
          next: 'reroute',
        },
        {
          id: 'reroute',
          title: 'Another way',
          objectives: [{ id: 'find_route', text: 'Find another route to the front line', detail: 'Pall Mall has collapsed beyond the shelter. Tottenham Sap branches east to Old Boot Alley, an old flooded German trench that still reaches the front line. Where a crater has cut the trench, climb the ladder and cross on the duckboard bridge.', complete: { flag: 'zone.front_line' }, marker: 'reroute' }],
          onComplete: [{ checkpoint: 'front_line' }, { journal: 'fact_traverses' }, { journal: 'fact_fire_step' }],
          next: 'deliver',
        },
        {
          id: 'deliver',
          title: 'Deliver the message',
          objectives: [{ id: 'talk_ward', text: 'Deliver the message to Captain Ward', detail: 'Captain Ward commands B Company from a dugout in the west part of Cheapside Trench, the front line. Look for the “COY H.Q.” sign.', complete: { flag: 'dlg.ward.delivered' }, marker: 'ward' }],
          next: 'search',
        },
        {
          id: 'search',
          title: 'The missing stretcher-bearer',
          objectives: [
            { id: 'find_avery', text: 'Search Moulin Farm for Private Avery', detail: 'Avery took a wounded man back towards the ruined farm in the village behind the support line. Return along Old Boot Alley and Tottenham Sap, then take Haymarket south out of the trenches. The farm is west along the village road.', complete: { flag: 'event.avery_found' }, marker: 'farm' },
            { id: 'see_echo', text: 'Use observation mode (F) at the farm to see what happened', optional: true, complete: { flag: 'event.echo_seen' } },
          ],
          onComplete: [{ journal: 'fact_village_destruction' }, { journal: 'fact_picardy_buildings' }, { journal: 'fact_farm_cellar_scene' }],
          next: 'free',
        },
        {
          id: 'free',
          title: 'Trapped',
          objectives: [
            { id: 'get_bar', text: 'Find something to lever the fallen beam', detail: 'Avery mentioned the Royal Engineers’ store in the ruined barn on the west side of the farmyard.', complete: { item: 'crowbar' }, marker: 'dump' },
            { id: 'lever', text: 'Lever the beam off the cellar steps', detail: 'Hold E at the beam with the crowbar.', complete: { flag: 'event.beam_moved' }, marker: 'beam' },
          ],
          onComplete: [{ checkpoint: 'farm' }],
          next: 'evacuate',
        },
        {
          id: 'evacuate',
          title: 'Stretcher case',
          objectives: [{ id: 'carry_whitlow', text: 'Help Avery carry Whitlow to the Regimental Aid Post', detail: 'You hold the rear handles; Avery leads. The R.A.P. is a dugout on Fleet Street, reached by Haymarket. When Avery shouts “Down!” or the screen warns of incoming shells, crouch (C) until it passes.', complete: { flag: 'event.whitlow_delivered' }, marker: 'rap' }],
          onComplete: [{ checkpoint: 'rap' }, { journal: 'fact_evac_chain' }, { journal: 'fact_stretcher_bearers' }, { journal: 'fact_stretcher_carry' }, { journal: 'fact_oct_1916_stretcher_bearing' }],
          next: 'mo',
        },
        {
          id: 'mo',
          title: 'Aid post',
          objectives: [{ id: 'talk_laird', text: 'Speak with the medical officer', complete: { flag: 'dlgdone.laird' }, marker: 'laird' }],
          next: 'return',
        },
        {
          id: 'return',
          title: 'Recall',
          onEnter: [{ setFlag: 'zone.anchor', value: false }],
          objectives: [{ id: 'go_anchor', text: 'Return to the temporal anchor point', detail: 'The anchor point is the fire bay in Fleet Street where you arrived, west of the company dugout.', complete: { flag: 'zone.anchor' }, marker: 'anchor' }],
        },
      ],
      onComplete: [{ artifact: 'ww1_message_form' }, { artifact: 'ww1_sb_armband' }, { event: 'chapter_complete' }],
    },
    {
      id: 'phone_line',
      title: 'A Thread of Wire',
      kind: 'optional',
      summary: 'Signaller Kemp’s line to the front line is cut somewhere along Pall Mall. Find the break and join it.',
      availableWhen: { flag: 'item.splice_kit' },
      stages: [
        {
          id: 'find',
          title: 'Find the break',
          objectives: [{ id: 'find_break', text: 'Follow the telephone cable along Pall Mall and find the break', detail: 'The cable runs along the west wall of Pall Mall. The scanner (Q) highlights the cut ends.', complete: { flag: 'event.break_found' } }],
          next: 'splice',
        },
        {
          id: 'splice',
          title: 'Join the line',
          objectives: [{ id: 'splice', text: 'Splice the cut cable', detail: 'Hold E at the cut ends.', complete: { flag: 'event.line_repaired' } }],
        },
      ],
      onComplete: [{ journal: 'fact_line_repair' }, { journal: 'fact_field_telephone' }, { notify: 'Kemp’s buzzer sounds faintly up the line. The company has a telephone again.', kind: 'info' }],
    },
    {
      id: 'diary',
      title: 'Words Home',
      kind: 'optional',
      summary: 'A pocket diary lies in a fire bay. Return it to its owner.',
      availableWhen: { flag: 'item.diary' },
      stages: [{ id: 'return', title: 'Return the diary', objectives: [{ id: 'give_diary', text: 'Return the diary to Private Whitlow', detail: 'The flyleaf names its owner: Pte. D. Whitlow, B Company.', complete: { flag: 'dlg.whitlow.diary' } }] }],
      onComplete: [{ artifact: 'ww1_diary_sketch' }],
    },
    {
      id: 'witness',
      title: 'Witness Record',
      kind: 'optional',
      summary: 'Record the sector with the temporal scanner: aim at highlighted objects and hold E while the scanner (Q) is active.',
      stages: [
        {
          id: 'record',
          title: 'Record',
          objectives: [{ id: 'scan8', text: 'Record 8 historical objects with the scanner', complete: { count: { flags: scanFlags, atLeast: 8 } }, progress: { flags: scanFlags, total: 8 } }],
        },
      ],
    },
  ],
  dialogues: [
    {
      id: 'hollis',
      entries: [{ condition: { flag: 'dlg.hollis.give' }, node: 'after' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Sgt. Hollis', text: 'There you are. You’re the runner Battalion promised? Took your time. Never mind; the mud takes everyone’s time.', choices: [
          { text: 'I’m here to help. What do you need?', next: 'task' },
          { text: 'I’m not exactly a runner…', next: 'notrunner' },
        ] },
        notrunner: { speaker: 'Sgt. Hollis', text: 'You’ve got two legs and you’re not on the sick list. Today that makes you a runner.', next: 'task' },
        task: { speaker: 'Sgt. Hollis', text: 'The line to Captain Ward in Cheapside went dead an hour ago. Shell must’ve cut it. This message has to reach him: relief’s postponed and he needs to know before dusk.', next: 'give' },
        give: {
          speaker: 'Sgt. Hollis',
          text: 'Up Pall Mall. It’s the communication trench just west of here, past the sign. Keep your head below the parapet, and if Fritz starts sending over whizz-bangs, get under cover. Don’t be a hero.',
          effects: [{ giveItem: 'message' }],
          choices: [
            { text: 'Whizz-bangs?', next: 'whizz' },
            { text: 'Anything else?', next: 'kemp' },
            { text: 'On my way.' },
          ],
        },
        whizz: { speaker: 'Sgt. Hollis', text: 'Field-gun shells. Fast. You hear them and they’re already there. The big stuff you hear coming. Either way: down and under.', next: 'kemp' },
        kemp: { speaker: 'Sgt. Hollis', text: 'Kemp in the signals dugout next door is tearing his hair out over that line. If you’ve a minute, he might want a hand. Now go.' },
        after: { speaker: 'Sgt. Hollis', text: 'Still here? Pall Mall, west of the sign. Captain Ward’s waiting on that message.' },
      },
    },
    {
      id: 'kemp',
      entries: [{ condition: { flag: 'event.line_repaired' }, node: 'fixed' }, { condition: { flag: 'item.splice_kit' }, node: 'again' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Signaller Kemp', text: 'Dead as a doornail. Buzzer, key, nothing. The cable runs up Pall Mall along the left-hand wall going north. Somewhere up there it’s been cut.', choices: [
          { text: 'I’m heading up Pall Mall. I could look for the break.', next: 'offer' },
          { text: 'Why not send it by Morse?', next: 'morse' },
          { text: 'Sorry, I’ve got a message to deliver.' },
        ] },
        morse: { speaker: 'Signaller Kemp', text: 'The D Mark III will send Morse on a line too poor for speech. Not on a line that’s been cut in two, it won’t.', choices: [{ text: 'I could look for the break.', next: 'offer' }, { text: 'Good luck with it.' }] },
        offer: { speaker: 'Signaller Kemp', text: 'Would you? Here: cable, tape and pliers. Find both cut ends, strip them, twist them together and tape them up tight. Keep low while you do it.', effects: [{ giveItem: 'splice_kit' }] },
        again: { speaker: 'Signaller Kemp', text: 'Left-hand wall going up Pall Mall. Your scanner gadget, or whatever it is, might pick out the cut ends.' },
        fixed: { speaker: 'Signaller Kemp', text: 'Buzzing like a hive! I’ve got Cheapside. That’s the best thing that’s happened all week. Thank you.' },
      },
    },
    {
      id: 'ellis',
      entries: [{ condition: { flag: 'event.barrage_done' }, node: 'after' }, { condition: { flag: 'barrage.active' }, node: 'during' }, { node: 'before' }],
      nodes: {
        before: { speaker: 'Pte. Ellis', text: 'Mind your feet. The duckboards up here are half floating.' },
        during: { speaker: 'Pte. Ellis', text: 'Count them, if it helps. I count them. Keeps your mind busy.', choices: [{ text: 'How long do these last?', next: 'long' }, { text: 'I’ll count with you.', next: 'count' }] },
        long: { speaker: 'Pte. Ellis', text: 'Could be a minute. Could be an hour. This feels like a short one. Just keep your back to the wall.' },
        count: { speaker: 'Pte. Ellis', text: 'Twenty-six… twenty-seven… there, that one was further off. Getting further off.' },
        after: { speaker: 'Pte. Ellis', text: 'Pall Mall’s fallen in up ahead. You won’t get through that way. Try Tottenham Sap. It runs east to Old Boot Alley, the old German trench. It’s flooded, mind, and there’s a crater where it’s blown through. There’s a ladder and a bridge of duckboards over it.', effects: [{ setFlag: 'hint.reroute' }] },
      },
    },
    {
      id: 'ward',
      entries: [{ condition: { flag: 'dlg.ward.delivered' }, node: 'after' }, { condition: { notFlag: 'item.message' }, node: 'busy' }, { node: 'start' }],
      nodes: {
        busy: { speaker: 'Capt. Ward', text: 'Not now, whoever you are. My line’s dead and I’m waiting on word from Battalion. If you’re going back down, tell Sergeant Hollis I need it.' },
        start: { speaker: 'Capt. Ward', text: 'Who on earth are you? Out of breath and covered in Old Boot Alley, by the look of it.', choices: [
          { text: 'A message from Battalion, sir. The line’s down.', next: 'read', condition: { notFlag: 'event.line_repaired' } },
          { text: 'A message from Battalion, sir. Kemp should have the line back.', next: 'read_phone', condition: { flag: 'event.line_repaired' } },
        ] },
        read: { speaker: 'Capt. Ward', text: 'Relief postponed… report on the wire by six… Marvellous. Well, thank you. You’ve earned a tot, if there were any.', effects: [{ takeItem: 'message' }, { setFlag: 'dlg.ward.delivered' }], next: 'avery' },
        read_phone: { speaker: 'Capt. Ward', text: 'Kemp got through ten minutes ago. The line’s yours, I take it? Good work. I’ll still sign for the paper copy. Relief postponed… as I feared.', effects: [{ takeItem: 'message' }, { setFlag: 'dlg.ward.delivered' }], next: 'avery' },
        avery: { speaker: 'Capt. Ward', text: 'Listen. Before the shelling, my stretcher-bearer Avery took Private Whitlow back. Leg wound, working party. They went down Haymarket towards Moulin Farm. The R.A.P. was getting a pasting and the farm cellar is the nearest cover back there. Nobody’s seen them since the barrage.', choices: [
          { text: 'I’ll find them.', next: 'go' },
          { text: 'Why the farm and not the aid post?', next: 'why' },
        ] },
        why: { speaker: 'Capt. Ward', text: 'Shells were landing on Fleet Street. Avery has good sense. He’d have gone to ground with his man somewhere solid and waited. That cellar’s the only solid thing left in the village.', next: 'go' },
        go: { speaker: 'Capt. Ward', text: 'Go back down Old Boot Alley, then Haymarket south to the village. The farm is west along the road. Take care.' },
        after: { speaker: 'Capt. Ward', text: 'Moulin Farm. Haymarket south, then west along the road. Find them.' },
      },
    },
    {
      id: 'avery_gap',
      entries: [{ condition: { flag: 'event.avery_found' }, node: 'again' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Pte. Avery (below)', text: 'Hello? Is someone up there? Thank God. The beam’s come down across the steps, and I can’t shift it from this side. Whitlow’s with me. Leg’s bad, but he’s talking.', choices: [
          { text: 'Captain Ward sent me. How do I get you out?', next: 'how' },
          { text: 'Hold on, I’ll find a way.', next: 'how' },
        ] },
        how: { speaker: 'Pte. Avery (below)', text: 'The Engineers keep a store in the barn, the ruined one on the west side of the yard. There’ll be a crowbar or a pick. Get it under the beam and lever it off.', effects: [{ setFlag: 'event.avery_found' }] },
        again: { speaker: 'Pte. Avery (below)', text: 'The barn on the west side of the yard. A crowbar, anything long and steel.' },
      },
    },
    {
      id: 'avery',
      entries: [{ condition: { flag: 'event.whitlow_delivered' }, node: 'done' }, { condition: { flag: 'carry.ready' }, node: 'ready' }, { node: 'freed' }],
      nodes: {
        freed: { speaker: 'Pte. Avery', text: 'Out at last. Thank you. We have the stretcher down here. Whitlow can’t walk. I need a second pair of hands at the back. The R.A.P. on Fleet Street is our best bet now the shelling’s eased.', choices: [{ text: 'I’ll take the back handles.', next: 'brief' }] },
        brief: { speaker: 'Pte. Avery', text: 'I’ll lead. You keep the pace. If you hear one coming, or I shout “Down!”, get low and hold on. We go up Haymarket. The traverses are tight; trust me on the corners.', effects: [{ setFlag: 'carry.ready' }] },
        ready: { speaker: 'Pte. Avery', text: 'Ready when you are. Take the rear handles.' },
        done: { speaker: 'Pte. Avery', text: 'Couldn’t have done it alone. Here, keep this. A spare armband. Wear it and they’ll know you’re one of us.' },
      },
    },
    {
      id: 'whitlow',
      entries: [{ condition: { all: [{ item: 'diary' }, { flag: 'event.whitlow_delivered' }] }, node: 'diary_offer' }, { condition: { flag: 'event.whitlow_delivered' }, node: 'rap' }, { node: 'cellar' }],
      nodes: {
        cellar: { speaker: 'Pte. Whitlow', text: 'Don’t mind me. Just resting my eyes. Avery says you’re taking us home. Well, to the aid post, which is near enough.' },
        rap: { speaker: 'Pte. Whitlow', text: 'Proper bandage, a blanket and the M.O. says it’s a Blighty one. Going home. Strange thing to be glad of.' },
        diary_offer: { speaker: 'Pte. Whitlow', text: 'Is that… my diary? I thought I’d lost it in Cheapside. There’s letters in there I never sent.', choices: [{ text: 'It was in a fire bay. I thought you’d want it back.', next: 'diary' }] },
        diary: { speaker: 'Pte. Whitlow', text: 'You don’t know what that means. Here, tear out the sketch at the back, the one of the farm. Something to remember us by.', effects: [{ takeItem: 'diary' }, { setFlag: 'dlg.whitlow.diary' }] },
      },
    },
    {
      id: 'laird',
      entries: [{ condition: { flag: 'dlgdone.laird' }, node: 'after' }, { node: 'start' }],
      nodes: {
        start: { speaker: 'Capt. Laird, R.A.M.C.', text: 'On the table. Gently. Good. Tourniquet’s been well done; that’s Avery’s work. He’ll go back to the Advanced Dressing Station tonight with the bearers, and from there to a Casualty Clearing Station.', choices: [
          { text: 'Will he be all right?', next: 'ok' },
          { text: 'What happens to him next?', next: 'chain' },
        ] },
        ok: { speaker: 'Capt. Laird, R.A.M.C.', text: 'He should keep the leg. In this mud, getting a man here quickly is half the battle. You did well.', next: 'end' },
        chain: { speaker: 'Capt. Laird, R.A.M.C.', text: 'Field Ambulance bearers will carry him back to the dressing station, then by motor ambulance to a clearing station, then a train, and home if he’s lucky. Every link in the chain is a carry like yours.', next: 'end' },
        end: { speaker: 'Capt. Laird, R.A.M.C.', text: 'Now, unless you’re hurt, out of my aid post. I need the room.' },
        after: { speaker: 'Capt. Laird, R.A.M.C.', text: 'He’s comfortable. Go on with you.' },
      },
    },
  ],
  checkpoints: {
    start: { label: 'Fleet Street — arrival', position: [ANCHOR[0], -2.0, SUPPORT_Z], yaw: -Math.PI / 2 },
    support_line: { label: 'Fleet Street — company dugout', position: [-6.8, -2.0, 4.2], yaw: Math.PI / 2 },
    shelter: { label: 'Pall Mall shelter', position: [-5.0, -2.2, -26.3], yaw: Math.PI / 2 },
    front_line: { label: 'Cheapside — front line', position: [23.6, -2.0, -59.4], yaw: Math.PI / 2 },
    farm: { label: 'Moulin Farm', position: [-17, 0.5, 76], yaw: -Math.PI / 2 },
    rap: { label: 'Regimental Aid Post', position: [18, -2.1, 7.8], yaw: 0 },
  },
  startCheckpoint: 'start',
  intro: [
    { kicker: 'Western Front · October 1916', caption: 'Autumn rain has turned the Somme battlefield to mud. The great offensive that began in July is grinding into its last weeks.', duration: 7, from: { pos: [-40, 12, 30], look: [-5, -1, -20] }, to: { pos: [-28, 7, 18], look: [-5, -1, -25] } },
    { kicker: 'Fleet Street · support line', caption: 'You arrive in a fictional British company sector. Telephone lines are cut. Messages go forward on foot.', duration: 6.5, from: { pos: [-28, 1.2, 4.4], look: [-12, -1, 3.8] }, to: { pos: [-23, -0.2, 4.2], look: [-10, -1.4, 4] } },
  ],
  outro: [
    { kicker: 'Regimental Aid Post', caption: 'Whitlow was carried on down the evacuation chain that night. His story, like every name here, is fiction.', duration: 6.5, from: { pos: [12, 4, 20], look: [18, -1, 6] }, to: { pos: [8, 6, 26], look: [10, -1, 0] } },
    { kicker: 'The Somme · 1916', caption: 'The documented history is unchanged. Rain and mud slowed the final weeks of fighting, and the offensive ended on 18 November 1916.', duration: 7.5, from: { pos: [-30, 14, -10], look: [10, 0, -70] }, to: { pos: [-10, 18, -30], look: [20, 0, -90] } },
  ],
  load: () => import('./WW1Runtime'),
};
