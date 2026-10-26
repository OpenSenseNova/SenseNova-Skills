# Motion frontend

## Non-negotiable structure

The experience is one virtual continuous take:

```text
scene 0 → connector 0 → scene 1 → connector 1 → … → final scene
```

Render every media segment as an absolutely stacked child of one fixed, full-viewport stage. A single document-height track supplies the route distance. Global progress selects the active segment, maps its local progress to `video.currentTime`, and crossfades only around frame-matched seams. Do not turn scenes into separate cards, articles, or independently sticky media blocks.

The bundled runtime fetches nearby clips as Blob URLs, keeps still posters visible until a sought frame paints, coalesces seeks, and supports reverse travel. A failed clip leaves the poster visible. Under `prefers-reduced-motion`, keep posters and cross-dissolve between them without loading video.

Drive automated scroll QA from the segment math, not from element geometry: every segment is absolutely stacked at the top of the stage, so `offsetTop` and `getBoundingClientRect().top` read ~0 for all of them and a geometry-based `scrollTo` silently stays on the first chapter. Compute the target as cumulative `units` (chapter `span`, default 4.6; connector `connectorSpan`, default 1.2) × `viewportHeight`. While there, assert the chapter counter only after the midpoint of a connector — the runtime reports the departure chapter until local progress passes 0.5 by design.

When segment math is not at hand, sweep the page in fixed steps (about a viewport-height per step) instead of guessing absolute offsets, and require every copy block to reach opacity ≥ 0.9 exactly once. Screenshots taken at guessed offsets usually land inside a connector, where copy is hidden by design, and read as missing content. Emulated states also need a reload: set `prefers-reduced-motion` or the device-metrics override through CDP first and then reload, or the check runs against the un-emulated page.

## Wheel snapping and connector timing

Scenes remain scroll-scrubbed. With `meta.scrollSnap: true` (default), mouse wheel and keyboard input stop at the next connector boundary. Continue scrolling in the same gesture to accumulate `meta.snapThreshold` normalized pixels (default 160); then the connector completes automatically and lands on the adjacent scene with its full copy visible. Reversing the gesture before commitment releases the boundary. A gap over 240 ms resets uncommitted intent.

Connector progress follows an elapsed-time clock at `meta.connectorPlaybackRate` (default 0.8, range 0.25–1), independent of wheel magnitude. A five-second clip takes about 6.25 seconds at the default rate. Do not use browser smooth-scroll duration or raw wheel deltas as the connector playback clock. Ignore additional wheel input during the transition and drain momentum before allowing another one. Missing media uses posters; reduced motion keeps native scrolling without fetching video.

Chapter navigation is an explicit jump and cancels any in-flight connector; Escape or scrollbar navigation also cancels it. Preserve native zoom, dialog scrolling, and scrollable copy. Touch gestures retain native scrubbing. Use `scrollSnap: false` to opt back into direct scroll scrubbing for all segments.

QA must verify both directions, below-threshold hold, automatic completion after input stops, no fast-forward from a large wheel burst, no chained transition from momentum, destination copy visibility, navigation cancellation, and reduced-motion behavior. The template owns and cleans up its animation frame and input listeners on unmount.

## Interface presets

All presets share the exact same stage and timeline. They change only page chrome and copy composition:

- **Folio (`ui: folio`)** — offset editorial header, unboxed transparent copy, fine rules, restrained vertical chapter index.
- **Caption (`ui: caption`)** — quiet centered header, wide transparent lower-third composition, minimal scene navigation.
- **Graphic (`ui: graphic`)** — compact block header, transparent outlined copy, assertive labels and progress marks.

Treat these as starting points. Subject-specific changes may reshape the panel, header, typography, and navigation, but must not alter the continuous-shot media topology.

## Copy placement

Each scene has one complete static copy block. Do not rotate paragraphs within a clip. Set `copyPosition` per scene:

- `left` or `right` uses available negative space beside the focal subject;
- `bottom` creates a wide lower-third panel;
- `center` is reserved for sparse title-like scenes and must retain image readability.

Keep copy positions stable for the duration of a scene. During a connector, hide the copy rather than switching paragraphs inside that connector clip. The next scene's copy appears only when its own scene segment begins.

Copy articles are transparent by default: no opaque rectangle, frosted card, or large drop shadow. Protect legibility with a soft localized gradient that has no visible edge, plus restrained text shadow or fine rules. A solid card is an explicit exception for a user-requested brand language, not a default preset.

## Header and navigation

The header stays fixed but visually quiet. It may contain the title, a compact source link, and overall progress. Navigation targets the beginning of each scene's route range, is keyboard-operable, and updates `aria-current` without seeking a different video independently.

Avoid cloning distinctive decorative elements from a reference. Use new geometry, spacing, materials, and type hierarchy while preserving the underlying interaction.

## Responsive and accessible behavior

- On narrow screens, default copy to a bottom panel even when desktop uses left or right placement.
- Keep critical subjects inside a safe central crop; landscape video crops aggressively on portrait screens.
- Preserve semantic headings, paragraphs, lists, and links in the generated copy layer.
- Maintain readable contrast with an edge-free localized gradient, never an opaque full-screen cover or default solid copy card.
- Prime loaded muted videos on the first user gesture for mobile browsers.

## Copy language and localization

The template ships English interface chrome and Latin-first font stacks: the loading status in `index.html`, the sources-dialog labels, and in `src/motion-runtime.js` the source link, the navigation `aria-label`, the scroll hint, the per-chapter "Go to" `aria-label`, plus the `src/app.js` load-error message. When the story language is not English, replace every one of these strings and set `<html lang>` to match, otherwise the delivered site mixes languages around already-localized copy.

Extend `--mh-display` and `--mh-body` in `styles.css` with scripts used by the copy language before the generic `serif` / `sans-serif` fallback — for Simplified Chinese, `"Songti SC"` / `"Noto Serif SC"` for display and `"PingFang SC"`, `"Hiragino Sans GB"`, `"Microsoft YaHei"`, `"Noto Sans SC"` for body. A Latin-only stack leaves CJK glyphs to platform fallback, which produces inconsistent weights and metrics across machines.

Story text itself comes from `content/story.json`, so audit only the three chrome files (`index.html`, `src/app.js`, `src/motion-runtime.js`) for leftover source-language strings.

## Hosting safety

If a static server exposes the project root, explicitly deny `.env` and other secret files. The generated project includes `scripts/serve_project.py` for safe local preview. Prefer serving a dedicated public directory for external hosting. Confirm MP4 responses include the correct content type and byte-range support.
