#!/usr/bin/env python3
"""HTML -> PNG 渲染脚本(sn-ppt-standard 自带,可移植)。

任何有 shell / 代码执行能力的脚手架都能直接跑它来渲染一页幻灯片,**不依赖宿主提供 render 工具**:

    python render.py <html路径> <输出png路径> [宽=1600] [高=900]
    python render.py --batch <workspace> [--pages 1,2,7] [--width 1600] [--height 900]

成功时把输出 png 的绝对路径打到 stdout;失败打到 stderr 并以非 0 退出。

注意:<html路径> / <输出png路径> 按**当前工作目录**解析(脚本对参数做 abspath);
调用方(slide subagent)须在**工作区根目录**运行本命令——skills/... 与 slides/ / renders/ 都相对工作区根。
依赖处理:
- 优先使用当前 Python 环境里的 Playwright;若导入失败,再尝试 `PPT_SKILL_PLAYWRIGHT_PATHS`
  指定的备用依赖路径,最后尝试兼容路径 `/tmp/pydeps` / `/tmp/wp`。
- 用 Playwright 的 Chromium 渲染(需先 `playwright install chromium` 或使用已安装浏览器)。
- headless Chromium 缺的系统 .so 自动从 `~/pwdeps/lib`(再退 `~/cdeps/lib`)补进 LD_LIBRARY_PATH。
- 中文字体需先装到 `~/.fonts`(Noto Sans SC / Noto Serif SC)并 `fc-cache`,否则中文渲染成豆腐块。
渲染时等 `document.fonts.ready` 再截图(防豆腐块 / 截到半截);device_scale_factor=2 出高清图。
"""
from contextlib import contextmanager
import argparse
import hashlib
import json
import os
import sys
import time
import importlib
import importlib.util as _iutil
import signal
import re
import glob
import platform
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.expanduser("~/.cache/ms-playwright"))

# chromium 稳定性参数。关 GPU / 软渲染省内存,降低高并发下崩溃(TargetClosed)。
# ★--disable-dev-shm-usage 的坑(2026-07-16 崩池真因)★:它逼 chromium 把 shm 从 /dev/shm 改用 /tmp。
#   仅当 /dev/shm 是默认小盘(Docker 64MB)时才该加;若 /dev/shm 是大 RAM tmpfs(CCI=128G),
#   加了反而把 shm 从「快 RAM」赶到「慢磁盘 overlay /tmp」→ 高并发磁盘 I/O 风暴 → D-state → 崩池。
#   故按 /dev/shm 实际大小动态决定(env RENDER_FORCE_DISABLE_DEVSHM=1 强制加 / =0 强制不加)。
#   ⚠️ 本补丁位于 skill 目录内,同步/覆盖 skill 会冲掉,覆盖后须重打(见 memory render-brokenpool-chromium-exhaustion)。
def _devshm_bytes():
    try:
        st = os.statvfs("/dev/shm")
        return st.f_blocks * st.f_frsize
    except Exception:
        return 0

def _should_disable_devshm():
    # ★2026-07-16 OOM 事故订正★:RAM /dev/shm(tmpfs)占用**算进 cgroup 256G 内存**,
    #   80~128 并发下几十个 chromium 的 shm 把 RAM 顶到 100% → OOM 级联。
    #   故默认改回 disk /tmp(不吃 cgroup RAM);D-state 风暴改由 flock 上限(RENDER_GLOBAL_LIMIT)+
    #   适度并发压住(concurrent chromium 远低于当年 48×8 无界的 ~147)。
    #   RENDER_FORCE_DISABLE_DEVSHM=0 可强制走 RAM(仅当 /dev/shm 不计入 cgroup 时才安全,CCI 不满足)。
    force = os.environ.get("RENDER_FORCE_DISABLE_DEVSHM", "")
    if force == "0":
        return False
    return True

LAUNCH_ARGS = ["--no-sandbox", "--disable-gpu",
               "--disable-software-rasterizer", "--disable-extensions",
               "--disable-breakpad", "--disable-crash-reporter",
               "--disable-features=Crashpad", "--noerrdialogs"]
if _should_disable_devshm():
    LAUNCH_ARGS.insert(1, "--disable-dev-shm-usage")

# —— 全局并发 chromium 上限(跨进程 flock 槽)——
# render.py 在各 worker 子进程里独立跑;整机同时渲染数 = Σ 各 deck 各 slide。RENDER_GLOBAL_LIMIT 卡住它。
# RAM-shm 治本后此上限降级为「防跑飞」软保险(设=WK)。=0(默认)关闭。flock:进程崩/被杀 OS 自动放锁不泄漏。
import fcntl as _fcntl
import atexit as _atexit
import random as _random
def _acquire_render_slot():
    limit = int(os.environ.get("RENDER_GLOBAL_LIMIT", "0") or "0")
    if limit <= 0:
        return None
    lock_dir = os.environ.get("RENDER_LOCK_DIR", "/tmp/ppt_render_slots")
    try:
        os.makedirs(lock_dir, exist_ok=True)
    except Exception:
        return None
    slots = list(range(limit)); _random.shuffle(slots)
    deadline = time.time() + int(os.environ.get("RENDER_SLOT_TIMEOUT", "900") or "900")
    waited = False
    while True:
        for i in slots:
            try:
                fd = os.open(os.path.join(lock_dir, "slot_%d.lock" % i), os.O_CREAT | os.O_RDWR, 0o666)
            except Exception:
                continue
            try:
                _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                return fd
            except OSError:
                os.close(fd)
        if time.time() > deadline:
            print("警告: 等 render 全局槽超时,直接渲染...", file=sys.stderr)
            return None
        if not waited:
            print("· render 全局并发已满(%d),排队等槽…" % limit, file=sys.stderr); waited = True
        time.sleep(0.3 + _random.random() * 0.5)
def _release_render_slot(fd):
    if fd is None:
        return
    try:
        _fcntl.flock(fd, _fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        os.close(fd)
    except Exception:
        pass


class BrowserUnavailable(RuntimeError):
    pass


# —— 中文语境半角标点 → 全角:渲染前机械兜底(模型仍应写对,见 SKILL §四「标点跟着语言走」)——
# 只把「紧跟在中文字之后的半角 , ; : ! ?」转全角;数字/英文/代码/日期因前导非中文字,天然不受影响。
_CJK = r"一-鿿㐀-䶿豈-﫿"
_PUNCT_FULL = {",": "，", ";": "；", ":": "：", "!": "！", "?": "？"}
_PUNCT_RE = re.compile(r"(?<=[" + _CJK + r"])([,;:!?])")
# 切出 <script>/<style> 整块 + 任意标签;其余即文本节点。标签 / 脚本 / 样式内不动。
_SEG_RE = re.compile(r"(<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]*>)", re.I)


def _normalize_cjk_punct(html_text):
    """把标签外文本节点里「中文后的半角 , ; : ! ?」转全角;<script>/<style>/标签本身与
    非中文语境(数字/英文/代码)一律不动。幂等——全角再跑仍是全角。"""
    out = []
    for seg in _SEG_RE.split(html_text):
        if not seg:
            continue
        if seg[0] == "<":                      # 标签 / script / style 块 → 原样
            out.append(seg)
        else:                                  # 文本节点 → 只转中文后半角标点
            out.append(_PUNCT_RE.sub(lambda m: _PUNCT_FULL[m.group(1)], seg))
    return "".join(out)


def _bundled_dep_paths():
    """Return optional Python dependency roots for non-standard runtimes."""
    raw = os.environ.get("PPT_SKILL_PLAYWRIGHT_PATHS", "")
    paths = [p for p in raw.split(os.pathsep) if p]
    paths += ["/tmp/pydeps", "/tmp/wp"]
    seen, out = set(), []
    for path in paths:
        path = os.path.abspath(os.path.expanduser(path))
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _load_bundled_playwright():
    """Fall back to configured or runtime-provided Python deps when normal import fails."""
    paths = _bundled_dep_paths()
    for path in paths:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
    for mod in ("greenlet",):
        spec = _iutil.find_spec(mod)
        if spec:
            importlib.import_module(mod)
    for path in paths:
        init_py = os.path.join(path, "playwright", "__init__.py")
        if os.path.isfile(init_py):
            spec = _iutil.spec_from_file_location(
                "playwright", init_py, submodule_search_locations=[os.path.join(path, "playwright")])
            mod = _iutil.module_from_spec(spec)
            sys.modules["playwright"] = mod
            spec.loader.exec_module(mod)
            break


def _sync_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception:
        _load_bundled_playwright()
        from playwright.sync_api import sync_playwright
        return sync_playwright


@contextmanager
def _alarm_timeout(seconds, label):
    """Raise TimeoutError if a Playwright start/stop call hangs."""
    if not hasattr(signal, "SIGALRM") or seconds <= 0:
        yield
        return

    def _handler(_signum, _frame):
        raise TimeoutError(f"{label} timed out after {seconds}s")

    old = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _call_with_timeout(fn, seconds, label):
    with _alarm_timeout(seconds, label):
        return fn()


def _stop_playwright(p):
    try:
        _call_with_timeout(p.stop, 5, "Playwright stop")   # 1s→5s:高并发下 1s 常超时→chromium 没关干净泄漏
    except Exception as e:
        print(f"警告: Playwright 清理失败或超时({e});即将继续/退出。", file=sys.stderr)


def _reap_leaked_chromium():
    """★收割泄漏的 chromium(2026-07-18 内存泄漏事故)★:b.close()/p.stop 高并发下常超时→chromium(含
    renderer/gpu/zygote 子进程)没被杀干净、500+ deck 累积几千僵尸吃几百 G。此函数杀掉:
      ① 本 render.py 进程的 chromium 子进程(ppid==自己,close 没杀掉的)
      ② 孤儿 chromium(ppid==1,其父 render.py 已死=确定泄漏)
    **不碰 ppid 指向其他活着 render.py 的 chromium**(它们是别的在跑渲染),故安全、只清泄漏。
    每次 render.py 退出都跑一遍 → 累积的孤儿僵尸也被陆续收割,内存不重启即回落。"""
    import signal as _sig
    mypid = os.getpid()
    killed = 0
    try:
        _hz = os.sysconf("SC_CLK_TCK") or 100
    except Exception:
        _hz = 100
    try:
        with open("/proc/uptime") as f:
            _uptime = float(f.read().split()[0])
    except Exception:
        _uptime = None
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % pid, "rb") as f:
                    parts = f.read().split()
                comm = parts[1].lower()          # (comm) 含括号,截断到15字符
                ppid = int(parts[3])
            except Exception:
                continue
            if b"chrom" not in comm and b"headless" not in comm and b"nacl" not in comm:
                continue
            # 判定泄漏(三选一): ①自己的子进程 ②孤儿(父已死→ppid=1) ③存活>300s(单次渲染<60s,超5min 必泄漏,
            # 不管 reparent 到谁都杀 —— 兜住孤儿被 subreaper 收养、ppid≠1 的情况)
            leaked = ppid == mypid or ppid == 1
            if not leaked and _uptime is not None:
                try:
                    age = _uptime - int(parts[21]) / _hz    # field22=starttime(clock ticks since boot)
                    if age > 300:
                        leaked = True
                except Exception:
                    pass
            if leaked:
                try:
                    os.kill(int(pid), _sig.SIGKILL)
                    killed += 1
                except Exception:
                    pass
    except Exception:
        pass
    if killed:
        print("[render] reaped %d leaked chromium (own-children + orphans)" % killed, file=sys.stderr)


import atexit as _atexit_reap
_atexit_reap.register(_reap_leaked_chromium)   # render.py 每次退出都收割一次泄漏 chromium


