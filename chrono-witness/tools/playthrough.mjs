// Automated playthrough of "The Runner" (Western Front 1916).
// Drives the real game simulation headlessly: walks routes with collision, aims at and uses
// interactables, answers dialogue and verifies every mission stage, checkpoint restore and saving.
// Usage: node tools/playthrough.mjs [baseUrl] [screenshotDir]
import { launch, waitFor } from './browser.mjs';
import { installHarness } from './harness.mjs';
import fs from 'node:fs';

const base = process.argv[2] || 'http://localhost:5173/';
const shots = process.argv[3] || '';
if (shots) fs.mkdirSync(shots, { recursive: true });
const { browser, page, logs } = await launch({ width: 960, height: 540 });
const results = [];
const check = (name, ok, info = '') => {
  results.push({ name, ok, info });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${info ? ' — ' + info : ''}`);
};
const shot = async (name) => {
  if (!shots) return;
  await page.evaluate(() => window.__game.renderOnce());
  await page.screenshot({ path: `${shots}/${name}.png` });
};

try {
  await page.goto(base);
  await waitFor(page, () => window.__game && document.querySelector('.title-logo'), 180000);
  await page.evaluate(() => localStorage.removeItem('chrono-witness.save.v1'));
  await page.evaluate(() => window.__game.save.resetAll());
  await page.evaluate(() => window.__game.travelTo('ww1_somme_1916', false));
  await waitFor(page, () => ['playing', 'cinematic'].includes(window.__game.state), 400000);
  await page.evaluate(() => (window.__game.automationHold = true));
  await installHarness(page, 'runner');
  check('Chapter loads', true, await page.evaluate(() => `issues: ${window.__game.assets.issues.length}`));
  // skip intro cinematic (hold Enter)
  await page.evaluate(() => {
    const g = window.__game;
    g.input.simulate('Enter', true);
    g.step(1.2);
    g.input.simulate('Enter', false);
    g.step(0.2);
  });
  check('Intro cinematic skippable', await page.evaluate(() => window.__game.state === 'playing'));
  await shot('p01-arrival');
  const start = await page.evaluate(() => window.__H.pos());
  check('Spawned in Fleet Street on the trench floor', start[1] < -1.5, JSON.stringify(start));

  // --- Stage 1: report to Hollis
  let r = await page.evaluate(() => window.__H.walkTo(-6.3, 4.3));
  check('Walk Fleet Street to the company dugout', r.ok, JSON.stringify(r));
  r = await page.evaluate(() => window.__H.use('talk_hollis'));
  check('Talk to Sergeant Hollis', r.ok, JSON.stringify(r));
  let said = await page.evaluate(() => window.__H.say([1, 2]));
  check('Hollis dialogue gives the message', await page.evaluate(() => window.__game.facts.hasItem('message')), said.join(' / '));
  check('Stage advanced to "carry"', (await page.evaluate(() => window.__H.stage())) === 'carry');
  check('Checkpoint saved (support_line)', await page.evaluate(() => window.__game.save.data.chapters.ww1_somme_1916?.checkpoint?.id === 'support_line'));

  // optional: Kemp's repair kit
  r = await page.evaluate(() => window.__H.walkTo(8, 7.6));
  check('Enter signals dugout (down the passage)', r.ok, JSON.stringify(r));
  r = await page.evaluate(() => window.__H.use('talk_kemp'));
  check('Talk to Kemp', r.ok, JSON.stringify(r));
  said = await page.evaluate(() => window.__H.say([1]));
  check('Optional task "A Thread of Wire" activated', (await page.evaluate(() => window.__H.missionState('phone_line'))) === 'active', said.join(' / '));
  // scan the telephone while here
  r = await page.evaluate(() => window.__H.scan('obj_telephone'));
  check('Scanner records the field telephone', await page.evaluate(() => window.__game.facts.get('scan.scan_field_telephone')), JSON.stringify(r));
  await shot('p02-signals-dugout');

  // --- Pall Mall: find the cable break and splice it
  r = await page.evaluate(() => window.__H.walkTo(-8.4, -9.0));
  check('Walk up Pall Mall to the cable break', r.ok, JSON.stringify(r));
  r = await page.evaluate(() => window.__H.use('cable_break'));
  const r2 = await page.evaluate(() => window.__H.use('cable_break'));
  await page.evaluate(() => window.__game.step(3));
  check('Cable break found and spliced (optional complete)', (await page.evaluate(() => window.__H.missionState('phone_line'))) === 'completed', JSON.stringify([r, r2]));

  // --- Barrage
  r = await page.evaluate(() => window.__H.walkTo(-9.6, -21.2));
  await page.evaluate(() => window.__game.step(0.3));
  check('Barrage triggers on Pall Mall', (await page.evaluate(() => window.__H.stage())) === 'barrage', JSON.stringify(r));
  const modal = await page.evaluate(() => [...document.querySelectorAll('.modal-layer button')].map((b) => b.textContent).join(' | '));
  check('Intense-sequence prompt offers a skip', modal.includes('Skip'), modal);
  await page.evaluate(() => window.__H.clickButton('Experience it'));
  await page.evaluate(() => window.__game.step(1.0));
  check('Danger indicator visible', await page.evaluate(() => !document.querySelector('.danger').classList.contains('hidden')));
  await shot('p03-barrage-exposed');
  r = await page.evaluate(() => window.__H.walkPoints([[-8.4, -26], [-7.4, -26.2], [-5.6, -26.3]]));
  await page.evaluate(() => window.__game.step(1));
  check('Reach the shelter in time', await page.evaluate(() => window.__game.facts.get('zone.shelter')), JSON.stringify(r));
  await shot('p04-shelter');
  await page.evaluate(() => window.__game.step(26));
  check('Bombardment ends; Pall Mall collapses', await page.evaluate(() => window.__game.facts.get('event.barrage_done')) && (await page.evaluate(() => window.__game.world.colliders.find((c) => c.id === 'collapse').enabled)));
  check('Stage "reroute" + shelter checkpoint', (await page.evaluate(() => window.__H.stage())) === 'reroute' && (await page.evaluate(() => window.__game.save.data.chapters.ww1_somme_1916.checkpoint.id === 'shelter')));
  r = await page.evaluate(() => window.__H.use('talk_ellis'));
  said = await page.evaluate(() => window.__H.say());
  check('Ellis suggests the alternative route', await page.evaluate(() => window.__game.facts.get('hint.reroute')), said.join(' / '));

  // collapse actually blocks
  r = await page.evaluate(() => window.__H.walkPoints([[-7.6, -26.2], [-8.6, -26.2], [-10.6, -31], [-10.4, -36.5]]));
  check('Collapsed section blocks Pall Mall', !r.ok, JSON.stringify(r));

  // --- reroute via Tottenham Sap, Old Boot Alley (flooded), crater ladder + bridge
  r = await page.evaluate(() => window.__H.walkPoints([[-10.5, -31], [-10.4, -30.5], [-3, -29.2], [6, -30.8], [15, -29.4], [22, -30.4], [28, -30], [29.0, -35.6], [29.3, -36.6]]));
  check('Tottenham Sap to Old Boot Alley', r.ok, JSON.stringify(r));
  r = await page.evaluate(() => window.__H.walkPoints([[29.3, -37.4]], { tol: 0.3 }));
  await page.evaluate(() => {
    const g = window.__game;
    window.__H.face(29.3, -38.5);
    g.input.simulate('KeyW', true);
    g.step(4);
    g.input.simulate('KeyW', false);
    g.step(0.3);
  });
  const afterLadder = await page.evaluate(() => window.__H.pos());
  check('Climb the ladder and cross the crater bridge', afterLadder[2] < -46, JSON.stringify(afterLadder));
  r = await page.evaluate(() => window.__H.walkPoints([[27.5, -49], [28.6, -51], [30, -53], [27, -57], [24, -59.6]]));
  check('Cross the crater bridge and reach the front line', (await page.evaluate(() => window.__H.stage())) === 'deliver', JSON.stringify(r));
  await shot('p05-front-line');

  // --- deliver to Ward (front HQ dugout)
  r = await page.evaluate(() => window.__H.walkTo(-25.5, -56.6));
  check('Walk Cheapside to Captain Ward', r.ok, JSON.stringify(r));
  r = await page.evaluate(() => window.__H.use('talk_ward'));
  said = await page.evaluate(() => window.__H.say([1, 2]));
  check('Message delivered', (await page.evaluate(() => window.__H.stage())) === 'search' && !(await page.evaluate(() => window.__game.facts.hasItem('message'))), said.join(' / '));
  // optional diary on a fire step
  const diaryPos = await page.evaluate(() => { const it = window.__game.interactions.items.get('diary'); return it ? [it.position.x, it.position.z] : null; });
  if (diaryPos) {
    r = await page.evaluate(([x, z]) => window.__H.walkTo(x, z + 0.6), diaryPos);
    check('Walk to the diary fire bay', r.ok, JSON.stringify(r));
    r = await page.evaluate(() => window.__H.use('diary'));
    await page.evaluate(() => window.__H.clickButton('Close'));
    await page.evaluate(() => window.__game.resume());
    check('Pick up the diary (optional task starts)', (await page.evaluate(() => window.__H.missionState('diary'))) === 'active', JSON.stringify(r));
  }

  // --- back to the farm: Cheapside → Old Boot → sap → Pall Mall → Fleet St → Haymarket → village
  r = await page.evaluate(() => window.__H.walkTo(24, -59.6));
  r = await page.evaluate(() => window.__H.walkPoints([[27, -57], [30, -53], [28.4, -50], [27.45, -48.5]], { tol: 0.3 }));
  await page.evaluate(() => {
    const g = window.__game;
    window.__H.face(27.42, -46.0); // climb the north ladder (facing south)
    g.input.simulate('KeyW', true);
    g.step(5);
    g.input.simulate('KeyW', false);
    g.step(0.3);
  });

  r = await page.evaluate(() => window.__H.walkPoints([[27.8, -45.5], [28.4, -41.5], [28.9, -38.2]], { tol: 0.35 }));
  await page.evaluate(() => {
    const g = window.__game;
    window.__H.face(29.3, -35.0); // walk off the top towards the trench: the ladder takes over
    g.input.simulate('KeyW', true);
    g.step(4.5);
    g.input.simulate('KeyW', false);
    g.step(0.5);
  });
  const down = await page.evaluate(() => window.__H.pos());
  check('Back down into Old Boot Alley', down[1] < -1.2, JSON.stringify(down));
  r = await page.evaluate(() => window.__H.walkPoints([[29.2, -36.2], [28, -30], [22, -30.4], [15, -29.4], [6, -30.8], [-3, -29.2], [-10.4, -30.5], [-8.4, -26], [-10, -20], [-7, -14], [-9, -8], [-6, -2], [-6, 4.3]]));
  check('Return route to Fleet Street', r.ok, JSON.stringify(r));
  r = await page.evaluate(() => window.__H.walkTo(-21, 64, { sprint: true }));
  check('Haymarket to the village and Moulin Farm', r.ok, JSON.stringify(r));
  await shot('p06-farm');
  // investigation: stretcher clue + observation echo
  r = await page.evaluate(() => window.__H.use('farm_stretcher'));
  await page.evaluate(() => { const g = window.__game; g.input.simulate('KeyF', true); g.step(0.1); g.input.simulate('KeyF', false); g.step(2); });
  await shot('p07-observation-echo');
  await page.evaluate(() => { const g = window.__game; g.input.simulate('KeyF', true); g.step(0.1); g.input.simulate('KeyF', false); g.step(0.5); });
  check('Observation mode reveals the echo (optional objective)', await page.evaluate(() => window.__game.facts.get('event.echo_seen')));
  r = await page.evaluate(() => window.__H.walkTo(-16.6, 77.4));
  r = await page.evaluate(() => window.__H.use('beam'));
  said = await page.evaluate(() => window.__H.say([1]));
  check('Call down to Avery through the gap', (await page.evaluate(() => window.__H.stage())) === 'free', said.join(' / '));
  // lever without a tool does not work
  r = await page.evaluate(() => window.__H.use('beam'));
  await page.evaluate(() => window.__H.say());
  check('Beam cannot be moved without a tool', !(await page.evaluate(() => window.__game.facts.get('event.beam_moved'))));
  r = await page.evaluate(() => window.__H.walkTo(-31.4, 65.4));
  r = await page.evaluate(() => window.__H.use('crowbar'));
  check('Take the crowbar from the Engineers’ store', await page.evaluate(() => window.__game.facts.hasItem('crowbar')), JSON.stringify(r));
  r = await page.evaluate(() => window.__H.walkTo(-16.6, 77.4));
  r = await page.evaluate(() => window.__H.use('beam'));
  await page.evaluate(() => window.__game.step(4.5));
  check('Lever the beam (operate simple machinery)', await page.evaluate(() => window.__game.facts.get('event.beam_moved')), JSON.stringify(r));
  check('Checkpoint saved (farm)', await page.evaluate(() => window.__game.save.data.chapters.ww1_somme_1916.checkpoint.id === 'farm'));
  // Avery climbs out and starts talking automatically (or talk to him)
  await page.evaluate(() => window.__game.step(6));
  if (!(await page.evaluate(() => window.__H.dialogueOpen()))) await page.evaluate(() => window.__H.use('talk_avery'));
  said = await page.evaluate(() => window.__H.say([1]));
  check('Avery briefs the stretcher carry', await page.evaluate(() => window.__game.facts.get('carry.ready')), said.join(' / '));

  // --- Checkpoint retry test: fail the carry on purpose by not crouching, then retry
  const goRear = () => page.evaluate(() => { const it = window.__game.interactions.items.get('stretcher_handles'); const p = window.__game.interactions.worldPos(it, it.position.clone()); return window.__H.walkPoints([[p.x - 0.3, p.z - 0.9]], { tol: 0.4 }); });
  r = await goRear();
  console.log('goRear', JSON.stringify(r), JSON.stringify(await page.evaluate(() => { const it = window.__game.interactions.items.get('stretcher_handles'); const p = window.__game.interactions.worldPos(it, it.position.clone()); const rt = window.__game.currentRuntime; return [p.x, p.y, p.z, window.__game.facts.get('carry.ready'), it.enabled(), rt.stretcher.position.toArray(), rt.stretcher.parent?.name, it.object?.name, it.object?.parent === rt.stretcher, rt.stretcher.visible]; })));
  r = await page.evaluate(() => window.__H.use('stretcher_handles'));
  check('Take the stretcher handles', await page.evaluate(() => window.__game.player.carrying), JSON.stringify(r));
  // follow Avery (walk toward him continuously) until the first hazard, do NOT crouch
  const failRun = await page.evaluate(() => {
    const g = window.__game;
    const av = g.npcs.npcs.get('avery');
    for (let i = 0; i < 30 * 90 && g.state === 'playing'; i++) {
      if (av) {
        const p = av.root.position;
        window.__H.face(p.x, p.z);
        const d = Math.hypot(p.x - g.player.position.x, p.z - g.player.position.z);
        g.input.simulate('KeyW', d > 2.2);
      }
      g.step(1 / 30);
    }
    g.input.simulate('KeyW', false);
    return { state: g.state, mission: g.missions.state.get('runner').state };
  });
  check('Not crouching under shellfire downs the player (mission failed state)', failRun.state !== 'playing' && failRun.mission === 'failed', JSON.stringify(failRun));
  await waitFor(page, () => [...document.querySelectorAll('button')].some((b) => b.textContent.includes('Retry from checkpoint')), 30000).catch(() => {});
  await page.evaluate(() => window.__H.clickButton('Retry from checkpoint'));
  await page.evaluate(() => window.__game.step(0.5));
  const afterRetry = await page.evaluate(() => ({ stage: window.__H.stage(), state: window.__game.missions.state.get('runner').state, beam: window.__game.facts.get('event.beam_moved'), pos: window.__H.pos() }));
  check('Retry restores the farm checkpoint', afterRetry.stage === 'evacuate' && afterRetry.state === 'active' && afterRetry.beam, JSON.stringify(afterRetry));

  // --- the real carry, crouching when warned
  await page.evaluate(() => { if (!window.__game.facts.get('carry.ready')) { window.__H.use('talk_avery'); window.__H.say([1]); } });
  await goRear();
  r = await page.evaluate(() => window.__H.use('stretcher_handles'));
  const carry = await page.evaluate(() => {
    const g = window.__game;
    const av = g.npcs.npcs.get('avery');
    let crouched = 0;
    const trace = [];
    for (let i = 0; i < 30 * 240 && g.state === 'playing' && !g.facts.get('event.whitlow_delivered'); i++) {
      const danger = !document.querySelector('.danger').classList.contains('hidden');
      g.input.simulate('KeyC', danger);
      if (danger) crouched++;
      if (av) {
        const p = av.root.position;
        if (i % 10 === 0) {
          const path = window.__H.navPath(p.x, p.z);
          const pd = Math.hypot(p.x - g.player.position.x, p.z - g.player.position.z);
          // first path point that is closer to Avery than we are, and not right under our feet
          window.__tgt = (path || []).find((q) => Math.hypot(q[0] - p.x, q[1] - p.z) < pd - 0.3 && Math.hypot(q[0] - g.player.position.x, q[1] - g.player.position.z) > 0.5) || [p.x, p.z];
        }
        const tg = window.__tgt || [p.x, p.z];
        window.__H.face(tg[0], tg[1]);
        const d = Math.hypot(p.x - g.player.position.x, p.z - g.player.position.z);
        g.input.simulate('KeyW', !danger && d > 2.2);
      } else {
        g.input.simulate('KeyW', false);
      }
      g.step(1 / 30);
      if (i % 90 === 0 && av) trace.push(`${i / 30}s P${window.__H.pos().join(',')} A${av.root.position.toArray().map((n) => n.toFixed(1)).join(',')} ws${av.walkSpeed} m${av.mode} pi${av.pathIndex}/${av.path.length} clip ${av.currentClip}`);
    }
    g.input.simulate('KeyW', false);
    g.input.simulate('KeyC', false);
    g.step(0.5);
    return { delivered: g.facts.get('event.whitlow_delivered'), crouchedFrames: crouched, state: g.state, pos: window.__H.pos(), trace: trace.slice(-8) };
  });
  check('Stretcher carry to the R.A.P. (escort, hazards, crouch)', carry.delivered, JSON.stringify(carry));
  await shot('p08-rap');
  r = await page.evaluate(() => window.__H.use('talk_laird'));
  said = await page.evaluate(() => window.__H.say([2]));
  check('Speak with the medical officer', (await page.evaluate(() => window.__H.stage())) === 'return', said.join(' / '));
  if (diaryPos) {
    r = await page.evaluate(() => window.__H.use('talk_whitlow'));
    said = await page.evaluate(() => window.__H.say([1]));
    check('Return the diary (optional complete)', (await page.evaluate(() => window.__H.missionState('diary'))) === 'completed', said.join(' / '));
  }
  r = await page.evaluate(() => window.__H.walkTo(-24, 4.1));
  await page.evaluate(() => window.__game.step(2));
  check('Return to the anchor point completes the chapter', await page.evaluate(() => window.__H.missionState('runner') === 'completed' && window.__game.facts.get('event.chapter_complete')), JSON.stringify(r));
  // outro + summary
  await page.evaluate(() => { const g = window.__game; g.input.simulate('Enter', true); g.step(1.5); g.input.simulate('Enter', false); g.step(0.5); });
  const sum = await page.evaluate(() => window.__H.modalText());
  check('Chapter summary shown', sum.includes('complete'), sum);
  const save = await page.evaluate(() => JSON.parse(localStorage.getItem('chrono-witness.save.v1') || '{}'));
  check('Progress persisted (completed, artifacts)', save.chapters?.ww1_somme_1916?.status === 'completed' && save.artifacts?.length >= 2, JSON.stringify({ status: save.chapters?.ww1_somme_1916?.status, artifacts: save.artifacts }));
  await page.evaluate(() => window.__H.clickButton('Return to Headquarters'));
  await page.evaluate(() => (window.__game.automationHold = false));
  await waitFor(page, () => window.__game.currentChapter?.id === 'hq' && window.__game.state === 'playing', 300000);
  check('Return to headquarters with progress saved', await page.evaluate(() => window.__game.save.data.artifacts.length >= 2));
} catch (e) {
  check('Unexpected error', false, e.message);
} finally {
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  const errs = logs.filter((l) => l.includes('[pageerror]') || (l.includes('[error]') && !l.includes('404')));
  if (errs.length) console.log('Page errors:\n' + errs.slice(0, 10).join('\n'));
  fs.writeFileSync('tests/playthrough-result.json', JSON.stringify({ date: new Date().toISOString(), results }, null, 2));
  await browser.close();
  process.exit(failed ? 1 : 0);
}
