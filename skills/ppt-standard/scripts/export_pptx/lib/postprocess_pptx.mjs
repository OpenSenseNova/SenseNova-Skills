// 后处理 .pptx：解压 → 对 slide XML 应用注册的 token 替换 → 重打包。
// 用于实现 pptxgenjs 不直接支持的 OOXML 特性，例如：
//   - gradient fill（D 类）
//   - chart 中心标签 / custom-color override（C 类）
//   - clip-path → custGeom（H 类）
//
// 用法：
//   const handler = createGradientHandler();
//   const tok = handler.registerLinear({ angle: 90, stops: [...] });
//   shape.fill = { color: tok };
//   ...
//   await buildPptx(...);
//   await postprocessPptx(pptxPath, [handler]);

import JSZip from 'jszip';
import { readFile, writeFile } from 'node:fs/promises';

/**
 * Apply a list of handlers to a built .pptx file in-place.
 *
 * Each handler is an object with:
 *   - apply(xml: string, slideName: string): string
 *     Receives the slide XML, returns modified XML. May be called for
 *     every slide (handlers must be idempotent and safe on slides that
 *     don't contain their tokens).
 *
 * Only files under `ppt/slides/` are passed through handlers.
 *
 * @param {string} pptxPath
 * @param {Array<{apply: (xml: string, name: string) => string}>} handlers
 */
export async function postprocessPptx(pptxPath, handlers) {
  if (!handlers || handlers.length === 0) return;
  const buf = await readFile(pptxPath);
  const zip = await JSZip.loadAsync(buf);

  let modifiedAny = false;
  for (const name of Object.keys(zip.files)) {
    if (zip.files[name].dir) continue;
    if (!/^ppt\/slides\/slide\d+\.xml$/.test(name)) continue;
    const xml = await zip.files[name].async('string');
    let cur = xml;
    for (const h of handlers) {
      cur = h.apply(cur, name);
    }
    if (cur !== xml) {
      zip.file(name, cur);
      modifiedAny = true;
    }
  }

  if (!modifiedAny) return;

  const out = await zip.generateAsync({
    type: 'nodebuffer',
    compression: 'DEFLATE',
    mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  });
  await writeFile(pptxPath, out);
}

/**
 * Create a gradient-fill handler.
 *
 * Caller registers gradient definitions and gets back token strings to use
 * as `<a:srgbClr val="...">` placeholders. After buildPptx writes the file,
 * postprocessPptx with this handler swaps each `<a:solidFill><a:srgbClr val="TOKEN"/></a:solidFill>`
 * into a real `<a:gradFill>...</a:gradFill>` block.
 *
 * Token format:  ZZGRADxxx  (12 char, ASCII alnum, never collides with real
 * 6-hex colors written by pptxgenjs).
 */
