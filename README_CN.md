# SenseNova-Skills

[English](README.md) | [简体中文](README_CN.md)

面向智能体运行时的 **AIGC** 技能与工具。

## 环境要求

- **Python** 3.10 及以上。
- **U1 API** 凭证：图像生成与 LLM/VLM 接口需 `U1_API_KEY`、`U1_LM_API_KEY`（见 [快速开始](#快速开始)）。

## 技能

### u1-image-base（第 0 层）

基础层基础设施技能，提供两个底层工具。完整说明见 [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md)。

- **u1-image-generate** — 文生图
- **u1-text-optimize** — 使用大语言模型进行文本处理

所有工具均通过统一的 `openclaw_runner.py` 入口调用。

### u1-infographic（第 1 层）

用于生成专业信息图的场景技能，基于 `u1-image-base`。完整说明见 [`skills/u1-infographic/SKILL.md`](skills/u1-infographic/SKILL.md)。示例输出见 [`examples/u1-infographics.md`](examples/u1-infographics.md)。

- 自动评估提示词质量
- 内容分析与版式/风格选择（87 种版式、66 种风格）
- 多轮图像生成与 VLM 评审
- 质量排序并输出最佳结果

## 快速开始

在 [OpenClaw](https://openclaw.ai/) 中使用本仓库技能。目录需符合 [Agent Skills](https://agentskills.io/) 约定；OpenClaw 如何发现并加载技能文件夹见 [OpenClaw Skills](https://docs.openclaw.ai/skills)。若尚未安装或配置 OpenClaw，请通过 **[官方文档](https://docs.openclaw.ai/)** 完成安装与配置（产品介绍：[openclaw.ai](https://openclaw.ai/)）。

### 1. 注册 `u1-image-base` 与 `u1-infographic`

克隆本仓库后，须将 **两个** 技能目录暴露给 OpenClaw（见 [Locations and precedence](https://docs.openclaw.ai/skills#locations-and-precedence)）。`u1-infographic` 依赖 `u1-image-base`，两者都需安装。

| 方式 | 做法 |
|------|------|
| **工作区 `skills/`**（常用） | 将 `skills/u1-image-base` 与 `skills/u1-infographic` 复制或符号链接到智能体工作区，得到 `./skills/u1-image-base/` 与 `./skills/u1-infographic/`。 |
| **本机共享** | 将同样两个目录复制或符号链接到 `~/.openclaw/skills/`。 |
| **`openclaw.json`** | 通过 `skills.load.extraDirs` 写入本仓库 `skills` 目录的绝对路径（同时为两个目录的父目录），示例如下。 |

```json5
{
  skills: {
    load: {
      extraDirs: ["/absolute/path/to/SenseNova-Skills/skills"],
    },
  },
}
```

将路径替换为你的克隆路径。详情见 [Skills config](https://docs.openclaw.ai/tools/skills-config)。若名称冲突，工作区中的技能优先于 `extraDirs`。

### 2. Python 依赖与 API 密钥

在 OpenClaw 运行 [`skills/u1-image-base/scripts/openclaw_runner.py`](skills/u1-image-base/scripts/openclaw_runner.py)（上述工具的统一直达入口）时所使用的 **Python 环境与进程**中安装依赖并设置密钥：

```bash
pip install -r skills/u1-image-base/requirements.txt
export U1_API_KEY="your-image-api-key"
export U1_LM_API_KEY="your-lm-api-key"  # 用于 LLM 与 VLM
```

请使用环境变量或本地 `.env` 文件。不要将密钥提交到版本库。也可通过 `skills.entries` 注入（见 [Environment injection](https://docs.openclaw.ai/skills#environment-injection-per-agent-run)）。可选：将 LLM/VLM 接口映射到 OpenClaw 的 provider，见 [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md)（Agent Configuration Integration）。

### 3. 在 OpenClaw 中调用

在对话中描述任务，例如：

> 「做一张解释水循环的信息图」

或按名称调用技能：

> /skill u1-infographic "The water cycle"

## 许可

MIT — 详见 [LICENSE](LICENSE)。
