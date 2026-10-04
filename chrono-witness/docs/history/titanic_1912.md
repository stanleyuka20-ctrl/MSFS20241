# Chapter research: RMS Titanic, night of 14-15 April 1912

The machine-readable version is `titanic_1912.json`. It uses the same fact IDs and source keys as this file. The older, broader note is `research_notes_titanic_1912.md`.

**Status tags:** **[DOCUMENTED]** means a cited source supports it. **[RECONSTRUCTION]** means it is plausible but not a specific recorded fact. **[FICTION]** means it is a game invention. **[UNVERIFIED]** marks a RECONSTRUCTION item that is widely published from the 1912 inquiries but could not be checked against any source in this pass. Its JSON text begins "Inquiry evidence, not verified in this pass".

**Verification caveat. This chapter is only partly verified.**
- Every source here was carried over from `research_notes_titanic_1912.md` (accessed 2026-10-03). Its author checked each one against search-engine summaries, not full reads.
- In this pass, the sandbox blocked direct fetches for every host tried: titanicinquiry.org, encyclopedia-titanica.org, rmg.co.uk, loc.gov, gutenberg.org and others.
- The session's web search budget ran out before any Titanic search was made, so no new Titanic source was checked.
- Before scripting, read the primary transcripts: British Wreck Commissioner's Inquiry and US Senate Inquiry, both at titanicinquiry.org.

---

## 1. Corrections to the premise

1. **The Mesaba warning did not reach the bridge. The player must not be the one who gets it there.** [UNVERIFIED `mesaba_warning`]
   - At about 9:40 p.m., Mesaba reported heavy pack ice and large icebergs across Titanic's track.
   - Phillips was busy with passenger traffic for Cape Race. He acknowledged the warning, but it is not known to have left the wireless room.
   - Have the player deliver a warning that **did** reach the bridge. Use the Californian-to-Antillian ice message at about 7:30 p.m., which Bride took to the bridge himself.
   - If the Mesaba scene is kept, it must end with the form set aside. [FICTION `fiction_messenger`]
2. **"Shut up, I am busy" was said to the Californian at about 11 p.m.** [UNVERIFIED `californian_shut_up`]
   - Cyril Evans, Californian's operator, called to say they were stopped and surrounded by ice.
   - Phillips's reply is recorded as "Shut up, shut up, I am busy; I am working Cape Race".
   - Evans soon turned in. Play it neutrally: Phillips is overworked, not villainous.
3. **Wireless operators were Marconi Company staff, not White Star crew.** A White Star junior steward would not normally run Marconi traffic, so the role is a game device. A "Marconi messenger" framing is safer than "steward". [UNVERIFIED `wireless_operators`; FICTION `fiction_messenger`]
4. **23:40 is ship's time.** The collision is documented at about 11:40 p.m. ship's time. Ship's time was local apparent time, about three hours behind GMT and two hours ahead of New York. Use ship's time everywhere and never mix in New York or GMT times. [DOCUMENTED `collision_time`; offset is RECONSTRUCTION `ships_time`]
5. **No deliberate lock-in of third class.** [RECONSTRUCTION `class_barriers`; UNVERIFIED `third_class_access`]
   - Gates and barriers separating the classes existed, partly because of US immigration rules.
   - The British inquiry found no evidence that third class was deliberately held back.
   - Third-class losses came mainly from distance, confusing routes, language barriers and lack of direction.
   - Show closed gates and confusion, not crew locking people in.
6. **Boat 7 first, at about 12:40-12:45: correct, with caveats.** The first boat lowered was probably No. 7, at about 12:40-12:45 a.m. Exact times are debated. "About 28 aboard" matches common estimates of 27-28 but is UNVERIFIED here. [DOCUMENTED `first_boat`; UNVERIFIED `boat7_load`]
7. **20 boats, 1,178 seats: correct.** [DOCUMENTED `boats_capacity`; breakdown RECONSTRUCTION `boat_types`]
   - 14 wooden lifeboats of 65 seats = 910.
   - 2 emergency cutters of 40 seats = 80.
   - 4 Engelhardt collapsibles of 47 seats = 188.
   - Total: 1,178.
8. **Port and starboard loading differed.** Lightoller (port) allowed women and children only. Murdoch (starboard) let men in when no women were waiting. The player's side of the deck changes who gets a seat, but never the total saved. [UNVERIFIED `port_starboard`]
9. **Carpathia and the sinking.** [DOCUMENTED `sinking`, `carpathia`; UNVERIFIED `carpathia_details`]
   - Sinking: about 2:20 a.m., after breaking in two.
   - Carpathia began picking up boats at about 4:00-4:10 a.m.
   - The first boat taken aboard was No. 2, and the last, No. 12, at about 8:30 a.m.
   - About 705-712 survivors were taken aboard.
   - A dawn ending in a lifeboat that is picked up after 4:10 a.m. is safe.
