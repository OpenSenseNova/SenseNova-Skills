# PPT 生成相关技能

简体中文 | [English](sn-ppt-generate_en.md)

本文档汇总演示文稿（PPT）生成相关技能（`sn-ppt-entry`、`sn-ppt-story`、`sn-ppt-standard`、`sn-ppt-dazzle`、`sn-ppt-creative`、`sn-ppt-doctor`、`sn-ppt-tools`、`sn-ppt-workbench`），用于在 Hermes / OpenClaw 中按用户需求生成演示文稿（Static HTML、Dynamic HTML、Creative 三种出口，可导出 PPTX）。

## 环境要求

- **Python** 3.9 或更高版本（推荐 3.10+）。
- **Node.js** 运行时（`sn-ppt-standard` 在分页 HTML 处理阶段使用）。
- 需要 LLM/VLM 与文生图 API 凭据（详见下文）。

## 技能介绍

| 名称 | 角色 | 说明 |
|------|------|------|
| [`sn-ppt-entry`](../skills/sn-ppt-entry/SKILL.md) | **PPT 入口** | 收集角色 / 受众 / 场景 / 页数 / 模式（创意 or 标准），解析 pdf / docx / md / txt 输入，产出 `task_pack.json` + `info_pack.json` 并分派到下游模式。 |
| [`sn-ppt-doctor`](../skills/sn-ppt-doctor/SKILL.md) | PPT 环境诊断 | 检查本地渲染/导出依赖（Python/Node Playwright、Chromium、PPTX exporter）与 Bundled 媒体配置；只报告，不写 `.env`、不修改任务目录。 |
| [`sn-ppt-creative`](../skills/sn-ppt-creative/SKILL.md) | PPT 创意模式 | 每页一张 16:9 全图（PNG），按页面构图 prompt 出图后导出 PPTX。 |
| [`sn-ppt-standard`](../skills/sn-ppt-standard/SKILL.md) | PPT 标准模式 | `style_spec` → 大纲 → 资产规划 + 分槽位图像 + VLM 质检 → 分页 HTML → 分页评审（可选重写）→ 汇总 `review.md` → 导出 PPTX。 |
| sn-ppt-story | PPT 编排 | 将 query、全部用户材料与已完成 Research 编排为唯一可编辑的 outli
ne.md；是入口到出口（standard / dazzle / creative）之间的强制中间环节，不得跳过或代写。 |
| sn-ppt-dazzle | PPT 动态模式 | 将已备好的 outline.md 制作为 1280×720 单文件动态 HTML 演示
文稿（动效、跨页过渡、键盘翻页），用于需要动态/交互效果的演示场景。 |
| sn-ppt-tools | Bundled 工具回退 | 宿主原生搜索/生图工具缺失或失败时提供回退：普通搜索、图
片搜索、图片生成与下载；读取 .env 中的 SN_PPT_* 配置。 |
| sn-ppt-workbench | PPT 编辑工作台 | 启动或复用 AI PPT 编辑 WebUI，在浏览器中预览、在线微调
已生成的 deck。 |

模型对话、视觉理解与生图优先使用宿主 Agent 的原生工具；原生缺失或失败时由 `sn-ppt-tools` 提供 Bundled 回退（普通搜索、图片搜索、生图）。

## Quick Start

在 Hermes 下将本仓库 `skills/` 目录中的 `sn-ppt-*` 整包拷贝或软链到 `~/.hermes/skills/` 即可注册；OpenClaw 放入 `~/.openclaw/skills/`。各宿主的安装步骤见仓库根 [`README_CN.md`](../README_CN.md#如何使用) 的「如何使用」章节。

### 1. Python 依赖

```bash
# sn-ppt-entry：解析 PDF / DOCX
pip install -r skills/sn-ppt-entry/requirements.txt

# sn-ppt-creative：导出 PPTX
pip install -r skills/sn-ppt-creative/requirements.txt

# sn-ppt-standard：首次部署运行其自带安装脚本（venv、字体、Chromium 等）
bash skills/sn-ppt-standard/scripts/install.sh
```

`sn-ppt-doctor` / `sn-ppt-tools` 仅用 Python 标准库；`sn-ppt-story` 为纯编排，无额外依赖；`sn-ppt-dazzle` 自带渲染脚本并复用已安装的 Chromium。`sn-ppt-entry` 依赖 `pypdf` / `python-docx` / `PyMupdf`；`sn-ppt-standard` 的 HTML 渲染依赖 Python Playwright Chromium，首次部署用
`scripts/install.sh` 安装（该脚本同时装 normalize venv、OFL 字体、FontTools/Brotli/Pillow）。

HTML → PPTX 导出（`scripts/export_pptx/`）需要 Node.js 运行时；npm 包（`pptxgenjs` / `echarts` / `playwright`）随技能目录自带 `node_modules`，
但其 Playwright Chromium 浏览器二进制需单独安装：

```bash
npm --prefix skills/sn-ppt-standard/scripts/export_pptx exec playwright install chromium
```

> Linux 提示：Python 渲染（`render.py`）缺系统动态库时会自动从 `~/pwdeps/lib`（再退 `~/cdeps/lib`）
> 补进 `LD_LIBRARY_PATH`；但 HTML → PPTX 导出是独立 Node 进程，没有该逻辑。若导出报 Chromium 启动
> 失败（如缺 `libnspr4.so` 等），把含这些库的目录加入 Agent 进程的 `LD_LIBRARY_PATH`，
> 或按 `sn-ppt-doctor` 输出中的 `install_hint` 处理。

### 2. API Key 与环境变量

LLM 对话、视觉理解与页面评审直接使用宿主 Agent 的原生模型能力，**无需为本套件配置模型变量**。
仅当宿主原生搜索 / 生图工具不存在或调用失败、需要走 Bundled 回退时，才需要配置以下变量。
将变量写入 `~/.hermes/.env`（Hermes）或 `~/.openclaw/.env`（OpenClaw）；
也可用 `SN_PPT_ENV_FILE=/absolute/path/to/file` 指定自定义文件。已有进程环境变量优先于文件值。
`sn-ppt-doctor` 会输出实际读取的 `.env` 路径与缺失字段（不输出 key 值）。

```ini
# 普通搜索与图片搜索共用（Bundled 回退）：默认请求 google.serper.dev
SN_PPT_SEARCH_API_KEY="<search-api-key>"

# 图片生成（Bundled 回退）：OpenAI / SenseNova 兼容的同步 /images/generations 接口
SN_PPT_IMAGE_GEN_URL="https://your-host/images/generations"
SN_PPT_IMAGE_GEN_API_KEY="<image-generation-api-key>"
SN_PPT_IMAGE_GEN_MODEL="<image-generation-model>"
```

回退链：搜索 URL 也可用 `SN_PPT_SEARCH_BASE_URL` / `SERPER_BASE_URL`（缺省 google.serper.dev），
key 也可用 `SERPER_API_KEY`；生图 URL 回退 `SN_IMAGE_GEN_BASE_URL` / `SN_BASE_URL` + `/images/generations`，
key 回退 `SN_IMAGE_GEN_API_KEY` / `SN_API_KEY`，model 回退 `SN_IMAGE_GEN_MODEL`。
完整检查项见 [`skills/sn-ppt-doctor/SKILL.md`](../skills/sn-ppt-doctor/SKILL.md)。

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
