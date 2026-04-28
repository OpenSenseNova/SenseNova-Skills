# Single-skill example: generative AI revolution PPT generation

This example shows how to use SenseNova-Skills' **PPT generation** ability with nothing but a single prompt — no input file at all — to have the agent build a ready-to-open PPTX given a topic, page count, color palette, style requirement, and audience.

[中文版 / Chinese](README_CN.md)

## Input

No bundled input files.

## Walkthrough

Prompt the agent directly:

```text
Build an 8-page Chinese PPT titled "生成式AI革命：从聊天机器人到内容生产引擎".
Use a tech-exhibition × premium-magazine visual style with bold color accents and varied layouts.
Cover text generation, image generation, video generation, code generation, office automation,
business applications, and end with a closing call to action.
```

The agent sequentially produces:

1. Deck metadata and planning files (`info-pack.json`, `style-spec.json`, `task-pack.json`, `storyboard.json`)
2. 8 per-page HTML files under `pages/`
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
├── 生成式AI革命_PPTX_20260416_2125.pptx   # Final PPT (open directly)
└── 生成式AI革命_PPTX_20260416_2125.zip    # HTML source and intermediate artifacts archive
```
