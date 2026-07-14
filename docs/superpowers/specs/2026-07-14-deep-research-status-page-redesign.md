# Deep Research Status Page Redesign

## Goal

Redesign `examples/deep-research-status-page/index.html` so the page is clearer for final users. The current page has the right information, but the modules compete for attention. The redesign should make the reading path obvious:

1. Where is the run now?
2. What has been completed?
3. What is happening in the simulated lifecycle?
4. What research material already exists?

## Layout Direction

Use the approved "left status console + right work area" layout.

### Left Status Console

The left column is the anchor of the page. On desktop it should remain visually dominant and preferably sticky within the viewport.

It should contain:

- Page title: `海外化妆品竞品研究`
- Scope: `欧莱雅 / 雅诗兰黛 / 资生堂，集团层为主，核心品牌为辅`
- Current state from the active simulation snapshot
- Clear marker when the active snapshot is the real sample state: `真实样例当前停在这里`
- Progress percentage and progress bar
- Four compact metrics from the active snapshot
- One short explanation of what this state means

The console should not include internal file paths, agent names, validators, schemas, or implementation detail.

### Right Work Area

The right column should contain:

1. Simulation controls
   - `播放 / 暂停`
   - `上一步`
   - `下一步`
   - `重置`

2. Compact lifecycle strip
   - Eight stages: 需求确认、研究规划、资料检索、资料核验、报告组织、章节撰写、引用整理、最终交付
   - Completed/current/pending states should be visually distinct.
   - The lifecycle strip should be compact; it should not dominate the page.

3. Current stage explanation
   - A focused panel that explains:
     - 当前阶段正在发生什么
     - 为什么这一步对最终报告有价值
     - If the stage is simulated, clearly say `以下为模拟后续状态`

4. Research materials
   - Show the six research themes as compact cards:
     - 可比财务骨架
     - 增长与盈利韧性
     - 品牌与价格带
     - 中国/亚太市场
     - 数字渠道
     - 战略与竞争压力
   - Each card should show the short summary plus evidence/source counts.
   - Cards may expand for one sentence of detail.

## Removed Module

Remove the separate `后续产出` panel.

The page should no longer have an independent deliverables section listing outline/sections/citations/report as a major module. Those simulated artifacts may still appear as short stage-specific text inside the current stage explanation when useful, but they should not compete with the main status and research-material view.

## Simulation Behavior

Keep the existing simulation data model and controls, with these behavioral expectations:

- Default snapshot remains the real sample state: `资料核验完成，准备组织报告`.
- `重置` returns to the real sample state, not the beginning.
- `下一步` advances into simulated section writing, citation organization, and final delivery states.
- Later states must be clearly labeled as simulated.
- The simulation should update:
  - Left status console
  - Lifecycle strip
  - Current stage explanation
  - Metrics and theme counts where relevant

## Visual Style

The page should feel like a calm operational dashboard:

- Dense but readable.
- No landing-page hero.
- No decorative blobs or ornamental backgrounds.
- Cards use radius `8px` or less.
- Use green for complete, blue for current, gray for pending, amber for the real-state marker or caution labels.
- Avoid a one-note palette; keep the existing neutral base with restrained accent colors.

## Responsive Behavior

Desktop:

- Two-column layout.
- Left status console around 300-360px wide.
- Right area takes remaining width.
- Left console may be sticky.

Mobile:

- Single column.
- Order should be:
  1. Status console
  2. Simulation controls
  3. Lifecycle strip
  4. Current stage explanation
  5. Research materials

Text must not overlap or overflow at mobile width.

## Tests

Update `tests/deep-research-status-page.test.mjs` to verify:

- The page still renders the default real-state marker.
- Simulation controls still work.
- `重置` returns to the real sample state.
- The separate `后续产出` panel is absent.
- Research theme names and counts remain present.
- The lifecycle stages remain present.
- The page still avoids active links to simulated report artifacts.

## Out Of Scope

- No backend.
- No live polling.
- No real parsing of report directories.
- No new dependencies.
- No separate deliverables panel.
