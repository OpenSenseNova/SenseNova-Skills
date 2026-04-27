---
name: sn-ppt-creative
description: |
  Creative-mode PPT pipeline. One full-page 16:9 PNG per slide.
  LLM / VLM calls go through sn-ppt-standard/lib/model_client.py (shared thin client).
  Text-to-image (the actual png rendering) goes through sn-image-base/scripts/sn_agent_runner.py.
  Expects task_pack.json + info_pack.json already written by sn-ppt-entry.
metadata:
  project: SenseNova-Skills
  tier: 1
  category: scene
  user_visible: false
triggers:
  - "sn-ppt-creative"
---

# sn-ppt-creative

## Call-routing policy

| Kind | Backend |
|---|---|
| LLM (text) | `$PPT_STANDARD_DIR/lib/model_client.py` → `llm(sys, user)` |
| VLM (image understanding) | `$PPT_STANDARD_DIR/lib/model_client.py` → `vlm(sys, user, images)` |
| T2I (image generation) | `$SN_IMAGE_BASE/scripts/sn_agent_runner.py sn-image-generate` |

Never mix — LLM / VLM through sn-image-base, or T2I through model_client — both violate policy.

## Preconditions

- `<deck_dir>/task_pack.json` exists and `ppt_mode == "creative"`
- `<deck_dir>/info_pack.json` exists
- `<deck_dir>/pages/` exists
- `$SN_IMAGE_BASE` env var (OpenClaw-injected) points at the sn-image-base skill root
- `$PPT_STANDARD_DIR` env var points at the sn-ppt-standard skill root (so we can import `model_client`)

Any missing → stop and tell user to enter via `/skill sn-ppt-entry`.

## Resume

```bash
python3 $SKILL_DIR/scripts/resume_scan.py --deck-dir <deck_dir>
# => {"style_spec_done": bool, "outline_done": bool, "pptx_done": bool,
#     "pages": [{"page_no": 1, "action": "skip|render_only|full"}, ...]}
```

Dispatch:

| Manifest | Do |
|---|---|
| `style_spec_done == false` | Run Stage 2 |
| `outline_done == false` | Run Stage 3 |
| per-page `action == "full"` | Run Stage 4.1 + 4.2 |
| per-page `action == "render_only"` | Run Stage 4.2 only (prompt.txt already on disk) |
| per-page `action == "skip"` | Skip |
| `pptx_done == false` (all pages done or failed) | Run Stage 5 |

## Stage 2 — style_spec.md  (LLM or VLM via model_client)

One independent exec tool_call. Two branches based on reference images.

**Branch A (no ref images, or all missing on disk)** — use `model_client.llm`:

```bash
python3 -c "
import sys, pathlib, json
sys.path.insert(0, '$PPT_STANDARD_DIR/lib')
from model_client import llm

deck = pathlib.Path('<deck_dir>')
tp = json.loads((deck / 'task_pack.json').read_text())
ip = json.loads((deck / 'info_pack.json').read_text())

sys_prompt = open('$SKILL_DIR/prompts/style_from_query.md').read()
user_prompt = json.dumps({
    'params': tp['params'],
    'query': ip.get('user_query'),
    'digest': ip.get('document_digest'),
}, ensure_ascii=False)

md = llm(sys_prompt, user_prompt)
(deck / 'style_spec.md').write_text(md, encoding='utf-8')
print('style_spec.md ok')
"
```

**Branch B (≥1 reference image on disk)** — use `model_client.vlm`:

