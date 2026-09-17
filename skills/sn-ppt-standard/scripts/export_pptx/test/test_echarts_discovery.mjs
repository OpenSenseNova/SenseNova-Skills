import assert from 'node:assert/strict';
import test from 'node:test';

import { discoverEchartsInstances } from '../lib/echarts_discovery.mjs';

test('discovers ECharts containers without requiring a chart_ id', () => {
  const named = {
    id: 'barChart',
    getBoundingClientRect: () => ({ left: 10, top: 20, width: 300, height: 180 }),
  };
  const legacy = {
    id: 'chart_1',
    getBoundingClientRect: () => ({ left: 30, top: 40, width: 320, height: 200 }),
  };
  const anonymous = {
    id: '',
    getBoundingClientRect: () => ({ left: 50, top: 60, width: 340, height: 220 }),
  };
  const instances = new Map([
    [named, { getOption: () => ({ series: [{ type: 'bar', data: [1] }] }) }],
    [legacy, { getOption: () => ({ series: [{ type: 'line', data: [2] }] }) }],
    [anonymous, { getOption: () => ({ series: [{ type: 'pie', data: [3] }] }) }],
  ]);
  const fakeDocument = {
    querySelectorAll(selector) {
      assert.equal(selector, '[_echarts_instance_], [id^="chart_"]');
      return [named, legacy, anonymous];
    },
    getElementById() {
      return null;
    },
  };
  const fakeEcharts = {
    getInstanceByDom(el) {
      return instances.get(el);
    },
  };

  const result = discoverEchartsInstances(fakeDocument, fakeEcharts);

  assert.deepEqual(Object.keys(result), ['barChart', 'chart_1', '__pptx_echart_1']);
  assert.equal(anonymous.id, '__pptx_echart_1');
  assert.deepEqual(result.barChart.bounds, { x: 10, y: 20, w: 300, h: 180 });
});
