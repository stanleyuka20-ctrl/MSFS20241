# Chapter research: Hiroshima, the morning of 6 August 1945

The machine-readable version is `hiroshima_1945.json`. It uses the same fact IDs and source keys as this file. The older, broader note is `research_notes_hiroshima_1945.md`. Its depiction guidance is kept and strengthened in section 8.

**Status tags:** **[DOCUMENTED]** means a cited source supports it. **[RECONSTRUCTION]** means it is plausible but not a specific recorded fact. **[FICTION]** means it is a game invention.

**Verification caveat (read first).**
- **No new web verification was possible in this pass.** The session's web-search budget ran out during the Pompeii research. Direct page fetches were blocked for every Hiroshima reference host tried: hpmmuseum.jp, city.hiroshima.lg.jp, hiroshimapeacemedia.jp, rerf.or.jp, ahf.nuclearmuseum.org, hiro-tsuitokinenkan.go.jp and Wikipedia.
- Every DOCUMENTED item comes from sources listed in `research_notes_hiroshima_1945.md`. Those sources were accessed on 2026-10-03 and checked against search-engine summaries of the official pages, not full reads.
- Items this brief asked for that the older notes did not cover are tagged RECONSTRUCTION and listed in section 10. They include the Hiroden girls' school, Ninoshima, relief stations, temperature, Korean victim numbers, death-toll ranges, clothing, rationing and fire-water tanks.
- **This file must be re-verified against the Hiroshima Peace Memorial Museum (HPMM) and the City of Hiroshima before anything ships.** All times are Japan time.

---

## 1. Corrections to the premise

1. **The 7:09 alert and 7:31 all-clear are correct.** It was a **yellow** alert, triggered by a single weather-reconnaissance B-29. After the all-clear, people went to work and school as normal. Do not play a siren at 8:15. [DOCUMENTED: `alert_0709`, `all_clear_0731`]
2. **Clear weather is correct.** The weather plane's report of clear skies over the primary target is what decided the target. **Temperature is not verified.** "Hot, humid midsummer morning" is RECONSTRUCTION; no number should appear on screen until it is sourced. [DOCUMENTED: `weather_clear`; RECONSTRUCTION: `temperature`]
3. **Mobilised students: ages about 12-14.** They were upper-elementary and first- and second-year junior high pupils, working alongside volunteer citizen corps of men in their 40s and women. About 8,400 students were at demolition sites, and about 6,300 died. [DOCUMENTED: `demolition_work`, `demolition_toll`]
   - These children can be shown alive and working before 8:15. Their fate is given only in memorial text, never shown or implied in the scene.
4. **Streetcar girls: partly verified.** A Chugoku Shimbun profile documents a woman conductor on the first streetcar after the bombing. The Hiroden girls' school (conductors *and* drivers, ages, numbers) is RECONSTRUCTION here. Show girl conductors; do not put a schoolgirl at the controls until the driver detail is confirmed. [DOCUMENTED: `student_conductor`; RECONSTRUCTION: `hiroden_school`]
5. **Death toll.** "About 140,000 by the end of 1945", out of about 350,000 people present, is the City of Hiroshima's figure, and the game should use it. Ranges from other estimates were not verified; do not quote a range. [DOCUMENTED: `death_toll`; RECONSTRUCTION: `death_toll_ranges`]
6. **Hypocentre and aiming point are correct.** The bomb detonated about 600 m above Shima Hospital. The aiming point was the T-shaped Aioi Bridge, and the burst was about 160 m south-east of the Industrial Promotion Hall. [DOCUMENTED: `detonation`, `aiming_point`, `dome_distance`]
7. **Black rain fell mainly north-west.** A neighbourhood south-east of the centre would not have had it overhead. Black rain is referenced in the epilogue text, not staged. [DOCUMENTED: `black_rain`]
8. **Relief: Ujina and the Akatsuki corps are verified; Ninoshima and other stations are not.** The Army Marine HQ at Ujina began relief on the day itself. Ninoshima's role, and the dates teams arrived from outside, are RECONSTRUCTION. The fictional relief station should sit on the south-east edge of the city, toward Ujina. [DOCUMENTED: `akatsuki_relief`; RECONSTRUCTION: `ninoshima`, `relief_stations`]

## 2. Recommended location and distance

**Recommendation: a fictional neighbourhood about 3 km south-east of the hypocentre, between the city centre and Ujina.** Give it an invented name, not a real district's. [FICTION: `fiction_location`; damage figures DOCUMENTED: `heat_blast`]

