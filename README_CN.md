<p align="center">
  <img src="assets/logo.webp" alt="SenseNova logo" width="180" />
</p>

# SenseNova-Skills

简体中文 | [English](README.md)

SenseNova系列模型可直接接入 [OpenClaw](https://openclaw.ai/)、[hermes-agent](https://github.com/nousresearch/hermes-agent) 等智能体，并借助skills实现更强大的能力。

本项目每个技能位于独立目录中，通过 `SKILL.md` 声明触发条件、能力边界和执行方式，遵循 [Agent Skills](https://agentskills.io/) 规范。

技能覆盖 **图像生成与可视化**、**演示文稿生成**、**Excel 数据分析**、**深度研究**  等场景，可独立使用，也可组合成端到端工作流。

## 如何使用

**本仓库的 skill 需要配合支持 [Agent Skills](https://agentskills.io/) 规范的智能体使用，推荐 [OpenClaw](https://openclaw.ai/) 或 [hermes-agent](https://github.com/NousResearch/hermes-agent) 获得最佳效果。完整的安装、LLM 配置与 skill 加载流程请参考 [`INSTALL_CN.md`](INSTALL_CN.md)。**

克隆本仓库后，把 `skills/` 下的子目录复制（或软链接）到所用智能体加载的 skills 目录：

| 智能体 | 目标目录 |
|--------|---------|
| [OpenClaw](https://openclaw.ai/) | `~/.openclaw/skills/` |
| [hermes-agent](https://github.com/nousresearch/hermes-agent) | `~/.hermes/skills/` |

例如，把全部技能复制到 OpenClaw：

```bash
git clone https://github.com/OpenSenseNova/SenseNova-Skills.git
mkdir -p ~/.openclaw/skills
cp -r SenseNova-Skills/skills/* ~/.openclaw/skills/
```

Hermes 把目录换成 `~/.hermes/skills/` 即可。

各分类技能的 Python 依赖、API key 与调用示例同样请参考对应分类的 📖 详细使用指南。

## 技能列表

### 🎨 图像与可视化

📖 详细使用指南：[`docs/sn-image-generate.md`](docs/sn-image-generate.md)（环境要求、Quick Start、API 配置与调用样例）。


| 名称                                                 | 标签            | 描述                                                                                              |
| -------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------- |
| [`sn-image-doctor`](skills/sn-image-doctor/SKILL.md)           | 环境诊断          | 检查 SenseNova-Skills 环境，验证 `sn-image-base` 安装、Python 依赖与必填环境变量；交互式补齐缺失项并写入 `.env`。               |
| [`sn-image-base`](skills/sn-image-base/SKILL.md)   | 图像基础层（Tier 0） | 提供文生图（`sn-image-generate`）、图像识别（`sn-image-recognize`）与文本优化（`sn-text-optimize`）三个底层工具，统一通过 `sn_agent_runner.py` 调用，供上层技能复用。 |
| [`sn-infographic`](skills/sn-infographic/SKILL.md) | 信息图生成（Tier 1） | 自动评估提示词、从 87 种布局 / 66 种风格中选型，多轮生成 + VLM 评审 + 质量排序，输出专业级信息图。                                     |


### 📊 演示文稿（PPT）

📖 详细使用指南：[`docs/ppt-generate.md`](docs/ppt-generate.md)（环境要求、Quick Start、API 配置与调用样例）。


| 名称                                             | 标签         | 描述                                                                                                                         |
| ---------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------- |
| [`sn-ppt-entry`](skills/sn-ppt-entry/SKILL.md)       | **PPT 入口** | **PPT 生成功能的统一入口**，收集角色 / 受众 / 场景 / 页数 / 模式（创意 or 标准），解析 pdf / docx / md / txt 输入，产出 `task_pack.json` + `info_pack.json` 并分派到下游模式。 |
| [`sn-ppt-doctor`](skills/sn-ppt-doctor/SKILL.md)     | PPT 环境诊断   | PPT 流水线的环境检查，验证 `sn-image-base`、API key、Node 运行时与可选依赖；按需写入 `.env`。                                                         |
| [`sn-ppt-creative`](skills/sn-ppt-creative/SKILL.md) | PPT 创意模式   | 每页一张 16:9 全图（PNG），按页面构图 prompt 走 `sn-image-generate` 一次性出图。                                                                |
| [`sn-ppt-standard`](skills/sn-ppt-standard/SKILL.md) | PPT 标准模式   | `style_spec` → 大纲 → 资产规划 + 分槽位图像 + VLM 质检 → 分页 HTML → 分页评审（可选重写）→ 汇总 `review.md` → 导出 PPTX。                                |


### 📈 数据分析（DA）

📖 详细使用指南：[`docs/data-analysis.md`](docs/data-analysis.md)（环境要求、Quick Start、API 配置与调用样例）。


| 名称                                                                 | 标签         | 描述                                                                               |
| ------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------- |
| [`sn-da-excel-workflow`](skills/sn-da-excel-workflow/SKILL.md)           | Excel 分析编排 | Excel 多表读取、大文件检测（≥10k 行触发 Parquet 优化）、清洗、条件过滤、跨表聚合、Excel/CSV 导出的全流程编排。           |
| [`sn-da-image-caption`](skills/sn-da-image-caption/SKILL.md)             | 图像理解与数据提取  | 图像类输入做表格 OCR / 图表解读 / 截图描述 / UI 描述；可解析为 DataFrame、复绘可视化、导出 Excel/CSV。            |
| [`sn-da-large-file-analysis`](skills/sn-da-large-file-analysis/SKILL.md) | 大文件高性能分析   | ≥10k 行 Excel 的流式读取（openpyxl read_only + iter_rows）、Parquet 转换、内存优化、分块处理与大文件写入模式。 |


### 🔬 深度研究

📖 详细使用指南：[`docs/deep-research.md`](docs/deep-research.md)（环境要求、`web_search` 硬检查、Quick Start 与各阶段调用）。


| 名称                                                                   | 标签        | 描述                                                                                      |
| -------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------- |
| [`sn-deep-research`](skills/sn-deep-research/SKILL.md)                     | **深度研究入口** | **深度研究功能的统一入口**，规划 → 分维度取证 → 综合 → 成稿（`report.md`）的全流程编排器，产物落盘到 `report_dir`，支持断点续跑。 |
| [`sn-research-planning`](skills/sn-research-planning/SKILL.md)             | 研究规划      | 基于 `request.md` 一次性产出 `plan.json`，覆盖定界、报告形态、维度拆解、关键问题、搜索策略、依赖与完成标准。                     |
| [`sn-dimension-research`](skills/sn-dimension-research/SKILL.md)           | 单维度取证     | 按 `plan.json` 中维度的 `search_strategy` 调用搜索、筛选证据、交叉验证，产出 `sub_reports/{dimension_id}.md`。 |
| [`sn-research-synthesis`](skills/sn-research-synthesis/SKILL.md)           | 综合判断      | 把多个 `sub_reports` 综合为 `synthesis.md`，明确主线判断、证据强弱、跨维度共识、关键冲突与不确定性。                       |
| [`sn-research-report`](skills/sn-research-report/SKILL.md)                 | 终稿写作 / 改写 | 把判断层落成最终 `report.md`；也可对已有报告做重写、润色、重组结构、补充表格等定向编辑。                                      |
| [`sn-report-format-discovery`](skills/sn-report-format-discovery/SKILL.md) | 报告形态发现    | 研究"这类报告应该长什么样"，给出章节结构、必备元素与风格约束；可独立使用，也可为 sn-deep-research 的 `report_shape` 提供依据。          |
| [`sn-md-to-html-report`](skills/sn-md-to-html-report/SKILL.md)             | Markdown → HTML 报告 | 把研究产出的 `report.md`（或任意 Markdown 文档）转换成单文件、可离线打开的 HTML 阅读视图——内嵌图片、侧栏目录、自适应表格，并自动修复表格分隔符。 |


### 🔍 搜索

📖 搜索技能与深度研究合并在同一份文档：[`docs/deep-research.md`](docs/deep-research.md)（含各平台 API key、调用方式与统一 JSON 输出）。


| 名称                                                     | 标签     | 描述                                                                                          |
| ------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------- |
| [`sn-search-academic`](skills/sn-search-academic/SKILL.md)   | 学术搜索   | ArXiv（含 HTML 全文按章节读）/ Semantic Scholar（含引用数）/ PubMed（含 PMC 开放获取全文）/ Wikipedia 四平台聚合。        |
| [`sn-search-code`](skills/sn-search-code/SKILL.md)           | 开发者搜索  | GitHub（仓库 / 代码 / Issue）/ Stack Overflow / Hacker News / HuggingFace（模型 / 数据集 / Space）四平台聚合。 |
| [`sn-search-social-cn`](skills/sn-search-social-cn/SKILL.md) | 中文社交搜索 | B 站 / 知乎 / 抖音 三个中文社交平台搜索；部分平台需 cookie 认证。                                                   |
| [`sn-search-social-en`](skills/sn-search-social-en/SKILL.md) | 英文社交搜索 | Reddit / Twitter (X) / YouTube 三个英文社交平台搜索。                                                  |


## 输出样例

### 🎨 信息图（sn-infographic）

`sn-infographic` 的部分生成效果（更多样例见 [`docs/sn-infographic-examples_CN.md`](docs/sn-infographic-examples_CN.md)）。

<p align="center"><img src="docs/images/teaser_v1.1.webp" width="800" alt="sn-infographic 生成效果合集"></p>

### 📊 演示文稿（sn-ppt-standard / sn-ppt-creative）

`sn-ppt-standard` 与 `sn-ppt-creative` 的部分生成效果（更多样例见 [`docs/ppt-examples.md`](docs/ppt-examples.md)）。

<!-- TODO: 补充 PPT 样例图片 -->

### 🔬 深度调研（sn-deep-research）

`sn-deep-research` 编排产出的报告样例（更多样例见 [`docs/deep-research-examples.md`](docs/deep-research-examples.md)）。

<!-- TODO: 补充深度调研报告样例截图或链接 -->

## 贡献

欢迎以本仓库的技能为模板创建你自己的 OpenClaw 技能。一个好技能的核心要素：

- **清晰的触发条件**：在 `description` 中写明"什么时候用 / 什么时候不用"，让智能体准确识别
- **聚焦的能力边界**：每个技能只把一件事做好，复杂工作流通过多个技能编排实现
- **完善的文档**：包含示例、产物约定、边界情况与失败处理
- **必要的支撑资源**：通过 `references/`、`scripts/`、`prompts/` 提供补充上下文

## 许可证

MIT — 详见 [LICENSE](LICENSE)。
