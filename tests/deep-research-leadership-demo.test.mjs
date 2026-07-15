import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { accessSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const archivePath = new URL(
  "./fixtures/deep-research-leadership-demo-source.zip",
  import.meta.url,
);
const builderPath = new URL(
  "../examples/deep-research-leadership-demo/build_demo.py",
  import.meta.url,
);
const outputPath = new URL(
  "../examples/deep-research-leadership-demo/index.html",
  import.meta.url,
);

const expectedHashes = {
  dimensions: "2e7e369a68f5132ec841e842b5a9dc4568bfef14d25646c9554c5b8418d94854",
  contentUnits: "af78593b71574c1d29cef113a6dc879f369e6a58ed9547d4c75449a8cdda737f",
  reportMarkdown: "2f4cc2a0da5d173fe09a3bce2651fd0606e9db782906573ad628a34a115acc18",
  citationsJson: "89b08831e60445e40972c86ec32030d972af9750cc6e61d377c6ab74316efb8e",
};

const expectedDimensionNames = [
  "九阶层定义、边界与可复算映射",
  "九层收入、现金流与人口分布事实",
  "九层资产、负债、净财富与可动用财力",
  "中国中产规模、内部结构与财力区间",
  "城乡、地区、城市等级与人口异质性",
  "消费结构、住房与社会保障负担",
  "财务韧性、冲击暴露与阶层流动",
];

const tempDir = mkdtempSync(join(tmpdir(), "dr-leadership-demo-"));
const tempOutput = join(tempDir, "index.html");
let freshHtml;
let payload;

after(() => rmSync(tempDir, { recursive: true, force: true }));

function decodePayload(html) {
  const match = html.match(
    /<script id="archive-data" type="application\/octet-stream">([A-Za-z0-9+/=]+)<\/script>/,
  );
  assert.ok(match, "embedded archive payload should exist");
  return JSON.parse(Buffer.from(match[1], "base64").toString("utf8"));
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])]),
    );
  }
  return value;
}

