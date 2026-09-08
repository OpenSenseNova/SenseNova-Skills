# Prompting patterns

Start from one of the coordinated presets in [style-presets.md](style-presets.md), or replace it with a user-defined art direction. Before generating any still, resolve the image capability exposed by the current environment: it may be a callable image tool, an image-generation skill, or both. The initializer writes the chosen image block to `prompts/style-preamble.txt` and the motion block to `prompts/style-motion.txt`.

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

## Dive motion

Describe restrained movement that preserves the source image:

```text
Use image 1 as the sole visual reference. Preserve identities, layout, palette, and materials.
Four-second continuous shot. [Small environmental motion]. [One subtle character action].
Camera [locked / slow push / shallow orbit]. No cut, no redesign, no new character,
no text, no logo, no sudden lighting change. End on a stable readable frame.
```

## Connector motion

For two reference images, explicitly assign semantic order even when both use `reference_image`:

```text
Image 1 is the departure boundary; image 2 is the destination boundary.
Create a continuous journey from [departure] to [destination]. Begin with the visual
language of image 1, travel via [sea / sky / tunnel / map / material transformation],
and settle into image 2. Preserve recurring identities and palette. No cut, no text,
no extra subject, no violent morph, no camera roll. Stable first and last moments.
```

Video prompts should describe changes over time, not repeat the entire still-image description.
