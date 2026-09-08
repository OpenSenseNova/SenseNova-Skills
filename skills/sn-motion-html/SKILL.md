---
name: sn-motion-html
description: Build continuous-shot motion-driven HTML stories from a subject or narrative, including research, story structure, consistent AI stills, Seedance scene and connector clips, interface styling, media normalization, and browser QA. Use for immersive journeys, timelines, product stories, fictional worlds, or other scene-based visual narratives whose camera should flow from beginning to end; not for ordinary autoplay video pages or general web apps.
---

# SN Motion HTML

Create a reusable project, not a one-off HTML file. Keep subject matter, chapter count, visual style, interface treatment, copy placement, language, image model, video model, clip duration, and hosting path configurable.

The defining experience is one continuous camera journey controlled by page progress. Preserve a single fixed media stage and one ordered timeline from the first scene through every connector to the final scene. Differentiate projects through transparent copy composition, header treatment, type, navigation, and scene-specific copy placement—not by replacing the continuous stage with separate article media blocks.

## Route the work

1. Resolve the story goal, audience, factual fidelity, chapter scale, visual language, copy language, target devices, sound policy, and available API credentials. Make reasonable defaults only for low-risk implementation details.
2. For factual or source-based stories, research before outlining and record sources separately from display copy.
3. Produce a chapter blueprint, shot/connector plan, and character/object bible before generating the full media set.
4. Detect the image-generation capability available in the current environment before generating any stills. The capability may be a callable image tool, a skill that exposes or instructs an image workflow, or both. Use the available capability when present; if no suitable capability is available, report that blocker to the user before continuing past the still-generation stage.
5. Prepare a review package containing the proposed visual style and the content/shot arrangement. When an image capability is available, generate only the small reference/gate set needed for review.
6. Obtain the user's explicit approval at both approval gates below. After approval, generate the complete still set and inspect it before any paid video batch.
7. Dry-run the video manifest and representative clip. Obtain explicit authorization immediately before the first paid video API request, then generate scene clips and connector clips in dependency-aware parallel phases.
8. Choose or design an interface treatment around the continuous stage, assemble from structured content, then verify media and browser behavior.

## Required user approval gates

Do not silently infer approval from an unanswered message or from a prior general instruction. If the user requests changes, revise the package and present the affected gate again.

1. **Visual style approval:** present the style preamble and identity blocks, including medium, palette, materials, lighting, camera grammar, composition, negative constraints, and recurring character/product treatment. When image generation is available, include a small reference/gate set (normally opening, middle, and ending stills). Do not generate the complete still set until the user explicitly approves the visual direction.
2. **Content and shot-plan approval:** present the chapter order, each chapter's dominant visual event and display copy, scene framing/camera intent, connector start and destination, and per-scene copy position. Do not generate the complete still set or write the final video manifest until the user explicitly approves this arrangement.

These are separate decisions: style approval determines how the world looks; content and shot-plan approval determines what is shown and how the camera moves through it. The later paid-video approval is an authorization gate, not a substitute for either creative approval.

Read [references/workflow.md](references/workflow.md) for the full production sequence. Read only the additional references needed for the current stage:

- [references/schemas.md](references/schemas.md) when creating manifests or content JSON.
- [references/prompting.md](references/prompting.md) when generating character references, scenes, or motion prompts.
- [references/style-presets.md](references/style-presets.md) when choosing or adapting anime, cinematic, or CGI production styles.
- [references/seedance.md](references/seedance.md) before configuring or calling the video API.
- [references/frontend.md](references/frontend.md) before selecting or adapting the interface treatment.

## Start from the template

Run:

```bash
python scripts/init_project.py /absolute/output/path --title "Story title" --style cinematic --ui folio
```

The initializer copies `assets/template/` and creates the media directories. Replace the example story and manifests; do not leave placeholder subject matter in the final project.

Choose `--style anime`, `--style cinematic`, or `--style cgi`. Separately choose `--ui folio`, `--ui caption`, or `--ui graphic`. Style controls the generated world; UI controls header, transparent copy treatment, navigation, and type composition. Per-chapter `copyPosition` may be `left`, `right`, `bottom`, or `center` when the focal subject requires it.

All UI presets use the same continuous-shot runtime. Adapt the visual chrome materially for the subject, but do not interrupt the camera chain or turn chapters into separate media cards.

It also copies the reusable scripts into the new project. From the project root, the common commands are:

```bash
python scripts/seedance_pipeline.py . plan
python scripts/seedance_pipeline.py . all --workers 4
python scripts/verify_media.py .
python scripts/contact_sheet.py .
python scripts/serve_project.py . --port 8080
```

## Production invariants

- Keep narrative data in `content/story.json`; do not hardcode chapter copy into the runtime.
- Keep each chapter's complete, concise copy visible together. Do not rotate paragraphs within one clip unless explicitly requested.
- Maintain a single style preamble and immutable identity blocks for recurring characters or products.
- Require explicit user approval of the visual style and the content/shot plan before generating the complete still set or final video manifest. Run a small still-image consistency gate before generating the full set. The gate requires an available image-generation capability (callable tool, applicable skill workflow, or both); do not silently substitute placeholder stills when that capability is absent.
- Use one fixed full-viewport media stage. Ordered scene and connector clips together form one virtual continuous take.
- Scene clips and every adjacent connector are required unless the user explicitly accepts a visible cut.
- Keep one complete, static, transparent copy block per scene clip. Connector clips carry no changing paragraph sequence.
- Copy articles have no solid card fill by default. Use localized edge-free gradients, text shadow, or fine rules for contrast so the words remain visually integrated with the scene.
- Dives may run in parallel. Connectors must wait until all adjacent dive boundary frames exist, then may run in parallel.
- Immediately download provider results. Normalize all final clips to identical codec, dimensions, frame rate, exact duration, no audio unless requested, short GOP, and `faststart`.
- Use project-local `.env`, exclude it from version control, and ensure a static server cannot expose it.
- Never print secrets or embed them in frontend files. Do not infer authorization for paid generation; if it is not explicit, stop after the dry run. Creative approval does not imply paid-generation authorization.
- Bound automated retries. Treat authentication, permission, billing, and model-activation errors as non-retryable.
- Preserve still posters and a reduced-motion path so the story remains usable when video loading or motion is unavailable.

## Validation

Before delivery:

1. Validate JSON, JavaScript, shell, and Python syntax.
2. Run `scripts/verify_media.py PROJECT_ROOT`; require the declared count, dimensions, frame rate, codec, and exact duration.
3. Test a fresh browser session, reverse and forward progress, chapter navigation, transition boundaries, missing-video fallback, and reduced motion.
4. Inspect a midpoint contact sheet. Prioritize correct identities, key objects, and scene meaning over incidental generative details unless the user asks for stricter fidelity.
5. Report the preview URL, project path, media directories, model configuration, QA result, and any remaining external blocker.