function sha256(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function assertEmbeddedCss(css) {
  assert.doesNotMatch(css, /@import\b/i, "CSS imports are not standalone");
  for (const match of css.matchAll(/url\(\s*["']?([^"')\s]+)["']?\s*\)/gi)) {
    assert.match(match[1], /^data:/i, "CSS URLs must be embedded data URLs");
  }
}

function assertStandaloneHtml(html) {
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
  for (const [, attributes, body] of scripts) {
    assert.doesNotMatch(
      attributes,
      /\btype\s*=\s*(?:["']module["']|module\b)/i,
      "module scripts are not standalone",
    );
    if (/\bid\s*=\s*["']archive-data["']/i.test(attributes)) continue;
    assert.doesNotMatch(
      body,
      /\bimport\b\s*(?:\(|["'{*\w])/,
      "module imports are not standalone",
    );
    assert.doesNotMatch(
      body,
      /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\b|\bnavigator\.sendBeacon\b/,
      "network APIs are not standalone",
    );
  }

  const styles = [...html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)];
  for (const [, body] of styles) {
    assertEmbeddedCss(body);
  }

  const tagSurface = html
    .replace(/(<script\b[^>]*>)[\s\S]*?(<\/script>)/gi, "$1$2")
    .replace(/(<style\b[^>]*>)[\s\S]*?(<\/style>)/gi, "$1$2");
  for (const tag of tagSurface.matchAll(/<([a-z][\w:-]*)\b([^>]*)>/gi)) {
    const [, tagName, attributes] = tag;
    assert.doesNotMatch(
      attributes,
      /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\b|\bnavigator\.sendBeacon\b/,
      "inline network APIs are not standalone",
    );
    assert.doesNotMatch(
      attributes,
      /\bimport\b\s*(?:\(|["'{*\w])/,
      "inline module imports are not standalone",
    );
    for (const style of attributes.matchAll(
      /\bstyle\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi,
    )) {
      assertEmbeddedCss(style[1] ?? style[2] ?? style[3]);
    }
    for (const attribute of attributes.matchAll(
      /\b(src|srcset|href|action|formaction|poster|data)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi,
    )) {
      const attributeName = attribute[1].toLowerCase();
      const value = attribute[2] ?? attribute[3] ?? attribute[4];
      if (attributeName === "srcset") {
        assert.match(
          value,
          /^data:[^\s]+(?:\s+\d+(?:\.\d+)?[wx])?$/i,
          "srcset resources must be one embedded data URL",
        );
        continue;
      }
      const isFragmentAnchor =
        tagName.toLowerCase() === "a" && attributeName === "href" && value.startsWith("#");
      const isEmbeddedData = /^data:/i.test(value);
      assert.ok(
        isFragmentAnchor || isEmbeddedData,
        `resource reference must be embedded: ${tagName} ${attributeName}=${value}`,
      );
    }
  }
}

before(() => {
  accessSync(archivePath);
  const build = spawnSync(
    "python3",
    [
      fileURLToPath(builderPath),
      "--archive",
      fileURLToPath(archivePath),
      "--output",
      tempOutput,
    ],
    { cwd: repoRoot, encoding: "utf8" },
  );
  assert.equal(build.status, 0, `builder failed:\n${build.stderr || build.stdout}`);
  freshHtml = readFileSync(tempOutput, "utf8");
  payload = decodePayload(freshHtml);
});

test("leadership demo builds deterministically from the tracked provenance fixture", () => {
  accessSync(outputPath);
  const committedHtml = readFileSync(outputPath, "utf8");

  assert.match(freshHtml, /^<!doctype html>/i);
  assert.doesNotMatch(freshHtml, /examples\/deep-research-status-page/);
  assert.equal(committedHtml, freshHtml, "committed demo must match a fresh archive build byte-for-byte");
});

test("standalone checks reject local, remote, module, CSS, and network dependencies", () => {
  assert.doesNotThrow(() => assertStandaloneHtml(freshHtml));
  assert.doesNotThrow(() =>
    assertStandaloneHtml('<a href="#details">详情</a><img src="data:image/gif;base64,AA==">'),
  );
  assert.doesNotThrow(() =>
    assertStandaloneHtml('<img srcset="data:image/gif;base64,AA== 1x">'),
  );

  for (const unsafeHtml of [
    '<script src="./runtime.js"></script>',
    '<link rel="stylesheet" href="/styles.css">',
    '<img src="//cdn.example.com/image.png">',
    '<img srcset="data:image/gif;base64,AA== 1x, //cdn.example.com/image.png 2x">',
    '<a href="https://example.com">remote</a>',
    '<script type="module">import "./runtime.js";</script>',
    '<script type=module></script>',
    '<script>import "./runtime.js";</script>',
    '<script>fetch("/api/status")</script>',
    '<button onclick="navigator.sendBeacon(\'/metrics\')">send</button>',
    '<style>@import "./theme.css";</style>',
    '<style>main { background: url(../background.png); }</style>',
    '<main style="background: url(./background.png)"></main>',
  ]) {
    assert.throws(() => assertStandaloneHtml(unsafeHtml));
  }
});

test("archive-derived normalized content matches independent SHA-256 provenance gates", () => {
  const normalizedDimensions = payload.dimensions.map(({ id, name, headline, findings }) => ({
    id,
    name,
    headline,
    findings: findings.map(({ text, claimIds }) => ({ text, claimIds })),
  }));

  assert.deepEqual(payload.dimensions.map((dimension) => dimension.name), expectedDimensionNames);
  assert.equal(sha256(JSON.stringify(canonicalize(normalizedDimensions))), expectedHashes.dimensions);
  assert.equal(
    sha256(JSON.stringify(canonicalize(payload.contentUnits))),
    expectedHashes.contentUnits,
  );
  assert.equal(sha256(payload.reportMarkdown), expectedHashes.reportMarkdown);
  assert.equal(sha256(payload.citationsJson), expectedHashes.citationsJson);
});

test("archive totals, dimension matrices, metadata, and snapshot gates stay exact", () => {
  assert.deepEqual(payload.totals, {
    dimensionCount: 7,
    claimCount: 108,
    sourceEntryCount: 73,
    uniqueSourceCount: 70,
    findingCount: 36,
    contentUnitCount: 5,
    citationCount: 58,
  });
  assert.equal(payload.verdict, "pass");
  assert.ok(payload.reportMarkdown.length > 0);
  assert.deepEqual(payload.metadata, {
    mode: "heavy",
    runId: "2026-07-14-china-9-strata-9185",
    reportTitle: "中国九阶层实际收入与财务状况：中产人数、特征与财力",
    startLabel: "2026-07-14 06:03",
    completionLabel: "2026-07-14 09:37",
    runSpanLabel: "真实运行跨度 06:03–09:37",
    elapsedLabel: "约 3 小时 34 分",
  });

  assert.equal(payload.dimensions.length, 7);
  assert.equal(payload.dimensions.flatMap((dimension) => dimension.findings).length, 36);
  assert.equal(payload.contentUnits.length, 5);
  assert.equal(payload.citations.length, 58);
  const canonicalCitations = JSON.parse(payload.citationsJson);
  assert.deepEqual(canonicalCitations.citations, payload.citations);
  assert.equal(payload.citationsJson, JSON.stringify(canonicalCitations, null, 2));
  assert.equal("finalReview" in payload, false, "review internals must not enter the payload");

  const expectedDimensions = {
    d1: [18, 12, 4],
    d2: [14, 10, 6],
    d3: [18, 11, 5],
    d4: [17, 9, 5],
    d5: [10, 15, 5],
    d6: [13, 8, 5],
    d7: [18, 8, 6],
  };
  for (const dimension of payload.dimensions) {
    assert.deepEqual(
      [dimension.claimCount, dimension.sourceCount, dimension.findings.length],
      expectedDimensions[dimension.id],
      `archive totals changed for ${dimension.id}`,
    );
    assert.ok(dimension.headline.length > 0, `${dimension.id} headline should be non-empty`);
    for (const finding of dimension.findings) {
      assert.ok(finding.text.length > 0, `${dimension.id} finding text should be non-empty`);
      assert.ok(finding.claimIds.length > 0, `${dimension.id} finding claim IDs should be non-empty`);
      assert.equal(finding.claimCount, finding.claimIds.length);
    }
  }
  for (const unit of payload.contentUnits) {
    assert.ok(unit.title.length > 0, `${unit.id} title should be non-empty`);
  }

  const expectedStages = [
    "需求确认",
    "研究规划",
    "多主题研究",
    "质量核验",
    "报告组织",
    "写作审校",
    "最终交付",
  ];
  const expectedProgress = [14, 29, 43, 57, 71, 86, 100];
  const expectedModes = ["scope", "plan", "research", "quality", "outline", "review", "delivery"];
  const expectedHeadlines = [
    "研究范围与关键口径已经确认",
    "7 个研究维度已经规划完成",
    "多主题研究正在推进",
    "研究材料已经完成质量核验",
    "最终报告结构已经组织完成",
    "报告写作与终审已经完成",
    "最终报告与引用清单已经生成",
  ];
  const expectedGates = [
    ["hidden", "hidden", false, false, false, false],
    ["planned", "hidden", false, false, false, false],
    ["researching", "hidden", false, false, false, false],
    ["verified", "hidden", true, true, false, false],
    ["verified", "organized", true, true, false, false],
    ["verified", "written", true, true, true, false],
    ["verified", "delivered", true, true, true, true],
  ];
  const snapshotKeys = [
    "dimensionState",
    "explanation",
    "findingsAvailable",
    "headline",
    "index",
    "metricsVisible",
    "progress",
    "reportAvailable",
    "reviewPassed",
    "stage",
    "statements",
    "unitState",
    "workMode",
  ].sort();

  assert.equal(payload.snapshots.length, 7);
  payload.snapshots.forEach((snapshot, index) => {
    assert.deepEqual(Object.keys(snapshot).sort(), snapshotKeys);
    assert.equal(snapshot.index, index + 1);
    assert.equal(snapshot.stage, expectedStages[index]);
    assert.equal(snapshot.progress, expectedProgress[index]);
    assert.equal(snapshot.workMode, expectedModes[index]);
    assert.equal(snapshot.headline, expectedHeadlines[index]);
    assert.ok(snapshot.explanation.length > 0);
    assert.ok(snapshot.statements.length >= 1 && snapshot.statements.length <= 3);
    assert.ok(snapshot.statements.every((statement) => statement.length > 0));
    assert.deepEqual(
      [
        snapshot.dimensionState,
        snapshot.unitState,
        snapshot.metricsVisible,
        snapshot.findingsAvailable,
        snapshot.reviewPassed,
        snapshot.reportAvailable,
      ],
      expectedGates[index],
    );
  });
});
