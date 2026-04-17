# Runtime Parameter Mapping

This file defines how `u1-infographic` infers runtime arguments for `u1-image-base` tools.

## Inputs

Read from:

- the original user request
- any explicit follow-up confirmation from the user about size or ratio

## Output Arguments

Map into:

- `--image-size`
- `--aspect-ratio`

## Image Size

**Default: `2k`** — always used unless the user explicitly says otherwise. Never ask the user about this.

Rules:

- **Never ask the user about `image_size`.** Default silently to `2k`.
- If the user explicitly asks for lower cost, faster draft, quick concept, or small output, use `--image-size 1k`.
- If the user explicitly asks for higher detail, print-quality, poster-quality, fine text, or large output, use `--image-size 2k`.
- Otherwise use `--image-size 2k` (default).

## Aspect Ratio

Supported values:

- `2:3`
- `3:2`
- `3:4`
- `4:3`
- `4:5`
- `5:4`
- `1:1`
- `16:9`
- `9:16`
- `21:9`
- `9:21`

Use the first matching rule:

1. If the user explicitly gives a supported ratio, use it directly.
2. If the user confirms a ratio preference in a follow-up turn, use that confirmed value.
3. If the user gives only orientation:
   - `Portrait` or `竖屏` -> prefer `9:16`; use `4:5`, `3:4`, or `2:3` when the prompt implies a print poster, editorial layout, or card-style portrait composition
   - `Landscape` or `横屏` -> prefer `16:9`; use `4:3`, `3:2`, `5:4`, or `21:9` when the prompt implies classic slides, photography framing, near-square cards, or cinematic banners
   - `Square` or `方形` -> `--aspect-ratio 1:1`
4. If neither ratio nor orientation is explicit, infer from the scene:
   - phone wallpaper, story card, vertical reel cover, ultra-tall mobile infographic -> `9:16` or `9:21`
   - print poster, book cover, one-page portrait infographic -> `2:3`
   - editorial illustration, portrait card, magazine-style page -> `3:4`
   - social feed poster, product card, portrait marketing creative -> `4:5`
   - avatar, icon, logo mark, square cover -> `1:1`
   - presentation slide, dashboard, classroom chart, classic screen layout -> `4:3`
   - landscape photo, postcard, brochure hero, medium-width banner -> `3:2`
   - near-square desktop card, comparison board, compact infographic panel -> `5:4`
   - banner, keynote cover, widescreen infographic, landing hero -> `16:9`
   - cinematic hero, panoramic banner, ultra-wide header -> `21:9`
   - otherwise -> `16:9`

## Notes

- The skill should pass `expanded_prompt` (from `prompts-expand`) as `--prompt`, not the raw user request.
- `image_size` defaults to `2k` — the Worker Agent must NOT ask the user about it.
- `aspect_ratio` is inferred from the **original `user_prompt`** (before expansion), not from `expanded_prompt`.
- Prefer inference over interruption when there is one clearly reasonable choice.
- Ask the user only when multiple aspect ratios are genuinely plausible and the choice would materially change composition or layout.
- When asking the user, ask for `aspect_ratio` directly instead of a vague "horizontal or vertical" question whenever possible.
- Use `--save-path` to write the output directly to the task's temp directory (`/tmp/openclaw/u1-infographic/<task_id>/round_<N>.png`), avoiding a separate move step.
