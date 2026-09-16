#!/usr/bin/env python3
"""sn-ppt-dazzle 渲染脚本：把单 HTML deck 渲染成逐页 PNG（给 agent 看图自检用）。

用法（在仓库根目录、fancy-sft 环境下）：
    python skills/sn-ppt-dazzle/scripts/render_deck.py <deck.html> <out_dir> --page N   # 渲染第 N 页（1-based）
    python skills/sn-ppt-dazzle/scripts/render_deck.py <deck.html> <out_dir> --all      # 渲染全部页 + contact sheet

行为契约（agent loop / accept 依赖，勿随意更改）：
- stdout 每行一个生成的 PNG 路径，**末行保证是一个 PNG 路径**（--all 时末行是 contact_sheet.png）。
- 告警（console error / 静态页 / fallback 翻页）打印在 PNG 路径之前，前缀 [console]/[static]/[nav]。
- 渲染元数据写 <out_dir>/render.json（console_errors / static_pages / blank_pages / nav / 页数）。
- 失败（页面打不开 / 一页都没截到）：stderr + 退出码非 0。

页面导航：
- --page N 优先用 `file://deck.html?slide=N` 直跳（sn-ppt-dazzle 架构契约要求 deck 支持），
  直跳后用"活动页信号"校验落点；失败则 fallback 从首页按 ArrowRight 翻过去并告警。
- --all 用真实按键翻页（ArrowRight/Space/PageDown + 活动页信号 + 截图感知哈希兜底 + 循环检测），
  这同时验证了 deck 的键盘导航真实可用。

动态检测（--motion-check，默认开）：对每页采样三帧——
- early（到达页后 ~0.5s，入场动画进行中）
- final（~2.6s，入场动画按契约 ≤2s 已落定，作为正式截图）
- live （final 后再 ~0.6s，探测持续型动画）
entrance_diff = diff(early, final)，live_diff = diff(final, live)。两者都 ≈0 → 该页记入
static_pages（仅是信号，不是错误：庄重场景的静帧页可以是有意识的设计，由 agent/judge 结合场景判断）。

移植自 visual_qc/render_shots.py（活动页信号 JS / 翻页收敛 / blank 检测 / 浏览器库注入），
本脚本必须保持自包含（skill 可整体拷走），如修 bug 请两边同步。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings
from io import BytesIO
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)  # PIL getdata 噪声

# ── 画布尺寸 / 时间常量 ─────────────────────────────────────────────────
DECK_W, DECK_H = 1280, 720
DEVICE_SCALE = 1               # CPU-only swiftshader 下 2x 会让重型 3D 页光栅慢一倍易超时
MAX_PAGES = 40                 # 逐页上界（防异常 deck 死循环）
SETTLE_MS = 1500               # 首屏稳定（Three.js / 粒子 / 字体）
NAV_SETTLE_MS = 900            # 翻页后过渡动画稳定（phash 模式判定"翻没翻动"前的等待）
NAV_CHECK_MS = 200             # signal 模式翻页确认等待（class 同步切换，无需等过渡画完，
                               # 早确认才能让 early 帧捕捉到快速入场动画）
EARLY_MS = 500                 # motion-check：early 帧采样点（入场动画进行中）
FINAL_EXTRA_MS = 2100          # early 之后再等这么久截 final 帧（合计 ~2.6s，入场动画已落定；
                               # 3D 场景也需要 ~2.5s 才把相机/布局 settle 到位，勿调小）
LIVE_EXTRA_MS = 600            # final 之后再等这么久截 live 帧（探测持续动画）
GOTO_TIMEOUT_MS = 30000
NETWORKIDLE_TIMEOUT_MS = 8000
SCREENSHOT_TIMEOUT_MS = 60000

# 感知差异阈值：16x16 灰度块平均绝对差（翻页判定用，沿用 render_shots 校准值）
PHASH_SAME_THRESH = 6.0        # 差 < 此值视为"没翻动"
BLANK_STD_THRESH = 3.0         # 灰度标准差 < 此值视为空白/近纯色页
MAX_CONSOLE_ERRORS = 20        # console 错误最多记录条数（去重后）

# 动态检测（64x64 网格）：无损截图下静态内容逐像素恒等，任何超出噪声的局部差异都是运动。
# 16x16 均值对小粒子/扫描线太钝（被平均稀释），改为统计"发生变化的格子数"。
MOTION_GRID = 64               # 下采样网格边长
MOTION_CELL_EPS = 4            # 格子灰度差 >= 此值算"变化格"（容忍抗锯齿微差）
MOTION_MIN_CELLS = 5           # 变化格数 < 此值（/4096）视为无运动


def ensure_browser_libs() -> None:
    """把 $CONDA_PREFIX/lib 与 ~/pwdeps/lib 加进 LD_LIBRARY_PATH，让 chromium 找到系统库。

    conda-forge 装了 nss/nspr/atk/X11 等大部分库；libgbm/libcups 系统与 conda 都没有，
    放在 ~/pwdeps/lib（从可用机器拷贝的二进制）。
    """
    candidates = []
    prefix = os.environ.get("CONDA_PREFIX")
    if prefix:
        candidates.append(str(Path(prefix) / "lib"))
    pwdeps = Path.home() / "pwdeps" / "lib"
    if pwdeps.is_dir():
        candidates.append(str(pwdeps))
    cur = os.environ.get("LD_LIBRARY_PATH", "")
    parts = [p for p in cur.split(":") if p]
    for libdir in candidates:
        if libdir not in parts:
            parts.insert(0, libdir)
    if parts:
        os.environ["LD_LIBRARY_PATH"] = ":".join(parts)
    # chromium 静态链接的 fontconfig 默认读 /etc/fonts/fonts.conf；本 pod 没有 /etc/fonts，
    # 不设 FONTCONFIG_FILE 会让整个字体系统失效（连 webfont 文本都画不出来，页面只剩图形）。
    if not Path("/etc/fonts/fonts.conf").exists() and "FONTCONFIG_FILE" not in os.environ:
        if prefix and (Path(prefix) / "etc/fonts/fonts.conf").exists():
            os.environ["FONTCONFIG_FILE"] = str(Path(prefix) / "etc/fonts/fonts.conf")


def chromium_executable_path() -> str | None:
    """Return a concrete Chromium executable when the runtime preselects one.

    Playwright 1.52 may prefer a headless-shell binary that is not present in the
    shared runtime cache. The generation wrapper sets this explicitly so the
    agent does not spend turns repairing the browser environment.
    """
    candidates: list[Path] = []
    for key in ("DYNAMIC_PPT_CHROMIUM_EXECUTABLE", "PLAYWRIGHT_CHROMIUM_EXECUTABLE"):
        value = os.environ.get(key, "").strip()
        if value:
            candidates.append(Path(value))
    root_value = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if root_value:
        root = Path(root_value)
        candidates.extend(sorted(root.glob("chromium-*/chrome-linux*/chrome"), reverse=True))
        candidates.extend(
            sorted(
                root.glob("chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
                reverse=True,
            )
        )
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


# 读"当前活动页"信号：返回 "活动页索引:总页数"（如 "2:6"）；测不到返回 "-1:N"。
# 优先级：显式 active/current 类 → 最可见(opacity 高且占满)的 slide 元素。
_ACTIVE_SIGNAL_JS = r"""
() => {
  // 只认 deck 契约的幻灯片标记：class="slide"（精确 token，不匹配 .slide-xxx）或 data-slide。
  // 不要用 [class*="page"]/section 等宽匹配——会把 .page-pad 等内容类名误数成幻灯片，触发假 [nav] 告警。
  const sel = '.slide,[data-slide]';
  let els = [...document.querySelectorAll(sel)];
  els = els.filter(e => {
    const r = e.getBoundingClientRect();
    return r.width >= window.innerWidth * 0.5 && r.height >= window.innerHeight * 0.5;
  });
  const total = els.length;
  if (total === 0) return "-1:0";
  for (let i = 0; i < total; i++) {
    const c = (els[i].className && els[i].className.baseVal !== undefined)
      ? els[i].className.baseVal : (els[i].className || '');
    if (/(^|[\s_-])(active|current|is-active|selected|on|visible|show)([\s_-]|$)/i.test(c))
      return i + ":" + total;
  }
  let best = -1, bo = -1;
  els.forEach((e, i) => {
    const s = getComputedStyle(e);
    if (s.display === 'none' || s.visibility === 'hidden') return;
    const o = parseFloat(s.opacity || '1');
    if (o > bo) { bo = o; best = i; }
  });
  return best + ":" + total;
}
"""


def _img_stats(png_bytes: bytes) -> tuple[float, tuple]:
    """返回 (灰度标准差, 16x16 缩略灰度块) —— 用于空白检测 + 感知差异。"""
    from PIL import Image

    im = Image.open(BytesIO(png_bytes)).convert("L").resize((16, 16))
    px = list(im.getdata())
    n = len(px)
    mean = sum(px) / n
    var = sum((p - mean) ** 2 for p in px) / n
    return var ** 0.5, tuple(px)


def _block_diff(a: tuple, b: tuple) -> float:
    """两个 16x16 灰度块的平均绝对差（0-255）。"""
    if not a or not b or len(a) != len(b):
        return 999.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _motion_blocks(png_bytes: bytes) -> tuple:
    """64x64 灰度网格（动态检测专用，比 16x16 phash 细得多）。"""
    from PIL import Image

    im = Image.open(BytesIO(png_bytes)).convert("L").resize((MOTION_GRID, MOTION_GRID))
    return tuple(im.getdata())


def _moving_cells(a: tuple, b: tuple) -> int:
    """两帧之间灰度差 >= MOTION_CELL_EPS 的格子数（0..MOTION_GRID^2）。"""
    if not a or not b or len(a) != len(b):
        return -1
    return sum(1 for x, y in zip(a, b) if abs(x - y) >= MOTION_CELL_EPS)


def _parse_sig(sig: str) -> tuple[int, int]:
    try:
        i, t = sig.split(":")
        return int(i), int(t)
    except Exception:
        return -1, 0


class DeckRenderer:
    """单次 CLI 调用：起独立 chromium → 渲染 → 关闭。"""

    def __init__(self, html_path: Path, out_dir: Path, motion_check: bool = True) -> None:
        self.html_path = html_path
        self.out_dir = out_dir
        self.motion_check = motion_check
        self.console_errors: list[str] = []
        self.rendered_this_run: set[int] = set()
        self.meta: dict = {
            "deck": str(html_path),
            "w": DECK_W, "h": DECK_H,
            "mode": "", "nav": "",
            "n_pages": 0,
            "pages": [],            # [{page, png, blank, entrance_diff, live_diff, static}]
            "console_errors": [],
            "static_pages": [],
            "blank_pages": [],
            "notes": "",
        }
        self._pw = None
        self._browser = None
        self._page = None

    # ── 浏览器生命周期 ────────────────────────────────────────────────
    def start(self) -> None:
        ensure_browser_libs()
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        launch_kwargs = {
            "headless": True,
            "args": [
                "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                "--use-gl=swiftshader", "--enable-unsafe-swiftshader",
            ],
        }
        chromium_path = chromium_executable_path()
        if chromium_path:
            launch_kwargs["executable_path"] = chromium_path
        self._browser = self._pw.chromium.launch(**launch_kwargs)
        ctx = self._browser.new_context(
            viewport={"width": DECK_W, "height": DECK_H},
            device_scale_factor=DEVICE_SCALE,
            ignore_https_errors=True,
            bypass_csp=True,
        )
        self._page = ctx.new_page()
        self._page.set_default_timeout(GOTO_TIMEOUT_MS)
        self._page.on("console", self._on_console)
        self._page.on("pageerror", self._on_pageerror)

    def close(self) -> None:
        for closer in (lambda: self._browser.close(), lambda: self._pw.stop()):
            try:
                closer()
            except Exception:
                pass

    def _on_console(self, msg) -> None:
        try:
            if msg.type == "error":
                self._record_error(f"console: {msg.text[:300]}")
        except Exception:
            pass

    def _on_pageerror(self, exc) -> None:
        self._record_error(f"pageerror: {str(exc)[:300]}")

    def _record_error(self, text: str) -> None:
        if text not in self.console_errors and len(self.console_errors) < MAX_CONSOLE_ERRORS:
            self.console_errors.append(text)

    # ── 加载与导航 ───────────────────────────────────────────────────
    def _load(self, query: str = "") -> None:
        """加载 deck，不做长 settle（采样时序由 _sample_page 控制，否则 early 帧会错过入场动画）。"""
        url = self.html_path.resolve().as_uri() + query
        self._page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
        try:
            self._page.wait_for_load_state("networkidle", timeout=NETWORKIDLE_TIMEOUT_MS)
        except Exception:
            pass
        self._page.set_default_timeout(SCREENSHOT_TIMEOUT_MS)
        # 很多 deck 的 fitDeck()/相机只在 resize 时重排，载入即触发一次促其归位
        try:
            self._page.evaluate("() => window.dispatchEvent(new Event('resize'))")
        except Exception:
            pass

    def _grab(self) -> tuple[bytes, str, float, tuple]:
        png = self._page.screenshot(clip={"x": 0, "y": 0, "width": DECK_W, "height": DECK_H})
        sig = self._page.evaluate(_ACTIVE_SIGNAL_JS)
        std, blocks = _img_stats(png)
        return png, sig, std, blocks

    def _signal(self) -> tuple[int, int]:
        try:
            return _parse_sig(self._page.evaluate(_ACTIVE_SIGNAL_JS))
        except Exception:
            return -1, 0

    # ── 三帧采样（motion check）────────────────────────────────────────
    def _sample_page(self, already_waited_ms: int = 0) -> dict:
        """对"刚到达"的当前页采样。返回 {png, std, blocks, entrance_diff, live_diff}。

        already_waited_ms：调用前已经等过的时间（goto 的 settle / 翻页的 NAV_SETTLE）。
        无 motion-check 时只补足到 final 时刻截一帧。
        """
        if not self.motion_check:
            remain = max(0, EARLY_MS + FINAL_EXTRA_MS - already_waited_ms)
            self._page.wait_for_timeout(remain)
            png, _sig, std, blocks = self._grab()
            return {"png": png, "std": std, "blocks": blocks,
                    "entrance_cells": None, "live_cells": None}

        # early 帧（尽量贴近到达后 0.5s；已等超过就立刻采）
        self._page.wait_for_timeout(max(0, EARLY_MS - already_waited_ms))
        early_png = self._page.screenshot(clip={"x": 0, "y": 0, "width": DECK_W, "height": DECK_H})
        # final 帧（正式截图）
        self._page.wait_for_timeout(FINAL_EXTRA_MS)
        png, _sig, std, blocks = self._grab()
        # live 帧（探测持续动画）
        self._page.wait_for_timeout(LIVE_EXTRA_MS)
        live_png = self._page.screenshot(clip={"x": 0, "y": 0, "width": DECK_W, "height": DECK_H})
        final_m = _motion_blocks(png)
        return {
            "png": png, "std": std, "blocks": blocks,
            "entrance_cells": _moving_cells(_motion_blocks(early_png), final_m),
            "live_cells": _moving_cells(final_m, _motion_blocks(live_png)),
        }

    # ── 单页渲染（--page N）──────────────────────────────────────────
    def render_page(self, n: int) -> list[Path]:
        self.meta["mode"] = f"page:{n}"
        nav = "jump"
        self._load(f"?slide={n}")
        self._page.wait_for_timeout(250)  # 给导航控制器初始化/读 URL 参数留一点时间
        idx, total = self._signal()
        waited = 250
        if not (idx == n - 1 and total >= n):
            # 直跳没生效 → fallback：回首页按键翻过去
            nav = "keys-fallback"
            print(f"[nav] deck 未实现 ?slide=N 直跳契约（信号 idx={idx} total={total}，期望 {n - 1}）；"
                  f"已 fallback 按键翻页。请按 sn-ppt-dazzle 契约在导航控制器中支持 URL 参数 slide。",
                  file=sys.stderr)
            self._load()
            self._page.wait_for_timeout(SETTLE_MS)  # 首屏稳定后再开始翻
            for _ in range(n - 1):
                self._page.keyboard.press("ArrowRight")
                self._page.wait_for_timeout(NAV_SETTLE_MS)
            idx2, _total2 = self._signal()
            if idx2 >= 0 and idx2 != n - 1:
                print(f"[nav] fallback 翻页后信号 idx={idx2}，与目标页 {n - 1} 不符，截图可能不是第 {n} 页。",
                      file=sys.stderr)
            waited = NAV_SETTLE_MS if n > 1 else SETTLE_MS
        self.meta["nav"] = nav

        s = self._sample_page(already_waited_ms=waited)
        out = self.out_dir / f"page_{n:02d}.png"
        out.write_bytes(s["png"])
        self._add_page_meta(n, out, s)
        self.meta["n_pages"] = max(self.meta["n_pages"], n)
        return [out]

    # ── 全部页渲染（--all）───────────────────────────────────────────
    def render_all(self) -> list[Path]:
        self.meta["mode"] = "all"
        self._load()
        # 首页采样（early 帧从载入即开始计时，能捕捉到首页入场动画）
        samples: list[dict] = [self._sample_page(already_waited_ms=0)]
        idx0, total0 = self._signal()
        use_signal = idx0 >= 0 and total0 > 1
        self.meta["nav"] = "keys+signal" if use_signal else "keys+phash"
        # 收敛靠"循环检测(翻回已见页)+翻不动检测"，不用 total 作硬上界；MAX_PAGES 仅兜底
        seen_idx: set[int] = {idx0} if use_signal else set()
        seen_blocks: list[tuple] = [samples[0]["blocks"]]
        prev_idx = idx0
        prev_blocks = samples[0]["blocks"]

        while len(samples) < MAX_PAGES:
            advanced = False
            cur_sig = ""
            waited = 0
            for key in ("ArrowRight", "Space", "PageDown"):
                self._page.keyboard.press(key)
                if use_signal:
                    # class 在 keydown 里同步切换，早确认 → early 帧能捕捉快速入场动画
                    self._page.wait_for_timeout(NAV_CHECK_MS)
                    waited = NAV_CHECK_MS
                    cur_sig = self._page.evaluate(_ACTIVE_SIGNAL_JS)
                    ci = _parse_sig(cur_sig)[0]
                    if ci >= 0 and ci != prev_idx:
                        advanced = True
                        break
                else:
                    self._page.wait_for_timeout(NAV_SETTLE_MS)
                    waited = NAV_SETTLE_MS
                    cur_sig = self._page.evaluate(_ACTIVE_SIGNAL_JS)
                    quick = self._page.screenshot(
                        clip={"x": 0, "y": 0, "width": DECK_W, "height": DECK_H})
                    _, qb = _img_stats(quick)
                    if _block_diff(prev_blocks, qb) >= PHASH_SAME_THRESH:
                        advanced = True
                        break
            if not advanced:
                break  # 三个键都翻不动 → 尾页
            cur_idx = _parse_sig(cur_sig)[0]
            s = self._sample_page(already_waited_ms=waited)
            if use_signal:
                if cur_idx in seen_idx:
                    break  # 翻回已见页 → 循环 deck，停
                seen_idx.add(cur_idx)
                prev_idx = cur_idx
            else:
                if any(_block_diff(b, s["blocks"]) < PHASH_SAME_THRESH for b in seen_blocks):
                    break
                seen_blocks.append(s["blocks"])
            samples.append(s)
            prev_blocks = s["blocks"]

        # 落盘
        paths: list[Path] = []
        for i, s in enumerate(samples, start=1):
            out = self.out_dir / f"page_{i:02d}.png"
            out.write_bytes(s["png"])
            self._add_page_meta(i, out, s)
            paths.append(out)
        self.meta["n_pages"] = len(paths)
        if total0 > 1 and total0 != len(paths):
            self._note(f"sig_total={total0} != captured={len(paths)}")
        if len(paths) >= MAX_PAGES:
            self._note("hit_max_pages(nav_nonconverge)")
        # contact sheet（拼图，整 deck 一眼扫）
        sheet = self._contact_sheet(paths)
        if sheet:
            paths.append(sheet)
        return paths

    def _add_page_meta(self, n: int, png_path: Path, s: dict) -> None:
        self.rendered_this_run.add(n)
        blank = s["std"] < BLANK_STD_THRESH
        static = (
            s["entrance_cells"] is not None
            and 0 <= s["entrance_cells"] < MOTION_MIN_CELLS
            and 0 <= s["live_cells"] < MOTION_MIN_CELLS
        )
        self.meta["pages"].append({
            "page": n, "png": str(png_path), "blank": blank,
            "entrance_cells": s["entrance_cells"], "live_cells": s["live_cells"],
            "static": static,
        })
        if blank:
            self.meta["blank_pages"].append(n)
        if static:
            self.meta["static_pages"].append(n)

    def _contact_sheet(self, paths: list[Path]) -> Path | None:
        try:
            from PIL import Image, ImageDraw

            thumb_w, thumb_h = 320, 180
            cols = min(4, max(1, len(paths)))
            rows = math.ceil(len(paths) / cols)
            sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (24, 24, 24))
            draw = ImageDraw.Draw(sheet)
            for i, p in enumerate(paths):
                im = Image.open(p).convert("RGB").resize((thumb_w, thumb_h))
                x, y = (i % cols) * thumb_w, (i // cols) * thumb_h
                sheet.paste(im, (x, y))
                draw.rectangle([x, y, x + 34, y + 18], fill=(0, 0, 0))
                draw.text((x + 6, y + 3), f"{i + 1:02d}", fill=(255, 255, 255))
            out = self.out_dir / "contact_sheet.png"
            sheet.save(out)
            return out
        except Exception as e:  # noqa: BLE001
            self._note(f"contact_sheet failed: {type(e).__name__}")
            return None

    def _note(self, text: str) -> None:
        self.meta["notes"] = (self.meta["notes"] + "; " if self.meta["notes"] else "") + text

    # ── 收尾 ─────────────────────────────────────────────────────────
    def finalize(self) -> None:
        self.meta["console_errors"] = self.console_errors
        # --page 模式合并进已有 render.json（保留其他页的记录）；--all 整体覆盖
        manifest = self.out_dir / "render.json"
        if self.meta["mode"].startswith("page:") and manifest.exists():
            try:
                old = json.loads(manifest.read_text(encoding="utf-8"))
                kept = [p for p in old.get("pages", [])
                        if p["page"] not in {q["page"] for q in self.meta["pages"]}]
                self.meta["pages"] = sorted(kept + self.meta["pages"], key=lambda p: p["page"])
                self.meta["n_pages"] = max(self.meta["n_pages"], old.get("n_pages", 0))
                old_errs = [e for e in old.get("console_errors", []) if e not in self.console_errors]
                self.meta["console_errors"] = (old_errs + self.console_errors)[:MAX_CONSOLE_ERRORS]
                self.meta["blank_pages"] = sorted({p["page"] for p in self.meta["pages"] if p["blank"]})
                self.meta["static_pages"] = sorted(
                    {p["page"] for p in self.meta["pages"] if p.get("static")})
            except Exception:
                pass
        manifest.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    global MOTION_MIN_CELLS
    ap = argparse.ArgumentParser(description="渲染单 HTML deck 为逐页 PNG")
    ap.add_argument("deck", help="deck.html 路径")
    ap.add_argument("out_dir", help="截图输出目录（render.json 也写在这里）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--page", type=int, help="渲染第 N 页（1-based），优先 ?slide=N 直跳")
    g.add_argument("--all", action="store_true", help="按键翻页渲染全部页 + contact sheet")
    ap.add_argument("--no-motion-check", action="store_true", help="关闭三帧动态采样（更快）")
    ap.add_argument("--motion-min-cells", type=int, default=MOTION_MIN_CELLS,
                    help=f"变化格数 < 此值视为无运动（默认 {MOTION_MIN_CELLS}/4096）")
    args = ap.parse_args()
    MOTION_MIN_CELLS = args.motion_min_cells

    html_path = Path(args.deck)
    if not html_path.exists():
        print(f"deck 不存在: {html_path}", file=sys.stderr)
        return 2
    if args.page is not None and args.page < 1:
        print(f"--page 必须 >= 1，收到 {args.page}", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    r = DeckRenderer(html_path, out_dir, motion_check=not args.no_motion_check)
    try:
        r.start()
        paths = r.render_page(args.page) if args.page is not None else r.render_all()
    except Exception as e:  # noqa: BLE001
        print(f"渲染失败: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
        r.finalize()
        return 1
    finally:
        r.close()
    r.finalize()

    if not paths:
        print("一页都没截到（deck 打不开或无内容）", file=sys.stderr)
        return 1

    # 告警先打，PNG 路径在后（末行保证是路径）
    for err in r.console_errors:
        print(f"[console] {err}")
    for p in r.meta["pages"]:
        if p["page"] not in r.rendered_this_run:
            continue  # --page 模式下 render.json 合并了历史页，告警只报本次渲染的页
        if p.get("static"):
            print(f"[static] page {p['page']}: entrance_cells={p['entrance_cells']} "
                  f"live_cells={p['live_cells']} — 本页无可见动态（若是有意的静帧设计可忽略）")
        if p.get("blank"):
            print(f"[blank] page {p['page']}: 近纯色/空白页")
    for p in paths:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
