import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { accessSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

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

function encodePayload(value) {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64");
}

function createElement(overrides = {}) {
  const listeners = new Map();
  const attributes = new Map();
  const element = {
    innerHTML: "",
    textContent: "",
    disabled: false,
    focused: false,
    focusCount: 0,
    open: false,
    isConnected: true,
    focusables: [],
    listeners,
    addEventListener(type, listener) {
      const entries = listeners.get(type) ?? [];
      entries.push(listener);
      listeners.set(type, entries);
    },
    dispatchEvent(event) {
      event.currentTarget ??= this;
      event.target ??= this;
      for (const listener of listeners.get(event.type) ?? []) listener(event);
    },
    click() {
      this.dispatchEvent({ type: "click", preventDefault() {} });
    },
    focus() {
      this.focused = true;
      this.focusCount += 1;
    },
    contains(candidate) {
      return candidate === this || this.focusables.includes(candidate);
    },
    matches(selector) {
      return !this.disabled && /button|\[href\]|input|select|textarea|\[tabindex\]/.test(selector);
    },
    closest() {
      return null;
    },
    setAttribute(name, value) {
      attributes.set(name, String(value));
    },
    getAttribute(name) {
      return attributes.get(name) ?? null;
    },
    removeAttribute(name) {
      attributes.delete(name);
    },
    querySelector(selector) {
      return this.querySelectorAll(selector)[0] ?? null;
    },
    querySelectorAll(selector) {
      return /button|\[href\]|input|select|textarea|\[tabindex\]/.test(selector)
        ? this.focusables.filter((item) => !item.disabled)
        : [];
    },
    ...overrides,
  };
  return element;
}

function createRuntime(html, { data = null, anchorClickError = null } = {}) {
  const runtimeMatch = html.match(/<script\s+data-demo-runtime>([\s\S]*?)<\/script>/i);
  assert.ok(runtimeMatch, "inline demo runtime should exist");

  const focusEvents = [];
  const documentListeners = new Map();
  const blobs = [];
  const objectUrls = [];
  const revokedUrls = [];
  const anchors = [];
  let renderedHtml = "";
  let elementGeneration = 0;
  let document;
  const createHeading = () => {
    const generation = elementGeneration;
    const element = createElement();
    element.focus = function () {
      this.focused = true;
      this.focusCount += 1;
      focusEvents.push(`heading.focus:${generation}`);
      document.activeElement = this;
    };
    return element;
  };
  const createAction = (action) => {
    const generation = elementGeneration;
    const disabled = new RegExp(`data-action="${action}"[^>]*disabled`).test(renderedHtml);
    const element = createElement({
      disabled,
      getAttribute(name) {
        return name === "data-action" ? action : null;
      },
    });
    element.focus = function () {
      if (this.disabled) {
        focusEvents.push(`action.focus-disabled:${action}:${generation}`);
        return;
      }
      this.focused = true;
      this.focusCount += 1;
      focusEvents.push(`action.focus:${action}:${generation}`);
      document.activeElement = this;
    };
    return element;
  };
  const createStage = (index) => {
    const generation = elementGeneration;
    const disabled = new RegExp(`data-stage-index="${index}"[^>]*disabled`).test(renderedHtml);
    const element = createElement({
      disabled,
      getAttribute(name) {
        return name === "data-stage-index" ? String(index) : null;
      },
    });
    element.focus = function () {
      if (this.disabled) {
        focusEvents.push(`stage.focus-disabled:${index}:${generation}`);
        return;
      }
      this.focused = true;
      this.focusCount += 1;
      focusEvents.push(`stage.focus:${index}:${generation}`);
      document.activeElement = this;
    };
    return element;
  };
  const createControls = () => ({
    play: createAction("play"),
    pause: createAction("pause"),
    previous: createAction("previous"),
    next: createAction("next"),
    restart: createAction("restart"),
    stages: Array.from({ length: 7 }, (_, index) => createStage(index)),
  });
  let heading = createHeading();
  let controls = createControls();
  const app = createElement();
  let reportActions = {};
  let dimensionTriggers = [];
  Object.defineProperty(app, "innerHTML", {
    configurable: true,
    get() {
      return renderedHtml;
    },
    set(value) {
      focusEvents.push("app.innerHTML");
      if (document?.activeElement) document.activeElement.detached = true;
      const previousElements = [
        heading,
        ...Object.values(controls).flatMap((item) => Array.isArray(item) ? item : [item]),
        ...Object.values(reportActions),
        ...dimensionTriggers,
      ];
      previousElements.forEach((element) => {
        if (element) {
          element.detached = true;
          element.isConnected = false;
        }
      });
      if (document) document.activeElement = null;
      renderedHtml = value;
      elementGeneration += 1;
      heading = createHeading();
      controls = createControls();
      reportActions = Object.fromEntries(["read", "report", "citations"].map((action) => {
        const disabled = new RegExp(`data-report-action="${action}"[^>]*disabled`).test(renderedHtml);
        return [action, createElement({
          disabled,
          getAttribute(name) { return name === "data-report-action" ? action : null; },
          focus() {
            if (this.disabled) return;
            this.focused = true;
            this.focusCount += 1;
            document.activeElement = this;
          },
        })];
      }));
      dimensionTriggers = [...renderedHtml.matchAll(/data-dimension-id="([^"]+)"/g)].map((match) =>
        createElement({
          getAttribute(name) { return name === "data-dimension-id" ? match[1] : null; },
          focus() { this.focused = true; this.focusCount += 1; document.activeElement = this; },
        }),
      );
    },
  });
  const announcement = createElement();
  const archive = createElement({ textContent: data ? encodePayload(data) : encodePayload(decodePayload(html)) });
  const reload = { count: 0 };
  const timerCalls = [];
  const clearCalls = [];
  let timerId = 0;
  const timers = new Map();
  const dimensionContent = createElement();
  const reportContent = createElement();
  const dimensionClose = createElement();
  const reportClose = createElement();
  const makeDialog = (closeButton, content, native = true) => {
    const dialog = createElement({ focusables: [closeButton, content] });
    if (native) {
      dialog.showModal = function () { this.open = true; this.setAttribute("open", ""); };
      dialog.close = function () { this.open = false; this.removeAttribute("open"); };
    }
    return dialog;
  };
  const dimensionDialog = makeDialog(dimensionClose, dimensionContent);
  const reportDialog = makeDialog(reportClose, reportContent);
  const byId = {
    app,
    announcement,
    "archive-data": archive,
    "dimension-dialog": dimensionDialog,
    "dimension-dialog-content": dimensionContent,
    "report-dialog": reportDialog,
    "report-dialog-content": reportContent,
  };
  const bySelector = { "[data-reload]": createElement() };
  document = {
    readyState: "loading",
    activeElement: null,
    addEventListener(type, listener) {
      const entries = documentListeners.get(type) ?? [];
      entries.push(listener);
      documentListeners.set(type, entries);
    },
    dispatchEvent(event) {
      for (const listener of documentListeners.get(event.type) ?? []) listener(event);
    },
    contains(element) {
      return Boolean(element && element.isConnected !== false);
    },
    getElementById(id) {
      return byId[id] ?? null;
    },
    querySelector(selector) {
      if (selector === "[data-current-heading]") return heading;
      const action = selector.match(/^\[data-action="(play|pause|previous|next|restart)"\]$/)?.[1];
      if (action) return controls[action];
      const stage = selector.match(/^\[data-stage-index="([0-6])"\]$/)?.[1];
      if (stage !== undefined) return controls.stages[Number(stage)];
      const reportAction = selector.match(/^\[data-report-action="(read|report|citations)"\]$/)?.[1];
      if (reportAction) return reportActions[reportAction] ?? null;
      const dimensionId = selector.match(/^\[data-dimension-id="(d[1-7])"\]$/)?.[1];
      if (dimensionId) return dimensionTriggers.find((element) => element.getAttribute("data-dimension-id") === dimensionId) ?? null;
      if (selector === "#dimension-dialog [data-dialog-close]") return dimensionClose;
      if (selector === "#report-dialog [data-dialog-close]") return reportClose;
      return bySelector[selector] ?? null;
    },
    querySelectorAll(selector) {
      if (selector === "[data-stage-index]") return controls.stages;
      if (selector === "[data-dimension-id]") return dimensionTriggers;
      return [];
    },
    createElement(tagName) {
      const element = createElement({ tagName: String(tagName).toUpperCase() });
      if (tagName === "a") {
        element.click = function () {
          this.clicked = true;
          if (anchorClickError) throw anchorClickError;
        };
        anchors.push(element);
      }
      return element;
    },
  };
  const window = {
    location: { reload: () => reload.count++ },
    setInterval(callback, delay) {
      const id = ++timerId;
      timers.set(id, callback);
      timerCalls.push({
        id,
        delay,
        callback() {
          if (timers.has(id)) callback();
        },
      });
      return id;
    },
    clearInterval(id) {
      clearCalls.push(id);
      timers.delete(id);
    },
  };
  class FakeBlob {
    constructor(parts, options = {}) {
      this.parts = parts;
      this.type = options.type ?? "";
      blobs.push(this);
    }
  }
  const context = vm.createContext({
    atob: (value) => Buffer.from(value, "base64").toString("binary"),
    TextDecoder,
    Uint8Array,
    Blob: FakeBlob,
    URL: {
      createObjectURL(blob) { const url = `blob:test-${objectUrls.length + 1}`; objectUrls.push({ blob, url }); return url; },
      revokeObjectURL(url) { revokedUrls.push(url); },
    },
    window,
    document,
    console,
  });
  vm.runInContext(runtimeMatch[1], context);
  return {
    context,
    document,
    app,
    announcement,
    archive,
    reload,
    get controls() {
      return controls;
    },
    get heading() {
      return heading;
    },
    focusEvents,
    timers,
    timerCalls,
    clearCalls,
    bySelector,
    byId,
    blobs,
    objectUrls,
    revokedUrls,
    anchors,
    documentListeners,
    get reportActions() { return reportActions; },
    get dimensionTriggers() { return dimensionTriggers; },
  };
}