def _ensure_browser_available(p):
    """
    找到可用的 Chromium 可执行文件。
    策略优先级:
      1. PPT_SKILL_BROWSER_EXE 环境变量 (用户显式指定)
      2. playwright.executable_path (期望版本，严格匹配)
      3. 回退扫描本地缓存中已有的 chromium 版本 (最接近期望版本的)
      4. 所有方式都失败才报错
    """
    override = os.environ.get("PPT_SKILL_BROWSER_EXE")
    if override:
        override = os.path.abspath(os.path.expanduser(override))
        if not os.path.isfile(override):
            raise BrowserUnavailable(f"PPT_SKILL_BROWSER_EXE 不存在: {override}")
        return override

    # ② 让 Playwright 算出期望路径
    exe = getattr(p.chromium, "executable_path", None)
    if exe and os.path.exists(exe):
        # 期望版本存在，走原有 headless-shell 优选逻辑
        return _prefer_headless_shell(exe)

    # ③ 期望版本不存在，回退扫描本地缓存
    scanned = _scan_local_chromium(p)
    if scanned:
        return scanned

    # ④ 都找不到，才报错
    if exe:
        raise BrowserUnavailable(
            f"Playwright Chromium 可执行文件不存在: {exe}，"
            f"且本地无可回退的 chromium 版本。请先运行 `playwright install chromium`。")
    raise BrowserUnavailable("无法解析 Chromium 路径，请检查环境变量 PLAYWRIGHT_BROWSERS_PATH")

def _prefer_headless_shell(exe):
    """
    原逻辑:从期望路径提取 revision，优先用同 revision 的 headless-shell。
    """
    revision = re.search(r"chromium-(\d+)", exe)
    cache_root = os.path.dirname(os.path.dirname(os.path.dirname(exe)))
    candidates = []
    if revision:
        candidates.append(os.path.join(
            cache_root,
            f"chromium_headless_shell-{revision.group(1)}",
            "chrome-headless-shell-linux64",
            "chrome-headless-shell",
        ))
    else:
        candidates.extend(sorted(glob.glob(os.path.join(
            cache_root, "chromium_headless_shell-*",
            "chrome-headless-shell-linux64", "chrome-headless-shell"
        )), reverse=True))
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return exe

def _scan_local_chromium(p):
    """
    不依赖 playwright 的 revision，直接扫描本地缓存目录，
    返回架构匹配且可执行的最接近版本。

    搜索顺序:
      1. chrome-headless-shell (更快，无 crashpad)
      2. full Google Chrome for Testing
    """
    cache_root = os.path.expanduser(
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                       os.path.expanduser("~/.box-agent/browsers")))
    if not os.path.isdir(cache_root):
        return None

    # 确定本机架构
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin":
        mac_arch = "chrome-mac-arm64" if machine == "arm64" else "chrome-mac-x64"
        shell_arch = "chrome-headless-shell-mac-arm64" if machine == "arm64" else "chrome-headless-shell-mac-x64"
    else:
        mac_arch = None
        shell_arch = "chrome-headless-shell-linux64"

    # 从 p.chromium.executable_path 提取期望的 revision 和 full arch，用于排序
    exe = getattr(p.chromium, "executable_path", None)
    desired_rev = None
    desired_full_arch = None
    if exe:
        m = re.search(r"chromium-(\d+)", exe)
        if m:
            desired_rev = int(m.group(1))
        # 提取完整架构目录名 (e.g. "chrome-mac-arm64")
        parts = exe.split(os.sep)
        for part in parts:
            if part.startswith("chrome-mac-") or part.startswith("chrome-linux"):
                desired_full_arch = part
                break

    candidates = []  # list of (rev_distance, path)

    # ① 扫 headless-shell:chromium_headless_shell-<rev>/shell_arch/chrome-headless-shell
    for d in sorted(glob.glob(os.path.join(cache_root, "chromium_headless_shell-*"))):
        m = re.search(r"chromium_headless_shell-(\d+)", d)
        if not m:
            continue
        rev = int(m.group(1))
        for arch_name in [shell_arch]:
            if not arch_name:
                continue
            candidate = os.path.join(d, arch_name, "chrome-headless-shell")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                dist = abs(desired_rev - rev) if desired_rev is not None else rev
                candidates.append((dist, candidate))

    # ② 扫 full chromium:chromium-<rev>/full_arch/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
    for d in sorted(glob.glob(os.path.join(cache_root, "chromium-*"))):
        m = re.search(r"chromium-(\d+)", d)
        if not m:
            continue
        rev = int(m.group(1))
        # 用期望的 arch 优先，否则扫同版本下所有 arch
        full_archs = [desired_full_arch] if desired_full_arch else [
            a for a in ["chrome-mac-arm64", "chrome-mac-x64", "chrome-linux64"]
        ]
        for arch_name in full_archs:
            # macOS: .app/Contents/MacOS/Google Chrome for Testing
            candidate_mac = os.path.join(
                d, arch_name,
                "Google Chrome for Testing.app", "Contents", "MacOS",
                "Google Chrome for Testing")
            # Linux: google-chrome
            candidate_linux = os.path.join(d, arch_name, "chrome")
            for c in [candidate_mac, candidate_linux]:
                if os.path.isfile(c) and os.access(c, os.X_OK):
                    dist = abs(desired_rev - rev) if desired_rev is not None else rev
                    candidates.append((dist, c))

    if not candidates:
        return None

    candidates.sort()
    best_dist, best_path = candidates[0]
    if desired_rev is not None and best_dist > 0:
        print(f"[render] 期望 chromium-{desired_rev} 不存在，回退到 {os.path.basename(best_path)} (revision 差 {best_dist})",
              file=sys.stderr)
    return best_path



def _short_browser_error(msg):
    lines = [line.strip() for line in msg.splitlines() if line.strip()]
    priority = (
        "error while loading shared libraries",
        "executable doesn't exist",
        "Host system is missing dependencies",
        "Looks like Playwright was just installed or updated",
        "Operation not permitted",
        "No usable sandbox",
        "SIGTRAP",
        "crashpad",
    )
    for bit in priority:
        for line in lines:
            if bit in line:
                return line
    return " ".join(lines[:3])


def _is_fatal_browser_error(msg):
    """Classify stable host/runtime launch failures that retries cannot repair."""
    lower = msg.lower()
    fatal_bits = (
        "executable doesn't exist",
        "looks like playwright was just installed or updated",
        "error while loading shared libraries",
        "host system is missing dependencies",
        "operation not permitted",
        "no usable sandbox",
        "sigtrap",
        "crashpad",
    )
    return any(bit in lower for bit in fatal_bits)

# 元素出框检测(在渲染好的页面里跑):.slide 是 overflow:hidden,内容越过 1600×900
# 会被**静默裁掉**;本 ablation 依靠 DOM 量化,不依赖像素观察。只报承载内容的叶子
# (有直接文字 / 是 img·canvas·svg)、按越界像素排序取前 8;满铺 .slide--bleed 背景到边合规、排除。
_OVERFLOW_JS = r"""
(() => {
  const W = window.innerWidth, H = window.innerHeight, tol = 4;
  const root = document.querySelector('.slide') || document.body;
  const out = [];
  for (const el of root.querySelectorAll('*')) {
    if (el.closest('.slide--bleed') &&
        (el.tagName === 'IMG' || (el.className && (''+(el.className.baseVal ?? el.className)).match(/bleed/)))) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const over = Math.max(r.right - W, r.bottom - H, -r.left, -r.top);
    if (over <= tol) continue;
    const media = /^(IMG|CANVAS|svg|SVG)$/.test(el.tagName);
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.textContent;
    if (!media && !t.trim()) continue;
    const side = (r.right - W > tol) ? 'right' : (r.bottom - H > tol) ? 'bottom'
               : (-r.left > tol) ? 'left' : 'top';
    const cls = ('' + ((el.className && (el.className.baseVal ?? el.className)) || '')).trim().slice(0, 36);
    out.push({tag: el.tagName.toLowerCase(), cls, over: Math.round(over), side,
              txt: (t.trim() || (media ? '[media]' : '')).slice(0, 24)});
  }
  out.sort((a, b) => b.over - a.over);
  return out.slice(0, 8);
})()
"""

_BROKEN_IMAGE_JS = r"""
(() => {
  const root = document.querySelector('.slide') || document.body;
  const broken = [];
  for (const img of root.querySelectorAll('img')) {
    const src = img.currentSrc || img.getAttribute('src') || '';
    if (!src || !img.complete || img.naturalWidth === 0 || img.naturalHeight === 0) {
      broken.push({
        src: src.slice(0, 160),
        alt: (img.getAttribute('alt') || '').slice(0, 80),
        cls: ('' + (img.className || '')).slice(0, 48),
        complete: !!img.complete,
        natural: `${img.naturalWidth || 0}x${img.naturalHeight || 0}`,
      });
    }
  }
  return broken.slice(0, 12);
})()
"""

