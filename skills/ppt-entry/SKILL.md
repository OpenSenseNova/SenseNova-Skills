---
name: ppt-entry
description: |
  Entry point for PPT generation. Collects role / audience / scene / page_count /
  ppt_mode (creative or standard), parses uploaded pdf/docx/md/txt files,
  produces task_pack.json + info_pack.json in a new deck_dir, then dispatches
  to ppt-creative or ppt-standard. Use when the user asks to make a PPT /
  presentation / 演示 / PPT.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: true
triggers:
  - "生成 PPT"
  - "做一套 PPT"
  - "做一份演示"
  - "ppt-entry"
---

# ppt-entry

## Hard preconditions

Run `ppt-doctor` hard checks (U1_LM_API_KEY / U1_LM_BASE_URL / U1_API_KEY / node / u1-image-base) at the start of this skill. If any fails, stop and tell the user to run `/skill ppt-doctor`.

## Flow

1. Extract parameters from the user's message:
   - `role` (speaker identity)
   - `audience`
   - `scene` (where the deck will be used)
   - `page_count`
   - `ppt_mode` in {creative, standard}
2. If `task_pack.json` + `info_pack.json` already exist in a deck_dir the user refers to, read them and jump to step 7 (see "Resume" below).
3. For each parameter missing or ambiguous, call `ask_user` one at a time, in the order:
   `ppt_mode -> role -> audience -> scene -> page_count`.
   Use the wording in `references/ask_user_templates.md`. 2-3 options per question; do not write "其他".
4. Create deck_dir.
   - Name: `<topic_concise>_<YYYYMMDD_HHMMSS>`.
   - Parent: `$PPT_DECK_ROOT` or `./ppt_decks`.
   - Create subdirs: `pages/` always; `images/` only if `ppt_mode=standard`.
5. If user attached reference_docs (pdf/docx/md/txt):
   - Run `parse_user_docs.py --files <paths...>` -> `deck_dir/raw_documents.json`.
   - Run u1-text-optimize with `prompts/document_digest.md` over the concatenated text -> `document_digest` JSON object.
   - If digest call fails -> degrade: set `info_pack.document_digest = null`, continue.
6. Query normalization (optional):
   - If user query >= 20 chars and non-list: run u1-text-optimize with `prompts/query_normalize.md`.
   - Failure -> **abort entry** (this is a structural artifact).
7. Write `task_pack.json` + `info_pack.json` to deck_dir (see "Schemas" below). Both must use **absolute paths** for all path-bearing fields.
8. Dispatch to `ppt-creative` or `ppt-standard` based on `task_pack.ppt_mode`.

## ask_user boundary conditions

- User answers multiple params in one turn -> extract all with a single `u1-text-optimize` call; skip asked-already params.
- User's answer isn't in the 2-3 options -> record verbatim; don't force into the enumeration.
- Session interrupted before task_pack.json written -> discard temp params; next entry starts over.
- task_pack.json already exists -> skip param collection, go straight to dispatch.

## Invoking u1-image-base

Resolve `<U1_IMAGE_BASE>` via env var or by locating the installed `u1-image-base` skill (see `references/conventions.md`). All model calls go through:

```bash
python <U1_IMAGE_BASE>/u1_image_base/openclaw_runner.py u1-text-optimize \
  --system-prompt-path <SKILL_DIR>/prompts/document_digest.md \
  --user-prompt "$(cat <<EOF
<concatenated query + doc excerpts>
EOF
)" \
  --output-format json
```

Parse the JSON stdout; `result` holds the model output (which should itself be JSON per the prompt).

## Schemas

`task_pack.json`:

```json
{
  "deck_id": "AI产品发布会_20260318_154500",
  "deck_dir": "/abs/path/ppt_decks/AI产品发布会_20260318_154500",
  "ppt_mode": "creative",
  "params": {
    "role": "...",
    "audience": "...",
    "scene": "...",
    "page_count": 10
  },
  "created_at": "2026-04-21T15:45:00+08:00",
  "skill_version": "0.1.0"
}
```

`info_pack.json`:

```json
{
  "user_query": "...",
  "query_normalized": {"topic": "...", "key_points": ["..."]},
  "user_assets": {
    "reference_images": ["/abs/..."],
    "reference_docs": ["/abs/..."],
    "reference_docs_failed": []
  },
  "document_digest": {
    "topic_summary": "...",
    "key_sections": [],
    "key_points": [],
    "data_highlights": []
  },
  "raw_document_excerpts": {
    "enabled": true,
    "path": "/abs/.../raw_documents.json"
  }
}
```

## Failure handling

- Missing required env var -> stop, tell user `/skill ppt-doctor`.
- `PPT_DECK_ROOT` set but unwritable -> stop.
- Per-file doc parse failure -> record in `reference_docs_failed`, continue.
- `document_digest` LLM failure -> set to null, continue.
- `query_normalized` LLM failure -> abort.

## Output and handoff

Final message includes a short summary:

```
准备就绪：
- 模式: <creative | standard>
- 页数: <n>
- deck_dir: <abs path>
即将进入<创意 | 标准>模式...
```

Then dispatch:
- ppt_mode=creative -> invoke `/skill ppt-creative deck_dir=<abs>`
- ppt_mode=standard -> invoke `/skill ppt-standard deck_dir=<abs>`

## Does NOT

- Do not generate any style / outline / page content (that's the mode skill's job).
- Do not run any image generation.
- Do not write `timing.json` final fields (just seed `stages.entry`).

## timing.json 埋点

Enter entry -> after step 1, before step 2, initialize:

```bash
python <SKILL_DIR>/scripts/timing_helper.py init --path <deck_dir>/timing.json
```

At entry close -> after step 7, before step 8 dispatch, record entry total:

```bash
python <SKILL_DIR>/scripts/timing_helper.py record-stage \
  --path <deck_dir>/timing.json --stage entry --seconds <wall_elapsed>
```

where `<wall_elapsed>` is the wall-clock elapsed seconds since entry began (2 decimals).
