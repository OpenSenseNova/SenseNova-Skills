# Prompting patterns

Start from one of the coordinated presets in [style-presets.md](style-presets.md), or replace it with a user-defined art direction. Before generating any still, resolve the image capability exposed by the current environment: it may be a callable image tool, an image-generation skill, or both. The initializer writes the chosen image block to `prompts/style-preamble.txt` and the motion block to `prompts/style-motion.txt`. Keep style-motion.txt limited to rendering, identity and temporal consistency; place camera trajectory, speed and environmental actions in each clip prompt. Inspect the combined prompt before submission: remove shared slow/locked/restrained-camera instructions that contradict a connector. Existing projects retain their copied prompts; updating this skill does not migrate them.

## Style preamble

Create one reusable block containing:

```text
MEDIUM: [photography / illustration / clay diorama / collage / ...]
PALETTE: [named colors and contrast]
MATERIALS: [surface and texture]
CAMERA: [lens, angle, distance, projection]
LIGHT: [direction, softness, time or studio setup]
COMPOSITION: landscape frame, safe central crop, readable depth layers
CONTINUITY: use supplied identity references without redesign
EXCLUDE: text, letters, numbers, logo, watermark, unintended modern objects
```

Keep style separate from subject instructions so every scene receives the identical style block.

## Identity block

For every recurring person, creature, product, or vehicle, lock:

- apparent age/form and body proportions;
- face or silhouette geometry;
- dominant colors and materials;
- signature garment, marking, or object;
- allowed scene-specific wear or state changes;
- features that must never change.

Generate a neutral reference sheet before narrative scenes. In scene prompts, name only references that actually appear; too many unrelated references dilute identity control.

## Scene still

```text
[STYLE PREAMBLE]
[RELEVANT IDENTITY BLOCKS]

Create chapter [ID]: [visual event].
Foreground: [anchor detail].
Midground: [main action and identities].
Background: [place, weather, destination].
Story facts that must be readable: [2–4 items].
Keep the main subjects inside the central safe area for a 16:9 web crop.
Static frozen moment; no motion blur; no embedded text.
```

One still should communicate one dominant event. A montage is acceptable only when the art direction explicitly calls for a miniature world or multi-event tableau.

## Landmark fidelity

For real buildings, verify each generated still field by field against the official form description (roof type, eave count, main tile colour versus edging colour, wall colour, podium material, and which structure stands in front of or behind which). Three failure modes recur, and each one silently falsifies the landmark:

- The model paints the accent colour across the whole roof when the real form is a plain body colour with that colour only on ridges and eave edges. Name the split explicitly in the Subject sentence ("main surface plain grey barrel tiles, ridges and eave edges trimmed in green"), not only in the midground description.
- The model drops a mid-depth building, so the real sequence compresses. Enumerate every building the depth must contain in order and end with "all of these must be present as separate, distinct buildings in depth".
- A secondary landmark that really stands behind the main one on the same axis gets drawn beside it at a similar height. State the offset, the relative height, and the colour contrast between the two.

Treat the official description as the authority when a detail is unverified or contested: draw the commonly published form and keep that detail out of the display copy.

For distant real places, plan a legible spatial or temporal bridge (for example sky or foreground occlusion) and keep the landmarks distinct. Specify when the destination becomes visible and allow time to settle. Treat travel compression as an artistic choice, not a claim that the landmarks are neighbours. Do not force all destinations to appear only in the last instant.

## Dive motion

Describe restrained movement that preserves the source image:

```text
Use image 1 as the sole visual reference. Preserve identities, layout, palette, and materials.
Four-second continuous shot. [Small environmental motion]. [One subtle character action].
Camera [locked / slow push / shallow orbit]. No cut, no redesign, no new character,
no text, no logo, no sudden lighting change. End on a stable readable frame.
```

## Connector motion

Choose the transition from the subject and the relationship between scenes, not from a fixed effect list. These are design options, not guarantees of model behaviour:

| Scene relationship | Candidate camera event | Evidence to require |
|---|---|---|
| A visible gate, arch or colonnade leads out of a scene | Pass through its open space | Opening enlarges, nearby surfaces pass the lens, then a distinct exit reveals the destination |
| Distant places or a large change of elevation | Rise, travel overhead, then descend | Departure shrinks below, viewpoint becomes aerial, destination grows during descent |
| Trees, clouds or another motivated foreground obstruction | Travel through/behind an occluder | Consistent travel direction and near-field parallax before and after occlusion |
| Product details or changes of scale | Orbit/reveal or macro approach into an actual feature | Coherent scale change and preserved object identity |
| Historical or abstract change | Designed environmental/time transformation | The chosen transformation is visible; use only when the brief permits it |

A city travel story may mix pass-through and aerial transitions; a product or historical story may need different choices. Variety should serve the route, not force an arbitrary effect on every pair. Pass through openings or gaps, never solid architecture. Prefer one dominant camera event per connector; avoid stacking a tunnel, ascent, orbit and dive into a short shot.

For each connector, record in the shot plan:
- departure framing and exit direction; destination framing and entry direction;
- dominant event, travel axis and height/scale changes;
- the intermediate opening, obstruction or aerial view that makes movement legible;
- reveal timing, acceleration/deceleration and intended duration;
- visible success criteria and forbidden substitutes.

Design adjacent scene endpoints for that path before generating them. A traveller may leave frame during an aerial move; preserving identity does not require keeping the figure fixed in the foreground. First/last conditioning constrains endpoints, not the intervening trajectory.

Use a temporal prompt such as:

```text
Image 1 is the departure boundary; image 2 is the destination boundary.
One continuous shot of [duration] seconds; main event: [selected camera event].
Opening phase: [starting viewpoint, orientation and acceleration].
Middle phase: [physical path, foreground parallax or altitude change, intermediate view].
Arrival phase: [destination reveal, approach direction, deceleration and final framing].
Preserve [relevant identities and rendering style].
Do not substitute [dissolve / landmark morph / static zoom / walking follow] for this event.
No unrequested cut, text, logo or watermark.
```

Allocate enough time to the middle and arrival; phase proportions are a planning aid, not an API control. Match the written duration to the manifest and simplify the move when it cannot fit. The bundled pipeline currently uses one global duration: per-item duration fields are not supported. If different durations are necessary, use separate manifests and output IDs or extend payload generation, normalization and validation together before submitting.

Keep slow environmental movement in scene clips when appropriate. In a dynamic connector, explicitly prioritize the planned camera event, with enough displacement to read clearly. Compare the final combined prompt with the shot plan rather than adding increasingly emphatic negative words to contradictory instructions.

## Style drift from still to clip

Video models re-render painted stills toward photographic or CG realism: detail sharpens, shadows harden, brushwork softens away. Verify by comparing the clip's first frame with its source still side by side and judging whether both still read as one style system. Accept a mild realism shift when composition, landmark form, and palette are preserved, and record it as a known deviation instead of re-rolling an otherwise correct clip.
