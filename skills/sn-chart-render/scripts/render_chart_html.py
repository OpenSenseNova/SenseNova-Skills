#!/usr/bin/env python3
"""
render_chart_html.py — 数据 dict → Chart.js HTML 代码块
单一职责：接收结构化数据 dict，输出 `<canvas>` + `<script>` Chart.js 初始化代码。
不嵌入已有报告，不验证渲染结果。

用法:
  python3 render_chart_html.py --input data.json --output chart_block.html --template chart-only
  python3 render_chart_html.py --input data.json --output report.html --template standard-report
"""
import argparse
import json
import os
import sys
from datetime import datetime

CHART_CDN = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js'

PALETTES = {
    "default":   {"primary": "#0f766e", "secondary": "#00b894", "warn": "#e17055", "danger": "#d63031", "dark": "#155e75", "colors": ["#0f766e","#2563eb","#e17055","#00b894","#d63031","#0891b2","#7c3aed","#f59e0b"]},
    "catering":  {"primary": "#e17055", "secondary": "#00b894", "warn": "#e17055", "danger": "#d63031", "dark": "#c0392b", "colors": ["#e17055","#00b894","#d63031","#0984e3","#6c5ce7","#fdcb6e","#00cec9","#e84393"]},
    "retail":    {"primary": "#0984e3", "secondary": "#e17055", "warn": "#e17055", "danger": "#d63031", "dark": "#0652DD", "colors": ["#0984e3","#e17055","#00b894","#6c5ce7","#fdcb6e","#d63031","#00cec9","#e84393"]},
    "tech":      {"primary": "#6366f1", "secondary": "#14b8a6", "warn": "#f59e0b", "danger": "#ef4444", "dark": "#4f46e5", "colors": ["#6366f1","#14b8a6","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#f97316","#84cc16"]},
    "medical":   {"primary": "#0891b2", "secondary": "#84cc16", "warn": "#e11d48", "danger": "#b91c1c", "dark": "#0e7490", "colors": ["#0891b2","#84cc16","#e11d48","#14b8a6","#2563eb","#f59e0b","#8b5cf6","#64748b"]},
    "monochrome":{"primary": "#374151", "secondary": "#6b7280", "warn": "#9ca3af", "danger": "#4b5563", "dark": "#1f2937", "colors": ["#374151","#6b7280","#9ca3af","#d1d5db","#4b5563","#111827"]},
}


def _cycle_color(palette_name: str, idx: int) -> str:
    """从 palette 取色，超出循环"""
    palette = PALETTES.get(palette_name, PALETTES["default"])
    colors = palette["colors"]
    return colors[idx % len(colors)]


def _chart_js_code(chart: dict, palette_name: str) -> str:
    """生成单个图表的 Chart.js 初始化 script 代码"""
    chart_type = chart.get("type", "bar")
    labels = json.dumps(chart.get("labels", []), ensure_ascii=False)
    cid = chart.get("id", "c1")
    horizontal = chart.get("options", {}).get("horizontal", False)

    # 构造 datasets
    ds_list = []
    for i, ds in enumerate(chart.get("datasets", [])):
        color = ds.get("options", {}).get("backgroundColor") or _cycle_color(palette_name, i)
        entry = {
            "label": ds["label"],
            "data": ds["data"],
            "backgroundColor": color,
            "borderColor": color,
            "borderRadius": 4 if chart_type == "bar" else 0,
        }
        if ds.get("options", {}).get("fill"):
            entry["fill"] = True
            entry["backgroundColor"] = color + "20"
        if ds.get("options", {}).get("tension"):
            entry["tension"] = ds["options"]["tension"]
        if ds.get("options", {}).get("yAxisID"):
            entry["yAxisID"] = ds["options"]["yAxisID"]
        if chart_type == "radar":
            entry.pop("borderRadius", None)
        ds_list.append(entry)

    datasets_json = json.dumps(ds_list, ensure_ascii=False)

    # 饼图特殊处理：合并小项
    if chart_type in ("pie", "doughnut"):
        datasets_json = _merge_small_slices(datasets_json)

    type_str = 'bar' if horizontal else chart_type

    # 高度
    height = chart.get("options", {}).get("height", 200)

    script = f"""
<script>
(function(){{
  const c = document.getElementById('{cid}');
  if (!c) return;
  if (Chart.getChart('{cid}')) Chart.getChart('{cid}').destroy();
  new Chart(c, {{
    type: '{type_str}',
    data: {{ labels: {labels}, datasets: {datasets_json} }},
    options: {json.dumps(_chart_options(chart, palette_name), ensure_ascii=False)}
  }});
}})();
</script>"""

    return script


