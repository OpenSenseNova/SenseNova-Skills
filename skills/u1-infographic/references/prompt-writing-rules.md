# Prompt Writing Rules

Rules for generating high-quality image generation prompts. Apply these when writing the final prompt in Step 5.

## 1. Visual Precision

Always describe:

- **Background texture** (e.g., off-white aged paper, black halftone shadows, light gray grid texture)
- **Font style** (e.g., handwritten, serif print, colorful block-lettering, monospace technical)

Omitting these causes the image model to make arbitrary choices that undermine the intended aesthetic.

## 2. Color Avoidance

Never use hexadecimal color codes (`#RRGGBB` format). Use specific color names instead.

| Instead of | Use |
|------------|-----|
| `#FF6B6B` | coral red |
| `#2D3748` | deep slate gray |
| `#F6E05E` | warm yellow |
| `#68D391` | sage green |

## 3. Text Citation

All copy intended to appear as text in the image must be enclosed in `"double quotes"`.

- Correct: a bold label reading `"Step 1: Define the Problem"`
- Incorrect: a bold label reading Step 1: Define the Problem

This lets the image model distinguish between descriptive instructions and literal text to render.

## 4. Arrow Minimalism

Minimize the use of arrows. Prefer spatial proximity to imply flow and connection.

When arrows are necessary:

- Specify exact **start point** and **end point** (e.g., "an arrow from the 'Input' box pointing to the 'Process' box")
- Never use vague orientations like "a horizontal arrow" or "a vertical arrow"

## 5. Semantic Correspondence

Every icon, illustration, or decorative element must correspond semantically to the adjacent text content. Avoid generic decorative elements that could apply to any topic.

## 6. Punctuation Hygiene

Never use quotation marks when describing:

- Style (e.g., write: flat design aesthetic — not: "flat design" aesthetic)
- Layout structure (e.g., write: three-column grid — not: "three-column grid")
- Colors or textures
- Moods or feelings

Quotation marks are reserved exclusively for **Rule 3: Text Citation**.

## 7. Step Granularity

If the content contains stages, steps, or a sequence:

- Detail **every single step** individually
- Never merge or compress multiple steps into one
- Each step gets its own visual element and label

## 8. Data & Encoding

All hard data from the source must be:

- Preserved **verbatim** — no paraphrasing of numbers, dates, or proper nouns
- Presented in a visually distinct format: bold text, labeled callout boxes, sticky notes, or data badges
