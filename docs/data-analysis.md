# 数据分析（DA）相关技能

简体中文 | [English](data-analysis_en.md)

本文档汇总数据分析（Data Analysis）相关技能（`sn-da-excel-workflow`、`sn-da-image-caption`、`sn-da-large-file-analysis`），覆盖 Excel 多表读取与清洗、大文件高性能分析、图像数据提取与可视化。

## 环境要求

- **Python** 3.9 或更高版本（推荐 3.10+）。
- 常用数据栈：`pandas`、`openpyxl`（含 read_only 模式）、`pyarrow`、`matplotlib`、`numpy`。
- `sn-da-image-caption` 需要 VLM API 凭据。

## 技能介绍

| 名称 | 角色 | 说明 |
|------|------|------|
| [`sn-da-excel-workflow`](../skills/sn-da-excel-workflow/SKILL.md) | Excel 分析编排 | 多表读取、大文件检测（≥10k 行触发 Parquet 优化、≥100k 行交由 `sn-da-large-file-analysis`）、清洗、条件过滤、跨表聚合、Excel/CSV 导出的全流程编排。 |
| [`sn-da-image-caption`](../skills/sn-da-image-caption/SKILL.md) | 图像理解与数据提取 | 表格 OCR / 图表解读 / 截图描述 / UI 描述；可解析为 DataFrame、复绘可视化、导出 Excel/CSV。 |
| [`sn-da-large-file-analysis`](../skills/sn-da-large-file-analysis/SKILL.md) | 大文件高性能分析 | 流式读取（`openpyxl read_only` + `iter_rows`）、Parquet 转换、内存优化（类型降阶）、向量化操作、分块写入。 |

`sn-da-excel-workflow` 是常用入口，根据文件规模自动选用读写策略并按需路由到 `sn-da-large-file-analysis`。

## Quick Start

通过 [OpenClaw](https://openclaw.ai/) 使用这些技能。技能注册步骤参考 [`sn-image-generate.md`](sn-image-generate.md#1-注册技能)。

### 1. Python 依赖

DA 技能未提供独立的 `requirements.txt`，依赖通常已包含在执行环境的基础镜像中。如需自行准备环境：

```bash
pip install pandas openpyxl pyarrow matplotlib numpy
```

`sn-da-image-caption` 还需要 HTTP 客户端（`requests` 或 `httpx`）。

### 2. API Key 与环境变量

`sn-da-image-caption` 通过视觉模型解析图像，需要在 `~/.openclaw/.env`（或 `~/.hermes/.env`）中设置：

```ini
VISION_API_KEY="your-vision-api-key"
VISION_API_BASE="https://your-vlm-endpoint"
```

`sn-da-excel-workflow` 与 `sn-da-large-file-analysis` 不直接调用模型，无需 API key。

### 3. 在智能体中调用

把数据文件交给智能体并描述需求即可：

> "分析这个 Excel：按部门汇总销售额，导出 CSV"

或显式按名调用：

> /skill sn-da-excel-workflow

图像类任务：

> "看一下这张图表，把里面的数据提成 Excel"
> /skill sn-da-image-caption

## 输出物

- 分析结果通常落盘为 `*.xlsx` / `*.csv`（或可视化图片）
- 大文件场景会生成 Parquet 中间文件以加速后续步骤
- 图像解析可输出结构化 JSON 或 Markdown 表格
