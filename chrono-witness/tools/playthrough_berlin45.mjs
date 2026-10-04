// Automated playthrough of "Chalk" (Berlin, 18 May 1945).
// Usage: node tools/playthrough_berlin45.mjs [baseUrl] [screenshotDir]
import { launch, waitFor } from './browser.mjs';
import { installHarness } from './harness.mjs';
import fs from 'node:fs';

const base = process.argv[2] || 'http://localhost:5173/';
const shots = process.argv[3] || '';
if (shots) fs.mkdirSync(shots, { recursive: true });
const { browser, page, logs } = await launch({ width: 960, height: 540 });
const results = [];
const check = (name, ok, info = '') => {
  results.push({ name, ok: !!ok, info });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${info ? ' — ' + info : ''}`);
};
const shot = async (name) => {
  if (!shots) return;
  await page.evaluate(() => window.__game.renderOnce());
  await page.screenshot({ path: `${shots}/${name}.png` });
};
const ev = (fn, arg) => page.evaluate(fn, arg);
const walk = (pts, opts) => ev(([p, o]) => window.__H.walkPoints(p, o), [pts, opts ?? {}]);
const use = (id, hold) => ev(([i, h]) => window.__H.use(i, h), [id, hold]);
const scan = (id) => ev((i) => window.__H.scan(i), id);
const say = (choices) => ev((c) => window.__H.say(c), choices ?? []);
const flag = (f) => ev((x) => window.__game.facts.get(x), f);
const has = (i) => ev((x) => window.__game.facts.hasItem(x), i);
const stage = () => ev(() => window.__H.stage());
const step = (s) => ev((x) => window.__game.step(x), s);
const cp = () => ev(() => window.__game.save.data.chapters.berlin_1945?.checkpoint?.id);
const waitUntil = (fn, max = 120) => ev(([f, m]) => {
  const g = window.__game;
  const test = new Function('g', `return (${f})(g)`);
  for (let k = 0; k < m * 30; k++) {
    if (test(g)) return true;
    g.step(1 / 30);
  }
  return test(g);
}, [fn.toString(), max]);

// routes
const streetToYard = [[0, 1], [0, -8], [0, -18]];
const yardToCellar = [[-6, -29.5], [-6, -31.6], [-6, -35.2], [-6, -36.9], [-6, -39.0], [-6.2, -39.8]];
const cellarToYard = [[-6, -39.0], [-6, -36.9], [-6, -35.2], [-6, -31.6], [-6, -29.5], [-3, -24]];
const yardToStreet = [[0, -18], [0, -8], [0, 1]];
const upToFlight1 = [[4.5, -25.4], [6.9, -25.4], [7.4, -26.4], [7.4, -29.2], [8.0, -29.9], [8.7, -29.2], [8.7, -26.0], [7.6, -25.4], [7.4, -26.4], [7.4, -29.2], [8.0, -29.9], [8.7, -29.4]];
const downFromFlight2 = [[8.7, -26.6], [8.7, -29.0], [8.0, -29.9], [7.4, -29.2], [7.4, -26.4], [8.7, -26.4], [8.7, -29.2], [8.0, -29.9], [7.4, -29.2], [7.4, -26.4], [7.4, -25.4], [5.6, -25.4], [3, -25]];

try {
  await page.goto(base);
  await waitFor(page, () => window.__game && document.querySelector('.title-logo'), 180000);
  await ev(() => window.__game.save.resetAll());
  await ev(() => window.__game.travelTo('berlin_1945', false));
  await waitFor(page, () => ['playing', 'cinematic'].includes(window.__game.state), 400000);
  await ev(() => (window.__game.automationHold = true));
  await installHarness(page, 'chalk');
  check('Chapter loads', true, await ev(() => `asset issues: ${window.__game.assets.issues.length}`));
  await ev(() => {
    const g = window.__game;
    g.input.simulate('Enter', true);
    g.step(1.2);
    g.input.simulate('Enter', false);
    g.step(0.3);
  });
  check('Intro cinematic skippable', await ev(() => window.__game.state === 'playing'));
  await shot('b01-arrival');

  // ---- Frau Brandt
  let r = await walk([[30, -1.5], [10, -1.5], ...streetToYard, [-1.0, -21.4]]);
  check('Walk through the gateway into the courtyard', r.ok, JSON.stringify(r));
  r = await use('talk_brandt');
  let said = await say([1]);
  check('Frau Brandt gives the buckets', await has('buckets'), JSON.stringify(r) + ' ' + said.join(' / '));
  check('Stage "water" + checkpoint "yard"', (await stage()) === 'water' && (await cp()) === 'yard');
  await shot('b02-yard');

  // ---- the pump queue
  r = await walk([...yardToStreet, [0, -1.5], [30, -1.5], [34.8, 3.5], [35.3, 8.0]], { tol: 0.4 });
  check('Join the end of the queue at the pump', r.ok, JSON.stringify(r));
  r = await use('pump', 3.2);
  check('Cannot pump before your turn', !(await flag('event.water_pumped')));
  await step(17);
  check('The queue moves on while you wait', await ev(() => window.__game.currentRuntime.queueLeft === 0));
  r = await scan('obj_buckets');
  r = await walk([[32.3, 8.0]], { tol: 0.35 });
  r = await use('pump', 3.2);
  check('Pump the water (hold E)', (await flag('event.water_pumped')) && (await ev(() => window.__game.player.carrying)), JSON.stringify(r));
  r = await scan('obj_pump');
  check('Scan the street pump', await flag('scan.scan_street_pump'), JSON.stringify(r));
  await shot('b03-pump');

  // ---- carry it down to the cellar
  r = await walk([[30, -1.5], [2, -1.5], ...streetToYard, ...yardToCellar]);
  check('Carry the water down the cellar steps', r.ok, JSON.stringify(r));
  r = await use('deliver_water');
  check('Water delivered (stage "lenz", checkpoint "cellar")', (await flag('event.water_delivered')) && (await stage()) === 'lenz' && (await cp()) === 'cellar', JSON.stringify(r));
  for (const id of ['obj_radio', 'obj_stirrup_pump']) await scan(id);
  r = await use('talk_lenz');
  said = await say([2]);
  check('Herr Lenz asks you to look at the chalk wall', await flag('dlg.lenz.walls'), said.join(' / '));
  await shot('b04-cellar');

  // ---- Frau Brandt again (optional firewood), then the firewall
  r = await walk([...cellarToYard, [-1.0, -21.4]]);
  r = await use('talk_brandt');
  said = await say();
  check('Optional "Firewood" offered', (await ev(() => window.__H.missionState('firewood'))) === 'active', said.join(' / '));
  r = await walk([...yardToStreet, [-30, 3.2], [-47, 3.2], [-47, -4], [-39.2, -13.6]]);
  check('Walk to the firewall at the west end', r.ok, JSON.stringify(r));
  r = await use('read_wall');
  await ev(() => {
    window.__H.clickButton('Close');
    window.__game.resume();
  });
  check('Read the chalked messages', await flag('event.read_wall'), JSON.stringify(r));
  r = await scan('obj_chalk');
  r = await walk([[-39.0, -11.6]], { tol: 0.4 });
  r = await use('write_chalk', 2.2);
  check('Chalk Herr Lenz’s answer', await flag('event.chalk_written'), JSON.stringify(r));
  await shot('b05-firewall');

  // ---- tell Lenz
  r = await walk([[-47, -4], [-47, 3.2], [-30, 3.2], [-2, 1], ...streetToYard, ...yardToCellar]);
  r = await use('talk_lenz');
  said = await say();
  check('Lenz needs his papers', await flag('dlg.lenz.papers'), said.join(' / '));

  // ---- the broken stairs
  r = await walk([...cellarToYard, [-8.6, -24.4]]);
  r = await use('take_planks');
  check('Take planks from the woodpile', await flag('event.planks_taken'), JSON.stringify(r));
  r = await walk(upToFlight1);
  check('Climb to the broken flight (carrying)', r.ok, JSON.stringify(r));
  r = await use('place_planks', 1.7);
  check('Lay planks across the gap', await flag('event.planks_placed'), JSON.stringify(r));
  r = await walk([[8.7, -26.6], [8.7, -25.8], [9.3, -25.4], [10.2, -25.4], [10.3, -27.2]]);
  check('Cross the planks into the Lenz flat', r.ok && (await ev(() => window.__game.player.position.y > 7)), JSON.stringify(r));
  r = await use('papers');
  check('Take the tin box of papers', await has('papers'), JSON.stringify(r));
  check('Checkpoint "papers"', (await cp()) === 'papers');
  r = await scan('obj_stove');
  await shot('b06-flat');
  r = await walk([[10.2, -25.4], [9.3, -25.4], ...downFromFlight2]);
  check('Back down the stairs', r.ok && (await ev(() => window.__game.player.position.y < 0.5)), JSON.stringify(r));

  // ---- ration cards
  r = await walk([[0, -18], ...yardToStreet, [0, 8.4], [0, 11.5], [0.8, 14.6]]);
  check('Into the ration-card office', r.ok, JSON.stringify(r));
  await step(7);
  check('Your turn comes', await flag('event.office_turn'));
  r = await use('talk_clerk');
  said = await say([2]);
  check('Clerk issues the new cards', await has('ration_cards'), said.join(' / '));
  r = await scan('obj_ration_cards');
  await shot('b07-office');
  r = await walk([[0, 11.5], [0, 8.4], [0, 1], ...streetToYard, ...yardToCellar]);
  r = await use('talk_lenz');
  said = await say();
  check('Cards delivered (stage "shell", checkpoint "office")', (await flag('dlg.lenz.cards')) && (await stage()) === 'shell' && (await cp()) === 'office', said.join(' / '));

  // ---- the shell
  r = await walk([...cellarToYard, ...yardToStreet]);
  await step(1);
  check('Peter brings news of the shell', await ev(() => window.__game.currentRuntime.shellState === 'active'));
  r = await walk([[-30, 3.2], [-47, 3.2], [-47, -4], [-47.6, -12.6]]);
  const kids = [['send_k1', [-47.8, -13.6]], ['send_k2', [-50.0, -13.4]], ['send_k3', [-49.4, -12.4]]];
  for (const [id, p] of kids) {
    await walk([p], { tol: 0.6 });
    await use(id);
  }
  check('Send all three children away', (await flag('event.kid_1')) && (await flag('event.kid_2')) && (await flag('event.kid_3')));
  r = await walk([[-47, -4], [-47, 3.2], [-30, 3.2], [10, -1.5], [40, -1.5], [63.5, 0.6]]);
  r = await use('talk_regulator');
  said = await say();
  check('Tell the traffic regulator; a sapper is sent', await flag('event.sapper_called'), said.join(' / '));
  r = await scan('obj_cyrillic');
  r = await walk([[40, -1.5], [10, -1.5], [-28, 0.5], [-32, -6.5]]);
  const arrived = await waitUntil((g) => g.npcs.get('sapper').mode !== 'path', 120);
  r = await walk([[-33.3, -6.8]], { tol: 0.5 });
  r = await use('talk_sapper');
  said = await say();
  await step(0.5);
  const modal = await ev(() => [...document.querySelectorAll('.modal-layer button')].map((b) => b.textContent).join(' | '));
  check('Sapper arrives; the demolition asks first (skippable)', arrived && modal.includes('Skip'), modal + ' ' + said.join(' / '));
  await ev(() => window.__H.clickButton('Experience it'));
  await step(7);
  check('Shell made safe (stage "chain")', (await flag('event.shell_cleared')) && (await stage()) === 'chain');

  // ---- the rubble chain (and firewood on the way)
  for (const [i, p] of [[1, [-29.8, -6.6]], [2, [-26.6, -6.4]], [3, [-23.4, -6.6]]]) {
    await walk([p], { tol: 0.5 });
    await use(`wood_${i}`);
  }
  check('Gather three pieces of firewood (optional)', (await flag('event.wood_1')) && (await flag('event.wood_2')) && (await flag('event.wood_3')));
  r = await walk([[-25.0, -4.9]], { tol: 0.4 });
  for (let k = 0; k < 5; k++) {
    await waitUntil((g) => g.currentRuntime.chainCue >= 0, 10);
    await use('chain');
  }
  check('Pass five buckets along the chain', await flag('event.chain_done'));
  await shot('b08-chain');

  // ---- reunion
  r = await walk([[-10, 1], ...streetToYard, ...yardToCellar]);
  r = await walk([[-7.0, -42.9]], { tol: 0.5 });
  r = await use('stove');
  check('Stack the firewood by the stove (optional complete)', (await ev(() => window.__H.missionState('firewood'))) === 'completed', JSON.stringify(r));
  const came = await waitUntil((g) => g.facts.get('event.lotte_arrived'), 120);
  check('Lotte arrives at the cellar', came);
  r = await walk([[-6.4, -40.4]], { tol: 0.4 });
  r = await use('talk_lotte');
  said = await say();
  check('Reunion (stage "return")', (await flag('dlg.lotte.end')) && (await stage()) === 'return', JSON.stringify(r) + ' ' + said.join(' / '));
  await shot('b09-reunion');

  // ---- recall
  r = await walk([...cellarToYard, ...yardToStreet, [10, -1.5], [30, -1.5], [48, 1]]);
  await step(1.5);
  check('Return to the anchor completes the chapter', (await ev(() => window.__H.missionState('chalk'))) === 'completed', JSON.stringify(r));
  await step(1.5);
  check('Completion recorded in the save', await ev(() => window.__game.save.data.chapters.berlin_1945?.status === 'completed'));
  const scans = await ev(() => [...window.__game.facts.flags.keys()].filter((k) => k.startsWith('scan.')).length);
  check('Witness record progress', scans >= 7, `${scans} scans`);
} catch (e) {
  check('Unhandled error', false, String(e?.stack || e));
}
const errs = logs.filter((l) => l.includes('pageerror') || (l.includes('[error]') && !l.includes('404')));
check('No page errors', errs.length === 0, errs.slice(0, 5).join('\n'));
const passed = results.filter((r) => r.ok).length;
console.log(`\n${passed}/${results.length} checks passed`);
fs.mkdirSync('tests', { recursive: true });
fs.writeFileSync('tests/playthrough-berlin45-result.json', JSON.stringify({ date: new Date().toISOString(), passed, total: results.length, results }, null, 2));
await browser.close();
process.exit(passed === results.length ? 0 : 1);