| Distance | City of Hiroshima damage data | Trade-off for this chapter |
|---|---|---|
| Under 2 km | Nearly everything destroyed by blast and fire | Not navigable. No way to show it without bodies or injury. **Reject.** |
| 2-2.5 km | Edge of near-total destruction | Severe damage and many badly injured people. Hard to stay non-graphic. Fires quickly become the citywide blaze. |
| **About 3 km (recommended)** | Poles and trees charred within about 3 km; exposed skin burned up to about 3.5 km | Houses damaged and partly collapsed, tiles and glass down, fires starting. Streets passable for a short time. Survivors walking out of the centre would pass through. Fits the walk toward Ujina relief. **Survivors here would still have burns.** The game handles this by framing (section 8), not by moving the location. |
| 4 km and beyond | Lighter damage | Easier to keep non-graphic, but reads as the outskirts. Weaker connection to the documented relief effort. |

- **Why south-east:** the relief route toward Ujina is documented, and black rain fell mainly north-west, so it does not need to be staged.
- **Why not the centre (Nakajima, Hondori):** use them only in the pre-8:15 sequence if the design wants the documented streets. The player must be withdrawn well before 8:15 and must never be near the hypocentre at 8:15.

## 3. Timeline (Japan time)

| Time | Event | Tag / sources |
|---|---|---|
| Before dawn | Weather B-29s leave Tinian; the Enola Gay and two observation planes follow | DOCUMENTED `weather_planes` |
| 7:09 | Yellow air-raid alert (weather plane over the city) | DOCUMENTED `alert_0709` |
| 7:31 | Alert lifted; breakfast, commute; students and volunteers gather at demolition sites | DOCUMENTED `all_clear_0731` |
| 8:15 | Detonation about 600 m above Shima Hospital | DOCUMENTED `detonation` |
| About 30-45 min later until about 3 p.m. | Black rain, mainly to the north-west; most widespread around 10 a.m. | DOCUMENTED `black_rain` |
| Rest of the day | Fires join into a citywide blaze; the Akatsuki corps from Ujina fights fires and carries and treats the injured | DOCUMENTED `conflagration`, `akatsuki_relief` |
| 9 August | Streetcars run between Koi and Tenma-cho; free rides for survivors | DOCUMENTED `streetcar_restart` |
| End of 1945 | About 140,000 dead | DOCUMENTED `death_toll` |

- [RECONSTRUCTION] US records often use Tinian time (one hour ahead). Use Japan time only. (`time_zones`)

## 4. The city before 8:15

- [DOCUMENTED] Nakajima-hon-machi was the commercial and cultural centre, with cinemas, cafes, restaurants and bell-shaped street lamps. About 160 retailers were still trading on Hondori in August 1945 (confirm). (`nakajima`, `hondori`)
- [DOCUMENTED] The Aioi Bridge was T-shaped after its 1932-34 rebuild and carried streetcar tracks. (`aiming_point`)
- [DOCUMENTED] The Industrial Promotion Hall (Jan Letzel, 1915) was 25 m high, with a five-storey tower and oval dome. (`dome_building`)
- [DOCUMENTED] Firebreak demolition had been going on since November 1944. (`demolition_work`)
- [DOCUMENTED] Clay roof tiles melted within about 600 m, which confirms tiled roofs. (`roof_tiles`) [RECONSTRUCTION] Most homes were wooden, one or two storeys, in narrow lanes. (`houses`)
- [RECONSTRUCTION] The Ota River delta, split into several channels with many bridges. (`rivers_delta`)
- [RECONSTRUCTION] **Clothing:** monpe trousers for women; khaki national civilian uniform (kokuminfuku) with puttees for men; school uniforms with name tags for students; padded air-raid hoods (bokuzukin) carried over the shoulder. (`clothing`)
- [RECONSTRUCTION] **Rationing:** rice and staples rationed and short; rice stretched with barley or other grains. (`rationing`)
- [RECONSTRUCTION] **Fire-water tanks** and buckets in the street for neighbourhood fire drills. (`fire_water_tanks`)
- [DOCUMENTED] **Foreign residents:** the dead included people from Korea, Taiwan and mainland China. [RECONSTRUCTION] Korean numbers vary widely by source; give no figure until sourced. (`death_toll_who`, `korean_victims`)

## 5. What was seen from a distance (for the protected viewpoint)

All DOCUMENTED. Use these as the factual basis for a respectful distant view.

- **Flash and sound.** Survivors called it *pika-don*: a blinding flash (*pika*), then a huge boom (*don*). (`pika_don`)
- **About 6 km:** Seiso Yamada photographed the cloud about two minutes after the explosion and remembered it as "blood red". (`cloud_6km`)
- **About 20 km, Kure:** a man at the Naval Arsenal photographed a huge cloud swirling up in the western sky. (`cloud_distant`)
- **About 30 km, Kake:** people saw it glinting silver in the sun. It was visible across the prefecture and into Shimane. (`cloud_distant`)
- **Height:** about 16 km. (`cloud_height`)

