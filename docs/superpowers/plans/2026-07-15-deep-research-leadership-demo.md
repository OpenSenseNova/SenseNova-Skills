# Deep Research Leadership Demo Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new offline, self-contained leadership demo that replays seven real Deep Research milestones and exposes the archive's verified findings, report, and citations.

**Architecture:** A Python standard-library builder reads the supplied ZIP, validates and normalizes its final artifacts, then injects one Base64-encoded JSON payload into a standalone HTML template. The generated page uses pure JavaScript reducers/renderers plus thin DOM controllers, so replay behavior, dialogs, downloads, validation, and Markdown escaping can be tested with Node's built-in runner and lightweight stubs.

**Tech Stack:** Python 3 standard library, HTML/CSS, vanilla JavaScript, Node built-in test runner.

**Spec:** `docs/superpowers/specs/2026-07-15-deep-research-leadership-demo-design.md`

---

## File Structure

- Create `examples/deep-research-leadership-demo/build_demo.py`: read the archive, validate provenance totals, construct deterministic snapshots, and write the self-contained output.
- Create `examples/deep-research-leadership-demo/template.html`: own the presentation CSS, semantic shell, inline replay reducer/renderers, dialog behavior, and download behavior.
- Create `examples/deep-research-leadership-demo/index.html`: generated deliverable containing the encoded archive payload and no external dependencies.
- Create `tests/deep-research-leadership-demo.test.mjs`: test builder output, archive fidelity, replay state, rendering, dialogs, downloads, accessibility, and responsive declarations.

The template stays focused on presentation/runtime behavior. The builder owns all archive knowledge and normalization. The generated HTML is committed so the demo opens directly without a build step.

---

## Chunk 1: Archive-Normalized Standalone Demo

### Task 1: Write Archive Fidelity Tests

**Files:**
- Create: `tests/deep-research-leadership-demo.test.mjs`
- Test: `tests/deep-research-leadership-demo.test.mjs`

- [ ] **Step 1: Add the failing builder/output test harness**

Create test helpers that resolve:

```js
const repoRoot = new URL("../", import.meta.url);
const archivePath = new URL("../2026-07-14-china-9-strata-9185.zip", import.meta.url);
const builderPath = new URL("../examples/deep-research-leadership-demo/build_demo.py", import.meta.url);
const outputPath = new URL("../examples/deep-research-leadership-demo/index.html", import.meta.url);
```

Use `spawnSync("python3", [fileURLToPath(builderPath), "--archive", fileURLToPath(archivePath), "--output", tempOutput])`. Assert exit status `0`, output existence, `<!doctype html>`, no `http://`/`https://` resource references, and no import/reference to `examples/deep-research-status-page`.

Create and clean the temporary output deterministically:

```js
const tempDir = mkdtempSync(join(tmpdir(), "dr-leadership-demo-"));
const tempOutput = join(tempDir, "index.html");
after(() => rmSync(tempDir, { recursive: true, force: true }));
```

Assert the committed `outputPath` exists. Build to `tempOutput`, read both files, and assert they are byte-for-byte equal so the committed demo cannot drift from the archive/template.

Extract the encoded payload with:

```js
function decodePayload(html) {
  const match = html.match(/<script id="archive-data" type="application\/octet-stream">([A-Za-z0-9+/=]+)<\/script>/);
  assert.ok(match, "embedded archive payload should exist");
  return JSON.parse(Buffer.from(match[1], "base64").toString("utf8"));
}
```

Assert exact totals, seven dimensions, 36 findings, five content units, 58 citations, `pass`, non-empty report Markdown, and the exact report title.

