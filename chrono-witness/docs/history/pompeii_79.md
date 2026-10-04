# Chapter research: Pompeii, the eruption of AD 79

The machine-readable version is `pompeii_79.json`. It uses the same fact IDs and source keys as this file. The older, broader note is `research_notes_pompeii_79.md`.

**Status tags:** **[DOCUMENTED]** means a cited source supports it. **[RECONSTRUCTION]** means it is plausible but not a specific recorded fact. **[FICTION]** means it is a game invention.

**Verification caveat.** Sources were accessed on 2026-10-04, apart from those carried over from the older note (accessed 2026-10-03, marked in the JSON). The sandbox network policy blocked direct page fetches for every reference host tried, including pompeiisites.org and the University of Virginia Pliny page. DOCUMENTED items were checked against search-engine summaries of the cited pages, not full reads. The session's web-search budget ran out partway through, so a few items rest on a single summary; they are listed in section 10. The Pliny passages on the sea and shore (`pliny_sea`) come from the standard text of Letters 6.16 and 6.20 and were not re-checked against a summary. Where the search index showed only a URL slug, the source title in the JSON is descriptive and says so. Confirm the wording on each live page before shipping.

---

## 1. Corrections to the premise

1. **The date is uncertain. Recommendation: set the chapter in autumn, but never print a day and month.** [DOCUMENTED: `date_traditional`, `date_inscription`, `date_autumn_finds`, `date_still_debated`]
   - **24 August** comes from manuscript copies of Pliny's Letter 6.16 ("the ninth day before the Kalends of September").
   - **About 24 October** is a hypothesis built on the 2018 charcoal inscription "XVI K Nov" (17 October). The inscription has no year. Its fragility makes October 79 likely, but not certain.
   - The autumn case also rests on heavier clothing, braziers, and pomegranate and walnut remains. A Titus coin is sometimes cited, but its date is disputed. On the other side, garum remains have been argued to fit summer. The Park's director has said the question is open.
   - **What to show:** an autumn setting. That means cool morning, cloaks, a lit brazier, new wine in jars, and pomegranates on a stall. It fits the stronger recent evidence and is consistent with the date being unknown. [RECONSTRUCTION: `october_life`]
   - **How to phrase it in the game.** Title card: *"Pompeii, AD 79. The day Vesuvius erupted."* Codex or scanner note: *"Pliny's letters, as copied by medieval scribes, give 24 August. An inscription found in 2018 and finds of autumn fruit suggest late October. The exact date is still debated."* Do not write "24 October AD 79" as fact, and do not write "24 August" without the caveat.
2. **The column appears at about 1 p.m., but there was an earlier warning.** The Plinian column was seen from Misenum at "about the seventh hour", early afternoon. A small explosive phase, probably that morning, threw fine ash mainly east. A morning tremor or a thin dusting of ash, without alarm, is defensible. A visible eruption column during the morning delivery is not. [DOCUMENTED: `erupt_column_time`, `erupt_opening_phase`; `roman_hours` is RECONSTRUCTION]
3. **The timeline in the premise is broadly right, with three refinements.** [DOCUMENTED: `erupt_pumice_rate`, `erupt_roof_collapse`, `erupt_surges`, `erupt_surge_pompeii`]
   - **Pumice:** about **15 cm an hour** for 18-20 hours, reaching about 2.8 m. It was white pumice first, then grey.
   - **Not everyone who died was killed by the surges.** About **38%** of known victims died during the pumice fall, mostly when roofs and walls collapsed. The scripted roof collapse is therefore grounded, but it must not kill anyone on screen (see section 8).
   - **Surges:** the pumice fall was interrupted six times by surges and flows. The one that killed the people left in Pompeii (S4) arrived at about **7 a.m. on Day 2**. Heat was the main cause of death.
4. **"Safety on the road beyond the walls" needs care.** [DOCUMENTED: `flight_outside_walls`, `most_escaped`]
   - Victims have been found just inside Porta Nocera (the Garden of the Fugitives), on the road outside Porta Nocera, and outside Porta Stabia. Passing the gate was not enough. Leaving early, on Day 1, and getting far away is what saved people.
   - Most of the population did escape, and survivors resettled in Naples, Cumae, Puteoli and Ostia.
   - Recommendation: the ending is the household on the road well beyond the walls on Day 1, late afternoon, in falling pumice and gathering dark, walking away. Do not set the ending at the Garden of the Fugitives or at a known findspot.
