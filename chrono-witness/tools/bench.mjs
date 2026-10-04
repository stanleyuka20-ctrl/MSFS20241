// Runs the in-game benchmark routes headlessly and writes JSON results.
// Usage: node tools/bench.mjs [baseUrl] [width] [height] [preset] [seconds] [routes,comma] [--gpu]
// NOTE: in a container without a GPU this uses SwiftShader (CPU rendering). Those numbers say nothing
// about real hardware; run on the reference system for meaningful results (see docs/PERFORMANCE.md).
import { launch, waitFor } from './browser.mjs';
import fs from 'node:fs';

const [base = 'http://localhost:5173/', W = '1920', H = '1080', preset = 'medium', seconds = '20', routesArg = 'ww1_explore,ww1_crowd,ww1_barrage,hq,travel'] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const gpu = process.argv.includes('--gpu');
const { browser, page, logs } = await launch({ width: +W, height: +H, gpu });
await page.addInitScript((p) => {
  const s = JSON.parse(localStorage.getItem('chrono-witness.settings') || '{}');
  s.graphics = { ...(s.graphics || {}), preset: p, adaptiveQuality: false, fpsCap: 0 };
  localStorage.setItem('chrono-witness.settings', JSON.stringify(s));
}, preset);
await page.goto(base);
await waitFor(page, () => window.__game && document.querySelector('.title-logo'), 180000);
await page.evaluate((p) => {
  const g = window.__game;
  if (p !== 'custom') g.setGraphicsPreset(p);
  g.settings.graphics.adaptiveQuality = false;
  g.applySettings(true);
}, preset);
const out = { preset, size: `${W}x${H}`, gpuFlag: gpu, results: [] };
for (const r of routesArg.split(',')) {
  const t0 = Date.now();
  const res = await page.evaluate(([id, s]) => window.__game.runBenchmark(id, +s), [r, seconds]);
  res.wallSeconds = Math.round((Date.now() - t0) / 1000);
  out.results.push(res);
  console.log(`${r}: avg ${res.avgFps} fps, 1% low ${res.low1Fps}, p99 ${res.p99FrameMs} ms, max ${res.maxFrameMs} ms, spikes ${res.spikes}, calls ${res.peakDrawCalls}, tris ${res.peakTriangles}, heap ${res.jsHeapMB} MB`);
  if (res.loads?.length) console.log('  loads', JSON.stringify(res.loads));
}
fs.mkdirSync('bench-results', { recursive: true });
const file = `bench-results/bench-${preset}-${W}x${H}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
fs.writeFileSync(file, JSON.stringify(out, null, 2));
console.log('GPU:', out.results[0]?.environment?.gpu, '\nwritten', file);
const errs = logs.filter((l) => l.includes('pageerror'));
if (errs.length) console.log(errs.join('\n'));
await browser.close();
