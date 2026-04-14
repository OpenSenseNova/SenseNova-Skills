---
name: sensenova-infographic
description: Generates professional infographics with 20 layout types and 17 visual styles. Analyzes content, recommends layout×style combinations, and generates publication-ready infographics. Use when user asks to create "infographic", "信息图", "visual summary", or "可视化".
---

# Infographic Generator

Two dimensions: **layout** (information structure) × **style** (visual aesthetics). Freely combine any layout with any style.

## Usage

```bash
/sensenova-infographic path/to/content.md
/sensenova-infographic path/to/content.md --layout hierarchical-layers --style technical-schematic
/sensenova-infographic path/to/content.md --aspect portrait --lang zh
/sensenova-infographic  # then paste content
```

## Options

| Option | Values |
|--------|--------|
| `--layout` | 20 options (see Layout Gallery), default: bento-grid |
| `--style` | 17 options (see Style Gallery), default: craft-handmade |
| `--aspect` | landscape (16:9), portrait (9:16), square (1:1) |
| `--lang` | en, zh, ja, etc. |

## Layout Gallery

| Layout | Best For |
|--------|----------|
| `linear-progression` | Timelines, processes, tutorials |
| `binary-comparison` | A vs B, before-after, pros-cons |
| `comparison-matrix` | Multi-factor comparisons |
| `hierarchical-layers` | Pyramids, priority levels |
| `tree-branching` | Categories, taxonomies |
| `hub-spoke` | Central concept with related items |
| `structural-breakdown` | Exploded views, cross-sections |
| `bento-grid` | Multiple topics, overview (default) |
| `iceberg` | Surface vs hidden aspects |
| `bridge` | Problem-solution |
| `funnel` | Conversion, filtering |
| `isometric-map` | Spatial relationships |
| `dashboard` | Metrics, KPIs |
| `periodic-table` | Categorized collections |
| `comic-strip` | Narratives, sequences |
| `story-mountain` | Plot structure, tension arcs |
| `jigsaw` | Interconnected parts |
| `venn-diagram` | Overlapping concepts |
| `winding-roadmap` | Journey, milestones |
| `circular-flow` | Cycles, recurring processes |

Full definitions: `references/layouts/<layout>.md`

## Style Gallery

| Style | Description |
|-------|-------------|
| `craft-handmade` | Hand-drawn, paper craft (default) |
| `claymation` | 3D clay figures, stop-motion |
| `kawaii` | Japanese cute, pastels |
| `storybook-watercolor` | Soft painted, whimsical |
| `chalkboard` | Chalk on black board |
| `cyberpunk-neon` | Neon glow, futuristic |
| `bold-graphic` | Comic style, halftone |
| `aged-academia` | Vintage science, sepia |
| `corporate-memphis` | Flat vector, vibrant |
| `technical-schematic` | Blueprint, engineering |
| `origami` | Folded paper, geometric |
| `pixel-art` | Retro 8-bit |
| `ui-wireframe` | Grayscale interface mockup |
| `subway-map` | Transit diagram |
| `ikea-manual` | Minimal line art |
| `knolling` | Organized flat-lay |
| `lego-brick` | Toy brick construction |

Full definitions: `references/styles/<style>.md`

## Recommended Combinations

| Content Type | Layout + Style |
|--------------|----------------|
| Timeline/History | `linear-progression` + `craft-handmade` |
| Step-by-step | `linear-progression` + `ikea-manual` |
| A vs B | `binary-comparison` + `corporate-memphis` |
| Hierarchy | `hierarchical-layers` + `craft-handmade` |
| Overlap | `venn-diagram` + `craft-handmade` |
| Conversion | `funnel` + `corporate-memphis` |
| Cycles | `circular-flow` + `craft-handmade` |
| Technical | `structural-breakdown` + `technical-schematic` |
| Metrics | `dashboard` + `corporate-memphis` |
| Educational | `bento-grid` + `chalkboard` |
| Journey | `winding-roadmap` + `storybook-watercolor` |
| Categories | `periodic-table` + `bold-graphic` |

Default: `bento-grid` + `craft-handmade`

## Output Structure

```
infographic/{topic-slug}/
├── source-{slug}.{ext}
├── analysis.md
├── structured-content.md
├── prompts/infographic.md
└── infographic.png
```

Slug: 2-4 words kebab-case from topic. Conflict: append `-YYYYMMDD-HHMMSS`.

## Core Principles

