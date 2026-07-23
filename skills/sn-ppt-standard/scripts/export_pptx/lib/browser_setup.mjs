import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { execSync } from 'node:child_process';

const require = createRequire(import.meta.url);
const hiddenProcessOptions = { windowsHide: true };
let hiddenHooksInstalled = false;
const patchedModules = new WeakSet();

/** Force child processes created by Playwright internals to stay backgrounded on Windows. */
export function installHiddenProcessHooks() {
  if (hiddenHooksInstalled || process.platform !== 'win32') {
    return;
  }

  hiddenHooksInstalled = true;
  patchChildProcessModule(require('node:child_process'));
  patchChildProcessModule(require('child_process'));
}

function patchChildProcessModule(childProcess) {
  if (patchedModules.has(childProcess)) {
    return;
  }

  patchedModules.add(childProcess);
  const originalSpawn = childProcess.spawn.bind(childProcess);
  childProcess.spawn = (command, argsOrOptions, options) => {
    if (Array.isArray(argsOrOptions)) {
      return originalSpawn(command, argsOrOptions, { ...options, windowsHide: true });
    }
    if (argsOrOptions && typeof argsOrOptions === 'object') {
      return originalSpawn(command, { ...argsOrOptions, windowsHide: true });
    }
    return originalSpawn(command, { windowsHide: true });
  };
}

/** Standard Chromium launch options for background rendering/export. */
export function hiddenChromiumLaunchOptions(options = {}) {
  return {
    headless: true,
    ...options,
    args: [
      ...(options.args || []),
      '--disable-breakpad',
      '--disable-crash-reporter',
    ],
  };
}

/**
 * Ensure the local Node and Playwright dependencies needed by HTML export are
 * available. Missing browser support is surfaced as a normal skipped export by
 * callers instead of crashing the PPT pipeline.
 */
export function ensureDependencies(baseDir) {
  installHiddenProcessHooks();
  const nodeModules = resolve(baseDir, 'node_modules');
  const pptxgenMarker = resolve(nodeModules, 'pptxgenjs');
  const playwrightMarker = resolve(nodeModules, 'playwright');

  if (!existsSync(pptxgenMarker) || !existsSync(playwrightMarker)) {
    console.error('[setup] 首次运行，正在安装 npm 依赖...');
    try {
      execSync('npm install --omit=dev', { ...hiddenProcessOptions, cwd: baseDir, stdio: 'inherit' });
    } catch (e) {
      throw new Error(`npm install failed: ${e.message}. Headless browser environment unavailable.`);
    }
  }

  try {
    const out = execSync('npx playwright install --dry-run chromium 2>&1', {
      ...hiddenProcessOptions,
      cwd: baseDir, encoding: 'utf-8', timeout: 10000,
    });
    if (out.includes('is already installed')) return;
  } catch {
    // Dry-run can fail on older Playwright builds; try executable detection.
  }

  try {
    execSync('node -e "require(\'playwright\').chromium.executablePath()"', {
      ...hiddenProcessOptions,
      cwd: baseDir, encoding: 'utf-8', timeout: 5000,
    });
  } catch {
    console.error('[setup] 正在安装 Playwright Chromium（仅首次）...');
    try {
      execSync('npx playwright install chromium', { ...hiddenProcessOptions, cwd: baseDir, stdio: 'inherit' });
    } catch (e) {
      throw new Error(`Chromium installation failed: ${e.message}. Cannot install headless browser in this environment.`);
    }
  }
}
