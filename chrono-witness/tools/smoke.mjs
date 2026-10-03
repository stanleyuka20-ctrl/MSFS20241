// Smoke test: boots the game, enters HQ and the WW1 chapter, captures screenshots.
// Usage: node tools/smoke.mjs [baseUrl] [outDir]
import { launch, waitFor } from './browser.mjs';
import fs from 'node:fs';

const base = process.argv[2] || 'http://localhost:5173/';
const out = process.argv[3] || 'docs/screenshots';
fs.mkdirSync(out, { recursive: true });
const { browser, page, logs } = await launch({ width: 1280, height: 720 });
const t0 = Date.now();
try {
  await page.goto(base, { waitUntil: 'load' });
  await waitFor(page, () => window.__game && document.querySelector('.title-logo'), 180000);
  console.log('menu ready', (Date.now() - t0) / 1000, 's');
  await page.screenshot({ path: `${out}/01-menu.png` });
  await page.evaluate(() => document.querySelectorAll('button')[0].click());
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/02-hq.png` });
  console.log('travelling');
  await page.evaluate(() => window.__game.travelTo('ww1_somme_1916', false));
  await waitFor(page, () => window.__game.state === 'playing' || window.__game.state === 'cinematic', 300000);
  console.log('chapter loaded', (Date.now() - t0) / 1000, 's');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${out}/03-ww1-start.png` });
  console.log('issues', JSON.stringify(await page.evaluate(() => window.__game.assets.issues.map((i) => i.url))));
} catch (e) {
  console.error('FAILED', e.message);
  await page.screenshot({ path: `${out}/error.png` }).catch(() => {});
} finally {
  console.log(logs.filter((l) => !l.includes("[vite]") && !l.includes("useProgram")).slice(0, 60).join("\n"));
  await browser.close();
}