function plain(value) {
  return JSON.parse(JSON.stringify(value));
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

test("replay reducer preserves deterministic playback and final-hold boundaries", () => {
  const { replayReducer } = createRuntime(freshHtml).context;
  const paused = { index: 0, playing: false, finalHold: false };

  assert.deepEqual(plain(replayReducer(paused, { type: "PLAY" })), {
    index: 0,
    playing: true,
    finalHold: false,
  });
  assert.deepEqual(plain(replayReducer(paused, { type: "TICK" })), paused);
  assert.deepEqual(
    plain(replayReducer({ index: 6, playing: false, finalHold: false }, { type: "PLAY" })),
    { index: 0, playing: true, finalHold: false },
  );

  let state = replayReducer(paused, { type: "PLAY" });
  for (let index = 1; index <= 5; index++) {
    state = replayReducer(state, { type: "TICK" });
    assert.deepEqual(plain(state), { index, playing: true, finalHold: false });
  }
  state = replayReducer(state, { type: "TICK" });
  assert.deepEqual(plain(state), { index: 6, playing: true, finalHold: true });
  state = replayReducer(state, { type: "TICK" });
  assert.deepEqual(plain(state), { index: 6, playing: false, finalHold: false });

  for (const [action, expected] of [
    [{ type: "PAUSE" }, { index: 6, playing: false, finalHold: false }],
    [{ type: "PREVIOUS" }, { index: 5, playing: false, finalHold: false }],
    [{ type: "NEXT" }, { index: 6, playing: false, finalHold: false }],
    [{ type: "SELECT", index: -20 }, { index: 0, playing: false, finalHold: false }],
    [{ type: "SELECT", index: 99 }, { index: 6, playing: false, finalHold: false }],
    [{ type: "RESTART" }, { index: 0, playing: true, finalHold: false }],
  ]) {
    assert.deepEqual(
      plain(replayReducer({ index: 6, playing: true, finalHold: true }, action)),
      expected,
    );
  }
  assert.deepEqual(
    plain(replayReducer({ index: 0, playing: true, finalHold: false }, { type: "PREVIOUS" })),
    { index: 0, playing: false, finalHold: false },
  );
  assert.deepEqual(
    plain(replayReducer({ index: 6, playing: true, finalHold: true }, { type: "NEXT" })),
    { index: 6, playing: false, finalHold: false },
  );
});

test("snapshot selector and dashboard renderer enforce every milestone gate", () => {
  const { context } = createRuntime(freshHtml);
  const render = (index, playing = false) =>
    context.renderDashboard({
      ...context.selectSnapshot(payload, index),
      playback: { index, playing, finalHold: false },
    });
  const alwaysVisible = [
    payload.metadata.reportTitle,
    payload.metadata.runId,
    "Heavy 深度模式",
    payload.metadata.runSpanLabel,
  ];

  for (let index = 0; index < 7; index++) {
    const html = render(index);
    for (const label of alwaysVisible) assert.match(html, new RegExp(label));
    assert.match(html, new RegExp(`历史回放 · 里程碑 ${index + 1} / 7`));
    assert.equal((html.match(/data-stage-index=/g) ?? []).length, 7);
    assert.match(html, /状态：(已完成|当前|待进行)/);
    assert.match(html, /aria-current="step"/);
  }

  const first = render(0);
  assert.match(first, /阶段 1 \/ 7/);
  assert.match(first, /14%/);
  assert.match(first, /流程阶段进度/);
  for (const forbidden of [...expectedDimensionNames, "108", "73", "36", ...payload.contentUnits.map((u) => u.title)]) {
    assert.doesNotMatch(first, new RegExp(forbidden));
  }

  const second = render(1);
  for (const name of expectedDimensionNames) assert.match(second, new RegExp(name));
  for (const forbidden of ["108", "73", "36", payload.dimensions[0].findings[0].text]) {
    assert.doesNotMatch(second, new RegExp(forbidden));
  }

  const third = render(2);
  assert.equal((third.match(/研究中/g) ?? []).length, 7);
  assert.doesNotMatch(third, /class="matrix"|研究要点 \/ 来源条目 \/ 核验发现/);

  const fourth = render(3);
  for (const row of ["18 / 12 / 4", "14 / 10 / 6", "18 / 11 / 5", "17 / 9 / 5", "10 / 15 / 5", "13 / 8 / 5", "18 / 8 / 6"]) {
    assert.match(fourth, new RegExp(row.replaceAll("/", "\\/")));
  }
  for (const expected of ["108", "73", "36", "已核验"]) assert.match(fourth, new RegExp(expected));

  const fifth = render(4);
  for (const unit of payload.contentUnits) assert.match(fifth, new RegExp(unit.title));
  assert.doesNotMatch(fifth, /research-card|维度研究矩阵/);

  const sixth = render(5);
  assert.equal((sixth.match(/已写作/g) ?? []).length, 5);
  assert.match(sixth, /终审通过/);
  assert.equal((sixth.match(/data-report-action[^>]+disabled/g) ?? []).length, 3);

  const seventh = render(6);
  for (const expected of ["100%", "108", "73", "70", "36", "58"]) {
    assert.match(seventh, new RegExp(expected));
  }
  for (const unit of payload.contentUnits) assert.match(seventh, new RegExp(unit.title));
  assert.equal((seventh.match(/data-report-action/g) ?? []).length, 3);
  assert.equal((seventh.match(/data-report-action[^>]+disabled/g) ?? []).length, 0);

  const dashboardCopy = render(6).replace(/<[^>]+>/g, " ");
  assert.match(dashboardCopy, /真实研究记录动态回放/);
  assert.match(dashboardCopy, /流程顺序回放，非逐秒运行日志/);
  assert.doesNotMatch(
    dashboardCopy,
    /实时同步|刚刚|当前更新时间|validator|review|perspective|supplement|stitcher|render|agent|schema|dispatch/i,
  );
});

test("archive decoder validates exact invariants and bootstrap offers reload fallback", () => {
  const valid = createRuntime(freshHtml);
  assert.equal(valid.context.validateArchiveData(payload), true);
  assert.deepEqual(plain(valid.context.decodeArchiveData()), payload);

  const invalidPayloads = [];
  const wrongProgress = structuredClone(payload);
  wrongProgress.snapshots[0].progress = 15;
  invalidPayloads.push(wrongProgress);
  const missingDimension = structuredClone(payload);
  missingDimension.dimensions.pop();
  invalidPayloads.push(missingDimension);
  const wrongTotals = structuredClone(payload);
  wrongTotals.totals.claimCount = 109;
  invalidPayloads.push(wrongTotals);
  const emptyReport = structuredClone(payload);
  emptyReport.reportMarkdown = "";
  invalidPayloads.push(emptyReport);
  const wrongVerdict = structuredClone(payload);
  wrongVerdict.verdict = "fail";
  invalidPayloads.push(wrongVerdict);
  const wrongHeadline = structuredClone(payload);
  wrongHeadline.snapshots[3].headline = "被篡改的里程碑标题";
  invalidPayloads.push(wrongHeadline);

  for (const invalid of invalidPayloads) {
    assert.throws(() => valid.context.validateArchiveData(invalid));
  }

  const fallback = createRuntime(freshHtml, { data: wrongProgress });
  fallback.context.bootstrap();
  assert.match(fallback.app.innerHTML, /演示数据暂时无法加载/);
  assert.match(fallback.app.innerHTML, /重新加载/);
  fallback.bySelector["[data-reload]"].click();
  assert.equal(fallback.reload.count, 1);

  const headlineFallback = createRuntime(freshHtml, { data: wrongHeadline });
  headlineFallback.context.bootstrap();
  assert.match(headlineFallback.app.innerHTML, /演示数据暂时无法加载/);
});

test("bound controls maintain one eight-second timer and deterministic final hold", () => {
  const runtime = createRuntime(freshHtml);
  runtime.context.bootstrap();
  assert.match(runtime.app.innerHTML, /阶段 1 \/ 7/);
  assert.match(runtime.app.innerHTML, /data-action="previous"[^>]*disabled/);

  runtime.controls.play.click();
  assert.equal(runtime.timerCalls.length, 1);
  assert.equal(runtime.timerCalls[0].delay, 8000);
  runtime.controls.play.click();
  assert.equal(runtime.timerCalls.length, 1, "repeated play must reuse the active interval");

  const tick = runtime.timerCalls[0].callback;
  for (let milestone = 2; milestone <= 7; milestone++) {
    tick();
    assert.match(runtime.app.innerHTML, new RegExp(`阶段 ${milestone} \\/ 7`));
  }
  assert.equal(runtime.clearCalls.length, 0, "snapshot 7 holds for one complete interval");
  tick();
  assert.match(runtime.app.innerHTML, /阶段 7 \/ 7/);
  assert.match(runtime.app.innerHTML, /data-action="next"[^>]*disabled/);
  assert.equal(runtime.clearCalls.length, 1);

  runtime.controls.play.click();
  assert.equal(runtime.timerCalls.length, 2);
  runtime.controls.previous.click();
  assert.equal(runtime.clearCalls.length, 2);

  runtime.controls.play.click();
  const clearsBeforePause = runtime.clearCalls.length;
  runtime.controls.pause.click();
  assert.equal(runtime.clearCalls.length, clearsBeforePause + 1);

  runtime.controls.play.click();
  const clearsBeforeNext = runtime.clearCalls.length;
  runtime.controls.next.click();
  assert.equal(runtime.clearCalls.length, clearsBeforeNext + 1);

  runtime.controls.play.click();
  const clearsBeforeSelect = runtime.clearCalls.length;
  runtime.controls.stages[4].click();
  assert.equal(runtime.clearCalls.length, clearsBeforeSelect + 1);
  assert.match(runtime.app.innerHTML, /阶段 5 \/ 7/);
  assert.match(runtime.announcement.textContent, /里程碑 5 \/ 7/);

  runtime.controls.play.click();
  const callsBeforeRestart = runtime.timerCalls.length;
  const clearsBeforeRestart = runtime.clearCalls.length;
  runtime.controls.restart.click();
  assert.equal(runtime.clearCalls.length, clearsBeforeRestart + 1);
  assert.equal(runtime.timerCalls.length, callsBeforeRestart + 1);
  assert.match(runtime.app.innerHTML, /阶段 1 \/ 7/);
  runtime.controls.pause.click();
  assert.ok(runtime.clearCalls.length > clearsBeforeRestart + 1);
});

test("play during the final hold replaces the timer and gives stage one a full interval", () => {
  const runtime = createRuntime(freshHtml);
  runtime.context.bootstrap();
  runtime.controls.play.click();
  const oldTimer = runtime.timerCalls[0];
  for (let tick = 0; tick < 6; tick++) oldTimer.callback();
  assert.match(runtime.app.innerHTML, /阶段 7 \/ 7/);
  assert.equal(runtime.clearCalls.length, 0);

  runtime.controls.play.click();
  assert.deepEqual(runtime.clearCalls, [oldTimer.id]);
  assert.equal(runtime.timerCalls.length, 2);
  const replacementTimer = runtime.timerCalls[1];
  assert.notEqual(replacementTimer.id, oldTimer.id);
  assert.equal(replacementTimer.delay, 8000);
  assert.match(runtime.app.innerHTML, /阶段 1 \/ 7/);
  assert.equal(runtime.timers.has(oldTimer.id), false);
  assert.equal(runtime.timers.has(replacementTimer.id), true);

  oldTimer.callback();
  assert.match(runtime.app.innerHTML, /阶段 1 \/ 7/, "cleared callback is inert");
  replacementTimer.callback();
  assert.match(runtime.app.innerHTML, /阶段 2 \/ 7/);
});

test("rerender moves focus only when replacing focused work content", () => {
  const workFocused = createRuntime(freshHtml);
  workFocused.context.bootstrap();
  workFocused.controls.play.click();
  workFocused.focusEvents.length = 0;
  workFocused.document.activeElement = createElement({
    closest(selector) {
      return selector === ".work-area" ? this : null;
    },
  });
  workFocused.timerCalls[0].callback();
  assert.deepEqual(workFocused.focusEvents, [
    "heading.focus:2",
    "app.innerHTML",
    "heading.focus:3",
  ]);

  const controlFocused = createRuntime(freshHtml);
  controlFocused.context.bootstrap();
  const oldNext = controlFocused.controls.next;
  oldNext.focus();
  controlFocused.focusEvents.length = 0;
  oldNext.click();
  assert.deepEqual(controlFocused.focusEvents, [
    "app.innerHTML",
    "action.focus:next:2",
  ]);
  assert.equal(controlFocused.document.activeElement, controlFocused.controls.next);
  assert.notEqual(controlFocused.document.activeElement, oldNext);
  assert.equal(oldNext.detached, true);

  const oldStage = controlFocused.controls.stages[4];
  oldStage.focus();
  controlFocused.focusEvents.length = 0;
  oldStage.click();
  assert.deepEqual(controlFocused.focusEvents, [
    "app.innerHTML",
    "stage.focus:4:3",
  ]);
  assert.equal(controlFocused.document.activeElement, controlFocused.controls.stages[4]);
  assert.notEqual(controlFocused.document.activeElement, oldStage);

  const tickFocused = createRuntime(freshHtml);
  tickFocused.context.bootstrap();
  tickFocused.controls.play.click();
  const oldPause = tickFocused.controls.pause;
  oldPause.focus();
  tickFocused.focusEvents.length = 0;
  tickFocused.timerCalls[0].callback();
  assert.deepEqual(tickFocused.focusEvents, [
    "app.innerHTML",
    "action.focus:pause:3",
  ]);
  assert.equal(tickFocused.document.activeElement, tickFocused.controls.pause);
  assert.notEqual(tickFocused.document.activeElement, oldPause);

  const unsupportedFocused = createRuntime(freshHtml);
  unsupportedFocused.context.bootstrap();
  unsupportedFocused.controls.play.click();
  unsupportedFocused.document.activeElement = createElement();
  unsupportedFocused.focusEvents.length = 0;
  unsupportedFocused.timerCalls[0].callback();
  assert.deepEqual(unsupportedFocused.focusEvents, ["app.innerHTML"]);
  assert.equal(unsupportedFocused.document.activeElement, null);
});

test("disabled replay targets fall back to the new stage heading", () => {
  const paused = createRuntime(freshHtml);
  paused.context.bootstrap();
  paused.controls.play.click();
  const oldPause = paused.controls.pause;
  oldPause.focus();
  paused.focusEvents.length = 0;
  oldPause.click();
  assert.deepEqual(paused.focusEvents, ["app.innerHTML", "heading.focus:3"]);
  assert.equal(paused.document.activeElement, paused.heading);
  assert.equal(paused.controls.pause.disabled, true);

  const previous = createRuntime(freshHtml);
  previous.context.bootstrap();
  previous.controls.next.click();
  const oldPrevious = previous.controls.previous;
  oldPrevious.focus();
  previous.focusEvents.length = 0;
  oldPrevious.click();
  assert.deepEqual(previous.focusEvents, ["app.innerHTML", "heading.focus:3"]);
  assert.equal(previous.document.activeElement, previous.heading);
  assert.equal(previous.controls.previous.disabled, true);

  const next = createRuntime(freshHtml);
  next.context.bootstrap();
  next.controls.stages[5].click();
  const oldNext = next.controls.next;
  oldNext.focus();
  next.focusEvents.length = 0;
  oldNext.click();
  assert.deepEqual(next.focusEvents, ["app.innerHTML", "heading.focus:3"]);
  assert.equal(next.document.activeElement, next.heading);
  assert.equal(next.controls.next.disabled, true);

  const finalTick = createRuntime(freshHtml);
  finalTick.context.bootstrap();
  finalTick.controls.play.click();
  const timer = finalTick.timerCalls[0];
  for (let tick = 0; tick < 6; tick++) timer.callback();
  const finalPause = finalTick.controls.pause;
  finalPause.focus();
  finalTick.focusEvents.length = 0;
  timer.callback();
  assert.deepEqual(finalTick.focusEvents, ["app.innerHTML", "heading.focus:9"]);
  assert.equal(finalTick.document.activeElement, finalTick.heading);
  assert.equal(finalTick.controls.pause.disabled, true);
});

test("enabled replay targets retain focus on their new equivalent", () => {
  for (const action of ["play", "restart"]) {
    const runtime = createRuntime(freshHtml);
    runtime.context.bootstrap();
    const oldControl = runtime.controls[action];
    oldControl.focus();
    runtime.focusEvents.length = 0;
    oldControl.click();
    assert.deepEqual(runtime.focusEvents, [
      "app.innerHTML",
      `action.focus:${action}:2`,
    ]);
    assert.equal(runtime.document.activeElement, runtime.controls[action]);
    assert.notEqual(runtime.document.activeElement, oldControl);
    assert.equal(runtime.controls[action].disabled, false);
  }

  const stage = createRuntime(freshHtml);
  stage.context.bootstrap();
  const oldStage = stage.controls.stages[3];
  oldStage.focus();
  stage.focusEvents.length = 0;
  oldStage.click();
  assert.deepEqual(stage.focusEvents, ["app.innerHTML", "stage.focus:3:2"]);
  assert.equal(stage.document.activeElement, stage.controls.stages[3]);
  assert.equal(stage.controls.stages[3].disabled, false);
});

test("leadership replay CSS keeps progress prominent and layout responsive", () => {
  const css = freshHtml.match(/<style>([\s\S]*?)<\/style>/i)?.[1] ?? "";
  assert.match(css, /body\s*\{[^}]*font-size:\s*15px/s);
  assert.match(css, /\.metadata[^}]*font-size:\s*12px/s);
  assert.match(css, /\.stage-headline[^}]*font-size:\s*clamp\(28px,\s*3vw,\s*34px\)/s);
  assert.match(css, /\.progress-value[^}]*font-size:\s*clamp\(46px,\s*5vw,\s*56px\)/s);
  assert.match(css, /\.lifecycle[^}]*grid-template-columns:\s*repeat\(7,\s*minmax\(0,\s*1fr\)\)/s);
  assert.match(css, /\.work-layout[^}]*grid-template-columns:/s);
  assert.match(css, /--pending:\s*#5d6975/);
  assert.doesNotMatch(css, /linear-gradient|radial-gradient|border-radius:\s*(?:1[3-9]|[2-9]\d)px/i);
  const { context } = createRuntime(freshHtml);
  const html = context.renderDashboard({
    ...context.selectSnapshot(payload, 0),
    playback: { index: 0, playing: false, finalHold: false },
  });
  assert.match(html, /<div class="controls" role="group" aria-label="回放控制">/);
});

