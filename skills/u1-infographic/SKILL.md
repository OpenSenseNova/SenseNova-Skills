---
name: u1-infographic
description: Generates professional infographics with 87 layout types and 66 visual styles. Analyzes content, recommends layout×style combinations, and generates publication-ready infographics. Use when user asks to create "infographic", "信息图", "visual summary", or "可视化".
---

# Infographic Generator

Two dimensions: **layout** (information structure) × **style** (visual aesthetics). Freely combine any layout with any style.

## Usage

```bash
/u1-infographic path/to/content.md                    # Auto-select layout & style
/u1-infographic path/to/content.md --interactive      # Interactive mode: choose from recommendations
/u1-infographic path/to/content.md --layout hierarchical-layers --style technical-schematic
/u1-infographic path/to/content.md --aspect portrait --lang zh
/u1-infographic  # then paste content
```

## Options

| Option | Values |
|--------|--------|
| `--layout` | 87 options (see Layout Gallery), auto-selected if not specified |
| `--style` | 66 options (see Style Gallery), auto-selected if not specified |
| `--aspect` | landscape (16:9), portrait (9:16), square (1:1), classic-landscape (4:3), classic-portrait (3:4), photo-landscape (3:2), photo-portrait (2:3), classic-photo (4:5), large-format (5:4), ultrawide (21:9) |
| `--lang` | Auto-detected from source content. Override if needed (en, zh, ja, etc.) |
| `--interactive` | Enable interactive mode to choose from recommendations |

## Layout Gallery

### Structural / Information Architecture

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
| `step-staircase` | Growth stages, level progressions |
| `swimlane` | Cross-functional workflows, service blueprints |
| `isometric-tech-stack` | Software/hardware layer diagrams |
| `multi-scale` | Macro-to-micro zoom diagrams |
| `data-landscape` | 3D data terrain, point cloud visualization |
| `axial-expansion` | Symmetric branching from a central axis |
| `chapter-layout` | Long-form multi-section guides |
| `containerization` | Boxed multi-topic reference sheets |
| `modular-repetition` | Feature lists, uniform step grids |

### Compositional / Visual Arrangement

| Layout | Best For |
|--------|----------|
| `single-focal-point` | Single concept spotlights |
| `top-image-bottom-text` | Image-led editorial cards |
| `left-text-right-image` | Feature explanations with visuals |
| `left-image-right-text` | Narrative-driven image-first panels |
| `three-tier` | Header / body / footer structured layouts |
| `four-quadrant-grid` | 2×2 strategic matrices (SWOT, BCG) |
| `nine-grid` | 3×3 frameworks or icon catalogs |
| `header-body` | Report covers, chapter openers |
| `heading-subheading` | Typography-led hierarchy |
| `tile-layout` | Metro-style color-block navigation |
| `swiss-grid` | Strict rational grid systems |
| `hard-alignment` | Precision-aligned technical layouts |
| `golden-ratio-split` | Aesthetically proportioned compositions |
| `asymmetry` | Dynamic imbalanced editorial layouts |
| `generous-margins` | Premium minimalist presentations |
| `ultra-minimalist` | Single-element brand statements |
| `gallery-style` | Gallery-wall item showcases |
| `luxury-layout` | Gold/black premium brand layouts |
| `editorial-vogue` | Serif headline magazine layouts |
| `frame-composition` | Subject framed by foreground elements |

### Compositional Techniques

| Layout | Best For |
|--------|----------|
| `full-bleed-image` | Atmospheric full-canvas imagery |
| `big-typography` | Oversized headline impact |
| `breaking-the-grid` | Elements popping beyond their containers |
| `diagonal-composition` | Dynamic diagonal energy |
| `center-focus` | Converging lines to a central subject |
| `strong-perspective` | Depth-driven vanishing point layouts |
| `edge-tension` | Cropped subjects pressing canvas edges |
| `macro-closeup` | Extreme detail close-up views |
| `visual-tension` | Stretched or conflicting visual forces |
| `overlapping` | Layered depth compositions |
| `deconstruction` | Fragmented and reassembled elements |
| `skewed-grid` | Rotated grid for dynamic energy |
| `random-scatter` | Controlled scatter compositions |
| `maximalism` | Dense information-rich layouts |
| `collage-glitch` | Torn fragment collage with glitch effects |
| `single-object-art` | Single object as sculptural subject |

