#!/usr/bin/env node
// HTML -> PNG screenshots -> image-only PPTX exporter.
//
// This complements html_to_pptx.mjs. The normal exporter rebuilds editable PPTX
// objects from DOM/IR; this exporter preserves visual fidelity by rasterizing
// each HTML slide and inserting one full-slide image per page.
//
// Usage:
//   node html_to_image_pptx.mjs --deck-dir <path> [--output <filename>]
//     [--output-dir <path>] [--viewport 1600x900] [--wait 1000] [--force]

import { existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import { resolve, basename, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const { ensureDeckPreconditions } = await import('./lib/cli_guards.mjs');
const { downloadRemoteImages } = await import('./lib/image_downloader.mjs');

const SLIDE_W = 10;
const SLIDE_H = 5.625;
const CAPTURE_SELECTORS = ['.wrapper', '.slide.canvas', '.slide', 'body'];

function parseArgs(args) {
  const result = {
    deckDir: null,
    pagesDir: null,
    output: null,
    outputDir: null,
    force: false,
    batch: false,
    viewport: '1600x900',
    waitMs: 1000,
  };
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--deck-dir' && args[i + 1]) {
      result.deckDir = resolve(args[++i]);
    } else if (arg === '--pages-dir' && args[i + 1]) {
      result.pagesDir = resolve(args[++i]);
    } else if (arg === '--output' && args[i + 1]) {
      result.output = args[++i];
    } else if (arg === '--output-dir' && args[i + 1]) {
      result.outputDir = resolve(args[++i]);
    } else if (arg === '--viewport' && args[i + 1]) {
      result.viewport = args[++i];
    } else if (arg === '--wait' && args[i + 1]) {
      result.waitMs = Number(args[++i]);
    } else if (arg === '--force') {
      result.force = true;
    } else if (arg === '--batch') {
      result.batch = true;
      result.force = true;
    }
  }
  return result;
}

function ensureDependencies() {
  const nodeModules = resolve(__dirname, 'node_modules');
  const pptxgenMarker = resolve(nodeModules, 'pptxgenjs');
  const playwrightMarker = resolve(nodeModules, 'playwright');

  if (!existsSync(pptxgenMarker) || !existsSync(playwrightMarker)) {
    console.error('[setup] 首次运行，正在安装 npm 依赖...');
    try {
      execSync('npm install --omit=dev', { cwd: __dirname, stdio: 'inherit' });
    } catch (e) {
      throw new Error(`npm install failed: ${e.message}. Headless browser environment unavailable.`);
    }
  }

  try {
    execSync('node -e "const fs=require(\'fs\'); const p=require(\'playwright\').chromium.executablePath(); if(!fs.existsSync(p)){ console.error(p); process.exit(2); }"', {
      cwd: __dirname,
      encoding: 'utf-8',
      timeout: 5000,
    });
  } catch {
    console.error('[setup] 正在安装 Playwright Chromium（仅首次）...');
    try {
      execSync('npx playwright install chromium', { cwd: __dirname, stdio: 'inherit' });
    } catch (e) {
      throw new Error(`Chromium installation failed: ${e.message}. Cannot install headless browser in this environment.`);
    }
  }
}

function parseViewport(viewport) {
  const [w, h] = String(viewport).split('x').map(Number);
  if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) {
    throw new Error(`bad --viewport: ${viewport}`);
  }
  return { width: Math.floor(w), height: Math.floor(h) };
}

function pageNumberFromPath(path) {
  const match = /page_(\d+)\.html?$/i.exec(basename(path));
  return match ? Number(match[1]) : null;
}

async function waitForCharts(page, timeoutMs = 8000) {
  const expected = await page.evaluate(() => {
    const chartNodes = Array.from(document.querySelectorAll('[id^="chart_"], .echarts, [data-chart]'));
    return chartNodes.length;
  });
  if (!expected) return;
  try {
    await page.waitForFunction(
      count => (window.__pptxChartsReady || 0) >= count,
      expected,
      { timeout: timeoutMs },
    );
  } catch {
    // Best-effort only. Some pages use static SVG/CSS charts and never set the
    // counter. The extra --wait still gives the browser a chance to settle.
  }
}

async function captureHtml(page, htmlPath, outPath, waitMs) {
  const url = 'file://' + resolve(htmlPath);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
  await waitForCharts(page);
  if (waitMs > 0) {
    await page.waitForTimeout(waitMs);
  }

  let chosen = null;
  for (const selector of CAPTURE_SELECTORS) {
    const loc = page.locator(selector).first();
    if ((await loc.count()) === 0) continue;
    const box = await loc.boundingBox();
    if (!box || box.width <= 0 || box.height <= 0) continue;
    chosen = { selector, loc, box };
    break;
  }
  if (!chosen) {
    throw new Error(`no capture target found in ${htmlPath}`);
  }

  await chosen.loc.screenshot({ path: outPath, type: 'png' });
  return {
    html: htmlPath,
    png: outPath,
    selector: chosen.selector,
    width: Math.round(chosen.box.width),
    height: Math.round(chosen.box.height),
  };
}

