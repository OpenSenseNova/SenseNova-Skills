# HTML generation constraints

These constraints are inlined into `page_html.md` and `page_rewrite.md`
system prompts. They describe what the downstream converter
(`scripts/export_pptx/html_to_pptx.mjs`) can and cannot faithfully reproduce.

## 1. Supported CSS elements

- Text: headings, body, lists, rich text incl. text-shadow, letter-spacing, line-height
- Images: local files only (remote http(s) auto-downloaded)
- Backgrounds: solid color, linear/radial gradients, background-image + gradient overlay, multi-layer
- Gradient fills (via SVG) with rgba stops
- Tables: colspan, rowspan, cell background, borders
- SVG (base64-embedded)
- Decorations: borders, border-radius, shadow, rotation, opacity
- Asymmetric borders (1-3 sides)
- Pseudo-elements (::before / ::after background-color / background-image)
- mask-image gradient masks (simulated via SVG overlay)
- Page footer (page number)

## 2. Known limits — avoid these

- `mix-blend-mode` — not supported
- Repeating texture backgrounds (`background-size` smaller than element) — may flatten
- CSS animations / transitions / :hover — dropped
- Custom fonts require target device to have them installed
- Image `opacity<1` simulated via background-color overlay (matching required)

## 3. Background resolution priority (slide background)

1. `#bg` element's `background-image`
2. `#bg`'s child `<img>` that covers >= 90% of `#bg`
3. `#bg`'s `background-color`
4. `.wrapper` background
5. `body` background
6. Default `#FFFFFF`

Always wrap a slide's primary background in `#bg`.

## 4. Motif `data-layer` conventions

When a slide has recurring decorative motifs declared in `style_spec.json`:

- Background motif: `<div data-layer="bg-motif" data-motif-key="...">...</div>`
- Foreground motif: `<div data-layer="fg-motif" data-motif-key="...">...</div>`

Without these tags the converter's gate may reject the HTML.

## 5. real-photo slot rule

Any asset slot whose `asset_plan` intent implies a real photograph MUST reference
the absolute path to a real local PNG produced by `sn-image-generate`.
Do NOT use `<svg>` placeholders, empty `<div>` blocks, grey squares, or text like "配图待补".

## 6. Canvas size (advisory, not gated)

- 16:9 aspect ratio
- Recommended: 1280x720 or 1600x900
- Write explicit `width` and `height` on the outer slide container.