5. **Gates.** All three named gates existed. [DOCUMENTED: `city_walls_gates`, `gate_marina`, `gate_stabia_nocera`; route choice is FICTION]
   - **Porta Marina** (west): steep, with a pedestrian passage and a larger one for animals, on the road down to the sea. Pliny shows escape by sea was blocked by debris, shallows and contrary wind (`pliny_sea`). It is a good place for a beat where residents want the harbour and are turned back.
   - **Porta Stabia** (south): at the end of Via Stabiana, on the road toward Stabiae. Stabiae itself was under the fall, and Pliny the Elder died there.
   - **Porta Nocera** (south-east): on the road to Nuceria, lined with tombs. Visually distinctive, but strongly associated with victims.
   - **Recommended route:** Porta Stabia for the playable exit, with the tomb-lined road beyond as scenery, kept clear of named findspots. Mention Porta Marina in dialogue as the route people tried first.
   - The pumice fell to the south-east, so roads south and east stayed under the fall for some distance. Which roads were passable is RECONSTRUCTION.
6. **The street fountain may not have been running normally.** In 79 Pompeii's piped water system was being rebuilt. The castellum aquae seems to have been out of use after the earthquake, and a new third phase of pipes was under construction. [DOCUMENTED: `water_castellum`, `water_under_repair`]
   - Make the fountain mission about a weak or intermittent flow, with pipe works in the street. That is RECONSTRUCTION, but it is better supported than a full basin.
   - The Park's site page still speaks of about 40 fountains distributed around the city, so a working fountain is not impossible.
7. **The wax-tablet model is real, but it predates 79.** The Caecilius Iucundus archive (153 tablets, found 1875) is almost entirely AD 52-62. Iucundus's records stop around the earthquake, so he probably was not trading in 79. Using a fictional freedman banker modelled on him is the right choice. Iucundus's own father was a freedman. [DOCUMENTED: `iucundus_archive`, `iucundus_role`; FICTION: `fictional_banker`]
8. **Earthquake date.** Say "the earthquake of 62" (some ancient sources give 63). Repairs were still in progress in 79. [DOCUMENTED: `quake_62`]

## 2. Context

- [DOCUMENTED] Population is estimated at 10,000-20,000 (11,000-15,000 often quoted), within walls enclosing about 66 hectares. (`population`)
- [DOCUMENTED] A 2003 study counted 1,150 recovered victims: 394 in the pumice layer and 650 in the surge deposits. Finds continue, such as two people in Regio IX in 2024. (`victims_found`)
- [DOCUMENTED] Most people escaped. (`most_escaped`)
- [DOCUMENTED] A 2024 DNA study overturned family stories told about the casts. Do not invent stories for real remains. (`casts_dna`)

## 3. Eruption timeline

| When (approx.) | What happened | Tag / sources |
|---|---|---|
| Day 1 morning | Brief explosive phase; fine ash mainly to the east, a few cm near the vent | DOCUMENTED `erupt_opening_phase` |
| Day 1, about 1 p.m. | Plinian column rises, umbrella-pine shape, seen from Misenum 30 km away | DOCUMENTED `erupt_column_time` |
| Day 1 afternoon to night | White, then grey pumice falls on Pompeii at about 15 cm/h; column roughly 15 to over 30 km high | DOCUMENTED `erupt_pumice_rate`, `erupt_column_height` |
| Day 1 evening and night | Roofs and walls give way under the pumice; 38% of known victims die in this phase | DOCUMENTED `erupt_roof_collapse` |
| Night to Day 2 | Six surges and flows interrupt the fall | DOCUMENTED `erupt_surges` |
| Day 2, about 7 a.m. | Surge S4 reaches Pompeii and kills those still there | DOCUMENTED `erupt_surge_pompeii` |
| Day 2 | Pliny the Elder dies on the shore at Stabiae | DOCUMENTED `pliny_stabiae` |

- [DOCUMENTED] At Stabiae, people tied pillows to their heads against falling stones and carried torches and lamps in a darkness "blacker than any night". Buildings shook with repeated tremors. These are good behaviours for fictional residents. (`pliny_stabiae`)
- [DOCUMENTED] People fleeing took coins, jewellery and house keys. (`flight_carried`)
- [RECONSTRUCTION] On Day 1 afternoon the light dims to grey-brown, pumice rattles on roof tiles, and by late afternoon it is as dark as night. (`light_and_sound`)

