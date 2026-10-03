# Chapter research: The Somme, October 1916

The machine-readable version is `ww1_somme_1916.json`. It uses the same fact IDs and source keys as this file.

**Status tags:** **[DOCUMENTED]** means a cited source supports it. **[RECONSTRUCTION]** means it is plausible and fits the evidence but is not a specific recorded fact. **[FICTION]** means it is a game invention.

**Verification caveat (read first).** All sources were accessed on 2026-10-03. The sandbox network policy blocked direct page fetches for every reference host I tried: IWM, NAM, Britannica, CWGC, Wikipedia, Long, Long Trail, Project Gutenberg and archive.org. Every DOCUMENTED item was checked against search-engine result summaries of the cited page, not a full read of it. Before shipping, a human should open each URL and confirm the wording. Wikipedia, Great War Forum and commercial sites are marked as tertiary or low reliability. They are used only alongside a stronger source, or for reconstruction items.

---

## 1. Corrections to the chapter premise

1. **Army Book 152 is not the message form.** [DOCUMENTED: `nli_ab152`, `ncl_ab152`, `royalsignals_forms`, `wartimecanada_ab153`]
   - AB 152 was the *Correspondence Book (Field Service)*, a squared-paper carbon-copy notebook used for notes, sketches and records.
   - The **"Messages and Signals"** form was **Army Form C.2121**. It was issued in pads and bound into the **Army Book 153 "Field Message Book"**.
   - Rename the prop to *Army Form C.2121 "Messages and Signals"*. An AB 152 can still appear as a separate notebook prop, for example a signaller's or medical officer's record book.
2. **Gas protection in October 1916 was changing over.** [DOCUMENTED: `awm_ph`, `awm_sbr`, `iwm_sbr_story`]
   - The PH helmet was standard by July 1916.
   - The Small Box Respirator began to be issued from about August 1916, and issue was complete by early 1917.
   - Showing the PH helmet is correct. A few SBRs would also be accurate.
3. **The Brodie helmet is correct for October 1916.** About a million were in service by July 1916. [DOCUMENTED: `nam_brodie`]
   - Do not call every helmet a "Mk I" in on-screen text unless the art matches the 1916 Mk I (manganese steel with a separate rim). "Brodie pattern steel helmet" is the safe label.
4. **Clocks.** British Summer Time ended on 1 October 1916, so October dawn and dusk stand-to fall on GMT. [DOCUMENTED that BST ended then: `wiki_bst`; the stand-to times are a RECONSTRUCTION]
5. **Front-line form.** The textbook trench system is right for established sectors. In the autumn advance, however, many front lines were hastily joined shell holes and shallow new trenches. [RECONSTRUCTION, consistent with `iwm_somme_final` and `wfa_guillemont`]
   - A "fictional sector" can reasonably mix an older, well-built support line with a rough front line.
6. **Ruined villages.** By September 1916, villages in the battle zone such as Guillemont and Ginchy were flattened into heaps of rubble and brick dust. [DOCUMENTED: `wfa_guillemont`]
   - A recognisable "ruined farm" works best a little behind the front line. Show it as roofless walls and rubble with an intact vaulted cellar, not as a standing house.
7. **Whale oil was real but went out of favour.** It was later thought undesirable because it trapped moisture against the skin. [DOCUMENTED: `iwm_whales`; the later doubts appear in contemporary medical papers seen in search results]

## 2. Battle outline and October conditions

- **[DOCUMENTED]** The battle ran from 1 July to 18 November 1916. It was a joint British and French offensive. The first day cost over 57,000 British casualties, including 19,240 killed, and the maximum British advance was about seven miles. (`iwm_somme`)
- **[DOCUMENTED]** In October and November the weather broke: rain, then sleet and snow. The final phase was an attempt to take a few more German positions. Beaumont Hamel fell in mid-November and the battle closed. (`iwm_somme`, `iwm_somme_final`)
- **[DOCUMENTED]** Operations in October 1916 (general level only):
  - The **Battle of Le Transloy**, by Fourth Army, from about 1 to 18-20 October.
  - The **Battle of the Ancre Heights**, by Reserve Army, from 1 October to 11 November. This includes the Canadian Corps' attacks on Regina Trench, which began in cold rain on 1 October.
  - The costly, failed **attacks on the Butte de Warlencourt**, by the 47th (London) Division with the 23rd and 41st Divisions on its flanks.
  - Sources: `canada_ancre_heights`, `wiki_transloy`, `wiki_ancre_heights`, `wiki_butte`.
