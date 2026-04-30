# SN Image Generation Skills

English | [简体中文](sn-image-generate.md)

This document collects the SN (SenseNova) related skills (`sn-image-doctor`, `sn-image-base`, `sn-infographic`, `sn-image-resume`, `sn-image-imitate`) and the end-to-end Quick Start for using them in OpenClaw / Hermes.

## Prerequisites

- **Python** 3.9 or later (3.10+ recommended).
- **SN API** credentials for image generation and LLM/VLM endpoints (`SN_BASE_URL` and `SN_API_KEY` are enough when all capabilities use one gateway; see Quick Start).

## Skills

### sn-image-doctor

Environment diagnostic skill that checks installation, dependencies, and configuration. See [`skills/sn-image-doctor/SKILL.md`](../skills/sn-image-doctor/SKILL.md) for full behavior.

- Validates `sn-image-base` installation and Python dependencies
- Checks environment variables and interactively prompts to configure missing required variables
- Saves configuration to `.env` file and reloads environment automatically

### sn-image-base (Tier 0)

Base-layer infrastructure skill providing low-level tools for image generation, image recognition (VLM), and text optimization (LLM). See [`skills/sn-image-base/SKILL.md`](../skills/sn-image-base/SKILL.md) for full behavior.

- **sn-image-generate** — text-to-image generation
- **sn-image-recognize** — image recognition using VLM (supports multiple image inputs)
- **sn-text-optimize** — text processing/optimization using LLM

All tools are invoked through a unified `sn_agent_runner.py` entrypoint.

### sn-infographic (Tier 1)

Scene skill for generating professional infographics, built on `sn-image-base`. See [`skills/sn-infographic/SKILL.md`](../skills/sn-infographic/SKILL.md) for full behavior.

- Automatic prompt quality evaluation
- Content analysis and layout/style selection (87 layouts, 66 styles)
- Multi-round image generation with VLM review
- Quality ranking and best-result output

### sn-image-resume (Tier 1)

Scene skill for generating a designed portfolio-resume image, built on `sn-image-base`. See [`skills/sn-image-resume/SKILL.md`](../skills/sn-image-resume/SKILL.md) for full behavior.

- Accepts resume content directly from conversational text
- Supports optional user-provided style direction
- Applies fixed portfolio-resume layout rules
- Generates a tall designed resume image through `sn-image-generate`

### sn-image-imitate (Tier 1)

Scene skill for imitating the style of a reference image while updating content, built on `sn-image-base`. See [`skills/sn-image-imitate/SKILL.md`](../skills/sn-image-imitate/SKILL.md) for full behavior.