### Flow / Eye Movement

| Layout | Best For |
|--------|----------|
| `z-pattern` | Marketing layouts with CTA |
| `f-pattern` | Text-heavy scannable reports |
| `s-curve` | Flowing multi-step processes |
| `wave-path` | Rhythmic cyclical processes |
| `one-way-flow` | Directional momentum narratives |
| `spiral-vortex` | Converging focus narratives |
| `multi-focal` | Network diagrams with multiple centers |
| `multi-directional` | Radial or explosive multi-perspective layouts |

### Narrative / Storytelling

| Layout | Best For |
|--------|----------|
| `full-illustration` | Scene-based storytelling |
| `scene-unfolding` | Panoramic environment narratives |
| `speech-bubbles` | Dialogue and Q&A formats |
| `character-guide` | Mascot-guided educational content |
| `hidden-details` | Discovery and exploration layouts |
| `nonlinear-path` | Playful non-linear reading paths |
| `visual-first` | Image-dominant minimal text |
| `text-wrap` | Text flowing around illustrations |
| `storyboard` | Film-style sequential scene panels |
| `flashback` | Main scene with inset past/future panels |
| `emotional-gradient` | Emotional journey color progressions |
| `conflict-contrast` | Opposing states with dramatic contrast |
| `panorama` | Ultra-wide expansive scene layouts |
| `chapter-layout` | Book-like multi-chapter structures |
| `disrupted-flow` | Intentionally broken reading order |
| `multi-directional` | Multi-direction text and element layouts |

Full definitions: `references/layouts/<layout>.md`

## Style Gallery

### Handmade / Craft

| Style | Description |
|-------|-------------|
| `paper-collage` | Paper cutout and collage aesthetic (default) |
| `crayon-hand-drawn` | Crayon hand-drawn texture, warm and playful |
| `claymation` | 3D clay figures, stop-motion |
| `kawaii` | Japanese cute, pastels |
| `storybook-watercolor` | Soft painted, whimsical |
| `chalkboard` | Chalk on black board |

### Tech / Future

| Style | Description |
|-------|-------------|
| `cyberpunk` | High tech meets low life, neon and darkness |
| `neon-futurism` | Pure neon future without dystopia |
| `sci-fi-ui` | Sci-fi holographic interfaces |
| `ui-wireframe` | Grayscale interface mockup |
| `tech-brand` | Clean tech company visuals |
| `vaporwave` | 80s-90s nostalgia retro-futurism |
| `synthwave` | 80s neon retro-futurism with grid landscapes |
| `glitch-art` | Digital glitch corrupted data visuals |
| `parametric-design` | Algorithmically generated geometric complexity |
| `holographic` | Rainbow iridescent foil, prismatic color shifts |
| `liquid-metal` | Flowing chrome surfaces, high-specular reflections |
| `material-design` | Paper-and-ink layered surfaces, elevation shadows |

### Graphic / Commercial

| Style | Description |
|-------|-------------|
| `cartoon-flat` | Clean cartoon with flat colors |
| `flat-design` | No shadows or gradients, solid color blocks |
| `high-contrast-ad` | High-contrast advertising impact |
| `corporate-memphis` | Flat vector, vibrant |
| `luxury-minimal` | High-end extreme minimalism |
| `screen-print` | Overprint layers, spot colors, bold graphic impact |

### Information / Data

| Style | Description |
|-------|-------------|
| `swiss-style` | Strict grid, objective typography, rational clarity |
| `data-visualization` | Charts and graphics for accurate data presentation |
| `minimalism` | Maximum impact through extreme restraint |
| `technical-diagram` | Blueprint and engineering diagram precision |
| `instructional-visual` | Step-by-step illustrated guidance |
| `technical-schematic` | Blueprint, engineering |
| `subway-map` | Transit diagram |
| `ikea-manual` | Minimal line art |

### Illustration / Drawing

