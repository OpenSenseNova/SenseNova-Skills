---
name: sn-chart-render
description: |-
  数据图表的编排器。接收分析结果（DataFrame/dict）→ 选图表类型 → 渲染 Chart.js HTML → 嵌入已有报告 → Playwright 验证渲染。
  覆盖三类场景：①生成含图表的独立 HTML 报告（从数据分析结果直接出页）；②在已有 HTML 报告的指定位置注入图表；
  ③对生成的图表做渲染验证（CDN、canvas 实例、中文字体）。
  本 skill 是编排器，不自己写 Chart.js 初始化脚本。具体渲染能力由 capability sub-skill 提供。
metadata:
  project: SenseNova-Skills
  tier: 1
  category: data-analysis
  user_visible: true
triggers:
  - "渲染图表"
  - "图表报告"
  - "生成可视化报告"
  - "数据可视化"
  - "插入图表"
  - "图表注入"
  - "data visualization"
  - "chart rendering"
  - "sn-chart-render"
---

# sn-chart-render — 图表渲染编排器

接收数据分析结果 → 渲染 Chart.js → 嵌入/验证 → 交付产物。

## 产物链

```
data (DataFrame / dict)
  → render_chart_html.py (渲染)
  → 〈chart HTML 块〉
    → embed_chart_to_html.py (嵌入已有报告)
    → validate_chart_rendering.py (Playwright 验证)
      → 最终 HTML 报告
```

所有中间产物都是文件和可执行命令。没有"先做图表，等会再嵌入"的对话状态——每一步落盘。

## 行为边界

做：

- 接收结构化数据 dict 或 DataFrame，判断数据形态（时序/对比/占比/分布）
- 根据数据形态推荐图表类型，调用 `chartjs-rendering` 生成 Chart.js HTML 块
- 将图表块注入已有的 HTML 报告（指定 slot 或自动追加）
- 用 Playwright 打开生成的 HTML，验证 canvas 实际渲染、无 JS 错误
- 检测数据规模，超过 Chart.js 推荐上限时自动切换离线/降采样策略
- 提供离线 Chart.js 打包（把 CDN 依赖下载到本地）

不做：

- 不生成矢量流程图、架构图（那是 drawio-skill 的事）
- 不生成手绘概念图（那是 excalidraw-diagram 的事）
- 不做数据清洗、聚合、统计（那是 sn-da-excel-workflow 的事）
- 不修改数据值本身
- 不生成研究报告中 Mermaid 流程图（那是 sn-research-report 的事）

## 调用者

| skill | 触发场景 |
|-------|---------|
| `sn-da-excel-workflow` | 数据分析完成后，需要从 DataFrame 出图表报告 |
| `sn-md-to-html-report` | Markdown 转 HTML 阶段，需要在报告中插入数据图表 |
| `sn-research-report` | 研究报告中需要数据子图（bar/line/pie），与 Mermaid 互补 |
| 用户直接调用 | 已有数据，想要一张交互式图表 |

## 输入

```
{
  "source": "data dict | DataFrame | file_path",
  "industry": "餐饮 | 零售 | 医疗 | ...",
  "charts": [
    {
      "type": "bar | line | pie | doughnut | radar | mixed",
      "title": "图表标题",
      "labels": ["1月", "2月", ...],
      "datasets": [
        {"label": "营收", "data": [5567, 4187, ...]},
        {"label": "利润", "data": [1200, 980, ...]}
      ],
      "options": { "palette": "catering" },
      "note": "下方说明文字"
    }
  ],
  "template": "standard-report | inject-only",
  "target_html": "/path/to/existing.html",
  "target_slot": "#chart-area"
}
```

## 输出

| 产出物 | 路径 |
|--------|------|
| 完整 HTML 报告 | `{out_dir}/{name}.html` |
| 图表注入后的现有报告 | `{target_html}`（原地修改） |
| 渲染验证报告 | `{out_dir}/chart-validation.json` |
| 离线 Chart.js 包 | `{out_dir}/chart.min.js` |

## 执行流程

### 模式 A：生成完整图表报告（数据分析后）

