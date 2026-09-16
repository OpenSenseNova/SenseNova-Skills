---
name: sn-ppt-doctor
description: Use when diagnosing PPT Skill setup or failures involving source parsing, Playwright or Chromium rendering, HTML-to-PPTX export, Workbench startup, or bundled search and image-tool configuration.
metadata:
  project: SenseNova-Skills
  tier: aux
  category: diagnostic
  user_visible: true
triggers:
  - "sn-ppt-doctor"
  - "ppt 体检"
---

# sn-ppt-doctor

这是按需运行的能力与本地依赖检查，不是 Entry 的强制前置。Doctor 分开报告：

1. 当前 Agent 的普通搜索、图片搜索和图片生成原生工具是否注册、配置或实际验证；
2. PPT 整包自带的 `sn-ppt-tools` 是否存在并已配置。

Doctor 不检查或恢复 `sn_agent_runner.py`，不写 `.env`，也不把可选媒体能力变成硬门槛。

## 持久配置

PPT 内置工具与 Doctor 自动读取：

- Hermes：`~/.hermes/.env`
- OpenClaw：`~/.openclaw/.env`
- 自定义：先设置 `SN_PPT_ENV_FILE=/absolute/path/to/file`

已有进程变量优先于文件值。推荐配置：

```ini
# 搜索和搜图共用；默认请求 google.serper.dev
SN_PPT_SEARCH_API_KEY="<search-api-key>"

# OpenAI/SenseNova 兼容的同步 /images/generations 接口
SN_PPT_IMAGE_GEN_URL="https://your-host/images/generations"
SN_PPT_IMAGE_GEN_API_KEY="<image-generation-api-key>"
SN_PPT_IMAGE_GEN_MODEL="<image-generation-model>"
```

用户只需编辑一次文件，不需要每次启动 Hermes 前执行 `export`。Doctor 输出实际读取的文件、
已采用的变量名和缺失字段，但不得输出 key 值。

## 检查内容

- 当前 workspace 是否可写，`<pwd>/ppt_decks` 是否可用；
- `pypdf`、`python-docx` 是否可用于附件解析；
- Standard HTML 渲染所需的 Python Playwright 是否存在；
- 当前解释器缺少 Playwright 时，先保留 bare Python 的 pip 安装路径，再检查已安装的
  `uv tool` Playwright 是否可作为可选隔离环境；
- Playwright Chromium 是否已经安装并能实际启动（不是只检查脚本文件）；
- Node.js 是否可用于 Workbench 和 Static 默认 HTML -> PPTX 兼容版导出；
- HTML -> PPTX 所需的 npm、`pptxgenjs`、`echarts`、Node Playwright 是否可解析，以及该
  Playwright 的 Chromium 是否能实际启动；
- Standard 渲染脚本、PPTX exporter 和 Workbench runtime 是否存在；
- `python-pptx` 是否可用于 Creative 整页图片打包。
- `sn-ppt-tools` 的四个脚本是否存在；
- 内置普通搜索、图片搜索和图片生成的 URL 是否有效，key/model 是否已配置；
- 实际加载的 `.env` 路径、无效行和缺失字段。

## 原生工具有效性

**工具出现在 Agent 工具列表中不等于可用。** Doctor 必须使用以下状态：

| 状态 | 含义 |
|---|---|
| `absent` | 当前 Agent 没有对应工具 |
| `present_unverified` | 工具已注册，但没有配置检查或成功调用证据 |
| `misconfigured` | 工具或已知配置检查明确报告缺少 URL、key、model 等 |
| `available` | 无费用 config/health 检查通过，或一次真实调用成功 |
| `failed` | 真实调用已经失败 |

运行 Doctor Skill 的 Agent 必须：

1. 检查当前实际工具列表，没有工具时写 `absent`。
2. 有工具时先寻找该工具暴露的 config/health 状态；明确缺配置时写 `misconfigured`。
3. 没有无费用检查时只能写 `present_unverified`，不得因工具名称存在就写 `available`。
4. 用户要求完整检查时，普通搜索和搜图各做一次最小真实调用。
5. 生图真实探测可能收费，必须先获得用户明确同意；未探测前保持
   `present_unverified`，除非已有明确缺配置证据。

本地脚本无法读取 Agent 工具注册表，所以只报告 Bundled 配置事实，并在 `native_media`
中返回 `agent_inspection_required`。Doctor Skill 负责把 Native 与 Bundled 两层并列呈现，
再给出 effective source：

- 经过验证的 Native；
- 否则已配置或已探测成功的 Bundled；
- 两者都不可确认时为 None。

缺少某个可选依赖只影响对应能力，不应阻止其他出口。例如没有 Node 时仍可使用宿主原生
PPTX 能力；HTML -> PPTX 失败时仍保留 HTML。

## 调用

```bash
python3 "$SKILL_DIR/ppt_doctor/check_environment.py"
```

默认命令不联网，只检查 Bundled 配置。显式探测 Bundled 搜索接口：

```bash
python3 "$SKILL_DIR/ppt_doctor/check_environment.py" --probe-search
```

Bundled 图片生成可能收费，只有用户明确要求时才执行：

```bash
python3 "$SKILL_DIR/ppt_doctor/check_environment.py" \
  --probe-image-generation \
  --probe-output-dir "/absolute/existing/directory"
```

Doctor 只报告，不安装依赖、不写 secret、不修改任务目录。`standard_html.status` 只有在
渲染脚本、Python Playwright 和 Chromium 实际启动都通过时才是 `available`；否则
`playwright_chromium.install_hint` 给出准备命令。报告中的 `python_source` 为
`current_interpreter` 或 `uv_tool`。前者始终先检查，缺包时的主安装提示保留
`python -m pip install -r requirements.txt`；只有当 Doctor 实际检测到已安装的 uv-tool
Playwright 时，才使用 `uv tool run --from playwright python ...`。
`html_to_pptx_environment.status` 只有在
导出脚本、Node 包和 Node Playwright Chromium 均可实际运行时才是 `available`，缺失时同样
给出准备命令。缺少媒体配置时仍以退出码 0 完成报告，并显示应编辑的 `.env` 路径和缺失项。