# 遮盖 / 拥挤检测(都在 1600×900 框**内**,no-visual 依靠 DOM 检测):
# ① OVERLAP=两个文字叶子的行框相交。行框包含透明区域,不能证明字形像素真的遮挡,
#    因此只作为后续 Vision 的候选线索,不单独使 batch 失败。「有意层叠」仍通过
#    scrim/overlay/gradient/decor/watermark… 声明类或有效透明度<0.45 豁免。
# ② CROWDED=会裁剪的盒里听众需要阅读的文字 scroll 尺寸超出自身盒(定高节点 /
#    表格格 / 卡片塞不下被切),仍是硬错。单个引号、破折号等纯装饰标点不承担阅读内容,
#    不使其自身字体行框的微溢出变成页面失败。
_COLLISION_JS = r"""
(() => {
  const root = document.querySelector('.slide') || document.body;
  // "有意遮盖"的声明词:媒介垫层 / 渐变罩 / 水印 / 装饰层 / 显式 overlap-ok —— 一律不算问题遮盖。
  const SCRIM = /scrim|overlay|gradient|backdrop|glow|mask|veil|shade|noise|texture|halftone|watermark|decor|deco|ghost|behind|faint|ornament|aura|overlap-ok/i;
  const leaves = [];
  for (const el of root.querySelectorAll('*')) {
    // 只收「有直接文字的叶子」——遮盖只查 文字↔文字(图 / 满图上的文字归 §6 scrim 规则管,图本身不是文字叶子、天然不入列)
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.textContent;
    if (!t.trim()) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    // 沿祖先链一次走完:opacity 不继承 → 连乘算有效透明度;并看文字是否落在「作者声明的」scrim / 装饰层里(类名常挂在容器上)
    let eff = 1, declared = false;
    for (let a = el; a && a !== root.parentElement; a = a.parentElement) {
      eff *= parseFloat(getComputedStyle(a).opacity || '1');
      const c = '' + ((a.className && (a.className.baseVal ?? a.className)) || '');
      if (SCRIM.test(c)) { declared = true; break; }
    }
    if (declared || eff < 0.45) continue;   // 淡 / 声明的装饰层里的文字 = 有意层叠,不当问题遮盖
    const cls = '' + ((el.className && (el.className.baseVal ?? el.className)) || '');
    // getBoundingClientRect() returns the union of every wrapped line fragment.
    // That union can cover neighbouring inline phrases even when no glyphs overlap.
    // Measure each direct text-node fragment instead, so a normal line wrap is not
    // misreported as 100% text collision and does not induce destructive Review edits.
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      for (const r of range.getClientRects()) {
        if (r.width < 4 || r.height < 4) continue;
        leaves.push({el, r, t: n.textContent.trim().slice(0, 22), cls: cls.trim().slice(0, 28), tag: el.tagName.toLowerCase()});
      }
    }
  }
  // CROWDED —— 会裁剪的盒(overflow 非 visible)里文字塞不下、被切;排除结构大容器与含图媒介的盒。
  // 只认真裁剪的盒:display 标题多是 overflow:visible 的字形微溢(无害),不算。
  const crowded = [];
  const ORNAMENTAL_PUNCT = /^[\s“”‘’"'«»‹›—–·•…《》〈〉「」『』]+$/;
  const W2 = window.innerWidth, H2 = window.innerHeight;
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    const clipX = cs.overflowX !== 'visible', clipY = cs.overflowY !== 'visible';
    if (!clipX && !clipY) continue;
    const ox = clipX ? el.scrollWidth - el.clientWidth : 0;
    const oy = clipY ? el.scrollHeight - el.clientHeight : 0;
    if (ox <= 4 && oy <= 4) continue;
    const txt = (el.textContent || '').trim();
    if (!txt) continue;
    if (txt.length <= 4 && ORNAMENTAL_PUNCT.test(txt)) continue;
    if (el.querySelector('img,canvas,svg,video')) continue;   // 图媒介的滚动不算文字拥挤
    const r = el.getBoundingClientRect();
    if (r.width > 0.72 * W2 && r.height > 0.72 * H2) continue; // 近满屏结构容器不算
    const cls = ('' + ((el.className && (el.className.baseVal ?? el.className)) || '')).trim().slice(0, 28);
    crowded.push({tag: el.tagName.toLowerCase(), cls, txt: txt.slice(0, 22),
                  ox: Math.max(0, Math.round(ox)), oy: Math.max(0, Math.round(oy))});
  }
  crowded.sort((a, b) => (b.ox + b.oy) - (a.ox + a.oy));
  // OVERLAP —— 文字↔文字 重叠面积够大、非父子(图上文字归 §6 scrim 管,不在 leaves 里)
  const overlap = [];
  for (let i = 0; i < leaves.length; i++) for (let j = i + 1; j < leaves.length; j++) {
    const A = leaves[i], B = leaves[j];
    if (A.el === B.el || A.el.contains(B.el) || B.el.contains(A.el)) continue;
    const a = A.r, b = B.r;
    const ix = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
    const iy = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    const inter = ix * iy;
    if (inter < 120) continue;
    const frac = inter / Math.min(a.width * a.height, b.width * b.height);
    if (frac < 0.12) continue;
    overlap.push({a: {tag: A.tag, cls: A.cls, txt: A.t}, b: {tag: B.tag, cls: B.cls, txt: B.t},
                  pct: Math.round(frac * 100)});
  }
  overlap.sort((x, y) => y.pct - x.pct);
  // BOXOVERFLOW —— 内容盒(panel/card/slide-body/layer… 常是 overflow:visible)里,直接子块的底/右
  //   越出盒的内容区(减 padding/border)> 容差 = 文字溢出文本框但没被裁、也没超整页 →
  //   CROWDED(只看裁剪盒)与 OVERFLOW(只看整页)之间的盲区。含位图媒介的盒不算(图非文字)。
  const CONTENT = /\b(panel|card|slide-body|layer|p-card|hero-band|stack-col|three-cards|six-grid|cards|org-canvas|matrix|workflows|flow|field-list|cover-meta|slide-title)\b/;
  const SKIPC = /(scrim|overlay|decor|deco|watermark|bleed|motif|tint|glow|aura|veil|shade)/i;
  const boxoverflow = [], innergap = [];
  for (const el of root.querySelectorAll('*')) {
    const c = '' + ((el.className && (el.className.baseVal ?? el.className)) || '');
    if (!CONTENT.test(c) || SKIPC.test(c)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (el.querySelector('img,canvas,video')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 20 || r.height < 20) continue;
    const pt=parseFloat(cs.paddingTop)||0, pb=parseFloat(cs.paddingBottom)||0;
    const pl=parseFloat(cs.paddingLeft)||0, pr=parseFloat(cs.paddingRight)||0;
    const bt=parseFloat(cs.borderTopWidth)||0, bb=parseFloat(cs.borderBottomWidth)||0;
    const bl=parseFloat(cs.borderLeftWidth)||0, brw=parseFloat(cs.borderRightWidth)||0;
    const cTop=r.top+bt+pt, cBottom=r.bottom-bb-pb, cLeft=r.left+bl+pl, cRight=r.right-brw-pr;
    let overB=0, overR=0, worst='';
    for (const ch of el.children) {
      const chc='' + ((ch.className && (ch.className.baseVal ?? ch.className)) || '');
      if (SKIPC.test(chc)) continue;
      const cr=ch.getBoundingClientRect();
      if (cr.width<2 || cr.height<2) continue;
      const ob=cr.bottom-cBottom, orr=cr.right-cRight;
      if (ob>overB){ overB=ob; worst=(ch.textContent||'').replace(/\s+/g,' ').trim().slice(0,22); }
      if (orr>overR) overR=orr;
    }
    if (overB>4 || overR>4)
      boxoverflow.push({tag:el.tagName.toLowerCase(), cls:c.trim().slice(0,28),
                        ob:Math.round(overB), orr:Math.round(overR), txt:worst});
    // INNER-GAP —— flex column / grid 卡片:相邻子块之间出现大纵向空洞(margin-top:auto 撑空)
    //   且内容利用率低 → 读成"中间莫名空一块"。
    if ((cs.display==='flex'&&cs.flexDirection==='column') || cs.display==='grid') {
      const kids=[...el.children].filter(k=>{
        const kc='' + ((k.className && (k.className.baseVal ?? k.className)) || '');
        if (SKIPC.test(kc)) return false;
        const kr=k.getBoundingClientRect();
        return kr.height>2 && getComputedStyle(k).display!=='none';
      }).map(k=>k.getBoundingClientRect()).sort((a,b)=>a.top-b.top);
      let maxGap=0;
      for (let i=1;i<kids.length;i++){ const g=kids[i].top-kids[i-1].bottom; if(g>maxGap)maxGap=g; }
      const contentH=cBottom-cTop, usedH=kids.reduce((s,k)=>s+k.height,0);
      const util=contentH>0?usedH/contentH:1;
      if (kids.length>=3 && maxGap>44 && util<0.72)
        innergap.push({cls:c.trim().slice(0,28), gap:Math.round(maxGap), util:Math.round(util*100)});
    }
  }
  boxoverflow.sort((a,b)=>(b.ob+b.orr)-(a.ob+a.orr));
  innergap.sort((a,b)=>b.gap-a.gap);
  return {crowded: crowded.slice(0, 6), overlap: overlap.slice(0, 6),
          boxoverflow: boxoverflow.slice(0, 6), innergap: innergap.slice(0, 6)};
})()
"""


