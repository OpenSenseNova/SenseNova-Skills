#!/usr/bin/env python3
"""SVG 图表生成助手（纯 Python，零外部依赖）。

用法：设计好候选人数据后直接调用 build_* 函数，输出 SVG 文本写到
prediction-reports/assets/ 即可。Markdown 里用相对路径引用。

已验证（2026-08 金球奖报告交付成功）：
- chart1_rating_bars：独立评分排名条形图
- chart2_model_vs_market：自研模型 vs 市场概率对比（双条对）
- chart3_radar：Top-N 候选多维雷达图
- chart4_market_history：预测市场随时间的价格动态
- chart5_data_table：候选人关键战绩表格

环境依赖提示：不要 import matplotlib / PIL / numpy。matplotlib 冷启动
导入在本机耗时 >60 秒会直接超时。纯字符串拼 SVG 更稳，且输出体积小。
"""
from __future__ import annotations

import os, math

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#39;"))

def _open(w: int, h: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n'

def _close() -> str:
    return '</svg>\n'

def _bg_fill(W: int, H: int, bg: str = "#0d1117", title: str = "", subtitle: str = "") -> str:
    s = f'<rect width="{W}" height="{H}" fill="{bg}"/>'
    if title:
        s += f'<text x="20" y="35" fill="#f0f6fc" font-size="20" font-weight="bold">{esc(title)}</text>'
    if subtitle:
        s += f'<text x="20" y="58" fill="#8b949e" font-size="13">{esc(subtitle)}</text>'
    return s

# 暗色主题配色（与 GitHub/DarkViz 一致）
COLORS = ["#1f6feb", "#5614e6", "#f0883e", "#3fb950", "#e3b341",
          "#f85149", "#d29922", "#8b949e", "#bc8cff", "#39c5cf"]


def chart_rating_bars(candidates: list[tuple[str, float]], title: str,
                      subtitle: str, max_scale: float | None = None,
                      W: int = 900, H: int = 520) -> str:
    """条形图。candidates: [(label, score_0_to_10), ...]"""
    s = _open(W, H) + _bg_fill(W, H, title=title, subtitle=subtitle)
    plot_x, plot_y = 60, 100
    plot_w, plot_h = W - 80, H - 140
    peak = max_scale or max(c[1] for c in candidates)
    n = len(candidates)
    bar_w = plot_w / n * 0.7
    gap = plot_w / n
    # 网格
    for g in range(0, 11):
        yy = plot_y + plot_h - (g / 10) * plot_h
        s += (f'<line x1="{plot_x}" y1="{yy:.1f}" x2="{plot_x + plot_w}" y2="{yy:.1f}" '
              f'stroke="#21262d" stroke-width="1"/>')
        s += f'<text x="{plot_x - 8}" y="{yy + 4:.1f}" fill="#8b949e" font-size="11" text-anchor="end">{g * 10}</text>'
    for i, (name, score) in enumerate(candidates):
        bx = plot_x + i * gap + (bar_w * 0.15)
        bh = (score / peak) * plot_h
        by = plot_y + plot_h - bh
        color = COLORS[i % len(COLORS)]
        s += (f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
              f'fill="{color}" rx="3" opacity="0.9"/>')
        s += (f'<text x="{bx + bar_w / 2:.1f}" y="{by - 8:.1f}" fill="#f0f6fc" '
              f'font-size="14" font-weight="bold" text-anchor="middle">{score:.2f}</text>')
        # 名字斜放避免重叠
        short = name.split(" (")[0]
        ly = plot_y + plot_h + 2 + i * (plot_h / n)
        s += (f'<text x="{bx + bar_w / 2 + 10:.1f}" y="{ly:.1f}" fill="#c9d1d9" font-size="13" '
              f'transform="rotate(28,{bx + bar_w / 2 + 10:.1f},{ly:.1f})">{esc(short)}</text>')
    s += f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" '
    s += f'stroke="#30363d" stroke-width="2"/>{_close()}'
    return s


def chart_model_vs_market(pairs: list[tuple[str, float, float]], title: str,
                          subtitle: str, W: int = 900, H: int = 520) -> str:
    """双条对比图。pairs: [(name, model_prob_pct, market_prob_pct)]"""
    s = _open(W, H) + _bg_fill(W, H, title=title, subtitle=subtitle)
    plot_x, plot_y = 130, 80
    plot_w, plot_h = W - 150, H - 140
    n = len(pairs)
    row_h = plot_h / n
    for pct in [0, 10, 20, 30, 40, 50, 60]:
        xx = plot_x + (pct / 60) * plot_w
        s += f'<line x1="{xx:.1f}" y1="{plot_y}" x2="{xx:.1f}" y2="{plot_y + plot_h}" stroke="#21262d" stroke-width="1"/>'
        s += f'<text x="{xx:.1f}" y="{plot_y + plot_h + 15}" fill="#8b949e" font-size="10" text-anchor="middle">{pct}%</text>'
    for i, (name, model_pct, mkt_pct) in enumerate(pairs):
        by = plot_y + i * row_h + row_h * 0.2
        bar_h = row_h * 0.6
        bw_m = (model_pct / 60) * plot_w
        bw_k = (mkt_pct / 60) * plot_w
        s += f'<rect x="{plot_x}" y="{by:.1f}" width="{bw_m:.1f}" height="{bar_h / 2:.1f}" fill="#1f6feb" rx="3"/>'
        s += f'<rect x="{plot_x}" y="{by + bar_h / 2:.1f}" width="{bw_k:.1f}" height="{bar_h / 2:.1f}" fill="#f85149" rx="3"/>'
        s += f'<text x="{plot_x + bw_m + 6:.1f}" y="{by + bar_h - 2:.1f}" fill="#58a6ff" font-size="11" font-weight="bold">{model_pct:.1f}%</text>'
        s += f'<text x="{plot_x + bw_k + 6:.1f}" y="{by + bar_h - 14:.1f}" fill="#ffa198" font-size="11" font-weight="bold">{mkt_pct:.1f}%</text>'
        s += f'<text x="{plot_x - 8}" y="{by + bar_h - 4:.1f}" fill="#c9d1d9" font-size="12" text-anchor="end">{esc(name)}</text>'
    # 图例
    for ii, (lbl, col) in enumerate([("独立预测概率", "#1f6feb"), ("Market 市场", "#f85149")]):
        lx = plot_x; ly = plot_y - 22 + ii * 16
        s += f'<rect x="{lx}" y="{ly}" width="12" height="12" fill="{col}"/>'
        s += f'<text x="{lx + 18}" y="{ly + 11}" fill="#c9d1d9" font-size="12">{lbl}</text>'
    s += _close()
    return s


def chart_radar(candidates: list[tuple[str, list[float], str]], dims: list[str],
                title: str, subtitle: str = "", W: int = 800, H: int = 700) -> str:
    """雷达图。candidates: [(name, values[0..10], hexcolor)]"""
    if len(dims) not in (4, 5, 6):
        raise ValueError("雷达图支 4/5/6 维")
    cx, cy = 230, 320
    R = 190
    step = 360 / len(dims)
    angles = [math.radians(-90 + i * step) for i in range(len(dims))]
    s = _open(W, H)
    s += f'<rect width="{W}" height="{H}" fill="#0d1117"/>'
    s += f'<text x="{W / 2}" y="30" fill="#f0f6fc" font-size="20" font-weight="bold" text-anchor="middle">{esc(title)}</text>'
    if subtitle:
        s += f'<text x="{W / 2}" y="52" fill="#8b949e" font-size="13" text-anchor="middle">{esc(subtitle)}</text>'
    for level in range(1, 6):
        r = R * level / 5
        pts = [f"{(cx + r * math.cos(a)):.1f},{(cy + r * math.sin(a)):.1f}" for a in angles]
        s += f'<polygon points="{" ".join(pts)}" fill="none" stroke="#21262d" stroke-width="1"/>'
    for a, dim in zip(angles, dims):
        s += f'<line x1="{cx}" y1="{cy}" x2="{cx + R * math.cos(a):.1f}" y2="{cy + R * math.sin(a):.1f}" stroke="#21262d" stroke-width="1"/>'
        s += f'<text x="{cx + (R + 30) * math.cos(a):.1f}" y="{cy + (R + 12) * math.sin(a):.1f}" fill="#c9d1d9" font-size="13" font-weight="bold" text-anchor="middle">{esc(dim)}</text>'
    for name, vals, color in candidates:
        pts = [f"{(cx + R * v / 10 * math.cos(a)):.1f},{(cy + R * v / 10 * math.sin(a)):.1f}"
               for v, a in zip(vals, angles)]
        s += f'<polygon points="{" ".join(pts)}" fill="{color}" opacity="0.18" stroke="{color}" stroke-width="2"/>'
        for v, a in zip(vals, angles):
            s += f'<circle cx="{cx + R * v / 10 * math.cos(a):.1f}" cy="{cy + R * v / 10 * math.sin(a):.1f}" r="4" fill="{color}"/>'
    lx, ly = 540, 100
    for name, _, color in candidates:
        s += f'<circle cx="{lx + 5}" cy="{ly + 5}" r="6" fill="{color}" opacity="0.7"/>'
        s += f'<text x="{lx + 18}" y="{ly + 9}" fill="#c9d1d9" font-size="13">{esc(name)}</text>'
        ly += 24
    s += _close()
    return s


def chart_history(series: list[tuple[str, str, list[float]]], x_labels: list[str],
                  title: str, subtitle: str = "", y_max: float = 70, y_step: float = 10,
                  W: int = 900, H: int = 500) -> str:
    """折线图。series: [(name, hexcolor, values_pct)]"""
    s = _open(W, H)
    s += f'<rect width="{W}" height="{H}" fill="#0d1117"/>'
    s += f'<text x="20" y="35" fill="#f0f6fc" font-size="20" font-weight="bold">{esc(title)}</text>'
    if subtitle:
        s += f'<text x="20" y="58" fill="#8b949e" font-size="13">{esc(subtitle)}</text>'
    plot_x, plot_y = 80, 90
    plot_w, plot_h = W - 120, H - 130
    n_x = len(x_labels) - 1
    for i, lbl in enumerate(x_labels):
        xx = plot_x + (i / n_x) * plot_w
        s += f'<line x1="{xx:.1f}" y1="{plot_y}" x2="{xx:.1f}" y2="{plot_y + plot_h}" stroke="#21262d" stroke-width="1"/>'
        for li, ln in enumerate(lbl.split("\n")):
            s += f'<text x="{xx:.1f}" y="{plot_y + plot_h + 20 + li * 14}" fill="#8b949e" font-size="11" text-anchor="middle">{ln}</text>'
    for pct in range(0, int(y_max) + 1, y_step):
        yy = plot_y + plot_h - (pct / y_max) * plot_h
        s += f'<text x="{plot_x - 10:.1f}" y="{yy + 4:.1f}" fill="#8b949e" font-size="11" text-anchor="end">{pct}%</text>'
        s += f'<line x1="{plot_x - 4:.1f}" y1="{yy:.1f}" x2="{plot_x}" y2="{yy:.1f}" stroke="#30363d" stroke-width="1"/>'
    for name, color, vals in series:
        pts = []
        for i, v in enumerate(vals):
            xx = plot_x + (i / n_x) * plot_w
            yy = plot_y + plot_h - (v / y_max) * plot_h
            pts.append(f"{xx:.1f},{yy:.1f}")
            s += f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="3.5" fill="{color}"/>'
        s += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.5" opacity="0.9"/>'
        last = pts[-1].split(",")
        s += f'<text x="{float(last[0]) + 6:.1f}" y="{float(last[1]) + 4:.1f}" fill="{color}" font-size="12" font-weight="bold">{esc(name)}</text>'
    s += _close()
    return s


def chart_data_table(rows: list[list[str]], title: str, subtitle: str = "",
                     headers: list[str] | None = None, W: int = 1000, H: int = 420) -> str:
    """表格图。rows 首行为非空时忽略 headers，直接用 rows[0] 当表头。"""
    if headers is None:
        headers = rows[0]
        rows = rows[1:]
    col_ws = [max(len(str(h)) * 9, 70) for h in headers]
    total_w = sum(col_ws) + 40
    actual_W = max(W, total_w)
    actual_H = H
    s = _open(actual_W, actual_H)
    s += f'<rect width="{actual_W}" height="{actual_H}" fill="#0d1117"/>'
    s += f'<text x="20" y="32" fill="#f0f6fc" font-size="20" font-weight="bold">{esc(title)}</text>'
    if subtitle:
        s += f'<text x="20" y="55" fill="#8b949e" font-size="13">{esc(subtitle)}</text>'
    row_y_base = 80
    row_h = 26
    x = 20
    for h, w in zip(headers, col_ws):
        s += f'<rect x="{x}" y="{row_y_base - 28}" width="{w}" height="28" fill="#21262d" stroke="#30363d"/>'
        s += f'<text x="{x + 8}" y="{row_y_base - 10}" fill="#f0f6fc" font-size="13" font-weight="bold">{esc(str(h))}</text>'
        x += w
    for r, row in enumerate(rows):
        yy = row_y_base + r * row_h
        if r % 2 == 0:
            s += f'<rect x="20" y="{yy}" width="{actual_W - 40}" height="{row_h}" fill="#161b22" opacity="0.6"/>'
        x = 20
        for ci, val in enumerate(row):
            weight = "bold" if ci == 0 else "normal"
            fill = "#f0f6fc" if ci == 0 else "#c9d1d9"
            s += f'<text x="{x + 8}" y="{yy + 18}" fill="{fill}" font-size="12" font-weight="{weight}">{esc(str(val))}</text>'
            x += col_ws[ci]
    s += _close()
    return s


def write_all(outdir: str, charts: dict[str, str]) -> list[str]:
    """批量写盘。返回成功写入的文件名。"""
    os.makedirs(outdir, exist_ok=True)
    written = []
    for fname, content in charts.items():
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as f:
            f.write(content)
        written.append(fname)
    return written


# -------- 快速自检脚本（可直接 python3 charts_svg.py 运行） --------
if __name__ == "__main__":
    demo_candidates = [("Player A", 8.8), ("Player B", 8.2), ("Player C", 7.5)]
    s1 = chart_rating_bars(demo_candidates, "演示条形图", "demo")
    s3 = chart_radar(
        [("A", [8, 8, 9, 7, 8], "#1f6feb"), ("B", [7, 6, 8, 9, 7], "#f0883e")],
        ["个表", "状态", "球队", "国家", "市场"], "演示雷达")
    s4 = chart_history(
        [("Kane", "#3fb950", [47, 45, 42, 16, 15, 59, 61]),
         ("Yamal", "#f85149", [15, 18, 25, 30, 33, 20, 15])],
        ["6月", "6月中", "7月初", "半决赛", "决赛", "7月底", "8月"], "演示折线")
    s5 = chart_data_table(
        [["候选人", "分", "进球", "荣誉"], ["Rodri", "8.88", "11", "世界杯+金球"]],
        "演示表格")
    for i, s in enumerate([s1, s3, s4, s5]):
        assert s.startswith("<svg") and s.rstrip().endswith("</svg>"), f"chart {i} 异常"
    print("✅ 全部示例 SVG 渲染通过")
