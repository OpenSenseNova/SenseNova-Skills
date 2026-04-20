# SenseNova-Skills

[English](README.md) | 简体中文

面向智能体运行时的 **AIGC** 技能与工具。

## 环境要求

- **Python** 3.10 及以上。
- **U1 API** 凭证：图像生成与 LLM/VLM 接口需 `U1_API_KEY`、`U1_LM_API_KEY`（见 [快速开始](#快速开始)）。

## 技能

### u1-doctor

环境诊断技能，用于检查安装、依赖和配置。完整说明见 [`skills/u1-doctor/SKILL.md`](skills/u1-doctor/SKILL.md)。

- 验证 `u1-image-base` 安装和 Python 依赖
- 检查环境变量并交互式提示配置缺失的必填变量
- 保存配置到 `.env` 文件并自动重载环境

### u1-image-base（第 0 层）

基础层基础设施技能，提供两个底层工具。完整说明见 [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md)。

- **u1-image-generate** — 文生图
- **u1-text-optimize** — 使用大语言模型进行文本处理

所有工具均通过统一的 `openclaw_runner.py` 入口调用。

### u1-infographic（第 1 层）

用于生成专业信息图的场景技能，基于 `u1-image-base`。完整说明见 [`skills/u1-infographic/SKILL.md`](skills/u1-infographic/SKILL.md)。

- 自动评估提示词质量
- 内容分析与版式/风格选择（87 种版式、66 种风格）
- 多轮图像生成与 VLM 评审
- 质量排序并输出最佳结果

## 快速开始

在 [OpenClaw](https://openclaw.ai/) 中使用本仓库技能。
目录需符合 [Agent Skills](https://agentskills.io/) 约定；OpenClaw 如何发现并加载技能文件夹见 [OpenClaw Skills](https://docs.openclaw.ai/tools/skills)。
若尚未完成 OpenClaw 的安装或配置，请通过 **[官方文档](https://docs.openclaw.ai/)** 进行安装与配置（产品介绍：[openclaw.ai](https://openclaw.ai/)）。

### 1. 注册 `u1-image-base` 与 `u1-infographic`

克隆本仓库后，须将 **两个** 技能目录暴露给 OpenClaw（见 [Locations and precedence](https://docs.openclaw.ai/tools/skills#locations-and-precedence)）。`u1-infographic` 依赖 `u1-image-base`，两者皆需安装。

可选用以下任一方式：

| 方式 | 做法 |
|------|------|
| **工作区 `skills/`**（常用） | 将 `skills/u1-image-base` 与 `skills/u1-infographic` 复制或符号链接到智能体工作区，路径为 `./skills/u1-image-base/` 与 `./skills/u1-infographic/`。 |
| **本机共享** | 将同样两个目录复制或符号链接到 `~/.openclaw/skills/`。 |
| **`openclaw.json`** | 通过 `skills.load.extraDirs` 将本仓库的 `skills` 目录（两个技能目录的父目录）配置为绝对路径（示例如下）。 |

```json5
{
  skills: {
    load: {
      extraDirs: ["/absolute/path/to/SenseNova-Skills/skills"],
    },
  },
}
```

将路径替换为你的克隆路径。详情见 [Skills config](https://docs.openclaw.ai/tools/skills-config)。若名称相同，工作区技能优先于 `extraDirs`。

### 2. Python 依赖与 API 密钥

在 OpenClaw 运行 [`skills/u1-image-base/u1_image_base/openclaw_runner.py`](skills/u1-image-base/u1_image_base/openclaw_runner.py)（上述工具的统一直达入口）时所使用的 **Python 环境与进程**中安装依赖并配置密钥：

```bash
pip install -r skills/u1-image-base/requirements.txt
# 图像生成
export U1_API_KEY="your-image-api-key"
# LLM/VLM
export U1_LM_API_KEY="your-lm-api-key"
export U1_LM_BASE_URL="your-lm-base-url"
```

请使用环境变量或本地 `.env` 文件。不要将密钥提交到版本库。

### 3. 在 OpenClaw 中调用

检查环境并交互式配置缺失的变量：

> /skill u1-doctor

在对话中描述任务，例如：

> 「做一张解释水循环的信息图」

或按名称调用技能：

> /skill u1-infographic "水循环"

## 示例输出

以下为 `u1-infographic` 的示例（更多示例见 [`u1-infographic-examples_CN.md`](docs/u1-infographic-examples_CN.md)）。

### 示例 1｜HEALTH_CHECK_PROMO

**User prompt:** `"HEALTH_CHECK_PROMO"`

#### Expanded prompt

```text
The infographic is titled "HEALTH_CHECK_PROMO.exe", styled as a retro computer application window with a pink title bar and standard window controls (close, minimize, maximize) in the top-right corner. The overall design mimics a 90s-era software interface with a grid background, pixelated icons, and bold, colorful sections. The primary color scheme includes bright yellow, purple, pink, blue, and green, creating a high-contrast, energetic aesthetic.

At the top, under the title bar, is a section labeled "Campaign Info" with fields for "Event Name:", "Date:", and "Coordinator:". Adjacent to this is an "HP Loading Bar" with a red heart icon, showing a segmented progress bar filled with green, yellow, and pink segments—indicating health or completion status.

Below this header, the main content is organized into three vertical columns representing a workflow:

1. **TO PROMOTE** (pink background):
   - Header: "TO PROMOTE" with a red circle labeled "Urgent".
   - Contains three blank rectangular input boxes.
   - Decorated with pixelated yellow band-aids and arrows indicating movement or prioritization.
   - A ">>>" symbol at the bottom suggests progression.

2. **LIVE DOING** (blue background):
   - Header: "LIVE DOING" with a yellow circle labeled "In-Progress".
   - Contains three blank rectangular input boxes.
   - Each box has small black or yellow squares on the left, possibly indicating status or priority.
   - Pixelated white cursor icons with sparkles point toward each box, suggesting active tasks.

3. **PUBLISHED** (yellow background):
   - Header: "PUBLISHED" with a green circle labeled "Healthy/Published".
   - Contains three blank rectangular input boxes.
   - Each box has a pink checkmark and a "DONE" stamp in the bottom-right corner, signifying completion.

Beneath these columns is a section titled "Media Milestones", displayed as a horizontal timeline with a black electrocardiogram (ECG) line. Three pixelated red hearts mark key points along the ECG:

- **Milestone 1: Pre-heat**
- **Milestone 2: Live Coverage**
- **Milestone 3: Recap & Insights**

Each milestone is linked to a blank rectangular box below for additional notes or details.

At the bottom of the infographic are two side-by-side panels:

- **Med-Team** (pink header):
  - Contains four circular placeholder icons for team members, each with a plus sign above or below, indicating expandability or addition.
  - Standard window controls (minimize, maximize, close) are present in the top-right.

- **Blockers** (pink header):
  - Contains a single green pixelated virus/bug icon with a skull face, symbolizing obstacles or issues.
  - Also includes window controls in the top-right.

The entire layout is framed by decorative elements: pixelated red crosses (like medical symbols), a pixelated hand cursor on the right, and scattered pixelated handheld gaming devices (resembling Game Boys) in pink and yellow. The background features a split of bright yellow and purple with grid patterns, reinforcing the retro digital theme.

All text is rendered in a bold, pixelated font consistent with early computer graphics. No numerical data beyond the segment counts in the HP bar is explicitly presented; all values are categorical or qualitative. The infographic serves as a dynamic, gamified project management tool for tracking promotional campaigns.
```

![示例信息图输出 — HEALTH_CHECK_PROMO](docs/images/demo8.webp)

### 示例 2｜流媒体：无界分发

**User prompt:** `"流媒体：无界分发"`

#### Expanded prompt

```text
信息图以赛博朋克风格的未来都市为视觉背景，整体采用垂直三段式布局，通过动态画面、科技元素与文字叠加，系统呈现“流媒体：无界分发”的核心主题。主色调为深蓝、紫粉与霓虹青色，营造出雨夜中数据流动的沉浸感，配合大量悬浮屏幕、发光管道与电子符号，强化科技氛围。

顶部标题为“流媒体：无界分发”，字体采用粗体无衬线字型，边缘带有青紫渐变光晕，置于黑色背景条上，极具视觉冲击力。

第一部分（上部）：
- 背景：高耸摩天大楼林立，布满悬挂式透明显示屏，播放着人物影像或界面内容，部分屏幕可见YouTube图标与视频播放进度条。
- 文字框1：“在矩阵中，每一次播放，都是跨越终端的灵魂共振。”位于左下方，背景为黑底青边，左侧标注“云端节点”。
- 视觉细节：建筑上有中文霓虹招牌如“云造街道”、“超清深潜”、“酒”、“食”等，增强场景真实感。

第二部分（中部）：
- 主体角色：一位女性赛博格形象，身穿紧身高科技战甲，面部有蓝色数据投影，机械臂握持带电蓝色管线，电流闪烁。
- 面部投影文字包括：“106.750.25&”、“BVB434E”、“B4V69G”、“65365818”、“HOOA: E3R 6Z8”、“000 0X-E4”等模拟数据流。
- 文字框2：“我能看见每一帧跳动的像素底色。”位于角色右侧，黑底白字，青边框。
- 文字框3：“解码协议：8K 120fps……无缓冲渲染成功。”位于左下角，黑底白字，青边框，左侧标注“超清深潜”。

第三部分（下部）：
- 动态场景：同一位女性角色在城市高速飞行，身后拖曳紫色光轨，前方是巨大发光“SHARE”标志。
- 右侧可视化网络结构：从“SHARE”出发，辐射出多个P2P节点与文件图标（如PDF、MP4、ZIP），用闪电状线条连接，象征数据分发网络。
- 文字框4：“点击分享，让视界呈指数级扩散。”位于左下角，黑底白字，青边框，下方标注“全网广播”。
- 文字框5：“多端同步通道已全域开启。”位于右下角，黑底白字，青边框。

整体设计融合了科幻美学与技术叙事，通过三个递进场景——云端传输、超清解码、全球共享——构建完整流媒体服务链条，所有文本均为中文，语言风格充满未来感与诗意，精准传达“无界分发”的技术愿景。
```

![示例信息图输出 — 流媒体：无界分发](docs/images/demo2.webp)

## 许可

MIT — 详见 [LICENSE](LICENSE)。
