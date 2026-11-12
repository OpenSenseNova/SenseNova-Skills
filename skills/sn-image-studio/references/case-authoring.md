# Publish a supplied image case

Use this workflow when the maintainer supplies an effect image and a prompt for other users to adapt. The gallery, host rewrite task and image runner share `assets/web/catalog-prompts.json`; adding a case requires no frontend code changes.

The maintainer's minimum submission is a prompt and its effect image. Derive display metadata and input requirements when publishing; author-written style-preservation rules are optional. Empty `recipe.preserve`, `editable` and `checks` lists are valid: the Agent uses the current prompt, sample and user requirements to understand the effect. `archived: true` hides a starter case from the gallery while keeping saved drafts and task IDs addressable.

Publish only information that helps users select and adapt the example: the prompt, preview, required inputs, style guidance, and public attribution. Keep private document links, spreadsheet locations, import logs, local file paths, and development notes outside the published catalog.

Prepare the original prompt as a UTF-8 text file, its effect image as PNG/JPG/WebP, and a metadata JSON file. This example describes a text-to-image case:

```json
{
  "id": "paper-landscape",
  "name": "纸雕山水",
  "category": "纸雕 · 微缩",
  "mode": "generate",
  "style": "层叠纸雕、自然山水、微缩建筑与柔和阴影。",
  "suggestion": "用这个风格画我的家乡桂林",
  "sourceLabel": "维护者提供 · 已验证 Prompt",
  "requiredInputs": 0,
  "width": 1664,
  "height": 2496,
  "recipe": {
    "effect": "以层叠纸片构成自然山水，用微缩建筑和纸张投影建立尺度与纵深。",
    "preserve": ["纸张纤维与切边", "层叠构图与微缩尺度", "柔和接触阴影"],
    "editable": ["地点、地貌与建筑", "季节、主色和可见文案"],
    "inputRoles": [],
    "checks": ["地点特征准确", "纸张层次清晰", "用户指定文案准确"]
  }
}
```

Use a verified source label only when there is supporting evidence. Describe sample results without claiming that every adaptation will reproduce them exactly. Public source links and required attribution may be included in `source` and `sourceLabel`.

Publish with:

```bash
python3 "$SKILL_DIR/scripts/catalog.py" add \
  --case-file /absolute/path/case.json \
  --prompt-file /absolute/path/prompt.txt \
  --preview /absolute/path/effect.webp
python3 "$SKILL_DIR/scripts/catalog.py" validate
```

The importer preserves the full prompt including whitespace, copies the preview into the skill using a content-based filename, validates metadata, and atomically updates the library. Existing IDs require `--replace`. Refresh the webpage to load the new case. Existing drafts are retained; a changed case revision requires a page refresh before new tasks can be submitted.

For editing cases set `mode` to `edit`, `requiredInputs` to the minimum number of user-uploaded images, and describe each required image in `recipe.inputRoles` in order. Optionally pass `--before /absolute/path/source.webp` and add `beforeLabel` to metadata. To show several originals on the canvas, list their local asset paths in `inputImages`, including the `before` image. These sample images are for display. The user supplies their own inputs, can edit each role and move images into the intended order.

The recipe describes the visual effect and adaptation decisions. Keep case-specific details here rather than adding another globally discoverable skill. Name and style descriptions are rendered as text; previews must be local assets. Model calls use the standalone `scripts/images.py` client, this skill's own Python requirements and the user's SenseNova configuration.

## Bilingual prompts

For a bilingual example, include complete `promptLocales` entries for `zh-CN` and `en`. Translate image-making instructions with the same subject, composition, quantities, materials, palette, and constraints. Preserve literal titles, captions, labels, signatures, dates, and brand text exactly. Keep the supplied `originalPrompt` unchanged.

`promptLocalization.sourceLanguage` identifies the original language for saved-draft migration. `sourceSha256` is the SHA-256 of the original UTF-8 prompt; `preservedText` lists literal strings that must occur in both translations. Validation checks that the translations match the current source and retain those strings. The webpage displays and submits the selected language, with independent draft histories.