- **[DOCUMENTED]** Frequent heavy rain turned roads into "rivers of mud", grounded aircraft and forced attacks to be postponed. Moving guns and supplies forward over the shell-churned ground was extremely difficult. (`canada_ancre_heights`, `iwm_somme_final`)
- **[DOCUMENTED]** A NAM-held account of 20 October 1916 describes being "out in mud and pouring rain, sopping wet through all day, stretcher bearing". This is a direct match for the chapter's mood. (`nam_eric_hall`)
- **[FICTION]** The player's battalion, sector, trench names, farm and every named character.

## 3. Trench system layout

| Element | Notes | Tag / source |
|---|---|---|
| Front / support / reserve lines | Parallel lines joined by communication trenches | DOCUMENTED `wfa_terms`, `smith_1917` |
| Sap | Narrow trench pushed out at an angle from the main trench, for listening posts | DOCUMENTED `wfa_terms` |
| Traverses and fire bays | Crenellated plan that limits enfilade fire and shell blast. One 1917 manual gives fire bays of 12-18 ft and traverses of about 9 x 9 ft | DOCUMENTED `wfa_terms`, `smith_1917` |
| Fire step | Ledge for firing and sentry duty. The 1911 *Manual of Field Engineering* reportedly puts the fire-step top 4 ft 6 in below the parapet top | DOCUMENTED (forum citing the manual) `gwf_firestep` |
| Parapet / parados | Raised front and back of the trench, often sandbagged. About 2 ft of earth stops a rifle bullet (1901 MME) | DOCUMENTED `wfa_terms`, `frontlineulster_parapet` |
| Sandbags | About 18 in x 12 in, earth-filled; constant refilling | DOCUMENTED `iwm_voices_trench` |
| Revetting | Corrugated iron with timber A-frames (which also carry duckboards). Hurdles and expanded metal as variety | DOCUMENTED for corrugated iron and A-frames (`iwm_film_engineers`); RECONSTRUCTION for hurdles and expanded metal |
| Duckboards and sumps | Slatted walkways over drainage sump pits along one side of the trench | DOCUMENTED `wfa_terms`, `iwm_duckboard_obj` |
| Dugouts | From "funk holes" to mined dugouts. German Somme dugouts went 10 m or more into chalk; most British front-line shelters were shallower | DOCUMENTED `wfa_terms`, `wfa_guillemont` |
| Gas curtain | Blanket across the dugout doorway | DOCUMENTED `iwm_gas_chamber` |
| Wire | Entanglements on steel corkscrew pickets, screwed in quietly at night | DOCUMENTED `cwm_wire`, `awm_corkscrew` |
| Periscopes | Two-mirror box periscopes, often improvised; army workshops made them from mid-1916 | DOCUMENTED `cwm_periscope` |

**Working dimensions for level design [RECONSTRUCTION]:**
- Floor about 6-8 ft below the parapet top.
- About 3.5-6 ft wide at the top, narrowing toward the bottom. Allow at least about 2 ft at duckboard level for a stretcher.
- Fire step about 18 in deep, set so the parapet top is about 4 ft 6 in above it.
- Fire bays 12-18 ft long, with traverses about 9 ft square.
- A two-man stretcher carry should visibly struggle at traverse corners.

## 4. Geology and spoil

- **[DOCUMENTED]** The Somme is a dissected chalk upland. The upper chalk is frost-shattered and covered by clay-with-flints, loess and loam ("limons des plateaux", sometimes up to 10 m thick). Trench spoil shows white against the darker surface. (`doyle_geology`)
- **[RECONSTRUCTION]** Art direction:
  - Brown loam topsoil over off-white, blocky chalk with dark flints.
  - Grey-white streaks on parapets and crater lips.
  - Milky grey standing water.
  - Sticky, clinging chalk-clay mud on boots, puttees and greatcoat hems.

## 5. Communications

- **[DOCUMENTED]** The Telephone D Mk III was the standard field set. Its buzzer and Morse key let signallers work through noisy lines. (`iwm_signalling_story`, `dva_signallers`)
- **[DOCUMENTED]** Cable was often cut by shells. Signallers, often in pairs, followed the line hand over hand to find and join the break under fire. (`dva_signallers`)
- **[DOCUMENTED]** When lines were down, runners were often the most reliable link but were exposed to fire. Pigeons, lamps and flags were also used. (`cwm_communication`, `nam_comms`)
- **[DOCUMENTED]** The message form was **Army Form C.2121 "Messages and Signals"** (see Corrections). (`royalsignals_forms`, `wartimecanada_ab153`)
- **[RECONSTRUCTION]** For the repair mini-game: find both cut ends, strip the insulation, twist the conductors together, bind the join with tape, then test with the buzzer. Exact 1916 jointing procedure is not verified.

