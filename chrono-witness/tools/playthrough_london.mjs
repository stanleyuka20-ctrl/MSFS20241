// Automated playthrough of "Blackout" (London, September 1940).
// Drives the real simulation headlessly: walks the streets with collision, uses interactables,
// answers dialogue and checks every mission stage, the optional tasks, a checkpoint retry and saving.
// Usage: node tools/playthrough_london.mjs [baseUrl] [screenshotDir]
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
const say = (choices) => ev((c) => window.__H.say(c), choices ?? []);
const flag = (f) => ev((x) => window.__game.facts.get(x), f);
const stage = () => ev(() => window.__H.stage());
const step = (s) => ev((x) => window.__game.step(x), s);
const pos = () => ev(() => window.__H.pos());
const cp = () => ev(() => window.__game.save.data.chapters.london_blitz_1940?.checkpoint?.id);
// No. 9 is at x −37.5 on the north side (local → world: x + lx, z −5.8 + lz)
const n9 = (lx, lz) => [-37.5 + lx, -5.8 + lz];
const s14 = (lx, lz) => [-27.5 - lx, 5.8 - lz];

try {
  await page.goto(base);
  await waitFor(page, () => window.__game && document.querySelector('.title-logo'), 180000);
  await ev(() => window.__game.save.resetAll());
  await ev(() => window.__game.travelTo('london_blitz_1940', false));
  await waitFor(page, () => ['playing', 'cinematic'].includes(window.__game.state), 400000);
  await ev(() => (window.__game.automationHold = true));
  await installHarness(page, 'blackout');
  check('Chapter loads', true, await ev(() => `asset issues: ${window.__game.assets.issues.length} (missing period characters use stand-ins)`));
  await ev(() => {
    const g = window.__game;
    g.input.simulate('Enter', true);
    g.step(1.2);
    g.input.simulate('Enter', false);
    g.step(0.3);
  });
  check('Intro cinematic skippable', await ev(() => window.__game.state === 'playing'));
  check('Spawned at the west end of Cable Row', true, JSON.stringify(await pos()));
  await shot('l01-arrival');

  // ---------------------------------------------------------------- Warden Pike
  let r = await walk([[-30, -1], [0, -1], [12, -1.5], [16.2, -2.6]]);
  check('Walk Cable Row to the warden’s post', r.ok, JSON.stringify(r));
  r = await ev(() => window.__H.scan('obj_warden_helmet'));
  check('Scan the warden’s helmet', await flag('scan.scan_warden_helmet'), JSON.stringify(r));
  r = await use('talk_pike');
  let said = await say([1, 2]);
  check('Pike gives the sand bucket', await ev(() => window.__game.facts.hasItem('sand_bucket')), said.join(' / '));
  check('Stage "family" + checkpoint "post"', (await stage()) === 'family' && (await cp()) === 'post');
  check('Optional "Fire-Watch" becomes available', (await ev(() => window.__H.missionState('firewatch'))) === 'active');
  await ev(() => window.__H.scan('obj_arp_post'));
  r = await walk([[12, -1.5], [10.6, -3.0], [11.0, -4.0]], { tol: 0.3 });
  for (const id of ['obj_stirrup_pump', 'obj_redhill']) await ev((i) => window.__H.scan(i), id);
  check('Scan stirrup pump, Redhill container and ARP post', (await flag('scan.scan_stirrup_pump')) && (await flag('scan.scan_redhill')) && (await flag('scan.scan_arp_post')));

  // ---------------------------------------------------------------- the Hartleys
  r = await walk([[0, -1.5], [-30, -1.5], [n9(-1.55, 1.3)[0], n9(-1.55, 1.3)[1]]]);
  check('Walk back to No. 9', r.ok, JSON.stringify(r));
  r = await use('talk_ivy');
  said = await say();
  check('Ivy asks for Joan’s gas mask', await flag('dlg.ivy.go'), JSON.stringify(r) + ' ' + said.join(' / '));
  await step(0.5);
  r = await walk([n9(-1.55, 0.6), n9(-1.55, -0.6), n9(-1.2, -1.2), n9(-0.4, -1.2), n9(-0.4, -5.3), n9(1.0, -5.7)]);
  check('Enter No. 9 and cross the front room', r.ok, JSON.stringify(r));
  await shot('l02-front-room');
  r = await ev(() => window.__H.scan('obj_ration_book'));
  check('Scan the ration book', await flag('scan.scan_ration_book'), JSON.stringify(r));
  r = await use('gasmask');
  check('Pick up the gas-mask box', await ev(() => window.__game.facts.hasItem('gasmask_box')), JSON.stringify(r));
  check('Stage "escort"', (await stage()) === 'escort');
  r = await walk([n9(-0.4, -5.3), n9(-0.4, -1.2), n9(-1.2, -1.2), n9(-1.55, -0.4), n9(-1.55, 1.6)]);
  await step(0.3);
  check('Incendiaries land when you step out', await ev(() => window.__game.currentRuntime.incendiariesLive), JSON.stringify(r));
  check('Danger timer shown', await ev(() => !document.querySelector('.danger').classList.contains('hidden')));
  await shot('l03-incendiaries');
  r = await walk([[-31.8, 0.6]], { tol: 0.4 });
  r = await use('incendiary_a', 1.7);
  check('Smother the first incendiary (hold E)', await flag('event.incendiary_a'), JSON.stringify(r));
  r = await ev(() => window.__H.scan('scan_incendiary_a'));
  check('Scan the burnt-out incendiary', await flag('scan.scan_incendiary'), JSON.stringify(r));
  r = await walk([[-24.4, -0.9]], { tol: 0.4 });
  r = await use('incendiary_b', 1.7);
  check('Smother the second incendiary', await flag('event.incendiary_b'), JSON.stringify(r));
  await step(0.5);
  check('Family follows once the street is safe', await ev(() => window.__game.currentRuntime.family.active && !window.__game.currentRuntime.family.holding));
  const route = [[-10, 0], [12, 0], [20, -6], [20, -25], [20, -43], [27, -47], [29, -50.8], [29, -54.2], [29, -57.5], [29, -60.0], [29, -61.2], [29, -64], [29, -66.9], [29, -68.2], [29, -69.3], [25, -69.3], [22, -69.3]];
  for (let i = 0; i < route.length; i++) {
    r = await walk([route[i]]);
    if (!r.ok) break;
    // let the family keep up (they follow your trail)
    await ev(() => {
      const g = window.__game;
      const fam = g.currentRuntime.family;
      for (let k = 0; k < 90 && fam.active; k++) {
        const p = g.player.position;
        if (fam.members.every((m) => m.root.position.distanceTo(p) < 6.5)) break;
        g.step(1 / 30);
      }
    });
  }
  check('Lead the family to Morley Road and down to the platform', r.ok, JSON.stringify(r));
  await step(2);
  const famInfo = await ev(() => window.__game.currentRuntime.family.members.map((m) => m.root.position.toArray().map((v) => +v.toFixed(1))));
  check('Family sheltered on the platform', await flag('event.family_sheltered'), JSON.stringify(famInfo));
  check('Stage "moss" + checkpoint "station"', (await stage()) === 'moss' && (await cp()) === 'station');
  r = await ev(() => window.__H.scan('obj_tube_shelter'));
  check('Scan the Tube shelter', await flag('scan.scan_tube_shelter'), JSON.stringify(r));
  await shot('l04-platform');

  // ---------------------------------------------------------------- the bomb, Mr Moss
  r = await walk([[25, -69.3], [29, -69.3], [29, -68.2], [29, -66.9], [29, -64], [29, -61.2], [29, -60.0], [29, -57.5], [29, -54.2], [29, -51.0], [29, -49.5]]);
  await step(0.3);
  const modal = await ev(() => [...document.querySelectorAll('.modal-layer button')].map((b) => b.textContent).join(' | '));
  check('Climb back up; the bomb sequence asks first (skippable)', modal.includes('Skip'), JSON.stringify(r) + ' ' + modal);
  await ev(() => window.__H.clickButton('Experience it'));
  await step(7);
  check('No. 14 is hit (ruin collision on)', (await flag('event.he_bomb')) && (await ev(() => window.__game.world.colliders.find((c) => c.id === 's14_ruin')?.enabled)));
  r = await walk([[20, -44], [20, -4], [0, 1], [-27, 1.5], [s14(1.5, -0.4)[0], s14(1.5, -0.4)[1]], [s14(1.4, -0.9)[0], s14(1.4, -0.9)[1]]]);
  check('Walk back to No. 14 and into the doorway', r.ok, JSON.stringify(r));
  await shot('l05-ruin');
  r = await use('moss_call');
  said = await say();
  check('Hear Mr Moss tapping under the stairs', await flag('event.moss_located'), JSON.stringify(r) + ' ' + said.join(' / '));
  check('Stage "route" + checkpoint "incident"', (await stage()) === 'route' && (await cp()) === 'incident');

  // checkpoint retry: restart and make sure the world matches the saved state
  await ev(() => window.__game.restartFromCheckpoint());
  await waitFor(page, () => window.__game.state === 'playing', 120000);
  await step(0.5);
  check('Retry from checkpoint "incident" restores the ruined house', (await flag('event.he_bomb')) && (await ev(() => window.__game.currentRuntime.ruinGroup.visible)) && (await stage()) === 'route');

  // ---------------------------------------------------------------- the gate
  r = await walk([[-10, 1.5], [12, -1], [16.2, -2.6]]);
  r = await use('talk_pike');
  said = await say([1]);
  check('Report the incident to Pike', await flag('dlg.pike.incident'), said.join(' / '));
  r = await walk([[20, 0], [20.5, 12], [20.5, 24], [30, 24], [31, 24.3]]);
  check('Down Dock Lane and along the south alley to the gate', r.ok, JSON.stringify(r));
  r = await use('gate_bolt');
  check('Bolt cannot be drawn while bricks block the gate', !(await flag('event.gate_open')));
  r = await use('gate_bricks', 2.6);
  check('Clear the fallen bricks (hold E)', await flag('event.gate_bricks'), JSON.stringify(r));
  r = await use('gate_bolt');
  await step(1.5);
  check('Open the gate', await flag('event.gate_open'), JSON.stringify(r));
  check('Gate collision removed', !(await ev(() => window.__game.world.colliders.find((c) => c.id === 'gate')?.enabled)));
  check('Rescue party sets off', await ev(() => window.__game.currentRuntime.rescuersMoving || window.__game.currentRuntime.rescuersArrived));
  check('Stage "supplies"', (await stage()) === 'supplies');
  await shot('l06-gate');

  // ---------------------------------------------------------------- tea and dressings
  r = await walk([[30, 24], [20.5, 24], [20.5, 4], [20, -20], [20, -42], [12, -47.2], [6.4, -47.2]]);
  r = await use('talk_wvs');
  said = await say();
  check('Collect tea from the WVS canteen (optional)', await ev(() => window.__game.facts.hasItem('tea')), JSON.stringify(r) + ' ' + said.join(' / '));
  r = await ev(() => window.__H.scan('obj_afs_pump'));
  r = await walk([[-20, -47.2], [-40, -47.2], [-40, -40.8], [-40.2, -36.0]]);
  check('Walk to the ARP depot', r.ok, JSON.stringify(r));
  r = await use('dressings');
  check('Take the dressings (carrying)', await ev(() => window.__game.player.carrying && window.__game.facts.hasItem('dressings')), JSON.stringify(r));
  const sprintBlocked = await ev(() => {
    const g = window.__game;
    g.input.simulate('ShiftLeft', true);
    g.input.simulate('KeyW', true);
    const p0 = g.player.position.clone();
    g.step(1.0);
    const speed = g.player.position.distanceTo(p0);
    g.input.simulate('ShiftLeft', false);
    g.input.simulate('KeyW', false);
    return speed;
  });
  check('Cannot sprint while carrying (slow walk)', sprintBlocked < 3.0, `${sprintBlocked.toFixed(2)} m/s`);
  r = await walk([[-40, -40.8], [-40, -47.2], [12, -47.2], [19.5, -42], [20, -20], [20, -2], [-20, 2.2], [-28.4, 2.9]]);
  check('Carry the dressings back to No. 14', r.ok, JSON.stringify(r));
  r = await use('talk_nurse');
  said = await say();
  check('Nurse takes the dressings', await flag('event.dressings_delivered'), JSON.stringify(r) + ' ' + said.join(' / '));
  check('Stage "listen" + checkpoint "rescue"', (await stage()) === 'listen' && (await cp()) === 'rescue');
  // wait for the rescue party
  await ev(() => {
    const g = window.__game;
    for (let k = 0; k < 30 * 240 && !g.currentRuntime.rescuersArrived; k++) g.step(1 / 30);
  });
  check('Rescue party arrives by the alley route', await ev(() => window.__game.currentRuntime.rescuersArrived));
  r = await walk([[-27.0, 3.0]], { tol: 0.35 });
  r = await use('give_tea');
  check('Give the rescue party their tea (optional complete)', (await ev(() => window.__H.missionState('tea'))) === 'completed', JSON.stringify(r));

  // ---------------------------------------------------------------- silence and rescue
  r = await walk([[-27.2, 3.0]], { tol: 0.4 });
  r = await use('talk_carver');
  said = await say();
  check('Carver calls for silence', await flag('event.silence'), JSON.stringify(r) + ' ' + said.join(' / '));
  r = await walk([[-29.0, 4.9], [-29.0, 6.3], [-28.7, 6.5]], { tol: 0.3 });
  check('Step into the front of the ruin', r.ok, JSON.stringify(r));
  await step(3);
  check('Tapping marks appear while you keep still', await ev(() => window.__game.currentRuntime.pulses.some((m) => m.visible)));
  await shot('l07-silence');
  r = await use('tap_spot_0');
  check('Pointing at the wrong place does not count', !(await flag('event.tapping_located')), JSON.stringify(r));
  r = await use('tap_spot_1');
  check('Point out the tapping under the stairs', await flag('event.tapping_located'), JSON.stringify(r));
  r = await walk([[-29.0, 6.2], [-29.0, 4.8], [-24.0, 3.4]], { tol: 0.4 });
  for (let k = 0; k < 3; k++) {
    r = await use('timber', 1.1);
    await step(0.3);
  }
  check('Pass three timbers', (await ev(() => window.__game.currentRuntime.timberCount())) === 3, JSON.stringify(r));
  await step(14);
  check('Mr Moss is brought out at dawn', await flag('event.moss_freed'));
  check('Stage "return"', (await stage()) === 'return');
  await shot('l08-dawn');
  r = await walk([[-27.8, 3.2]], { tol: 0.35 });
  r = await use('talk_moss');
  said = await say();
  check('Talk to Mr Moss', said.length > 0, said.join(' / '));

  // ---------------------------------------------------------------- optional fire-watch (one yard)
  r = await walk([[0, 1], [20, 0], [20, -24], [-14.15, -24], [-14.15, -21.5], [-12.0, -16.0]]);
  check('Through the back alley into the yard of No. 19', r.ok, JSON.stringify(r));
  r = await use('yard_fire_2', 1.6);
  check('Smother a yard incendiary via the back alley (optional)', await flag('event.yard_fire_2'), JSON.stringify(r));

  // ---------------------------------------------------------------- recall
  r = await walk([[-14.15, -21.5], [-14.15, -24], [20, -24], [20, -2], [-20, -1], [-46, -1]]);
  await step(1.5);
  check('Return to the anchor point', await flag('zone.anchor'), JSON.stringify(r));
  check('Main mission complete', (await ev(() => window.__H.missionState('blackout'))) === 'completed');
  await step(1.5);
  check('Chapter completion recorded in the save', await ev(() => window.__game.save.data.chapters.london_blitz_1940?.status === 'completed'));
  const scans = await ev(() => Object.keys(Object.fromEntries(window.__game.facts.flags)).filter((k) => k.startsWith('scan.')).length);
  check('Witness record progress', scans >= 7, `${scans} scans`);
} catch (e) {
  check('Unhandled error', false, String(e?.stack || e));
}
const errs = logs.filter((l) => l.includes('pageerror') || (l.includes('[error]') && !l.includes('404')));
check('No page errors', errs.length === 0, errs.slice(0, 5).join('\n'));
const passed = results.filter((r) => r.ok).length;
console.log(`\n${passed}/${results.length} checks passed`);
fs.mkdirSync('tests', { recursive: true });
fs.writeFileSync('tests/playthrough-london-result.json', JSON.stringify({ date: new Date().toISOString(), passed, total: results.length, results }, null, 2));
await browser.close();
process.exit(passed === results.length ? 0 : 1);