# 布局护栏:补 OVERLAP 只看文字↔文字的盲区,把常见的「下方遮盖 / 装饰压字 /
# 大型 SVG 媒介策略 / 旧 SVG 过小或标签互撞 / 绕开标准骨架变成可见 warning。report-only。
_LAYOUT_GUARD_JS = r"""
(() => {
  const root = document.querySelector('.slide') || document.body;
  const W = window.innerWidth, H = window.innerHeight;
  const DECOR = /decor|deco|doodle|blob|ornament|watermark|sticker|shape|star|sparkle|badge|stamp|seal|aura|glow|texture|pattern/i;
  const OK = /overlap-ok|allow-overlap|scrim|text-plate|overlay|bleed|backdrop/i;
  const SKIP_SVG = /icon|logo|mark|brand|page-no|pageno|qr|spark|decor|deco|watermark|ornament|bleed|svg-allowed|vector-asset/i;
  const out = {decor: [], footer: [], svgLarge: [], svgSmall: [], svgLabel: [], abs: [], customBody: [],
               footerPushed: null, widow: [], imgLonely: [], coverOOB: []};

  function cls(el){ return ('' + ((el.className && (el.className.baseVal ?? el.className)) || '')).trim(); }
  function txt(el){ return (el.textContent || '').replace(/\s+/g, ' ').trim(); }
  function visible(el){
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 3 && r.height > 3;
  }
  function effOpacity(el){
    let v = 1;
    for(let a = el; a && a !== root.parentElement; a = a.parentElement) v *= parseFloat(getComputedStyle(a).opacity || '1');
    return v;
  }
  function declaredOk(el){
    for(let a = el; a && a !== root.parentElement; a = a.parentElement) if(OK.test(cls(a))) return true;
    return false;
  }
  function isDecor(el){
    for(let a = el; a && a !== root.parentElement; a = a.parentElement) if(DECOR.test(cls(a))) return true;
    return false;
  }
  function overlap(a,b){
    const ix = Math.max(0, Math.min(a.right,b.right) - Math.max(a.left,b.left));
    const iy = Math.max(0, Math.min(a.bottom,b.bottom) - Math.max(a.top,b.top));
    const area = ix * iy;
    const frac = area / Math.max(1, Math.min(a.width * a.height, b.width * b.height));
    return {area, frac};
  }
  function mediaLike(el){ return /^(IMG|SVG|CANVAS|VIDEO)$/i.test(el.tagName); }
  function contentLike(el){
    let direct = '';
    for(const n of el.childNodes) if(n.nodeType === 3) direct += n.textContent;
    return !!direct.trim() || mediaLike(el) || !!el.querySelector('img,svg,canvas,video');
  }

  // 标准骨架契约:必须有 root 直下 .slide-body;禁止 .slide-body-xx 替代它。
  const directBody = root.querySelector(':scope > .slide-body');
  if(!directBody) out.customBody.push({msg: 'missing direct .slide-body'});
  for(const el of Array.from(root.children || [])){
    const c = cls(el);
    if(/\bslide-body-[\w-]+/.test(c)) out.customBody.push({msg: 'custom body class', cls: c.slice(0, 40)});
  }

  // 绝对定位内容:装饰 / scrim 可绝对定位,正文内容不应靠 absolute 拼版。
  if(directBody){
    for(const el of directBody.querySelectorAll('*')){
      const cs = getComputedStyle(el);
      if(cs.position !== 'absolute' && cs.position !== 'fixed') continue;
      if(!visible(el) || declaredOk(el) || isDecor(el)) continue;
      if(!contentLike(el)) continue;
      const r = el.getBoundingClientRect();
      out.abs.push({tag: el.tagName.toLowerCase(), cls: cls(el).slice(0, 32), txt: txt(el).slice(0, 22),
                    box: `${Math.round(r.width)}×${Math.round(r.height)}`});
    }
  }

  // 装饰压住文字:OVERLAP 不看文字↔图形/装饰,这里补上。
  const textLeaves = [];
  for(const el of root.querySelectorAll('.slide-title *, .slide-body *, .slide-footer *')){
    let direct = '';
    for(const n of el.childNodes) if(n.nodeType === 3) direct += n.textContent;
    direct = direct.trim();
    if(!direct || !visible(el) || isDecor(el) || declaredOk(el)) continue;
    textLeaves.push({el, r: el.getBoundingClientRect(), text: direct.slice(0, 22)});
  }
  const decors = [];
  for(const el of root.querySelectorAll('*')){
    if(!visible(el) || !isDecor(el) || declaredOk(el) || effOpacity(el) < 0.12) continue;
    const r = el.getBoundingClientRect();
    if(r.width > 0.96 * W && r.height > 0.96 * H) continue;
    decors.push({el, r, cls: cls(el).slice(0, 32)});
  }
  for(const d of decors){
    for(const t of textLeaves){
      if(d.el.contains(t.el) || t.el.contains(d.el)) continue;
      const hit = overlap(d.r, t.r);
      if(hit.area > 80 && hit.frac > 0.03){
        out.decor.push({decor: d.cls, text: t.text, pct: Math.round(hit.frac * 100)});
        if(out.decor.length >= 6) break;
      }
    }
    if(out.decor.length >= 6) break;
  }

  // 页脚 / 页码安全:正文区媒体或装饰压到 footer 带时,必须用几何关系直接报告。
  const footer = root.querySelector(':scope > .slide-footer');
  if(footer && visible(footer)){
    const fr = footer.getBoundingClientRect();
    const candidates = [];
    for(const el of root.querySelectorAll('img,svg,canvas,video,*')){
      if(el === footer || footer.contains(el) || !visible(el) || declaredOk(el)) continue;
      if(el.closest && el.closest('.bleed')) continue;
      if(!mediaLike(el) && !isDecor(el)) continue;
      if(effOpacity(el) < 0.12) continue;
      const r = el.getBoundingClientRect();
      const hit = overlap(fr, r);
      if(hit.area > 120 && hit.frac > 0.04){
        candidates.push({tag: el.tagName.toLowerCase(), cls: cls(el).slice(0, 32), pct: Math.round(hit.frac * 100)});
      }
    }
    out.footer = candidates.slice(0, 6);
  }

  // #2 FOOTER-PUSHED —— 正文内容太多把页脚顶下去 / 正文压到页脚顶之下 / 页脚被挤出视口底。
  //   (FOOTER-COVER 抓的是"媒体/装饰压页脚";这条抓的是"正文体量撑破底部安全带",最严重那类底部溢出。)
  if(footer && visible(footer)){
    const fr = footer.getBoundingClientRect();
    const belowViewport = Math.round(fr.bottom - H);   // >0 = 页脚掉出视口底
    let bodyOverFooter = 0, worst = '';
    if(directBody){
      let deepest = 0, deepEl = null;
      for(const el of directBody.querySelectorAll('*')){
        if(!visible(el)) continue;
        const c = cls(el);
        if(DECOR.test(c) || OK.test(c) || (el.closest && el.closest('.bleed'))) continue;
        if(mediaLike(el)) continue;                    // 媒体压页脚归 FOOTER-COVER
        const r = el.getBoundingClientRect();
        if(r.bottom > deepest){ deepest = r.bottom; deepEl = el; }
      }
      bodyOverFooter = Math.round(deepest - fr.top);   // >0 = 正文最深内容压过页脚顶
      if(deepEl) worst = txt(deepEl).slice(0, 20);
    }
    if(belowViewport > 2 || bodyOverFooter > 8)
      out.footerPushed = {belowViewport, bodyOverFooter, worst};
  }

  // #3a WIDOW-LINE —— 文本块渲染后末行只剩 1-2 个 CJK 实字(或单个短西文词)= 寡字/孤行。
  //   判据(探针实测不误报):去掉标点后末行实字 1-2、末行宽 < 盒宽 35%、且是多行块。
  const WSEL = 'p,li,.card-p,.hero-p,.lead-line,.subtitle,.diagram-caption';
  for(const el of root.querySelectorAll(WSEL)){
    if(!visible(el)) continue;
    const c = cls(el);
    if(/kicker|badge|card-tag|chip/i.test(c)) continue;
    const cs = getComputedStyle(el);
    const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3;
    const r = el.getBoundingClientRect();
    if(r.height < lh * 1.6) continue;                  // 单行,无寡行
    const node = [...el.childNodes].reverse().find(n => n.nodeType === 3 && n.textContent.trim());
    if(!node) continue;
    const full = node.textContent;
    if(full.trim().length < 8) continue;
    try{
      const rng = document.createRange();
      rng.setStart(node, full.length - 1); rng.setEnd(node, full.length);
      const lastTop = rng.getBoundingClientRect().top;
      let i = full.length - 1;
      while(i > 0){ rng.setStart(node, i - 1); rng.setEnd(node, i);
        if(Math.abs(rng.getBoundingClientRect().top - lastTop) > 2) break; i--; }
      rng.setStart(node, i); rng.setEnd(node, full.length);
      const lastW = rng.getBoundingClientRect().width;
      const lastLine = full.slice(i).trim();
      const stripped = lastLine.replace(/[。，、；：？！,.;:!?）)\]】」』"'\s]/g, '');
      if(stripped.length >= 1 && stripped.length <= 2 && lastW < 0.35 * r.width){
        out.widow.push({cls: c.slice(0, 24), last: lastLine, tag: el.tagName.toLowerCase()});
        if(out.widow.length >= 8) break;
      }
    }catch(e){}
  }

  // #3b IMG-LONELY —— 位图 <img>(非满铺 / 非装饰 / 非图标)相对正文区过小且孤立 = 孤图突兀。
  //   (SVG-SMALL 管手写概念图;这条管真实照片 / 位图。)
  const bodyR = (directBody || root).getBoundingClientRect();
  for(const img of root.querySelectorAll('img')){
    if(!visible(img)) continue;
    const c = cls(img);
    if(/bleed|scrim|overlay|decor|deco|watermark|logo|icon|mark|brand|avatar|qr/i.test(c)) continue;
    if(img.closest('.slide-title,.slide-footer')) continue;
    if(img.closest('.bleed')) continue;
    const r = img.getBoundingClientRect();
    const area = r.width * r.height, bodyArea = Math.max(1, bodyR.width * bodyR.height);
    const par = img.parentElement;
    const sib = par ? par.querySelectorAll('img').length : 1;   // 同父图数(成组图不算孤)
    if(area < 0.10 * bodyArea && r.width < 0.34 * bodyR.width && sib < 2){
      out.imgLonely.push({cls: c.slice(0, 24),
                          size: Math.round(r.width) + '×' + Math.round(r.height),
                          pct: Math.round(area / bodyArea * 100)});
      if(out.imgLonely.length >= 6) break;
    }
  }

  // #4 COVER-OOB —— 封面标题块贴到 / 越出安全区(左上尤甚:标题贴到 x=0 / y=0)。
  //   (§9⑰ 治的是"固定巨字号顶界";这条把它变成可见 warning。)
  if(/slide--cover|\bcover\b/.test(cls(root))){
    const MX = 60, MY = 60;          // --margin-x/y 出厂默认
    const seen = new Set();
    for(const sel of ['.cover-h1', '.cover-h2', 'h1', '.slide-title']){
      const el = root.querySelector(sel);
      if(!el || !visible(el)) continue;
      const r = el.getBoundingClientRect();
      const key = Math.round(r.left) + ',' + Math.round(r.top) + ',' + Math.round(r.right);
      if(seen.has(key)) continue; seen.add(key);
      const overR = Math.round(r.right - (W - MX)), overL = Math.round(MX - r.left),
            overT = Math.round(MY - r.top), overB = Math.round(r.bottom - (H - MY));
      if(overR > 2 || overL > 2 || overT > 2 || overB > 2){
        out.coverOOB.push({sel, overR: Math.max(0, overR), overL: Math.max(0, overL),
                           overT: Math.max(0, overT), overB: Math.max(0, overB)});
        if(out.coverOOB.length >= 4) break;
      }
    }
  }

  // 新页面默认不用大型手写 SVG；旧 SVG 继续检查体量与标签互撞。
  const bodyRect = (directBody || root).getBoundingClientRect();
  for(const svg of root.querySelectorAll('svg')){
    if(!visible(svg) || declaredOk(svg) || isDecor(svg)) continue;
    if(svg.closest('.slide-title,.slide-footer')) continue;
    const c = cls(svg);
    if(SKIP_SVG.test(c)) continue;
    const shapeCount = svg.querySelectorAll('path,rect,circle,ellipse,line,polyline,polygon,text').length;
    const textCount = svg.querySelectorAll('text').length;
    if(shapeCount < 4 && textCount < 1) continue;
    const r = svg.getBoundingClientRect();
    const area = r.width * r.height;
    const bodyArea = Math.max(1, bodyRect.width * bodyRect.height);
    const tooLargeForIcon = r.width > 160 || r.height > 160 || area > 0.06 * bodyArea;
    if(tooLargeForIcon){
      out.svgLarge.push({cls: c.slice(0, 32), size: `${Math.round(r.width)}×${Math.round(r.height)}`});
    }
    const tooSmall = r.width < 0.52 * bodyRect.width || r.height < 0.42 * bodyRect.height || area < 0.28 * bodyArea;
    if(tooSmall){
      out.svgSmall.push({cls: c.slice(0, 32), size: `${Math.round(r.width)}×${Math.round(r.height)}`,
                         body: `${Math.round(bodyRect.width)}×${Math.round(bodyRect.height)}`});
    }
    const labels = [];
    for(const t of svg.querySelectorAll('text')){
      if(!visible(t)) continue;
      const tr = t.getBoundingClientRect();
      if(tr.width < 3 || tr.height < 3) continue;
      labels.push({r: tr, text: txt(t).slice(0, 18)});
    }
    for(let i = 0; i < labels.length; i++) for(let j = i + 1; j < labels.length; j++){
      const hit = overlap(labels[i].r, labels[j].r);
      if(hit.area > 45 && hit.frac > 0.08){
        out.svgLabel.push({a: labels[i].text, b: labels[j].text, pct: Math.round(hit.frac * 100)});
        if(out.svgLabel.length >= 6) break;
      }
    }
  }
  out.abs = out.abs.slice(0, 6);
  out.svgLarge = out.svgLarge.slice(0, 6);
  out.svgSmall = out.svgSmall.slice(0, 6);
  out.svgLabel = out.svgLabel.slice(0, 6);
  out.customBody = out.customBody.slice(0, 6);
  return out;
})()
"""


# 垂直重心 / 上下留白检测(治「大字突兀 = 位置奇怪、整体偏上或偏下留大白」):
# 量「主体内容」(正文 / 标题 / 图 / 概念图,排除页脚·页码·眉签等边角家具与满铺背景 / 装饰 / scrim)的
# 垂直包围盒 → 若内容没填满(span<82%H)且重心明显偏离画布中线(|off|>13%H)= 视觉重心不居中、一侧大片空。report-only。
_VBALANCE_JS = r"""
(() => {
  const root = document.querySelector('.slide') || document.body;
  const W = window.innerWidth, H = window.innerHeight;
  // 封面 / 满图 / 章节页有意偏置构图(标题压角等),不量垂直居中——只管常规内容页
  if (root.matches && root.matches('.slide--cover, .slide--bleed')) return null;
  const SKIP = /scrim|overlay|gradient|backdrop|glow|mask|veil|noise|texture|halftone|watermark|decor|deco|slide-footer|page-no|pageno/i;
  let top = Infinity, bot = -Infinity, any = false;
  const rects = [];
  for (const el of root.querySelectorAll('*')) {
    let t = ''; for (const n of el.childNodes) if (n.nodeType === 3) t += n.textContent;
    const isText = !!t.trim();
    const isMedia = /^(IMG|CANVAS|svg|VIDEO)$/i.test(el.tagName);
    if (!isText && !isMedia) continue;
    let skip = false;
    for (let a = el; a && a !== root.parentElement; a = a.parentElement) {
      const c = '' + ((a.className && (a.className.baseVal ?? a.className)) || '');
      if (SKIP.test(c)) { skip = true; break; }
    }
    if (skip) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity || '1') < 0.35) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    if (r.width > 0.9 * W && r.height > 0.9 * H) continue;   // 满铺背景不算内容
    const rt = Math.max(0, r.top), rb = Math.min(H, r.bottom);
    if (rb - rt < 8) continue;
    if (rt < top) top = rt;
    if (rb > bot) bot = rb;
    rects.push([Math.max(0, r.left), rt, Math.min(W, r.right), rb]);
    any = true;
  }
  if (!any || bot <= top) return null;
  // 版面填充率:把画布切 GX×GY 网格,任一内容盒盖到即算覆盖 → 覆盖格/总格。
  // 只收「有直接文字的叶子 + 图媒介」,故行内 leader gap、条目间空档、少内容摊大画布都读成未覆盖 =
  // 真实「构图密度」(纯 top/bot 纵向跨度看不出——内容摊开但稀疏时跨度仍大)。
  const GX = 48, GY = 27, cw = W / GX, ch = H / GY;
  const grid = new Uint8Array(GX * GY);
  for (const q of rects) {
    const cx0 = Math.max(0, Math.floor(q[0] / cw)), cx1 = Math.min(GX - 1, Math.floor((q[2] - 1) / cw));
    const cy0 = Math.max(0, Math.floor(q[1] / ch)), cy1 = Math.min(GY - 1, Math.floor((q[3] - 1) / ch));
    for (let gy = cy0; gy <= cy1; gy++) for (let gx = cx0; gx <= cx1; gx++) grid[gy * GX + gx] = 1;
  }
  let cov = 0; for (let i = 0; i < grid.length; i++) cov += grid[i];
  return {top: Math.round(top), bot: Math.round(bot), H: H, fill: Math.round(100 * cov / (GX * GY))};
})()
"""


