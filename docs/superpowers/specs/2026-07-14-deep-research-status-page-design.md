# Deep Research Status Page Design

## Goal

Build a single HTML demo page that shows a Deep Research run from the final user's point of view. The page should answer three questions quickly:

- Where is my research task now?
- What has already been produced?
- What will I receive next?

The first version is a static demo based on:

`/mnt/d/code/SenseNova-Skills/2026-06-25-cosmetics-overseas-competitor-d17f`

This run has completed planning, evidence gathering, reviews, perspective checks, and supplement planning for six research themes. The `sections/` directory is empty, so the demo state is: research materials are ready, report organization/writing is next.

The static demo output should be created at:

`examples/deep-research-status-page/index.html`

## Audience

The page is for final users and business stakeholders, not developers. It must avoid exposing internal agent names, validator details, file schemas, retry mechanics, or prompt-level implementation.

Use user-facing stage names:

- Requirement confirmed
- Research planned
- Materials verified
- Report organization
- Final delivery

Avoid internal names such as scout, plan agent, perspective lens, supplement planner, report stitcher, validator, `d1.evidence.json`, or schema fields unless hidden behind future diagnostics.

## Page Structure

Use the approved hybrid layout:

1. Top status overview
   - Report title: "海外化妆品竞品研究"
   - Scope subtitle: "欧莱雅 / 雅诗兰黛 / 资生堂，集团层为主，核心品牌为辅"
   - Current state: "资料核验完成，准备组织报告"
   - Progress indicator around 72%
   - Mode label: "Heavy 深度模式"
   - Plain-language explanation of what has been completed and what happens next

2. Key metrics
   - `6/6` research themes completed
   - `114` evidence points整理
   - `120` sources归档
   - `0` user inputs needed

3. Stage timeline
   - Requirement confirmed: complete
   - Research planned: complete
   - Materials verified: complete
   - Report organization: next/current handoff
   - Final delivery: pending

4. Research materials
   - Show six user-facing themes as cards:
     - 可比财务骨架
     - 增长与盈利韧性
     - 品牌与价格带
     - 中国/亚太市场
     - 数字渠道
     - 战略与竞争压力
   - Each card should summarize the topic in one short phrase. Do not show evidence JSON internals.

5. Next deliverables
   - 报告大纲与章节安排
   - 章节草稿与核心判断
   - 引用编号与来源清单
   - 最终 Markdown / HTML 报告

## Static Demo Data

Use static data derived from the sample run:

- Mode: heavy
- Dimensions: 6
- Evidence claims by dimension: 18, 19, 22, 20, 17, 18
- Total evidence points: 114
- Sources by dimension: 10, 20, 35, 21, 21, 13
- Total sources: 120
- `sections/` is empty, and no `outline.json` exists, so no section draft/report links should be marked available yet. The page should describe the state as a handoff from verified materials into report organization, not as an already-started writing phase.

For the demo, future artifacts may be shown as pending rather than fabricated. If visual completeness requires example filenames, label them clearly as "即将生成" or "待生成".

## Interaction

The page can be a standalone static HTML file for the first version. Expected interactions:

- Open/close a lightweight detail area for each research theme.
- Show available/pending status for deliverables.
- No backend calls.
- No need for live polling in this version.

## Visual Direction

The page should feel like a calm operational status view, not a marketing landing page. Use a restrained, information-dense layout with:

- Full-width app surface
- Compact cards with radius 8px or less
- Clear status colors: green for complete, blue for current, gray for pending, amber for upcoming outputs
- A palette that is not dominated by one hue
- Responsive layout for desktop and mobile

Do not use oversized hero sections, decorative blobs, or dense internal logs.

## Data Boundary

The static demo may hard-code data in JavaScript or directly in HTML. Keep the data grouped so a later version can replace it with parsed run-directory data.

Future dynamic version can infer status from files:

- `briefing.json` exists: requirement/scoping complete
- `plan.json` exists: research planned
- all expected `sub_reports/*.evidence.json` exist: materials gathered
- reviews and supplement plans exist: materials verified
- `outline.json` or `sections/*.evidence_subset.json` exists: report organization started
- `sections/*.md` exists: report writing started
- `report.md` and `citations.json` exist: final delivery complete
- `report.html` exists: visual report available

## Error And Empty States

The static demo should include copy patterns for these states, even if not all are active:

- Waiting for user input: show what decision is needed and why.
- Research still running: show current stage and completed metrics.
- No final report yet: show pending deliverables without broken links.
- Missing data: use "待生成" or "暂无" instead of showing internal file errors.

## Verification

Before considering the page done:

- Open it locally in a browser or static server.
- Check desktop and mobile viewport screenshots.
- Confirm text does not overlap or overflow.
- Confirm theme cards and deliverable statuses are readable without internal Deep Research knowledge.
- Confirm the page does not claim final report files exist while `sections/` is still empty.
