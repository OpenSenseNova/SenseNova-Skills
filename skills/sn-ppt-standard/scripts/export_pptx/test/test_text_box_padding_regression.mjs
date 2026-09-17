import assert from 'node:assert/strict';
import test from 'node:test';

import { buildTextElement } from '../lib/pptx_builder.mjs';
import { setCanvasWidth } from '../lib/style_parser.mjs';

test('maps CSS padding to pptx margins in left-top-right-bottom order', () => {
  setCanvasWidth(1280);
  const element = buildTextElement({
    text: 'GOVERNMENT GUIDED',
    bounds: { x: 0, y: 0, w: 220, h: 28 },
    styles: {
      color: 'rgb(0, 0, 0)',
      fontSize: '14px',
      paddingTop: '3px',
      paddingRight: '10px',
      paddingBottom: '5px',
      paddingLeft: '7px',
    },
  });

  assert.deepEqual(element.options.margin, [3.9375, 1.6875, 5.625, 2.8125]);
});