# 对比度门核(治 matq5k 39-deck 诊断【极高】#1「文本/背景对比度不足 = 可读性灾难」):
# 对每个可见文字叶子,算其 computed color 对**有效背景**的 WCAG 对比;并把「坐在 .slide--bleed / 图片上、
# 且祖先链无声明 scrim/plate/托板」的文字单列(图底不透明色测不到、天然低对比风险)。
# 阈值对齐 SKILL:正文 ≥4.5、大字(≥24px 或 ≥18px 且 bold)≥3.0。只报**高置信硬点**:
#   - 有实心背景色可测且比值 < 阈值 → LOW-CONTRAST(确定性硬伤)
#   - 文字在 bleed/图上、无 scrim/plate 声明 → ON-IMAGE-NOSCRIM(疑似,提示垫 scrim/托板)
# report-only,永不影响出图。
_CONTRAST_JS = r"""
(() => {
  const root = document.querySelector('.slide') || document.body;
  const W = window.innerWidth, H = window.innerHeight;
  const SCRIM = /scrim|plate|text-plate|overlay|backdrop|panel|card|glass/i;
  const BLEED = /bleed/i;
  function toRGBA(s){
    if(!s) return null;
    let m = s.match(/rgba?\(([^)]+)\)/i);
    if(!m) return null;
    const p = m[1].split(',').map(x=>parseFloat(x));
    return {r:p[0],g:p[1],b:p[2],a:(p.length>3?p[3]:1)};
  }
  function lum(c){
    const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);
  }
  function ratio(a,b){const L1=lum(a),L2=lum(b);const hi=Math.max(L1,L2),lo=Math.min(L1,L2);return (hi+0.05)/(lo+0.05);}
  // 有效背景:沿祖先找第一个 alpha>=0.7 的 background-color;返回该色 + 是否遇到 bleed/图/scrim
  function effBg(el){
    let onBleed=false, hasScrim=false, bg=null;
    for(let a=el; a && a!==root.parentElement; a=a.parentElement){
      const c=''+((a.className&&(a.className.baseVal??a.className))||'');
      if(SCRIM.test(c)) hasScrim=true;
      if(BLEED.test(c)) onBleed=true;
      const cs=getComputedStyle(a);
      if(/^(IMG|VIDEO)$/i.test(a.tagName)) onBleed=true;
      if(cs.backgroundImage && cs.backgroundImage!=='none' && /url\(|gradient/i.test(cs.backgroundImage)) onBleed=true;
      if(!bg){
        const cc=toRGBA(cs.backgroundColor);
        if(cc && cc.a>=0.7) bg=cc;
      }
    }
    return {bg,onBleed,hasScrim};
  }
  const low=[], onimg=[];
  for(const el of root.querySelectorAll('*')){
    let t=''; for(const n of el.childNodes) if(n.nodeType===3) t+=n.textContent;
    t=t.trim(); if(!t) continue;
    const cs=getComputedStyle(el);
    if(cs.visibility==='hidden'||cs.display==='none'||parseFloat(cs.opacity||'1')<0.5) continue;
    const r=el.getBoundingClientRect();
    if(r.width<8||r.height<8||r.bottom<0||r.top>H||r.right<0||r.left>W) continue;
    const fs=parseFloat(cs.fontSize||'16');
    const bold=(parseInt(cs.fontWeight||'400',10)>=600)||/bold/i.test(cs.fontWeight||'');
    const large=(fs>=24)||(fs>=18&&bold);
    const need=large?3.0:4.5;
    const fg=toRGBA(cs.color); if(!fg) continue;
    const {bg,onBleed,hasScrim}=effBg(el);
    const txt=t.slice(0,24);
    if(bg){
      const rr=ratio(fg,bg);
      if(rr<need) low.push({txt, cls:(''+((el.className&&(el.className.baseVal??el.className))||'')).slice(0,32), ratio:Math.round(rr*10)/10, need, fs:Math.round(fs)});
    } else if(onBleed && !hasScrim){
      onimg.push({txt, cls:(''+((el.className&&(el.className.baseVal??el.className))||'')).slice(0,32), fs:Math.round(fs)});
    }
  }
  low.sort((a,b)=>a.ratio-b.ratio);
  return {low:low.slice(0,6), onimg:onimg.slice(0,6)};
})()
"""

_CJK_TYPOGRAPHY_JS = r"""
(() => {
  const issues=[];
  const cjk=/[\u3400-\u9fff\uf900-\ufaff]/;
  const mono=/(?:ibm\s*plex\s*mono|\bmono\b|monospace|consolas|courier)/i;
  const expressive=/(?:smiley\s*sans|zcool\s*kuai\s*le|zcool\s*qingke\s*huangyou|xiaolai|ma\s*shan\s*zheng|zhi\s*mang\s*xing|liu\s*jian\s*mao\s*cao|long\s*cang|ruanmeng|软萌|行书|草书)/i;
  const visible=(el,cs) => {
    const r=el.getBoundingClientRect();
    return cs.display!=='none' && cs.visibility!=='hidden' && Number(cs.opacity||1)>0.01 && r.width>1 && r.height>1;
  };
  const family=(cs) => (cs.fontFamily||'').split(',')[0].replace(/["']/g,'').trim().toLowerCase();
  const declared=(el) => !!el.closest('.is-expressive-type,[data-type-intent="expressive"]');
  const push=(el,text,cs,kinds,extra={}) => {
    if(!kinds.length) return;
    issues.push({
      text:text.slice(0,48), cls:(''+((el.className&&(el.className.baseVal??el.className))||'')).slice(0,48),
      font:(cs.fontFamily||'').slice(0,96), letterSpacing:Math.round((parseFloat(cs.letterSpacing)||0)*10)/10,
      fontSize:Math.round((parseFloat(cs.fontSize)||16)*10)/10, kinds, ...extra
    });
  };
  for(const el of document.querySelectorAll('.slide *')){
    const direct=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent||'').join(' ').trim();
    if(!direct || !cjk.test(direct)) continue;
    const cs=getComputedStyle(el); if(!visible(el,cs)) continue;
    const fs=parseFloat(cs.fontSize)||16;
    const ls=cs.letterSpacing==='normal' ? 0 : (parseFloat(cs.letterSpacing)||0);
    const kinds=[];
    if(mono.test(cs.fontFamily||'')) kinds.push('cjk-in-mono');
    if(ls > fs*0.08+0.2) kinds.push('cjk-tracking-too-wide');
    if(expressive.test(cs.fontFamily||'') && !declared(el)) kinds.push('expressive-cjk-without-intent');
    push(el,direct,cs,kinds);
  }
  for(const el of document.querySelectorAll('.slide h1,.slide h2,.slide h3,.slide h4,.slide h5,.slide h6,.slide p,.slide blockquote,.slide .slide-title,.slide .sec-name,.slide .headline,.slide .title,.slide .subtitle,.slide .kicker')){
    const cs=getComputedStyle(el); if(!visible(el,cs)) continue;
    const runs=[];
    for(const node of el.childNodes){
      if(node.nodeType===3){
        const text=(node.textContent||'').trim();
        if(cjk.test(text)) runs.push({text, family:family(cs)});
      }else if(node.nodeType===1){
        const child=node;
        const childStyle=getComputedStyle(child);
        if(!['inline','inline-block','contents'].includes(childStyle.display)) continue;
        const text=(child.textContent||'').trim();
        if(cjk.test(text)) runs.push({text, family:family(childStyle)});
      }
    }
    const text=runs.map(r=>r.text).join('');
    const families=[...new Set(runs.map(r=>r.family).filter(Boolean))];
    if(runs.length>1 && text.length<=80 && families.length>1){
      push(el,text,cs,['mixed-cjk-family'],{families:families.slice(0,4)});
    }
  }
  return issues.slice(0,20);
})()
"""


def _setup_libs():
    """把本地依赖库目录加进 LD_LIBRARY_PATH —— 在 chromium 子进程启动前设置即可生效。"""
    extra = [d for d in (os.path.expanduser("~/.cache/ms-playwright/chrome-libs"),
                          os.path.expanduser("~/pwdeps/lib"), os.path.expanduser("~/cdeps/lib"))
             if os.path.isdir(d)]
    if extra:
        os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
            extra + [os.environ.get("LD_LIBRARY_PATH", "")]).rstrip(os.pathsep)
    # Prefer system libatk-1.0.so.0 over the incompatible cdeps vendor copy
    # (cdeps libatk was built against an old glib lacking g_once_init_enter_pointer).
    for _p in ("/lib/x86_64-linux-gnu/libatk-1.0.so.0",
               "/usr/lib/x86_64-linux-gnu/libatk-1.0.so.0"):
        if os.path.isfile(_p):
            _pre = os.environ.get("LD_PRELOAD", "")
            os.environ["LD_PRELOAD"] = (_p + (os.pathsep if _pre else "") + _pre).strip(os.pathsep)
            break


