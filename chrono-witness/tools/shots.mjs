// Renders fixed viewpoints for visual review (docs/screenshots by default).
// Usage: node tools/shots.mjs [baseUrl] [outDir] [width] [height] [preset]
import { launch, waitFor } from './browser.mjs';
import fs from 'node:fs';

const base = process.argv[2] || 'http://localhost:5173/';
const out = process.argv[3] || 'docs/screenshots';
const W = +(process.argv[4] || 1280);
const H = +(process.argv[5] || 720);
const preset = process.argv[6] || 'high';
const filter = process.argv[7] || '';
fs.mkdirSync(out, { recursive: true });
const { browser, page, logs } = await launch({ width: W, height: H });
await page.addInitScript((p) => {
  const s = JSON.parse(localStorage.getItem('chrono-witness.settings') || '{}');
  s.graphics = { ...(s.graphics || {}), preset: p, adaptiveQuality: false };
  localStorage.setItem('chrono-witness.settings', JSON.stringify(s));
}, preset);
await page.goto(base);
await waitFor(page, () => window.__game && document.querySelector('.title-logo'), 180000);
await page.evaluate((p) => { const g = window.__game; const { applyPreset } = window.__presetFns || {}; g.settings.graphics.adaptiveQuality = false; }, preset);

// viewpoints: [name, chapter, eye x,z, eyeHeightAboveGround, look x,y-offset,z]
const views = [
  ['hq-hall', 'hq', [0, 9], 1.65, [0, 2.2, -6]],
  ['hq-gallery', 'hq', [-6, 5], 1.65, [-11, 1.3, 0]],
  ['hq-archive', 'hq', [3, 6], 1.65, [11, 1.4, -2]],
  ['ww1-fleet-street', 'ww1_somme_1916', [-26, 4], 1.62, [-12, 1.4, 4]],
  ['ww1-pall-mall', 'ww1_somme_1916', [-6, 1], 1.62, [-8.5, 1.3, -12]],
  ['ww1-shelter', 'ww1_somme_1916', [-3.6, -26.3], 1.5, [-7, 1.2, -26.2]],
  ['ww1-front-west', 'ww1_somme_1916', [-14.5, -60], 1.62, [-27, 1.5, -60]],
  ['ww1-front-east', 'ww1_somme_1916', [20, -60.1], 1.62, [40, 1.6, -60]],
  ['ww1-over-parapet', 'ww1_somme_1916', [-10.5, -60.6], 2.15, [-10, 0.6, -120]],
  ['ww1-crater', 'ww1_somme_1916', [28.9, -37.9], 1.8, [27.6, 0, -50]],
  ['ww1-village-road', 'ww1_somme_1916', [6, 48], 1.65, [-26, 2, 66]],
  ['ww1-farm', 'ww1_somme_1916', [-15, 64], 1.65, [-26, 1.4, 78]],
  ['ww1-cellar-steps', 'ww1_somme_1916', [-15.6, 77.4], 1.65, [-20, -1.2, 77.4]],
  ['ww1-rap', 'ww1_somme_1916', [18, 7.5], 1.5, [17.2, 0.9, 10]],
  ['ww1-overview', 'ww1_somme_1916', [-40, 30], 14, [0, -2, -40]],
  ['ldn-cable-row', 'london_blitz_1940', [-50, -1], 1.65, [-20, 1.6, 0]],
  ['ldn-n9-front', 'london_blitz_1940', [-37, 1.5], 1.65, [-39, 1.4, -6]],
  ['ldn-n9-room', 'london_blitz_1940', [-38.9, -7.0], 1.65, [-36, 1.0, -11]],
  ['ldn-warden-post', 'london_blitz_1940', [18.5, -1], 1.65, [13, 1.3, -5]],
  ['ldn-dock-lane-south', 'london_blitz_1940', [20, 14], 1.65, [21, 2.5, 40]],
  ['ldn-alley-gate', 'london_blitz_1940', [27.5, 24], 1.65, [31, 1, 25.6]],
  ['ldn-high-street', 'london_blitz_1940', [10, -45], 1.65, [29, 2.5, -52]],
  ['ldn-booking-hall', 'london_blitz_1940', [29, -51], 1.65, [29, 0.2, -56]],
  ['ldn-stairs', 'london_blitz_1940', [29, -57.2], 0, [29, -4.2, -61], [-1.0, true]],
  ['ldn-platform', 'london_blitz_1940', [36, -67.8], 0, [18, -7.4, -68.6], [-7.28, true]],
  ['ldn-s14', 'london_blitz_1940', [-27.5, 1.5], 1.65, [-28.5, 1.0, 8]],
  ['ldn-overview', 'london_blitz_1940', [-45, 28], 22, [0, -3, -20]],
  ['ldn-sky-south', 'london_blitz_1940', [20, 18], 1.65, [28, 40, 140]],
];
let current = null;
for (const [name, ch, [x, z], eh, [lx, ly, lz], abs] of views.filter((v) => !filter || v[0].includes(filter))) {
  if (current !== ch) {
    await page.evaluate((c) => { window.__game.automationHold = false; return window.__game.loadForBenchmark(c); }, ch);
    await waitFor(page, () => window.__game.currentRuntime, 400000);
    await page.evaluate(() => (window.__game.automationHold = true));
    current = ch;
  }
  await page.evaluate(([x, z, eh, lx, ly, lz, abs]) => {
    const g = window.__game;
    const T = window.__THREE;
    const rt = g.currentRuntime;
    // abs = [eyeY, true]: absolute eye height and absolute look height (underground views)
    const gy = abs ? abs[0] - 1.6 : rt.resolveSpawnHeight ? rt.resolveSpawnHeight(x, z) - 0.15 : 0;
    const ground = abs ? abs[0] : (g.world.groundHeight(x, gy + 1.0, z, 4) ?? gy);
    const lgy = abs ? 0 : rt.resolveSpawnHeight ? rt.resolveSpawnHeight(lx, lz) - 0.15 : 0;
    g.player.controller.position.set(x, ground, z);
    g.setBenchmarkCamera(new T.Vector3(x, ground + eh, z), new T.Vector3(lx, lgy + ly, lz));
    g.step(0.5);
    g.setBenchmarkCamera(new T.Vector3(x, ground + eh, z), new T.Vector3(lx, lgy + ly, lz));
    g.ui.showHUD(false);
    g.renderOnce();
  }, [x, z, eh, lx, ly, lz, abs]);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log('shot', name);
}
console.log(logs.filter((l) => l.includes('error') && !l.includes('404')).slice(0, 5).join('\n'));
await browser.close();