**Recommended viewpoint:** a hillside about 20 km away, consistent with the Kure accounts (the exact place is FICTION). Sequence:
1. A white-out of the screen, not a fireball.
2. Silence.
3. A long, delayed, low boom.
4. The cloud rising over distant hills, seen small, held briefly, in muted colour.
5. Text: *"By the end of 1945, about 140,000 people had died."*

The scanner entry `scan_distant_cloud` pairs the sight with the death toll so it cannot be read as spectacle.

## 6. Scanner entries (13)

The full text is in the JSON `scanEntries` array.

| ID | Title | Status | Sources |
|---|---|---|---|
| scan_streetcar | Streetcar | documented | hpmm_relief, hpmc_sasaguchi |
| scan_demolition_site | Firebreak Demolition Site | documented | hpmm_demolition |
| scan_alert_board | Neighbourhood Notice Board | documented | hiro_city_booklet, hpmm_exhibit_doc |
| scan_fire_water_tank | Fire-Water Tank | reconstruction | none |
| scan_air_raid_hood | Air-Raid Hood | reconstruction | none |
| scan_monpe | Monpe Work Trousers | reconstruction | none |
| scan_tile_roof | Wooden House with Tile Roof | reconstruction | none |
| scan_ration_book | Rice Ration Book | reconstruction | none |
| scan_dome_postcard | Postcard: Industrial Promotion Hall | documented | hiro_city_dome, unesco_dome |
| scan_city_map | City Map | documented | hpmc_aioi |
| scan_river_steps | River Embankment Steps | reconstruction | none |
| scan_relief_station | Relief Station | documented (station fictional) | hiro_city_realities, hpmm_relief |
| scan_distant_cloud | The Cloud over Hiroshima | documented | hpmc_yamada, hpmc_cloud_photo, hpmc_cloud_height, hiro_city_deaths |

Six entries are RECONSTRUCTION because their sources were not reachable this pass. They are the first to re-verify (section 10).

## 7. What the game must NOT claim

- That the neighbourhood, the resident, the survivors or the relief station existed. All are FICTION (`fiction_location`, `fiction_premise`).
- That the player, or anyone, could have warned the city, changed the outcome or "saved" people in a way that implies history could change.
- A temperature, a Korean death figure, a death-toll range or a Ninoshima casualty figure, until sourced.
- That schoolgirls drove streetcars on 6 August, until confirmed.
- That a siren sounded at 8:15.
- Any reference to a real victim by name as a character, including at Shima Hospital, a specific school or a demolition site.

## 8. Sensitive-content guidance (mandatory)

This chapter depicts the killing of about 140,000 people. Survivors (hibakusha) are still alive, and their families live in Hiroshima today. The chapter is an act of witness, not a set-piece.

**A. The viewpoint.**
1. The player is a clearly fictional, protected observer. The temporal device withdraws them before 8:15, to a distant hillside (section 5). The player never experiences the detonation in the city.
2. The player is never placed with, or framed as, the people who planned or carried out the bombing. There is no bomber point of view and no aerial view of the city at 8:15.

**B. No graphic injury, no bodies.**
1. Show no burns, wounds, skin, eyes, blood, keloids, hair loss or radiation sickness at any distance.
2. Show no bodies, no "shadows" of people on stone, and no rivers or water tanks with people in them.
3. Survivors in the aftermath appear dusty, exhausted, frightened and walking. Injuries are never shown and are conveyed only by the help they accept (being led, sitting down, being given water) and by a short attributed testimony line (section 9).
4. Absence can carry meaning: an empty street, a stopped clock, a dropped lunch box, a school bag left on a wall. Use these sparingly. Do not copy specific museum artefacts without the museum's permission.

**C. No spectacle of the explosion.**
1. No fireball, no slow motion, no shockwave sweeping toward the camera, no destruction physics.
2. **Never frame the cloud as beautiful.** No golden-hour lighting, no swelling or uplifting music, no lingering shot, no photo mode, no screenshot prompt. Hold it briefly, small and distant, in muted colour, and follow it immediately with the death-toll text.
3. Avoid the words "awe", "magnificent" and "beautiful" in any line about the bomb or the cloud. Quote witnesses accurately ("blood red", "glinting silver") with attribution, never as the game's own judgement.

**D. Never gamify the bombing.**
1. No timers, scores, collectibles, achievements, trophies, fail states or "too slow" outcomes tied to the bombing, to victims or to survivors.
2. The aftermath has no countdown. A survivor the player does not reach is never shown dying. The scene simply continues, and the epilogue speaks of people in general.
3. No scanner entry, collectible or reward on an injured person.
4. The 8:15 sequence gives no reward or completion stat.

