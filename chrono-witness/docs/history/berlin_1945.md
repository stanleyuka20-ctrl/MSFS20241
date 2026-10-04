# Chapter research: Berlin, Friday 18 May 1945

The machine-readable version is `berlin_1945.json`. It uses the same fact IDs and source keys as this file. The older, broader note is `research_notes_berlin_1945.md`.

**Status tags:** **[DOCUMENTED]** means a cited source supports it. **[RECONSTRUCTION]** means it is plausible but not a specific recorded fact, or it could not be checked in this pass. **[FICTION]** means it is a game invention.

**Verification caveat.** Sources were accessed on 2026-10-04 unless marked 2026-10-03.
- The network egress proxy blocked direct page fetches for every reference host tried: bpb, Stiftung Berliner Mauer, museum-digital, gvoon, Wikipedia and Chronik der Mauer.
- DOCUMENTED items were checked against search-engine summaries of the cited pages, not full reads.
- **The session's web-search budget ran out partway through this chapter.** Curfew hours, the U-Bahn restart date, shelter signs, Cyrillic signs, clothing, weather and chalked messages could not be researched. They are tagged RECONSTRUCTION.
- Sources dated 2026-10-03 come from the older note and were not re-checked.
- Keys starting `sec_` are secondary sources and `tert_` are tertiary. Some titles are taken from page headings or URL slugs.
- Confirm the wording on each live page before shipping.

---

## 1. Corrections to the premise

1. **Chosen date: Friday 18 May 1945.** [FICTION, justified by DOCUMENTED dates] (`chapter_date`)
   - The new Soviet ration system began on 15 May and cards were being handed out. This fits the ration-office mission. (`md_ration_card`, `sec_the_berliner`)
   - Radio Berlin had been on air since 13 May (`dhm_kk_timeline`), and tram repairs had started on 13 May (`berlin_de_tram`).
   - It is before Moscow time was ordered (20 May) and before the new city government was presented (19 May). That keeps the scene in the raw first weeks.
   - Mid-May, as planned, is right. Avoid any date after 21 May, when the *Berliner Zeitung* first appeared.
2. **Moscow time was ordered from 20 May, not from the surrender.** [DOCUMENTED: `vobl_1945_p4`, `tert_tz_germany`]
   - Order No. 4 of the Soviet city commandant, dated 20 May 1945, put work in Berlin on Moscow time "until further notice".
   - The tz time-zone database dates the change to 02:00 on 24 May 1945.
   - On 18 May, civilian clocks most likely still showed German summer time (UTC+2), one hour behind Moscow. Soviet units may already have used Moscow time. Two clocks that disagree by an hour is a good, honest detail. [RECONSTRUCTION, `clocks_on_chapter_date`]
3. **The ration card dates are right, with two steps.** [DOCUMENTED]
   - A temporary ration from 5 May (200 g bread, 400 g potatoes, 25 g meat and so on). (`md_ration_card`, `bz_berlin_lebt_auf`)
   - New cards announced on 13 May. (`md_ration_card`, `bz_berlin_lebt_auf`)
   - The five-group system began on 15 May. (`sec_the_berliner`, `berlin_de_ns`)
   - Where cards were collected is not verified. A local district office is a reasonable reconstruction. [RECONSTRUCTION, `card_distribution`]
4. **The bucket chain is not "Trümmerfrauen" yet.** [DOCUMENTED: `pw_truemmerfrauen`, `bpb_treber`]
   - Secondary sources give 1 June 1945 for compulsory rubble work by Berlin women, two weeks after the chapter date.
   - Historian Leonie Treber shows that early post-war clearing relied heavily on conscripted former Nazi Party members and prisoners of war, and that the heroic "rubble woman" was partly a press image.
   - On 18 May, show a small, local neighbourly bucket chain clearing a doorway or courtyard. Do not show an organised, paid women's work gang or use the word "Trümmerfrauen" in dialogue. [RECONSTRUCTION, `bucket_chain_mid_may`]