async function capturePages(htmlFiles, deckDir, viewport, waitMs, chromium) {
  const screenshotsDir = resolve(deckDir, 'screenshots');
  mkdirSync(screenshotsDir, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  const captures = [];
  try {
    for (const htmlFile of htmlFiles) {
      const pageNo = pageNumberFromPath(htmlFile);
      const name = pageNo ? `page_${String(pageNo).padStart(3, '0')}.png` : `${basename(htmlFile, '.html')}.png`;
      const outPath = resolve(screenshotsDir, name);
      const capture = await captureHtml(page, htmlFile, outPath, waitMs);
      captures.push({ ...capture, pageNo });
      console.error(`[capture] ${basename(htmlFile)} -> ${outPath} (${capture.width}x${capture.height}, ${capture.selector})`);
    }
  } finally {
    await browser.close();
  }
  return captures;
}

async function buildImagePptx(captures, outputPath, PptxGenJS) {
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'HTML_IMAGE_SLIDE', width: SLIDE_W, height: SLIDE_H });
  pptx.layout = 'HTML_IMAGE_SLIDE';
  pptx.author = 'SenseNova-Skills sn-ppt-standard';
  pptx.subject = 'Image-based PPTX exported from HTML screenshots';
  pptx.title = basename(outputPath, '.pptx');
  pptx.company = 'SenseNova-Skills';
  pptx.lang = 'zh-CN';
  pptx.theme = {
    headFontFace: 'Microsoft YaHei',
    bodyFontFace: 'Microsoft YaHei',
    lang: 'zh-CN',
  };

  for (const capture of captures) {
    const slide = pptx.addSlide();
    slide.background = { color: 'FFFFFF' };
    slide.addImage({
      path: capture.png,
      x: 0,
      y: 0,
      w: SLIDE_W,
      h: SLIDE_H,
    });
    slide.addNotes(`Source HTML: ${capture.html}\nScreenshot: ${capture.png}`);
  }

  await pptx.writeFile({ fileName: outputPath });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  try {
    ensureDependencies();
  } catch (e) {
    console.log(JSON.stringify({
      status: 'skipped',
      reason: 'headless_browser_unavailable',
      detail: `Playwright/Chromium cannot be installed in this environment: ${e.message}. Image-based PPTX export skipped — HTML pages are the final deliverable.`,
      converted: 0,
      pages: 0,
      skipped: true,
    }));
    return;
  }

  if (args.deckDir && !args.batch) {
    await downloadRemoteImages(args.deckDir);
  }

  const [{ chromium }, { default: PptxGenJS }] = await Promise.all([
    import('playwright'),
    import('pptxgenjs'),
  ]);

  const { htmlFiles } = ensureDeckPreconditions(args.deckDir, {
    force: args.force,
    batch: args.batch,
    pagesDir: args.pagesDir,
  });

  const viewport = parseViewport(args.viewport);
  console.error(`正在将 ${htmlFiles.length} 个 HTML 页面截图为 PNG...`);
  const captures = await capturePages(htmlFiles, args.deckDir, viewport, args.waitMs, chromium);

  const outputFilename = args.output || `${basename(args.deckDir)}.image.pptx`;
  const outputBase = args.outputDir || args.deckDir;
  mkdirSync(outputBase, { recursive: true });
  const outputPath = resolve(outputBase, outputFilename);

  console.error('正在将 PNG 全页插入 PPTX...');
  await buildImagePptx(captures, outputPath, PptxGenJS);

  if (!existsSync(outputPath) || statSync(outputPath).size === 0) {
    throw new Error('image-based PPTX file was not generated');
  }

  const manifestPath = resolve(args.deckDir, 'screenshots', 'image_pptx_manifest.json');
  writeFileSync(
    manifestPath,
    JSON.stringify({ output: outputPath, pages: captures.length, captures }, null, 2),
    'utf-8',
  );

  console.log(JSON.stringify({
    success: true,
    mode: 'html-image-pptx',
    output: outputPath,
    screenshotsDir: resolve(args.deckDir, 'screenshots'),
    manifest: manifestPath,
    pages: captures.length,
    converted: captures.length,
    failed: 0,
    fileSize: `${(statSync(outputPath).size / 1024).toFixed(1)} KB`,
  }));
}

main().catch(err => {
  console.error(`错误: ${err?.message || String(err)}`);
  process.exit(1);
});
