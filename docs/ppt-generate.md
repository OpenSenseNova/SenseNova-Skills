# PPT 生成相关技能

简体中文 | [English](ppt-generate_en.md)

本文档汇总演示文稿（PPT）生成相关技能（`sn-ppt-entry`、`sn-ppt-doctor`、`sn-ppt-creative`、`sn-ppt-standard`），用于在 OpenClaw / Hermes 中按用户需求生成 PPTX 文件。

## 环境要求

- **Python** 3.9 或更高版本（推荐 3.10+）。
- **Node.js** 运行时（`sn-ppt-standard` 在分页 HTML 处理阶段使用）。
- 需要 LLM/VLM 与文生图 API 凭据（详见下文）。

## 技能介绍

| 名称 | 角色 | 说明 |
|------|------|------|
| [`sn-ppt-entry`](../skills/sn-ppt-entry/SKILL.md) | **PPT 入口** | 收集角色 / 受众 / 场景 / 页数 / 模式（创意 or 标准），解析 pdf / docx / md / txt 输入，产出 `task_pack.json` + `info_pack.json` 并分派到下游模式。 |
| [`sn-ppt-doctor`](../skills/sn-ppt-doctor/SKILL.md) | PPT 环境诊断 | 验证 `sn-image-base` 可用性、API key、Node 运行时与可选依赖；按需写入 `.env`。 |
| [`sn-ppt-creative`](../skills/sn-ppt-creative/SKILL.md) | PPT 创意模式 | 每页一张 16:9 全图（PNG），按页面构图 prompt 走 `sn-image-generate` 一次性出图后导出 PPTX。 |
| [`sn-ppt-standard`](../skills/sn-ppt-standard/SKILL.md) | PPT 标准模式 | `style_spec` → 大纲 → 资产规划 + 分槽位图像 + VLM 质检 → 分页 HTML → 分页评审（可选重写）→ 汇总 `review.md` → 导出 PPTX。 |

`sn-ppt-creative` 依赖 `sn-image-base` 进行文生图；`sn-ppt-standard` 自带 LLM / VLM 调用脚本（`scripts/run_stage.py`），文生图阶段仍走 `sn-image-base`。

## Quick Start

通过 [OpenClaw](https://openclaw.ai/) 使用这些技能。技能注册（拷贝 / 软链 / `openclaw.json` 三种方式）请参考 [`sn-image-generate.md`](sn-image-generate.md#1-注册技能) 中的对应章节，本文档不再赘述。

### 1. Python 依赖

```bash
# sn-ppt-entry：解析 PDF / DOCX
pip install -r skills/sn-ppt-entry/requirements.txt

# sn-ppt-creative：导出 PPTX
pip install -r skills/sn-ppt-creative/requirements.txt

# sn-ppt-creative 依赖 sn-image-base 的图像生成接口
pip install -r skills/sn-image-base/requirements.txt
```

`sn-ppt-doctor` 仅用 Python 标准库，无需额外依赖。`sn-ppt-standard` 在 `scripts/run_stage.py` 中包装模型调用，最终导出 PPTX 同样需要 `python-pptx`。

### 2. API Key 与环境变量

将以下变量写入 `~/.openclaw/.env`（OpenClaw）或 `~/.hermes/.env`（Hermes）：

```ini
# LLM（大纲、style_spec、内容规划、图片内容识别、页面review）
SN_CHAT_API_KEY="your-api-key"
SN_CHAT_BASE_URL="https://token.sensenova.cn/v1"
SN_CHAT_MODEL="sensenova-6.7-flash-lite"
SN_VISION_API_KEY="your-api-key"
SN_VISION_BASE_URL="https://token.sensenova.cn/v1"
SN_VISION_MODEL="sensenova-6.7-flash-lite"

# 文生图（创意模式必填，标准模式按需）
SN_IMAGE_GEN_API_KEY="your-api-key"
SN_IMAGE_GEN_MODEL_TYPE="sensenova"
SN_IMAGE_GEN_MODEL="sensenova-u1-fast"
```

可选环境变量：`SN_IMAGE_GEN_*`、`SN_TEXT_*`、`SN_VISION_*` 用于覆盖默认模型与超时。详细列表见 [`skills/sn-image-base/README.md`](../skills/sn-image-base/README.md)。

调用前先运行环境诊断：

> 运行 `sn-ppt-doctor` 技能

### 3. 在智能体中调用

`sn-ppt-entry` 是统一入口，会自动调度到 creative 或 standard 模式：

> "做一份关于团队 OKR 的 10 页 PPT，受众是高管，风格简洁"

或直接按名调用：

> /skill sn-ppt-entry "团队 OKR 汇报"

## 输出物

PPT 产物默认保存在 `$(pwd)/ppt_decks/<topic>_<timestamp>/`，目录内包含：

- `task_pack.json` / `info_pack.json` —— `sn-ppt-entry` 解析后的任务参数
- `style_spec.json`（标准模式）/ `style_spec.md`（创意模式）、`outline.json` —— 风格与大纲
- `pages/page_*.png` —— 单页全图（创意模式）或 HTML 渲染图（标准模式）
- `review.md` —— 分页评审汇总（标准模式）
- `<deck_id>.pptx` —— 最终 PPTX

_更多端到端样例参见仓库根目录 [`README_CN.md`](../README_CN.md#输出样例) 中的「输出样例」章节。_
