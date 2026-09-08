# Motion frontend

## Non-negotiable structure

The experience is one virtual continuous take:

```text
scene 0 → connector 0 → scene 1 → connector 1 → … → final scene
```

Render every media segment as an absolutely stacked child of one fixed, full-viewport stage. A single document-height track supplies the route distance. Global progress selects the active segment, maps its local progress to `video.currentTime`, and crossfades only around frame-matched seams. Do not turn scenes into separate cards, articles, or independently sticky media blocks.

The bundled runtime fetches nearby clips as Blob URLs, keeps still posters visible until a sought frame paints, coalesces seeks, and supports reverse travel. A failed clip leaves the poster visible. Under `prefers-reduced-motion`, keep posters and cross-dissolve between them without loading video.

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

## Hosting safety

If a static server exposes the project root, explicitly deny `.env` and other secret files. The generated project includes `scripts/serve_project.py` for safe local preview. Prefer serving a dedicated public directory for external hosting. Confirm MP4 responses include the correct content type and byte-range support.
