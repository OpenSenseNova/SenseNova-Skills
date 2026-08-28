---
name: chart-embedding
description: 将 Chart.js 图表代码块注入已有 HTML 报告。处理 CDN 注入、chart_id 冲突避让、slot 定位。不负责图表渲染本身。
tier: 2
category: ability
parent: sn-chart-render
---

# chart-embedding — 图表注入能力

## 行为边界

做：

- 在目标 HTML 的 `<head>` 前注入 Chart.js CDN（如果尚未注入）
- 在指定 slot 位置（CSS 选择器或注释锚点）插入 canvas + script
- 检测 chart_id 冲突并自动重编号
- 支持多图表顺序注入（c1, c2, c3...自动递增）
- 只注入一次 CDN，多个图表共用一个 `<script src>`

不做：

- 不生成图表内容（那是 chartjs-rendering 的事）
- 不修改数据值
- 不验证渲染结果（chart-validation 做）
- 不改动已有 HTML 中非图表部分的内容和样式

## 输入

```
--target    /path/to/existing.html     # 目标 HTML 文件（原地修改）
--source    /path/to/chart_block.html   # chartjs-rendering 输出的图块
--slot      "#chart-area"               # CSS 选择器或 <!-- CHART-SLOT --> 注释
                                        # 默认: 在 </body> 前追加
--dry-run   true/false                  # 不写文件，只输出 diff 预览
```

## 输出

成功：原地修改 target HTML，退出码 0

失败：退出码 1 + stderr 说明原因

## slot 定位优先级

1. 指定 CSS 选择器（`#chart-area`, `.report-section-3`）
2. `<!-- CHART-SLOT-1 -->` 注释锚点
3. `</body>` 前（默认 fallback）

注入后自动在 slot 处插入：

```html
<!-- chart:c1 -->
<canvas id="c1" height="200"></canvas>
<script>
// Chart.js init code
</script>
<!-- /chart:c1 -->
```

## chart_id 冲突处理

1. 扫描 target HTML 中已有 `id="cN"` 的 canvas
2. 最大 N 为 current_max
3. 新图 id 从 current_max + 1 开始编号
4. 同时更新 script 中的 `document.getElementById('c...')` 引用

## 多轮注入

embed_chart_to_html.py 是幂等的：

- 同一 target 多次注入 → 每次 append 新图块
- CDN 只注一次（检查 `<script src="...chart.js...">` 已存在）
- 已存在的 chart_id 不会重复添加

## 常见失败

- slot 选择器不存在 → 退到 `</body>` 前追加，打印警告
- 目标 HTML 编码非 UTF-8 → 自动检测并转换
- CDN 已存在但版本不同 → 不做降级，保持原有版本
