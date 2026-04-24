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

## 1a. Pseudo-element decorations require wrapped text

If an element has a `::before` / `::after` pseudo with a background color / gradient / image (bullet dot, label pill, underline bar, gradient strip, etc.), the host element's text content **must be wrapped in a `<span>`**. The converter paints pseudos as separate shapes; bare text nodes next to a pseudo can get painted over in the exported PPTX and the title disappears.

- ✅ `<div class="head"><span>产能占用</span></div>`
- ❌ `<div class="head">产能占用</div>` (text may vanish in PPTX)

## 1b. Backgrounds are single-layer only

`#bg`, `.wrapper`, and card containers must use **at most one** background layer — a single solid color, OR a single gradient, OR a single `background-image: url(...)`. Multi-layer stacks (`background: linear-gradient(...), radial-gradient(...), url(...), #FFF;`) are not reliably rendered; only the first layer survives the PPTX export. For "photo + overlay" effects use two child elements (`<img class="bg-photo">` + a sibling overlay div), not two background layers on one element.

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
the absolute path to a real local PNG produced by `u1-image-generate`.
Do NOT use `<svg>` placeholders, empty `<div>` blocks, grey squares, or text like "配图待补".

## 6. Charts / tables / diagrams — MUST be code, NOT images

Data visualization of ANY kind (tables, charts, flow diagrams, KPI tiles, architecture diagrams) MUST be written as code. NOT `<img src="...">`.

### Data charts → ECharts (preferred, becomes editable PPTX)

For **bar / line / pie / doughnut / radar / scatter / area** charts, use ECharts:

    <script src="../assets/echarts.min.js"></script>
    <div id="chart_1" style="width: 600px; height: 400px;"></div>
    <script>
      const chart = echarts.init(document.getElementById('chart_1'), null, {renderer: 'svg'});
      chart.setOption({ /* ... */ });
      window.__pptxChartsReady = (window.__pptxChartsReady || 0) + 1;
    </script>

The PPTX converter extracts the ECharts `option` and **rebuilds a native editable chart** inside the PPTX — double-clicking the chart in PowerPoint opens the data editor, same as Excel.

Do NOT hand-roll `<rect>` + `<text>` SVG charts — they become rasterized PNG in the PPTX (can't edit the underlying data) AND the agent frequently miscalculates axis positions / labels.

See `prompts/page_html.md` § "Charts: use ECharts" for complete syntax and example `setOption` for each chart kind.

### Tables → `<table>`

For raw tabular data use `<table>` / `<thead>` / `<tbody>`. The PPTX converter exports these as native tables with editable cells.

### Diagrams (flow, architecture) → `<div>` + inline `<svg>`

Non-data visuals (flow steps, boxes + arrows, org charts) use `<div>` boxes styled with CSS + inline `<svg>` for connector lines. These become rasterized in PPTX but the content is correct.

### KPI tiles → pure CSS

Big number + label + delta → `<div class="kpi">` with flex / CSS. No SVG, no chart.

### Decorations → inline `<svg>` is fine

Wave backgrounds, outlined circles, icon-like shapes — inline `<svg>` is still the right tool.

### Banned

- `<img src="...bar_chart.png">` — no T2I charts
- `background-image: url('...chart.png')` for data content
- Hand-rolled `<svg>` bar/line/pie/radar/scatter charts — use ECharts instead

Data copied into chart / table code MUST be verbatim from the source (inherited_table, outline.data_points, digest.data_highlights). No paraphrase, no unit conversion, no rounding beyond what the source used.

## 7. Canvas size — REQUIRED `.wrapper` at 1600×900

The HTML-to-PPTX converter (`lib/dom_extractor.mjs`) detects the slide canvas via `document.querySelector('.wrapper')`. Every page HTML **must** have:

```html
<body>
  <div class="wrapper">    <!-- 1600×900 fixed; overflow hidden -->
    <div id="bg">...</div>  <!-- decoration layer, z-index 0 -->
    <div id="ct">...</div>  <!-- content layer, z-index 1 -->
  </div>
</body>
```

CSS (comes from `style_spec.base_styles`, already handled):

```css
.wrapper { width: 1600px; height: 900px; position: relative; overflow: hidden; margin: 0 auto; }
#bg { position: absolute; inset: 0; z-index: 0; }
#ct { position: absolute; inset: 0; z-index: 1; padding: 60px; box-sizing: border-box; }
```

Without `.wrapper`, the converter falls back to `body.getBoundingClientRect()` → canvas width = Playwright viewport, height = auto from content flow → not 16:9 → PPTX aspect ratio comes out wrong. This is not optional.
