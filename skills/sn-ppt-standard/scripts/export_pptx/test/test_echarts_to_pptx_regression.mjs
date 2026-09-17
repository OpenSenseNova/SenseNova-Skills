import assert from 'node:assert/strict';
import test from 'node:test';

import { echartsOptionToPptx } from '../lib/echarts_to_pptx.mjs';

const ChartType = { bar: 'bar' };

test('maps horizontal bar axis styles by category/value semantics', () => {
  const option = {
    legend: [{ show: true, data: [] }],
    xAxis: [{
      type: 'value',
      axisLabel: { show: false, color: '#111111' },
      axisLine: { show: false, lineStyle: { color: '#222222' } },
      splitLine: { show: false, lineStyle: { color: '#333333' } },
    }],
    yAxis: [{
      type: 'category',
      data: ['美洲', '欧洲'],
      axisLabel: { show: true, color: '#f2ede4' },
      axisLine: { show: false, lineStyle: { color: '#444444' } },
      splitLine: { show: false, lineStyle: { color: '#555555' } },
    }],
    series: [{
      type: 'bar',
      data: [
        { value: 585, itemStyle: { color: '#7a8b6e' } },
        { value: 382, itemStyle: { color: '#7a8b6e' } },
      ],
    }],
  };

  const mapped = echartsOptionToPptx(option, ChartType);

  assert.equal(mapped.options.barDir, 'bar');
  assert.equal(mapped.options.catAxisLabelColor, 'F2EDE4');
  assert.equal(mapped.options.valAxisLabelPos, 'none');
  assert.equal(mapped.options.catAxisLineShow, false);
  assert.equal(mapped.options.valAxisLineShow, false);
  assert.deepEqual(mapped.options.catGridLine, { style: 'none' });
  assert.deepEqual(mapped.options.valGridLine, { style: 'none' });
  assert.equal(mapped.options.showLegend, false);
});

test('uses a uniform data-item color as the series color', () => {
  const option = {
    color: ['#5470c6', '#91cc75'],
    legend: [{ show: true, data: ['2024 秋季', '2025 秋季'] }],
    xAxis: [{ type: 'category', data: ['美洲', '欧洲'] }],
    yAxis: [{ type: 'value' }],
    series: [
      {
        name: '2024 秋季',
        type: 'bar',
        itemStyle: { color: '#7a8b6e' },
        data: [526, 339],
      },
      {
        name: '2025 秋季',
        type: 'bar',
        data: [
          { value: 585, itemStyle: { color: '#c4452a' } },
          { value: 382, itemStyle: { color: '#c4452a' } },
        ],
      },
    ],
  };

  const mapped = echartsOptionToPptx(option, ChartType);

  assert.deepEqual(mapped.options.chartColors, ['7A8B6E', 'C4452A']);
  assert.equal(mapped.options.showLegend, true);
});
