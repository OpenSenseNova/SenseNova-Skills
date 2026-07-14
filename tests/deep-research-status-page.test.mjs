import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { test } from "node:test";

const pagePath = new URL("../examples/deep-research-status-page/index.html", import.meta.url);

async function readPage() {
  return readFile(pagePath, "utf8");
}

function stripTags(value) {
  return value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
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
