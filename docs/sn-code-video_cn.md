# 代码视频创作

[English](sn-code-video.md) | 简体中文

[`sn-code-video`](../skills/sn-code-video/SKILL.md) 将创作需求转化为用代码绘制、
可播放的 MP4，适用于科普解释、程序化动画、动态图形、宣传片、3D 场景和音乐视频，
可配合旁白、音乐与音效。滚动驱动的网页叙事使用 `sn-motion-html`。

## 环境要求

- 支持 Agent Skills 的 Agent，具备命令执行和图片查看能力，以便检查渲染结果。
- 浏览器捕获需要 Node.js 18+；若 Agent 运行时要求更高版本，以运行时要求为准。
- Python 3、FFmpeg/ffprobe，支持 libx264、AAC，以及检查脚本使用的滤镜
  （`drawtext`、`blackdetect`、`freezedetect`、`ebur128`、`astats`、`silencedetect`）。
- 覆盖视频语言的字体，可用 `fc-list` 检查。
- 浏览器渲染需要在视频项目中安装 Playwright + Chromium，或 Puppeteer 及其浏览器。
  Manim、Node Canvas 等其他渲染方式需安装各自依赖。
- 声音工作流的 Python 依赖见 Skill 内的 `requirements.txt`。
  `edge-tts` 需要联网，`faster-whisper` 转录检查需要相应模型权重。

随附的渲染与检查工具不需要 SenseNova 图片或视频 API Key。
Agent 的语言模型配置见 [INSTALL_CN.md](../INSTALL_CN.md)。

## 安装与准备

按照仓库[安装指南](../INSTALL_CN.md)安装完整的 `skills/sn-code-video/` 目录，
保留其中的 `references/`、`scripts/` 和 `requirements.txt`。

以下命令从克隆的 **SenseNova-Skills 仓库根目录**开始执行。
若已将 Skill 安装到 Agent 中，将 `SKILL_DIR` 替换为实际安装目录的绝对路径。

```bash
export SKILL_DIR="$PWD/skills/sn-code-video"
mkdir -p ../my-code-video
cd ../my-code-video
npm install playwright
npx playwright install chromium
```

Linux 上若缺少 Chromium 系统库，且环境允许安装系统依赖，可使用 Playwright 的
安装命令 `npx playwright install --with-deps chromium`。
需要声音时，在项目虚拟环境中安装 Python 依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r "$SKILL_DIR/requirements.txt"
```

源码、构建文件和输出放在**视频项目目录**。每个新的 Shell 会话重新设置 `SKILL_DIR`，
并通过绝对路径调用随附脚本，确保 Skill 安装到 `~/.openclaw/skills/` 或
`~/.hermes/skills/` 后仍能正确定位工具。

## 调用示例

> 使用 sn-code-video 制作一个 12 秒、1920×1080、30 fps 的科普视频，解释单摆的动能
> 与势能如何转化。使用中文标注、程序化音效，不要旁白。交付 out/final.mp4、源码、
> 复现命令、SPEC.md、VERIFY.md 和联系表。阅读相关指南，检查实际渲染画面并验证最终文件。

## 工作流与工具

1. 根据 Skill 中的路由表，只读取本次任务需要的创作指南。
2. 编写 `SPEC.md`，明确文案、事实、素材、时长、尺寸、帧率、声音策略及验收项。
   长视频另写 `STRUCTURE.md`。
3. 将每一帧实现为时间的确定性函数。浏览器页面暴露 `window.seek(t)`，
   字体和素材加载完成后设置 `window.READY = true`。
4. 先捕获少量帧，再尽早产出完整粗剪，随后逐步改善。
5. 查看关键帧、联系表、动作连续帧并按正常速度播放，完成至少两轮检查。
6. 需要声音时，阅读声音指南、编写 `SOUND.md`，从动画时间线导出事件，
   据此制作声音、合成并检查同步。
7. 检查实际交付文件，在 `VERIFY.md` 中逐项记录验收证据。

在视频项目目录执行以下命令（需先准备好 `index.html`）：

```bash
node "$SKILL_DIR/scripts/capture.mjs" . --page index.html \
  --fps 30 --dur 12 --size 1920x1080 --frames 3 --out out/smoke.mp4
node "$SKILL_DIR/scripts/capture.mjs" . --page index.html \
  --fps 30 --dur 12 --size 1920x1080 --out out/video.mp4
sh "$SKILL_DIR/scripts/contact_sheet.sh" out/video.mp4 out/sheet.jpg 1
sh "$SKILL_DIR/scripts/check_video.sh" out/video.mp4 1920 1080 30 12 12 0
```

`capture.mjs` 输出不含音轨的 MP4。`check_video.sh` 最后一个参数为 `0` 时禁止音轨，
为 `1` 时要求音轨，省略时仅报告音轨情况。有声音的视频须先合成到 `out/final.mp4`，
用参数 `1` 检查最终文件，再执行：

```bash
sh "$SKILL_DIR/scripts/audio_check.sh" out/final.mp4 -14
python3 "$SKILL_DIR/scripts/sync_check.py" out/final.mp4 build/events.json --fps 30
```

8 份创作指南覆盖：解释图解、风格化视觉、模拟与生成、角色动作、Three.js 场景与摄影机、
动态图形与宣传片、声音与旁白、音乐节拍同步。声音指南还介绍了 `tts.py` 和可导入的
`synth.py` 程序化声音工具。

## 交付与失败处理

交付最终 MP4、可编辑源码与素材、复现命令、`SPEC.md`、`VERIFY.md` 和联系表；
有声音时保留分轨及时间数据。

Chromium 无法启动时，修复缺失依赖或改用适合的 Node Canvas / Manim 渲染方案。
TTS 不可用时，如实报告旁白缺失，不能用静音轨代替并标记验收通过。
未解决的渲染、画面或声音问题必须明确记入 `VERIFY.md`。

## 来源

整合自 OpenSenseNova 的
[`code-video` Skill](https://github.com/OpenSenseNova/SenseNova-6.8-Code2Video/tree/776ae79824e338ba5d63fef66167455edc94ad26/skills/code-video)。
按本仓库规范使用 `sn-` 命名和 `references/` 目录，保留原始制作工作流、8 份创作指南及 7 个辅助脚本。