test("dashboard escapes archive strings in work cards and milestone copy", () => {
  const malicious = structuredClone(payload);
  malicious.dimensions[0].name = '<script>alert("dimension")</script>';
  malicious.contentUnits[0].title = '<img src=x onerror="alert(1)">';
  malicious.snapshots[1].explanation = '<script>alert("explanation")</script>';
  malicious.snapshots[1].statements = ['<svg onload="alert(2)">'];
  const { context } = createRuntime(freshHtml);
  const planned = context.renderDashboard({
    ...context.selectSnapshot(malicious, 1),
    playback: { index: 1, playing: false, finalHold: false },
  });
  const organized = context.renderDashboard({
    ...context.selectSnapshot(malicious, 4),
    playback: { index: 4, playing: false, finalHold: false },
  });

  for (const html of [planned, organized]) {
    assert.doesNotMatch(html, /<script\b|<img\b|<svg\b/i);
  }
  assert.match(planned, /&lt;script&gt;alert\(&quot;dimension&quot;\)&lt;\/script&gt;/);
  assert.match(planned, /&lt;script&gt;alert\(&quot;explanation&quot;\)&lt;\/script&gt;/);
  assert.match(planned, /&lt;svg onload=&quot;alert\(2\)&quot;&gt;/);
  assert.match(organized, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
});

test("dimension findings stay gated, then render every archive-backed finding on demand", () => {
  const { context } = createRuntime(freshHtml);
  for (let index = 0; index < 3; index++) {
    assert.equal(context.renderDimensionDialog(payload, "d1", index), "<p>该维度尚未形成可展示发现</p>");
  }

  for (let index = 3; index < 7; index++) {
    for (const dimension of payload.dimensions) {
      const html = context.renderDimensionDialog(payload, dimension.id, index);
      assert.match(html, new RegExp(dimension.name));
      assert.match(html, new RegExp(dimension.headline.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
      assert.match(html, new RegExp(`${dimension.claimCount} 条研究要点`));
      assert.match(html, new RegExp(`${dimension.sourceCount} 条来源`));
      assert.match(html, /已核验/);
      for (const finding of dimension.findings) {
        assert.match(html, new RegExp(finding.text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
        assert.match(html, new RegExp(`关联 ${finding.claimCount} 条证据主张`));
      }
    }
    const dashboard = context.renderDashboard({
      ...context.selectSnapshot(payload, index),
      playback: { index, playing: false, finalHold: false },
    });
    assert.equal((dashboard.match(/data-dimension-id=/g) ?? []).length, 7);
    assert.doesNotMatch(dashboard, new RegExp(payload.dimensions[0].findings[0].text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("the single report reader is promoted into the topbar and follows delivery gating", () => {
  const { context } = createRuntime(freshHtml);
  const render = (index) => context.renderDashboard({
    ...context.selectSnapshot(payload, index),
    playback: { index, playing: false, finalHold: false },
  });

  for (let index = 0; index < 6; index++) {
    const html = render(index);
    const topbar = html.match(/<header class="topbar">([\s\S]*?)<\/header>/)?.[1] ?? "";
    assert.match(topbar, /data-report-action="read"[^>]*disabled/);
    assert.equal((html.match(/data-report-action="read"/g) ?? []).length, 1);
  }

  const delivered = render(6);
  const topbar = delivered.match(/<header class="topbar">([\s\S]*?)<\/header>/)?.[1] ?? "";
  const delivery = delivered.match(/<div class="delivery-card">([\s\S]*?)<\/div><\/div>/)?.[1] ?? "";
  assert.match(topbar, /class="control primary[^>]*data-report-action="read"/);
  assert.doesNotMatch(topbar, /data-report-action="read"[^>]*disabled/);
  assert.doesNotMatch(delivery, /data-report-action="read"/);
  assert.match(delivery, /data-report-action="report"/);
  assert.match(delivery, /data-report-action="citations"/);
  assert.ok(delivered.indexOf('data-report-action="read"') < delivered.indexOf('class="lifecycle-panel"'));
});

test("markdown renderer supports the safe report subset and escapes raw HTML first", () => {
  const { renderMarkdown } = createRuntime(freshHtml).context;
  const synthetic = [
    "# 一级标题",
    "## 二级标题",
    "### 三级标题",
    "",
    "普通 **加粗** 与 *斜体*，引用 [12]，脚注 [^safe] 和数字脚注 [^12]。<script>alert(1)</script>",
    "",
    "- 条目一",
    "- 条目二",
    "",
    "| 左列 | 右列 |",
    "|---|---:|",
    "| 甲 | 12 |",
    "",
    "[^safe]: 脚注定义",
    "[^12]: 数字脚注定义",
  ].join("\n");
  const html = renderMarkdown(synthetic);
  for (const pattern of [/<h1>一级标题<\/h1>/, /<h2>二级标题<\/h2>/, /<h3>三级标题<\/h3>/, /<p>普通/, /<strong>加粗<\/strong>/, /<em>斜体<\/em>/, /<ul>/, /<li>条目一<\/li>/, /class="table-scroll"/, /<table>/, /text-align:right/, /class="citation-token"/, /href="#footnote-safe"/, /id="footnote-safe"/]) {
    assert.match(html, pattern);
  }
  assert.doesNotMatch(html, /<script\b/i);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  const numericFootnote = html.match(/<sup class="footnote-ref"><a href="#footnote-12"[\s\S]*?<\/sup>/)?.[0] ?? "";
  assert.match(numericFootnote, /数字脚注|\[12\]/);
  assert.doesNotMatch(numericFootnote, /citation-token/);
  assert.equal((html.match(/class="citation-token"[^>]*aria-label="引用 12"/g) ?? []).length, 1);
  assert.match(html, /id="footnote-12">数字脚注定义<\/li>/);

  const report = renderMarkdown(payload.reportMarkdown);
  assert.match(report, /^<h1>中国九阶层实际收入与财务状况：中产人数、特征与财力<\/h1>/);
  assert.match(report, /<ul>[\s\S]*全国官方可直接观测的是调查户收入五等份/);
  assert.match(report, /<div class="table-scroll"[\s\S]*<table>[\s\S]*<th/);
  assert.match(report, /<strong>中国中产没有脱离口径的单一人数答案<\/strong>/);
  assert.match(report, /class="citation-token"[^>]*>\[1\]<\/sup>/);
});

test("malformed pipe tables preserve escaped content without partial table rendering", () => {
  const { renderMarkdown } = createRuntime(freshHtml).context;
  for (const [markdown, preserved] of [
    ["| A | B | C |\n|---|---|\n| one | two | three |", "three"],
    ["| A | B |\n|---|---|\n| one | two | <script>EXTRA</script> |", "&lt;script&gt;EXTRA&lt;/script&gt;"],
  ]) {
    const html = renderMarkdown(markdown);
    assert.doesNotMatch(html, /<table\b|class="table-scroll"/);
    assert.doesNotMatch(html, /text-align:undefined/);
    assert.doesNotMatch(html, /<script\b/);
    assert.match(html, new RegExp(preserved));
    assert.match(html, /\|/);
  }
});

test("dialog shells and controllers provide native and fallback modal accessibility", () => {
  assert.match(freshHtml, /<dialog id="dimension-dialog"[^>]*aria-labelledby="dimension-dialog-title"[^>]*aria-describedby="dimension-dialog-description"/);
  assert.match(freshHtml, /id="dimension-dialog-title"/);
  assert.match(freshHtml, /id="dimension-dialog-description"/);
  assert.match(freshHtml, /<dialog id="report-dialog"[^>]*aria-labelledby="report-dialog-title"[^>]*aria-describedby="report-dialog-description"/);
  assert.match(freshHtml, /id="report-dialog-title"/);
  assert.match(freshHtml, /id="report-dialog-description"/);

  const runtime = createRuntime(freshHtml);
  runtime.context.bootstrap();
  runtime.controls.stages[6].click();
  const reportTrigger = runtime.reportActions.read;
  reportTrigger.focus();
  reportTrigger.click();
  const reportDialog = runtime.byId["report-dialog"];
  assert.equal(reportDialog.open, true);
  assert.equal(reportDialog.getAttribute("aria-hidden"), "false");
  assert.match(runtime.byId["report-dialog-content"].innerHTML, /^<h1>/);
  assert.ok(runtime.byId["report-dialog-content"].focusCount > 0, "report viewer receives focus");

  const reportFocusables = reportDialog.focusables;
  runtime.document.activeElement = reportFocusables.at(-1);
  runtime.document.dispatchEvent({ type: "keydown", key: "Tab", shiftKey: false, preventDefault() { this.prevented = true; } });
  assert.ok(reportFocusables[0].focusCount > 0, "Tab wraps to first focusable");
  runtime.document.activeElement = reportFocusables[0];
  runtime.document.dispatchEvent({ type: "keydown", key: "Tab", shiftKey: true, preventDefault() { this.prevented = true; } });
  assert.ok(reportFocusables.at(-1).focusCount > 0, "Shift+Tab wraps to last focusable");

  runtime.document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });
  assert.equal(reportDialog.open, false);
  assert.equal(reportTrigger.focused, true, "report Escape restores its trigger");
  reportTrigger.click();
  runtime.dimensionTriggers[0].click();
  assert.equal(runtime.byId["dimension-dialog"].open, true);
  assert.equal(reportDialog.open, false, "opening one dialog closes the other");
  const dimensionTrigger = runtime.dimensionTriggers[0];
  runtime.document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });
  assert.equal(runtime.byId["dimension-dialog"].open, false);
  assert.equal(dimensionTrigger.focused, true, "Escape restores trigger focus");
  reportTrigger.click();
  reportDialog.dispatchEvent({ type: "click", target: reportDialog });
  assert.equal(reportDialog.open, false, "backdrop closes the report dialog");
  assert.equal(reportTrigger.focused, true);

  const fallback = createRuntime(freshHtml);
  const fallbackDialog = fallback.byId["dimension-dialog"];
  delete fallbackDialog.showModal;
  delete fallbackDialog.close;
  const fallbackTrigger = createElement({
    getAttribute(name) { return name === "data-dimension-id" ? "d1" : null; },
    focus() { this.focused = true; },
  });
  const controller = fallback.context.createDialogController(fallbackDialog, { initialFocus: () => fallbackDialog.focusables[0] });
  controller.open(fallbackTrigger);
  assert.equal(fallbackDialog.getAttribute("role"), "dialog");
  assert.equal(fallbackDialog.getAttribute("aria-modal"), "true");
  assert.equal(fallbackDialog.getAttribute("aria-hidden"), "false");
  assert.notEqual(fallbackDialog.getAttribute("open"), null);
  fallbackDialog.dispatchEvent({ type: "click", target: fallbackDialog });
  assert.equal(fallbackDialog.getAttribute("aria-hidden"), "true");
  assert.equal(fallbackTrigger.focused, true);
});

test("dimension dialog restores focus to the new trigger generation after a playback tick", () => {
  const runtime = createRuntime(freshHtml);
  runtime.context.bootstrap();
  runtime.controls.stages[3].click();
  runtime.controls.play.click();
  const timer = runtime.timerCalls.at(-1);
  const oldTrigger = runtime.dimensionTriggers[0];
  oldTrigger.focus();
  oldTrigger.click();
  assert.equal(runtime.byId["dimension-dialog"].open, true);
  const oldFocusCount = oldTrigger.focusCount;

  timer.callback();
  const replacement = runtime.dimensionTriggers[0];
  assert.notEqual(replacement, oldTrigger);
  assert.equal(oldTrigger.isConnected, false);
  assert.equal(runtime.byId["dimension-dialog"].open, true, "tick keeps the drawer open");
  runtime.document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });

  assert.equal(runtime.document.activeElement, replacement);
  assert.equal(replacement.focusCount, 1);
  assert.equal(oldTrigger.focusCount, oldFocusCount, "detached opener is never refocused");
});

test("report dialog restores focus to the new read trigger after the final-hold tick", () => {
  const runtime = createRuntime(freshHtml);
  runtime.context.bootstrap();
  runtime.controls.play.click();
  const timer = runtime.timerCalls[0];
  for (let tick = 0; tick < 6; tick++) timer.callback();
  const oldTrigger = runtime.reportActions.read;
  oldTrigger.focus();
  oldTrigger.click();
  const oldFocusCount = oldTrigger.focusCount;

  timer.callback();
  const replacement = runtime.reportActions.read;
  assert.notEqual(replacement, oldTrigger);
  assert.equal(oldTrigger.isConnected, false);
  assert.equal(runtime.byId["report-dialog"].open, true, "final tick keeps the viewer open");
  runtime.document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });

  assert.equal(runtime.document.activeElement, replacement);
  assert.equal(replacement.focusCount, 1);
  assert.equal(oldTrigger.focusCount, oldFocusCount, "detached read trigger is never refocused");
});

test("dialog focus restoration falls back to the current heading for unavailable or unsafe triggers", () => {
  const disabled = createRuntime(freshHtml);
  disabled.context.bootstrap();
  disabled.controls.play.click();
  const timer = disabled.timerCalls[0];
  for (let tick = 0; tick < 6; tick++) timer.callback();
  const oldRead = disabled.reportActions.read;
  oldRead.focus();
  oldRead.click();
  timer.callback();
  disabled.reportActions.read.disabled = true;
  disabled.document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });
  assert.equal(disabled.document.activeElement, disabled.heading);

  const absent = createRuntime(freshHtml);
  absent.context.bootstrap();
  absent.controls.play.click();
  const absentTimer = absent.timerCalls[0];
  for (let tick = 0; tick < 6; tick++) absentTimer.callback();
  absent.reportActions.read.focus();
  absent.reportActions.read.click();
  absentTimer.callback();
  delete absent.reportActions.read;
  absent.document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });
  assert.equal(absent.document.activeElement, absent.heading);

  for (const unsafeTrigger of [
    createElement({ getAttribute(name) { return name === "data-report-action" ? "report" : null; } }),
    createElement({ getAttribute(name) { return name === "data-dimension-id" ? 'd1\"] *' : null; } }),
  ]) {
    const runtime = createRuntime(freshHtml);
    const controller = runtime.context.createDialogController(runtime.byId["dimension-dialog"]);
    controller.open(unsafeTrigger);
    controller.close();
    assert.equal(unsafeTrigger.focused, false, "unsafe selector source is not restored");
    assert.equal(runtime.document.activeElement, runtime.heading);
  }
});