## 4. Streets, water and shops

| Topic | Summary | Tag / sources |
|---|---|---|
| Paving and ruts | At least 61% of streets lava-paved; deep cart ruts; about 80% too narrow for two-way traffic | DOCUMENTED `street_paving` |
| Sidewalks and stepping stones | Raised kerbs; stepping stones keep feet out of water and dung, spaced for wheels | DOCUMENTED `street_stepping_stones` |
| Fountains | About 40 (42 catalogued); stone basin plus spout stone; lead pipes; at least 14 water towers | DOCUMENTED `water_fountains` |
| Castellum aquae | At Porta Vesuvio, highest point (42 m), Serino aqueduct, three outlets; apparently out of use in 79 | DOCUMENTED `water_castellum`, `water_under_repair` |
| Thermopolium | Over a hundred food bars; dolia in counters; 2020 Regio V bar with painted ducks, rooster and dog | DOCUMENTED `thermopolium` |
| Bakery | About 33 known; lava mills turned by donkeys and enslaved workers; carbonised loaves | DOCUMENTED `bakery` |
| Fullonica | Urine as detergent, cloth trodden in vats, often by enslaved workers; Stephanus on Via dell'Abbondanza | DOCUMENTED `fullonica` |

## 5. Walls, houses and daily life

- [DOCUMENTED] **Programmata:** about 2,500 painted election notices in red or black by professional sign painters, mostly for aedile and duovir, on busy streets. Use fictional candidate names. (`programmata`)
- [DOCUMENTED] **Graffiti:** scratched personal messages, greetings and show notices. (`graffiti`)
- [DOCUMENTED] **House:** entrance passage, atrium with compluvium and impluvium, peristyle garden beyond. (`house_atrium`)
- [DOCUMENTED] **Fourth Style** painting (about AD 50/60-79) was current. Much was painted during post-earthquake repairs. (`fourth_style`)
- [DOCUMENTED] **Clothing:** tunics of wool or linen. Togas for formal occasions only, and palla over stola for married citizen women. Hooded paenula cloak, sandals or calcei, mostly undyed cloth for ordinary people. (`clothing`)
- [DOCUMENTED] **Coins:** aureus = 25 denarii; denarius = 4 sestertii; sestertius = 2 dupondii; dupondius = 2 asses. (`coinage`)
- [DOCUMENTED] **Wax tablets:** triptychs of three tied leaves, waxed inside; receipts with witnesses' names. (`iucundus_archive`)

## 6. Scanner entries (14)

