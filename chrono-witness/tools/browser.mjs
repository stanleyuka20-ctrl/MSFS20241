// Shared headless-browser helper for smoke tests and benchmarks.
// Uses the system Chromium (Playwright build) with SwiftShader when no GPU is available.
import { chromium } from 'playwright-core';

export async function launch({ width = 1280, height = 720, gpu = false } = {}) {
  const exe = process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium';
  const args = gpu
    ? ['--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--use-angle=default']
    : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
  const browser = await chromium.launch({ executablePath: exe, args: [...args, '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width, height } });
  await page.addInitScript(() => {
    window.__automation = true;
  });
  const logs = [];
  page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
  return { browser, page, logs };
}

export async function waitFor(page, fn, timeout = 120000, arg) {
  return page.waitForFunction(fn, arg, { timeout, polling: 250 });
}
