import assert from 'node:assert/strict';
import test from 'node:test';

import { flattenIRToElements } from '../lib/pptx_builder.mjs';
import { setCanvasWidth } from '../lib/style_parser.mjs';

test('keeps an off-center transparent radial overlay as a gradient image', () => {
  setCanvasWidth(1600);
  const elements = flattenIRToElements({
    tag: 'DIV',
    bounds: { x: 1420, y: 740, w: 180, h: 160 },
    styles: {
      backgroundColor: 'rgba(0, 0, 0, 0)',
      backgroundImage: 'radial-gradient(at 100% 100%, color(srgb 0.960784 0.945098 0.92549 / 0.95) 0%, rgba(0, 0, 0, 0) 100%)',
      borderRadius: '0px',
      boxShadow: 'none',
      borderTopStyle: 'none',
      borderRightStyle: 'none',
      borderBottomStyle: 'none',
      borderLeftStyle: 'none',
      opacity: '1',
    },
    children: [],
  });

  assert.equal(elements.some(element => element.type === 'shape'), false);
  const image = elements.find(element => element.type === 'image');
  assert.ok(image);
  assert.match(image.data.data, /^data:image\/svg\+xml;base64,/);
});