5. **There was no formal tracing service on Berlin streets yet.** [DOCUMENTED: `pw_suchdienste`]
   - The German Red Cross Suchdienst grew out of 1945 efforts in Flensburg, Hamburg and Munich, using card indexes.
   - In mid-May Berlin, chalked notes on walls and word of mouth are the right tools.
   - The chalk-message practice itself was **not** tied to an archive source in this pass. [RECONSTRUCTION, `chalk_messages`]
   - The related practice of Soviet soldiers writing in chalk and charcoal on the Reichstag in May 1945 is documented. (`bpb_zdes_byl`)
6. **Trams were not running yet near most streets; the U-Bahn was closed or flooded.** [DOCUMENTED: `tert_bvg_history`, `berlin_de_tram`]
   - Tram repairs started on 13 May, and Order No. 6 set out twelve lines to resume.
   - Show a stranded tram under fallen wires, not a working service.
   - A first short U-Bahn shuttle is often dated 14 May, but this was not verified. [RECONSTRUCTION, `ubahn_restart`]
7. **The curfew existed, but its hours are unverified.** Do not show a clock time on screen. [RECONSTRUCTION, `curfew`]
8. **"Plumpe" is fine as dialogue colour only.** The street pumps are well documented. The dialect nickname was not found in a cited source.

## 2. Context

- [DOCUMENTED] The Soviet offensive opened on 16 April 1945. Weidling surrendered the Berlin garrison on 2 May. The German surrender was signed in Karlshorst on 8 May. (`iwm_battle_berlin`, `barch_lagekarte`, `barch_kapitulation`, `nam_may1945`)
- [DOCUMENTED] Berlin was bombed from 1940. About 16 km² of rubble lay across the city (secondary figure). (`berlin_de_ns`, `sec_the_berliner`)
- [DOCUMENTED] About two-thirds of Berlin's roughly 3.1 million people were women. (`pw_truemmerfrauen`)
- [DOCUMENTED] The main daily struggles were hunger, water, a roof overhead and warmth. The old German ration cards became invalid at the surrender. (`berlin_de_ns`, `sec_the_berliner`)

## 3. Water

| Topic | Summary | Tag / sources |
|---|---|---|
| Utilities | Electricity, gas and mains water failed across large parts of Berlin, in places for months | DOCUMENTED `mieterverein_pumps`, `tip_pumps` |
| Street pumps | Old cast-iron pumps, each its own well, were often the only water source. People queued with buckets | DOCUMENTED `mieterverein_pumps`, `tip_pumps` |
| Queues | Civilians queued for hours for food and water | DOCUMENTED `sec_hoxne`, `sec_macmillan` |
| Disease | Water had to be boiled but fuel was scarce. Dysentery and typhus in summer 1945 killed about 3,000 people | DOCUMENTED `mieterverein_pumps`, `tip_pumps` |

## 4. Soviet rule, clocks and media

- [DOCUMENTED] Nikolai Bersarin was the first Soviet city commandant. (`dhm_bersarin`)
- [DOCUMENTED] **Order No. 1** (28 April 1945) announced that all power had passed to the Soviet commandant's office. It was a bilingual Russian and German poster, 47.5 x 63.5 cm, with the date filled in district by district. This is an ideal prop. (`md_order1`)
- [RECONSTRUCTION] Each district had a local Soviet commandant's office (Kommandantura) that issued orders and work demands.
- [DOCUMENTED] The new Magistrat was appointed on 12 May and presented on 19 May, with Arthur Werner as mayor. (`bpb_19_mai_1945`, `berlin_de_mayors`)
- [DOCUMENTED] Bersarin opened soup kitchens and allowed private trade. (`bz_berlin_lebt_auf`)
- [DOCUMENTED] Radio Berlin first broadcast on 13 May. The *Tägliche Rundschau* appeared on 15 May. The *Berliner Zeitung* appeared on 21 May, so it must not be shown. (`dhm_kk_timeline`)
- [DOCUMENTED] A Soviet officer's diary says the Germans all wore white armbands. (`bz_white_armbands`)
- [RECONSTRUCTION] Some white sheets still hang, torn and grey, from windows.
- [RECONSTRUCTION, computed] On 18 May sunrise was about 05:05 and sunset about 21:00 German summer time.
- [RECONSTRUCTION] The weather was not verified. Use a mild late-spring day with dust in the air and trees in leaf, and check Deutscher Wetterdienst records.