- Preserve all source data **verbatim**—no summarization or rephrasing
- Define learning objectives before structuring content
- Structure for visual communication (headlines, labels, visual elements)

## Workflow

### Step 1: Setup & Analyze

**1.1 Load Preferences (EXTEND.md)**

Use Bash to check EXTEND.md existence (priority order):

```bash
# Check project-level first
test -f .sensenova-skills/sensenova-infographic/EXTEND.md && echo "project"

# Then user-level (cross-platform: $HOME works on macOS/Linux/WSL)
test -f "$HOME/.sensenova-skills/sensenova-infographic/EXTEND.md" && echo "user"
```

┌────────────────────────────────────────────────────┬───────────────────┐
│                        Path                        │     Location      │
├────────────────────────────────────────────────────┼───────────────────┤
│ .sensenova-skills/sensenova-infographic/EXTEND.md          │ Project directory │
├────────────────────────────────────────────────────┼───────────────────┤
│ $HOME/.sensenova-skills/sensenova-infographic/EXTEND.md    │ User home         │
└────────────────────────────────────────────────────┴───────────────────┘

┌───────────┬───────────────────────────────────────────────────────────────────────────┐
│  Result   │                                  Action                                   │
├───────────┼───────────────────────────────────────────────────────────────────────────┤
│ Found     │ Read, parse, display summary                                              │
├───────────┼───────────────────────────────────────────────────────────────────────────┤
│ Not found │ Ask user with AskUserQuestion (see references/config/first-time-setup.md) │
└───────────┴───────────────────────────────────────────────────────────────────────────┘

**EXTEND.md Supports**: Preferred layout/style | Default aspect ratio | Custom style definitions | Language preference

Schema: `references/config/preferences-schema.md`

**1.2 Analyze Content → `analysis.md`**

1. Save source content (file path or paste → `source.md`)
   - **Backup rule**: If `source.md` exists, rename to `source-backup-YYYYMMDD-HHMMSS.md`
2. Analyze: topic, data type, complexity, tone, audience
3. Detect source language and user language
4. Extract design instructions from user input
5. Save analysis
   - **Backup rule**: If `analysis.md` exists, rename to `analysis-backup-YYYYMMDD-HHMMSS.md`

See `references/analysis-framework.md` for detailed format.

### Step 2: Generate Structured Content → `structured-content.md`

Transform content into infographic structure:
1. Title and learning objectives
2. Sections with: key concept, content (verbatim), visual element, text labels
3. Data points (all statistics/quotes copied exactly)
4. Design instructions from user

**Rules**: Markdown only. No new information. All data verbatim.

See `references/structured-content-template.md` for detailed format.

### Step 3: Recommend Combinations

Recommend 3-5 layout×style combinations based on:
- Data structure → matching layout
- Content tone → matching style
- Audience expectations
- User design instructions

### Step 4: Confirm Options

Use **single AskUserQuestion call** with multiple questions to confirm all options together:

| Question | When | Options |
|----------|------|---------|
| **Combination** | Always | 3+ layout×style combos with rationale |
| **Aspect** | Always | landscape (16:9), portrait (9:16), square (1:1) |
| **Language** | Only if source ≠ user language | Language for text content |

**Important**: Do NOT split into separate AskUserQuestion calls. Combine all applicable questions into one call.

### Step 5: Generate Prompt → `prompts/infographic.md`

**Backup rule**: If `prompts/infographic.md` exists, rename to `prompts/infographic-backup-YYYYMMDD-HHMMSS.md`

Combine:
1. Layout definition from `references/layouts/<layout>.md`
2. Style definition from `references/styles/<style>.md`
3. Base template from `references/base-prompt.md`
4. Structured content from Step 2
5. All text in confirmed language

### Step 6: Generate Image

1. Select available image generation skill (ask user if multiple)
2. **Check for existing file**: Before generating, check if `infographic.png` exists
   - If exists: Rename to `infographic-backup-YYYYMMDD-HHMMSS.png`
3. Call with prompt file and output path
4. On failure, auto-retry once

### Step 7: Output Summary

Report: topic, layout, style, aspect, language, output path, files created.

## References

- `references/analysis-framework.md` - Analysis methodology
- `references/structured-content-template.md` - Content format
- `references/base-prompt.md` - Prompt template
- `references/layouts/<layout>.md` - 20 layout definitions
- `references/styles/<style>.md` - 17 style definitions

## Extension Support

Custom configurations via EXTEND.md. See **Step 1.1** for paths and supported options.
