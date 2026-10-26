# Coordinated style presets

The selected style governs visual treatment across HTML, still-image generation, and video motion. Interface treatment is an independent choice. Do not infer `folio`, `caption`, or `graphic` from a style name, and do not mix visual presets unless the user intentionally asks for a hybrid.

The HTML preset supplies color and type defaults, not a fixed composition. A project may add `meta.accent` to `content/story.json` when an explicit brand color should override that preset.

## Anime (`--style anime`)

- HTML: warm paper-white background, ink-blue text, coral accent, rounded display type, crisp labels, lightly graphic shadows.
- Still images: polished theatrical anime illustration, clean controlled linework, cel shading with selective soft gradients, expressive but identity-stable faces, designed color scripting, layered backgrounds, strong silhouette readability.
- Video: preserve line weight, face proportions, costume colors, and cel boundaries frame to frame. Put parallax, environmental loops and gestures in individual scene prompts; connector camera paths follow the shot plan. Avoid line boil, face drift, flicker, extra fingers, and uncontrolled smear frames.
- Best for: mythology, youth stories, explainers, stylized history, fantasy journeys, and character-led product worlds.

For real-place travel and heritage subjects, this user's preferred anime register is Japanese animated-feature **background art**, not theatrical character illustration: transparent clear sky with soft cloud modelling, diffuse low-contrast light, delicately drawn architecture with simplified but accurate textures, an airy high-key palette, and a quiet, hopeful, healing mood. Write "hand-painted background art for an animated feature film" and exclude photographic realism, a 3D render look, thick cartoon outlines, and chibi. Keep the real building forms accurate: the stylization applies to rendering, not to architecture. When the brief calls for youth, travel, or healing, add one recurring traveller seen only from behind (small in frame, locked outfit and bag) instead of detailed foreground faces; it carries the mood and supplies a continuous protagonist without identity risk.

## Cinematic (`--style cinematic`)

- HTML: restrained warm-neutral palette, serif display typography, dark compact controls, soft localized image gradients.
- Still images: authored film still, believable production design, motivated practical lighting, cinematic dynamic range, natural lens behavior, controlled depth of field, atmospheric perspective, fictional casting rather than recognizable actors.
- Video: physically plausible movement, stable wardrobe and props, motivated camera grammar, camera movement specified per clip, consistent exposure and color grade. Avoid abrupt lens changes, glossy AI skin, temporal warping, excessive slow motion, and trailer-style cuts unless requested.
- Best for: historical narratives, documentaries, brand films, travel, architecture, and dramatic nonfiction.

## CGI (`--style cgi`)

- HTML: cool mineral background, deep slate text, cyan-teal accent, precise sans-serif typography, subtle glass and inset highlights.
- Still images: high-end authored CGI, coherent PBR materials, controlled topology and silhouette, physically based lighting, ray-traced reflections used sparingly, volumetric depth, polished but not plastic surfaces.
- Video: stable geometry, material IDs, rig proportions, lighting direction, and simulated effects. Use smooth virtual-camera motion and believable secondary animation. Avoid mesh melting, texture swimming, reflection flicker, rubbery motion, and random particle changes.
- Best for: science, technology, industrial systems, speculative worlds, architecture, products, and data-driven environments.

## Customization

Preserve the preset's consistency rules while changing palette, period, cultural references, or genre. Do not imitate a living artist by name; describe observable visual properties instead. Record deviations in the project production spec so image, video, and HTML layers stay aligned.

A user may replace the preset entirely mid-production, after the style gate, because the look only becomes concrete once sample stills exist. When that happens, edit `prompts/style-preamble.txt` and `prompts/style-motion.txt` in place: every scene prompt is recombined with them at request time, so one edit restyles the whole set. Still regenerate every scene, because the old masters carry the discarded look, and record the reversal in the image QA log with the consumed attempts.

## Shared rendering versus camera motion

The generated `style-motion.txt` is shared by scenes and connectors. Keep it neutral about camera speed, travel distance and framing: preserve rendering style and identity while allowing the planned perspective changes. Put slow scene movement and dynamic connector paths in their respective clip prompts. When adapting an existing project, inspect its combined prompts for obsolete global movement limits; preserve request caches and use new IDs for authorized changed requests.