Assert metadata exactly matches mode `heavy`, run ID `2026-07-14-china-9-strata-9185`, start/completion labels `2026-07-14 06:03` and `2026-07-14 09:37`, and the fixed run-span/elapsed labels. Assert all seven snapshots match the full gate matrix defined in Task 2.

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
node --test tests/deep-research-leadership-demo.test.mjs
```

Expected: FAIL because `build_demo.py` and `index.html` do not exist.

- [ ] **Step 3: Add per-dimension fidelity assertions**

Assert the exact matrix:

```js
const expected = {
  d1: [18, 12, 4], d2: [14, 10, 6], d3: [18, 11, 5],
  d4: [17, 9, 5], d5: [10, 15, 5], d6: [13, 8, 5], d7: [18, 8, 6],
};
```

For every normalized finding, assert `text.length > 0`, `claimIds.length > 0`, and `claimCount === claimIds.length`. Assert the seven archived headlines and five outline titles are non-empty.

- [ ] **Step 4: Run again and confirm the same expected RED cause**

Expected: FAIL only because the builder/output are missing, not because the test file has syntax errors.

### Task 2: Implement the Deterministic Archive Builder

**Files:**
- Create: `examples/deep-research-leadership-demo/build_demo.py`
- Create: `examples/deep-research-leadership-demo/template.html`
- Create: `examples/deep-research-leadership-demo/index.html`
- Test: `tests/deep-research-leadership-demo.test.mjs`

- [ ] **Step 1: Implement ZIP reading and artifact helpers**

In `build_demo.py`, define:

```python
RUN_PREFIX = "2026-07-14-china-9-strata-9185/"

def read_text(archive, relative_path):
    return archive.read(RUN_PREFIX + relative_path).decode("utf-8")

def read_json(archive, relative_path):
    return json.loads(read_text(archive, relative_path))
```

Use only `argparse`, `base64`, `json`, `pathlib`, `re`, and `zipfile` from the standard library. Accept required `--archive` and optional `--output` defaulting to the sibling `index.html`.

- [ ] **Step 2: Normalize exact archive data**

Build:

```python
dimension = {
    "id": plan_dimension["id"],
    "name": plan_dimension["name"],
    "headline": evidence["headline"],
    "claimCount": len(evidence["claims"]),
    "sourceCount": len(evidence["sources"]),
    "sourceIds": [source["id"] for source in evidence["sources"]],
    "findings": [
        {
            "text": item["finding"],
            "claimIds": list(item["claim_ids"]),
            "claimCount": len(item["claim_ids"]),
        }
        for item in evidence["key_findings"]
    ],
}
```

Normalize the five `outline.json.content_units` to `{id, title}`. Read `report.md` verbatim and extract its first `# ` heading as `reportTitle`. Read and preserve `citations.json` as canonical pretty JSON using `ensure_ascii=False, indent=2`. Parse `VERDICT: pass` from `final_review.md` without embedding review internals.

Derive `mode` from `plan.json`, derive `runId` from the ZIP root directory, and derive start/completion labels from the ZIP entry timestamps for `briefing.json` and `report.md`. Validate the derived values against this sample's expected values before adding exact run metadata:

```python
"metadata": {
    "mode": "heavy",
    "runId": "2026-07-14-china-9-strata-9185",
    "reportTitle": report_title,
    "startLabel": "2026-07-14 06:03",
    "completionLabel": "2026-07-14 09:37",
    "runSpanLabel": "真实运行跨度 06:03–09:37",
    "elapsedLabel": "约 3 小时 34 分",
}
```

- [ ] **Step 3: Construct the exact seven replay snapshots**

Use progress `[14, 29, 43, 57, 71, 86, 100]`, exact stage names `需求确认`, `研究规划`, `多主题研究`, `质量核验`, `报告组织`, `写作审校`, `最终交付`, and work modes `scope`, `plan`, `research`, `quality`, `outline`, `review`, `delivery`.

Use these user-facing headlines:

```python
[
  "研究范围与关键口径已经确认",
  "7 个研究维度已经规划完成",
  "多主题研究正在推进",
  "研究材料已经完成质量核验",
  "最终报告结构已经组织完成",
  "报告写作与终审已经完成",
  "最终报告与引用清单已经生成",
]
```

Every snapshot has this complete shape:

```python
{
    "index": 1,                 # 1..7
    "stage": "需求确认",        # exact business stage
    "progress": 14,            # exact ordinal progress
    "workMode": "scope",       # exact mode above
    "headline": "...",         # exact user-facing headline
    "explanation": "...",      # one concise leadership explanation
    "statements": ["..."],      # 1..3 untimed milestone statements
    "dimensionState": "hidden",# hidden|planned|researching|verified
    "unitState": "hidden",     # hidden|organized|written|delivered
    "metricsVisible": False,
    "findingsAvailable": False,
    "reviewPassed": False,
    "reportAvailable": False,
}
```