def _chart_options(chart: dict, palette_name: str) -> dict:
    """生成 Chart.js options dict"""
    palette = PALETTES.get(palette_name, PALETTES["default"])
    opts = {
        "responsive": True,
        "maintainAspectRatio": False,
        "plugins": {"legend": {"position": "top"}},
    }
    if chart.get("options", {}).get("stacked"):
        opts["scales"] = {
            "x": {"stacked": True},
            "y": {"stacked": True, "beginAtZero": True},
        }

    if chart.get("type") == "radar":
        opts["scales"] = {"r": {"beginAtZero": True, "pointLabels": {"font": {"size": 11}}}}

    if chart.get("type") in ("doughnut", "pie"):
        opts["plugins"]["legend"]["labels"] = {"maxWidth": 80}

    return opts


def _merge_small_slices(datasets_json: str) -> str:
    """饼图小项合并（通过 Python 数据层做）"""
    ds = json.loads(datasets_json)
    for d in ds:
        data = d.get("data", [])
        labels_raw = d.get("_labels", [])
        if len(data) > 10:
            total = sum(data)
            keep = []
            other_sum = 0
            for i, v in enumerate(data):
                if total > 0 and (v / total) >= 0.02:
                    keep.append((i, v))
                else:
                    other_sum += v
            new_data = [v for _, v in keep]
            if other_sum > 0:
                new_data.append(other_sum)
            d["data"] = new_data
    return json.dumps(ds, ensure_ascii=False)


def render_charts_html(data: dict) -> str:
    """主入口：data dict → Chart.js HTML 代码块"""
    palette_name = data.get("palette", "default")
    charts = data.get("charts", [])
    if not charts:
        return "<!-- no charts to render -->"

    parts = [f'<script src="{CHART_CDN}"></script>']
    for i, chart in enumerate(charts):
        chart.setdefault("id", f"c{i+1}")
        canvas = f'<canvas id="{chart["id"]}" height="{chart.get("options", {}).get("height", 200)}"></canvas>'
        script = _chart_js_code(chart, palette_name)
        note = chart.get("note", "")
        note_html = f'<div class="chart-note">{note}</div>' if note else ""
        parts.append(f'<!-- chart:{chart["id"]} -->\n{canvas}\n{script}\n{note_html}\n<!-- /chart:{chart["id"]} -->')

    return "\n".join(parts)


