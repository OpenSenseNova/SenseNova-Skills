// browser_picker.mjs — 浏览器可执行文件选择器
// 移植自 render.py 的 _ensure_browser_available()，四层优先级：
//   ① PPT_SKILL_BROWSER_EXE 环境变量覆盖（与 render.py 共用同一变量）
//   ② playwright 期望路径存在 → 优先同 revision 的 headless shell
//   ③ 期望版本缺失 → 扫描 PLAYWRIGHT_BROWSERS_PATH 本地缓存，
//      选架构匹配、可执行、revision 距离最近者（dist 相同时 headless shell 优先）
//   ④ 兜底返回 playwright 期望路径（行为同现状，让 playwright 自行报错）

import { existsSync, accessSync, constants, readdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { chromium } from 'playwright';

function isExecutable(p) {
  if (!existsSync(p)) return false;
  try {
    accessSync(p, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function expandHome(p) {
  if (p === '~') return homedir();
  if (p.startsWith('~/') || p.startsWith('~\\')) return join(homedir(), p.slice(2));
  return p;
}

// 各平台架构目录名（对应 render.py _scan_local_chromium 的 mac/linux 分支）
function archNames() {
  const plat = process.platform;
  const arch = process.arch;
  if (plat === 'darwin') {
    const mac = arch === 'arm64' ? 'mac-arm64' : 'mac-x64';
    return {
      shellArch: `chrome-headless-shell-${mac}`,
      fullArchs: [`chrome-${mac}`],
      shellExe: 'chrome-headless-shell',
      fullExe: join('Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing'),
    };
  }
  if (plat === 'win32') {
    return {
      shellArch: 'chrome-headless-shell-win64',
      fullArchs: ['chrome-win64'],
      shellExe: 'chrome-headless-shell.exe',
      fullExe: 'chrome.exe',
    };
  }
  // linux 及默认
  return {
    shellArch: 'chrome-headless-shell-linux64',
    fullArchs: ['chrome-linux64'],
    shellExe: 'chrome-headless-shell',
    fullExe: 'chrome',
  };
}

// 浏览器缓存根：优先环境变量，缺省 node playwright 默认路径
function browserCacheRoot() {
  const env = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (env && env !== '0') return expandHome(env);
  return join(homedir(), '.cache', 'ms-playwright');
}

// 从期望路径提取 revision，优先同 revision 的 headless shell
// （对应 render.py _prefer_headless_shell）
function headlessShellFor(exe) {
  const m = /chromium-(\d+)/.exec(exe);
  if (!m) return null;
  const rev = m[1];
  const parts = exe.split(/[\\/]/);
  const idx = parts.indexOf(`chromium-${rev}`);
  if (idx < 0) return null;
  const cacheRoot = parts.slice(0, idx).join('/');
  const { shellArch, shellExe } = archNames();
  const candidate = join(cacheRoot, `chromium_headless_shell-${rev}`, shellArch, shellExe);
  return isExecutable(candidate) ? candidate : null;
}

// 扫描本地缓存：期望版本缺失时的回退选择
// （对应 render.py _scan_local_chromium；排序键 (dist, isShell, path)，
//   dist 相同时 headless shell 优先，避开 render.py 里按路径字典序的瑕疵）
function scanLocal(expectedExe) {
  const root = browserCacheRoot();
  if (!existsSync(root)) return null;

  const em = /chromium-(\d+)/.exec(expectedExe || '');
  const desired = em ? parseInt(em[1], 10) : null;
  const { shellArch, fullArchs, shellExe, fullExe } = archNames();

  const entries = readdirSync(root, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name);

  const candidates = [];  // [dist, isShell(0=shell优先), path]

  // ① headless shell：chromium_headless_shell-<rev>/<shellArch>/<shellExe>
  for (const name of entries) {
    const m = /^chromium_headless_shell-(\d+)$/.exec(name);
    if (!m) continue;
    const rev = parseInt(m[1], 10);
    const c = join(root, name, shellArch, shellExe);
    if (isExecutable(c)) {
      const dist = desired === null ? rev : Math.abs(desired - rev);
      candidates.push([dist, 0, c]);
    }
  }

  // ② full chromium：chromium-<rev>/<fullArch>/<fullExe>
  for (const name of entries) {
    const m = /^chromium-(\d+)$/.exec(name);
    if (!m) continue;
    const rev = parseInt(m[1], 10);
    for (const arch of fullArchs) {
      const c = join(root, name, arch, fullExe);
      if (isExecutable(c)) {
        const dist = desired === null ? rev : Math.abs(desired - rev);
        candidates.push([dist, 1, c]);
        break;
      }
    }
  }

  if (candidates.length === 0) return null;
  candidates.sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
  return candidates[0][2];
}

export function pickBrowserExe() {
  // ① 环境变量覆盖（与 render.py 同一变量，box-agent 运行脚本已导出）
  const override = process.env.PPT_SKILL_BROWSER_EXE;
  if (override) {
    const p = resolve(expandHome(override));
    if (isExecutable(p)) return p;
    console.error(`[browser_picker] PPT_SKILL_BROWSER_EXE 不存在: ${p}，忽略并回退`);
  }

  // ② playwright 期望路径
  let expected = null;
  try {
    expected = chromium.executablePath();
  } catch {
    return null;
  }

  // ③ 期望路径存在 → 优选同 revision headless shell
  if (existsSync(expected)) {
    return headlessShellFor(expected) || expected;
  }

  // ④ 期望版本缺失 → 扫描本地缓存回退
  const local = scanLocal(expected);
  if (local) {
    console.error(`[browser_picker] 期望 ${expected} 不存在，回退到本地 ${local}`);
    return local;
  }

  // ⑤ 兜底返回期望路径（保持现状行为，让 playwright 自行报错）
  return expected;
}