test("delivery actions are inert before stage seven and download exact archive bytes", () => {
  const runtime = createRuntime(freshHtml);
  runtime.context.bootstrap();
  for (let index = 0; index < 6; index++) {
    runtime.controls.stages[index].click();
    for (const action of Object.values(runtime.reportActions)) action.click();
  }
  assert.equal(runtime.blobs.length, 0);
  assert.equal(runtime.byId["report-dialog"].open, false);

  runtime.controls.stages[6].click();
  runtime.reportActions.report.click();
  runtime.reportActions.citations.click();
  assert.equal(runtime.blobs.length, 2);
  assert.deepEqual(plain(runtime.blobs.map((blob) => blob.parts)), [[payload.reportMarkdown], [payload.citationsJson]]);
  assert.deepEqual(runtime.blobs.map((blob) => blob.type), ["text/markdown;charset=utf-8", "application/json;charset=utf-8"]);
  assert.deepEqual(runtime.anchors.map((anchor) => anchor.download), ["report.md", "citations.json"]);
  assert.ok(runtime.anchors.every((anchor) => anchor.clicked));
  assert.deepEqual(runtime.anchors.map((anchor) => anchor.href), runtime.objectUrls.map((entry) => entry.url));
  assert.deepEqual(runtime.revokedUrls, runtime.objectUrls.map((entry) => entry.url));
});

