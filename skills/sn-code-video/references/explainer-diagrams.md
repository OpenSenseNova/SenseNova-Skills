# Explainer diagrams

*When to read:* Explain one idea with animated diagrams: math proofs and constructions, physics and chemistry mechanisms, astronomy, economics graphs, history timelines and processes, children's science. Covers choosing one persistent example, computing every position from the real equations or data, keeping objects identifiable through transformations, labels and reading time, and a fact ledger. Use with the main SKILL.md for any educational or explanatory animation.

An explainer succeeds when the viewer could redraw the idea afterwards. It fails in two ways: it looks good but is wrong (a curve drawn by hand, a date from memory, a lit half of the Moon facing Earth), or it is right but unreadable (labels flash by, everything moves at once). A 10–15 s explainer has room for exactly one idea; a 1–2 minute explainer has room for one question answered in a few connected steps (section 8).

## 1. Plan the idea before the picture

Write three lines in `SPEC.md`:

- **The one idea**, as a sentence the viewer should be able to say ("a phase is how much of the lit half faces Earth").
- **The persistent example**: one object or setup that carries the whole film (one triangle, one ball, one bottle). Do not switch examples mid-film.
- **The visible change** that proves the idea (the same triangles leave different gaps; the timer stops at 12 s).

Then the order of events: establish the objects → show the change → name it (label or formula) → hold the conclusion. Show the animation before the formula, never the formula alone.

## 2. Compute, do not draw by eye

- Every position, curve and angle comes from the actual relation: `y = sin θ` sampled per frame, Snell's law for the refracted ray, kinematics for a projectile, the real data values for a chart, exact geometry for a proof (shared vertices are the same variables, not two numbers that happen to match).
- Keep one scale and one origin per diagram. If the brief gives numbers (20 m/s, 45°, n = 1.33), the picture must agree with them to the pixel at the stated scale.
- Slow motion is allowed only as a uniform time scale, and say so on screen if the brief cares about time.
- Label teaching values and schematic sizes as schematic ("not to scale") when the brief asks or the real scale would mislead.

## 3. Facts

- Put every claim the film makes (dates, names, constants, results) in `FACTS.md` with its source: the brief itself, or a reliable reference you checked. If you cannot verify a claim and the brief did not give it, leave it out.
- Use the brief's exact wording and numbers. Do not "improve" a date or add a second fact to fill time.
- For history: distinguish when something was invented, demonstrated, published and widely adopted. Clothing, tools and machines must fit the period (no rollers on a 1450s press, no modern cockpit on a 1903 aircraft).

## 4. Identity and transformation

- Objects the viewer follows keep their identity: a triangle that moves is the same mesh sliding and rotating along a path, never a fade-out and a new copy elsewhere. Atoms in a reaction travel to their new molecule; nothing is created or destroyed unless the idea says so.
- One colour = one quantity for the whole film (the sin θ segment and the sine curve share a colour; a² is always the same hue). Limit the palette to the quantities that matter plus neutrals.
- When a shape changes, interpolate a correspondence (vertex to vertex, sector to sector) so the change is traceable.
- Move one thing at a time in the key moment. Secondary motion stays quiet while the main change happens.

## 5. Text, labels and pace

- **Fill the frame.** The diagram that carries the idea spans at least about 60% of the frame width or height. Side panels, legends and counters are secondary: few, large and grouped, not a dashboard of small boxes. When a single board or graph sits in a third of the frame, scale it up or move the camera in.
- **Minimum sizes at 1080p:** labels and readouts at least about 28 px tall, captions or subtitles at least about 36 px, titles at least about 64 px. Measure them in a still; text that only reads when zoomed in does not count.
- Labels sit next to what they name, never on top of it, and follow it if it moves. Measure the text box with the real font and keep a 5% safe margin. Check that labels do not overlap each other (stacked value labels, boxes piling up in one corner).
- Reading time: hold a label or caption about `letters / 15 + 1.5` s after it appears (Chinese `characters / 4.5 + 1.5` s). In a 10–15 s film that means very few words: prefer a few labels plus one closing line.
- Formulas: render with LaTeX (Manim `MathTex`, KaTeX or MathJax to SVG) or a math-capable font; check subscripts, superscripts and minus signs at final size.
- Pace: a short hold to establish, an even main action, a slightly longer hold on the conclusion. Do not stop the main motion for every label.

## 6. Looks that suit explainers

- **3Blue1Brown-like**: near-black blue background, thin light strokes, three or four saturated accents, LaTeX labels, smooth easing. Good for math.
- **Clean diagram**: white or paper background, dark lines, one accent; good for physics and economics.
- **Whiteboard / marker**: strokes that draw themselves on in reading order, slight fixed wobble (generated once, never re-jittered per frame), one accent colour.
- **Picture book (children)**: big simple shapes, rounded friendly characters, one recurring character, large rounded labels, warm palette, no scary imagery. See [`references/stylized-looks.md`](stylized-looks.md) for paper and crayon textures.
- **Period style (history)**: sepia photo grain, woodcut hatching or a period poster palette; keep the information legible on top.

## 7. Checks specific to explainers

Before the final render, view stills at the moments the idea depends on and verify against the numbers: the curve value equals the point height; the angle readout matches Snell's law; the counter stops at the stated value; the atom tally is unchanged; every receding line meets the vanishing point. Write each check and its result in `VERIFY.md`.

## 8. Longer explainers (1–2 minutes)

- Organize around one central question and answer it in 3–6 steps, each adding one piece: setup → mechanism step by step → the key insight → a short recap or application. Each step reuses the persistent example and the colour code from the steps before.
- Open with the question or a surprising observation within the first few seconds; end on the answer in one line.
- Give difficult steps more time and simple ones less; one clear slow-down at the key insight.
- A recap is visual (the pieces assembled in one frame), not a wall of text.

## 9. Narration or captions

Follow the brief: it says whether the film is narrated or explained by captions over music and effects. When it is open, decide from the audience and length. For narration, script budgets, TTS, checks, subtitles and mixing are in [`references/sound-design-and-narration.md`](sound-design-and-narration.md); the essentials are below.

- **Captions only:** short lines, one idea each, placed near what they describe; the picture must carry most of the meaning.
- **Narration:** write the script first and budget it against the duration: about 130–150 words per minute in English, about 220–260 characters per minute in Mandarin, slower for technical passages. Generate the voice with a TTS engine available in the environment, measure each line's real length, then time the animation to the voice (not the other way round). Show synchronized subtitles in a reserved band that never covers the diagram. Say numbers aloud as words in the TTS text and show them as digits on screen. Check the final mix (see the main `SKILL.md`, section 10).

Common mistakes: a label covering the object it names; the conclusion line shown for under a second; a second, unrequested fact or example; colours that change meaning; a hand-drawn approximation where an exact curve was required; Chinese text rendered with a font that lacks the glyphs.