def render_full_report(data: dict) -> str:
    """生成完整 HTML 报告（含 header/kpi/图表/表格/findings）"""
    palette = PALETTES.get(data.get("palette", "default"), PALETTES["default"])

    title = data.get("title", "分析报告")
    subtitle = data.get("subtitle", f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    summary_items = data.get("summary_items", [])
    sections = data.get("sections", [])

    # 渲染 sections 中的 charts
    for sec in sections:
        for chart in sec.get("charts", []):
            chart["html"] = _chart_js_code(chart, data.get("palette", "default"))

    # 拼 CSS（palette 变量替换）
    css = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif;background:#f5f6fa;color:#2d3436;line-height:1.7}}
.header{{background:linear-gradient(135deg,{palette['primary']},{palette['dark']});color:#fff;padding:48px 0;text-align:center}}
.header h1{{font-size:28px;font-weight:700;margin-bottom:8px}}
.header p{{opacity:.85;font-size:14px}}
.container{{max-width:960px;margin:0 auto;padding:20px}}
.card{{background:#fff;border-radius:12px;padding:24px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,0.06)}}
.card h2{{font-size:18px;color:{palette['primary']};border-left:4px solid {palette['primary']};padding-left:12px;margin-bottom:16px}}
.card h3{{font-size:15px;color:#636e72;margin:12px 0 8px}}
.chart-row{{display:flex;flex-wrap:wrap;gap:16px;margin:16px 0}}
.chart-box{{flex:1;min-width:280px;height:260px;position:relative}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}}
th{{background:#f8f9fa;color:#636e72;font-weight:600;padding:8px 10px;border-bottom:2px solid #dfe6e9}}
td{{padding:7px 10px;border-bottom:1px solid #f1f2f6}}
tr:hover td{{background:#f8f9fa}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:16px 0}}
.summary-item{{background:#f8f9fa;border-radius:8px;padding:14px;text-align:center}}
.summary-item .num{{font-size:22px;font-weight:700;color:{palette['primary']}}}
.summary-item .label{{font-size:11px;color:#636e72;margin-top:4px}}
.insight{{background:#fff3e0;border-radius:8px;padding:14px;margin:10px 0;border-left:4px solid {palette['warn']}}}
.insight h4{{color:{palette['warn']};font-size:13px;margin-bottom:4px}}
.suggestion{{background:#e8f5e9;border-radius:8px;padding:14px;margin:10px 0;border-left:4px solid {palette['secondary']}}}
.suggestion h4{{color:{palette['secondary']};font-size:13px;margin-bottom:4px}}
.risk{{background:#ffebee;border-radius:8px;padding:14px;margin:10px 0;border-left:4px solid {palette['danger']}}}
.risk h4{{color:{palette['danger']};font-size:13px;margin-bottom:4px}}
.ft{{text-align:center;color:#636e72;font-size:11px;padding:24px 0}}
.chart-note{{font-size:11px;color:#b2bec3;text-align:center;margin-top:-8px;margin-bottom:12px}}
.tag{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600}}
.tag.green{{background:#00b89420;color:#00b894}}
.tag.orange{{background:{palette['warn']}20;color:{palette['warn']}}}
.tag.red{{background:{palette['danger']}20;color:{palette['danger']}}}
.tag.blue{{background:#0984e320;color:#0984e3}}
"""

    # 拼 KPI 网格
    kpi_html = ""
    if summary_items:
        cards = "".join(
            f'<div class="summary-item"><div class="num">{i["value"]}</div><div class="label">{i["label"]}</div></div>'
            for i in summary_items
        )
        kpi_html = f'<div class="card"><h2>关键指标</h2><div class="summary-grid">{cards}</div></div>'

    # 拼 sections
    sections_html = ""
    for sec in sections:
        sec_title = sec.get("title", "")
        sec_desc = sec.get("description", "")
        sec_desc_html = f'<p style="color:#636e72;font-size:13px;margin-bottom:12px">{sec_desc}</p>' if sec_desc else ""

        # charts
        charts_html = ""
        if sec.get("charts"):
            chart_boxes = "".join(
                f'<div class="chart-box">{ch.get("html","")}'
                + (f'<div class="chart-note">{ch["note"]}</div>' if ch.get("note") else "")
                + "</div>"
                for ch in sec["charts"]
            )
            charts_html = f'<div class="chart-row">{chart_boxes}</div>'

        # table
        table_html = ""
        if sec.get("table"):
            tbl = sec["table"]
            headers = "".join(f"<th>{h}</th>" for h in tbl.get("headers", []))
            rows = "".join(
                "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
                for row in tbl.get("rows", [])
            )
            thead = f"<thead><tr>{headers}</tr></thead>" if headers else ""
            table_html = f"<table>{thead}<tbody>{rows}</tbody></table>"

        # findings
        findings_html = ""
        for f in sec.get("findings", []):
            cls = f.get("type", "insight")
            findings_html += f'<div class="{cls}"><h4>{f["title"]}</h4><p>{f.get("content","")}</p></div>'

        sections_html += f"""
<div class="card">
<h2>{sec_title}</h2>
{sec_desc_html}
{charts_html}
{table_html}
{findings_html}
</div>"""

    # chart CDN
    chart_cdn = f'<script src="{CHART_CDN}"></script>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{css}</style>
{chart_cdn}
</head>
<body>
<div class="header">
<h1>{title}</h1>
<p>{subtitle}</p>
</div>
<div class="container">
{kpi_html}
{sections_html}
<div class="ft"><p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p></div>
</div>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="数据 dict → Chart.js HTML 代码块")
    parser.add_argument("--input", required=True, help="JSON 数据文件路径")
    parser.add_argument("--output", required=True, help="输出 HTML 文件路径")
    parser.add_argument("--template", choices=["chart-only", "standard-report"], default="chart-only",
                        help="chart-only: 纯图块注入; standard-report: 完整报告页")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.template == "chart-only":
        html = render_charts_html(data)
    else:
        html = render_full_report(data)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(json.dumps({"status": "ok", "output": args.output}, ensure_ascii=False))


if __name__ == "__main__":
    main()