- Extracts high-fidelity long caption and layout blueprint from a reference image
- Rewrites caption according to user-requested content change while preserving style and layout
- Multi-round generation with layout consistency review and bounded retries
- Returns structured process artifacts for debugging and reproducibility

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/).
They follow the [Agent Skills](https://agentskills.io/) layout; see [OpenClaw Skills](https://docs.openclaw.ai/tools/skills) for how OpenClaw discovers and loads skill folders.
If you have not set up OpenClaw yet, install and configure it from the **[official documentation](https://docs.openclaw.ai/)** (product site: [openclaw.ai](https://openclaw.ai/)).

### 1. Register skills

Clone this repository, then expose the `skills/` directory to OpenClaw ([locations and precedence](https://docs.openclaw.ai/tools/skills#locations-and-precedence)) (or Hermes).

Use one of the following approaches:

| Approach | What to do |
|----------|------------|
| **Shared on this machine** | Copy or symlink subdirectories under `skills/` to `~/.openclaw/skills/` (OpenClaw) or `~/.hermes/skills/openclaw-imports/` (Hermes). |
| **Workspace `skills/`** | Copy or symlink `skills/sn-image-base`, `skills/sn-infographic`, `skills/sn-image-doctor`, `skills/sn-image-resume`, and `skills/sn-image-imitate` into your agent workspace. |
| **`openclaw.json` (OpenClaw only)** | Add an absolute path to this repo's `skills` folder (the parent of all skill directories) via `skills.load.extraDirs` (example below). |

```json5
{
  skills: {
    load: {
      extraDirs: ["/absolute/path/to/SenseNova-Skills/skills"],
    },
  },
}
```

Replace the path with your clone. Details: [Skills config](https://docs.openclaw.ai/tools/skills-config). Workspace skills win over `extraDirs` if the same name appears twice.

### 2. Python dependencies and API keys

Install packages and export keys in the **Python environment and process** OpenClaw uses when it runs [`skills/sn-image-base/scripts/sn_agent_runner.py`](../skills/sn-image-base/scripts/sn_agent_runner.py) (the unified runner for these tools):

```bash
pip install -r skills/sn-image-base/requirements.txt
```

**Minimum Configurations:**

We recommend you to try out our [SenseNova Token Plan](https://platform.sensenova.cn/token-plan) to setup these skills.

Go to <https://platform.sensenova.cn/token-plan/> to register a free account and get your API key.

Set the following environment variables in `~/.openclaw/.env` (for OpenClaw) or `~/.hermes/.env` (for Hermes):

```ini
SN_BASE_URL="https://token.sensenova.cn/v1"
SN_API_KEY="your-api-key"
```

Fallback priority is dedicated variable > domain shared variable > global variable. If a capability needs a different provider, set `SN_TEXT_*`, `SN_VISION_*`, `SN_CHAT_*`, or `SN_IMAGE_GEN_*`.

**Note:** Never commit `.env` files or API keys to git.

**Advanced Configurations:**

If you want to use different models for image generation (e.g. Nano Banana, GPT-Image-2) and LLM/VLM (e.g. GPT, Claude Sonnet 4.6),
Please see [`skills/sn-image-base/README.md`](../skills/sn-image-base/README.md) for detailed configurations.

### 3. Invoke in Agent

Check your environment variables before using the skills:

> Run the `sn-image-doctor` skill

Describe the task in chat, for example:

> "Create an infographic explaining the water cycle"

Or call the skill by name:

> /skill sn-infographic "The water cycle"

## Sample Outputs

Examples for `sn-infographic` (more examples in [`sn-infographic-examples.md`](sn-infographic-examples.md)).

### Example 1

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

![Sample infographic output — HEALTH_CHECK_PROMO](images/infographics/info_042.webp)

### Example 2｜Streaming Media: Borderless Distribution

**User prompt:** `"流媒体：无界分发"`

#### Expanded prompt

```text
信息图以赛博朋克风格的未来都市为视觉背景，整体采用垂直三段式布局，通过动态画面、科技元素与文字叠加，系统呈现"流媒体：无界分发"的核心主题。主色调为深蓝、紫粉与霓虹青色，营造出雨夜中数据流动的沉浸感，配合大量悬浮屏幕、发光管道与电子符号，强化科技氛围。

顶部标题为"流媒体：无界分发"，字体采用粗体无衬线字型，边缘带有青紫渐变光晕，置于黑色背景条上，极具视觉冲击力。

第一部分（上部）：
- 背景：高耸摩天大楼林立，布满悬挂式透明显示屏，播放着人物影像或界面内容，部分屏幕可见YouTube图标与视频播放进度条。
- 文字框1："在矩阵中，每一次播放，都是跨越终端的灵魂共振。"位于左下方，背景为黑底青边，左侧标注"云端节点"。
- 视觉细节：建筑上有中文霓虹招牌如"云造街道"、"超清深潜"、"酒"、"食"等，增强场景真实感。

第二部分（中部）：
- 主体角色：一位女性赛博格形象，身穿紧身高科技战甲，面部有蓝色数据投影，机械臂握持带电蓝色管线，电流闪烁。
- 面部投影文字包括："106.750.25&"、"BVB434E"、"B4V69G"、"65365818"、"HOOA: E3R 6Z8"、"000 0X-E4"等模拟数据流。
- 文字框2："我能看见每一帧跳动的像素底色。"位于角色右侧，黑底白字，青边框。
- 文字框3："解码协议：8K 120fps……无缓冲渲染成功。"位于左下角，黑底白字，青边框，左侧标注"超清深潜"。

第三部分（下部）：
- 动态场景：同一位女性角色在城市高速飞行，身后拖曳紫色光轨，前方是巨大发光"SHARE"标志。
- 右侧可视化网络结构：从"SHARE"出发，辐射出多个P2P节点与文件图标（如PDF、MP4、ZIP），用闪电状线条连接，象征数据分发网络。
- 文字框4："点击分享，让视界呈指数级扩散。"位于左下角，黑底白字，青边框，下方标注"全网广播"。
- 文字框5："多端同步通道已全域开启。"位于右下角，黑底白字，青边框。

整体设计融合了科幻美学与技术叙事，通过三个递进场景——云端传输、超清解码、全球共享——构建完整流媒体服务链条，所有文本均为中文，语言风格充满未来感与诗意，精准传达"无界分发"的技术愿景。
```

![Sample infographic output — Streaming Media: Borderless Distribution](images/infographics/info_088.webp)