Gates by snapshot are exact:

| Snapshot | dimensionState | unitState | metricsVisible | findingsAvailable | reviewPassed | reportAvailable |
|---:|---|---|---|---|---|---|
| 1 | hidden | hidden | false | false | false | false |
| 2 | planned | hidden | false | false | false | false |
| 3 | researching | hidden | false | false | false | false |
| 4 | verified | hidden | true | true | false | false |
| 5 | verified | organized | true | true | false | false |
| 6 | verified | written | true | true | true | false |
| 7 | verified | delivered | true | true | true | true |

Use 1–3 specific untimed statements per stage that restate only the gates above, such as `已规划 7 个研究维度` or `5 个报告内容单元已组织完成`. Do not add per-stage timestamps or incremental evidence totals.

- [ ] **Step 4: Validate builder invariants before writing**

Implement `validate_payload(payload)` with exact assertions for:

- seven unique IDs `d1`–`d7`
- claim/source/finding sums `108/73/36`
- unique source IDs `70`
- five units, 58 citations, verdict `pass`
- exact metadata fields/values above and non-empty extracted report title
- seven snapshots with sequential indexes, exact stage names/progress/work modes, non-empty headline/explanation/statements, valid state enums, and the exact gate matrix above
- non-empty report/citation payloads

Raise `ValueError` with a concise builder-facing message on failure.

- [ ] **Step 5: Add the minimal template shell and payload injection**

In `template.html`, include a single literal marker `__ARCHIVE_DATA_BASE64__` inside:

```html
<script id="archive-data" type="application/octet-stream">__ARCHIVE_DATA_BASE64__</script>
```

Create semantic containers `#app`, `#announcement`, `#dimension-dialog`, and `#report-dialog`. Include no external assets.

In the builder:

```python
payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
encoded = base64.b64encode(payload_json.encode("utf-8")).decode("ascii")
output = template.replace("__ARCHIVE_DATA_BASE64__", encoded)
```

Require the marker to occur exactly once, then write UTF-8 output.

- [ ] **Step 6: Build the real deliverable and verify GREEN**

Run:

```bash
python3 examples/deep-research-leadership-demo/build_demo.py \
  --archive 2026-07-14-china-9-strata-9185.zip \
  --output examples/deep-research-leadership-demo/index.html
node --test tests/deep-research-leadership-demo.test.mjs
```

Expected: archive fidelity tests PASS.

- [ ] **Step 7: Commit chunk 1**

```bash
git add examples/deep-research-leadership-demo tests/deep-research-leadership-demo.test.mjs
git commit -m "feat: build leadership demo from research archive"
```

---

## Chunk 2: Replay Runtime And Progress-First Presentation

### Task 3: Add Failing Replay Reducer And Control Tests

**Files:**
- Modify: `tests/deep-research-leadership-demo.test.mjs`
- Modify: `examples/deep-research-leadership-demo/template.html`
- Regenerate: `examples/deep-research-leadership-demo/index.html`

- [ ] **Step 1: Add an inline-script VM harness**

Extract the script marked `data-demo-runtime` and run it in `node:vm`. Provide a complete host context:

- `atob` implemented with `Buffer.from(value, "base64").toString("binary")`
- Node's global `TextDecoder`
- `window` with recorded `setInterval`, `clearInterval`, and `location.reload`
- `document` with `readyState: "loading"` so bootstrap does not run unless a test explicitly invokes it
- element stubs for `getElementById`, `querySelector`, `querySelectorAll`, attributes, `innerHTML`, event listeners, and focus
- minimal `Blob`/`URL` placeholders, replaced by focused stubs in download tests

Expose declared top-level functions from the VM context; do not add test-only production APIs.

- [ ] **Step 2: Write reducer tests**

Assert:

```js
replayReducer({ index: 0, playing: false }, { type: "PLAY" })
// => { index: 0, playing: true, finalHold: false }

replayReducer({ index: 0, playing: true }, { type: "TICK" })
// => index 1

replayReducer({ index: 6, playing: false }, { type: "PLAY" })
// => index 0, playing true
```

Cover `PAUSE`, `PREVIOUS`, `NEXT`, `SELECT`, `RESTART`, the disabled boundaries, arrival at snapshot 7 after six ticks, one final-hold tick, and pause after the seventh tick.

