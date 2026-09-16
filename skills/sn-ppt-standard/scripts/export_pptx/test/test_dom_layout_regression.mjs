import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright';
import { extractPage } from '../lib/dom_extractor.mjs';

const fixture = fileURLToPath(new URL('./fixtures/dom-layout-regression.html', import.meta.url));
let browser;
let ir;

function findNode(node, predicate) {
  if (!node || typeof node !== 'object') return null;
  if (predicate(node)) return node;
  for (const child of node.children || []) {
    const found = findNode(child, predicate);
    if (found) return found;
  }
  return null;
}

before(async () => {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  ir = await extractPage(page, fixture);
});

after(async () => {
  await browser?.close();
});

test('preserves list-style:none rows as positioned child elements', () => {
  const list = findNode(ir.ct, node => node.className === 'pairs');
  assert.ok(list);
  assert.equal(list.listData, undefined);
  assert.equal(list.children[0].tag, 'LI');
  assert.deepEqual(list.children[0].children.map(child => child.text), [
    '定义',
    '业主支付固定服务费，盈亏由物业自负',
  ]);
});

test('keeps adjacent inline spans in one rich-text box', () => {
  const foot = findNode(ir.ct, node => node.className === 'foot');
  assert.ok(foot);
  assert.deepEqual(foot.textRuns.map(run => run.text), [
    '人工 40-60% ',
    '含工资、五险一金、福利',
  ]);
  assert.equal(foot.children.length, 0);
});
