# SN 图像风格模仿技能

简体中文 | [English](README.md)

本文档介绍 `sn-image-imitate` 技能，并提供在 OpenClaw / Hermes 中端到端使用的 Quick Start。

## 环境要求

- **Python** 3.9 或更高版本（推荐 3.10+）。
- **SN API** 凭据，用于图像生成与 LLM/VLM 接口（`SN_IMAGE_BASE_API_KEY`、`SN_CHAT_API_KEY`，详见 Quick Start）。
- 已安装 `sn-image-base` 技能（作为底层依赖）。

## 技能介绍

### sn-image-imitate（Tier 1）

图像风格模仿场景技能，构建于 `sn-image-base` 之上。完整行为见 [`skills/sn-image-imitate/SKILL.md`](../sn-image-imitate/SKILL.md)。

给定一张参考图像和目标内容描述，该技能会：

1. **图像标注** —— 使用 VLM 提取参考图像的长描述（long caption）和布局蓝图（layout blueprint）
2. **描述改写** —— 在保持风格与布局不变的前提下，将内容替换为用户指定的目标内容
3. **生成与审查** —— 根据改写后的描述生成新图像，并通过 VLM 审查布局一致性；不满足阈值时自动重试并叠加修正提示

### 不适用场景

- 纯风格迁移（不修改内容）—— 请使用专用风格迁移工具
- 局部编辑 / Inpainting
- 视频或动画输入
- 多张参考图批量生成
- 像素级还原

### 依赖关系

```
sn-image-base (Tier 0)
  ├── sn-image-recognize  → VLM 调用（图像标注 + 布局审查）
  ├── sn-text-optimize    → LLM 调用（描述改写）
  └── sn-image-generate   → 图像生成
```

## Quick Start

### 1. 注册技能

确保 `sn-image-base` 已注册（详见 [`sn-image-generate.md`](../../docs/sn-image-generate.md) 的注册步骤），然后将 `sn-image-imitate` 同样注册到 OpenClaw 或 Hermes：

| 方式 | 操作 |
|------|------|
| **本机共享** | 将 `skills/sn-image-imitate` 拷贝或软链接到 `~/.openclaw/skills/`（OpenClaw）或 `~/.hermes/skills/openclaw-imports/`（Hermes）。 |
| **工作区 `skills/`** | 将 `skills/sn-image-imitate` 拷贝或软链接到智能体工作区。 |
| **`openclaw.json`** | 如果已通过 `skills.load.extraDirs` 指向本仓库 `skills` 目录，则无需额外操作。 |

### 2. Python 依赖与 API Key

依赖安装与 API Key 配置用于 [sn-image-base](../sn-image-base/SKILL.md) 技能。

使用 [SenseNova Token Plan](https://platform.sensenova.cn/token-plan) 运行 `sn-image-base` 技能所需的最小环境变量：

```ini
SN_IMAGE_GEN_API_KEY="your-api-key"
SN_CHAT_API_KEY="your-api-key"
```

更多配置请参考 [`sn-image-generate.md`](../../docs/sn-image-generate.md) 中的 **Python 依赖与 API Key** 段落。

### 3. 在智能体中调用

在对话中描述任务，例如：

> "按这张图的风格，画一张关于新能源汽车的海报"

或按名调用技能：

> /skill sn-image-imitate "参考图：/path/to/ref.png，目标内容：新能源汽车海报"

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `reference_image` | string | **必填** | 参考图像的本地路径或 URL |
| `target_content` | string | **必填** | 期望生成的新内容描述 |
| `output_mode` | string | `friendly` | 输出模式：`friendly`（简洁）或 `verbose`（详细） |
| `aspect_ratio` | string | `16:9` | 生成图像的宽高比 |
| `image_size` | string | `2k` | 生成图像的尺寸预设 |
| `max_attempts` | int | `3` | 最大生成尝试次数 |
| `layout_threshold` | float | `0.75` | 布局一致性通过阈值 |

## 工作流程概览

```
用户请求 → Main Agent
  ├── 参数校验 + 预检消息
  └── 启动 Worker Agent
        ├── Step 0: 初始化（task_id、临时目录）
        ├── Step 1: VLM 图像标注 → short/long caption + layout blueprint
        ├── Step 2: LLM 描述改写（保持风格与布局，替换内容）
        └── Step 3: 生成 + 审查循环
              ├── 生成候选图像
              ├── VLM 布局一致性审查（max_attempts > 1 时执行）
              ├── 通过阈值 → 提前终止
              └── 未通过 → 叠加修正提示，继续下一轮
```

## 输出模式

### friendly 模式（默认）

一段简洁描述 + 最终生成的图像。

### verbose 模式

结构化摘要，包含：

1. 参考图像的短描述
2. 风格与布局要点
3. 改写后的长描述
4. 每轮尝试的相似度评分与主要偏差
5. 耗时统计
6. 最终图像

## 常见问题

### Q: 生成结果布局与参考图差异较大怎么办？

- 增大 `max_attempts` 以允许更多重试轮次
- 降低 `layout_threshold` 以放宽通过条件
- 确保参考图包含清晰的视觉结构和区域划分

### Q: API Key 缺失报错如何处理？

运行 `sn-image-doctor` 技能检查环境配置，或参考 [`sn-image-generate.md`](../../docs/sn-image-generate.md) 中的 API Key 配置说明。

### Q: 能否只改风格不改内容？

该技能设计目标是同时保持风格并替换内容。如果只需风格迁移而不修改内容，建议使用专用风格迁移工具。