| Style | Description |
|-------|-------------|
| `line-drawing` | Pure contour linework, no fills, elegant reduction |
| `thick-paint` | Heavy impasto brushwork, oil-painting tactility |
| `pen-sketch` | Rapid gestural pen strokes, sketchbook immediacy |
| `marker-style` | Bold flat marker colors, vivid graphic punch |
| `monochrome-illustration` | Single-hue tonal range, depth through value |

### Photography / Image

| Style | Description |
|-------|-------------|
| `film-photography` | Analog grain, color shifts, light leaks |
| `double-exposure` | Two images merged, silhouette filled with scene |
| `fashion-editorial` | High-fashion magazine art direction |
| `newspaper-collage` | Vintage newsprint clippings, ransom-note assembly |

### Artistic / Cultural

| Style | Description |
|-------|-------------|
| `art-deco` | 1920s geometric luxury |
| `art-nouveau` | Natural curves, botanical motifs, organic forms |
| `surrealism` | Dream-like reality and fantasy |
| `chinese-guochao` | Chinese traditional meets modern |
| `modern-ink-wash` | Traditional ink wash contemporary |
| `ukiyo-e` | Japanese woodblock print, bold outlines, flat color |
| `scandinavian` | Minimal, functional, warm natural tones |
| `aged-academia` | Vintage science, sepia |
| `vintage-poster` | Classic lithographic poster, limited colors |
| `woodcut` | Rough-edged black lines, raw expressive reduction |
| `bauhaus` | Form follows function, geometric shapes and primary colors |
| `baroque` | Dramatic chiaroscuro, ornate decoration, theatrical grandeur |
| `impressionism` | Broken brushwork, captured light, atmospheric color |
| `expressionism` | Distorted forms, raw emotion, psychological intensity |
| `cubism` | Multiple simultaneous viewpoints, geometric faceted planes |

### Experimental / Avant-garde

| Style | Description |
|-------|-------------|
| `op-art` | Optical illusion patterns, perceptual effects |
| `deconstructivism` | Fragmented, rule-breaking, deliberately disruptive |
| `mixed-media` | Photography, illustration, and texture combined |
| `fractal-art` | Infinite self-similar recursive mathematical patterns |
| `surreal-collage` | Photomontage with impossible dreamlike juxtapositions |
| `geometric-burst` | Explosive angular shards radiating with kinetic energy |

### Playful / Geometric

| Style | Description |
|-------|-------------|
| `origami` | Folded paper, geometric |
| `pixel-art` | Retro 8-bit |
| `knolling` | Organized flat-lay |
| `lego-brick` | Toy brick construction |

Full definitions: `references/styles/<style>.md`

## Auto-Selection Reference

These combinations guide automatic layout×style selection:

| Content Type | Layout + Style |
|--------------|----------------|
| Timeline/History | `linear-progression` + `paper-collage` |
| Step-by-step | `linear-progression` + `ikea-manual` |
| A vs B | `binary-comparison` + `cartoon-flat` |
| Hierarchy | `hierarchical-layers` + `paper-collage` |
| Overlap | `venn-diagram` + `crayon-hand-drawn` |
| Conversion | `funnel` + `corporate-memphis` |
| Cycles | `circular-flow` + `paper-collage` |
| Technical | `structural-breakdown` + `technical-schematic` |
| Metrics | `dashboard` + `corporate-memphis` |
| Educational | `bento-grid` + `chalkboard` |
| Journey | `winding-roadmap` + `storybook-watercolor` |
| Categories | `periodic-table` + `high-contrast-ad` |
| Tech Brand | `bento-grid` + `tech-brand` |
| Luxury | `four-quadrant-grid` + `luxury-minimal` |
| Chinese Culture | `chapter-layout` + `chinese-guochao` |

Default: Auto-selected based on content analysis. Fallback: `bento-grid` + `paper-collage`

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
test -f .u1-skills/u1-infographic/EXTEND.md && echo "project"