**E. Skippable and signposted.**
1. A content note before the chapter names the subject plainly.
2. The 8:15 sequence and the aftermath can each be skipped with one button. Skipping goes to a calm text card summarising what happened, with no penalty and no missed content flag.
3. Provide a "quiet mode" that also removes the aftermath and goes straight to the epilogue.

**F. Children.** Mobilised students and children are shown alive and ordinary before 8:15. Their fate is given only in memorial text, for example: *"About 8,400 students were working at demolition sites that morning. About 6,300 of them died."* (`demolition_toll`)

**G. Consultation.**
- Before writing final text, consult HPMM and the City of Hiroshima on content and wording.
- Ask for their written guidance on presenting the bombing; it was not obtainable in this pass.
- Also consult hibakusha organisations and the Hiroshima National Peace Memorial Hall for the Atomic Bomb Victims.
- Credit them in the game if they agree.

**H. Foreign victims.** Acknowledge Korean, Taiwanese and Chinese victims in the epilogue text, and Korean residents in the pre-8:15 street, without stereotype.

## 9. Testimony: how a game may reference it

- **Preferred form:** a short attributed quote (one phrase or one sentence) or an attributed paraphrase. Name the speaker and the collection, for example *"Seiso Yamada, about 6 km away, remembered the cloud as 'blood red' (Chugoku Shimbun, Survivors' Stories)."*
- **Never** put words in a real survivor's mouth, combine testimonies into a composite voice, or have a fictional NPC recite real testimony as their own.
- Get permission for any quotation beyond a short phrase, and for any recorded voice or image. Rights belong to the speaker, their family or the collection.
- Testimony is placed in quiet moments, such as the epilogue and the relief-station scanner entries, never as background chatter or during gameplay tension.
- **Citable collections:** [DOCUMENTED: `testimony_collections`]
  - Chugoku Shimbun / Hiroshima Peace Media Center, the *Survivors' Stories* series (examples: `hpmc_yamada`, `hpmc_sasaguchi`).
  - Atomic Heritage Foundation / National Museum of Nuclear Science & History, *Voices of the Manhattan Project* oral histories (example: `ahf_ogura`, Keiko Ogura).
  - Hiroshima Peace Memorial Museum (testimony and memoir holdings; specific pages not reachable this pass).
  - Hiroshima National Peace Memorial Hall for the Atomic Bomb Victims (memoirs and testimony videos; not reachable this pass, so no URL is given here).
- **How the museums present testimony:** not verified in this pass. Ask HPMM and the Peace Memorial Hall directly (section 10) and follow their guidance over this file.

## 10. Open questions (re-verify before shipping)

1. Every DOCUMENTED item: re-check on the live HPMM and City of Hiroshima pages. Nothing was re-read in this pass.
2. Hiroden girls' school: opening year, students' ages and numbers, and whether students drove as well as conducted on 6 August. Ask the Hiroshima Electric Railway archive and HPMM.
3. Temperature and humidity at 8 a.m. on 6 August 1945 (JMA / Hiroshima Local Meteorological Observatory).
4. Ninoshima quarantine station: when injured people arrived and how many. Other relief stations and when outside rescue teams arrived.
5. Korean and other foreign victim estimates, with a source the City or HPMM accepts.
6. Death-toll ranges (City of Hiroshima, RERF).
7. 1945 civilian clothing (monpe, kokuminfuku, bokuzukin), rationing and fire-water tanks in Hiroshima specifically. HPMM collection objects are the best reference.
8. Number of river channels and bridges in 1945.
9. HPMM and Peace Memorial Hall guidance on presenting the bombing and on quoting testimony in games.
10. Hondori retailer count (`hondori`).

## Sources

All accessed 2026-10-03, via search summaries (carried over from `research_notes_hiroshima_1945.md`). Full entries are in `hiroshima_1945.json`.

- City of Hiroshima: `hiro_city_realities`, `hiro_city_deaths`, `hiro_city_booklet`, `hiro_city_dome`
- Hiroshima Peace Memorial Museum: `hpmm_exhibit_doc`, `hpmm_demolition`, `hpmm_relief`, `hpmm_before`
- Hiroshima Peace Culture Foundation: `pcf_hypocenter`
- Chugoku Shimbun / Hiroshima Peace Media Center: `hpmc_aioi`, `hpmc_black_rain`, `hpmc_sasaguchi`, `hpmc_nakajima`, `hpmc_yamada`, `hpmc_cloud_height`, `hpmc_cloud_photo`
- Atomic Heritage Foundation / National Museum of Nuclear Science & History: `ahf_tibbets`, `ahf_ogura`
- UNESCO World Heritage Centre: `unesco_dome`