Assert `TICK` is ignored when `playing=false`. Assert `PAUSE`, `PREVIOUS`, `NEXT`, and `SELECT` always set `playing=false` and `finalHold=false`, including when dispatched during snapshot 7's final hold.

- [ ] **Step 3: Write rendered-state tests**

Assert every snapshot gate:

- Snapshot 1 includes `阶段 1 / 7`, `14%`, `流程阶段进度`, and no dimensions/metrics/units.
- Snapshot 2 includes all seven planned names and contains none of `108`, `73`, `36`, or findings text.
- Snapshot 3 shows seven `研究中` states and contains no dimension claim/source/finding counts.
- Snapshot 4 contains the exact per-dimension `18/12/4 ... 18/8/6` matrix, aggregate `108/73/36`, and `已核验`.
- Snapshot 5 shows the five unit titles and does not render the research work-card layout as the primary work surface.
- Snapshot 6 marks all five units written, shows `终审通过`, and keeps all three report/download actions disabled.
- Snapshot 7 contains `100%`, `108`, `73`, `70`, `36`, `58`, all five units, and all three enabled actions.

Every snapshot asserts the report title, run ID, `Heavy 深度模式`, fixed run span, milestone label, and lifecycle items with visible text/icon states rather than color alone.

- [ ] **Step 4: Write failing bootstrap/fallback tests**

Call `validateArchiveData()` with a valid payload and with mutations for wrong snapshot progress, missing dimension, incorrect totals, empty report, and wrong verdict. Assert invalid bootstrap rendering contains `演示数据暂时无法加载`; click its reload action and assert `window.location.reload()` was called.

- [ ] **Step 5: Write failing bound-control and timer tests**

Invoke `bindControls()` with element/timer stubs. Assert:

- play creates exactly one 8,000 ms interval; repeated play creates no second interval
- recorded callbacks advance at seconds 8–48, hold snapshot 7 through second 56, then pause and clear the interval
- pause/previous/next/select/restart clear any existing interval before applying state
- restart creates exactly one replacement 8,000 ms interval after clearing the old one
- stage-button click selects its exact index and pauses
- boundary controls expose disabled state at snapshots 1 and 7
- rerender updates the polite announcement

- [ ] **Step 6: Run tests and verify RED**

Expected: FAIL because reducer/renderers and controls are not implemented.

### Task 4: Implement Replay State And Leadership UI

**Files:**
- Modify: `examples/deep-research-leadership-demo/template.html`
- Regenerate: `examples/deep-research-leadership-demo/index.html`
- Test: `tests/deep-research-leadership-demo.test.mjs`

- [ ] **Step 1: Decode and validate the embedded payload in the browser**

Implement `decodeArchiveData()` using `atob`, `Uint8Array`, and `TextDecoder`. Implement `validateArchiveData(data)` with the same exact invariant checks as the builder. On failure, render the specified `演示数据暂时无法加载` fallback and bind `重新加载` to `window.location.reload()`.

- [ ] **Step 2: Implement the pure replay reducer**

State is:

```js
{ index: 0, playing: false, finalHold: false }
```

`PLAY` at indexes 0–5 preserves the current index and sets `playing=true`; `PLAY` at index 6 returns to index 0 and starts playback. `TICK` does nothing while paused. While playing, it advances indexes 0–5, marks `finalHold=true` when first arriving at 6, then pauses and clears `finalHold` on the next tick. `PAUSE`, `PREVIOUS`, `NEXT`, and `SELECT` always clear both `playing` and `finalHold`. `RESTART` returns to 0, clears `finalHold`, and plays. Clamp all indexes to 0–6.

- [ ] **Step 3: Implement pure view selection and escaped renderers**

`selectSnapshot(data, index)` returns the snapshot, completed/current/pending stage states, available metrics, work cards, units, and action availability without mutating source data.

`renderDashboard(view)` must render:

- fixed replay labels and run span
- exact report title, run ID, and `Heavy 深度模式`
- dominant progress hero
- seven semantic stage buttons with visible complete/current/pending icons and text in addition to color
- large controls with correct disabled/pressed state
- snapshot-specific work area
- final metrics/report card only when allowed
- no raw internal vocabulary or path

