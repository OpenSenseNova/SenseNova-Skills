# Stylized looks

*When to read:* Render a named visual style convincingly in code: ink wash, watercolour, crayon picture book, paper cut-outs, 8-bit pixel art, vaporwave/synthwave, pop-art halftone, constructivist poster, woodcut/engraving, ancient pottery painting, hand-painted anime backgrounds, sepia photo. Covers translating a style name into concrete rules, stable textures that never crawl, procedural paper and brush marks, pixel-grid discipline and post passes. Use whenever the brief names a style, medium or artist's manner.

A style is a set of rules about material, mark, colour and composition, not a filter. Two things make a code-made style look cheap: generic vector shapes with a texture laid on top, and textures that crawl or flicker because they are re-randomized every frame.

## 1. Translate the style into rules

Before drawing, write a short style sheet in `SPEC.md`:

- **Material:** what the image is made of (rice paper and ink, gouache on cut paper, crayon on paper, pixels, printed dots, fired clay).
- **Mark:** how shapes are made (a loaded brush stroke whose edge is the contour; scissor-cut edges; crayon strokes with paper tooth; single pixels; halftone dots).
- **Palette:** a short list of exact colours and their roles.
- **Composition habits:** empty space, flatness or depth, framing.
- **What it is not:** e.g. "ink wash is not vector shapes with a grey fill"; "pixel art has no anti-aliasing".

When the brief names an artist or studio, describe and reproduce the features (palette, mark, composition), never specific artworks, characters or logos.

## 2. Stability rules (the most common failure)

- Generate randomness once with a seed: stroke jitter, paper fibres, crayon grain, halftone offsets. Store it per object.
- Attach texture to the object (its local coordinates or UV), not to the screen, so it moves with the object. Paper grain belongs to the page and stays fixed while things move over it.
- If a style needs a "boiling" hand-drawn line, do it deliberately: switch among 2–3 stored variants on twos (every 2 frames), never fresh noise each frame.
- Check stability with frame strips: adjacent frames must look like the same drawing.

## 2b. Subjects must read before style

A style never rescues an unrecognizable subject. For every named object (koi, pine, pavilion, boat, lantern, animal):

- Design its silhouette first as a plain filled shape from real proportions (a koi: blunt rounded head, body widest at the front third, a narrow tail stalk, a large forked tail, paired pectoral fins). Check it at thumbnail size (about 200 px wide): it should be nameable at a glance. Only then build it from strokes or particles.
- Natural forms are irregular. Mountains are not triangles and trees are not straight sticks: build ridges from layered noise with several peaks, and taper trunks with branches that fork.
- When the shape is made of strokes or particles, the stroke edge and the fill must line up; an outline offset from its wash reads as a mistake.
- Keep each named object large enough to read in the frame (a pavilion that is a 15 px tick is missing).

## 3. Recipes

| Style | Key rules |
|---|---|
| **Ink wash (水墨)** | Warm rice paper (~#F2ECDE) with fixed fibres; ink as opacity multiplied onto paper in about five tones (near-black to pale grey); shapes built from tapered pressure strokes with bristle tracks and dry-brush breaks; soft bleed on wet strokes; large empty areas; at most one small vermilion seal. Mountains: texture strokes (cun) following the slope, dark at ridges, fading into mist at the base; distant ranges as pale, soft, flat washes. Rain or snow: very fine, faint marks at low opacity that never cover the motif; uniform grey bars read as a screen effect, not ink. Particle ink: vary density so cores are dense black and edges feather; uniform dithered grey reads as noise. |
| **Watercolour / picture book** | Paper texture; washes with darker pigment pooling at edges; soft wet-on-wet blooms; wobbly friendly outlines in a darker tone; warm palette; big simple shapes for children. |
| **Crayon / coloured pencil** | Strokes made of many thin lines with gaps where paper tooth shows; fills hatched in one direction; colour builds by layering; outlines slightly broken. |
| **Paper cut-outs (Matisse-like)** | Flat gouache-painted sheets with slightly irregular scissor edges (low-frequency wobble + small notches), faint brush texture inside, a soft drop shadow as if pinned; bold saturated palette on off-white. |
| **8-bit pixel art** | Draw on a true low-res buffer (e.g. 320×180), quantize positions when drawing (keep motion continuous underneath), palette ≤ 16 colours, dithering instead of gradients, upscale by an integer factor with nearest-neighbour. Zoom into a still to confirm every pixel is a crisp square. At 320×180, one-pixel sparks are nearly invisible: give hero effects (fireworks, explosions) 2–3 px bright heads, short trails, enough count to fill a good part of the sky, and the brightest colours on screen; keep windows, stars and reflections dimmer than them. |
| **Vaporwave / synthwave** | Hot pink, violet, cyan, pastel mint and peach on purple-black; striped low sun; perspective neon grid; chrome type; bloom; subtle scanlines and chromatic aberration that never hide text. |
| **Pop-art / comic** | Thick black outlines, flat primaries, Ben-Day dots (fixed grid, dot size encodes tone), jagged burst shapes, action lines, slanted bold lettering with drop shadow. |
| **Constructivist poster** | Red, black, cream; diagonals at 30–45°; wedges, circles, bars; bold sans capitals set on diagonals; print grain; decisive, machine-like motion. |
| **Woodcut / engraving** | Cream paper, black hatching whose direction follows form, cross-hatching for shadow, limited sepia accent; hatching fixed to objects. |
| **Greek black-figure pottery** | Orange-red clay; figures as glossy black silhouettes; details incised as thin lines showing the clay colour; meander and tongue bands; a little added red or white. |
| **Hand-painted anime background** | Big soft cumulus with painterly edges, warm-to-cool sky gradients, light catching cloud undersides, layered foliage strokes; painted layers fixed, only gentle drift. |
| **Sepia / old photograph** | Warm monochrome, lifted blacks, soft vignette, grain that stays fixed unless a film flicker is wanted (ffmpeg `noise=alls=8:allf=t` adds moving grain at encode time). |

## 4. Techniques

- **Procedural paper:** low-frequency value noise for mottling + a few hundred thin, slightly curved fibre lines at low opacity + fine grain; render once to an offscreen canvas and reuse.
- **Brush stroke:** a centreline (spline) × a pressure profile (thin–thick–thin) × width noise; draw many thin bristle lines along it with ink load decreasing along the stroke; for dry brush, drop segments where noise is low.
- **Bleed / wet edge:** blur a copy of the wet layer, threshold softly, and darken the boundary ring (edge pigment accumulation).
- **Halftone:** sample tone on a rotated grid; dot radius ∝ √darkness; keep the grid fixed in screen or object space as the style requires.
- **Post passes:** in WebGL, a full-screen fragment shader for scanlines, chromatic aberration, bloom, vignette; in Canvas, composite layers with `globalCompositeOperation` (`multiply` for ink and paper, `screen` for glow).

## 5. Checks

- A still from the film next to your style sheet: material, mark, palette, composition all present?
- Zoom to 100% on edges: pixel art crisp; cut paper irregular but clean; ink edges soft but not blurry mush.
- Frame strips: textures stable, no crawling or shimmering.
- Text in the film uses a face that fits the style and remains readable.
