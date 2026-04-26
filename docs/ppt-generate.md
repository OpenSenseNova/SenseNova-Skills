# PPT 生成相关技能

简体中文 | [English](ppt-generate_en.md)

本文档汇总演示文稿（PPT）生成相关技能（`ppt-entry`、`ppt-doctor`、`ppt-creative`、`ppt-standard`），用于在 OpenClaw / Hermes 中按用户需求生成 PPTX 文件。

## 环境要求

- **Python** 3.9 或更高版本（推荐 3.10+）。
- **Node.js** 运行时（`ppt-standard` 在分页 HTML 处理阶段使用）。
- 需要 LLM/VLM 与文生图 API 凭据（详见下文）。

## 技能介绍

| 名称 | 角色 | 说明 |
|------|------|------|
| [`ppt-entry`](../skills/ppt-entry/SKILL.md) | **PPT 入口** | 收集角色 / 受众 / 场景 / 页数 / 模式（创意 or 标准），解析 pdf / docx / md / txt 输入，产出 `task_pack.json` + `info_pack.json` 并分派到下游模式。 |
| [`ppt-doctor`](../skills/ppt-doctor/SKILL.md) | PPT 环境诊断 | 验证 `u1-image-base` 可用性、API key、Node 运行时与可选依赖；按需写入 `.env`。 |
| [`ppt-creative`](../skills/ppt-creative/SKILL.md) | PPT 创意模式 | 每页一张 16:9 全图（PNG），按页面构图 prompt 走 `u1-image-generate` 一次性出图后导出 PPTX。 |
| [`ppt-standard`](../skills/ppt-standard/SKILL.md) | PPT 标准模式 | `style_spec` → 大纲 → 资产规划 + 分槽位图像 + VLM 质检 → 分页 HTML → 分页评审（可选重写）→ 汇总 `review.md` → 导出 PPTX。 |

`ppt-creative` 依赖 `u1-image-base` 进行文生图；`ppt-standard` 自带模型调用脚本（`scripts/run_stage.py`）。

## Quick Start

通过 [OpenClaw](https://openclaw.ai/) 使用这些技能。技能注册（拷贝 / 软链 / `openclaw.json` 三种方式）请参考 [`u1-image-generate.md`](u1-image-generate.md#1-注册技能) 中的对应章节，本文档不再赘述。

### 1. Python 依赖

```bash
# ppt-entry：解析 PDF / DOCX
pip install -r skills/ppt-entry/requirements.txt

# ppt-creative：导出 PPTX
pip install -r skills/ppt-creative/requirements.txt

# ppt-creative 依赖 u1-image-base 的图像生成接口
pip install -r skills/u1-image-base/requirements.txt
```

`ppt-doctor` 仅用 Python 标准库，无需额外依赖。`ppt-standard` 在 `scripts/run_stage.py` 中包装模型调用，最终导出 PPTX 同样需要 `python-pptx`。

### 2. API Key 与环境变量

将以下变量写入 `~/.openclaw/.env`（OpenClaw）或 `~/.hermes/.env`（Hermes）：

```ini
# LLM（大纲、style_spec、内容规划）
U1_LM_API_KEY="your-api-key"
U1_LM_BASE_URL="https://token.sensenova.cn/v1"

# 文生图（创意模式必填，标准模式按需）
U1_API_KEY="your-api-key"
```

可选环境变量：`U1_IMAGE_GEN_*`、`VLM_*`、`LLM_*` 用于覆盖默认模型与超时。详细列表见 [`skills/u1-image-base/README.md`](../skills/u1-image-base/README.md)。

调用前先运行环境诊断：

> 运行 `ppt-doctor` 技能

### 3. 在智能体中调用

`ppt-entry` 是统一入口，会自动调度到 creative 或 standard 模式：

> "做一份关于团队 OKR 的 10 页 PPT，受众是高管，风格简洁"

或直接按名调用：

> /skill ppt-entry "团队 OKR 汇报"

## 输出物

PPT 产物默认保存在 `$(pwd)/ppt_decks/<topic>_<timestamp>/`，目录内包含：

- `task_pack.json` / `info_pack.json` —— `ppt-entry` 解析后的任务参数
- `style_spec.md`、`outline.json` —— 风格与大纲（标准模式）
- `pages/page_*.png` —— 单页全图（创意模式）或 HTML 渲染图（标准模式）
- `review.md` —— 分页评审汇总（标准模式）
- `<deck_id>.pptx` —— 最终 PPTX

更多样例参见 [`docs/ppt-examples.md`](ppt-examples.md)（待补充）。