## 5. Posters and signs

Use only these:
- Order No. 1 and later commandant's orders (bilingual posters). [DOCUMENTED: `md_order1`, `vobl_1945_p4`]
- Copies of the *Tägliche Rundschau* (from 15 May). [DOCUMENTED: `dhm_kk_timeline`]
- Chalked messages. [RECONSTRUCTION]
- Painted shelter arrows. [RECONSTRUCTION]
- Wooden Cyrillic direction boards. [RECONSTRUCTION]

Avoid these:
- Western Allied signs ("You are leaving the American sector"). The Western Allies arrived in Berlin only in July 1945. (Not verified in this pass; it is well known, but check it.)
- Later SED or Magistrat propaganda.

## 6. Scanner entries (13)

The full text is in the JSON `scanEntries` array. Six are DOCUMENTED. Seven are RECONSTRUCTION because the search budget ran out before they could be sourced.

| ID | Title | Status | Sources |
|---|---|---|---|
| scan_street_pump | Street Water Pump | documented | mieterverein_pumps, tip_pumps |
| scan_water_buckets | Water Bucket and Pail | documented | mieterverein_pumps, tip_pumps |
| scan_ration_card | Ration Card, May 1945 | documented | md_ration_card, sec_the_berliner |
| scan_kommandantura_notice | Commandant's Order | documented | md_order1, vobl_1945_p4 |
| scan_white_armband | White Armband | documented | bz_white_armbands |
| scan_tram | Stranded Tram | documented | berlin_de_tram, tert_bvg_history |
| scan_chalk_messages | Chalked Messages | reconstruction | none |
| scan_volksempfaenger | People's Radio | reconstruction | dhm_kk_timeline, mieterverein_pumps |
| scan_shelter_sign | Air-Raid Shelter Sign | reconstruction | none |
| scan_stirrup_pump | Hand Pump and Sand Bucket | reconstruction | none |
| scan_handcart | Handcart | reconstruction | ghdi_bombed_out |
| scan_cyrillic_sign | Soviet Road Sign | reconstruction | none |
| scan_coal_stove | Tiled Stove | reconstruction | mieterverein_pumps |

## 7. Missions check

| Mission | Verdict |
|---|---|
| Water from a street pump, with a queue | Well supported (DOCUMENTED) |
| Chalked messages; add one for a neighbour | Keep it, but tag RECONSTRUCTION. No formal Suchdienst in Berlin yet |
| Recover papers from a damaged flat | RECONSTRUCTION. Plausible. Papers mattered for new ration cards and registration (not verified) |
| Rubble bucket chain | Keep it small and local. Do not call it Trümmerfrauen work (compulsory from about 1 June) |
| New ration cards at a district office | Date fits (five-group system from 15 May). The office type is RECONSTRUCTION |
| Unexploded shell, area cleared | FICTION event. Keep children out of danger on screen; the shell is found, reported and cordoned off |

## 8. Sensitive-content guidance

- **Sexual violence.** Historians estimate around 100,000 women were raped by Soviet soldiers in Berlin (`berlin_de_ns`, `ghdi_female_survival`).
  - Never depict or imply it in gameplay, dialogue, set dressing or Soviet NPC behaviour.
  - If it is acknowledged at all, do so only in respectful documentary text written with expert advice.
- **Suicides** were widespread in spring 1945. Do not depict or imply them.
- **Nazi symbols.**
  - Show them only in historical context and in line with German law (StGB §86a) and platform rules.
  - Prefer scraped-off or torn-down remains, such as a pale patch where an eagle was removed, to intact symbols.
  - No glorifying framing of the last defenders.
- **Forced labourers, prisoners of war and surviving Jewish Berliners** were in the city.
  - If present, they should be named characters with their own goals (going home, finding family). They are not background or comic relief.
  - The number of forced labourers in Berlin was not verified in this pass.
