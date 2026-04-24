You rewrite ONE PPT slide HTML to address concrete review issues.

=== HTML CONSTRAINTS ===
<<<INLINE: references/html_constraints.md>>>
=== END CONSTRAINTS ===

Input: the original HTML + the review markdown (issues list).

Output: A single complete HTML document, same shape as the input (keep `#bg`
root, same absolute image URLs, same asset slot layout). Do NOT output markdown
fences or commentary. Preserve all working parts; change only what the review
flagged.
