# Deep Research Leadership Demo Design

## Goal

Create a new standalone HTML demo that replays the real Deep Research run in:

`/mnt/d/code/SenseNova-Skills/2026-07-14-china-9-strata-9185.zip`

The demo is for leadership presentation. It should make a long-running research task easy to understand at a glance, then show the value accumulated during the run: research dimensions, verified findings, and the final report.

This is a truthful dynamic replay of an already completed run. It is not a live production status service and must not imply that it is connected to a currently running controller.

Create the demo at:

`examples/deep-research-leadership-demo/index.html`

Do not reuse the existing status-page HTML, simulation data, layout structure, or JavaScript. The new page may follow repository conventions, but its implementation and data model must be independent.

## Approved Experience

Use the approved progress-first visual direction:

- Large typography and generous spacing.
- A dominant current-stage statement.
- Stage number and overall progress visible without scrolling.
- A clear seven-stage lifecycle for this Heavy run.
- Only active research dimensions shown prominently during replay; completed and waiting dimensions are summarized.
- Dimension findings remain closed until requested, so they do not compete with progress.
- At completion, the final report becomes the primary action.

Use business-facing stage names:

1. 需求确认
2. 研究规划
3. 多主题研究
4. 质量核验
5. 报告组织
6. 写作审校
7. 最终交付

Internal phases such as validator, review, perspective, supplement, stitcher, and render may appear only in secondary detail text.

## Source Of Truth

All displayed research facts and metrics must come from the supplied archive. The demo must use these verified totals:

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
- `report.html` is not present and must not be claimed as an archive artifact.

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

The page must embed the real `headline` and `key_findings` values from all seven `sub_reports/d*.evidence.json` files. Findings may be editorially shortened for the compact card headline, but expanding a dimension must expose the complete archived finding text and associated claim count.

The final-report card must use the real title from `report.md`:

`中国九阶层实际收入与财务状况：中产人数、特征与财力`

It must list the five real content-unit titles from `outline.json`.

## Replay Model

The page uses a fixed replay model derived from the run artifacts and `.pipeline_state.json`. Keep replay snapshots grouped into the seven user-facing stages instead of exposing dozens of internal pipeline events.

Each snapshot contains:

- Stage index and stage name.
- Progress percentage.
- User-facing current-state headline and explanation.
- Display clock based on the real run timeline.
- Completed, active, and waiting dimension IDs.
- Accumulated claim, source, and finding counts.
- Up to three recent activity entries based on real phase ordering.
- Whether findings are provisional or verified at that snapshot.
- Whether final report actions are available.

The replay must start at requirement confirmation, play forward automatically, and end at the real completed state. Use a presentation-friendly total replay duration of roughly 45 to 60 seconds; show the real run clock in the UI so time compression is explicit.

Required controls:

- 播放 / 暂停
- 上一步
- 下一步
- 重新播放
- A timeline scrubber or seven clickable stage markers

Behavior:

- Initial load starts in a paused state at stage 1 so a presenter controls the opening.
- Pressing 播放 advances automatically.
- Manual stage selection pauses playback.
- 重新播放 returns to stage 1 and starts playback.
- The final snapshot remains stable and does not loop automatically.
- Controls remain keyboard accessible and expose pressed/disabled state through ARIA.

## Page Structure

### Header

- Real report title and run identifier.
- `Heavy 深度模式` label.
- Explicit `真实研究记录动态回放` label.
- Real replay clock and current snapshot update time.
- Final report action disabled until the final stage.

### Progress Hero

- Large `阶段 N / 7` label.
- Large current-state headline.
- One-sentence user explanation.
- Overall progress percentage and bar.
- Real-time-compressed playback note, so viewers do not confuse replay time with live execution.

### Lifecycle

- Seven large, readable stages.
- Complete, current, and pending states must use both icons/text and color.
- Stage markers are clickable replay navigation.

### Current Work

- During research and quality stages, show only currently active dimensions as large cards.
- Each card shows name, current user-facing status, accumulated claim/source counts, and whether findings are provisional or verified.
- Completed and waiting dimensions appear as compact grouped summaries.
- During report stages, replace the active-dimension cards with the five real content units and their writing/review status.

### Findings Detail

- Clicking a dimension opens a large right-side drawer on desktop and a full-screen bottom sheet on mobile.
- The drawer shows the dimension headline, archived findings, claim counts, claim/source totals, and verification state.
- Before quality completion, findings display `暂定发现，仍可能调整`.
- At or after the dimension quality gate, findings display `已核验`.
- Closing the drawer restores the progress-first view.
- Escape closes the drawer; focus is trapped while open and restored to the trigger afterward.

### Completion And Report

At the final stage:

- Show 100% completion and final-review pass.
- Show the verified totals listed above.
- Show the five real report units.
- Enable `阅读最终报告`.
- Provide demo-safe secondary actions for `report.md` and `citations.json` using embedded archive-derived content or Blob URLs. Do not link to nonexistent local paths.
- The in-page report viewer may render the known Markdown subset used by this report: headings, paragraphs, unordered lists, tables, emphasis, inline numeric citations, and footnote-style content. Raw HTML must be escaped before rendering.

## Visual Direction

- Calm executive operations view, not a developer console or marketing landing page.
- Minimum 15px body text in main content and 12px only for secondary metadata.
- Current-state headline around 28–32px on desktop.
- Progress percentage around 44–52px.
- Neutral base, dark green completion state, blue active state, amber caution or provisional state.
- Cards use 8–12px radius.
- Avoid dense tiny labels, decorative blobs, gradients, and permanent findings panels.
- Desktop should use the available width; mobile must be a single readable column with no page-level horizontal scrolling.

## Data And Safety Boundaries

- No network requests and no external dependencies.
- No backend or local server required for the demo.
- No arbitrary file reads from the browser.
- No internal absolute paths, agent prompts, validator error dumps, schema names, or dispatch payloads in visible UI.
- Do not invent ETA, confidence scores, evidence quality percentages, or report artifacts.
- Make replay status explicit in the header and progress hero.

## Empty And Error States

The embedded replay data is expected to be valid. Still render a user-facing fallback if initialization fails:

- Title: `演示数据暂时无法加载`
- Explanation: the local demo data is incomplete or invalid.
- A `重新加载` action.
- Do not expose JavaScript stack traces or internal filenames.

If a dimension has no findings at a snapshot, the drawer says `该维度尚未形成可展示发现` rather than rendering an empty list.

## Testing

Use Node's built-in test runner and no new dependencies.

Tests must verify:

- The new demo is independent and does not import or copy the existing status-page runtime.
- All verified real totals are present and internally consistent.
- All seven dimension names, headlines, and finding counts are present.
- The five real content-unit titles are present.
- Default state is paused at stage 1.
- Play, pause, previous, next, restart, and stage selection work.
- Final report action remains disabled until stage 7 and becomes enabled at completion.
- Opening and closing a dimension detail updates ARIA state and visibility.
- Provisional and verified finding states change with replay stage.
- Visible UI avoids internal implementation terms and absolute paths.
- No active `report.html` claim or link exists.
- A narrow viewport has no designed page-level horizontal overflow.

## Acceptance Criteria

- Opening the HTML locally produces a polished leadership-ready page.
- A presenter can replay the completed run in under one minute.
- The current stage, overall progress, and active work are readable at normal viewing distance.
- Every displayed research number and finding is traceable to the supplied archive.
- The final snapshot accurately exposes the completed report, citations, dimensions, and findings without inventing missing artifacts.
- The page works offline as a single self-contained HTML file.
