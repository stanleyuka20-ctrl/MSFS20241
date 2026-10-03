import type { ChapterConfig } from './types';

/**
 * Destinations that use the shared chapter system but are NOT playable yet. They appear in the
 * destination selector clearly marked "In development" with their research basis and planned
 * missions. Research notes: docs/history/research_notes_<id>.md
 */
function planned(c: Pick<ChapterConfig, 'id' | 'title' | 'destination' | 'dateLabel' | 'year' | 'tagline' | 'overview' | 'plannedMissions'> & { contentNotes?: string }): ChapterConfig {
  return {
    ...c,
    status: 'in-development',
    missions: [],
    dialogues: [],
    items: [],
    journal: [],
    scans: [],
    sources: {},
    artifacts: [],
    checkpoints: {},
    startCheckpoint: '',
  };
}

export const PLANNED_CHAPTERS: ChapterConfig[] = [
  planned({
    id: 'london_blitz_1940',
    title: 'Blackout',
    destination: 'London during the Blitz',
    dateLabel: 'Autumn 1940',
    year: 1940,
    tagline: 'Sirens, blackout curtains and the long night in the shelters.',
    overview: 'The sustained German bombing of London began on 7 September 1940. Planned environment: a terraced East End street under blackout, an Underground station used as a shelter, searchlights and ARP wardens.',
    plannedMissions: ['Guide a family to a shelter before the raid', 'Locate a missing resident after an incident', 'Deliver medical supplies to a first-aid post', 'Help a rescue party reach a blocked street'],
  }),
  planned({
    id: 'normandy_1944',
    title: 'Hedgerows',
    destination: 'Normandy',
    dateLabel: 'June 1944',
    year: 1944,
    tagline: 'Coastal defences, sunken lanes and aid stations after the landings.',
    overview: 'The Allied landings in Normandy began on 6 June 1944. Planned environment: the area behind a landing beach, bocage lanes, a farm used as an aid station and damaged equipment.',
    plannedMissions: ['Reach a rendezvous point inland', 'Find a lost communications operator', 'Deliver supplies to an aid station', 'Help a stranded group reach cover'],
  }),
  planned({
    id: 'berlin_1945',
    title: 'The Last Weeks',
    destination: 'Berlin',
    dateLabel: 'April 1945',
    year: 1945,
    tagline: 'Rubble, cellars and exhausted civilians at the end of the war in Europe.',
    overview: 'The Battle of Berlin ended with the city’s surrender on 2 May 1945. Planned environment: a damaged residential block, a cellar shelter and a disrupted U-Bahn line, focused on civilians.',
    contentNotes: 'Wartime civilian suffering; handled without graphic depictions.',
    plannedMissions: ['Escort civilians along a passable route', 'Recover missing records from a damaged office', 'Locate an emergency shelter', 'Restore contact between separated neighbours'],
  }),
  planned({
    id: 'hiroshima_1945',
    title: 'Morning',
    destination: 'Hiroshima',
    dateLabel: '6 August 1945',
    year: 1945,
    tagline: 'A living city on an ordinary summer morning.',
    overview: 'At 8:15 a.m. on 6 August 1945 an atomic bomb exploded about 600 m above Shima Hospital, killing about 140,000 people by the end of the year. This chapter is being researched first. It will show the city’s everyday life before the bombing, use a clearly fictional protected viewpoint, and keep the aftermath to navigation, assistance and testimony-based understanding.',
    contentNotes: 'Atomic bombing and its aftermath. No graphic injury close-ups. The intense sequence can be skipped while keeping progress.',
    plannedMissions: ['Document daily life on a city street before 8:15', 'Complete a fictional resident’s delivery', 'Observe the event from a fictional protected temporal viewpoint (skippable)', 'Assist survivors on the route to a relief station'],
  }),
  planned({
    id: 'pompeii_79',
    title: 'Ash',
    destination: 'Pompeii',
    dateLabel: 'AD 79',
    year: 79,
    tagline: 'Tremors, markets and frescoed houses beneath Vesuvius.',
    overview: 'Vesuvius erupted in AD 79. The traditional date is 24 August, but an inscription found in 2018 suggests about 24 October. The chapter will make its date choice explicit. Planned environment: a residential insula, a bakery, the forum edge and changing volcanic conditions.',
    plannedMissions: ['Investigate the tremors with a local household', 'Reunite a separated household', 'Retrieve a wax-tablet record', 'Guide residents toward an evacuation route'],
  }),
  planned({
    id: 'titanic_1912',
    title: 'North Atlantic',
    destination: 'RMS Titanic',
    dateLabel: '14–15 April 1912',
    year: 1912,
    tagline: 'Corridors, decks and the freezing night after the collision.',
    overview: 'Titanic struck an iceberg at 11:40 p.m. on 14 April 1912 and sank at about 2:20 a.m. Planned environment: third-class corridors, working spaces, the boat deck and changing access routes.',
    plannedMissions: ['Locate a missing passenger', 'Deliver an urgent message', 'Navigate changing access routes below deck', 'Help passengers reach the boat deck'],
  }),
  planned({
    id: 'berlin_wall_1989',
    title: 'The Night the Gates Opened',
    destination: 'Berlin Wall',
    dateLabel: '9 November 1989',
    year: 1989,
    tagline: 'Crowds, checkpoints and a border that suddenly opened.',
    overview: 'After Günter Schabowski’s press conference on the evening of 9 November 1989, crowds gathered at the crossings, and the Bornholmer Straße crossing opened late that night. Planned environment: streets near a checkpoint, period vehicles and crowds.',
    plannedMissions: ['Reunite separated relatives', 'Document witness accounts', 'Find a meeting location', 'Experience the crossing sequence'],
  }),
];
