import assert from "node:assert/strict";
import { accessSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { after, test } from "node:test";

const repoRoot = fileURLToPath(new URL("../", import.meta.url));
const archivePath = new URL("../2026-07-14-china-9-strata-9185.zip", import.meta.url);
const builderPath = new URL(
  "../examples/deep-research-leadership-demo/build_demo.py",
  import.meta.url,
);
const outputPath = new URL(
  "../examples/deep-research-leadership-demo/index.html",
  import.meta.url,
);

const tempDir = mkdtempSync(join(tmpdir(), "dr-leadership-demo-"));
const tempOutput = join(tempDir, "index.html");

after(() => rmSync(tempDir, { recursive: true, force: true }));

function decodePayload(html) {
  const match = html.match(
    /<script id="archive-data" type="application\/octet-stream">([A-Za-z0-9+/=]+)<\/script>/,
  );
  assert.ok(match, "embedded archive payload should exist");
  return JSON.parse(Buffer.from(match[1], "base64").toString("utf8"));
}

test("leadership demo is a deterministic standalone build of the research archive", () => {
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
  accessSync(tempOutput);
  accessSync(outputPath);

  const freshHtml = readFileSync(tempOutput, "utf8");
  const committedHtml = readFileSync(outputPath, "utf8");

  assert.match(freshHtml, /^<!doctype html>/i);
  assert.doesNotMatch(
    freshHtml,
    /https?:\/\//i,
    "standalone page must not load external HTTP resources",
  );
  assert.doesNotMatch(freshHtml, /examples\/deep-research-status-page/);
  assert.equal(committedHtml, freshHtml, "committed demo must match a fresh archive build byte-for-byte");

  const payload = decodePayload(freshHtml);
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
  assert.equal(
    payload.metadata.reportTitle,
    "中国九阶层实际收入与财务状况：中产人数、特征与财力",
  );
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
  assert.ok(payload.citationsJson.length > 0);
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
