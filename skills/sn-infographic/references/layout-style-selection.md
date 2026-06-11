# Layout & Style Selection Rules

Resolved by the Worker Agent's own reasoning — no additional LLM call required.

**Operate on names only.** This whole procedure manipulates layout/style **names** (e.g. `hub-spoke`, `corporate-memphis`). **Never open the definition files under `references/layouts/*.md` or `references/styles/*.md` to make the choice** — the pick is a weighted *random* draw, not a quality comparison, so their contents are irrelevant here. Only the two finally-selected files are read, once, in SKILL.md Step 2.3.

## Step 1 — Layout Candidates (by data_type)

Analyze the information structure of `user_prompt`, determine the `data_type`, and map to layout candidates.
Each data_type has a primary (match_score=1.0) and alternatives (match_score=0.7).

| data_type | Primary Layout | Alternative Layouts |
|-----------|----------------|---------------------|
| timeline / history | `linear-progression` | `winding-roadmap`, `step-staircase`, `one-way-flow`, `flashback` |
| process / tutorial | `linear-progression` | `winding-roadmap`, `step-staircase`, `swimlane`, `modular-repetition`, `funnel`, `one-way-flow` |
| comparison | `binary-comparison` | `four-quadrant-grid`, `conflict-contrast` |
| hierarchy | `hierarchical-layers` | `axial-expansion`, `deconstruction` |
| relationships | `hub-spoke` | `jigsaw`, `multi-focal`, `venn-diagram` |
| data / metrics | `dashboard` | `periodic-table`, `data-landscape`, `hard-alignment`, `swiss-grid` |
| cycle / loop | `circular-flow` | `s-curve`, `wave-path`, `spiral-vortex` |
| system / structure | `structural-breakdown` | `multi-scale`, `containerization`, `deconstruction` |
| journey / narrative | `winding-roadmap` | `story-mountain`, `comic-strip`, `emotional-gradient`, `storyboard`, `flashback`, `full-illustration`, `one-way-flow`, `left-image-right-text`, `diagonal-composition`, `overlapping` |
| overview / summary | `bento-grid` | `periodic-table`, `containerization`, `top-image-bottom-text`, `panorama`, `golden-ratio-split` |
| problem / solution | `iceberg` | `conflict-contrast`, `visual-tension`, `funnel`, `bridge` |
| categories / collection | `periodic-table` | `bento-grid`, `tile-layout`, `gallery-style`, `skewed-grid` |
| spatial / geographic | `multi-scale` | `strong-perspective`, `panorama`, `isometric-map` |
| cross-functional / workflow | `swimlane` | `linear-progression`, `modular-repetition` |
| feature list / catalog | `modular-repetition` | `bento-grid`, `containerization`, `left-text-right-image` |
| single concept spotlight | `single-focal-point` | `big-typography`, `ultra-minimalist`, `header-body`, `center-focus`, `frame-composition`, `full-bleed-image`, `visual-first`, `single-object-art`, `macro-closeup`, `golden-ratio-split`, `deconstruction`, `heading-subheading`, `top-image-bottom-text`, `generous-margins`, `asymmetry`, `edge-tension`, `breaking-the-grid`, `strong-perspective` |
| dialogue / Q&A | `speech-bubbles` | `character-guide`, `comic-strip` |
| discovery / exploration | `nonlinear-path` | `scene-unfolding`, `random-scatter`, `disrupted-flow`, `collage-glitch`, `hidden-details` |
| network / multi-center | `multi-focal` | `hub-spoke`, `multi-directional` |
| report / long-form | `header-body` | `swiss-grid`, `hard-alignment`, `heading-subheading`, `editorial-vogue`, `chapter-layout` |
| marketing / CTA | `z-pattern` | `tile-layout`, `luxury-layout`, `editorial-vogue`, `generous-margins`, `full-bleed-image`, `visual-first`, `center-focus`, `frame-composition`, `overlapping`, `asymmetry`, `edge-tension`, `breaking-the-grid`, `skewed-grid`, `diagonal-composition`, `visual-tension`, `collage-glitch` |

## Step 2 — Style Candidates (by tone / domain, independent of layout)

Analyze the tone and domain of `user_prompt`, and map to style candidates.
Each context has a primary (match_score=1.0) and alternatives (match_score=0.7).

