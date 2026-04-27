---
name: sn-ppt-entry
description: |
  Entry point for PPT generation. Collects role / audience / scene / page_count /
  ppt_mode (creative or standard), parses uploaded pdf/docx/md/txt files,
  produces task_pack.json + info_pack.json in a new deck_dir, then dispatches
  to sn-ppt-creative or sn-ppt-standard. Use when the user asks to make a PPT /
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
  - "sn-ppt-entry"
---

# sn-ppt-entry

## Hard preconditions

Run `sn-ppt-doctor` hard checks (SN_CHAT_API_KEY or SN_TEXT/SN_VISION API keys / SN_IMAGE_GEN_API_KEY / node / sn-image-base) at the start of this skill. If any fails, stop and tell the user to run `/skill sn-ppt-doctor`.

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
4. Create deck_dir — **location is FIXED, do not guess**:
   - Parent: always `$(pwd)/ppt_decks/`. In OpenClaw, cwd at skill-invocation time is the agent's workspace directory (e.g. `~/.openclaw/workspace/`). Do NOT use `/tmp`, the home directory, the repo root, or `$SKILL_DIR` as the parent. Do NOT honor `$PPT_DECK_ROOT` either — it's been removed to avoid drift.
   - Parent directory must be created if missing: `mkdir -p $(pwd)/ppt_decks`.
   - Deck name: `<topic_concise>_<YYYYMMDD_HHMMSS>`.
   - Full deck_dir path: `$(pwd)/ppt_decks/<topic_concise>_<YYYYMMDD_HHMMSS>/`.
   - Immediately resolve to absolute (`realpath` / `Path.resolve()`) before writing it into `task_pack.json` — downstream must see an absolute path.
   - Create subdirs: `pages/` always; `images/` only if `ppt_mode=standard`.
   - If `$(pwd)/ppt_decks/` cannot be created (permission denied) → **abort**, tell the user to check workspace permissions.
