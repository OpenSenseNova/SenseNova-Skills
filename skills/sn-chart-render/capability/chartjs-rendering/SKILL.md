---
name: chartjs-rendering
description: 把结构化数据渲染成 Chart.js HTML 代码块。接收 data dict → 输出 `<canvas>` + `<script>` Chart.js 初始化代码。不负责嵌入已有报告或验证渲染结果。
tier: 2
category: ability
parent: sn-chart-render
---

# chartjs-rendering — Chart.js 渲染能力

## 行为边界

做：

- 把结构化数据 dict 渲染为 Chart.js 初始化脚本
- 支持 bar / line / pie / doughnut / radar / mixed（bar+line）
- 自动分配配色（支持 palette 参数切换色系）
- 自动生成 chart_id（c1, c2, c3...），不存在冲突
- 输出格式：纯 HTML 代码块（`<canvas id="cN" height="N"></canvas>` + `<script>new Chart(...)</script>`）

不做：

- 不选择图表类型（编排器通过 chart-type-selection.md 决策后传入 type）
- 不生成完整 HTML 页（嵌入层做那个）
- 不验证渲染结果（chart-validation 做）
- 不做数据清洗
- 不处理离线 CDN 打包

## 输入

接收一个 dict：

```python
{
    "charts": [
        {
            "id": "c1",               # 可选，自动生成
            "type": "bar",             # bar | line | pie | doughnut | radar | mixed
            "title": "月度营收趋势",    # 图标题，可选
            "labels": ["1月", "2月", "3月"],
            "datasets": [
                {
                    "label": "营收（万元）",
                    "data": [5567, 4187, 3818],
                    "options": {}       # 数据集级别选项，如 backgroundColor
                },
                {
                    "label": "利润（万元）",
                    "data": [1200, 980, 756],
                    "options": {"yAxisID": "y1"}  # 次坐标轴
                }
            ],
            "options": {               # 图表级别选项
                "palette": "default",  # default | catering | retail | tech | medical | monochrome
                "stacked": false,
                "horizontal": false
            },
            "note": "数据来源：财务系统"
        }
    ],
    "chart_cdn": "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"
}
```

## 输出

Chart.js HTML 代码块：

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<canvas id="c1" height="200"></canvas>
<script>
new Chart(document.getElementById('c1'), {
  type: 'bar',
  data: { labels: ['1月','2月','3月'], datasets: [{ label: '营收（万元）', data: [5567,4187,3818], backgroundColor: '#e17055', borderRadius: 4 }] },
  options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } } }
});
</script>
```

## 配色方案

| palette | 主色 | 辅助色 | 警告色 | 适用 |
|---------|------|--------|--------|------|
| default | #0f766e (青绿) | #2563eb (蓝) | #c2410c (橙) | 通用 |
| catering | #e17055 (橙红) | #00b894 (绿) | #d63031 (红) | 餐饮业 |
| retail | #0984e3 (蓝) | #e17055 (橙) | #d63031 (红) | 零售业 |
| tech | #6366f1 (紫蓝) | #14b8a6 (青) | #f59e0b (金) | 科技/互联网 |
| medical | #0891b2 (深青) | #84cc16 (草绿) | #e11d48 (红) | 医疗/健康 |
| monochrome | #374151 (灰) | #6b7280 | #9ca3af | 打印/黑白 |

数据集超过 4 个时，从 palette 的主色循环取色。

## 调用方式

```python
from hermes_tools import terminal

# 生成 chart HTML 块
result = terminal(
    f"python3 {SKILL_DIR}/scripts/render_chart_html.py "
    f"--input /tmp/chart_data.json "
    f"--output /tmp/chart_block.html "
    f"--template chart-only"
)
```

或通过 capabilty 读取本 SKILL.md 中的代码模式手动生成。

## 数据点限制

| chart type | 推荐上限 | 超过后的处理 |
|-----------|---------|-------------|
| bar | 50 | 超过 50 改为 horizontalBar |
| line | 200 | 建议降采样或改为移动平均 |
| pie/doughnut | 10 | 合并 < 2% 为"其他" |
| radar | 15 | 超过分两组 radar 对比 |
| mixed | 50 | 超过拆为两个独立 chart |

## 常见失败

- `backgroundColor` 用 `fill: false` 时误写 → line 图不显色：检查填充模式
- labels 过长（> 15 字）：`plugins.legend.labels.maxWidth` 或截断
- 饼图数据含 0 值：filter `value > 0` 再渲染
- 负值被误用 doughnut → 自动回退到 bar
- 同一个 `canvas.id` 被重复 init → 先 `Chart.getChart('c1')?.destroy()`
