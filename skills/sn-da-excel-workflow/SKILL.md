---
name: sn-da-excel-workflow
description: "Multi-step workflow for Excel data analysis. Use when a task involves: (1) reading multi-sheet Excel files and counting rows, (2) large file detection (>=10k rows -> Parquet optimization), (3) data cleaning (missing values, text normalization, invalid characters), (4) conditional filtering and category extraction, (5) statistical aggregation across sheets, (6) exporting results as Excel/CSV with download links. Covers the full pipeline from ingestion to report generation. Orchestrates capability sub-skills for each step."
---

# Excel Data Analysis Workflow

End-to-end workflow for structured Excel analysis. Each step maps to a
capability sub-skill that can be loaded for detailed patterns.

## Workflow

### Step 1 — Count rows across all sheets (lightweight, no full load)

Count rows per sheet **without loading data into memory**. Use openpyxl
`read_only` mode — this works for any file size.

```python
import openpyxl, gc

wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
total_rows = 0
sheet_info = {}
for name in wb.sheetnames:
    ws = wb[name]
    row_count = sum(1 for _ in ws.iter_rows(min_row=2, values_only=True))
    total_rows += row_count
    sheet_info[name] = row_count
    print(f"Sheet '{name}': {row_count} rows")
wb.close()
print(f"总行数={total_rows}")
```

⚠️ **Do NOT use `pd.read_excel()` to count rows** — it loads all data into
memory, which will OOM on large files.

→ capability: `excel-reading/multi-sheet-reading`

### Step 2 — Large file gate (CRITICAL — choose strategy by row count)

| total_rows | Strategy | What to do |
|-----------|----------|------------|
| < 10k | Direct read | `df = pd.read_excel(file_path, sheet_name=target_sheet)` |
| 10k – 100k | Parquet cache | `pd.read_excel()` once → `df.to_parquet()` → all later reads from Parquet |
| **>= 100k** | **STOP. Load `sn-da-large-file-analysis` skill** | Read its SKILL.md, then follow its streaming read + Parquet pattern. **Do NOT use `pd.read_excel()` at all** — it will OOM or timeout on 100k+ rows. |

**For >= 100k rows:**
```
read_file(path="<skills_base>/sn-da-large-file-analysis/SKILL.md")
```
Then use `stream_excel_to_parquet()` from that skill — it reads via
openpyxl `iter_rows` in 50k-row chunks with constant memory.

**For 10k – 100k rows (only):**
```python
import pandas as pd
parquet_path = "/tmp/_auto_parquet.parquet"
df = pd.read_excel(file_path, sheet_name=target_sheet)
df.to_parquet(parquet_path, engine="pyarrow")
del df; gc.collect()
df = pd.read_parquet(parquet_path)
```

→ capability: `excel-reading/large-excel-reading`

### Step 3 — Inspect schema & data types

Preview target sheet structure. **For large files (>= 10k rows), only read
a small sample — never full load just to inspect.**

```python
# For any file size — read only first N rows for inspection
df_head = pd.read_excel(file_path, sheet_name=target_sheet, nrows=20)
print(f"Columns: {df_head.columns.tolist()}")
print(f"Dtypes:\n{df_head.dtypes}")
print(df_head.head(10))
```

→ capability: `excel-reading/range-reading`

### Step 4 — Data cleaning

Handle missing values, normalize text, clean invalid characters.

```python
# Missing values
null_count = df[col].isna().sum()

# Text cleaning: keep only Chinese characters
import re
def clean_text(val):
    if pd.isna(val): return val
    return "".join(re.findall(r"[\u4e00-\u9fff]", str(val))) or ""

df[col] = df[col].apply(clean_text)
```

⚠️ **Large file rule**: When `total_rows >= 100k`, do NOT use `df.apply(lambda...)`.
Use vectorized operations or `np.where()` instead. See `sn-da-large-file-analysis` skill
for the vectorized cheat sheet.

→ capabilities:
  - `excel-data-cleaning/missing-value-handling`
  - `excel-data-cleaning/invalid-data-cleaning`
  - `excel-data-cleaning/text-normalization`

### Step 5 — Filter & extract

Apply condition or category filters, aggregate results.

