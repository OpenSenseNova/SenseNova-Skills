# Motion HTML Stories

English | [简体中文](sn-motion-html_cn.md)

[`sn-motion-html`](../skills/sn-motion-html/SKILL.md) creates immersive, scroll-driven
web stories. It is intended for brand stories, product journeys, timelines, industry
explainers, and fictional worlds where the camera should move through one continuous space.
It is not a general web-app generator or an ordinary autoplay-video page.

## What it produces

- A reusable project rather than a one-off HTML file.
- A structured `content/story.json` with chapters and display copy.
- One continuous media stage: scene clip → connector → next scene.
- Consistent stills, Seedance scene/connector clips, posters, and a responsive interface.
- A reduced-motion path that keeps the story usable when video is unavailable.

## Requirements

- Python and FFmpeg for media normalization, verification, and contact sheets.
- An image-generation capability for the still-image consistency gate.
- An Ark-compatible Seedance account for video generation.
- A project-local `.env` containing credentials; never expose it through static hosting.

The bundled template uses:

```dotenv
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
SEEDANCE_MODEL=doubao-seedance-2-5-260628
```

Use the current official provider documentation for model IDs and supported parameters.

## Start a project

Initialize a project with a style and interface preset:

```bash
python scripts/init_project.py /absolute/output/path \
  --title "Story title" \
  --style cinematic \
  --ui folio
```

Available styles are `anime`, `cinematic`, and `cgi`; interface presets are `folio`,
`caption`, and `graphic`. Replace the example story and manifests before delivery.

## Production workflow

1. Define the audience, factual scope, visual language, device targets, sound policy, and budget.
2. Research factual stories and separate source notes from display copy.
3. Create a chapter blueprint, shot plan, connector plan, and identity bible.
4. Obtain explicit visual-style approval and content/shot-plan approval.
5. Generate a small still-image gate set, then the complete still set after approval.
6. Dry-run the video manifest and one representative clip.
7. Obtain explicit authorization immediately before the first paid video batch.
8. Generate dives, extract real boundary frames, generate connectors, normalize media, and run browser QA.

The approval gates are separate from paid-generation authorization. A creative approval does
not authorize a paid video request. Do not retry authentication, permission, billing, or
model-activation errors automatically.

## Common commands

Run these from the initialized project root:

```bash
python scripts/seedance_pipeline.py . plan
python scripts/seedance_pipeline.py . all --workers 4
python scripts/verify_media.py .
python scripts/contact_sheet.py .
python scripts/serve_project.py . --port 8080
```

Before handoff, validate media dimensions, frame rate, codec, duration, browser navigation,
reverse and forward progress, missing-video fallback, and reduced-motion behavior. Deliver the
preview URL, project path, media directories, provider settings, and any remaining blocker.
