#!/usr/bin/env node
// HTML slides -> vector-preserving print PDF exporter.
// Usage: node html_to_pdf.mjs --deck-dir <path> [--output <filename>] [--force]

import { existsSync, mkdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, resolve, basename } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const { ensureDeckPreconditions } = await import('./lib/cli_guards.mjs');
const { downloadRemoteImages } = await import('./lib/image_downloader.mjs');

const PAGE_W = 1600;
const PAGE_H = 900;
const TARGET_SELECTORS = ['.wrapper', '.slide.canvas', '.slide', 'body'];

function ensureDependencies(baseDir) {
  const nodeModules = resolve(baseDir, 'node_modules');
  const pptxgenMarker = resolve(nodeModules, 'pptxgenjs');
  const playwrightMarker = resolve(nodeModules, 'playwright');
  const pdfLibMarker = resolve(nodeModules, 'pdf-lib');

  if (!existsSync(pptxgenMarker) || !existsSync(playwrightMarker) || !existsSync(pdfLibMarker)) {
    console.error('[setup] 首次运行，正在安装 npm 依赖...');
    try {
      execSync('npm install --omit=dev', { cwd: baseDir, stdio: 'inherit' });
    } catch (e) {
      throw new Error(`npm install failed: ${e.message}. Headless browser environment unavailable.`);
    }
  }

  try {
    const out = execSync('npx playwright install --dry-run chromium 2>&1', {
      cwd: baseDir, encoding: 'utf-8', timeout: 10000,
    });
    if (out.includes('is already installed')) return;
  } catch {
    // Dry-run can fail on older Playwright builds; try executable detection.
  }

  try {
    execSync('node -e "require(\'playwright\').chromium.executablePath()"', {
      cwd: baseDir, encoding: 'utf-8', timeout: 5000,
    });
  } catch {
    console.error('[setup] 正在安装 Playwright Chromium（仅首次）...');
    try {
      execSync('npx playwright install chromium', { cwd: baseDir, stdio: 'inherit' });
    } catch (e) {
      throw new Error(`Chromium installation failed: ${e.message}. Cannot install headless browser in this environment.`);
    }
  }
}

function parseArgs(args) {
  const result = { deckDir: null, pagesDir: null, output: null, outputDir: null, force: false, batch: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--deck-dir' && args[i + 1]) {
      result.deckDir = resolve(args[i + 1]);
      i++;
    } else if (args[i] === '--pages-dir' && args[i + 1]) {
      result.pagesDir = resolve(args[i + 1]);
      i++;
    } else if (args[i] === '--output' && args[i + 1]) {
      result.output = args[i + 1];
      i++;
    } else if (args[i] === '--output-dir' && args[i + 1]) {
      result.outputDir = resolve(args[i + 1]);
      i++;
    } else if (args[i] === '--force') {
      result.force = true;
    } else if (args[i] === '--batch') {
      result.batch = true;
      result.force = true;
    }
  }
  return result;
}

async function waitForFonts(page) {
  await page.evaluate(() => {
    if (!document.fonts || !document.fonts.ready) return true;
    return document.fonts.ready.then(() => true);
  }).catch(() => true);
}

async function waitForCharts(page) {
  const expected = await page.locator('[id^="chart_"]').count();
  if (!expected) return;
  await page.waitForFunction(
    (count) => (window.__pptxChartsReady || 0) >= count,
    expected,
    { timeout: 5000 },
  ).catch(() => undefined);
}

async function fitSlideForPrint(page) {
  return page.evaluate(({ pageW, pageH, selectors }) => {
    function findTarget() {
      for (const selector of selectors) {
        const node = document.querySelector(selector);
        if (!node) continue;
        const box = node.getBoundingClientRect();
        if (box && box.width > 0 && box.height > 0) return node;
      }
      return document.body || document.documentElement;
    }

    const target = findTarget();
    const box = target.getBoundingClientRect();
    const docEl = document.documentElement;
    const body = document.body || docEl;
    const rawW = Math.ceil(Math.max(box.width, target.scrollWidth || 0, body.scrollWidth || 0, pageW));
    const rawH = Math.ceil(Math.max(box.height, target.scrollHeight || 0, body.scrollHeight || 0, pageH));
    const contentW = Math.max(1, rawW);
    const contentH = Math.max(1, rawH);
    const scale = Math.min(pageW / contentW, pageH / contentH, 1);
    const left = Math.max(0, (pageW - contentW * scale) / 2);
    const top = Math.max(0, (pageH - contentH * scale) / 2);

    const style = document.createElement('style');
    style.textContent = `
      @page { size: ${pageW}px ${pageH}px; margin: 0; }
      html, body {
        width: ${pageW}px !important;
        height: ${pageH}px !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
      }
      *, *::before, *::after {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }
    `;
    document.head.appendChild(style);

    if (target !== body && target !== docEl) {
      target.style.position = 'absolute';
      target.style.left = '0';
      target.style.top = '0';
      target.style.margin = '0';
      target.style.transformOrigin = 'top left';
      target.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
    } else {
      target.style.transformOrigin = 'top left';
      target.style.transform = `scale(${scale})`;
    }

    return {
      contentWidth: contentW,
      contentHeight: contentH,
      scale,
      target: target === body ? 'body' : target === docEl ? 'html' : (
        target.id ? `#${target.id}` : target.className ? `.${String(target.className).trim().split(/\s+/).join('.')}` : target.tagName.toLowerCase()
      ),
    };
  }, { pageW: PAGE_W, pageH: PAGE_H, selectors: TARGET_SELECTORS });
}

