# Coordinated style presets

The selected style governs visual treatment across HTML, still-image generation, and video motion. Interface treatment is an independent choice. Do not infer `folio`, `caption`, or `graphic` from a style name, and do not mix visual presets unless the user intentionally asks for a hybrid.

The HTML preset supplies color and type defaults, not a fixed composition. A project may add `meta.accent` to `content/story.json` when an explicit brand color should override that preset.

## Anime (`--style anime`)

- HTML: warm paper-white background, ink-blue text, coral accent, rounded display type, crisp labels, lightly graphic shadows.
- Still images: polished theatrical anime illustration, clean controlled linework, cel shading with selective soft gradients, expressive but identity-stable faces, designed color scripting, layered backgrounds, strong silhouette readability.
- Video: preserve line weight, face proportions, costume colors, and cel boundaries frame to frame. Use restrained multiplane parallax, environmental loops, purposeful character gestures, and clean camera moves. Avoid line boil, face drift, flicker, extra fingers, and uncontrolled smear frames.
- Best for: mythology, youth stories, explainers, stylized history, fantasy journeys, and character-led product worlds.

## Cinematic (`--style cinematic`)

- HTML: restrained warm-neutral palette, serif display typography, dark compact controls, soft localized image gradients.
- Still images: authored film still, believable production design, motivated practical lighting, cinematic dynamic range, natural lens behavior, controlled depth of field, atmospheric perspective, fictional casting rather than recognizable actors.
- Video: physically plausible movement, stable wardrobe and props, motivated camera grammar, subtle handheld or dolly movement, consistent exposure and color grade. Avoid abrupt lens changes, glossy AI skin, temporal warping, excessive slow motion, and trailer-style cuts unless requested.
- Best for: historical narratives, documentaries, brand films, travel, architecture, and dramatic nonfiction.

## CGI (`--style cgi`)

- HTML: cool mineral background, deep slate text, cyan-teal accent, precise sans-serif typography, subtle glass and inset highlights.
- Still images: high-end authored CGI, coherent PBR materials, controlled topology and silhouette, physically based lighting, ray-traced reflections used sparingly, volumetric depth, polished but not plastic surfaces.
- Video: stable geometry, material IDs, rig proportions, lighting direction, and simulated effects. Use smooth virtual-camera motion and believable secondary animation. Avoid mesh melting, texture swimming, reflection flicker, rubbery motion, and random particle changes.
- Best for: science, technology, industrial systems, speculative worlds, architecture, products, and data-driven environments.

## Customization

Preserve the preset's consistency rules while changing palette, period, cultural references, or genre. Do not imitate a living artist by name; describe observable visual properties instead. Record deviations in the project production spec so image, video, and HTML layers stay aligned.