10. **There is a sliver of moon at dawn.** The night was moonless. A thin waning crescent (about 4% lit) rose shortly before dawn; new moon was on 17 April. [DOCUMENTED `weather`; moon is RECONSTRUCTION, computed]

## 2. Timeline (ship's time)

| Time | Event | Tag / sources |
|---|---|---|
| 10 April | Leaves Southampton; calls at Cherbourg and Queenstown | DOCUMENTED `rmg_facts`, `rmg_d1` |
| 14 April, day | Ice warnings from Caronia, Baltic, Amerika and others | UNVERIFIED `warnings_received` |
| From ~6 p.m. | Clear, no moon, stars, not a cloud | DOCUMENTED `bot_weather` |
| ~7:30 p.m. | Air at 33 °F; Californian-to-Antillian ice message taken to the bridge | DOCUMENTED `bot_weather` / UNVERIFIED |
| ~9:40 p.m. | Mesaba warning; not known to reach the bridge | UNVERIFIED `mesaba_warning` |
| ~11:00 p.m. | Californian calls; "Shut up, I am busy" | UNVERIFIED `californian_shut_up` |
| **~11:40 p.m.** | Collision | DOCUMENTED `collision_time` |
| ~12:15 a.m. | "CQD MGY" sent with position; SOS used later | DOCUMENTED `cqd_sos` |
| ~12:40-12:45 a.m. | First boat lowered, probably No. 7 (starboard) | DOCUMENTED `first_boat` |
| ~12:45-1:25 a.m. | White rockets fired by Boxhall and Rowe; eight seen from Californian | DOCUMENTED `rockets` |
| ~2:05 a.m. | Collapsible D, the last boat lowered from davits | UNVERIFIED `last_boats` |
| **~2:20 a.m.** | Titanic sinks after breaking in two | DOCUMENTED `sinking` |
| ~4:00-4:10 a.m. | Carpathia begins picking up boats (first: No. 2) | DOCUMENTED `carpathia` / UNVERIFIED |
| ~8:30 a.m. | Last boat (No. 12) taken aboard | UNVERIFIED `carpathia_details` |

## 3. Conditions

- [DOCUMENTED] Flat calm, no swell, no moon, brilliant stars. The iceberg was harder to see with no waves breaking at its base. (`bot_weather`)
- [DOCUMENTED] Air temperature 33 °F (about 0.5 °C) by about 7:30 p.m., later 32 °F (0 °C). Sea temperature about −2 °C (28 °F). (`bot_weather`, `rmg_facts`, `rmg_d1`)
- [RECONSTRUCTION] Visible breath; a black, glassy sea reflecting the stars; deafening steam venting after the engines stopped; increasing bow-down trim and list; deck lights burning until near the end.
- [RECONSTRUCTION] At dawn: icebergs and field ice around the boats, and a light breeze getting up. This is reported in survivor testimony but UNVERIFIED here.

## 4. Wireless and the ice warnings

- [UNVERIFIED] Two Marconi operators, Phillips (senior) and Bride (junior), handled much paid passenger traffic via Cape Race. (`wireless_operators`)
- [UNVERIFIED] The Marconi room was on the Boat Deck behind the bridge, with an operating room, a soundproofed "silent room" for the transmitter, and a sleeping cabin. (`marconi_room`)
- [UNVERIFIED] Warnings and their fate (`warnings_received`, `warnings_bridge`, `mesaba_warning`):

| Ship | Approximate time | Reached bridge? |
|---|---|---|
| Caronia | morning | Yes; posted on the bridge |
| Baltic | early afternoon | Shown to Smith, who handed it to Ismay |
| Amerika | early afternoon | Relayed onward; not known to have reached the bridge |
| Californian to Antillian | ~7:30 p.m. | Yes; Bride took it up |
| Mesaba | ~9:40 p.m. | Not known to have reached the bridge |

- [DOCUMENTED] At about 12:15 a.m. Phillips sent "CQD MGY" and the position. SOS was used later. (`et_rockets`)
- [RECONSTRUCTION] Do not claim Titanic was the first ship to send SOS. (`sos_first_myth`)

## 5. Collision: what was felt where

All items in this section are UNVERIFIED (`lookout_warning`, `collision_felt`, `steam_noise`).

- **Crow's nest and bridge.** Three bells and "Iceberg right ahead". Murdoch orders the helm over, the bow swings to port, and the berg scrapes the starboard bow.
- **Upper decks (first and second class).** A slight jar or a long grinding vibration. Many people noticed little or nothing, and some slept on.
- **Forward, low down (firemen, forward third class).** A loud crash, water bursting into the forward boiler rooms, and ice falling onto the forward well deck.
- **Afterwards.** The engines stop and steam roars from the funnels. The sudden quiet of the engines alarms people more than the impact did.

