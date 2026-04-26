#!/usr/bin/env node
/**
 * Headless screenshot of a single PPT-style HTML file.
 *
 * Re-uses the Playwright + chromium installed for html_to_pptx.mjs so this
 * file has no extra dependencies.
 *
 * Mirrors the behaviour of `agentos/scripts/ppt_html_screenshot.py`:
 *   - viewport defaults 1600x900 (matches our `.wrapper` size)
 *   - capture target = first of [`.wrapper`, `.slide.canvas`, `.slide`, body]
 *   - PNG output, locator.screenshot semantics
 *
 * Usage:
 *   node screenshot.mjs --html PATH --out PATH [--viewport WxH] [--wait MS]
 *
 * Stdout on success:  {"status":"ok","html":...,"out":...,"selector":...}
 * Stdout on failure:  {"status":"failed","error":...} (also exit code 1)
 */

import { chromium } from 'playwright';
import { resolve } from 'path';
import { existsSync, mkdirSync } from 'fs';
import { dirname } from 'path';

function getArg(name, def = null) {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : def;
}

function fail(error) {
  console.log(JSON.stringify({ status: 'failed', error: String(error) }));
  process.exit(1);
}

const htmlPath = getArg('--html');
const outPath = getArg('--out');
const viewport = getArg('--viewport', '1600x900');
const waitMs = parseInt(getArg('--wait', '500'), 10);

if (!htmlPath || !outPath) {
  fail('usage: --html PATH --out PATH [--viewport WxH] [--wait MS]');
}
if (!existsSync(htmlPath)) {
  fail(`html not found: ${htmlPath}`);
}

const [vw, vh] = viewport.split('x').map(Number);
if (!vw || !vh) fail(`bad --viewport: ${viewport}`);

mkdirSync(dirname(outPath), { recursive: true });

const url = 'file://' + resolve(htmlPath);
const SELECTORS = ['.wrapper', '.slide.canvas', '.slide', 'body'];

let browser;
try {
  browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: vw, height: vh },
    deviceScaleFactor: 1,
  });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  if (waitMs > 0) await page.waitForTimeout(waitMs);

  let chosen = null;
  for (const sel of SELECTORS) {
    const loc = page.locator(sel).first();
    if ((await loc.count()) === 0) continue;
    const box = await loc.boundingBox();
    if (!box || box.width <= 0 || box.height <= 0) continue;
    chosen = { sel, loc };
    break;
  }
  if (!chosen) fail('no capture target found (.wrapper / .slide / body)');

  await chosen.loc.screenshot({ path: outPath, type: 'png' });
  console.log(JSON.stringify({ status: 'ok', html: htmlPath, out: outPath, selector: chosen.sel }));
} catch (e) {
  fail(e?.message || String(e));
} finally {
  if (browser) await browser.close();
}
