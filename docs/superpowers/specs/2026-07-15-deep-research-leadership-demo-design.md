# Deep Research Leadership Demo Design

## Goal

Create a new standalone HTML demo that replays the completed Deep Research run in:

`/mnt/d/code/SenseNova-Skills/2026-07-14-china-9-strata-9185.zip`

The demo is for leadership presentation. It must make the long research process understandable at a glance, then expose the value accumulated by the run: research dimensions, verified findings, and the final report.

This is a historical milestone replay, not a live production status service. The page must say `真实研究记录动态回放` and `流程顺序回放，非逐秒运行日志`, and must never use live-status wording such as `实时同步`, `刚刚`, or `当前更新时间`.

Create the demo at:

`examples/deep-research-leadership-demo/index.html`

Do not reuse the existing status-page HTML, simulation data, layout structure, or JavaScript. The new page may follow repository conventions, but its implementation and data model must be independent.

## Approved Experience

Use the approved progress-first direction:

- Large typography and generous spacing.
- A dominant current-stage statement.
- Stage number and stage-ordinal progress visible without scrolling.
- A clear seven-stage lifecycle for this Heavy run.
- During replay, prominent cards show only the work relevant to the selected milestone.
- Findings stay closed until requested, so they do not compete with progress.
- At completion, the final report becomes the primary action.

Use these business-facing stages:

1. 需求确认
2. 研究规划
3. 多主题研究
4. 质量核验
5. 报告组织
6. 写作审校
7. 最终交付

Do not show raw internal phase or role names such as validator, review, perspective, supplement, stitcher, render, agent, schema, or dispatch. Translate all visible status into the seven stages above.

## Source Of Truth

All research facts and metrics come from the supplied archive. Use these verified totals:

- Mode: Heavy
- Start: 2026-07-14 06:03
- Completion: 2026-07-14 09:37
- Approximate elapsed time: 3 hours 34 minutes
- Research dimensions: 7
- Evidence claims: 108
- Source entries across dimensions: 73
- Unique source IDs across dimensions: 70
- Key findings: 36
- Report content units: 5
- Final citations: 58
- Final review verdict: pass
- Final artifacts present: `report.md`, `citations.json`

Dimension data:

| ID | User-facing name | Claims | Sources | Findings |
|---|---|---:|---:|---:|
| d1 | 九阶层定义、边界与可复算映射 | 18 | 12 | 4 |
| d2 | 九层收入、现金流与人口分布事实 | 14 | 10 | 6 |
| d3 | 九层资产、负债、净财富与可动用财力 | 18 | 11 | 5 |
| d4 | 中国中产规模、内部结构与财力区间 | 17 | 9 | 5 |
| d5 | 城乡、地区、城市等级与人口异质性 | 10 | 15 | 5 |
| d6 | 消费结构、住房与社会保障负担 | 13 | 8 | 5 |
| d7 | 财务韧性、冲击暴露与阶层流动 | 18 | 8 | 6 |

Embed the real `headline` and `key_findings` values from all seven `sub_reports/d*.evidence.json` files. A compact card may shorten a finding, but the dimension detail must expose the complete archived finding text. Its `associated claim count` is exactly `key_findings[].claim_ids.length`, not the dimension's total claim count.

Use the real report title from `report.md`:

`中国九阶层实际收入与财务状况：中产人数、特征与财力`

List the five real content-unit titles from `outline.json`.

Archive provenance:

| Displayed data | Archive source |
|---|---|
| Mode and seven dimension names | `plan.json` |
| Dimension headline, claim counts, source-entry counts, findings, and finding claim IDs | `sub_reports/d*.evidence.json` |
| Five content-unit titles | `outline.json` |
| Final report title and body | `report.md` |
| Final citation count and payload | `citations.json` |
| Final pass verdict | `final_review.md` |
| Internal ordering grouped into seven business stages | `.pipeline_state.json` |
| Start and completion labels | archive timestamps for `briefing.json`, `report.md`, and `citations.json` |

The archive does not contain incremental evidence snapshots or an exact timestamp for every grouped business stage. Do not fabricate either.

The page must contain no visible, disabled, pending, or active `report.html` artifact claim and no `report.html` link.

## Deterministic Replay Model

Use exactly seven replay snapshots, one per business stage. They are milestone illustrations in the real stage order, not reconstructed wall-clock states.