def _render_once(p, html, out, w, h, browser_exe=None, browser=None):
    """渲染一次；可传共享 browser 供 batch 调用。返回版式诊断字典。"""
    rep = {"broken": [], "overflow": [], "overlap": [], "crowded": [], "vbalance": None,
           "cjkTypography": [],
           "layout": {}, "runtime": {"script_failed": [], "page_errors": [], "charts_missing": []}}
    owns_browser = browser is None
    if owns_browser:
        try:
            b = p.chromium.launch(executable_path=browser_exe, args=LAUNCH_ARGS)
        except Exception as e:
            msg = str(e)
            if _is_fatal_browser_error(msg):
                raise BrowserUnavailable(_short_browser_error(msg))
            raise
        print(f"[render] launched browser {b}", file=sys.stderr)
    else:
        b = browser
    try:
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        print(f"[render] page created", file=sys.stderr)
        try:
            runtime = rep["runtime"]

            def _page_error(error):
                message = str(error).strip()
                if message and message not in runtime["page_errors"]:
                    runtime["page_errors"].append(message[:500])

            def _request_failed(request):
                try:
                    if request.resource_type == "script":
                        failure = request.failure
                        detail = failure if isinstance(failure, str) else str(failure or "request failed")
                        runtime["script_failed"].append({"url": request.url, "error": detail[:240]})
                except Exception:
                    pass

            pg.on("pageerror", _page_error)
            pg.on("requestfailed", _request_failed)
            # 字体:CDN + 本地缓存兜底(方案 B,实测可行)。允许 HTML 用 CDN 字体:
            # 先查本地缓存命中即离线复用(高并发不打爆 CDN),未命中抓 CDN 并落盘缓存,
            # CDN 挂/超时则放行(route.continue_)最终落 --sans/--sans-zh 系统字体栈,不吊死。
            import hashlib as _hl
            _font_cache = os.environ.get("FONT_CACHE", os.path.expanduser("~/.cache/ppt-fonts"))
            try:
                os.makedirs(_font_cache, exist_ok=True)
            except Exception:
                pass

            def _font_route(route, *a):
                url = route.request.url
                # ECharts 走它自己的本地 vendor 路由(下方注册、优先级更高);字体路由防御性跳过。
                if "echarts" in url:
                    try:
                        route.fallback()
                    except Exception:
                        try:
                            route.continue_()
                        except Exception:
                            pass
                    return
                try:
                    # content-type 按扩展名判:CSS / JS 库(Three.js·GSAP·D3 从 jsdelivr)/ 字体。
                    # JS 若误当 font/woff2 供给,浏览器不执行 → r5 fancy 动效/背景全废;故单列 .js/.mjs。
                    _path_only = url.split("?", 1)[0]
                    if ".css" in url or "css2" in url:
                        ct, _ext = "text/css", ".css"
                    elif _path_only.endswith((".js", ".mjs")):
                        ct, _ext = "application/javascript", ".js"
                    else:
                        ct, _ext = "font/woff2", ".woff2"
                    cpath = os.path.join(_font_cache, _hl.sha1(url.encode()).hexdigest() + _ext)
                    if os.path.isfile(cpath):
                        route.fulfill(body=open(cpath, "rb").read(), content_type=ct)
                        return
                    resp = route.fetch(timeout=15000)
                    body = resp.body()
                    try:
                        with open(cpath, "wb") as _f:
                            _f.write(body)
                    except Exception:
                        pass
                    route.fulfill(response=resp, body=body)
                except Exception:
                    try:
                        route.continue_()
                    except Exception:
                        try:
                            route.abort()
                        except Exception:
                            pass
            for _h in ("fonts.googleapis.com", "fonts.gstatic.com", "fonts.bunny.net", "cdn.jsdelivr.net"):
                try:
                    pg.route(f"**{_h}**", _font_route)
                except Exception:
                    pass
            # CDN ECharts 可用 Deck 自带副本离线替换；本地相对路径必须自行真实存在。
            # 禁止从 Skill 目录兜底，否则服务端 PNG 会掩盖最终 present.html 的依赖缺失。
            try:
                _ech = os.path.abspath(
                    os.path.join(os.path.dirname(html), "..", "assets", "vendor", "echarts.min.js")
                )
                _ech = _ech if os.path.isfile(_ech) else None
                if _ech:
                    _ech_body = open(_ech, "rb").read()

                    def _echarts_route(route, *args, _body=_ech_body):
                        if route.request.url.startswith(("http://", "https://")):
                            route.fulfill(body=_body, content_type="application/javascript")
                        else:
                            route.continue_()

                    pg.route("**echarts**", _echarts_route)
            except Exception:
                pass
            try:
                # 用 "load" 而非 "networkidle":本地 file:// 页若引用外部 CDN,
                # networkidle 可能永远不达成、白等满 timeout;load 只等本地资源就绪。
                pg.goto("file://" + html, wait_until="load", timeout=30000)
            except Exception as e:
                # 不静默吞:goto 异常打到 stderr,免得"截到半截却当成功"。
                print(f"警告: goto 未正常完成({e}),仍尝试截图", file=sys.stderr)
            try:
                pg.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass
            pg.wait_for_timeout(900)   # 给 ECharts / 渐变 / 布局定帧
            try:
                with open(html, encoding="utf-8", errors="ignore") as _stream:
                    _html_source = _stream.read()
                _chart_ids = sorted(set(re.findall(
                    r"echarts\.init\(\s*document\.getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)",
                    _html_source,
                )))
                _chart_init_count = len(re.findall(r"\becharts\.init\s*\(", _html_source))
                if _chart_init_count:
                    _chart_audit = pg.evaluate(
                        """payload => {
                          const missing=payload.ids.filter(id => {
                            const el=document.getElementById(id);
                            if(!el || !window.echarts) return true;
                            const graphic=el.querySelector('canvas,svg');
                            if(!graphic) return true;
                            const r=graphic.getBoundingClientRect();
                            return r.width < 2 || r.height < 2;
                          });
                          const rendered=[...document.querySelectorAll('[_echarts_instance_]')].filter(el => {
                            const graphic=el.querySelector('canvas,svg');
                            if(!graphic) return false;
                            const r=graphic.getBoundingClientRect();
                            return r.width >= 2 && r.height >= 2;
                          }).length;
                          return {missing, rendered};
                        }""",
                        {"ids": _chart_ids, "expected": _chart_init_count},
                    ) or {}
                    runtime["charts_missing"] = list(_chart_audit.get("missing") or [])
                    if int(_chart_audit.get("rendered") or 0) < _chart_init_count:
                        runtime["charts_missing"].append(
                            f"rendered={int(_chart_audit.get('rendered') or 0)}/expected={_chart_init_count}"
                        )
            except Exception as exc:
                runtime["page_errors"].append(f"ECharts runtime audit failed: {exc}"[:500])
            try:
                rep["broken"] = pg.evaluate(_BROKEN_IMAGE_JS) or []
            except Exception:
                rep["broken"] = []
            try:
                rep["overflow"] = pg.evaluate(_OVERFLOW_JS) or []
            except Exception:
                rep["overflow"] = []    # 检测失败绝不影响出图
            try:
                _c = pg.evaluate(_COLLISION_JS) or {}
                rep["overlap"] = _c.get("overlap", []) or []
                rep["crowded"] = _c.get("crowded", []) or []
                rep["boxoverflow"] = _c.get("boxoverflow", []) or []
                rep["innergap"] = _c.get("innergap", []) or []
            except Exception:
                pass
            try:
                rep["layout"] = pg.evaluate(_LAYOUT_GUARD_JS) or {}
            except Exception:
                pass
            try:
                rep["vbalance"] = pg.evaluate(_VBALANCE_JS)
            except Exception:
                pass
            try:
                rep["contrast"] = pg.evaluate(_CONTRAST_JS)
            except Exception:
                pass
            try:
                rep["cjkTypography"] = pg.evaluate(_CJK_TYPOGRAPHY_JS) or []
            except Exception:
                rep["cjkTypography"] = []
            pg.screenshot(path=out)
        finally:
            pg.close()
    finally:
        if owns_browser:
            b.close()
    return rep


def _batch_page_number(path):
    match = re.search(r"(\d+)", os.path.splitext(os.path.basename(path))[0])
    return int(match.group(1)) if match else None


def _runtime_failures(report):
    runtime = report.get("runtime") or {}
    return bool(runtime.get("script_failed") or runtime.get("page_errors") or runtime.get("charts_missing"))


def _batch_warning_summary(report):
    keys = ("broken", "overflow", "overlap", "crowded", "boxoverflow", "innergap")
    counts = {key: len(report.get(key) or []) for key in keys}
    layout = report.get("layout") or {}
    counts.update({key: len(layout.get(key) or [])
                   for key in ("customBody", "abs", "decor", "footer", "svgLarge")})
    counts["contrast"] = len((report.get("contrast") or {}).get("low") or [])
    counts["onimg"] = len((report.get("contrast") or {}).get("onimg") or [])
    counts["cjkTypography"] = len(report.get("cjkTypography") or [])
    runtime = report.get("runtime") or {}
    counts["script_failed"] = len(runtime.get("script_failed") or [])
    counts["page_errors"] = len(runtime.get("page_errors") or [])
    counts["charts_missing"] = len(runtime.get("charts_missing") or [])
    active = [f"{key}={value}" for key, value in counts.items() if value]
    return " ".join(active) if active else "clean"


_HARD_RENDER_KEYS = (
    "broken", "overflow",
)

# Geometry and typography heuristics (``boxoverflow``, ``overlap``, ``crowded``,
# ``cjkTypography`` and contrast candidates) are intentionally advisory.  They
# are useful diagnostic leads, but transforms, optical punctuation, intentional
# editorial overlap and stylised CJK can trigger them on perfectly readable
# pixels.  Only broken assets, confirmed overflow/clipping, runtime errors and
# footer displacement are deterministic render blockers.  Advisory findings
# remain in render.json for Slide/Review to verify against fresh pixels.


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hard_render_issues(report):
    issues = []
    for key in _HARD_RENDER_KEYS:
        values = report.get(key) or []
        if values:
            issues.append({"type": key, "count": len(values), "items": values})
    layout = report.get("layout") or {}
    for key in ("footer",):
        values = layout.get(key) or []
        if values:
            issues.append({"type": key, "count": len(values), "items": values})
    if layout.get("footerPushed"):
        issues.append({"type": "footerPushed", "count": 1,
                       "items": [layout.get("footerPushed")]})
    runtime = report.get("runtime") or {}
    for key in ("script_failed", "page_errors", "charts_missing"):
        values = runtime.get(key) or []
        if values:
            issues.append({"type": key, "count": len(values), "items": values})
    return issues