```bash
python3 -c "
import sys, pathlib, json
sys.path.insert(0, '$PPT_STANDARD_DIR/lib')
from model_client import vlm

deck = pathlib.Path('<deck_dir>')
ip = json.loads((deck / 'info_pack.json').read_text())
tp = json.loads((deck / 'task_pack.json').read_text())

refs = [p for p in (ip.get('user_assets') or {}).get('reference_images', []) if pathlib.Path(p).exists()]

sys_prompt = open('$SKILL_DIR/prompts/style_from_image.md').read()
user_prompt = f'PPT 主题/参数: {json.dumps(tp[\"params\"], ensure_ascii=False)}\nuser_query: {ip.get(\"user_query\") or \"\"}'

md = vlm(sys_prompt, user_prompt, images=refs)
(deck / 'style_spec.md').write_text(md, encoding='utf-8')
print(f'style_spec.md ok (from {len(refs)} ref images)')
"
```

If `user_assets.reference_images` is non-empty but **all** paths missing on disk: fall through to Branch A and prepend a line `reference_images_missing: <original paths>` at the top of style_spec.md.

## Stage 3 — outline.json  (LLM via model_client)

```bash
python3 -c "
import sys, pathlib, json
sys.path.insert(0, '$PPT_STANDARD_DIR/lib')
from model_client import llm

deck = pathlib.Path('<deck_dir>')
tp = json.loads((deck / 'task_pack.json').read_text())
ip = json.loads((deck / 'info_pack.json').read_text())
style = (deck / 'style_spec.md').read_text()

sys_prompt = open('$SKILL_DIR/prompts/outline.md').read()
user_prompt = json.dumps({
    'style_spec_markdown': style,
    'params': tp['params'],
    'query': ip.get('user_query'),
    'digest': ip.get('document_digest'),
}, ensure_ascii=False)

raw = llm(sys_prompt, user_prompt).strip()
if raw.startswith('\`\`\`'):
    raw = raw.split('\n', 1)[1].rsplit('\`\`\`', 1)[0]
data = json.loads(raw)
assert len(data['pages']) == tp['params']['page_count'], 'page_count mismatch'
(deck / 'outline.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
print(f'outline ok, {len(data[\"pages\"])} pages')
"
```

On failure (non-JSON / length mismatch): **abort**.

## Stage 4 — per-page: one independent exec per page

### 4.1 Compose prompt  (LLM via model_client) — skip if `action == "render_only"`

```bash
python3 -c "
import sys, pathlib, json
sys.path.insert(0, '$PPT_STANDARD_DIR/lib')
from model_client import llm

deck = pathlib.Path('<deck_dir>')
N = <NNN>
style = (deck / 'style_spec.md').read_text()
outline = json.loads((deck / 'outline.json').read_text())
page = next(p for p in outline['pages'] if int(p['page_no']) == N)

sys_prompt = open('$SKILL_DIR/prompts/page_prompt.md').read()
user_prompt = json.dumps({'style_spec_markdown': style, 'page': page}, ensure_ascii=False)

txt = llm(sys_prompt, user_prompt)
(deck / 'pages' / f'page_{N:03d}.prompt.txt').write_text(txt, encoding='utf-8')
print(f'prompt page {N} ok')
"

# sanitize the written prompt in-place: strip hex/rgb/hsl/CSS/px/em/rem etc
# to prevent T2I server-side prompt-enhance from baking them into the image.
# Silent: no chat-facing notification; removals go to stderr only.
python3 $SKILL_DIR/scripts/sanitize_prompt.py --path <deck_dir>/pages/page_<NNN>.prompt.txt
```

### 4.2 Generate image  (T2I via sn-image-base)

`--negative-prompt` 是针对可能带自身 prompt-enhance 的 T2I 后端的最后一道防线：
即使前面的 sanitize 没拦住、或后端重写时引入了新的样式元数据，也通过反向约束压制模型把它们画出来。这段字符串在所有页上都一致。

```bash
python $SN_IMAGE_BASE/scripts/sn_agent_runner.py sn-image-generate \
  --prompt "$(cat <deck_dir>/pages/page_<NNN>.prompt.txt)" \
  --negative-prompt "hex color code, #RRGGBB, rgb(), rgba(), hsl(), hsla(), css, json, yaml, code snippet, pixel values, px, em, rem, pt, color palette text, typography label, design spec, style guide, font stack, hex code, layout annotation, dimensional callout, figma-style spec sheet, wireframe annotation, swatch with numbers" \
  --aspect-ratio 16:9 \
  --image-size 2k \
  --save-path <deck_dir>/pages/page_<NNN>.png \
  --output-format json
```