The full text is in the JSON `scanEntries` array. All 14 are DOCUMENTED. Where the object in the scene is a fictional prop (the tablet, the candidate's name, the graffiti text), the entry says so.

| ID | Title | Sources |
|---|---|---|
| scan_stepping_stones | Stepping Stones | archaeology_poehler, pbs_traffic |
| scan_street_fountain | Street Fountain | lacus_northumbria, keenanjones2015 |
| scan_water_tower | Water Tower | pap_castellum, lacus_northumbria |
| scan_wax_tablet | Wax Writing Tablet | mau1899_tablets, wiki_iucundus |
| scan_thermopolium | Food-Bar Counter | thepast_thermopolium, madain_commercial |
| scan_bakery_mill | Lava-Stone Mill | whe_popidius, finestre_bakery |
| scan_fullonica_vat | Fuller's Vat | whe_fullers |
| scan_programma | Painted Election Notice | archaeology_politics, mann_elections |
| scan_graffiti | Wall Graffiti | madain_commercial |
| scan_impluvium | Atrium Rain Basin | britannica_domus, bas_four_styles |
| scan_fresco | Fourth Style Wall Painting | bas_four_styles |
| scan_coin_purse | Coin Purse | whe_coinage, pap_coins_fugitive |
| scan_pumice | Pumice Stones | smithsonian_fall_rise, luongo2003 |
| scan_repair_works | Earthquake Repairs | cambridge_earthquake, smithsonian_construction, pap_guide |

## 7. What the game must NOT claim

- That the house, street block, banker, baker or household existed. All are FICTION (`fiction_premise`, `fictional_banker`).
- A specific day and month as certain.
- A visible eruption column in the morning.
- That everyone who stayed died only in the surges, or that leaving through a gate guaranteed survival.
- That the fictional banker is Caecilius Iucundus, or any story about a real excavated individual or a real house owner (for example the Vettii or Julia Felix).
- That all fountains were running normally.
- Specific victim numbers for the fictional block.

## 8. Sensitive-content guidance

- **The plaster casts are people.** They contain real skeletal remains. Do not use cast poses as set dressing, silhouettes, jump-scares, collectibles or scanner entries. Do not put a cast-like figure in any scene, including the epilogue. (`casts_ethics`)
- **Do not show anyone dying.** The player leaves on Day 1. Day 2 is told afterwards in a calm epilogue card grounded in archaeology. For example: *"Early the next morning, a surge of hot gas and ash reached the city. Many of those who had stayed died. Most of Pompeii's people had already left."*
- **Roof collapse (skippable).** Show it as an empty room giving way after the household has been led out: creaking beams, a warning crack, dust. No one is under it. Provide a skip option and a content note before the chapter. Never show or imply a trapped body.
- **No forensic spectacle.** Do not depict contested claims about boiling blood or exploding skulls (`petrone2018`), and do not show burns or the effects of heat.
- **No fail state tied to deaths.** Residents who are not guided do not die on screen. At most they choose to stay, and the epilogue speaks of people in general, not of named NPCs.
- **Enslaved people** (millers, fullers, household workers) are characters with names, voices and choices, not props. The household's decisions about who flees together should acknowledge them.
- **Children** are frightened but safe on screen.

## 9. Fiction boundaries

- [FICTION] All named residents, the banker or baker, the household, the street block and every mission.
- Real gates, street types and building types may be used as settings. Real houses (the House of the Vettii, the House of Caecilius Iucundus) may appear only as landmarks, with no invented occupants.
- Electoral notices and graffiti use invented names, or are clearly labelled as reproductions if a real text is quoted.
- The epilogue speaks of the city's people in general and never attaches a fictional NPC's fate to a real findspot.

## 10. Open questions

- Which roads out of Porta Stabia or Porta Nocera stayed passable on Day 1 afternoon, and how thick the pumice was there by evening. Check Sigurdsson et al. 1985 (*National Geographic Research* 1(3)) and Luongo et al. 2003 isopach maps.
- Whether any street fountains still ran in 79. The Park page and Keenan-Jones (2015) point in different directions. Ask the Park.
- Exact counts: the number of thermopolia (the "150+" figure is from a secondary source) and of surviving graffiti. Not re-verified this pass.
- The Sigurdsson surge time (about 7 a.m., Day 2) was verified only via tertiary and popular summaries. Confirm in the 1985 paper.
- Plume and wind direction if the date is October rather than August. Some atmospheric studies link the fallout pattern to autumn winds; not verified here.
- Park guidance on depicting casts and remains in games. Contact the Parco Archeologico di Pompei directly.

## Sources

See the `sources` object in `pompeii_79.json` for full titles, publishers, URLs and access dates. Main sources:

- Parco Archeologico di Pompei: `pap_regio_v_inscription`, `pap_marina_gate`, `pap_fugitives`, `pap_coins_fugitive`, `pap_regio_ix_victims`, `pap_castellum`, `pap_guide`
- Pliny, Letters 6.16 and 6.20 in translation: `pliny_uva`, `pliny_cscp`, `pliny_uark`
- Volcanology and casualties: `luongo2003` (J. Volcanol. Geotherm. Res.), `plos_lethal_surges`, `mtu_vesuvio79`, `smithsonian_fall_rise`, `wiki_eruption79` (tertiary), `historyuk_eruption`
- Date debate: `cnn_inscription`, `thelocal_inscription`, `finestre_date_debate`, `brewminate_date`
- Water: `keenanjones2015` (AJA), `lacus_northumbria`
- Streets: `archaeology_poehler`, `pbs_traffic`
- Shops, walls and houses: `thepast_thermopolium`, `whe_popidius`, `finestre_bakery`, `whe_fullers`, `archaeology_politics`, `mann_elections`, `madain_commercial`, `britannica_domus`, `bas_four_styles`
- Earthquake: `cambridge_earthquake`, `wiki_ad62`, `smithsonian_construction`
- Daily life: `aia_clothing`, `wiki_clothing`, `whe_coinage`, `wiki_iucundus`, `cscp_iucundus`, `mau1899_tablets`, `mau1899_overwhelmed`
- People and remains: `britannica_pompeii`, `livescience_tuck`, `currbio_dna2024`, `archmag_dna`, `ansa_casts`, `conversation_casts`, `petrone2018`