- **Soviet soldiers** should not be shown as cartoon villains or heroes. Show ordinary soldiers, traffic controllers and sappers doing their jobs.
- **Children and the shell.** Children are startled, then safely moved away. Show no injury.
- **Hunger and disease** can be referenced (thin faces, boiling water) without showing death.

## 9. What the game must NOT claim (fiction boundaries)

- That the tenement, residents, neighbour, district office, sappers or any mission existed. All are FICTION. (`fiction_premise`)
- No real figures on screen: not Bersarin, Weidling or Zhukov.
- No Moscow time on civilian clocks as official fact before 20 May.
- No *Berliner Zeitung*, Western Allied soldiers or signs, or paid Trümmerfrauen gangs on 18 May.
- No working U-Bahn near the scene, and no specific curfew hour.
- No specific weather stated as fact.
- No casualty figures for the fictional street.

## 10. Open questions

- The curfew hours in Soviet-occupied Berlin in May 1945. Check the 1945 *Verordnungsblatt* and the Landesarchiv Berlin.
- The exact first U-Bahn restart date (often given as 14 May 1945) and the first tram line in service. Check BVG and Landesarchiv sources.
- Primary sources for chalked search messages. Check Bundesarchiv picture archive, DHM and Landesarchiv photo collections.
- Where ration cards were collected (Kartenstelle, district office or house warden).
- Whether the Soviet authorities required radios to be handed in in mid-May 1945.
- Deutscher Wetterdienst weather for 18 May 1945.
- Shelter sign lettering (for example "LSR" arrows) in Berlin cellars. Check Berliner Unterwelten or museum collections.
- When the Western Allies arrived in Berlin (believed to be July 1945).

## 11. Sources

All accessed 2026-10-04 via search summaries, except where marked (2026-10-03, carried over).