| Index | Stage | Stage progress | Supported display state |
|---:|---|---:|---|
| 1 | 需求确认 | 14% | Scope confirmed; no dimensions or research metrics yet |
| 2 | 研究规划 | 29% | Seven planned dimension names; no evidence totals yet |
| 3 | 多主题研究 | 43% | Seven dimensions marked research-in-progress; no incremental totals or findings |
| 4 | 质量核验 | 57% | All seven final dimension metrics and 36 verified findings become available |
| 5 | 报告组织 | 71% | Five real content-unit titles become available |
| 6 | 写作审校 | 86% | Five units shown as written and final review shown as pass; final artifact actions remain disabled |
| 7 | 最终交付 | 100% | `report.md` and `citations.json` actions become available |

The percentages are exactly rounded ordinal completion of seven stages. Label them `流程阶段进度`; they are not workload, confidence, quality, time, or ETA estimates.

Every snapshot contains:

- Stage index and name.
- The exact ordinal progress from the table.
- User-facing headline and explanation.
- Replay label `历史回放 · 里程碑 N / 7`.
- Work items appropriate to the milestone.
- Metrics only when supported by the artifacts represented at that milestone.
- Up to three untimed milestone statements, with no invented timestamps.
- Whether verified findings are available.
- Whether final artifact actions are available.

The page always shows the fixed overall run span `真实运行跨度 06:03–09:37`.

### Replay Controls

Required controls:

- 播放 / 暂停
- 上一步
- 下一步
- 重新播放
- Seven clickable stage markers

Behavior:

- Initial state is paused at snapshot 1.
- 播放 holds each snapshot for 8 seconds. Transitions occur at 8, 16, 24, 32, 40, and 48 seconds.
- 播放 at snapshot 7 returns to snapshot 1 and starts playback.
- 暂停 keeps the current snapshot.
- 上一步 is disabled at snapshot 1; 下一步 is disabled at snapshot 7.
- 上一步 and 下一步 move exactly one snapshot and pause playback.
- Clicking a stage marker selects exactly that snapshot and pauses playback.
- 重新播放 returns to snapshot 1 and immediately starts playback.
- Snapshot 7 holds from second 48 through second 56, then playback changes to paused and remains stable. It does not loop automatically.
- A complete presentation, including the final 8-second leadership handoff, lasts 56 seconds.

## Page Structure

### Header

- Real report title and run identifier.
- `Heavy 深度模式`.
- `真实研究记录动态回放`.
- `真实运行跨度 06:03–09:37`.
- `历史回放 · 里程碑 N / 7`.
- Final report action disabled until snapshot 7.

### Progress Hero

- Large `阶段 N / 7` label.
- Large milestone headline.
- One-sentence user explanation.
- `流程阶段进度` percentage and bar.
- `流程顺序回放，非逐秒运行日志`.

### Lifecycle

- Seven large, readable, clickable stage buttons.
- Complete, current, and pending states use icon/text and color.
- The selected stage exposes `aria-current="step"`.

### Current Work

- Snapshot 1 shows the confirmed research scope.
- Snapshot 2 shows seven planned dimension names and no evidence totals.
- Snapshot 3 shows seven research-in-progress dimensions and no findings or accumulated totals.
- Snapshot 4 shows the real final per-dimension claim/source/finding counts and verified findings.
- Snapshot 5 replaces research work with the five real content-unit titles in an organized state.
- Snapshot 6 shows the five units as written and the final review as pass, but keeps artifact actions disabled.
- Snapshot 7 shows final totals, report, citations, and completion.

### Findings Detail

- Clicking a dimension opens a right-side drawer on desktop and full-screen bottom sheet on mobile.
- Before snapshot 4, it says `该维度尚未形成可展示发现`.
- From snapshot 4 onward, it shows the archived headline, full findings, each finding's `claim_ids.length`, dimension claim/source totals, and `已核验`.
- Closing returns to the progress-first view.
- Escape closes the dialog; focus is trapped while open and restored to its trigger.

### Completion And Report

At snapshot 7:

- Show 100%, final-review pass, and all verified totals.
- Show the five real report units.
- `阅读最终报告` opens an accessible modal containing archive-exact `report.md` rendered with the supported Markdown subset.
- `下载 report.md` creates a Blob with MIME `text/markdown;charset=utf-8` and filename `report.md`.
- `下载 citations.json` creates a Blob with MIME `application/json;charset=utf-8` and filename `citations.json`.
- All three actions are disabled before snapshot 7.
- The report viewer supports headings, paragraphs, unordered lists, tables, emphasis, inline numeric citations, and footnote-style content.
- Escape raw HTML before applying Markdown transformations.
- Escape closes the viewer; focus is trapped while open and restored to the report trigger.

## Visual Direction

- Calm executive operations view, not a developer console or marketing landing page.
- Minimum 15px body text in main content; 12px is reserved for metadata.
- Current-state headline around 28–32px on desktop.
- Progress percentage around 44–52px.
- Neutral base, dark green completion, blue active, amber caution.
- Cards use 8–12px radius.
- Avoid tiny labels, decorative blobs, gradients, and permanent findings panels.
- Desktop uses available width; mobile is one readable column with no page-level horizontal scrolling.

