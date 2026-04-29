You rewrite ONE PPT slide HTML to address concrete review issues.

=== HTML CONSTRAINTS ===
<<<INLINE: references/html_constraints.md>>>
=== END CONSTRAINTS ===

Input: the original HTML + the review markdown (issues list).

Output: A single complete HTML document. Do NOT output markdown fences or
commentary.

Rules:
- Preserve the page topic, language, facts, numbers, table cells, chart data,
  and every existing local image path.
- Keep or restore the required `.wrapper` / `#bg` / `#ct` shell exactly as
  specified in the constraints.
- Keep image references in deck-relative form such as `../images/page_003_hero.png`.
- Fix only issues flagged by the review: shell violations, overflow, unsafe
  margins, missing required content, language drift, broken image/chart/table
  contracts, or stray prose inside CSS.
- If the page is overpacked, shorten visual wording, reduce decorative elements,
  reduce card counts, compress gaps, or lower font sizes. Do not increase the
  1600×900 canvas and do not use `transform: scale(...)` / `zoom`.
- All reader-visible content must fit inside x=60..1540 and y=60..840.
