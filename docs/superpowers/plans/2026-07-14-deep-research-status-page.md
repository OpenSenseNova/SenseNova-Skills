# Deep Research Status Page Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone static HTML demo that clearly shows a Deep Research run's user-facing status, completed materials, and pending deliverables.

**Architecture:** Create one self-contained HTML file with inline CSS and JavaScript at `examples/deep-research-status-page/index.html`. Keep all demo data in a single `runData` object so a later dynamic version can replace it with parsed report-directory data.

**Tech Stack:** HTML, CSS, vanilla JavaScript, browser-only static page. No build system or external runtime dependency.

---

## Chunk 1: Static Page

### Task 1: Create The Demo Page

**Files:**
- Create: `examples/deep-research-status-page/index.html`

- [ ] **Step 1: Create the page shell and static data**

Add a complete HTML document with:

```javascript
const runData = {
  title: "海外化妆品竞品研究",
  scope: "欧莱雅 / 雅诗兰黛 / 资生堂，集团层为主，核心品牌为辅",
  mode: "Heavy 深度模式",
  currentState: "资料核验完成，准备组织报告",
  statusSummary: "已完成资料收集、口径核验和补充检查。接下来会把 6 个研究主题整理成报告大纲，并生成章节草稿、引用和最终 HTML 报告。",
  progress: 72,
  metrics: [
    { value: "6/6", label: "研究主题完成" },
    { value: "114", label: "证据点整理" },
    { value: "120", label: "来源已归档" },
    { value: "0", label: "待用户补充" }
  ],
  stages: [
    { name: "需求确认", description: "确定对象与研究深度", status: "complete" },
    { name: "研究规划", description: "拆成 6 个主题", status: "complete" },
    { name: "资料核验", description: "证据与来源完成", status: "complete" },
    { name: "报告组织", description: "下一步生成大纲", status: "current" },
    { name: "最终交付", description: "Markdown / HTML / 引用", status: "pending" }
  ],
  themes: [
    { name: "可比财务骨架", summary: "营收、利润率、份额口径", claims: 18, sources: 10 },
    { name: "增长与盈利韧性", summary: "分化原因与恢复迹象", claims: 19, sources: 20 },
    { name: "品牌与价格带", summary: "集团品牌矩阵与核心品类", claims: 22, sources: 35 },
    { name: "中国/亚太市场", summary: "敞口、份额、旅游零售", claims: 20, sources: 21 },
    { name: "数字渠道", summary: "电商、内容、DTC 能力", claims: 17, sources: 21 },
    { name: "战略与竞争压力", summary: "转型计划与本土品牌冲击", claims: 18, sources: 13 }
  ],
  deliverables: [
    { name: "报告大纲与章节安排", status: "next" },
    { name: "章节草稿与核心判断", status: "pending" },
    { name: "引用编号与来源清单", status: "pending" },
    { name: "最终 Markdown / HTML 报告", status: "pending" }
  ],
  stateCopy: {
    waitingForUser: "需要你确认一个口径选择后继续。",
    researchRunning: "资料仍在检索和核验中，完成后会进入报告组织。",
    missingData: "部分运行数据暂不可用，页面会以待生成显示而不是暴露内部错误。"
  }
};
```

- [ ] **Step 2: Implement the layout**

Build sections in this order:

1. Top status overview with title, scope, current state, progress bar, mode badge, and the `statusSummary` plain-language explanation of what has completed and what happens next.
2. Four compact metric cards.
3. Stage timeline using complete/current/pending states.
4. Research material cards using `button` elements to expand short details.
5. Next deliverables panel with `next`/`pending` wording only. Because the source run has empty `sections/` and no `outline.json`, do not render any active report, outline, citation, Markdown, or HTML links.
6. A visually quiet copy-pattern area or hidden data block for inactive states: waiting for user input, research still running, and missing data. These patterns should be easy to reuse later but should not distract from the active demo state.

- [ ] **Step 3: Add visual styling**

Use inline CSS in the same file:

- Calm operational layout, not a landing page.
- Compact cards with border radius `8px` or less.
- Green for complete, blue for current, gray for pending, amber for next deliverables.
- Responsive grid breakpoints for narrow screens.
- No decorative blobs, oversized hero, or internal log styling.
- Inactive state copy patterns should be subdued and clearly labeled as reusable states, not active alerts.

- [ ] **Step 4: Add lightweight interaction**

Use vanilla JavaScript to:

- Render the page from `runData`.
- Toggle a theme card's detail area with `aria-expanded`.
- Keep the page usable if JavaScript runs after DOM load.

### Task 2: Verify Locally

**Files:**
- Inspect: `examples/deep-research-status-page/index.html`

- [ ] **Step 1: Start a static server**

Run:

```bash
python3 -m http.server 4173 --directory examples/deep-research-status-page
```

Expected: server starts and serves `http://localhost:4173`.

- [ ] **Step 2: Check the rendered page**

Open `http://localhost:4173` and confirm:

- The current state says `资料核验完成，准备组织报告`.
- No final report link is marked available.
- No outline, section, citation, Markdown, or HTML report link is marked available.
- The six themes match the source run.
- Theme expansion works.

- [ ] **Step 3: Check responsive behavior**

Use browser viewport sizes:

- Desktop: 1440 x 900
- Mobile: 390 x 844

Expected:

- Text does not overlap.
- Cards stack cleanly on mobile.
- Progress bar, timeline, buttons, and deliverables remain readable.

Capture screenshots for both viewports if Playwright or another local browser automation tool is available. If screenshot tooling is unavailable, record that limitation and still perform manual viewport checks.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add examples/deep-research-status-page/index.html
git commit -m "feat: add deep research status page demo"
```
