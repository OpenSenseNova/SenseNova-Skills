import assert from 'node:assert/strict';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

import { extractPages } from '../lib/dom_extractor.mjs';
import { buildEchartsElements } from '../lib/pptx_builder.mjs';

const fixturePath = fileURLToPath(new URL('./fixtures/echarts-fallback.html', import.meta.url));

test('injects bundled ECharts and captures each chart host', async () => {
  const [result] = await extractPages([fixturePath]);

  assert.ok(result.ir, result.error || 'expected extracted IR');
  const charts = result.ir._chartOptions || {};
  assert.deepEqual(Object.keys(charts).sort(), ['fallback-bar', 'fallback-heatmap']);
  assert.equal(charts['fallback-bar'].option.series[0].type, 'bar');
  assert.equal(charts['fallback-heatmap'].option.series[0].type, 'heatmap');
  assert.match(charts['fallback-bar'].pngData, /^data:image\/png;base64,/);
  assert.match(charts['fallback-heatmap'].pngData, /^data:image\/png;base64,/);
});

test('keeps native charts first and rasterizes only unsupported chart types', () => {
  const node = {
    id: 'chart-host',
    bounds: { x: 100, y: 120, w: 500, h: 300 },
  };
  const pngData = 'data:image/png;base64,ZmFrZQ==';
  const barEntry = {
    pngData,
    option: {
      xAxis: [{ type: 'category', data: ['A', 'B'] }],
      yAxis: [{ type: 'value' }],
      series: [{ type: 'bar', data: [12, 20] }],
    },
  };
  const heatmapEntry = {
    pngData,
    option: {
      xAxis: [{ type: 'category', data: ['2025', '2026'] }],
      yAxis: [{ type: 'category', data: ['Alpha', 'Beta'] }],
      series: [{ type: 'heatmap', data: [[0, 0, 2], [1, 1, 10]] }],
    },
  };

  const nativeResult = buildEchartsElements(node, barEntry, { bar: 'bar' });
  assert.equal(nativeResult.handled, true);
  assert.equal(nativeResult.elements[0].type, 'chart');

  const fallbackResult = buildEchartsElements(node, heatmapEntry, { bar: 'bar' });
  assert.equal(fallbackResult.handled, true);
  assert.equal(fallbackResult.elements[0].type, 'image');
  assert.equal(fallbackResult.elements[0].data.data, pngData);
});