test("download click failures propagate after revoking the created object URL", () => {
  const failure = new Error("download click failed");
  const runtime = createRuntime(freshHtml, { anchorClickError: failure });
  runtime.context.bootstrap();
  runtime.controls.stages[6].click();

  assert.throws(() => runtime.reportActions.report.click(), /download click failed/);
  assert.equal(runtime.objectUrls.length, 1);
  assert.deepEqual(runtime.revokedUrls, [runtime.objectUrls[0].url]);
  assert.equal(runtime.anchors[0].download, "report.md");
  assert.equal(runtime.anchors[0].clicked, true);
});

test("generated dashboard and dialogs expose safe visible copy and responsive accessibility CSS", () => {
  const { context } = createRuntime(freshHtml);
  const visible = [];
  for (let index = 0; index < 7; index++) {
    visible.push(context.renderDashboard({
      ...context.selectSnapshot(payload, index),
      playback: { index, playing: false, finalHold: false },
    }));
    for (const dimension of payload.dimensions) visible.push(context.renderDimensionDialog(payload, dimension.id, index));
  }
  const visibleCopy = visible.join(" ").replace(/<[^>]+>/g, " ");
  assert.doesNotMatch(visibleCopy, /实时同步|刚刚|当前更新时间|validator|review|perspective|supplement|stitcher|render|agent|schema|dispatch/i);
  assert.doesNotMatch(visibleCopy, /report\.html/i);

  const css = freshHtml.match(/<style>([\s\S]*?)<\/style>/i)?.[1] ?? "";
  assert.match(freshHtml, /role="progressbar"[^>]*aria-valuemin="0"[^>]*aria-valuemax="100"[^>]*aria-valuenow=/);
  assert.match(freshHtml, /id="announcement"[^>]*role="status"[^>]*aria-live="polite"/);
  assert.match(css, /(?:html|body|\.page-shell)[^{]*\{[^}]*overflow-x:\s*(?:hidden|clip)/s);
  assert.match(css, /\.dimension-dialog[^}]*position:\s*fixed[^}]*right:\s*0/s);
  assert.match(css, /\.topbar-layout[^}]*display:\s*flex[^}]*justify-content:\s*space-between/s);
  assert.match(css, /\.dialog-body[^}]*min-width:\s*0/s);
  assert.match(css, /\.report-viewer[^}]*width:\s*100%/s);
  assert.match(css, /dialog\[role="dialog"\][^}]*width:\s*100vw[^}]*height:\s*100dvh[^}]*background:/s);
  assert.match(css, /\.dimension-dialog\[role="dialog"\][\s\S]*?\.dialog-surface[^}]*width:\s*min\(580px,\s*100%\)[^}]*margin-left:\s*auto/s);
  assert.match(css, /\.table-scroll[^}]*overflow-x:\s*auto/s);
  assert.match(css, /@media\s*\(max-width:\s*780px\)[\s\S]*\.dialog-surface[^}]*width:\s*100%[^}]*height:\s*100%/s);
  assert.match(css, /@media\s*\(max-width:\s*780px\)[\s\S]*\.lifecycle[^}]*grid-template-columns:\s*1fr/s);
  assert.match(css, /@media\s*\(max-width:\s*780px\)[\s\S]*\.work-layout[^}]*grid-template-columns:\s*1fr/s);
  assert.match(css, /@media\s*\(max-width:\s*780px\)[\s\S]*\.metrics[^}]*grid-template-columns:\s*1fr/s);
  assert.match(css, /@media\s*\(max-width:\s*780px\)[\s\S]*\.topbar-layout[^}]*flex-direction:\s*column/s);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*animation(?:-duration)?:/s);
  const staticVisibleCopy = freshHtml
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ");
  assert.doesNotMatch(staticVisibleCopy, /实时同步|刚刚|当前更新时间|validator|review|perspective|supplement|stitcher|render|agent|schema|dispatch|report\.html/i);
});