### 4.3 Failure handling

- 4.1 failure (model timeout / empty / malformed): record `page_no` into `failed_pages`, echo failure line, continue.
- 4.2 failure: same — record, echo, continue.
- **No retries.** **No placeholder PNG.** Don't write 1x1 transparent PNGs to fake success.
- `.prompt.txt` may remain on disk for a later manual re-run of 4.2 only.

## Stage 5 — pptx 打包（一次独立 exec）

所有页图生成后（含部分失败的情况），把 `pages/page_*.png` 平铺打包成 16:9 整册 PPTX，每张图满版一页。由 `scripts/build_pptx.py` 完成，模型只负责执行脚本。

```bash
python3 $SKILL_DIR/scripts/build_pptx.py --deck-dir <deck_dir>
# => {"deck_id": "...", "output": "<deck_dir>/<deck_id>.pptx",
#     "total_slides": N, "included_pages": [...], "missing_pages": [...]}
```

行为约定：

- 输出路径默认 `<deck_dir>/<deck_id>.pptx`；可用 `--output` 覆盖。
- 页序按 `outline.json` 的 `page_no` 排；缺失 `outline.json` 时按 `page_001..page_NNN` 走。
- 缺失的 PNG 会插入空白页并在 stderr 记录一行，**不中止**；这样跟 Stage 4 的"失败跳过"语义一致。
- 脚本失败（依赖缺失 / 写盘失败）：echo 失败原因，**不中止整个 skill**，仍进入 Stage 6 收尾；PNG 已在磁盘上。

依赖：`python-pptx`（与 `sn-ppt-standard` 共用的打包思路；若运行环境未装，由 `sn-ppt-doctor` 的 env check 提示安装）。

## Stage 6 — closing

Emit:

```
创意模式已完成。

📁 输出目录：<deck_dir>
📄 结果文件：
  - style_spec.md
  - outline.json
  - pages/page_001.png ~ page_NNN.png（失败 M 页：page_..., page_...）
  - <deck_id>.pptx（整册，缺失页插入空白）

⚠️ 未完成：
  - page_007：生图返回超时，已跳过（pptx 中为空白页）

下一步：
  - 可直接打开 <deck_id>.pptx 查看整册
  - 或在 pages/ 目录查看 PNG
```

## Progress echo — MANDATORY

| Stage | Example |
|---|---|
| After resume_scan | `已进入 sn-ppt-creative，共 N 页` |
| After Stage 2 | `[1] style_spec.md ✓` |
| After Stage 3 | `[2] outline.json ✓（N 页）` |
| Per page-prompt (4.1) | `[prompt 3/10] ✓` |
| Per page-image (4.2) | `[图 3/10] page_003.png ✓` or `[图 3/10] ✗ 超时` |
| After Stage 5 | `[pptx] <deck_id>.pptx ✓（N 页，缺失 M 页）` or `[pptx] ✗ <reason>` |
| Closing | full summary above |

- Each echo is a chat reply, not a log write.
- Per-page echo is the heartbeat for Stage 4.
- On failure, echo failure line with reason before moving on.

## 🚫 Hard rules

1. **Do NOT loop inside a single exec.** One page = one tool_call.
2. **Do NOT fake images.** Failed T2I → record failed, move on. No 1x1 placeholder PNGs.
3. **Do NOT use `model_client.t2i`** — T2I must go through `sn-image-base`. `model_client` handles only LLM / VLM.
4. **Do NOT use `sn-text-optimize` or `sn-image-recognize`** from sn-image-base — those must go through `model_client.llm` / `model_client.vlm`.
5. **Do NOT retry on first failure.**
6. **Do NOT generate editable JSON from PNG** (out of scope).