export function createGradientHandler() {
  let counter = 0;
  // token → OOXML replacement (the full `<a:gradFill>...</a:gradFill>` block)
  const replacements = new Map();

  function nextToken() {
    counter++;
    // pptxgenjs validates color values as 6-digit hex.
    // Token format: `AB` + 4-hex counter. The leading `AB` is a sentinel
    // unlikely to occur as a deliberately-authored color (light pinkish
    // gray with 0xCD blue is rare in design palettes), and the 4 hex digits
    // give us 65536 distinct tokens per deck — far more than needed.
    if (counter > 0xFFFF) {
      throw new Error(`gradient handler exceeded 65536 unique tokens (counter=${counter})`);
    }
    return `AB${counter.toString(16).toUpperCase().padStart(4, '0')}`;
  }

  /**
   * Register a linear gradient.
   *
   * @param {{angle: number, stops: Array<{pos: number, color: string, alpha?: number}>}} spec
   *   - angle: CSS gradient angle in degrees (0 = top, 90 = right, etc.)
   *   - stops: array of stops with `pos` 0-100, `color` 6-hex, optional `alpha` 0-1
   * @returns {string} token to use as the placeholder color
   */
  function registerLinear(spec) {
    const tok = nextToken();
    // Convert CSS angle to OOXML <a:lin ang="..."> units.
    // CSS:    0deg = "to top",    90deg = "to right"
    // OOXML:  0    = "to right",  5400000 = "to bottom"  (units = 60000 * deg, clockwise from 3 o'clock)
    // CSS angle θ means gradient goes _to_ that direction; OOXML angle is direction-of-color-flow.
    // Mapping: ooxml = ((θ - 90 + 360) % 360) * 60000
    const ang = Math.round(((spec.angle - 90 + 360) % 360) * 60000);
    const gsList = spec.stops.map(s => {
      const posVal = Math.round((s.pos ?? 0) * 1000);
      const colorVal = (s.color || '000000').replace('#', '').toUpperCase();
      const alpha = s.alpha == null ? 1 : Math.max(0, Math.min(1, s.alpha));
      const alphaTag = alpha < 1 ? `<a:alpha val="${Math.round(alpha * 100000)}"/>` : '';
      return `<a:gs pos="${posVal}"><a:srgbClr val="${colorVal}">${alphaTag}</a:srgbClr></a:gs>`;
    }).join('');
    const ooxml = `<a:gradFill rotWithShape="1"><a:gsLst>${gsList}</a:gsLst><a:lin ang="${ang}" scaled="0"/></a:gradFill>`;
    replacements.set(tok, ooxml);
    return tok;
  }

  /**
   * Register a radial gradient.
   *
   * @param {{stops: Array<{pos: number, color: string, alpha?: number}>}} spec
   * @returns {string} token
   */
  function registerRadial(spec) {
    const tok = nextToken();
    const gsList = spec.stops.map(s => {
      const posVal = Math.round((s.pos ?? 0) * 1000);
      const colorVal = (s.color || '000000').replace('#', '').toUpperCase();
      const alpha = s.alpha == null ? 1 : Math.max(0, Math.min(1, s.alpha));
      const alphaTag = alpha < 1 ? `<a:alpha val="${Math.round(alpha * 100000)}"/>` : '';
      return `<a:gs pos="${posVal}"><a:srgbClr val="${colorVal}">${alphaTag}</a:srgbClr></a:gs>`;
    }).join('');
    const ooxml = `<a:gradFill rotWithShape="1"><a:gsLst>${gsList}</a:gsLst><a:path path="circle"><a:fillToRect l="50000" t="50000" r="50000" b="50000"/></a:path></a:gradFill>`;
    replacements.set(tok, ooxml);
    return tok;
  }

  /**
   * The handler hook for postprocessPptx.
   *
   * Looks for both shape fill `<a:solidFill><a:srgbClr val="TOKEN"/></a:solidFill>`
   * and slide background `<p:bgPr><a:solidFill><a:srgbClr val="TOKEN"/></a:solidFill>`,
   * replaces each with the registered gradient block.
   *
   * Important: `<a:solidFill>` may also appear in `<a:lnRef>`, line color,
   * text run color, etc. We deliberately look only at the entire solidFill
   * wrapping, so any match is a safe replacement (token is unique enough that
   * it can only have come from registerLinear/registerRadial).
   */
  function apply(xml /*, slideName */) {
    if (replacements.size === 0) return xml;
    let cur = xml;
    for (const [tok, ooxml] of replacements) {
      // Match `<a:solidFill><a:srgbClr val="TOKEN"/></a:solidFill>` or
      //       `<a:solidFill><a:srgbClr val="TOKEN"><...inner...></a:srgbClr></a:solidFill>`.
      // The srgbClr may carry inner alpha/lumMod tags but for our tokens
      // pptxgenjs doesn't add any (we never pass alpha to pptxgenjs for
      // gradient tokens — gradient alpha is encoded in our OOXML directly).
      const re = new RegExp(
        `<a:solidFill>\\s*<a:srgbClr val="${tok}"\\s*\\/>\\s*</a:solidFill>`,
        'g',
      );
      cur = cur.replace(re, ooxml);
    }
    return cur;
  }

  return { registerLinear, registerRadial, apply, _replacementsCount: () => replacements.size };
}