async function renderSlidePdf(browser, htmlPath) {
  const page = await browser.newPage({ viewport: { width: PAGE_W, height: PAGE_H } });
  try {
    await page.emulateMedia({ media: 'screen' });
    await page.goto(pathToFileURL(resolve(htmlPath)).href, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(300);
    await waitForFonts(page);
    await waitForCharts(page);
    const sizing = await fitSlideForPrint(page);
    const pdf = await page.pdf({
      width: `${PAGE_W}px`,
      height: `${PAGE_H}px`,
      margin: { top: 0, right: 0, bottom: 0, left: 0 },
      printBackground: true,
      preferCSSPageSize: true,
    });
    return {
      pdf,
      sizing: { name: basename(htmlPath), ...sizing },
    };
  } finally {
    await page.close();
  }
}

async function mergePdfBuffers(buffers) {
  const { PDFDocument } = await import('pdf-lib');
  const merged = await PDFDocument.create();
  for (const buffer of buffers) {
    const source = await PDFDocument.load(buffer);
    const pages = await merged.copyPages(source, source.getPageIndices());
    for (const page of pages) {
      merged.addPage(page);
    }
  }
  return Buffer.from(await merged.save());
}

async function main() {
  const args = parseArgs(process.argv.slice(2));

  try {
    ensureDependencies(__dirname);
  } catch (e) {
    console.log(JSON.stringify({
      status: 'skipped',
      reason: 'headless_browser_unavailable',
      detail: `Playwright/Chromium cannot be installed in this environment: ${e.message}. PDF export skipped - HTML pages are the final deliverable.`,
      converted: 0,
      pages: 0,
      skipped: true,
    }));
    return;
  }

  if (args.deckDir && !args.batch) {
    await downloadRemoteImages(args.deckDir);
  }

  const { htmlFiles } = ensureDeckPreconditions(args.deckDir, {
    force: args.force,
    batch: args.batch,
    pagesDir: args.pagesDir,
  });

  const outputFilename = args.output || (basename(args.deckDir) + '.pdf');
  const outputBase = args.outputDir || args.deckDir;
  mkdirSync(outputBase, { recursive: true });
  const outputPath = resolve(outputBase, outputFilename);

  const { chromium } = await import('playwright');
  const browser = await chromium.launch();
  try {
    console.error(`正在处理 ${htmlFiles.length} 个 HTML 页面...`);
    const failures = [];
    const sizing = [];
    const pdfBuffers = [];

    for (const htmlPath of htmlFiles) {
      try {
        const rendered = await renderSlidePdf(browser, htmlPath);
        pdfBuffers.push(rendered.pdf);
        sizing.push(rendered.sizing);
      } catch (e) {
        failures.push({ path: htmlPath, message: e?.message || String(e) });
      }
    }

    if (pdfBuffers.length === 0) {
      throw new Error('No HTML pages could be converted to PDF');
    }

    writeFileSync(outputPath, await mergePdfBuffers(pdfBuffers));

    if (!existsSync(outputPath) || statSync(outputPath).size === 0) {
      throw new Error('PDF file was not generated');
    }

    const fileSize = statSync(outputPath).size;
    const sizeKB = (fileSize / 1024).toFixed(1);
    console.log(JSON.stringify({
      success: true,
      output: outputPath,
      pages: htmlFiles.length,
      converted: pdfBuffers.length,
      failed: failures.length,
      fileSize: `${sizeKB} KB`,
      sizing,
      failures: failures.length ? failures : undefined,
    }));
    if (failures.length > 0) process.exit(1);
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error(`错误: ${err.message}`);
  process.exit(1);
});