All archive strings pass through `escapeHTML`.

- [ ] **Step 4: Implement bindings and 8-second playback**

`bindControls()` dispatches actions for play/pause/previous/next/restart/stage selection. Use one interval at a time. Rerender after actions, update the polite live region, and move focus to the current-stage heading before replacing work cards when necessary.

- [ ] **Step 5: Implement the approved large-type CSS**

Use CSS tokens and these minimums:

- main body `15px`
- metadata `12px`
- current headline `clamp(28px, 3vw, 34px)`
- progress `clamp(46px, 5vw, 56px)`
- desktop lifecycle seven columns
- desktop work grid with active content and explanation panel
- no permanent findings pane

Use blue for current, dark green for completion, amber for caution, neutral gray for pending. Avoid gradients and radius above `12px`.

- [ ] **Step 6: Regenerate and verify GREEN**

Run:

```bash
python3 examples/deep-research-leadership-demo/build_demo.py \
  --archive 2026-07-14-china-9-strata-9185.zip \
  --output examples/deep-research-leadership-demo/index.html
node --test tests/deep-research-leadership-demo.test.mjs
```

Expected: bootstrap, reducer, bound-control, timer, and rendering tests PASS.

- [ ] **Step 7: Commit chunk 2**

```bash
git add examples/deep-research-leadership-demo tests/deep-research-leadership-demo.test.mjs
git commit -m "feat: replay real deep research milestones"
```

---

## Chunk 3: Findings, Final Report, Accessibility, And Delivery

### Task 5: Add Failing Dialog, Report, Download, And Safety Tests

**Files:**
- Modify: `tests/deep-research-leadership-demo.test.mjs`
- Modify: `examples/deep-research-leadership-demo/template.html`
- Regenerate: `examples/deep-research-leadership-demo/index.html`

- [ ] **Step 1: Add finding availability tests**

Assert `renderDimensionDialog()` returns `该维度尚未形成可展示发现` at snapshots 1–3. At every snapshot 4–7, assert the complete archived headline/findings, dimension claim/source totals, each finding `claimCount`, and `已核验`.

- [ ] **Step 2: Add dialog-controller tests**

With lightweight focusable stubs, assert open state, `aria-hidden`, focus movement, Tab/Shift+Tab wrapping, Escape close, and focus restoration for both dimension and report dialogs. Assert each dialog has `aria-labelledby` and `aria-describedby` pointing to existing label/description elements. For the non-native fallback, assert `role="dialog"` and `aria-modal="true"` while open.

- [ ] **Step 3: Add Markdown safety tests**

Use a synthetic document containing `#`/`##`/`###` headings, unordered lists, `**strong**`, `*italic*`, numeric `[1]` citations, inline `[^note]`, a `[^note]:` definition, an aligned table separator such as `|---|---:|`, and raw `<script>`. Assert every supported construct renders, raw HTML becomes escaped text, and no executable script remains.

Also render the embedded real `reportMarkdown` and assert representative content appears from its opening heading, bullet summary, a multi-column table, strong text, and numeric citations. This prevents a synthetic-only renderer from breaking the actual report.

- [ ] **Step 4: Add download tests**

Stub `Blob`, `URL.createObjectURL`, `URL.revokeObjectURL`, and an anchor. Assert exact filenames `report.md` and `citations.json`, MIME types `text/markdown;charset=utf-8` and `application/json;charset=utf-8`, exact Blob text bytes equal to `archiveData.reportMarkdown` and `archiveData.citationsJson`, and each object URL is revoked after its synthetic click. Assert actions do nothing before snapshot 7.

- [ ] **Step 5: Add failing report-action interaction tests**

Bind a `阅读最终报告` trigger with dialog stubs. At snapshots 1–6, assert clicking is inert and the trigger is disabled. At snapshot 7, assert clicking opens the accessible report viewer, injects rendered archive-backed report content, moves focus into the viewer, and Escape restores focus to the trigger.

- [ ] **Step 6: Add static accessibility/responsive/safety checks**