## Data And Safety Boundaries

- No network requests or external dependencies.
- No backend or local server.
- No arbitrary browser file reads.
- No internal absolute paths, prompts, error dumps, schema names, dispatch payloads, or raw internal phase names in visible UI.
- Do not invent ETA, confidence scores, evidence quality percentages, timestamps, incremental metrics, or artifacts.
- Make historical replay status explicit in the header and hero.

## Validation And Error State

Before first render, `validateArchiveData(data)` verifies:

- Exactly seven replay snapshots indexed 1 through 7.
- Progress values exactly `[14, 29, 43, 57, 71, 86, 100]`.
- Exactly seven dimensions with unique IDs `d1` through `d7`.
- Dimension totals sum to 108 claims, 73 source entries, and 36 findings.
- Final aggregate contains 70 unique source IDs, five content units, 58 citations, and verdict `pass`.
- Embedded `report.md` and `citations.json` payloads are non-empty.

If validation fails, render:

- Title: `演示数据暂时无法加载`
- Explanation: the local demo data is incomplete or invalid.
- `重新加载`, which calls `window.location.reload()`.
- No stack trace or internal filename.

## Implementation Boundaries

Keep the single HTML file internally separated into testable units:

- `archiveData`: immutable archive-derived values.
- `validateArchiveData(data)`: pure bootstrap validation.
- `replayReducer(state, action)`: pure stage/playback transitions.
- `selectSnapshot(data, index)`: pure derived-view selection.
- `renderDashboard(view)`, `renderDimensionDialog(view)`, and `renderReportViewer(markdown)`: escaped string renderers.
- `createDialogController(...)`: focus, Escape, open, and close with injected DOM elements.
- `bindControls(...)`: event binding separate from reducers and renderers.

Tests may evaluate the inline script in a Node VM with lightweight DOM and timer stubs, following the existing repository pattern. Responsive automated checks assert CSS rules; a manual narrow-viewport check covers actual layout.

## Accessibility

- Replay updates are announced through a polite live region.
- The progress bar exposes `role="progressbar"`, `aria-valuemin`, `aria-valuemax`, and current `aria-valuenow`.
- Stage buttons expose `aria-current="step"` for the selected milestone.
- Play/pause exposes pressed state; unavailable previous/next/report actions expose disabled state.
- Dimension and report dialogs expose accessible names/descriptions, trap focus, close with Escape, and restore focus.
- If work cards change while focus is inside them, move focus to the current-stage heading before rerendering.
- Under `prefers-reduced-motion: reduce`, remove decorative transitions. Explicit playback still changes snapshots without animated movement.

## Testing

Use Node's built-in test runner and no new dependencies.

Automated tests verify:

- The new demo is independent and does not import the existing status-page runtime.
- All verified totals are present and internally consistent.
- All seven dimension names, headlines, full finding texts, and finding claim counts are present.
- The five real content-unit titles are present.
- Invalid data renders the specified fallback and reload action.
- Default state is paused at snapshot 1.
- Play, pause, previous, next, restart, stage selection, automatic timing, and boundary behavior are deterministic.
- Report actions remain disabled until snapshot 7 and become enabled only there.
- Findings are unavailable before snapshot 4 and verified from snapshot 4 onward.
- Dimension and report dialogs update ARIA state, trap/restore focus, and close with Escape.
- Dashboard, replay controls, dialogs, and status copy avoid raw internal terms, absolute paths, fabricated timestamps, and live-status wording. This vocabulary check excludes the archive-exact final report body and citations, whose source titles are not rewritten.
- The page contains no `report.html` artifact claim or link.
- Report and citation Blob downloads use the specified filenames and MIME types.
- The Markdown renderer escapes raw HTML.
- Replay progress and lifecycle navigation expose the required ARIA attributes.
- Responsive CSS declares a one-column layout and no page-level horizontal scrolling at the mobile breakpoint.

Manual verification checks desktop and narrow mobile widths, readable type size, no overlap, no page-level horizontal overflow, keyboard navigation, and a full 56-second presentation.

## Acceptance Criteria

- Opening the HTML locally produces a polished leadership-ready page.
- A presenter can replay the real stage order in 56 seconds.
- The current milestone, ordinal progress, and represented work are readable at normal viewing distance.
- Every displayed research number and finding is traceable to the archive.
- The final snapshot exposes the completed report, citations, dimensions, and findings without inventing missing artifacts or historical intermediate data.
- The page works offline as one self-contained HTML file.
