# SenseNova-Skills

[English](README.md) | [简体中文](README_CN.md)

Skills and tooling for **AIGC** in agent runtimes.

## Prerequisites

- **Python** 3.10 or later.
- **U1 API** credentials for image generation and LLM/VLM endpoints (`U1_API_KEY`, `U1_LM_API_KEY`; see Quick Start).

## Skills

### u1-image-base (Tier 0)

Base-layer infrastructure skill providing two low-level tools. See [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md) for full behavior.

- **u1-image-generate** — text-to-image generation
- **u1-text-optimize** — text processing using LLM

All tools are invoked through a unified `openclaw_runner.py` entrypoint.

### u1-infographic (Tier 1)

Scene skill for generating professional infographics, built on `u1-image-base`. See [`skills/u1-infographic/SKILL.md`](skills/u1-infographic/SKILL.md) for full behavior. Sample outputs: [`examples/u1-infographics.md`](examples/u1-infographics.md).

- Automatic prompt quality evaluation
- Content analysis and layout/style selection (87 layouts, 66 styles)
- Multi-round image generation with VLM review
- Quality ranking and best-result output

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/). They follow the [Agent Skills](https://agentskills.io/) layout; see [OpenClaw Skills](https://docs.openclaw.ai/skills) for how OpenClaw discovers and loads skill folders. If you have not set up OpenClaw yet, install and configure it from the **[official documentation](https://docs.openclaw.ai/)** (product site: [openclaw.ai](https://openclaw.ai/)).

### 1. Register `u1-image-base` and `u1-infographic`

Clone this repository, then expose **both** skill directories to OpenClaw ([locations and precedence](https://docs.openclaw.ai/skills#locations-and-precedence)). `u1-infographic` depends on `u1-image-base`—install both.

Use one of the following approaches:

| Approach | What to do |
|----------|------------|
| **Workspace `skills/`** (typical) | Copy or symlink `skills/u1-image-base` and `skills/u1-infographic` into your agent workspace as `./skills/u1-image-base/` and `./skills/u1-infographic/`. |
| **Shared on this machine** | Copy or symlink the same two folders under `~/.openclaw/skills/`. |
| **`openclaw.json`** | Add an absolute path to this repo’s `skills` folder (the parent of both directories) via `skills.load.extraDirs` (example below). |

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

Install packages and export keys in the **Python environment and process** OpenClaw uses when it runs [`skills/u1-image-base/scripts/openclaw_runner.py`](skills/u1-image-base/scripts/openclaw_runner.py) (the unified runner for these tools):

```bash
pip install -r skills/u1-image-base/requirements.txt
export U1_API_KEY="your-image-api-key"
export U1_LM_API_KEY="your-lm-api-key"  # for LLM and VLM
```

Prefer environment variables or a local `.env` file. Do not commit secrets.

### 3. Invoke in OpenClaw

Describe the task in chat, for example:

> "Create an infographic explaining the water cycle"

Or call the skill by name:

> /skill u1-infographic "The water cycle"

## Sample Outputs

Examples from `u1-infographic` (more comparisons in [`examples/u1-infographics.md`](examples/u1-infographics.md)).

| # | User prompt | Output image |
|---|-------------|--------------|
| 1 | Operational Excellence: Standards for Hotel Linen Hygiene and Disposable Supplies | ![Sample 1](examples/images/01-info.png) |
| 2 | Lemons: complete uses & reference guide | ![Sample 2](examples/images/05-info.png) |

Skill-generated expanded prompts for the runs above:

**Sample 1**

```markdown
技术蓝图风格，6个操作模块纵向排列，浅灰网格背景，深海军蓝边框。
Section 1 — Linen Hygiene Lifecycle：7节点横向流程图，图标：垃圾箱→封闭推车→分类箱→洗衣机→熨斗→货架→配送车。三色分区：红（SOILED ZONE：Collection+Transport）、黄（PROCESSING ZONE：Sort+Wash+Finish）、绿（CLEAN ZONE：Store+Distribute）。
Section 2 — Laundering Parameters：工业洗衣机剖面图，标注：71°C/160°F（温度）、50-100ppm Chlorine（化学消毒）、pH 6.5-7.5、45-60min cycle、80%+ moisture removal。
Section 3 — Linen Quality Tiers：三列对比矩阵：Clean（基础布草）→ Sanitized（≥99.9%灭菌）→ Sterile（121°C高压灭菌，医疗专用）。
Section 4 — Quality Control Checklist：六项检查清单：✓无污渍 ✓无破损 ✓无异味 ✓正确折叠 ✓文件记录，QC Passed印章。
Section 5 — Disposable Supplies Control：仪表盘式库存系统，三类：Amenities/Housekeeping/Food Service，颜色指示：绿（充足）→黄（低）→红（补货）。
Section 6 — Compliance Documentation：文件堆叠+合规徽章：ISO 9001、Health Code Compliant、Brand Certified。
```

**Sample 2**

```markdown
The title of this infographic is "The Lemon: Nature's Multi-Purpose Fruit" and adopts a modern minimalist matrix style with botanical touches.
整体布局： 模块化便当盒网格布局，清晰分区，背景为泛黄纸张纹理配浅灰网格。字体采用粗体衬线标题 + 浓缩等宽技术数据字体。配色以活力柠檬黄、叶绿、纯净白为主。
左上象限： 详细植物插图展示柠檬横截面，显示果瓣、果皮、汁囊。标签：Citrus limon, pH 2.3, 50-70ml juice per average fruit。三个圆形图标展示品种：Eureka、Lisbon、Meyer（柠檬-柠檬杂交）。产地：Northeastern India, northern Myanmar, or China。产季：Winter through early summer。
右上象限： Culinary Uses 网格，美食插图。图标：Salad Dressing碗、Lemonade杯、Ceviche鱼盘、Lemon Cake蛋糕、Preserved Lemons罐。分类：Fresh Juice、Zest & Garnish、Preserved、Cooking、Beverages。
中左区： Health & Nutrition。徽章：53mg Vitamin C per 100g (88% DV)。图标：盾牌Immune Support、分子Antioxidant Power、胃Digestive Aid、脸Skin Health、肾Kidney Stone Prevention。提及Hesperidin, diosmin抗氧化剂。
中右区： Household Hacks。教学图示：柠檬半+盐Clean Cutting Boards、微波炉Deodorize Fridge、水壶Descaling Kettle、洗衣机Natural Laundry Bleach、木桌+油Wood Polish。
底部： Selection & Storage 对比。好柠檬打勾：Heavy for size、Firm skin、Bright yellow、Thin skin。坏柠檬打叉：Soft spots、Mold、Green tint。储存：Room temp 1 week、Fridge 3-4 weeks。技巧：Roll on counter before cutting、Freeze juice in ice cube trays、Zest before juicing; avoid white pith。
```

## License

MIT — see [LICENSE](LICENSE).