```python
# Condition filter
mask = df[col].astype(str).str.strip() == target_value
filtered = df[mask]

# Category extraction (for headerless layouts)
df_raw = pd.read_excel(file_path, sheet_name=sheet, header=None)
# Walk rows to find category markers, collect items until next marker
```

→ capabilities:
  - `excel-data-filtering/condition-filtering`
  - `excel-data-filtering/category-filtering`
  - `excel-data-filtering/threshold-filtering`

### Step 6 — Export results

Save filtered/cleaned data as Excel or CSV. Provide download link.

```python
output_path = "/mnt/data/result.xlsx"
result_df.to_excel(output_path, index=False)
print(f"[Download](sandbox:{output_path})")
```

→ capabilities:
  - `excel-result-export/single-sheet-export`
  - `excel-result-export/formatted-export`

## Key rules

- **Always count rows first** — gate large-file logic on the 10k threshold.
- **>= 100k rows → MUST load `sn-da-large-file-analysis` skill** — do not attempt to handle with `pd.read_excel()`.
- **Column names may contain spaces** (e.g. `'是否通 过'`) — use exact string indexing.
- **Headerless sheets** — use `header=None` and positional indexing.
- **Prohibited on large files (>= 100k rows)**:
  - `pd.read_excel()` for full load (use streaming read → Parquet)
  - `df.apply(lambda...)` or `df.iterrows()` (use vectorized ops or `itertuples()`)
  - `fc-list`, `find ... fonts`, `subprocess` to search fonts, or `pip install` (use fixed font paths below)
  - Printing all unique values or full DataFrames (use `.head()`, `.value_counts().head()`)

## CJK Font Setup (mandatory for charts)

When generating charts with matplotlib, **copy this block as-is**. Do NOT search for fonts.

```python
import os
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

_FONT_PATHS = [
    '/mnt/afs_agents/SimHei.ttf',
    '/mnt/afs_agents/mnt/data/SimHei.ttf',
    os.path.expanduser('~/.fonts/SimHei.ttf'),
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/usr/share/fonts/SimHei.ttf',
]
for _p in _FONT_PATHS:
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
        matplotlib.rcParams['font.family'] = fm.FontProperties(fname=_p).get_name()
        break
matplotlib.rcParams['axes.unicode_minus'] = False
```

## How to load sub-skills

Each workflow step references one or more capability sub-skills. When you
need the detailed code pattern for a step, load the sub-skill on demand:

```
read_file(path="<base_path>/<category>/<sub-skill-name>/SKILL.md")
```

**Rules:**
- Only load the sub-skill(s) needed for your current step.
- Do NOT load all sub-skills at once — it wastes context.
- The top-level workflow (this file) is your guide; sub-skills provide
  detailed implementation patterns.

## Available capability sub-skills

Base path: `<skills_root>/sn-da-excel-workflow/capability/{category}/{sub-skill}/SKILL.md`

### excel-reading — 读取与解析

| Sub-skill | 功能 |
|---|---|
| single-sheet-reading | 读取单个工作表，支持合并单元格处理、交叉分析及多维度可视化 |
| multi-sheet-reading | 读取多工作表，动态评估数据量启用Parquet优化，支持正则清洗、分类汇总与线性拟合 |
| range-reading | 特定区域数据提取，根据数据量动态选择处理策略 |
| large-excel-reading | 大型Excel文件处理，支持Parquet转换提速，生成带条件高亮的格式化报告 |
| multi-file-reading | 多文件读取与统计，支持大文件Parquet转换与可视化报告 |
| specific-sheet-reading | 跨Sheet特定字段统计、数据清洗与交叉分析，生成带下载链接的汇总报告 |
| structured-header-reading | 动态识别目标列进行统计，正则清洗文本字段提取中文字符 |

### excel-data-cleaning — 数据清洗

| Sub-skill | 功能 |
|---|---|
| missing-value-handling | 多Sheet智能清洗、跨表核对与可视化分析 |
| duplicate-removal | 多Sheet去重统计，生成摘要与明细报表 |
| invalid-data-cleaning | 正则清洗指定文本列（如保留中文字符），大文件自动Parquet加速 |
| text-normalization | 文本标准化清洗（去除异常前缀、提取纯中文字符等） |
| numeric-format-normalization | 数值格式标准化，支持关键指标合计核对与结果文件导出 |
| outlier-detection | IQR异常值检测，结合偏度/峰度分析数据分布，适用于非正态数据预处理 |

