# 视角反馈 Markdown 契约

`{report_dir}/sub_reports/d{N}.perspectives/{lens.axis}_{lens.value}.md` 记录单个研究维度下某个视角的覆盖面审查结果。

它不是正式证据。它可以诊断覆盖缺口、提出补研问题，并说明写作上下文边界。任何新的事实线索都必须由 `research` 复核并写入 `d{N}.evidence.json`，之后才能支撑报告断言。

## 文件位置

```text
{report_dir}/sub_reports/d{N}.perspectives/{lens.axis}_{lens.value}.md
```

## 必备章节

```markdown
# Perspective Feedback: {dimension_id} / {lens.axis}:{lens.value}

## Lens 定位

## 对本维度的关键反馈

### 写作补充边界（非正文主张）

### 需要补研后才能使用

## 探索性搜索线索

## 维度内补研需求

## 写回摘要
```

## 章节契约

### 视角定位

必须包含：

- `lens: {axis}:{value}`
- `rationale`
- 已审查的证据文件路径

### 写作补充边界（非正文主张）

用于记录结构、解释顺序、来源边界说明、风险提醒，以及缺口提示或醒目标注的措辞边界。

每项应说明：

- 标题
- 解释
- 建议用途：`writing_context` / 表注 / 段尾限定语 / 缺口提示
- 证据依赖：`none` 或当前维度证据

这些内容不得成为导语、内容块主旨、L0 摘要或新的事实断言。

### 需要补研后才能使用

用于记录尚未获得证据支撑的事实、趋势、比较、因果、定量或案例判断。

每项应说明：

- 待确认判断
- 当前问题
- 具体补研问题
- 跳过补研的影响

### 探索性搜索线索

使用包含以下列的 Markdown 表格：

| 线索 | URL/来源 | 可能意义 | 是否需要 research 复核 |
| --- | --- | --- | --- |

所有线索都需要由 `research` 复核，本身不属于证据。

### 维度内补研需求

使用包含以下列的 Markdown 表格：

| 缺口 | 补研问题 | 建议来源 | 候选线索 | 不补研的影响 |
| --- | --- | --- | --- | --- |

如果无需补研，必须原样写：`无必要补研。`

### 写回摘要

为 `controller` / `supplement-planner` 提供 3–6 条简短要点。要点必须区分：

- 需要补研的断言
- `writing_context` 边界
- 无需补研的决定

此处不要撰写最终报告正文。

## 消费方规则

- `supplement-planner` 会将此 Markdown 与 `review.md`、当前 `evidence.json` 一并读取。
- 控制器调度时只应使用该角色的完成摘要，不应读取完整的视角反馈 Markdown。
- 报告阶段智能体不得把视角反馈当作证据使用。
- 未解决的视角反馈必须先通过证据或 `writing_context` 边界完成路由，之后才能作为限制说明或缺口提示呈现。
