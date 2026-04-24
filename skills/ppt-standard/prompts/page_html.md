You generate ONE complete HTML page for a PPT slide.

=== HTML CONSTRAINTS ===
<<<INLINE: references/html_constraints.md>>>
=== END CONSTRAINTS ===

Input: style_spec.json + outline.pages[i] (current page) + asset_plan.pages[i]
(with local_path / quality_review fields) + (optional) raw_documents.json excerpts.

Output: A single complete HTML document (doctype + html/head/body + one `#bg` root),
no markdown fences, no commentary. Use **absolute file:// URLs** for all images
(they are provided as absolute local paths in asset_plan).

Hard rules from the constraints above apply. If a slot's image is `status=failed`
(no local_path), render a blank card that fits the layout — do NOT emit placeholder
text or broken <img> tags.
