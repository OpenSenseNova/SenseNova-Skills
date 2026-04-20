# SenseNova-Skills

English | [简体中文](README_CN.md)

Skills and tooling for **AIGC** in agent runtimes.

## Prerequisites

- **Python** 3.9 or later.
- **U1 API** credentials for image generation and LLM/VLM endpoints (`U1_API_KEY`, `U1_LM_API_KEY`; see Quick Start).

## Skills

### u1-doctor

Environment diagnostic skill that checks installation, dependencies, and configuration. See [`skills/u1-doctor/SKILL.md`](skills/u1-doctor/SKILL.md) for full behavior.

- Validates `u1-image-base` installation and Python dependencies
- Checks environment variables and interactively prompts to configure missing required variables
- Saves configuration to `.env` file and reloads environment automatically

### u1-image-base (Tier 0)

Base-layer infrastructure skill providing two low-level tools. See [`skills/u1-image-base/SKILL.md`](skills/u1-image-base/SKILL.md) for full behavior.

- **u1-image-generate** — text-to-image generation
- **u1-text-optimize** — text processing using LLM

All tools are invoked through a unified `openclaw_runner.py` entrypoint.

### u1-infographic (Tier 1)

Scene skill for generating professional infographics, built on `u1-image-base`. See [wwwills/u1-infographic/SKILL.md`](skills/u1-infographic/SKILL.md) for full behavior.

- Automatic prompt quality evaluation
- Content analysis and layout/style selection (87 layouts, 66 styles)
- Multi-round image generation with VLM review
- Quality ranking and best-result output

## Quick Start

Use these skills from [OpenClaw](https://openclaw.ai/).
They follow the [Agent Skills](https://agentskills.io/) layout; see [OpenClaw Skills](https://docs.openclaw.ai/tools/skills) for how OpenClaw discovers and loads skill folders.
If you have not set up OpenClaw yet, install and configure it from the **[official documentation](https://docs.openclaw.ai/)** (product site: [openclaw.ai](https://openclaw.ai/)).

### 1. Register `u1-image-base` and `u1-infographic`

Clone this repository, then expose **both** skill directories to OpenClaw ([locations and precedence](https://docs.openclaw.ai/tools/skills#locations-and-precedence)). `u1-infographic` depends on `u1-image-base`—install both.

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

Install packages and export keys in the **Python environment and process** OpenClaw uses when it runs [`skills/u1-image-base/u1_image_base/openclaw_runner.py`](skills/u1-image-base/u1_image_base/openclaw_runner.py) (the unified runner for these tools):

```bash
pip install -r skills/u1-image-base/requirements.txt
# for image generation
export U1_API_KEY="your-image-api-key"
# for LLM and VLM
export U1_LM_API_KEY="your-lm-api-key"
export U1_LM_BASE_URL="your-lm-base-url"
```

Prefer environment variables or a local `.env` file. Do not commit secrets.

### 3. Invoke in OpenClaw

Check your environment and configure missing variables interactively:

> /skill u1-doctor

Describe the task in chat, for example:

> "Create an infographic explaining the water cycle"

Or call the skill by name:

> /skill u1-infographic "The water cycle"

## Sample Outputs

Examples for `u1-infographic` (more examples in [`u1-infographic-examples.md`](docs/u1-infographic-examples.md)).

### Example 1 — hotel linen hygiene

**User prompt:** `"Operational Excellence: Standards for Hotel Linen Hygiene and Disposable Supplies"`

**Expanded prompt**

```
Technical blueprint style: six operational modules arranged vertically, light grey grid background, deep navy blue borders.
Section 1 — Linen Hygiene Lifecycle: a seven-node horizontal flow; icons: waste bin → sealed cart → sort bin → washer → iron → shelf → delivery cart. Three color zones: red (soiled zone: collection and transport), yellow (processing zone: sort → wash → finish), green (clean zone: store and distribute).
Section 2 — Laundering Parameters: cutaway of an industrial washer, labeled: 71°C/160°F (temperature), 50–100 ppm chlorine (chemical disinfection), pH 6.5–7.5, 45–60 min cycle, 80%+ moisture removal.
Section 3 — Linen Quality Tiers: a three-column matrix: Clean (standard linen) → Sanitized (≥99.9% pathogen reduction) → Sterile (121°C autoclave, medical use).
Section 4 — Quality Control Checklist: ✓ no stains ✓ no damage ✓ no odor ✓ correct fold ✓ documented traceability; "QC Passed" stamp.
Section 5 — Disposable Supplies Control: dashboard-style stock for three lines: amenities, housekeeping, food service; color bands: green (sufficient) → yellow (low) → red (reorder).
Section 6 — Compliance Documentation: stacked files and badges: ISO 9001, health-code compliant, brand certified.
```

<p align="center"><img src="docs/images/01-info-nb2.webp" width="720" alt="Sample infographic output — hotel linen hygiene"></p>

### Example 2 — lemon guide

**User prompt:** `"Lemons: complete uses & reference guide"`

**Expanded prompt**

```
The title of this infographic is "The Lemon: Nature's Multi-Purpose Fruit" and it uses a modern minimalist matrix layout with botanical illustration accents.
Overall layout: a modular bento-style grid, clear sections, yellowed-paper texture on a light grey grid; bold serif titles plus a narrow monospaced data face; palette: bright lemon yellow, leaf green, and clean white.
Top-left quadrant: detailed botanical cutaway of a lemon (flesh, peel, juice sacs). Labels: Citrus limon, pH ~2.3, 50–70 ml juice per average fruit. Three round variety icons: Eureka, Lisbon, Meyer (lemon hybrid). Origin: northeastern India, northern Myanmar, or China. Season: winter through early summer.
Top-right quadrant: culinary uses grid with food icons: salad-dressing bowl, lemonade glass, ceviche plate, lemon cake, preserved-lemon jar. Categories: fresh juice, zest and garnish, preserved, cooking, beverages.
Center-left: health and nutrition—badge: ~53 mg vitamin C per 100 g (about 88% DV); icons: immune support, antioxidant, digestive aid, skin health, kidney-stone prevention; note hesperidin and diosmin.
Center-right: household hacks—lemon half + salt for cutting boards, microwave to deodorize the fridge, descale a kettle, natural laundry bleach, wood polish with oil.
Bottom: selection and storage—good: heavy for size, firm skin, bright yellow, thin skin. Avoid: soft spots, mold, greenish tint. Storage: room temp ~1 week; fridge ~3–4 weeks. Tips: roll on the counter before cutting; freeze juice in ice-cube trays; zest before juicing; avoid the white pith.
```

<p align="center"><img src="docs/images/05-info-nb2.webp" width="720" alt="Sample infographic output — lemon guide"></p>

## License

MIT — see [LICENSE](LICENSE).