## 6. Medical evacuation

- **[DOCUMENTED]** The chain ran:
  1. Regimental stretcher-bearers carried the wounded to the **Regimental Aid Post**, where the battalion MO did a first assessment.
  2. RAMC Field Ambulance bearers carried them in relays to the **Advanced Dressing Station**. One RAMC source gives this as about 3,000 yards behind, with relays every 600-800 yards.
  3. From there to the **Main Dressing Station**.
  4. Then by motor or horse ambulance to the **Casualty Clearing Station**, the closest point to the front where female nurses served.
  - Sources: `ramc_chain`, `iwm_medicine`, `tna_stretcher`.
- **[DOCUMENTED]** Each battalion had at least 16 stretcher-bearers, at first often bandsmen. They wore a white brassard with a red "SB". (`ramc_chain`, `iwm_sb_brassard`)
- **[DOCUMENTED]** Four bearers were often needed per case, and a carry could be up to about 4 miles. Narrow, fire-stepped trenches and knee- to thigh-deep mud forced bearers into the open under fire. (`awm_med_evac`, `tna_stretcher`)

## 7. Kit

- **[DOCUMENTED]** Khaki Service Dress, with 1908 Pattern web equipment or 1914 Pattern leather equipment as a New Army stopgap. (`iwm_kit`, `iwm_1908_webbing`, `iwm_1914_leather`)
- **[DOCUMENTED]** Brodie steel helmet: about a million in service by July 1916. (`nam_brodie`)
- **[DOCUMENTED]** PH helmet standard; Small Box Respirator issued from about August 1916, complete by early 1917. (`awm_ph`, `awm_sbr`)
- **[DOCUMENTED]** Rum ration of about 2.5 fl oz, in one-gallon "SRD" jars, issued in front of an officer or NCO. (`nam_rumjar`, `wfa_rum`)
- **[DOCUMENTED]** Food: tea, bully beef, Maconochie stew, hard biscuit, jam. Water came up in petrol tins. (`iwm_food`)
- **[DOCUMENTED]** Trench foot measures: dry socks daily and whale oil rubbed into the feet. (`iwm_whales`, `iwm_clean`)

## 8. Artillery from inside the trench

- **[DOCUMENTED]** "Whizz-bang": a shell from a light high-velocity gun (first the German 77 mm) that arrives with almost no warning. (`iwm_whizzbang`, `iwm_slang`)
- **[DOCUMENTED]** Veterans' accounts describe:
  - continuous noise, with heavier shells heard approaching;
  - dugouts shaking, collapsing and having to be dug out;
  - men breaking down under the strain.
  - Source: `iwm_voices_trench`.
- **[DOCUMENTED]** At night, Very lights lit up no man's land. (`wfa_terms`, `cwm_raids`)
- **[RECONSTRUCTION]** Sound and visual design for the bombardment:
  - **Sound:** a low rumble of distant guns, and the rising whistle of heavy shells (the player has time to react). Whizz-bangs give near-instant cracks (no time to react).
  - **Feel:** ground shock through the duckboards, earth and chalk dust falling from dugout ceilings, candle flames guttering.
  - **Smell and sight:** the smell of explosive fumes. Never show explicit wounds.

## 9. Daily routine

- **[DOCUMENTED]** (`cwm_routine`)
  - Stand-to at dawn and dusk.
  - In daylight: sentries on duty while others sleep or work below ground out of snipers' sight.
  - At night: wiring, digging, ration and carrying parties, patrols and raids.

## 10. Picardy villages and farms

- **[DOCUMENTED]** Picardy farms were built around a closed courtyard with barns. Walls were brick, or timber frame filled with torchis (clay-and-fibre cob), and roofs were steep with flat tiles. (`peinetti_torchis`, `fp_picardy`, the latter low reliability)
- **[DOCUMENTED]** By late summer 1916, frontline villages were shelled flat to rubble and reddish dust. Cellars and wells were used as shelters. (`wfa_guillemont`)
- **[RECONSTRUCTION]** The farm cellar:
  - A brick barrel vault with chalk walls, partly blocked by fallen beams and tiles.
  - Reached through a collapsed trapdoor or the cellar steps of a ruined barn.