def _atomic_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + f".{os.getpid()}.tmp"
    with open(temp, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.replace(temp, path)


def _record_render_report(root, number, slide, target, report):
    """Persist canonical page diagnostics; stdout is never the quality truth source."""
    root = os.path.abspath(root)
    source = os.path.abspath(slide)
    output = os.path.abspath(target)
    if not (os.path.isfile(source) and os.path.isfile(output)):
        return
    record = {
        "page": int(number),
        "source": os.path.relpath(source, root).replace(os.sep, "/"),
        "png": os.path.relpath(output, root).replace(os.sep, "/"),
        "source_sha256": _sha256_file(source),
        "png_sha256": _sha256_file(output),
        "source_mtime_ns": os.stat(source).st_mtime_ns,
        "png_mtime_ns": os.stat(output).st_mtime_ns,
        "summary": _batch_warning_summary(report),
        "hard_issues": _hard_render_issues(report),
        "report": report,
    }
    lock_path = os.path.join(root, "_trace", "render-report.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "a+b") as lock:
        _fcntl.flock(lock.fileno(), _fcntl.LOCK_EX)
        manifest_path = os.path.join(root, "renders", "render.json")
        try:
            with open(manifest_path, encoding="utf-8") as stream:
                manifest = json.load(stream)
        except (OSError, ValueError, TypeError):
            manifest = {"schema_version": 2, "pages": {}}
        manifest["schema_version"] = 2
        manifest.setdefault("pages", {})[f"{int(number):02d}"] = record
        _atomic_json(manifest_path, manifest)

        issue_path = os.path.join(root, "_trace", "render-issues.json")
        try:
            with open(issue_path, encoding="utf-8") as stream:
                ledger = json.load(stream)
        except (OSError, ValueError, TypeError):
            ledger = {"schema_version": 1, "pages": {}}
        ledger["schema_version"] = 1
        ledger.setdefault("pages", {})[f"{int(number):02d}"] = {
            "source_sha256": record["source_sha256"],
            "png_sha256": record["png_sha256"],
            "hard_issues": record["hard_issues"],
        }
        _atomic_json(issue_path, ledger)
        _fcntl.flock(lock.fileno(), _fcntl.LOCK_UN)


def _workspace_from_render_paths(slide, target):
    source_parent = os.path.dirname(os.path.abspath(slide))
    output_parent = os.path.dirname(os.path.abspath(target))
    if os.path.basename(source_parent) != "slides" or os.path.basename(output_parent) != "renders":
        return None
    source_root = os.path.dirname(source_parent)
    output_root = os.path.dirname(output_parent)
    return source_root if source_root == output_root else None


def render_batch(root, pages=None, width=1600, height=900):
    """Render selected deck pages while reusing one Playwright/Chromium process."""
    root = os.path.abspath(root)
    wanted = None
    if pages:
        wanted = {int(item.strip()) for item in pages.split(",") if item.strip()}
    slides = []
    for path in sorted(glob.glob(os.path.join(root, "slides", "slide_*.html"))):
        number = _batch_page_number(path)
        if ".bak." not in os.path.basename(path) and number is not None and (wanted is None or number in wanted):
            slides.append((number, path))
    if not slides:
        raise FileNotFoundError("no matching slides found")
    os.makedirs(os.path.join(root, "renders"), exist_ok=True)
    _setup_libs()
    sync_playwright = _sync_playwright()
    slot = _acquire_render_slot()
    playwright = None
    browser = None
    hard_pages = []
    try:
        playwright = _call_with_timeout(sync_playwright().start, 60, "Playwright start")
        browser_exe = _ensure_browser_available(playwright)
        browser = playwright.chromium.launch(executable_path=browser_exe, args=LAUNCH_ARGS)
        for number, slide in slides:
            target = os.path.join(root, "renders", f"slide_{number:02d}.png")
            report = _render_once(
                playwright, os.path.abspath(slide), target, width, height,
                browser_exe=browser_exe, browser=browser,
            )
            if not os.path.isfile(target) or not os.path.getsize(target):
                raise RuntimeError(f"render produced no PNG for {os.path.basename(slide)}")
            if _runtime_failures(report):
                _record_render_report(root, number, slide, target, report)
                raise RuntimeError(
                    f"runtime dependency failure in {os.path.basename(slide)}: "
                    + json.dumps(report.get("runtime"), ensure_ascii=False)
                )
            _record_render_report(root, number, slide, target, report)
            if _hard_render_issues(report):
                hard_pages.append(number)
            print(f"{target} {_batch_warning_summary(report)}")
        if hard_pages:
            raise RuntimeError(
                "render quality gate failed for pages: "
                + ",".join(f"{page:02d}" for page in hard_pages)
                + "; see _trace/render-issues.json"
            )
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            _stop_playwright(playwright)
        if slot is not None:
            _release_render_slot(slot)


def _player_chart_targets(root):
    targets = []
    for slide in sorted(glob.glob(os.path.join(root, "slides", "slide_*.html"))):
        number = _batch_page_number(slide)
        if number is None or ".bak." in os.path.basename(slide):
            continue
        try:
            source = open(slide, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        ids = sorted(set(re.findall(
            r"echarts\.init\(\s*document\.getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)",
            source,
        )))
        expected = len(re.findall(r"\becharts\.init\s*\(", source))
        if expected:
            targets.append((number, ids, expected))
    return targets


def audit_player(root):
    """Open canonical present.html and verify every ECharts page in its iframe."""
    root = os.path.abspath(root)
    present = os.path.join(root, "present.html")
    if not os.path.isfile(present) or not os.path.getsize(present):
        raise FileNotFoundError("present.html is missing or empty")
    targets = _player_chart_targets(root)
    if not targets:
        print("player-runtime-audit:PASS charts=0")
        return
    _setup_libs()
    sync_playwright = _sync_playwright()
    slot = _acquire_render_slot()
    playwright = None
    browser = None
    try:
        playwright = _call_with_timeout(sync_playwright().start, 60, "Playwright start")
        browser_exe = _ensure_browser_available(playwright)
        browser = playwright.chromium.launch(executable_path=browser_exe, args=LAUNCH_ARGS)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page_errors = []
        script_failures = []
        page.on("pageerror", lambda error: page_errors.append(str(error)[:500]))

        def failed(request):
            try:
                if request.resource_type == "script":
                    script_failures.append(request.url)
            except Exception:
                pass

        page.on("requestfailed", failed)
        page.goto("file://" + present, wait_until="load", timeout=30000)
        failures = []
        for number, ids, expected in targets:
            page.evaluate("n => window.cleanDeck.go(n)", number)
            page.wait_for_function(
                "n => { const f=document.querySelector(`iframe[data-slide=\"${n}\"]`); "
                "return f && f.dataset.ok === '1'; }",
                arg=number,
                timeout=10000,
            )
            handle = page.query_selector(f'iframe[data-slide="{number}"]')
            frame = handle.content_frame() if handle else None
            if frame is None:
                failures.append(f"slide_{number:02d}: iframe unavailable")
                continue
            result = frame.evaluate(
                """payload => {
                  const missing=payload.ids.filter(id => {
                    const el=document.getElementById(id);
                    if(!el || !window.echarts) return true;
                    const graphic=el.querySelector('canvas,svg');
                    if(!graphic) return true;
                    const r=graphic.getBoundingClientRect();
                    return r.width < 2 || r.height < 2;
                  });
                  const rendered=[...document.querySelectorAll('[_echarts_instance_]')].filter(el => {
                    const graphic=el.querySelector('canvas,svg');
                    if(!graphic) return false;
                    const r=graphic.getBoundingClientRect();
                    return r.width >= 2 && r.height >= 2;
                  }).length;
                  return {missing,rendered};
                }""",
                {"ids": ids, "expected": expected},
            ) or {}
            if result.get("missing") or int(result.get("rendered") or 0) < expected:
                failures.append(
                    f"slide_{number:02d}: missing={result.get('missing') or []} "
                    f"rendered={int(result.get('rendered') or 0)}/expected={expected}"
                )
        if script_failures:
            failures.append("failed scripts: " + ", ".join(sorted(set(script_failures))[:8]))
        if page_errors:
            failures.append("page errors: " + " | ".join(page_errors[:8]))
        if failures:
            raise RuntimeError("canonical player runtime audit failed: " + "; ".join(failures))
        print(f"player-runtime-audit:PASS charts={sum(expected for _, _, expected in targets)}")
    finally:
        if browser is not None:
            browser.close()
        if playwright is not None:
            _stop_playwright(playwright)
        if slot is not None:
            _release_render_slot(slot)


def _batch_cli(argv):
    parser = argparse.ArgumentParser(prog="render.py --batch")
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--pages", help="comma-separated page numbers; default renders all")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args(argv)
    last_error = None
    for attempt in range(2):
        try:
            render_batch(args.root, args.pages, args.width, args.height)
            return 0
        except BrowserUnavailable as exc:
            print(f"batch render failed: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1.5)
    print(f"batch render failed after retry: {last_error}", file=sys.stderr)
    return 1


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--audit-player":
        if len(sys.argv) != 3:
            print("用法: render.py --audit-player <workspace>", file=sys.stderr)
            raise SystemExit(2)
        try:
            audit_player(sys.argv[2])
        except Exception as exc:
            print(f"player runtime audit failed: {exc}", file=sys.stderr)
            raise SystemExit(1)
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "--batch":
        raise SystemExit(_batch_cli(sys.argv[2:]))
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print("用法: render.py <html> <out.png> [宽] [高]\n"
              "      render.py --batch <workspace> [--pages 1,2,7]")
        return
    if len(sys.argv) < 3:
        print("用法: render.py <html> <out.png> [宽] [高]", file=sys.stderr)
        sys.exit(2)
    html = os.path.abspath(sys.argv[1])
    out = os.path.abspath(sys.argv[2])
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
    h = int(sys.argv[4]) if len(sys.argv) > 4 else 900
    if not os.path.exists(html):
        print(f"渲染失败:找不到 HTML {html}", file=sys.stderr)
        sys.exit(1)

    # 渲染必须只读源 HTML。发现中文后的半角标点只报告,由 Slide 修源文件后重渲。
    try:
        with open(html, "r", encoding="utf-8") as _f:
            _orig = _f.read()
        _norm = _normalize_cjk_punct(_orig)
        if _norm != _orig:
            count = sum(a != b for a, b in zip(_orig, _norm)) + abs(len(_orig) - len(_norm))
            print(f"⚠ CJK-PUNCT: {count} 处中文后半角标点;render 保持只读,请修 HTML 后重渲", file=sys.stderr)
    except Exception as _e:
        print(f"警告: CJK 标点只读检查跳过({_e})", file=sys.stderr)

    _setup_libs()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    sync_playwright = _sync_playwright()
    last_err = None
    # 全局并发 chromium 上限:整个渲染(含 3 次重试)期间持一个 flock 槽;进程任何方式退出都释放。
    _slot_fd = _acquire_render_slot()
    if _slot_fd is not None:
        _atexit.register(_release_render_slot, _slot_fd)
    for attempt in range(3):                 # 高并发下 chromium 偶发崩(TargetClosed),重试 + 退避
        p = None
        try:
            rep = {"broken": [], "overflow": [], "overlap": [], "crowded": [], "boxoverflow": [], "innergap": [], "vbalance": None, "layout": {}}
            p = _call_with_timeout(sync_playwright().start, 60, "Playwright start")
            browser_exe = _ensure_browser_available(p)
            rep = _render_once(p, html, out, w, h, browser_exe)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                print(out)
                print("✓ RENDER_OK: PNG 已生成。若上面有 greenlet/字体/CDN 等 stderr 警告,均为无害噪声——"
                      "环境已就绪,**切勿 pip install / 重装或调试 playwright/chromium**;有问题只改 HTML。")
                broken = rep.get("broken") or []
                if broken:
                    print("⚠ BROKEN-IMAGE: %d 个 img 未加载或自然尺寸为 0——修正本地路径/文件后重渲:" % len(broken))
                    for e in broken:
                        print("   · src=%s alt=%s class=%s complete=%s natural=%s"
                              % (e.get("src"), e.get("alt"), e.get("cls"), e.get("complete"), e.get("natural")))
                runtime = rep.get("runtime") or {}
                if _runtime_failures(rep):
                    workspace = _workspace_from_render_paths(html, out)
                    number = _batch_page_number(html)
                    if workspace is not None and number is not None:
                        _record_render_report(workspace, number, html, out, rep)
                    print("✗ RUNTIME-DEPENDENCY: 页面脚本未完整加载或图表没有生成真实 Canvas/SVG：")
                    for item in runtime.get("script_failed") or []:
                        print("   · script %s (%s)" % (item.get("url"), item.get("error")))
                    for item in runtime.get("page_errors") or []:
                        print("   · pageerror %s" % item)
                    for item in runtime.get("charts_missing") or []:
                        print("   · chart #%s 未产生 Canvas/SVG" % item)
                    print("机检结论: 不过")
                    sys.exit(3)
                ov = rep.get("overflow") or []
                if ov:
                    print("⚠ OVERFLOW: %d 个元素超出 1600×900 安全框(.slide 是 overflow:hidden,"
                          "会静默裁掉;no-visual 依靠 DOM 报告)——**当硬伤修**:收紧该元素/缩内容/换版式,"
                          "别用 overflow:hidden 硬遮。越界最狠的几个:" % len(ov))
                    for e in ov:
                        _t = ("  文字「%s」" % e["txt"]) if e.get("txt") else ""
                        print("   · <%s class=\"%s\"> 越 %s 边 %spx%s"
                              % (e.get("tag"), e.get("cls"), e.get("side"), e.get("over"), _t))
                lap = rep.get("overlap") or []
                if lap:
                    print("⚠ OVERLAP: %d 处元素相互遮盖(DOM 确定性检测)——文字被压 / 被盖 = 硬伤:"
                          "让两块**在流式布局里错开**(别绝对定位互叠)、拉间距、或给图上文字垫局部 scrim + "
                          "`paint-order:stroke`;Canvas/图片概念图的准确文字放 HTML 顶层。最重的几处:" % len(lap))
                    for e in lap:
                        a, b2 = e.get("a", {}), e.get("b", {})
                        print("   · <%s「%s」> 撞 <%s「%s」> 叠 ~%s%%"
                              % (a.get("tag"), a.get("txt"), b2.get("tag"), b2.get("txt"), e.get("pct")))
                crw = rep.get("crowded") or []
                if crw:
                    print("⚠ CROWDED: %d 个文字挤出自身容器(定高节点 / 表格格 / 卡片塞不下、贴边或截断)——"
                          "**放大容器 / 缩短文案 / 降字号 / 加 padding**,别硬塞:" % len(crw))
                    for e in crw:
                        print("   · <%s class=\"%s\"> 文字「%s」溢出 %s×%spx"
                              % (e.get("tag"), e.get("cls"), e.get("txt"), e.get("ox"), e.get("oy")))
                bxo = rep.get("boxoverflow") or []
                if bxo:
                    print("⚠ TEXT-OVERFLOW-BOX: %d 个内容盒(panel/卡片/正文区)里文字撑出了自己的文本框——"
                          "盒是 overflow:visible,文字溢到框外但没被裁、也没超整页,截图上看着「压边/串到下一块」= 硬伤。"
                          "**别靠 1fr 硬撑不等量文本**:缩文案 / 降字号(clamp)/ 该盒给 auto 行高、或整体换更省高的版式。最狠的几个:" % len(bxo))
                    for e in bxo:
                        _s = (("↓%spx" % e["ob"]) if e.get("ob") else "") + (" →%spx" % e["orr"] if e.get("orr") else "")
                        print("   · <%s class=\"%s\"> 文字「%s」溢出 %s"
                              % (e.get("tag"), e.get("cls"), e.get("txt"), _s))
                igp = rep.get("innergap") or []
                if igp:
                    print("⚠ INNER-GAP: %d 个卡片中间空出一大块(相邻内容块之间 >44px 死白 + 卡内利用率低)——"
                          "多因 `margin-top:auto` 把末块顶到底、或等高网格把内容少的卡拉高。**别让卡靠 1fr 被动撑高**:"
                          "内容按需高 + 顶对齐(align-content:start)、去掉不必要的 margin-top:auto、或补齐内容:" % len(igp))
                    for e in igp:
                        print("   · <div class=\"%s\"> 中缝 %spx(利用率 %s%%)"
                              % (e.get("cls"), e.get("gap"), e.get("util")))
                lg = rep.get("layout") or {}
                cbody = lg.get("customBody") or []
                if cbody:
                    print("⚠ CUSTOM-BODY: 标准骨架被绕开/替换——必须 root 直下 `<section class=\"slide\">` + "
                          "`.slide-title` + `.slide-body` + `.slide-footer`;不要造 `.slide-body-xx` 这类替身,否则底部安全区/重心/页脚机检都会失效:")
                    for e in cbody:
                        print("   · %s%s" % (e.get("msg"), (" class=\"" + e.get("cls", "") + "\"") if e.get("cls") else ""))
                abs_items = lg.get("abs") or []
                if abs_items:
                    print("⚠ ABS-LAYOUT: %d 个正文内容用 absolute/fixed 拼版——装饰/scrim 可以绝对定位,正文/图表/标签要回到 `.slide-body` 的网格/flow,否则极易遮盖和下方溢出:" % len(abs_items))
                    for e in abs_items:
                        print("   · <%s class=\"%s\"> %s 文字「%s」"
                              % (e.get("tag"), e.get("cls"), e.get("box"), e.get("txt")))
                decor = lg.get("decor") or []
                if decor:
                    print("⚠ DECOR-OVERLAP: %d 处装饰/水印/形状压到文字——装饰必须低 z-index、避让标题/正文/页脚,或显式降透明/声明 overlap-ok:" % len(decor))
                    for e in decor:
                        print("   · decor class=\"%s\" 压到文字「%s」约 %s%%"
                              % (e.get("decor"), e.get("text"), e.get("pct")))
                foot = lg.get("footer") or []
                if foot:
                    print("⚠ FOOTER-COVER: %d 个媒体/装饰碰到页脚/页码安全带——正文区图片/Canvas/小 SVG/装饰要在 footer 上方收住;满铺页则给页脚文字 scrim/托板:" % len(foot))
                    for e in foot:
                        print("   · <%s class=\"%s\"> 与页脚重叠约 %s%%"
                              % (e.get("tag"), e.get("cls"), e.get("pct")))
                fp = lg.get("footerPushed")
                if fp:
                    _b = fp.get("belowViewport", 0)
                    print("⚠ FOOTER-PUSHED: 正文体量把底部撑破了(最严重的一类底部溢出)——"
                          "%s%s。**别把内容硬堆到爆**:减字 / 拆两页 / 换更紧凑版式(多要点用 `.arch-*` 2×2 卡,别 N 项纵向长流水)、"
                          "定高区改 `minmax(0,1fr)` 自适应,守住 `--body-safe-bottom`,让页脚坐在安全带上方。"
                          % (("页脚被挤出视口底 %spx;" % _b) if _b > 2 else "",
                             ("正文最深内容「%s」压过页脚顶 %spx" % (fp.get("worst", ""), fp.get("bodyOverFooter")))
                             if fp.get("bodyOverFooter", 0) > 8 else "页脚位置异常"))
                widow = lg.get("widow") or []
                if widow:
                    print("⚠ WIDOW-LINE: %d 处文本末行只剩 1-2 个孤字(寡行,读着突兀)——"
                          "**别让容器太窄逼出孤字**:加宽文字块 / 去掉多余 max-width / 微调字号让末行不落单,或在语义完整处主动断行:" % len(widow))
                    for e in widow:
                        print("   · <%s class=\"%s\"> 末行孤字「%s」"
                              % (e.get("tag"), e.get("cls"), e.get("last")))
                lonely = lg.get("imgLonely") or []
                if lonely:
                    print("⚠ IMG-LONELY: %d 张位图/照片相对正文区过小且孤立(孤图突兀、像没放好)——"
                          "**放大到有存在感 / 落进版面网格 / 配紧邻说明**,或成组排(别单张小图飘在大片留白里):" % len(lonely))
                    for e in lonely:
                        print("   · <img class=\"%s\"> 大小 %s(占正文 %s%%)"
                              % (e.get("cls"), e.get("size"), e.get("pct")))
                coob = lg.get("coverOOB") or []
                if coob:
                    print("⚠ COVER-OOB: %d 处封面标题贴到 / 越出安全区(常见「标题堆左上角、快出界」)——"
                          "封面巨字号用 `clamp()` / 按字数降档,标题块守住 `--margin-x/y` 安全边、在安全区内做有意构图(别顶死左上角):" % len(coob))
                    for e in coob:
                        _sides = []
                        for k, lbl in (("overL", "左"), ("overT", "上"), ("overR", "右"), ("overB", "下")):
                            if e.get(k, 0) > 2:
                                _sides.append("%s越%spx" % (lbl, e[k]))
                        print("   · %s %s" % (e.get("sel"), " ".join(_sides)))
                large_svg = lg.get("svgLarge") or []
                if large_svg:
                    print("⚠ SVG-LARGE: %d 个 SVG 超出 icon/标记尺度——新页面的大型流程、架构、机制图"
                          "默认改用 Canvas 几何 + HTML 标签，或图片 + HTML 标注；仅用户要求矢量或复用准确矢量资产时"
                          "给 class `svg-allowed`/`vector-asset` 豁免:" % len(large_svg))
                    for e in large_svg:
                        print("   · svg class=\"%s\" 大小 %s" % (e.get("cls"), e.get("size")))
                small = lg.get("svgSmall") or []
                if small:
                    print("⚠ SVG-SMALL: %d 个旧式大型 SVG 相对 `.slide-body` 过小——若是概念图,"
                          "优先迁移为 Canvas/图片 + HTML 标签并让主视觉吃满正文区;若必须保留矢量,放大图框:" % len(small))
                    for e in small:
                        print("   · svg class=\"%s\" 大小 %s, body %s"
                              % (e.get("cls"), e.get("size"), e.get("body")))
                slabel = lg.get("svgLabel") or []
                if slabel:
                    print("⚠ SVG-LABEL-OVERLAP: %d 处旧 SVG 标签互相遮盖——优先把准确文字迁到 HTML 层;"
                          "必须保留时重排标签、扩大节点间距:" % len(slabel))
                    for e in slabel:
                        print("   · 「%s」撞「%s」约 %s%%"
                              % (e.get("a"), e.get("b"), e.get("pct")))
                vb = rep.get("vbalance")
                if vb and vb.get("H"):
                    Hh, top, bot = vb["H"], vb["top"], vb["bot"]
                    span = bot - top
                    off = (top + bot) / 2.0 - Hh / 2.0          # >0 内容偏下, <0 偏上
                    if span < 0.82 * Hh and abs(off) > 0.13 * Hh:
                        where = "下" if off > 0 else "上"
                        empty = "上" if off > 0 else "下"
                        band = top if off > 0 else (Hh - bot)
                        print("⚠ VBALANCE: 主体内容重心偏%s、%s方留白 ~%dpx——视觉重心没居中、%s边大片空着(治「大字/内容位置奇怪、上下留白」)。"
                              "把内容在安全区内**垂直居中或撑开占满**(短内容 justify-content:center;内容多就拉开层级/加分区把版面填匀),"
                              "别让 hero/大字/正文孤零坠在一侧。〔封面/满图页有意偏置可忽略。〕"
                              % (where, empty, int(band), empty))
                    _fill = vb.get("fill")
                    if _fill is not None and _fill < 42:
                        print("⚠ SPARSE: 版面填充率仅 ~%d%%、构图发空(内容盒只盖住画布约 %d%%,大片深底空着、读成「空 / 没做完」;"
                              "目录页 / 少条目页最常栽——纵向即便居中平衡、VBALANCE 也看不出)。这几乎都是**规划 / base.css 定死的**,别指望子代理临场救:"
                              "① 别靠 `justify-content:center` 把少量内容居中留大边、别用 `auto 1fr auto` 让 1fr 那段空着(= 行内 leader gap);"
                              "② 放大标题 / 序号字阶到能压住画布、把条目做成**撑满纵向的编号块**、加锚定视觉 / 分区把版面填匀;"
                              "③ 真只有 2–3 条就合并轻页或每条升维(加释义 / 数据 / 图元)。〔封面 / 满图 / 单焦点 hero 有意留白可忽略。〕"
                              % (_fill, _fill))
                ct = rep.get("contrast") or {}
                clow = ct.get("low") or []
                if clow:
                    print("⚠ CONTRAST: %d 处文字对背景对比度不足(WCAG,低于阈值 = 投影/小屏几乎读不了 = 硬伤)——"
                          "把该文字**换深一档(600 级)/ 改高亮白·亮米·主题色**,或给底垫更实的色;暗底禁深灰/深棕/暗金小字:" % len(clow))
                    for e in clow:
                        print("   · 「%s」<%s> 对比 ~%s:1(需 ≥%s,字号 %spx)"
                              % (e.get("txt"), e.get("cls"), e.get("ratio"), e.get("need"), e.get("fs")))
                coni = ct.get("onimg") or []
                if coni:
                    print("⚠ ON-IMG-NOSCRIM: %d 处文字压在图/满铺背景上但**无 scrim/托板声明**(图底测不出对比、极易糊)——"
                          "用现成 `.scrim--t/b/l`(或 `.scrim--light`)定向压一侧、或给该行加 `.text-plate` 局部托板、"
                          "或 `paint-order:stroke` 描边(别整图压暗、保住氛围):" % len(coni))
                    for e in coni:
                        print("   · 「%s」<%s> 字号 %spx" % (e.get("txt"), e.get("cls"), e.get("fs")))
                cjk_typography = rep.get("cjkTypography") or []
                if cjk_typography:
                    print("⚠ CJK-TYPE: %d 处中文字体语义错误——同一句中文必须保持同一字体家族；强调只改颜色/字重/字号。中文不得误用 mono 或拉丁式疏字距；卡通/手写体只有合题且加 `.is-expressive-type` 才允许：" % len(cjk_typography))
                    for e in cjk_typography:
                        print("   · 「%s」<%s> %s, letter-spacing=%spx"
                              % (e.get("text"), e.get("cls"), "/".join(e.get("kinds") or []), e.get("letterSpacing")))
                workspace = _workspace_from_render_paths(html, out)
                number = _batch_page_number(html)
                if workspace is not None and number is not None:
                    _record_render_report(workspace, number, html, out, rep)
                hard_issues = _hard_render_issues(rep)
                if hard_issues:
                    print(
                        "机检结论: 不过；硬伤已写入 _trace/render-issues.json："
                        + ",".join(item["type"] for item in hard_issues),
                        file=sys.stderr,
                    )
                    sys.exit(4)
                return
        except BrowserUnavailable as e:
            print(f"渲染失败:{e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            last_err = e
        finally:
            if p is not None:
                _stop_playwright(p)
        time.sleep(1.5 * (attempt + 1))      # 退避,顺带错峰,缓解 sibling 同时起 chromium
    print(f"渲染失败(重试 3 次): {last_err}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
