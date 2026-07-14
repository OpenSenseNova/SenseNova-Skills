# Deep Research Status Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the static Deep Research status page into a clearer two-column dashboard with a left status console and right work area, while removing the separate deliverables panel.

**Architecture:** Keep the existing single-file static HTML runtime at `examples/deep-research-status-page/index.html`. Reuse the current `runSnapshots` simulation model, but reorganize rendering into a left status console, compact lifecycle strip, current-stage explanation panel, and research-material cards.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Node built-in test runner.

---

## Chunk 1: Two-Column Redesign

### Task 1: Redesign Static Page Layout

**Files:**
- Modify: `examples/deep-research-status-page/index.html`
- Modify: `tests/deep-research-status-page.test.mjs`

- [ ] **Step 1: Write failing layout assertions**

Update `tests/deep-research-status-page.test.mjs` so the rendered DOM checks verify:

```js
assert.match(page.app.innerHTML, /class="[^"]*dashboard-shell/);
assert.match(page.app.innerHTML, /class="[^"]*status-console/);
assert.match(page.app.innerHTML, /class="[^"]*work-area/);
assert.match(page.app.innerHTML, /当前阶段/);
assert.match(page.app.innerHTML, /阶段进度/);
assert.match(page.app.innerHTML, /当前阶段说明/);
assert.match(page.app.innerHTML, /已形成的研究材料/);
assert.doesNotMatch(page.app.innerHTML, />后续产出</);
```

Also add a rendered-UI assertion that visible copy does not contain internal terms:

```js
assert.doesNotMatch(stripTags(page.app.innerHTML), /validator|agent|schema|sub_reports|sections\//i);
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
node --test tests/deep-research-status-page.test.mjs
```

Expected: FAIL because the current rendered page does not yet have the new `dashboard-shell`, `status-console`, and `work-area` layout classes, and it still renders the separate `后续产出` panel.

- [ ] **Step 3: Rework CSS for the new dashboard shell**

In `examples/deep-research-status-page/index.html`:

- Replace the current stacked page layout with a desktop grid:
  - `.dashboard-shell` with `grid-template-columns: minmax(300px, 340px) minmax(0, 1fr)`.
  - `.status-console` for the left column.
  - `.work-area` for the right column.
- Make `.status-console` sticky on desktop using `position: sticky; top: 20px`.
- Keep card radii at `8px` or less.
- Add a mobile breakpoint at `760px` where the layout becomes one column in this order:
  1. Status console
  2. Simulation controls
  3. Lifecycle strip
  4. Current stage explanation
  5. Research materials

- [ ] **Step 4: Rework rendering into the approved layout**

Update `renderPage(data)` so it renders:

1. `.dashboard-shell`
2. `.status-console`
   - title
   - scope
   - current snapshot state
   - real-state marker when applicable
   - progress percentage/bar
   - four metrics
   - short state explanation
3. `.work-area`
   - simulation controls
   - compact lifecycle strip
   - current stage explanation panel
   - research material cards

Remove the separate deliverables panel from the rendered layout.

- [ ] **Step 5: Keep simulated artifacts lightweight**

Remove `renderDeliverables()` from the main page flow. If simulated artifacts are shown, show them only as short text inside the current stage explanation, not as a standalone panel.

- [ ] **Step 6: Preserve interactions**

Keep existing behavior:

- Default snapshot index remains the real sample state.
- `重置` returns to the real sample state.
- `下一步` reaches section writing, citation organization, and final delivery states.
- Theme cards still toggle with `aria-expanded`.

- [ ] **Step 7: Run tests and verify they pass**

Run:

```bash
node --test tests/deep-research-status-page.test.mjs
```

Expected: PASS.

- [ ] **Step 8: Run script-level interaction smoke test**

Run this command:

```bash
node <<'NODE'
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('examples/deep-research-status-page/index.html', 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
const app = { innerHTML: '' };
const buttons = {};
function button(action) {
  let handler = () => {};
  return {
    addEventListener(type, fn) { if (type === 'click') handler = fn; },
    click() { handler(); },
    getAttribute(name) { return name === 'data-action' ? action : null; },
    setAttribute() {},
  };
}
const context = {
  console,
  window: { setInterval, clearInterval },
  document: {
    readyState: 'complete',
    querySelector(selector) { return selector === '#app' ? app : null; },
    querySelectorAll(selector) {
      if (selector === '.theme-toggle') return [];
      if (selector === '[data-action]') return ['previous','play','next','reset'].map((a) => (buttons[a] = button(a)));
      return [];
    },
    getElementById() { return null; },
    addEventListener() {},
  },
};
vm.createContext(context);
vm.runInContext(script, context);
if (!app.innerHTML.includes('真实样例当前停在这里')) throw new Error('missing default real marker');
buttons.next.click();
if (!app.innerHTML.includes('正在撰写章节草稿')) throw new Error('next did not show section-writing state');
buttons.reset.click();
if (!app.innerHTML.includes('真实样例当前停在这里')) throw new Error('reset did not return to real marker');
console.log('simulation controls verified');
NODE
```

This verifies:

- default render includes `真实样例当前停在这里`
- `next` shows simulated section writing
- `reset` returns to real marker

Expected: command exits 0.

- [ ] **Step 9: Commit**

Run:

```bash
git add examples/deep-research-status-page/index.html tests/deep-research-status-page.test.mjs
git commit -m "feat: redesign deep research status page"
```