## 11. Scanner entries (all DOCUMENTED, 35-54 words)

The full text is in the JSON `scanEntries` array. Titles and source keys:

| ID | Title | Sources |
|---|---|---|
| scan_brodie_helmet | Steel Helmet (Brodie pattern) | nam_brodie, iwm_brodie_obj |
| scan_duckboard | Duckboard | wfa_terms, iwm_duckboard_obj |
| scan_field_telephone | Field Telephone (D Mk III) | iwm_signalling_story, dva_signallers |
| scan_message_form | Message Form (Army Form C.2121) | royalsignals_forms, wartimecanada_ab153, cwm_communication |
| scan_periscope | Trench Periscope | cwm_periscope, iwm_periscope_obj |
| scan_sandbag_parapet | Sandbag Parapet | iwm_voices_trench, frontlineulster_parapet, wfa_terms |
| scan_ph_helmet | PH Gas Helmet | awm_ph, awm_sbr |
| scan_screw_picket | Screw Picket and Barbed Wire | cwm_wire, awm_corkscrew |
| scan_stretcher | Field Stretcher | iwm_stretcher_obj, awm_med_evac, tna_stretcher |
| scan_rap | Regimental Aid Post | ramc_chain, iwm_medicine |
| scan_gas_curtain | Dugout Entrance and Gas Curtain | iwm_gas_chamber, wfa_terms, iwm_dugout_1916 |
| scan_very_pistol | Very Pistol and Flares | wfa_terms, cwm_raids |
| scan_corrugated_revetment | Corrugated-Iron Revetment | iwm_film_engineers, doyle_geology |
| scan_rum_jar | Rum Jar (SRD) | nam_rumjar, wfa_rum |

## 12. What the game must NOT claim

- That the battalion, its regiment number, the sector, trench names, the farm, or any character (the stretcher-bearer, the wounded soldier, the diary's owner) existed. In-game text must label them fictional.
- That any real attack, such as the Butte de Warlencourt, Regina Trench or Le Transloy, happened differently, succeeded, or was influenced by the player.
- That the player's message changed the outcome of any operation.
- Real named individuals in invented situations. Do not use names from war memorials or casualty records for fictional characters.
- That "Army Book 152" was the Messages and Signals form.
- Specific casualty numbers for the fictional sector, or specific weather on a specific day unless sourced.
- That every soldier carried a Small Box Respirator in October 1916.
- Medical outcomes or treatments beyond the documented chain. Do not depict surgery or graphic wounds.

## 13. Sensitive-content guidance

- Depict danger through sound, shaking, dust, darkness and the reactions of NPCs. Do not show dismemberment or close-up wounds.
- The wounded soldier: a bandaged leg and a field dressing, shown as pain and exhaustion, not gore.
- Shell shock may be shown respectfully as trembling or freezing, never as comedy.
- The dead may appear only at a distance or covered by groundsheets, if at all.

## 14. Open questions

- Confirm the wording of every DOCUMENTED item on the live pages, because fetches were blocked here.
- Exact British trench dimensions in a 1916 War Office manual (*Notes for Infantry Officers on Trench Warfare*, 1916). The full text was not accessible.
- 1916 field-cable jointing procedure, and cable types such as D3 twisted cable.
- Whether gas curtains were chemically treated in 1916.
- Sunrise and sunset times for the chosen date at about 50.0°N 2.8°E, to time stand-to accurately.

## Sources

Full citations (title, publisher, URL, accessed 2026-10-03) are in `ww1_somme_1916.json` → `sources`. Key institutional sources:
- **IWM:** Battle of the Somme; How did the Battle of the Somme end?; Soldiers' kit; Food; Whales; Keeping clean; Voices: Trench Life; collection objects 30090820, 30060231, 30028459, 30028121, 30025172, 286, 22976.
- **NAM:** The Brodie Helmet; Second Lieutenant Eric Hall; Mudbound rum jar; Communication on the Front Line.
- **Canadian War Museum:** Trench Routine; Communication; Barbed Wire; Trench Periscope.
- **Australian War Memorial:** PH Helmet; Small box respirator; Corkscrew picket; Medical evacuation.
- **UK National Archives:** Medicine on the Western Front.
- **Government of Canada DND:** Ancre Heights.
- **Western Front Association:** Great War Terms; Guillemont; Rum ration.
- **Primary manual:** J. S. Smith, *Trench Warfare* (1917), Project Gutenberg.
- **Geology:** P. Doyle, LSBU Open Research.
