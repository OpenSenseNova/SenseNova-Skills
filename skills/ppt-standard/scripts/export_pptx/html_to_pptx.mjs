#!/usr/bin/env node
// HTML → PPTX 转换器 CLI
// 用法: node html_to_pptx.mjs --deck-dir <path> [--output <filename>] [--force]

import { existsSync, statSync, mkdirSync } from 'node:fs';
import { resolve, basename, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * 首次运行时自动安装依赖（npm install + playwright chromium）。
 * 后续运行检测到 node_modules 和 chromium 已存在则跳过。
 */
function ensureDependencies() {
  const nodeModules = resolve(__dirname, 'node_modules');
  const pptxgenMarker = resolve(nodeModules, 'pptxgenjs');
  const playwrightMarker = resolve(nodeModules, 'playwright');

  if (!existsSync(pptxgenMarker) || !existsSync(playwrightMarker)) {
    console.error('[setup] 首次运行，正在安装 npm 依赖...');
    execSync('npm install --omit=dev', { cwd: __dirname, stdio: 'inherit' });
  }

  // 检查 chromium 是否已安装（playwright 在 ~/.cache/ms-playwright/ 下）
  try {
    const out = execSync('npx playwright install --dry-run chromium 2>&1', {
      cwd: __dirname, encoding: 'utf-8', timeout: 10000,
    });
    // dry-run 无输出或提示 already installed → 已安装
    if (out.includes('is already installed')) return;
  } catch { /* dry-run 失败或不支持，保守地尝试安装 */ }

  // 如果 chromium 二进制不存在，安装之
  try {
    execSync('node -e "require(\'playwright\').chromium.executablePath()"', {
      cwd: __dirname, encoding: 'utf-8', timeout: 5000,
    });
  } catch {
    console.error('[setup] 正在安装 Playwright Chromium（仅首次）...');
    execSync('npx playwright install chromium', { cwd: __dirname, stdio: 'inherit' });
  }
}

ensureDependencies();

// 依赖就绪后再 import 业务模块
const { ensureDeckPreconditions } = await import('./lib/cli_guards.mjs');
const { downloadRemoteImages } = await import('./lib/image_downloader.mjs');

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

async function main() {
  const args = parseArgs(process.argv.slice(2));

  // 先下载远程图片并规范化 deck 结构
  if (args.deckDir && !args.batch) {
    await downloadRemoteImages(args.deckDir);
  }

  const { htmlFiles } = ensureDeckPreconditions(args.deckDir, {
    force: args.force,
    batch: args.batch,
    pagesDir: args.pagesDir,
  });

  const { extractPages } = await import('./lib/dom_extractor.mjs');
  const { buildPptx } = await import('./lib/pptx_builder.mjs');

  console.error(`正在处理 ${htmlFiles.length} 个 HTML 页面...`);

  // DOM 提取
  console.error('步骤 1/2: 提取 DOM...');
  const pages = await extractPages(htmlFiles);

  // PPTX 构建：默认文件名与 deck_dir 目录名一致
  const outputFilename = args.output || (basename(args.deckDir) + '.pptx');
  const outputBase = args.outputDir || args.deckDir;
  mkdirSync(outputBase, { recursive: true });
  const outputPath = resolve(outputBase, outputFilename);
  console.error('步骤 2/2: 生成 PPTX...');
  const result = await buildPptx(pages, args.deckDir, outputPath);

  // 输出验证
  if (!existsSync(outputPath)) {
    console.error('错误: PPTX 文件未生成');
    process.exit(1);
  }

  const fileSize = statSync(outputPath).size;
  if (fileSize === 0) {
    console.error('错误: PPTX 文件大小为 0');
    process.exit(1);
  }

  // 成功输出（stdout）
  const sizeKB = (fileSize / 1024).toFixed(1);
  console.log(JSON.stringify({
    success: true,
    output: outputPath,
    pages: result.totalPages,
    converted: result.successCount,
    failed: result.failCount,
    fileSize: `${sizeKB} KB`,
  }));

  if (result.failCount > 0) {
    const details = (result.failures || [])
      .map(item => `${item.path}: ${item.message}`)
      .join('\n- ');
    console.error(`错误: ${result.failCount} 个页面转换失败\n- ${details}`);
    process.exit(1);
  }

  process.exit(0);
}

main().catch(err => {
  console.error(`错误: ${err.message}`);
  process.exit(1);
});
