# Project schemas

## `content/story.json`

```json
{
  "meta": {
    "title": "Story title",
    "kicker": "Optional short genre or series label",
    "subtitle": "Short deck",
    "description": "Search and share description",
    "note": "Optional adaptation note",
    "style": "anime | cinematic | cgi",
    "ui": "folio | caption | graphic",
    "connectorSpan": 1.2
  },
  "chapters": [
    {
      "id": "01-opening",
      "label": "Opening",
      "eyebrow": "Chapter 1",
      "title": "A concise title",
      "subtitle": "Place or phase",
      "accent": "#B85C3C",
      "copyPosition": "left | right | bottom | center",
      "span": 4.6,
      "linger": 0.35,
      "paragraphs": ["Short paragraph one.", "Short paragraph two."],
      "tags": ["Source", "Theme"],
      "still": "assets/images/scenes/01-opening.webp",
      "clip": "assets/video/dives/01-opening.mp4"
    }
  ],
  "connectors": ["assets/video/connectors/01-opening-to-next.mp4"],
  "sources": [{"label": "Source title", "url": "https://example.com"}]
}
```

Requirements:

- `id` values are unique, filename-safe, and stable.
- `style` controls art direction; `ui` controls header, panel, typography, and navigation. Do not infer one from the other.
- For a continuous take, `connectors.length` is `chapters.length - 1`. Use `null` only when the user accepts a visible cut.
- Keep paragraphs short enough to display together at the minimum supported viewport.
- `copyPosition` is optional. Choose it against the scene's focal subject and safe negative space.
- `span` is measured in viewport heights, not seconds. Larger values gives the chapter more reading and motion distance.

## `prompts/video-manifest.json`

```json
{
  "model": "doubao-seedance-2-5-260628",
  "duration": 4,
  "resolution": "720p",
  "ratio": "16:9",
  "generate_audio": false,
  "conditioning_mode": "reference_images",
  "dives": [
    {
      "id": "01-opening",
      "prompt": "prompts/video/dives/01-opening.txt",
      "still": "assets/images/scenes/01-opening.png",
      "output": "assets/video/dives/01-opening.mp4"
    }
  ],
  "connectors": [
    {
      "id": "01-opening-to-next",
      "from": "01-opening",
      "to": "02-next",
      "prompt": "prompts/video/connectors/01-opening-to-next.txt",
      "output": "assets/video/connectors/01-opening-to-next.mp4"
    }
  ]
}
```

`conditioning_mode` values:

- `reference_images`: each local frame uses `role: reference_image`; works well for Seedance multimodal composition and explicit output ratios.
- `first_last`: a connector uses `first_frame` and `last_frame`; choose this when exact boundary anchoring is more important and the selected model supports it. Verify model-specific ratio restrictions.

The first/last frame cache is `assets/video/frames/{dive-id}-{first|last}.png`.
