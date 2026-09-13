#!/usr/bin/env python3
"""
embed_chart_to_html.py — Chart.js 图块注入已有 HTML 报告
单一职责：把 chartjs-rendering 输出的图块注入到目标 HTML 的指定 slot。
处理 CDN 去重、chart_id 冲突避让。

用法:
  python3 embed_chart_to_html.py --target report.html --source chart_block.html --slot "#chart-area"
  python3 embed_chart_to_html.py --target report.html --source chart_block.html  # 追加到 </body> 前
  python3 embed_chart_to_html.py --target report.html --source chart_block.html --slot "<!-- CHART-SLOT -->"
"""
import argparse
import json
import os
import re
import sys


def _find_max_canvas_id(html: str) -> int:
    """扫描已有 canvas id="cN"，返回最大 N"""
    ids = re.findall(r'<canvas\s+[^>]*id="c(\d+)"', html)
    return max((int(i) for i in ids), default=0)


def _rewrite_ids(html: str, offset: int) -> str:
    """把 html 中所有 cN 的 id 和 getElementById 引用重编号"""
    def _replace_id(m):
        num = int(m.group(1))
        return m.group(0).replace(m.group(1), str(num + offset))

    html = re.sub(r'id="c(\d+)"', _replace_id, html)
    html = re.sub(r"getElementById\('c(\d+)'\)", _replace_id, html)
    return html


def _has_cdn(html: str) -> bool:
    """检查是否已有 Chart.js CDN"""
    return 'chart.js' in html or 'chart.umd.min.js' in html


def _extract_cdn(source_html: str) -> str:
    """从源 HTML 中提取 Chart.js CDN script 标签"""
    m = re.search(r'<script[^>]*src="[^"]*chart[^"]*\.js[^"]*"[^>]*></script>', source_html)
    return m.group(0) if m else ""


def inject_charts(target_path: str, source_path: str, slot: str = None) -> dict:
    """主入口：把 source 图块注入 target"""
    with open(target_path, "r", encoding="utf-8") as f:
        target_html = f.read()

    with open(source_path, "r", encoding="utf-8") as f:
        source_html = f.read()

    # 1. 处理 CDN
    cdn_src = _extract_cdn(source_html)
    need_cdn = cdn_src and not _has_cdn(target_html)
    if need_cdn:
        target_html = target_html.replace("<head>", f"<head>\n{cdn_src}")

    # 2. 检查 chart_id 冲突，重编号
    max_id = _find_max_canvas_id(target_html)
    if max_id > 0:
        source_html = _rewrite_ids(source_html, max_id)

    # 3. 定位 slot 并注入
    if slot:
        # 尝试 CSS 选择器
        slot_sel = slot.lstrip("#").lstrip(".")
        if slot.startswith("#"):
            # id 选择器
            pattern = rf'(<[^>]*\s+id="{slot_sel}"[^>]*>)'
            m = re.search(pattern, target_html)
            if m:
                target_html = target_html.replace(m.group(1), m.group(1) + "\n" + source_html, 1)
            else:
                slot = None  # 退到 body 前
        elif slot.startswith("<!--"):
            # 注释锚点
            if slot in target_html:
                target_html = target_html.replace(slot, slot + "\n" + source_html, 1)
            else:
                slot = None

    if not slot:
        # fallback: </body> 前
        target_html = target_html.replace("</body>", source_html + "\n</body>", 1)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(target_html)

    return {
        "status": "ok",
        "target": target_path,
        "cdn_injected": need_cdn,
        "id_offset": max_id,
        "slot_used": slot or "</body>",
    }


def main():
    parser = argparse.ArgumentParser(description="Chart.js 图块注入已有 HTML 报告")
    parser.add_argument("--target", required=True, help="目标 HTML 路径")
    parser.add_argument("--source", required=True, help="图块 HTML 路径（chartjs-rendering 输出）")
    parser.add_argument("--slot", default=None, help="注入位置（CSS 选择器或注释锚点）")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写")
    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(json.dumps({"status": "failed", "error": f"target not found: {args.target}"}))
        sys.exit(1)
    if not os.path.exists(args.source):
        print(json.dumps({"status": "failed", "error": f"source not found: {args.source}"}))
        sys.exit(1)

    if args.dry_run:
        with open(args.target, "r") as f:
            html = f.read()
        max_id = _find_max_canvas_id(html)
        print(json.dumps({
            "status": "dry_run",
            "has_cdn": _has_cdn(html),
            "max_canvas_id": max_id,
            "next_id_offset": max_id,
        }, ensure_ascii=False))
        sys.exit(0)

    result = inject_charts(args.target, args.source, args.slot)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()