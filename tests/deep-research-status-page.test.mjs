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
