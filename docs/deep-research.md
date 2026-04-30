# 深度研究与搜索相关技能

简体中文 | [English](deep-research_en.md)

本文档汇总深度研究（`sn-deep-research`、`sn-research-planning`、`sn-dimension-research`、`sn-research-synthesis`、`sn-research-report`、`sn-report-format-discovery`）与搜索（`sn-search-academic`、`sn-search-code`、`sn-search-social-cn`、`sn-search-social-en`）相关技能。

深度研究技能负责规划、综合与成稿；搜索技能由 `sn-dimension-research` 在分维度取证阶段调用，覆盖学术论文、开发者资源、中英文社交平台。两类技能编排成端到端流水线。

## 环境要求

- **Python** 3.9 或更高版本（推荐 3.10+）。
- **当前智能体宿主必须已配置可用的 `web_search`**（深度研究编排器在启动时硬检查；OpenClaw / Hermes 等宿主的具体配置入口可能不同）。
- 如需在最终 `report.md` 中生成 AI 配图，必须安装并配置 `sn-image-base` 的 `sn-image-generate`。
- 视维度需要，可选 / 必填若干平台的 API key（详见 [API Key](#2-api-key)）。

## 深度研究技能

| 名称 | 角色 | 说明 |
|------|------|------|
| [`sn-deep-research`](../skills/sn-deep-research/SKILL.md) | **深度研究入口** | 全流程编排器：`request.md → plan.json → sub_reports/*.md → synthesis.md → report.md`，产物落盘到 `report_dir`，支持断点续跑。 |
| [`sn-research-planning`](../skills/sn-research-planning/SKILL.md) | 研究规划 | 基于 `request.md` 一次性产出 `plan.json`，覆盖定界、报告形态、维度拆解（3–8 维度）、关键问题、搜索策略、依赖与完成标准。 |
| [`sn-dimension-research`](../skills/sn-dimension-research/SKILL.md) | 单维度取证 | 按 `plan.json` 中维度的 `search_strategy` 调用[搜索技能](#搜索技能)完成多轮取证、交叉验证，产出 `sub_reports/{dimension_id}.md`。 |
| [`sn-research-synthesis`](../skills/sn-research-synthesis/SKILL.md) | 综合判断 | 把多个 `sub_reports` 综合为 `synthesis.md`，明确主线判断、证据强弱、跨维度共识、关键冲突与不确定性。 |
| [`sn-research-report`](../skills/sn-research-report/SKILL.md) | 终稿写作 / 改写 | 把判断层落成最终 `report.md`；也可对已有报告做重写、润色、重组结构、补充表格、规划插图并调用 `sn-image-base` 生成配图等定向编辑。 |
| [`sn-report-format-discovery`](../skills/sn-report-format-discovery/SKILL.md) | 报告形态发现 | 研究"这类报告应该长什么样"，给出章节结构、必备元素与风格约束；可独立使用，也可为 `sn-deep-research` 的 `report_shape` 提供依据。 |

## 搜索技能

| 名称 | 角色 | 说明 |
|------|------|------|
| [`sn-search-academic`](../skills/sn-search-academic/SKILL.md) | 学术搜索 | ArXiv（含 HTML 全文按章节读）/ Semantic Scholar（含引用数与正反向引用链）/ PubMed（含 PMC 开放获取全文）/ Wikipedia 多语言聚合。 |
| [`sn-search-code`](../skills/sn-search-code/SKILL.md) | 开发者搜索 | GitHub（仓库 / 代码 / Issue）/ Stack Overflow（按标签 / 票数）/ Hacker News / HuggingFace（模型 / 数据集 / Space）四平台聚合。 |
| [`sn-search-social-cn`](../skills/sn-search-social-cn/SKILL.md) | 中文社交搜索 | B 站 / 知乎 / 抖音 三个中文社交平台搜索；知乎、抖音必须配 cookie，B 站 cookie 可选。 |
| [`sn-search-social-en`](../skills/sn-search-social-en/SKILL.md) | 英文社交搜索 | Reddit（按 subreddit / 排序 / 时间）/ Twitter (X)（经 TikHub）/ YouTube（API key）。 |

每个搜索技能在自己的 `scripts/` 目录下携带 `search_utils.py` 共用工具模块，不直接面向用户。

## Quick Start

可通过 [OpenClaw](https://openclaw.ai/)、Hermes 或其他支持 Agent Skills 的智能体宿主使用这些技能。技能注册步骤参考 [`sn-image-generate.md`](sn-image-generate.md#1-注册技能)。

### 1. 启动前硬检查：`web_search`

`sn-deep-research` 在创建 `report_dir`、写 `request.md` 或进入任何研究阶段之前，**必须通过一次极小的通用 `web_search` 探测确认当前会话搜索能力可用**。未确认时不要开始研究，也不要用记忆或既有知识替代联网取证。

- 不判断自己运行在 OpenClaw、Hermes 还是其他宿主；不要读取或推断宿主专属配置路径
- 发起一次低成本、低歧义的 `web_search` 探测，只需要确认工具能返回正常搜索结果
- 探测成功且返回非空结果即可继续；探测失败、工具不存在、缺 key、provider 未就绪、服务不可达、search disabled、权限不足或结果为空时停止

### 2. API Key

按需在 `~/.openclaw/.env`（OpenClaw）、`~/.hermes/.env`（Hermes）或当前宿主支持的等效环境配置中配置：

| 平台 | 必填 / 可选 | 环境变量 | 说明 |
|------|------|----------|------|
| GitHub 仓库/Issue 搜索 | 可选（提高限额） | `GITHUB_TOKEN` | 公开搜索可匿名 |
| GitHub 代码搜索 | **必填** | `GITHUB_TOKEN` | `--type code` 必须提供 |
| Semantic Scholar | 可选 | `S2_API_KEY` | 提高速率限制 |
| PubMed | 可选 | `NCBI_API_KEY` | 限额从 3 req/s 提升到 10 req/s |
| HuggingFace | 可选 | `HF_TOKEN` | 提高限额 |
| B 站 | 可选 | `BILIBILI_COOKIE` | 提高结果质量 |
| 知乎 | **必填** | `ZHIHU_COOKIE` | 不配置无法搜索 |
| 抖音 | **必填** | `DOUYIN_COOKIE` | 不配置无法搜索 |
| Twitter/X | **必填** | `TIKHUB_TOKEN` | 通过 TikHub 反代 |
| YouTube | **必填** | `YOUTUBE_API_KEY` | YouTube Data API v3 |
| AI 配图（`sn-image-base` / `sn-image-generate`） | 生成配图时**必填** | `SN_API_KEY` | 用于 `report.md` 中的 AI 配图；`SN_IMAGE_GEN_API_KEY` 仅在图像生成使用不同 key 时覆盖 |
| AI 配图模型 | 可选 | `SN_IMAGE_GEN_MODEL` | 默认见 `sn-image-base` 配置；可指定 Token Plan 或其他支持的图像模型 |
| AI 配图服务地址 | 可选 | `SN_IMAGE_GEN_BASE_URL` | 默认见 `sn-image-base` 配置；使用非默认服务时设置 |
| AI 配图模型类型 | 可选 | `SN_IMAGE_GEN_MODEL_TYPE` | 如 `sensenova`、`nano-banana`、`openai-image` |

ArXiv、Stack Overflow、Hacker News、Reddit 公开搜索无需 key。

`sn-image-generate` 相关最小配置示例：

```ini
SN_API_KEY="sk-xxx"
SN_BASE_URL="https://token.sensenova.cn/v1"
SN_IMAGE_GEN_MODEL_TYPE="sensenova"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"
```

### 3. Python 依赖

搜索技能未提供独立的 `requirements.txt`，依赖通常已包含在执行环境中。如需自行准备：

```bash
pip install requests httpx lxml beautifulsoup4
```

如果最终报告需要 AI 配图，还需要安装 `sn-image-base` 的运行依赖，并确保宿主能定位到 `sn-image-base`：

```bash
pip install -r skills/sn-image-base/requirements.txt
```

深度研究编排器本身不直接调用 HTTP，主要依赖宿主 `web_search` 与上面的搜索脚本；终稿阶段只有在需要 AI 配图时才额外调用 `sn-image-base`。

### 4. 在智能体中调用

**深度研究入口**——直接描述研究主题即可触发：

> "深度研究：2025 年家用机器人产业链与主要玩家"

或按名调用：

> /skill sn-deep-research "家用机器人产业链"

**单独使用搜索**——按场景描述需求：

> "搜一下最近关于 RAG 的 ArXiv 论文，按引用数排序"
> "在 GitHub 上找 Python 实现的 in-context learning 项目"

或按名调用：

> /skill sn-search-academic "retrieval-augmented generation"
> /skill sn-search-code "in-context learning python"
> /skill sn-search-social-cn "扩散模型 教程"
> /skill sn-search-social-en "vision transformer explained"

**深度研究细分阶段**（高级用法）：

> /skill sn-research-planning  # 基于已写好的 request.md 产出 plan.json
> /skill sn-dimension-research # 按 plan.json 中某个维度做取证
> /skill sn-research-synthesis # 把已有 sub_reports 综合为 synthesis.md
> /skill sn-research-report    # 由 synthesis.md 与 sub_reports 落成 report.md

**直接以子进程方式调用搜索脚本**：

```bash
GITHUB_TOKEN=ghp_xxx python3 skills/sn-search-code/scripts/github_search.py "import asyncio" --type code --limit 5
ZHIHU_COOKIE="..." python3 skills/sn-search-social-cn/scripts/zhihu_search.py "Python 异步编程" --limit 5
```

## 输出物

### 深度研究

报告产物默认保存在 `{workspace}/reports/{YYYY-MM-DD}-{slug}-{hex4}/`：

- `request.md` —— 用户原始诉求与边界
- `plan.json` —— 维度拆解、关键问题、搜索策略、报告形态
- `sub_reports/d1.md` … `d8.md` —— 各维度证据汇总（含证据表与置信度）
- `synthesis.md` —— 综合判断（主线、共识、冲突、不确定性）
- `report.md` —— 最终报告

_更多端到端样例参见仓库根目录 [`README_CN.md`](../README_CN.md#输出样例) 中的「输出样例」章节。_

### 搜索

所有搜索脚本统一输出 JSON 到 stdout：

```json
{
  "success": true,
  "query": "...",
  "provider": "...",
  "items": [
    {"title": "...", "url": "...", "snippet": "..."}
  ],
  "error": null
}
```

ArXiv 与 PMC 的全文阅读脚本会返回结构化的章节内容，便于按需读取。