| Context | Primary Style | Alternative Styles |
|---------|---------------|-------------------|
| Technical / Engineering | `technical-schematic` | `ikea-manual`, `ui-wireframe`, `technical-diagram`, `parametric-design`, `subway-map` |
| Software / Product / Tech brand | `tech-brand` | `material-design`, `corporate-memphis`, `ui-wireframe`, `parametric-design` |
| Sci-fi / Futuristic | `neon-futurism` | `cyberpunk`, `sci-fi-ui`, `synthwave`, `holographic`, `liquid-metal`, `vaporwave` |
| Professional / Business | `corporate-memphis` | `swiss-style`, `minimalism`, `flat-design`, `bauhaus`, `high-contrast-ad` |
| Data / Analytics | `data-visualization` | `technical-diagram`, `swiss-style`, `minimalism`, `subway-map`, `parametric-design` |
| Educational / Instructional | `chalkboard` | `instructional-visual`, `ikea-manual`, `paper-collage`, `bauhaus` |
| Playful / Casual / Kids | `paper-collage` | `crayon-hand-drawn`, `cartoon-flat`, `kawaii`, `lego-brick`, `screen-print` |
| Luxury / Premium / Fashion | `luxury-minimal` | `art-deco`, `fashion-editorial`, `art-nouveau`, `liquid-metal` |
| Chinese domain | `chinese-guochao` | `modern-ink-wash` |
| Japanese domain | `ukiyo-e` | `kawaii` |
| Vintage / Retro | `aged-academia` | `vintage-poster`, `newspaper-collage`, `woodcut`, `art-nouveau`, `screen-print`, `vaporwave` |
| Artistic / Fine art | `impressionism` | `expressionism`, `cubism`, `baroque`, `surrealism`, `art-nouveau` |
| Handmade / Craft | `paper-collage` | `crayon-hand-drawn`, `storybook-watercolor`, `claymation`, `origami`, `screen-print` |
| Illustration / Drawing | `pen-sketch` | `line-drawing`, `marker-style`, `thick-paint`, `monochrome-illustration` |
| Experimental / Avant-garde | `deconstructivism` | `glitch-art`, `op-art`, `geometric-burst`, `fractal-art`, `surreal-collage`, `parametric-design`, `vaporwave` |
| Scandinavian / Minimal | `scandinavian` | `minimalism`, `swiss-style`, `luxury-minimal`, `bauhaus` |
| Playful / Geometric | `origami` | `pixel-art`, `knolling`, `lego-brick`, `bauhaus` |
| Photography / Mixed | `mixed-media` | `film-photography`, `double-exposure`, `newspaper-collage` |
| Marketing / Advertising | `high-contrast-ad` | `screen-print`, `flat-design`, `corporate-memphis` |
| Futuristic / Luxury Tech | `liquid-metal` | `neon-futurism`, `holographic`, `parametric-design` |
| Internet / Youth Culture | `vaporwave` | `glitch-art`, `cyberpunk`, `pixel-art` |

## Step 3 — Random Sampling

Layout and style are sampled independently using the same process, **on names only**. The "all available options" universe is just the **filenames** under `references/layouts/` and `references/styles/` — enumerate them with `ls` (names, not contents):

```bash
mapfile -t ALL_LAYOUTS < <(ls "$SKILL_DIR/references/layouts/" | sed 's/\.md$//')
mapfile -t ALL_STYLES  < <(ls "$SKILL_DIR/references/styles/"  | sed 's/\.md$//')
```

For each of layout and style, build the weighted pool from the matched row of the table above — the **primary** name ×10, each **alternative** name ×9, plus **3 random names** drawn from the full `ls` list (outside the current data_type / context) ×1 — then shuffle and take the first. Example for layout (style is identical with `ALL_STYLES`):

```bash
PRIMARY_LAYOUT="hub-spoke"                       # match_score=1.0 row for this data_type
ALT_LAYOUTS=(jigsaw multi-focal venn-diagram)    # match_score=0.7 alternatives

LAYOUT_POOL=()
for _ in $(seq 10); do LAYOUT_POOL+=("$PRIMARY_LAYOUT"); done
for a in "${ALT_LAYOUTS[@]}"; do for _ in $(seq 9); do LAYOUT_POOL+=("$a"); done; done
for r in $(printf '%s\n' "${ALL_LAYOUTS[@]}" | shuf | head -3); do LAYOUT_POOL+=("$r"); done

LAYOUT=$(printf '%s\n' "${LAYOUT_POOL[@]}" | shuf | head -1)
```

The weighting gives primary and alternatives roughly equal win probability (~10:9), with the random non-matching items a combined ~10%.

## Fallback

If `data_type` or `context` cannot be determined, use `hub-spoke` + `corporate-memphis`.