```
sn-da-excel-workflow 传来 DataFrame
  → sn-chart-render 读 capability/chartjs-rendering
    → scripts/render_chart_html.py data.json --template standard-report
      → {out_dir}/report.html
  → capability/chart-validation 做 Playwright 验证
```

### 模式 B：注入已有报告（研究报告中补图）

```
sn-research-report 已有 report.html，需要补个图
  → sn-chart-render 先调 chartjs-rendering 生成图块
    → scripts/render_chart_html.py data.json --template chart-only
      → /tmp/chart_block.html
  → 调 chart-embedding
    → scripts/embed_chart_to_html.py --target report.html --source /tmp/chart_block.html --slot "#section-3"
      → report.html（已注入 Chart.js CDN + canvas + script）
  → 调 chart-validation 验证
```

### 模式 C：纯渲染验证（已有 HTML 只做检查）

```
用户已有含 Chart.js 的 HTML 文件
  → capability/chart-validation
    → scripts/validate_chart_rendering.py report.html
      → chart-validation.json
```

## 选型策略

在 `chart-type-selection.md` 中有完整决策树，编排器调 chartjs-rendering 前先做这个判断：

| 数据类型 | 推荐 chart type | 触发条件 |
|---------|----------------|---------|
| 同一指标随时间变化 | line | labels 是连续时间（月/季/年），数据集 ≤ 3 条 |
| 多对象单指标对比 | bar | 对象数 3-20，适合比较大小 |
| 组成占比 | doughnut | 类别 ≤ 10，合计 100% |
| 多维度评分 | radar | 维度 3-12，2-4 个对比对象 |
| 不同量级混显 | mixed (bar+line) | 一组柱状 + 一组折线，量级差 > 5x |
| 大量级单元排行 | horizontalBar | 对象 8-30，适合排名阅读 |

退路：如果数据不符合上述任何模式，默认用 bar。

## 质量守门

- 每个 chart_id 全局唯一（`c1`, `c2`, ...不重复）
- CDN 可达性检查（`requests.head(CDN_URL) time < 3s`)；不通则提示下载本地版
- 数据点数量 ≤ 1000（Chart.js 默认渲染阈值）；超过则警告并建议降采
- canvas 实际渲染检查：`document.querySelectorAll('canvas').length > 0` + `canvas.height > 0`
- console 无 Chart.js 报错（`requested scale X is not configured` 等）
- 中文字体渲染检查（非 ASCII 文本的 bounding box 非零）

## 续跑规则

若产物目录已有 `*_validated.json` 且全部通过 → 跳过，直接交付。
若只有 `.html` 无验证 → 只跑验证。
若 `.html` 也不存在 → 从头渲染。

## 常见失败

- 饼图数据点超过 10 个，标签挤在一起 → 自动合并 `< 2%` 的 data 为"其他"
- 混合图 dataset 过多（> 6 条）→ 拆成两张子图
- 中文字体在 Chart.js 默认配置下宽度不准确 → 用 `font.family: 'system-ui, sans-serif'` 覆盖
- CDN 被墙 → 需要本地 fallback，参见 `capability/chart-offline-pack`
- 目标 HTML 文件中已有 chart_id 冲突 → 自动重编号（c1→c6→c6_01）

## 环境准备

Playwright 验证器依赖：

```bash
pip install playwright
playwright install chromium
```

一次性。首次运行 `validate_chart_rendering.py` 时会自动检查。

## 与兄弟 skill 的分工

```
           数据图表 (Chart.js)      架构/流程图 (drawio)    手绘概念图 (Excalidraw)
            ─────────────────       ────────────────────    ─────────────────────
Tier 1      sn-chart-render         drawio-skill            excalidraw-diagram
适用场景    柱/线/饼/雷达/混合       ER/UML/拓扑/流程        思维导图/框架图/白板
渲染方式    浏览器 Chart.js CDN      draw.io CLI 转 PNG      serve + Puppeteer 转 PNG
验证方式    Playwright canvas 检查    图片尺寸/文件非空         图片尺寸/文件非空
```

三管线不重叠。如果需要在一份报告中同时使用三种图，由 `sn-md-to-html-report` 编排层整合输出，本 skill 只负责数据图表部分。
