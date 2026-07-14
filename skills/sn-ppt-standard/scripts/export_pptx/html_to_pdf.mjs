#!/usr/bin/env node
// HTML slides -> vector-preserving print PDF exporter.
// Usage: node html_to_pdf.mjs --deck-dir <path> [--output <filename>] [--force]

import { existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, resolve, basename, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const { ensureDependencies, hiddenChromiumLaunchOptions, installHiddenProcessHooks } = await import('./lib/browser_setup.mjs');
const { ensureDeckPreconditions } = await import('./lib/cli_guards.mjs');
const { downloadRemoteImages } = await import('./lib/image_downloader.mjs');

const PAGE_W = 1600;
const PAGE_H = 900;

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

function injectBase(html, htmlPath) {
  if (/<base\b/i.test(html)) return html;
  const baseHref = pathToFileURL(dirname(resolve(htmlPath)) + sep).href;
  const baseTag = `<base href="${baseHref}">`;
  if (/<head[^>]*>/i.test(html)) {
    return html.replace(/<head([^>]*)>/i, `<head$1>${baseTag}`);
  }
  return `${baseTag}\n${html}`;
}

function renderPdfHost(slides) {
  const slideJson = JSON.stringify(slides);
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @page { size: ${PAGE_W}px ${PAGE_H}px; margin: 0; }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      background: #fff;
    }
    .pdf-page {
      width: ${PAGE_W}px;
      height: ${PAGE_H}px;
      margin: 0;
      padding: 0;
      page-break-after: always;
      overflow: hidden;
      background: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .pdf-page:last-child { page-break-after: auto; }
    .frame {
      width: ${PAGE_W}px;
      height: ${PAGE_H}px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #fff;
    }
    iframe {
      border: 0;
      flex: 0 0 auto;
      transform-origin: center center;
      background: #fff;
    }
  </style>
</head>
<body>
  <main id="root"></main>
  <script>
    const PAGE_W = ${PAGE_W};
    const PAGE_H = ${PAGE_H};
    const SLIDES = ${slideJson};
    const SELECTORS = ['.wrapper', '.slide.canvas', '.slide', 'body'];
    window.__pdfSlidesTotal = SLIDES.length;
    window.__pdfSlidesReady = 0;
    window.__pdfFailures = [];

    function sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }

    function waitForLoad(iframe) {
      return new Promise(resolve => {
        iframe.addEventListener('load', resolve, { once: true });
      });
    }

    function findTarget(doc) {
      for (const selector of SELECTORS) {
        const node = doc.querySelector(selector);
        if (!node) continue;
        const box = node.getBoundingClientRect();
        if (box && box.width > 0 && box.height > 0) return node;
      }
      return doc.body || doc.documentElement;
    }

    function fitFrame(iframe) {
      const doc = iframe.contentDocument;
      const target = findTarget(doc);
      const box = target.getBoundingClientRect();
      const docEl = doc.documentElement;
      const body = doc.body || docEl;
      const rawW = Math.ceil(Math.max(box.width, target.scrollWidth || 0, body.scrollWidth || 0, PAGE_W));
      const rawH = Math.ceil(Math.max(box.height, target.scrollHeight || 0, body.scrollHeight || 0, PAGE_H));
      const contentW = Math.max(1, rawW);
      const contentH = Math.max(1, rawH);
      const scale = Math.min(PAGE_W / contentW, PAGE_H / contentH, 1);
      iframe.style.width = contentW + 'px';
      iframe.style.height = contentH + 'px';
      iframe.style.transform = 'scale(' + scale + ')';
      iframe.dataset.contentWidth = String(contentW);
      iframe.dataset.contentHeight = String(contentH);
      iframe.dataset.scale = String(scale);
    }

    async function waitForCharts(iframe) {
      const win = iframe.contentWindow;
      const doc = iframe.contentDocument;
      const expected = doc.querySelectorAll('[id^="chart_"]').length;
      if (!expected) return;
      const deadline = Date.now() + 5000;
      while (Date.now() < deadline) {
        if ((win.__pptxChartsReady || 0) >= expected) return;
        await sleep(150);
      }
    }

    async function mountSlides() {
      const root = document.getElementById('root');
      for (const slide of SLIDES) {
        const section = document.createElement('section');
        section.className = 'pdf-page';
        const frame = document.createElement('div');
        frame.className = 'frame';
        const iframe = document.createElement('iframe');
        iframe.setAttribute('title', slide.name);
        iframe.srcdoc = slide.html;
        frame.appendChild(iframe);
        section.appendChild(frame);
        root.appendChild(section);

        try {
          await waitForLoad(iframe);
          await waitForCharts(iframe);
          await sleep(300);
          fitFrame(iframe);
        } catch (e) {
          window.__pdfFailures.push({ path: slide.path, message: String(e && e.message || e) });
        } finally {
          window.__pdfSlidesReady += 1;
        }
      }
    }

    mountSlides();
  </script>
</body>
</html>`;
}

function loadSlides(htmlFiles) {
  return htmlFiles.map((htmlPath) => ({
    path: htmlPath,
    name: basename(htmlPath),
    html: injectBase(readFileSync(htmlPath, 'utf-8'), htmlPath),
  }));
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

  installHiddenProcessHooks();
  const { chromium } = await import('playwright');
  const browser = await chromium.launch(hiddenChromiumLaunchOptions());
  try {
    console.error(`正在处理 ${htmlFiles.length} 个 HTML 页面...`);
    const page = await browser.newPage({ viewport: { width: PAGE_W, height: PAGE_H } });
    const slides = loadSlides(htmlFiles);
    await page.setContent(renderPdfHost(slides), { waitUntil: 'load' });
    await page.waitForFunction(
      () => window.__pdfSlidesReady === window.__pdfSlidesTotal,
      null,
      { timeout: Math.max(30000, htmlFiles.length * 8000) },
    );
    await page.waitForTimeout(500);

    const failures = await page.evaluate(() => window.__pdfFailures || []);
    const sizing = await page.evaluate(() => [...document.querySelectorAll('iframe')].map((iframe) => ({
      name: iframe.getAttribute('title'),
      contentWidth: Number(iframe.dataset.contentWidth || 0),
      contentHeight: Number(iframe.dataset.contentHeight || 0),
      scale: Number(iframe.dataset.scale || 1),
    })));

    await page.pdf({
      path: outputPath,
      width: `${PAGE_W}px`,
      height: `${PAGE_H}px`,
      margin: { top: 0, right: 0, bottom: 0, left: 0 },
      printBackground: true,
      preferCSSPageSize: true,
    });
    await page.close();

    if (!existsSync(outputPath) || statSync(outputPath).size === 0) {
      throw new Error('PDF file was not generated');
    }

    const fileSize = statSync(outputPath).size;
    const sizeKB = (fileSize / 1024).toFixed(1);
    console.log(JSON.stringify({
      success: true,
      output: outputPath,
      pages: htmlFiles.length,
      converted: htmlFiles.length - failures.length,
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
