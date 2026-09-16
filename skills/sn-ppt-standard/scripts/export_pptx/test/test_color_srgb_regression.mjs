import assert from 'node:assert/strict';
import test from 'node:test';

import {
  cssColorToHex,
  extractCssAlpha,
  isTransparent,
  parseLinearGradient,
} from '../lib/style_parser.mjs';

test('parses Chromium color(srgb) values with alpha', () => {
  const color = 'color(srgb 0.960784 0.945098 0.92549 / 0.35)';
  assert.equal(cssColorToHex(color), 'F5F1EC');
  assert.equal(extractCssAlpha(color), 0.35);
  assert.equal(isTransparent('color(srgb 0 0 0 / 0)'), true);
});

test('retains color and alpha from color(srgb) gradient stops', () => {
  const gradient = parseLinearGradient(
    'linear-gradient(90deg, color(srgb 0 0 0 / 0) 0%, color(srgb 0.960784 0.945098 0.92549 / 0.88) 100%)',
  );

  assert.equal(gradient.stops[0].isTransparent, true);
  assert.equal(gradient.stops[1].color, 'F5F1EC');
  assert.equal(extractCssAlpha(gradient.stops[1].rawColor), 0.88);
});