# Then user-level (cross-platform: $HOME works on macOS/Linux/WSL)
test -f "$HOME/.u1-skills/u1-infographic/EXTEND.md" && echo "user"
```

┌──────────────────────────────────────────────┬───────────────────┐
│                        Path                  │     Location      │
├──────────────────────────────────────────────┼───────────────────┤
│ .u1-skills/u1-infographic/EXTEND.md          │ Project directory │
├──────────────────────────────────────────────┼───────────────────┤
│ $HOME/.u1-skills/u1-infographic/EXTEND.md    │ User home         │
└──────────────────────────────────────────────┴───────────────────┘

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
3. **Detect language**: Auto-detect source content language (used for infographic text)
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

### Step 3: Determine Layout & Style

**If user specified `--layout` and `--style`**: Use user's choice directly.

**If not specified**: Auto-select based on analysis results.

#### 3.1 Read Content Classification from analysis.md

From `analysis.md` frontmatter, extract:

- `data_type`: Content structure classification
- `topic`: Domain context
- `complexity`: Layout density guidance

#### 3.2 Map to Layout Candidates

Use `data_type` from analysis to select layout (see `references/analysis-framework.md` Content Type Classification):

| data_type | Primary Layout | Alternative Layouts |
|-----------|----------------|---------------------|
| timeline/history | linear-progression | winding-roadmap |
| process/tutorial | linear-progression | winding-roadmap, step-staircase |
| comparison | binary-comparison | comparison-matrix, four-quadrant-grid |
| hierarchy | hierarchical-layers | tree-branching |
| relationships | venn-diagram | hub-spoke, jigsaw |
| data/metrics | dashboard | periodic-table |
| cycle/loop | circular-flow | s-curve |
| system/structure | structural-breakdown | bento-grid |
| journey/narrative | winding-roadmap | story-mountain, comic-strip |
| overview/summary | bento-grid | periodic-table, nine-grid |

#### 3.3 Map to Style Candidates

Based on content tone and domain from analysis:

| Context | Primary Style | Alternative Styles |
|---------|---------------|-------------------|
| Technical/DIY | technical-schematic | ikea-manual, ui-wireframe |
| Professional/Business | corporate-memphis | swiss-style, minimalism |
| Educational | chalkboard | instructional-visual |
| Playful/Casual | paper-collage | crayon-hand-drawn, cartoon-flat |
| Luxury/Premium | luxury-minimal | art-deco |
| Chinese domain | chinese-guochao | modern-ink-wash |
| Japanese domain | ukiyo-e | - |
| Data-focused | data-visualization | technical-diagram |

#### 3.4 Select with Randomness

From the matched candidates:

```
final_score = match_score + random(0, 0.3)
```

- `match_score`: 1.0 for primary, 0.7 for alternatives
- `random`: 0-0.3 to ensure variety

**Select**: Highest scoring layout × style combination.

**Fallback**: `bento-grid` + `paper-collage` (only if data_type cannot be determined)

### Step 4: Confirm Options (Only if `--interactive`)

If user specified `--interactive` flag, use **single AskUserQuestion call** to confirm:

| Question | When | Options |
|----------|------|---------|
| **Combination** | `--interactive` | 3+ layout×style combos with rationale |
| **Aspect** | `--interactive` | landscape (16:9), portrait (9:16), square (1:1), classic-landscape (4:3), classic-portrait (3:4), photo-landscape (3:2), photo-portrait (2:3), classic-photo (4:5), large-format (5:4), ultrawide (21:9) |
| **Language** | `--interactive` | Confirm detected language or override |

**Important**: Do NOT split into separate AskUserQuestion calls. Combine all applicable questions into one call.

### Step 5: Generate Prompt → `prompts/infographic.md`

**Backup rule**: If `prompts/infographic.md` exists, rename to `prompts/infographic-backup-YYYYMMDD-HHMMSS.md`

Combine:

1. Layout definition from `references/layouts/<layout>.md`
2. Style definition from `references/styles/<style>.md`
3. Base template from `references/base-prompt.md`
4. Structured content from Step 2
5. All text in detected (or overridden) language
6. Prompt writing rules from `references/prompt-writing-rules.md`

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
- `references/layout-style-selection.md` - Layout and style selection
- `references/base-prompt.md` - Prompt template
- `references/layouts/<layout>.md` - 87 layout definitions
- `references/styles/<style>.md` - 66 style definitions

## Extension Support

Custom configurations via EXTEND.md. See **Step 1.1** for paths and supported options.
