#!/usr/bin/env python3
"""
validate_chart_rendering.py — Playwright 验证 Chart.js 渲染
打开 HTML 文件 → 检查每个 canvas 的 Chart.js 实例 → 收集 console 错误
→ 输出 JSON 验证报告。

用法:
  python3 validate_chart_rendering.py --input report.html --output validation.json
  python3 validate_chart_rendering.py --input report.html  # stdout
"""
import argparse
import json
import os
import subprocess
import sys
import time


def _check_playwright():
    """检查 Playwright 是否可用"""
    try:
        r = subprocess.run(["playwright", "--version"], capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def validate_html(html_path: str, timeout_ms: int = 30000, viewport: str = "1280x800") -> dict:
    """用 Playwright 验证 HTML 中的 Chart.js 渲染"""
    if not _check_playwright():
        return {"status": "failed", "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

    # 用 Python Playwright API
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "failed", "error": "playwright Python package not installed"}

    abspath = os.path.abspath(html_path)
    if not os.path.exists(abspath):
        return {"status": "failed", "error": f"file not found: {abspath}"}

    vp = viewport.split("x")
    vp_w, vp_h = int(vp[0]), int(vp[1])

    start = time.time()
    result = {
        "status": "passed",
        "file": abspath,
        "viewport": viewport,
        "canvas_count": 0,
        "charts": [],
        "console_errors": [],
        "font_issues": [],
        "elapsed_ms": 0,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": vp_w, "height": vp_h})
        console_msgs = []
        page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text}))

        page.goto(f"file://{abspath}", wait_until="networkidle", timeout=timeout_ms)

        # 等待 Chart.js 有时间渲染
        page.wait_for_timeout(2000)

        # 检查 canvas
        charts_data = page.evaluate("""() => {
            const canvases = document.querySelectorAll('canvas');
            const results = [];
            for (const c of canvases) {
                const id = c.id;
                let chartInfo = null;
                try {
                    if (typeof Chart !== 'undefined') {
                        const chart = Chart.getChart(id);
                        if (chart) {
                            chartInfo = {
                                type: chart.config.type || chart.config.data?.type,
                                initialized: true,
                                data_points: chart.data.datasets.reduce((s, ds) => s + (ds.data?.length || 0), 0),
                            };
                        }
                    }
                } catch(e) {}
                results.push({
                    id: id || '(no-id)',
                    exists: !!c,
                    height_px: c.height,
                    width_px: c.width,
                    visible: c.offsetParent !== null,
                    chartjs: chartInfo || { initialized: false },
                });
            }
            return results;
        }""")

        # 中文字体检查
        font_issues = page.evaluate("""() => {
            const issues = [];
            const canvases = document.querySelectorAll('canvas');
            for (const c of canvases) {
                try {
                    const ctx = c.getContext('2d');
                    if (!ctx) continue;
                    ctx.font = '14px sans-serif';
                    const m = ctx.measureText('中文测试');
                    // 如果 width < 28px（14px*2个汉字），可能缺字
                    if (m.width < 20) {
                        issues.push({ canvas: c.id, measure_width: m.width, expected_min: 28 });
                    }
                } catch(e) {}
            }
            return issues;
        }""")

        result["charts"] = charts_data
        result["font_issues"] = font_issues

        # 过滤 console 错误
        errors = [m for m in console_msgs if m["type"] in ("error", "warning")]
        result["console_errors"] = errors

        # 总体状态
        all_initialized = all(ch.get("chartjs", {}).get("initialized", False) for ch in charts_data)
        has_errors = len(errors) > 0
        has_font = len(font_issues) > 0

        if not charts_data:
            result["status"] = "failed"
            result["reason"] = "no canvas elements found"
        elif not all_initialized:
            result["status"] = "partial"
            result["reason"] = "some charts not initialized"
        elif has_errors:
            result["status"] = "partial"
            result["reason"] = f"{len(errors)} console errors"
        elif has_font:
            result["status"] = "partial"
            result["reason"] = "font rendering issues detected"
        else:
            result["status"] = "passed"

        result["canvas_count"] = len(charts_data)
        browser.close()

    result["elapsed_ms"] = int((time.time() - start) * 1000)
    return result


def main():
    parser = argparse.ArgumentParser(description="Chart.js 渲染验证器")
    parser.add_argument("--input", required=True, help="HTML 文件路径")
    parser.add_argument("--output", default=None, help="验证结果 JSON 路径（默认 stdout）")
    parser.add_argument("--timeout", type=int, default=30000, help="Playwright 超时 ms")
    parser.add_argument("--viewport", default="1280x800", help="浏览器视口，如 1280x800")
    args = parser.parse_args()

    result = validate_html(args.input, args.timeout, args.viewport)
    output_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
    else:
        print(output_json)

    if result["status"] != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()