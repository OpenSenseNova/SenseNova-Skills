import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";
import vm from "node:vm";

const pagePath = new URL("../examples/deep-research-status-page/index.html", import.meta.url);

async function readPage() {
  return readFile(pagePath, "utf8");
}

function stripTags(value) {
  return value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function createElementStub({ action = null } = {}) {
  const listeners = {};
  return {
    addEventListener(type, handler) {
      listeners[type] = handler;
    },
    click() {
      listeners.click?.();
    },
    getAttribute(name) {
      return name === "data-action" ? action : null;
    },
    setAttribute() {},
  };
}

function runPageScript(html) {
  const script = html.match(/<script>([\s\S]*)<\/script>/)?.[1];
  assert.ok(script, "page should contain an inline script");

  const app = { innerHTML: "" };
  let actionButtons = [];
  const context = {
    console,
    window: {
      setInterval,
      clearInterval,
    },
    document: {
      readyState: "complete",
      querySelector(selector) {
        return selector === "#app" ? app : null;
      },
      querySelectorAll(selector) {
        if (selector === ".theme-toggle") return [];
        if (selector === "[data-action]") {
          actionButtons = ["previous", "play", "next", "reset"].map((action) =>
            createElementStub({ action }),
          );
          return actionButtons;
        }
        return [];
      },
      getElementById() {
        return null;
      },
      addEventListener() {},
    },
  };

  vm.createContext(context);
  vm.runInContext(script, context);

  return {
    app,
    clickAction(action) {
      const button = actionButtons.find((item) => item.getAttribute("data-action") === action);
      assert.ok(button, `expected ${action} button to be bound`);
      button.click();
    },
  };
}

test("deep research status page has required static structure", async () => {
  await assert.doesNotReject(() => access(pagePath), "status page HTML file should exist");

  const html = await readPage();

  assert.match(html, /资料核验完成，准备组织报告/);

  for (const themeName of [
    "可比财务骨架",
    "增长与盈利韧性",
    "品牌与价格带",
    "中国/亚太市场",
    "数字渠道",
    "战略与竞争压力",
  ]) {
    assert.match(html, new RegExp(themeName.replace("/", "\\/")));
  }

  for (const metricValue of ["6/6", "114", "120", "0"]) {
    assert.match(html, new RegExp(`>${metricValue}<|["']${metricValue}["']`));
  }

  const deliverableTerms = [
    "final report",
    "outline",
    "citation",
    "markdown",
    "html",
    "最终",
    "报告",
    "大纲",
    "引用",
  ];
  const anchorsWithHref = [...html.matchAll(/<a\b(?=[^>]*\bhref\s*=)[^>]*>[\s\S]*?<\/a>/gi)];
  const activeDeliverableLinks = anchorsWithHref.filter(([anchor]) => {
    const linkText = stripTags(anchor).toLowerCase();
    const hasDeliverableTerm = deliverableTerms.some((term) => linkText.includes(term.toLowerCase()));
    const hasDisabledSemantics = /\baria-disabled\s*=\s*["']true["']/i.test(anchor);
    return hasDeliverableTerm && !hasDisabledSemantics;
  });

  assert.deepEqual(
    activeDeliverableLinks.map(([anchor]) => stripTags(anchor)),
    [],
    "final report, outline, citation, Markdown, and HTML deliverables must not be active links",
  );

  assert.match(html, /<button\b(?=[^>]*\baria-expanded\s*=)[^>]*>/i);
});

test("deep research status page simulates the full run lifecycle", async () => {
  const html = await readPage();

  for (const text of ["模拟运行", "播放", "上一步", "下一步", "重置"]) {
    assert.match(html, new RegExp(text), `expected simulation control text: ${text}`);
  }

  for (const stageName of [
    "需求确认",
    "研究规划",
    "资料检索",
    "资料核验",
    "报告组织",
    "章节撰写",
    "引用整理",
    "最终交付",
  ]) {
    assert.match(html, new RegExp(stageName), `expected lifecycle stage: ${stageName}`);
  }

  assert.match(html, /真实样例当前停在这里/);
  assert.match(html, /以下为模拟后续状态/);

  for (const simulatedArtifact of [
    "01_可比财务骨架.md",
    "02_增长与盈利韧性.md",
    "03_品牌与价格带.md",
    "04_中国亚太市场.md",
    "05_数字渠道.md",
    "06_战略与竞争压力.md",
    "report.md",
    "citations.json",
    "report.html",
  ]) {
    assert.match(html, new RegExp(simulatedArtifact.replace(".", "\\.")));
  }

  assert.match(html, /const runSnapshots = \[/);
  assert.match(html, /data-action="play"/);
  assert.match(html, /aria-live="polite"/);
});

test("simulation controls render default, advance, and reset states", async () => {
  const html = await readPage();
  const page = runPageScript(html);

  assert.match(page.app.innerHTML, /class="[^"]*dashboard-shell/);
  assert.match(page.app.innerHTML, /class="[^"]*status-console/);
  assert.match(page.app.innerHTML, /class="[^"]*work-area/);
  assert.match(page.app.innerHTML, /当前阶段/);
  assert.match(page.app.innerHTML, /阶段进度/);
  assert.match(page.app.innerHTML, /当前阶段说明/);
  assert.match(page.app.innerHTML, /已形成的研究材料/);
  assert.doesNotMatch(page.app.innerHTML, />后续产出</);
  assert.doesNotMatch(stripTags(page.app.innerHTML), /validator|agent|schema|sub_reports|sections\//i);

  assert.match(page.app.innerHTML, /资料核验完成，准备组织报告/);
  assert.match(page.app.innerHTML, /真实样例当前停在这里/);

  page.clickAction("next");
  assert.match(page.app.innerHTML, /正在撰写章节草稿/);
  assert.match(page.app.innerHTML, /01_可比财务骨架\.md/);

  page.clickAction("next");
  assert.match(page.app.innerHTML, /正在整理引用和来源清单/);
  assert.match(page.app.innerHTML, /citations\.json/);

  page.clickAction("next");
  assert.match(page.app.innerHTML, /最终报告已模拟生成/);
  assert.match(page.app.innerHTML, /report\.md/);
  assert.match(page.app.innerHTML, /report\.html/);

  page.clickAction("reset");
  assert.match(page.app.innerHTML, /资料核验完成，准备组织报告/);
  assert.match(page.app.innerHTML, /真实样例当前停在这里/);
});