- `iwm_battle_berlin`: IWM, "The Battle of Berlin: Germany's downfall on the Eastern Front", https://www.iwm.org.uk/history/second-world-war/eastern-front/the-battle-of-berlin-germanys-downfall-on-the-eastern-front (2026-10-03)
- `barch_lagekarte`: Bundesarchiv, "Lagekarte zur Schlacht um Berlin", https://www.bundesarchiv.de/themen-entdecken/online-entdecken/dokumente-zur-zeitgeschichte/lagekarte-zur-schlacht-um-berlin/ (2026-10-03)
- `barch_kapitulation`: Bundesarchiv, "Die deutsche Kapitulation 1945", https://www.bundesarchiv.de/themen-entdecken/online-entdecken/geschichtsgalerien/die-deutsche-kapitulation-1945/ (2026-10-03)
- `nam_may1945`: National Army Museum, "On This Day: May 1945", https://nam.ac.uk/explore/day-may-1945 (2026-10-03)
- `ghdi_female_survival`: GHDI, "Female survival in Berlin in April 1945", https://germanhistorydocs.org/en/nazi-germany-1933-1945/female-survival-in-berlin-in-april-1945-retrospective-account-1950s (2026-10-03)
- `sec_the_berliner`: The Berliner, "Trümmerfrauen: rubble women", https://www.the-berliner.com/berlin/trummerfrauen-rubble-women-history-debris/ (2026-10-03)
- `berlin_de_ns`: Berlin.de, "Berlin in the National Socialist era", https://www.berlin.de/en/history/8481323-8619314-berlin-in-the-national-socialist-era.en.html (2026-10-03)
- `sec_hoxne`: Hoxne local history society, "WW2 The Battle for Berlin" (PDF), https://hoxnehistory.org.uk/WW2%20The%20Battle%20for%20Berlin.pdf (2026-10-03)
- `sec_macmillan`: Macmillan, *Berlin: Life and Death in the City at the Center of the World*, excerpt, https://us.macmillan.com/books/9781250277510/berlinlifeanddeathinthecityatthecenteroftheworld (2026-10-03)
- `ghdi_bombed_out`: GHDI, "After the storming of Berlin: bombed-out people on the street (May 1, 1945)", https://germanhistorydocs.org/en/occupation-and-the-emergence-of-two-states-1945-1961/after-the-storming-of-berlin-bombed-out-people-on-the-street-may-1-1945.pdf
- `mieterverein_pumps`: Berliner Mieterverein, "Berliner Wasserpumpen: Trinkwasser per Muskelkraft", https://www.berliner-mieterverein.de/magazin/online/hintergrund/berliner-wasserpumpen-trinkwasser-per-muskelkraft-042024.htm
- `tip_pumps`: tip Berlin, "Straßenbrunnen in Berlin", https://www.tip-berlin.de/stadtleben/strassenbrunnen-berlin-wasserpumpen-geschichte/
- `vobl_1945_p4`: Verordnungsblatt der Stadt Berlin 1945, p. 4 (Order No. 4, 20 May 1945), transcription at gvoon.de, https://www.gvoon.de/art/dokumente/1945/verordnungsblatt-vobl-berlin-1945/pdf/verordnungsblatt-vobl-berlin-1945-seite_004.pdf
- `tert_tz_germany`: tz mailing list, "Completed timezone history of Germany", https://mm.icann.org/pipermail/tz/2011-August/033787.html
- `cma_baltermants`: Cleveland Museum of Art, Dmitri Baltermants, "Resetting German Clocks Forward to Moscow Time, May 1945", https://www.clevelandart.org/art/2014.561
- `md_order1`: museum-digital:berlin, Order No. 1 poster, https://berlin.museum-digital.de/pdf/object/71177.pdf?lang=en
- `md_ration_card`: museum-digital:berlin, food ration card, May 1945 (Museum Berlin-Karlshorst), https://berlin.museum-digital.de/pdf/object/81605.pdf?lang=en
- `bz_berlin_lebt_auf`: Berliner Zeitung, "Berlin lebt auf", https://www.berliner-zeitung.de/article/nicht-veroeffentlichen-teil7-wurst-wider-wurst-83752
- `bz_white_armbands`: Berliner Zeitung, "28. April 1945 … Die Deutschen tragen alle weiße Armbinden", https://www.berliner-zeitung.de/article/28-april-1945-hitler-erfaehrt-von-der-kapitulation-die-deutschen-tragen-alle-weisse-armbinden-46686
- `dhm_bersarin`: DHM LeMO, "Nikolai Bersarin 1904-1945", https://www.dhm.de/lemo/biografie/nikolai-bersarin
- `bpb_19_mai_1945`: bpb, Deutschland-Chronik "19. Mai 1945", https://www.bpb.de/themen/zeit-kulturgeschichte/deutschland-chronik/131273/19-mai-1945/
- `berlin_de_mayors`: Berlin.de, "Besatzung, Spaltung und Blockade 1945-1948/49", https://www.berlin.de/rbmskzl/politik/senat/buergermeistergalerie/artikel.4559.php
- `dhm_kk_timeline`: DHM, Kalter Krieg exhibition timeline, https://www.dhm.de/archiv/ausstellungen/kalter_krieg/aet_02.htm
- `berlin_de_tram`: Berlin.de, "150 Jahre Straßenbahn", https://www.berlin.de/aktuell/ausgaben/2015/dezember/berliner-ereignisse/150-jahre-strassenbahn-404916.php
- `tert_bvg_history`: FundingUniverse, "Berliner Verkehrsbetriebe (BVG) History", https://www.fundinguniverse.com/company-histories/berliner-verkehrsbetriebe-bvg-history/
- `bpb_treber`: bpb, Leonie Treber, "Mythos Trümmerfrau", https://www.bpb.de/shop/zeitschriften/apuz/204282/mythos-truemmerfrau-deutsch-deutsche-erinnerungen/
- `pw_truemmerfrauen`: Planet Wissen, "Trümmerfrauen", https://www.planet-wissen.de/geschichte/deutsche_geschichte/nachkriegszeit/truemmerfrauen-114.html
- `pw_suchdienste`: Planet Wissen, "Suchdienste nach 1945", https://www.planet-wissen.de/geschichte/deutsche_geschichte/nachkriegszeit/suchdienste-nach-1945-100.html
- `bpb_zdes_byl`: bpb, "Ich war hier / Zdes byl", https://www.bpb.de/shop/buecher/schriftenreihe/290688/ich-war-hier-zdes-byl/
