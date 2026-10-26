# Prompting patterns

Use an approved [preset](style-presets.md) or custom direction and the available image-generation capability. The initializer writes shared image rules to `prompts/style-preamble.txt` and video rules to `prompts/style-motion.txt`.

Shared video rules govern rendering, identity and temporal consistency; camera path, speed and environmental actions belong in each clip prompt. Inspect the combined prompt for conflicts before submission. Existing projects retain copied prompts and need explicit updates when these rules change.

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

For factual places, verify required silhouettes, materials and spatial relationships against authoritative references. Record uncertainty and omit unsupported details from display copy. Stylization may change rendering without changing identifying geometry. Distinguish artistic travel compression from literal geography; use a legible bridge between distant places without implying false adjacency.

## Dive motion

Describe restrained movement that preserves the source image:

```text
Use image 1 as the sole visual reference. Preserve identities, layout, palette, and materials.
[Duration]-second continuous shot. [Small environmental motion]. [One subtle character action].
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

Choose one dominant event that serves the story and fits the duration. Pass through openings, never solid architecture.

Record departure/arrival framing, physical path and intermediate view, duration and reveal timing, and visible success criteria. Design adjacent endpoints for that path before generating them. First/last-frame conditioning constrains endpoints, not the intervening trajectory; identity continuity does not require a character to stay in frame throughout.

Use a temporal prompt such as:

```text
Image 1 is the departure; image 2 is the destination.
One continuous [duration]-second shot:
Opening: [viewpoint and exit direction].
Middle: [physical path and visible intermediate event].
Arrival: [reveal, approach and settling into image 2].
Preserve the approved identities and rendering style as perspective changes.
Follow the planned camera event; no unintended cut, morph, text or watermark.
```

Match duration to the manifest and allow time for both travel and settling. Phase timing is prompt guidance, not an API control. The pipeline uses one global duration; per-item durations are unsupported. For mixed durations, use separate manifests and output IDs or extend request generation, normalization and validation together.

## Motion acceptance

- Inspect the actual path and intermediate views against the table and approved plan; matching endpoints alone is insufficient.
- Reject unplanned cuts or substitutes such as a dissolve or walking follow when camera travel was required. Legitimate foreground occlusion is allowed; a hidden discontinuous jump is not.
- Require a readable destination and settling time appropriate to the planned duration. Record observed phases and timestamps in video QA.
- If the move fails, simplify its path or revise its boundary framing/duration within authorized scope. Fix conflicting instructions before adding more negatives.

## Style drift from still to clip

Compare the clip's first frame with its source still side by side. Record minor drift as acceptable only when it preserves the approved visual direction and fidelity requirements; otherwise revise or seek approval for the changed look.
