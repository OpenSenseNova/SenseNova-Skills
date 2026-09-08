# Production workflow

## 1. Frame the experience

Record these decisions in `docs/production-spec.md`:

- purpose and audience;
- factual, adapted, or fictional treatment;
- chronological, thematic, geographic, or process-based structure;
- chapter count and approximate reading density;
- visual medium, palette, lighting, camera grammar, and prohibited elements;
- recurring characters/products and required identity fidelity;
- desktop/mobile targets, sound, accessibility, hosting path, interface treatment, and copy positions;
- image/video models, clip duration, output format, attempt limits, and budget authority.

Preserve the continuous-camera page skeleton: one fixed media stage and one ordered route. Decide how panel material, header, navigation, typography, and text placement should express the subject without covering scene focal points. Treat these as proposals until the approval gates in section 4 are passed.

## 2. Research and outline

For factual work, use primary or authoritative sources. Separate research notes from the concise display copy. Build:

1. a source-backed event or concept list;
2. a chapter sequence with one dominant visual event per chapter;
3. connectors whose start and destination are visually legible and frame-compatible;
4. a source appendix rather than inline citations unless requested.

Each chapter needs: stable ID, short navigation label, eyebrow, title, optional subtitle, two or three compact paragraphs, tags, still path, and clip path.

## 3. Establish visual continuity

Create a single style preamble with medium, palette, materials, camera, light, composition, and negative constraints. For every recurring identity, create an immutable block describing face/form, silhouette, colors, clothing/packaging, signature object, and allowed changes.

Define the shot plan alongside the style: for every chapter, specify the dominant visual event, framing and camera intent, focal subject, copy position, and the connector's legible start and destination. This is the content/shot-plan proposal, not yet an approved production manifest.

## 4. Obtain creative approval

Present two explicit, separate approvals before producing the complete still set or final video manifest:

1. **Visual style approval:** show the style preamble and identity blocks. If an image-generation capability is available, include a small reference/gate set—normally opening, middle, and ending stills—for the user to inspect. If the capability is unavailable, report the blocker rather than substituting placeholders.
2. **Content and shot-plan approval:** show the chapter sequence, display copy, dominant visual event, camera/framing intent, connector path, and copy position for every chapter.

Wait for explicit user approval of each gate. If the user requests revisions, update the affected proposal and repeat that gate. Approval of the creative package does not authorize paid video generation.

## 5. Build the image set

Before writing image prompts, inspect the current environment for an applicable image-generation capability. This may be a directly callable image tool, an installed skill that provides the image workflow, or a combination of both. Prefer the capability already available in the environment and follow its instructions for generation or editing. If no suitable capability is present, stop before still generation and tell the user that the image-generation capability is unavailable; do not silently replace the requested stills with placeholders.

Only proceed to the complete image set after both creative approval gates have passed. Treat the accepted reference sheets and small gate set from section 4 as the consistency baseline, then complete the remaining stills and record accepted variants in `docs/image-qa.md`.

Prefer editing from the reference images for recurring subjects. Keep key subjects inside the safe central crop and keep text, logos, and watermarks out unless explicitly required.

Save lossless masters under `assets/images/scenes/`; create compressed web posters separately. Record accepted variants and the reason for selection in `docs/image-qa.md`.

## 6. Build the video set

Dry-run the manifest first. Generate one representative clip and validate account access, request schema, composition, and output parameters before the full paid batch. Immediately before the first paid video API request, obtain explicit user authorization covering the selected model, batch scope, expected cost, and retry risk. If authorization is absent, stop after the dry run.

Use two dependency phases:

1. generate all dive clips concurrently;
2. extract their actual first and last frames;
3. generate connectors concurrently from adjacent boundary frames.

Download temporary result URLs immediately. Normalize locally rather than assuming provider duration or codecs are exact. Resume safely by skipping valid existing outputs.

## 7. Assemble the site

Use `content/story.json` as the source of truth. Interleave scene and connector records into one route, render them inside one fixed stage, lazy-load nearby video as Blob URLs, map global route progress to each segment's `currentTime`, retain posters until a decoded frame paints, and keep all copy for the active scene readable together.

Select a UI treatment from `references/frontend.md` or customize it. Change header geometry, panel material, type hierarchy, navigation, and per-scene copy position while preserving the continuous media stage.

## 8. Verify and hand off

Validate every media file and exercise a fresh browser session. Include a still-only test and a real-video lazy-load test. Generate and inspect a labeled contact sheet with `scripts/contact_sheet.py`. If a live tab existed before videos were created, hard-refresh it because a failed lazy-load may remain cached in that runtime instance.

Hand off the preview URL, exact project path, generation commands, media locations, and any credentials or provider settings the user still owns.