5. If user attached reference_docs (pdf/docx/md/txt):
   - Run `$SKILL_DIR/scripts/parse_user_docs.py --files <paths...> --output <deck_dir>/raw_documents.json`. The `--output` flag tells the script to write the JSON itself (recommended — works reliably even on agents that don't handle shell redirection well). The script prints a single-line JSON status `{"status":"ok","output":"...","documents":N,"errors":M}` to stdout when `--output` is used.
   - Call the LLM with `$SKILL_DIR/prompts/document_digest.md` as system prompt + (user_query + concatenated document text) as user prompt. See "Invoking the LLM" below.
   - On success: write `document_digest` JSON into `info_pack.document_digest`.
   - On failure: degrade — set `info_pack.document_digest = null`, continue (do NOT abort entry).
6. Write `task_pack.json` + `info_pack.json` to deck_dir (see "Schemas" below). All path-bearing fields **absolute**.
7. **Caption every image once with VLM** (mandatory, idempotent — runs after `info_pack.json` is written so both pools are visible):
   ```bash
   python3 $SKILL_DIR/scripts/caption_images.py --deck-dir <deck_dir>
   ```
   This script is the **single source of truth** for image-content descriptions:
   - Pool A — doc-embedded images (`raw_documents.json` `documents[*].inherited_images[*]`): caption written into the same JSON as `vlm_caption`.
   - Pool B — standalone uploads (`info_pack.user_assets.reference_images`): caption written into a sister field `info_pack.user_assets.reference_image_captions: {abs_path: caption}`.
   - Already-captioned images are **skipped silently**, so re-running is cheap and safe. Only newly added images incur a VLM call.
   - Failures don't abort: the script reports them in the JSON status; downstream stages fall back to filename / alt / digest hint when a caption is missing.
   Downstream (sn-ppt-standard `cmd_page_html`) reads these cached captions and **never** re-captions — that's the "single source of truth" rule. If you change image files in a deck, delete their `vlm_caption` (or `reference_image_captions[path]`) entry and re-run this script to refresh.
8. Dispatch to `sn-ppt-creative` or `sn-ppt-standard` based on `task_pack.ppt_mode`.

## ask_user boundary conditions

- User answers multiple params in one turn -> extract all with a single `sn-text-optimize` call; skip asked-already params.
- User's answer isn't in the 2-3 options -> record verbatim; don't force into the enumeration.
- Session interrupted before task_pack.json written -> discard temp params; next entry starts over.
- task_pack.json already exists -> skip param collection, go straight to dispatch.

## Invoking the LLM for document_digest

`parse_user_docs.py --output <deck_dir>/raw_documents.json` already creates the file. Then call the LLM with a user prompt that gives only **counts + indices** of tables/images (not row contents) so the LLM can't accidentally paraphrase numbers:

```bash
python3 -c "
import sys, json, pathlib
sys.path.insert(0, '$PPT_STANDARD_DIR/lib')
from model_client import llm

raw = json.loads(pathlib.Path('<deck_dir>/raw_documents.json').read_text())

# Build the digest-safe view: strip tables[] and image paths, keep text + indices
docs_view = []
for d in raw.get('documents', []):
    docs_view.append({
        'doc_index': d['doc_index'],
        'type': d['type'],
        'text': d.get('text',''),
        'tables_count': len(d.get('tables') or []),
        'images_count': len(d.get('inherited_images') or []),
    })

user_prompt = json.dumps({
    'user_query': '<the user's original query>',
    'documents': docs_view,
}, ensure_ascii=False)

sys_prompt = open('$SKILL_DIR/prompts/document_digest.md').read()

out = llm(sys_prompt, user_prompt)
# Parse JSON; if it fails, degrade digest to null (not abort entry)
try:
    digest = json.loads(out)
except Exception:
    digest = None
pathlib.Path('<deck_dir>/digest_tmp.json').write_text(json.dumps(digest, ensure_ascii=False))
"
```

The digest JSON then merges into `info_pack.document_digest`. Downstream stages (outline, page_html) read both `info_pack.document_digest` (structured summary + inherited_tables/images index lists) AND `raw_documents.json` (actual table rows + image paths).

Substitute `$PPT_STANDARD_DIR` with the `sn-ppt-standard` skill install dir.

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
  "user_assets": {
    "reference_images": ["/abs/..."],
    "reference_docs": ["/abs/..."],
    "reference_docs_failed": []
  },
  "document_digest": {
    "topic_summary": "...",
    "key_sections": [],
    "key_points": [],
    "data_highlights": [],
    "inherited_tables": [{"doc_index": 0, "table_index": 2, "title_hint": "..."}],
    "inherited_images": [{"doc_index": 0, "image_index": 0, "caption_hint": "..."}]
  },
  "raw_document_excerpts": {
    "enabled": true,
    "path": "/abs/.../raw_documents.json"
  }
}
```

## Failure handling

- Missing required env var -> stop, tell user `/skill sn-ppt-doctor`.
- `$(pwd)/ppt_decks/` not creatable / not writable -> stop, tell user to check workspace permissions.
- Per-file doc parse failure -> record in `reference_docs_failed`, continue.
- `document_digest` LLM failure -> set to null, continue.

## Progress echo — MANDATORY

Emit a short chat reply at each boundary. Silence between ask_user rounds and mode dispatch is a bug.

| When | Example |
|---|---|
| Right after entering sn-ppt-entry | `已进入 sn-ppt-entry，开始收集参数...` |
| Missing a param | `缺少参数：<role>，马上问你` (then ask_user) |
| All 5 params collected | `参数齐备：mode=standard, role=...。开始创建 deck_dir...` |
| Before doc parse | `检测到 2 个附件，开始解析...` |
| After doc parse | `解析完成：sample.pdf (12 页) / sample.docx (45 段)` |
| Before digest | `[LLM] 正在汇总文档要点...` |
| After digest | `文档摘要已入 info_pack.json` |
| task_pack / info_pack written | `task_pack.json / info_pack.json 已写入 <deck_dir>` |
| Dispatching | `分发到 sn-ppt-creative（deck_dir=...）` |

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
- ppt_mode=creative -> invoke `/skill sn-ppt-creative deck_dir=<abs>`
- ppt_mode=standard -> invoke `/skill sn-ppt-standard deck_dir=<abs>`

## Does NOT

- Do not generate any style / outline / page content (that's the mode skill's job).
- Do not run any image generation.