Assert the generated page contains progressbar ARIA, polite live region, dialogs with accessible label/description references, fallback dialog role/modal semantics, `prefers-reduced-motion`, a desktop dimension-dialog rule positioning a fixed-width panel at the right edge, a mobile breakpoint converting it to a full-width/full-height bottom sheet, a one-column mobile layout, and `overflow-x: hidden` or `clip` on the page shell. Render each dashboard snapshot plus unavailable/available dimension dialogs, strip tags, and search that visible copy for forbidden live-status/raw internal terms; do not search function names, scripts, encoded archive payload, or archive-exact report/citation content. Assert no artifact action or visible label claims `report.html`.

- [ ] **Step 7: Run tests and verify RED**

Expected: FAIL because dialogs, Markdown renderer, Blob downloads, and final accessibility details are missing.

### Task 6: Implement Findings And Final Delivery

**Files:**
- Modify: `examples/deep-research-leadership-demo/template.html`
- Regenerate: `examples/deep-research-leadership-demo/index.html`
- Test: `tests/deep-research-leadership-demo.test.mjs`

- [ ] **Step 1: Implement dimension dialog rendering**

Show unavailable copy before snapshot 4. From snapshot 4, show dimension name, headline, claim/source totals, and every archived finding with `已核验` plus business-facing `关联 N 条证据主张` using the normalized finding claim count.

- [ ] **Step 2: Implement report Markdown rendering**

Escape the entire source first. Parse the known subset line-by-line: levels 1–3 headings, unordered lists, paragraphs, pipe tables including aligned separator cells, `**strong**`, `*italic*`, numeric `[N]` citation tokens, inline `[^id]` references, and `[^id]:` definitions. Do not support raw HTML passthrough. Render inside a readable report surface with local table overflow. Verify the archive-exact report through this renderer, not only synthetic input.

- [ ] **Step 3: Implement accessible modal controllers**

Use `<dialog>` when available and a hidden fixed-position fallback otherwise. On desktop, style the dimension dialog as a fixed-width right-side drawer anchored to the viewport's right edge; the report dialog may be centered and wider. Trap Tab within the active dialog, close on Escape/backdrop, restore trigger focus, and keep the report and dimension dialogs mutually exclusive.

- [ ] **Step 4: Implement final artifact actions**

Enable only at snapshot 7. Before then, the report trigger is both semantically disabled and inert. At snapshot 7, open the report viewer from embedded Markdown. Generate exact Blob downloads and revoke object URLs after the synthetic click.

- [ ] **Step 5: Finish responsive and reduced-motion behavior**

At `max-width: 780px`, switch lifecycle/work/metrics to one column, convert the right-side dimension drawer and report dialog to full-width/full-height bottom sheets, keep tables locally scrollable, and prevent page-level horizontal overflow. Remove transitions/animations under reduced motion.

- [ ] **Step 6: Regenerate and run the full automated suite**

```bash
python3 examples/deep-research-leadership-demo/build_demo.py \
  --archive 2026-07-14-china-9-strata-9185.zip
node --test tests/deep-research-leadership-demo.test.mjs
node --test tests/deep-research-status-page.test.mjs
```

Expected: all tests PASS with no warnings.

- [ ] **Step 7: Run manual presentation smoke checks**

Run:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 \
  --directory examples/deep-research-leadership-demo
```

Open `http://127.0.0.1:8765/` at desktop `1440×900` and mobile `390×844`. Verify:

- initial paused state
- full 56-second replay and final hold
- manual navigation and boundary disabling
- readable progress at normal viewing distance
- all findings dialog content
- report viewer and both downloads
- keyboard/Escape/focus behavior
- no overlap or page-level horizontal overflow

Stop the server with `Ctrl-C` after verification.

- [ ] **Step 8: Run final diff and artifact checks**

```bash
git diff --check
if rg -n "report\.html|实时同步|刚刚|当前更新时间" \
  examples/deep-research-leadership-demo/index.html; then exit 1; fi
git status --short
```

Expected: the guarded wording check exits 0 with no matches, no whitespace errors, and only intended files changed. External-resource absence is covered by the HTML-structure test because the generated page legitimately contains neither external `src` nor stylesheet references; URLs inside embedded report/citation data are Base64-encoded and do not affect the offline runtime.

- [ ] **Step 9: Commit chunk 3**

```bash
git add examples/deep-research-leadership-demo tests/deep-research-leadership-demo.test.mjs
git commit -m "feat: present verified findings and final report"
```