## 6. Third class: routes, gates and myths

- [DOCUMENTED] The general room was aft, about 36 x 38 ft, pine-panelled with white enamel. The dining saloon was in two compartments, about 100 ft, seating 473. Food was plain and hearty. (`et_accommodation`, `belfast_food`)
- [UNVERIFIED] Single men were berthed mainly forward, and women and families mainly aft. (`third_class_quarters`)
- [UNVERIFIED] **Scotland Road** was the long E Deck working alleyway on the port side, used by crew and third-class passengers. (`scotland_road`)
- [UNVERIFIED] Steward John Hart testified that he guided groups of third-class women and children aft and up through second-class spaces to the Boat Deck. A good model for the player's route. (`third_class_access`)
- [RECONSTRUCTION] Gates existed, partly for US immigration rules. Whether any were locked during the sinking is disputed. (`class_barriers`)
- [RECONSTRUCTION] **Suggested in-game route** (aft families):
  1. Third-class cabins.
  2. Aft third-class stairs.
  3. The general room area.
  4. The aft well deck and poop.
  5. Up through second-class stairs or crew ladders.
  6. The Boat Deck aft.
- [RECONSTRUCTION] **Suggested in-game route** (forward men): along Scotland Road and up forward stairs. Confirm every connection against the deck plans in section 8.

## 7. Boat Deck, A Deck and lifeboats

- [UNVERIFIED] **Boat Deck.** Lifeboats in four groups on davits, two forward and two aft on each side. Also on this deck: the bridge, officers' quarters, Marconi room, the top of the Grand Staircase and the gymnasium. (`boat_deck`)
- [UNVERIFIED] **A Deck promenade.** First-class, along both sides. Its forward half was enclosed by a screen with sliding windows, unlike Olympic's, which complicated loading Boat 4 from A Deck. (`a_deck_promenade`)
- [DOCUMENTED] **Grand Staircase.** From the Boat Deck down to E Deck, about 60 ft high and 16 ft wide, under an iron-and-glass dome, with the "Honour and Glory crowning Time" clock. (`et_accommodation`)
- [DOCUMENTED] The first-class dining saloon on D Deck was 114 ft long and 92 ft wide, Jacobean in style. (`et_accommodation`)
- [UNVERIFIED] Loads: Boat 7 about 27-28 aboard; Boat 1 about 12 aboard. Many early boats left part-empty because people did not believe the ship would sink. (`boat7_load`)
- [UNVERIFIED] Collapsible D was the last boat lowered, at about 2:05 a.m. A and B floated off, B upside down. (`last_boats`)
- [RECONSTRUCTION] **The band.** The musicians played first indoors, then near the Boat Deck. The last piece is unknown, and all the musicians died. (`band`)

## 8. Deck-plan sources for layout

None of these could be opened in this pass. Titles are listed so the team can obtain them; only the first was checked, and only via a search summary.

1. **"Olympic & Titanic: Passenger Accommodation"**, Encyclopedia Titanica (`et_accommodation`).
   - It reprints the builders' period descriptions, with room dimensions and finishes.
   - Checked via summary on 2026-10-03.
2. **Harland & Wolff general arrangement plans** for Olympic and Titanic.
   - The originals and copies are held in Belfast archives (the Harland & Wolff collection). National Museums NI and the Public Record Office of Northern Ireland are the places to ask.
   - Not verified here.
3. **Deck plans entered as exhibits at the British Wreck Commissioner's Inquiry**, reproduced by the Titanic Inquiry Project (titanicinquiry.org). Not verified here.
4. **The 1911 special number of *The Shipbuilder*** on Olympic and Titanic, a builders' technical description. It is widely reprinted. Not verified here.
5. **Bruce Beveridge and others, *Titanic: The Ship Magnificent*** (two volumes). A modern, detailed reconstruction of the ship's structure and fittings. Not verified here.
6. **Encyclopedia Titanica deck plan pages and lifeboat research**, including `et_lifeboats_1`. Use these to fix boat positions and launch order.

## 9. Scanner entries (13: 8 DOCUMENTED, 5 RECONSTRUCTION)

The full text is in the JSON `scanEntries` array.