### excel-data-filtering — 数据筛选

| Sub-skill | 功能 |
|---|---|
| condition-filtering | 根据数据规模动态选择处理策略进行条件筛选 |
| category-filtering | 自定义分类统计、交叉分析，支持文本长度/术语密度/正则匹配等综合评分与分级 |
| range-filtering | 根据多维数值条件筛选并导出，支持大规模数据自动性能优化 |
| threshold-filtering | 数值列清洗、条件过滤，使用openpyxl对符合条件的单元格进行样式标记 |

### excel-data-analysis — 数据分析

| Sub-skill | 功能 |
|---|---|
| comparison-analysis | 两类分类数据对比分析，统计数量差异与比例关系并生成可视化 |
| group-by-analysis | 多Sheet数据清洗及分组聚合分析，生成带样式标记的统计表与图表 |
| kpi-metric-analysis | 提取关键指标进行单位一致性验证与排序分析 |
| pivot-table-analysis | 交叉表与热力图进行多维度占比分析，适用于奖项分布/绩效评估/市场占有率 |
| time-series-analysis | 时间序列趋势分析、百分比清洗、绩效分级建模与预测，生成高分辨率可视化报告 |
| trend-analysis | 多维度分级评估与趋势预测，差异化增长率计算，适用于绩效评估/目标设定 |

### excel-data-statistics — 统计计算

| Sub-skill | 功能 |
|---|---|
| basic-statistics | 基础统计，支持按条件筛选计算均值，指定行区间提取数据去重求和 |
| category-statistics | 各类别数量与占比统计，生成柱状图/饼图等组合可视化报告 |
| grouped-statistics | 多Sheet数据合并与前向填充，分组统计 |
| percentage-calculation | 逐行扫描或列匹配提取关键指标并计算占比/均值，输出结构化报告及图表 |

### excel-data-visualization — 数据可视化

| Sub-skill | 功能 |
|---|---|
| bar-chart-visualization | 处理合并单元格，交叉分组统计，生成支持中英文字体的美化柱状图 |
| histogram-visualization | 数值型分布分析与异常值检测，支持正则提取误差项，生成箱线图与直方图 |
| line-chart-visualization | 特征清洗与聚类分析，生成趋势对比/分布特征/参数敏感性多维度图表 |
| pie-chart-visualization | 分类汇总统计，自动识别关键字段生成包含占比/数值的美化饼图 |
| scatter-plot-visualization | 多维度统计分析与散点图可视化 |
| stacked-chart-visualization | 百分比字符串数据处理，补全缺失维度，生成堆叠柱状图展示构成变化趋势 |

### excel-cell-coloring — 单元格着色

| Sub-skill | 功能 |
|---|---|
| category-coloring | 提取目标指标计算最大值，对特定行进行高亮标注 |
| duplicate-value-coloring | 对比多表中的特定系数并对异常值进行颜色标记 |
| outlier-coloring | 识别超限数值与错误单元格并进行高亮标注 |
| threshold-cell-coloring | 计算时间序列平均值，使用openpyxl输出带条件格式（如低于均值标绿）的报告 |
| top-value-coloring | 根据数据规模动态选择策略，多表合并、统计筛选，关键指标自动化样式高亮 |

### excel-conditional-formatting — 条件格式

| Sub-skill | 功能 |
|---|---|
| data-bar-formatting | 从带单位字符串列提取数值并清洗，生成直方图/饼图/条形图/累积分布图 |

### excel-result-export — 结果导出

| Sub-skill | 功能 |
|---|---|
| single-sheet-export | 多Sheet数据探查与条件过滤导出，重命名字段后生成带下载链接的Excel |
| formatted-export | 条件筛选记录并以整行标红格式导出Excel |
| chart-embedded-export | 分类分布清洗与统计，生成多维度交叉分析与高分辨率嵌入式图表报告 |
| report-generation-export | 从Excel提取多类型数据，生成包含可视化图表与下载链接的综合分析报告 |

### excel-table-styling — 表格样式

| Sub-skill | 功能 |
|---|---|
| table-theme-styling | 大文件Parquet加速读取，条件筛选/分类汇总与结果导出 |
