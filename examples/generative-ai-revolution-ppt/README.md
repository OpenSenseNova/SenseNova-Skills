# Single-skill example: generative AI revolution PPT generation

This example packages a generated 8-page PPT about the generative AI revolution in the same deliverable shape used by the other examples: docs at the top level, plus a `result/` directory containing the final PPTX and a portable source archive.

[中文版 / Chinese](README_CN.md)

## Input

No bundled input files.

Based on the saved task metadata, the deck was configured as:

- Title: `生成式AI革命：从聊天机器人到内容生产引擎`
- Language: Chinese (`zh-CN`)
- Pages: `8`
- Style direction: `科技展览 × 高端杂志`

## Walkthrough

Representative prompt reconstructed from `task-pack.json`:

```text
Build an 8-page Chinese PPT titled "生成式AI革命：从聊天机器人到内容生产引擎".
Use a tech-exhibition × premium-magazine visual style with bold color accents and varied layouts.
Cover text generation, image generation, video generation, code generation, office automation,
business applications, and end with a closing call to action.
```

The packaged source bundle contains:

1. Deck metadata and planning files (`info-pack.json`, `style-spec.json`, `task-pack.json`, `storyboard.json`)
2. Eight per-page HTML files under `pages/`
3. Referenced images under `images/`
4. Review notes in `review.md`

## Artifacts

- [`result/生成式AI革命_PPTX_20260416_2125.pptx`](result/生成式AI革命_PPTX_20260416_2125.pptx): ready-to-open PPTX
- [`result/生成式AI革命_PPTX_20260416_2125.zip`](result/生成式AI革命_PPTX_20260416_2125.zip): zipped editable source bundle

Inside the zip, the directory `生成式AI革命_PPTX_20260416_2125/` contains:

- `pages/page_01.html ~ page_08.html`: per-page HTML sources
- `images/`: referenced image assets
- `info-pack.json` / `review.md` / `storyboard.json` / `style-spec.json` / `task-pack.json`: saved intermediate artifacts and review notes

## Artifacts overview

```text
result/
├── 生成式AI革命_PPTX_20260416_2125.pptx
└── 生成式AI革命_PPTX_20260416_2125.zip
```