| ID | Title | Status | Sources |
|---|---|---|---|
| scan_lifeboat | Wooden Lifeboat | documented | rmg_facts, rmg_d1, et_time_to_go |
| scan_collapsible | Engelhardt Collapsible | reconstruction | none |
| scan_rocket | Distress Rocket | documented | et_rockets |
| scan_staircase_clock | Grand Staircase Clock | documented | et_accommodation |
| scan_wireless_key | Marconi Transmitting Key | documented | et_rockets |
| scan_ice_message | Ice Warning Form | reconstruction | none |
| scan_deck_ice | Ice on the Well Deck | reconstruction | none |
| scan_general_room | Third-Class General Room | documented | et_accommodation |
| scan_bill_of_fare | Third-Class Bill of Fare | documented | belfast_food, et_accommodation |
| scan_lifebelt | Cork Lifebelt | reconstruction | rmg_facts |
| scan_scotland_road | Scotland Road | reconstruction | none |
| scan_thermometer | Deck Thermometer | documented | bot_weather |
| scan_carpathia | RMS Carpathia | documented | britannica_apr15, et_boat8 |

## 10. Sensitive-content guidance

- **Scale.** About 1,500 people died. State this plainly in the journal. Do not turn deaths into a score or a failure state.
- **No bodies.** No bodies on deck, in corridors or in the water.
- **The water.** Do not linger on people in the water. Once the boat pulls away, the scene stays on the people in the boat. Cries are at most distant and brief, then fade under narration or music. Do not stage a "row back" rescue the player can fail.
- **The sinking is skippable.** Offer a skip before the final plunge and the break-up. Skipping cuts to the boats in the dark, then to dawn. Never show the break-up from close by, with people on deck.
- **Real people.** Real victims and survivors have living descendants.
  - Do not give real passengers invented dialogue or make them NPCs the player helps.
  - Officers, Phillips, Bride and the band may appear in the background doing what the record says.
  - All passengers the player guides are composites.
- **Class.** Show the class system honestly, including gates, distance and language barriers. Do not invent villains: no crew deliberately locking people below.
- **Myths.** Avoid stating these as fact:
  - that "Nearer, My God, to Thee" was the last tune;
  - that Titanic sent the first SOS;
  - that White Star advertised the ship as "unsinkable".
- **The Californian.** If mentioned at all, the Californian question is stated neutrally.
- **Children and families.** Separations are shown through worry and searching, never through on-screen deaths.

## 11. What the game must NOT claim

- That the player's steward or messenger, the third-class family or any spoken-to passenger existed. All are FICTION.
- That the player got the Mesaba (or any undelivered) warning to the bridge, or changed any message, time or order.
- That the player added seats, filled a boat beyond its documented load or raised the number saved.
- That third class was deliberately locked below.
- Exact launch times or loads stated as certain; they are contested.
- New York or GMT times mixed with ship's time.
- The last tune, "first SOS", or "unsinkable" claims.

## 12. Open questions

- **Everything marked UNVERIFIED.** It needs confirming against the US Senate and British inquiry transcripts (titanicinquiry.org) and Encyclopedia Titanica, then upgrading to DOCUMENTED. Priority, in order:
  1. Ice warnings and Mesaba timing.
  2. The Phillips and Evans wording.
  3. Boat 7 and Boat 1 loads.
  4. Lightoller and Murdoch practice.
  5. Hart's testimony on third-class routes.
  6. Scotland Road's deck and side.
  7. The A Deck screen and Boat 4.
  8. Carpathia's pickup times.
- **Ship's-time offset** from GMT and New York on 14-15 April (`et_rockets`).
- **A full launch-order model.** Choose one consistent model from `et_lifeboats_1` and Encyclopedia Titanica.
- **Third-class corridor finishes and lighting**, and the exact gate positions on E, D and C Decks (deck plans and inquiry testimony).
- **When the lights failed**, and the break-up geometry. Only needed if the skippable sinking is shown at a distance.
- **Who physically carried Marconi messages to the bridge**, to frame the messenger role.

## Sources

Full citations (title, publisher, URL, accessed 2026-10-03) are in `titanic_1912.json` under `sources`. All of them come from the earlier research note; none could be newly checked in this pass.
- **Royal Museums Greenwich:** RMS Titanic facts; Research guide D1 fact sheet.
- **British Wreck Commissioner's Inquiry** (titanicinquiry.org): Report, "Weather conditions".
- **Encyclopedia Titanica:**
  - Rockets, Lifeboats, and Time Changes;
  - 12.45am: A Time to Go!;
  - Lifeboats, Launch Times, List and Trim, Part 1;
  - The sailor and the countess: Lifeboat No. 8;
  - Olympic & Titanic: Passenger Accommodation.
- **Encyclopaedia Britannica:** April 15: The Titanic's Final Moments and Messages.
- **Titanic Belfast:** Food for All Classes.
- **Primary sources still to read:** US Senate Inquiry and British Wreck Commissioner's Inquiry testimony, especially Bride, Evans, Fleet, Lightoller, Boxhall, Hart, Cottam and Rostron.
