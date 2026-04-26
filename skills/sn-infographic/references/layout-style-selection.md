# Layout & Style Selection Rules

Resolved by the Worker Agent's own reasoning — no additional LLM call required.

## Step 1 — Layout Candidates (by data_type)

Analyze the information structure of `user_prompt`, determine the `data_type`, and map to layout candidates.
Each data_type has a primary (match_score=1.0) and alternatives (match_score=0.7).

| data_type | Primary Layout | Alternative Layouts |
|-----------|----------------|---------------------|
| timeline / history | `linear-progression` | `winding-roadmap`, `step-staircase`, `one-way-flow`, `flashback` |
| process / tutorial | `linear-progression` | `winding-roadmap`, `step-staircase`, `swimlane`, `modular-repetition`, `funnel`, `one-way-flow` |
| comparison | `binary-comparison` | `comparison-matrix`, `four-quadrant-grid`, `conflict-contrast` |
| hierarchy | `hierarchical-layers` | `tree-branching`, `axial-expansion`, `deconstruction` |
| relationships | `venn-diagram` | `hub-spoke`, `jigsaw`, `multi-focal` |
| data / metrics | `dashboard` | `periodic-table`, `data-landscape`, `hard-alignment`, `swiss-grid` |
| cycle / loop | `circular-flow` | `s-curve`, `wave-path`, `spiral-vortex` |
| system / structure | `structural-breakdown` | `isometric-tech-stack`, `multi-scale`, `containerization`, `deconstruction` |
| journey / narrative | `winding-roadmap` | `story-mountain`, `comic-strip`, `emotional-gradient`, `storyboard`, `flashback`, `full-illustration`, `one-way-flow`, `left-image-right-text`, `diagonal-composition`, `overlapping` |
| overview / summary | `bento-grid` | `periodic-table`, `nine-grid`, `chapter-layout`, `containerization`, `top-image-bottom-text`, `panorama`, `golden-ratio-split` |
| problem / solution | `bridge` | `iceberg`, `conflict-contrast`, `visual-tension`, `funnel` |
| categories / collection | `periodic-table` | `bento-grid`, `tile-layout`, `nine-grid`, `gallery-style`, `maximalism`, `skewed-grid` |
| spatial / geographic | `isometric-map` | `isometric-tech-stack`, `multi-scale`, `strong-perspective`, `panorama` |
| cross-functional / workflow | `swimlane` | `linear-progression`, `modular-repetition` |
| feature list / catalog | `modular-repetition` | `bento-grid`, `containerization`, `left-text-right-image` |
| single concept spotlight | `single-focal-point` | `big-typography`, `ultra-minimalist`, `header-body`, `center-focus`, `frame-composition`, `full-bleed-image`, `visual-first`, `single-object-art`, `macro-closeup`, `golden-ratio-split`, `text-wrap`, `deconstruction`, `heading-subheading`, `top-image-bottom-text`, `generous-margins`, `asymmetry`, `edge-tension`, `breaking-the-grid`, `strong-perspective` |
| dialogue / Q&A | `speech-bubbles` | `character-guide`, `comic-strip` |
| discovery / exploration | `hidden-details` | `nonlinear-path`, `scene-unfolding`, `random-scatter`, `disrupted-flow`, `collage-glitch` |
| network / multi-center | `multi-focal` | `hub-spoke`, `multi-directional` |
| report / long-form | `chapter-layout` | `f-pattern`, `three-tier`, `header-body`, `swiss-grid`, `hard-alignment`, `heading-subheading`, `editorial-vogue` |
| marketing / CTA | `z-pattern` | `tile-layout`, `three-tier`, `luxury-layout`, `editorial-vogue`, `generous-margins`, `full-bleed-image`, `visual-first`, `center-focus`, `frame-composition`, `overlapping`, `asymmetry`, `edge-tension`, `breaking-the-grid`, `skewed-grid`, `diagonal-composition`, `visual-tension`, `collage-glitch` |

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

Layout and style are sampled independently using the same process:

1. Build a weighted candidate pool: repeat the primary item **10 times**, each alternative item **9 times**, then randomly pick **3 items** from all available options outside the current data_type / context and repeat each **1 time**, then merge into the candidate pool
2. Shuffle the pool with bash `shuf` and take the first item as the result:

```bash
LAYOUT=$(printf '%s\n' "${LAYOUT_POOL[@]}" | shuf | head -1)
STYLE=$(printf '%s\n' "${STYLE_POOL[@]}" | shuf | head -1)
```

The weighting gives primary and alternatives roughly equal win probability (~10:9), with non-matching items having a combined win probability of ~10%.

## Fallback

If `data_type` or `context` cannot be determined, use `hub-spoke` + `corporate-memphis`.
