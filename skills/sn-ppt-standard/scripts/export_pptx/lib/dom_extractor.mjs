/**
 * dom_extractor.mjs
 * 基于 Playwright 的 DOM 提取模块。
 * 将 HTML 幻灯片页面解析为中间表示（IR），供 PPTX builder 使用。
 */

import { chromium } from 'playwright';
import path from 'node:path';

// ---------------------------------------------------------------------------
// 浏览器端执行的 DOM 提取脚本
// 通过 page.evaluate() 注入到页面中运行
// ---------------------------------------------------------------------------

/**
 * 在浏览器中执行的提取函数（字符串形式注入）。
 * 不可引用外部模块或闭包变量。
 */
const BROWSER_EXTRACT_FN = () => {
  // CSS 属性列表（kebab-case），用于 getPropertyValue
  const CSS_PROPS = [
    'color', 'font-size', 'font-weight', 'font-family', 'font-style',
    'background-color', 'background-image',
    'border-radius', 'box-shadow',
    'border-top', 'border-right', 'border-bottom', 'border-left',
    'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
    'opacity', 'text-align', 'line-height', 'letter-spacing',
    'text-decoration', 'display', 'overflow',
    'object-fit', 'vertical-align',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'filter', 'backdrop-filter', 'text-shadow',
    '-webkit-background-clip', 'background-clip',
    '-webkit-text-fill-color',
    'transform',
    '-webkit-mask-image', 'mask-image',
    'word-break', 'overflow-wrap', 'white-space',
    'z-index', 'position',
    '-webkit-text-stroke', '-webkit-text-stroke-width', '-webkit-text-stroke-color',
  ];

  // kebab-case → camelCase 转换（用于返回对象的 key）
  function kebabToCamel(str) {
    return str.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
  }

  /**
   * 提取元素的计算样式，返回 camelCase key 的对象。
   * @param {Element} el
   * @returns {Object}
   */
  function extractStyles(el) {
    const cs = window.getComputedStyle(el);
    const styles = {};
    for (const prop of CSS_PROPS) {
      const val = cs.getPropertyValue(prop);
      if (val) {
        styles[kebabToCamel(prop)] = val;
      }
    }
    return styles;
  }

  /**
   * 提取元素的边界框（相对于 .wrapper 左上角）。
   * @param {Element} el
   * @param {DOMRect} wrapperRect
   * @returns {{x:number, y:number, w:number, h:number}}
   */
  function extractBounds(el, wrapperRect) {
    const r = el.getBoundingClientRect();
    // L-ii: 如果元素被 transform: rotate() 旋转，getBoundingClientRect 返回的是
    // axis-aligned bounding box（外接矩形），而不是元素真实矩形。pptxgenjs 的
    // shape rotate 是绕中心旋转 —— 我们要给它"未旋转矩形 + 旋转角"，否则位置错。
    // 用 offsetWidth/Height 拿元素真实尺寸（CSS 布局尺寸，未受 transform 影响），
    // 从 BB 中心反推未旋转矩形。
    const cs = window.getComputedStyle(el);
    const transform = cs.getPropertyValue('transform');
    if (transform && transform !== 'none' && /matrix|rotate/.test(transform)) {
      const offW = el.offsetWidth || r.width;
      const offH = el.offsetHeight || r.height;
      if (offW > 0 && offH > 0
          && (Math.abs(offW - r.width) > 1 || Math.abs(offH - r.height) > 1)) {
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        return {
          x: cx - offW / 2 - wrapperRect.left,
          y: cy - offH / 2 - wrapperRect.top,
          w: offW,
          h: offH,
        };
      }
    }
    return {
      x: r.left - wrapperRect.left,
      y: r.top - wrapperRect.top,
      w: r.width,
      h: r.height,
    };
  }

  /**
   * 提取表格数据。
   * @param {HTMLTableElement} table
   * @returns {Array<Array<{text:string, isHeader:boolean, colspan:number, rowspan:number, styles:Object}>>}
   */
  function extractTableData(table) {
    const rows = [];
    for (const tr of table.rows) {
      const cells = [];
      for (const cell of tr.cells) {
        cells.push({
          text: cell.innerText || '',
          isHeader: cell.tagName === 'TH',
          colspan: cell.colSpan || 1,
          rowspan: cell.rowSpan || 1,
          styles: extractStyles(cell),
        });
      }
      rows.push(cells);
    }
    return rows;
  }

  /**
   * 提取列表数据。
   * @param {HTMLUListElement|HTMLOListElement} listEl
   * @returns {Array<{text:string, styles:Object}>}
   */
  function extractListData(listEl) {
    const items = [];
    for (const li of listEl.querySelectorAll(':scope > li')) {
      // 提取 ::before 伪元素内容（如 ✓、★ 等自定义 bullet）
      let bulletChar = null;
      try {
        const beforeContent = window.getComputedStyle(li, '::before').getPropertyValue('content');
        // content 返回格式如 '"✓"' 或 'none'
        if (beforeContent && beforeContent !== 'none' && beforeContent !== 'normal') {
          const cleaned = beforeContent.replace(/^["']|["']$/g, '');
          if (cleaned && cleaned.length <= 3) {
            bulletChar = cleaned;
          }
        }
      } catch (e) { /* 忽略 */ }

      items.push({
        text: li.innerText || '',
        styles: extractStyles(li),
        bulletChar,
      });
    }
    return items;
  }

  /**
   * 检测元素的子节点中是否存在混合内容（文本节点 + 元素节点）。
   * @param {Element} el
   * @returns {boolean}
   */
  function hasMixedContent(el) {
    let hasText = false;
    let hasElement = false;
    for (const child of el.childNodes) {
      if (child.nodeType === 3 && child.textContent.trim()) {
        hasText = true;
      } else if (child.nodeType === 1) {
        hasElement = true;
      }
    }
    return hasText && hasElement;
  }

  /**
   * 元素自身是否带有独立装饰（背景色/边框/阴影/非零圆角配背景），
   * 应该作为独立 shape 输出而不是被合并到父节点的 textRuns 文本流里。
   *
   * 用于：父节点是混合内容时，装饰 inline 子元素（如 <span class="pill">01</span>）
   * 需要作为独立 IR 节点保留，让 flattenIRToElements 自然输出 shape+text 双图层。
   */
  /**
   * Inline computed CSS styles back into SVG element attributes so the SVG
   * renders correctly when extracted as standalone outerHTML.
   *
   * Rationale:
   *   - HTML often styles SVG via CSS (`.card-icon { stroke: white; fill: none }`)
   *   - outerHTML serializes the SVG markup without applying that CSS
   *   - When PowerPoint renders the embedded SVG, it has no CSS context, so
   *     unset fill/stroke fall back to defaults (black fill, no stroke), and
   *     the icon becomes a black blob.
   *   - The fix: walk every SVG descendant, read getComputedStyle, write
   *     fill/stroke/etc. as attributes on a clone, then serialize the clone.
   *
   * Also resolves `currentColor` (which getComputedStyle returns as the
   * actual `color` value) and any CSS variable references, since computed
   * style values are fully resolved.
   */
  function inlineSvgStyles(svgEl) {
    const SVG_PRESENTATION_ATTRS = [
      'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin',
      'stroke-dasharray', 'stroke-miterlimit',
      'opacity', 'fill-opacity', 'stroke-opacity',
    ];
    const clone = svgEl.cloneNode(true);
    const origNodes = [svgEl, ...svgEl.querySelectorAll('*')];
    const cloneNodes = [clone, ...clone.querySelectorAll('*')];
    if (origNodes.length !== cloneNodes.length) return svgEl.outerHTML;
    for (let i = 0; i < origNodes.length; i++) {
      const orig = origNodes[i];
      const target = cloneNodes[i];
      const cs = window.getComputedStyle(orig);
      for (const attr of SVG_PRESENTATION_ATTRS) {
        let val = cs.getPropertyValue(attr);
        if (!val || val === 'normal' || val === 'auto') continue;
        // Skip if attribute already explicitly set (HTML wins over computed)
        if (target.hasAttribute(attr)) continue;
        // SVG presentation attrs use unitless lengths (vs CSS px). Strip 'px'
        // suffix so PowerPoint's strict SVG parser accepts the value.
        if (/-(?:width|miterlimit|offset)$/.test(attr) || attr === 'stroke-dasharray') {
          val = val.replace(/(\d+(?:\.\d+)?)px/g, '$1');
        }
        target.setAttribute(attr, val);
      }
    }
    return clone.outerHTML;
  }

  function hasOwnDecoration(el) {
    const cs = window.getComputedStyle(el);
    const bg = cs.getPropertyValue('background-color');
    if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return true;
    const bgImg = cs.getPropertyValue('background-image');
    if (bgImg && bgImg !== 'none') return true;
    for (const dir of ['top', 'right', 'bottom', 'left']) {
      const w = parseFloat(cs.getPropertyValue(`border-${dir}-width`));
      const style = cs.getPropertyValue(`border-${dir}-style`);
      if (w > 0 && style && style !== 'none') return true;
    }
    const shadow = cs.getPropertyValue('box-shadow');
    if (shadow && shadow !== 'none') return true;
    return false;
  }

  /**
   * 提取混合内容的 textRuns 数组。
   * @param {Element} el
   * @returns {Array<{text:string, bold:boolean, italic:boolean, fontSize:string, color:string, fontFamily:string, underline:boolean}>}
   */
  function extractTextRuns(el) {
    const runs = [];

    function walk(node) {
      if (node.nodeType === 3) {
        // 纯文本节点：折叠空白（与浏览器行为一致）
        const raw = node.textContent.replace(/\s+/g, ' ');
        const text = raw.trim();
        if (text) {
          const parent = node.parentElement || el;
          const cs = window.getComputedStyle(parent);
          runs.push({
            text,
            bold: cs.getPropertyValue('font-weight') >= 600 || cs.getPropertyValue('font-weight') === 'bold',
            italic: cs.getPropertyValue('font-style') === 'italic',
            fontSize: cs.getPropertyValue('font-size'),
            color: cs.getPropertyValue('color'),
            fontFamily: cs.getPropertyValue('font-family'),
            // I-vi: 用 text-decoration-line（非继承）代替 text-decoration（继承），
// 避免父节点的 underline 误传给子文本 run（如 company-11th p2 黄色下划线 bug）
underline: cs.getPropertyValue('text-decoration-line').includes('underline'),
          });
        } else if (raw.includes(' ') && runs.length > 0) {
          // 纯空白文本节点（如 <span>def</span> <span>func</span> 之间的空格）
          // 在前一个 run 末尾追加空格，避免相邻单词粘连
          const lastRun = runs[runs.length - 1];
          if (lastRun && !lastRun.text.endsWith(' ') && !lastRun.isBlock) {
            lastRun.text += ' ';
          }
        }
      } else if (node.nodeType === 1) {
        // E-ii: <br> 哨兵 —— 显式换行符。pptxgenjs 看到 breakLine:true 的空 run 会换行。
        if (node.tagName === 'BR') {
          runs.push({ text: '', isBlock: true, fontSize: '16px', color: '#000', fontFamily: 'inherit', bold: false, italic: false, underline: false });
          return;
        }

        const cs = window.getComputedStyle(node);
        const display = cs.getPropertyValue('display');
        if (display === 'none') return;

        // 装饰子元素（自带 background/border/shadow）的文字仍保留在 textRuns 里——
        // 这样父文本框排版的水平空间和 HTML 一致。装饰子元素同时作为独立 IR child
        // 输出 shape+text，z-order 上由后输出的子节点覆盖父文本（见 extractNode 的
        // hasMixedContent 分支为它们追加 children）。
        //
        // R5 修复（Turn-2）：父 textRuns 中装饰子元素的文字渲染为父样式，但子 shape
        // 边界与父 textbox 字符位置存在像素级差异，导致父文字从子 shape 边缘漏出
        // 形成"重影"。对策：把装饰 run 的文字保留（保排版宽度），但 color 设为
        // 透明 → 父 textbox 只占位不渲染该段文字，子 textbox 是唯一实际显示。
        const isDecorated = hasOwnDecoration(node);

        const text = node.innerText || '';
        if (!text) return;

        const isBlock = ['block', 'flex', 'grid', 'table', 'list-item'].includes(display);

        runs.push({
          text,
          bold: cs.getPropertyValue('font-weight') >= 600 || cs.getPropertyValue('font-weight') === 'bold',
          italic: cs.getPropertyValue('font-style') === 'italic',
          fontSize: cs.getPropertyValue('font-size'),
          // R5: 装饰子元素的文字在父 textbox 中用透明色占位（不实际渲染），
          // 真正的文字由它独立的 IR child shape+textbox 显示。
          color: isDecorated ? 'rgba(0, 0, 0, 0)' : cs.getPropertyValue('color'),
          fontFamily: cs.getPropertyValue('font-family'),
          // I-vi: 用 text-decoration-line（非继承）代替 text-decoration（继承），
          // 避免父节点的 underline 误传给子文本 run（如 company-11th p2 黄色下划线 bug）
          underline: cs.getPropertyValue('text-decoration-line').includes('underline'),
          isBlock,
        });
      }
    }

    for (const child of el.childNodes) {
      walk(child);
    }

    return runs;
  }

  /**
   * 判断节点是否应跳过。
   * @param {Element} el
   * @param {CSSStyleDeclaration} cs
   * @returns {boolean}
   */
  function shouldSkip(el, cs) {
    if (el.nodeType !== 1) return true;
    if (cs.getPropertyValue('display') === 'none') return true;
    // M-i: visibility:hidden / opacity:0 也跳过，避免凭空多出空圆角等
    if (cs.getPropertyValue('visibility') === 'hidden') return true;
    const op = cs.getPropertyValue('opacity');
    if (op === '0') return true;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0 && el.children.length === 0) return true;
    return false;
  }

  /**
   * 提取元素的 ::before / ::after 伪元素。
   * 仅当伪元素有可见内容（背景、尺寸）时提取为合成 IR 节点。
   * @param {Element} el
   * @param {DOMRect} wrapperRect
   * @returns {Array<Object>}
   */
  function extractPseudoElements(el, wrapperRect) {
    const pseudos = [];
    for (const pseudo of ['::before', '::after']) {
      try {
        const cs = window.getComputedStyle(el, pseudo);
        const content = cs.getPropertyValue('content');
        // 跳过 content: none / normal 的伪元素
        // 注意：content: '' (空字符串，computed 值为 '""') 是合法的，不跳过
        if (content === 'none' || content === 'normal') continue;

        const display = cs.getPropertyValue('display');
        if (display === 'none') continue;

        // 检查伪元素是否有可见视觉效果（背景色、背景图、边框等）
        const bgColor = cs.getPropertyValue('background-color');
        const bgImage = cs.getPropertyValue('background-image');
        const hasBg = (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent');
        const hasBgImg = (bgImage && bgImage !== 'none');
        if (!hasBg && !hasBgImg) continue;

        // 伪元素的尺寸和位置：
        // 通常是 position:absolute + width:100% + height:100%（覆盖父元素）
        // 无法对伪元素调用 getBoundingClientRect，使用父元素的 bounds
        const position = cs.getPropertyValue('position');
        let bounds;
        if (position === 'absolute' || position === 'fixed') {
          // 绝对定位伪元素：解析 top/left/width/height，回退到父元素的 bounds
          const parentRect = el.getBoundingClientRect();
          const wRect = wrapperRect;
          const top = parseFloat(cs.getPropertyValue('top')) || 0;
          const left = parseFloat(cs.getPropertyValue('left')) || 0;
          const width = cs.getPropertyValue('width');
          const height = cs.getPropertyValue('height');
          const w = (width === 'auto' || width === '100%') ? parentRect.width : (parseFloat(width) || parentRect.width);
          const h = (height === 'auto' || height === '100%') ? parentRect.height : (parseFloat(height) || parentRect.height);
          bounds = {
            x: parentRect.left - wRect.left + left,
            y: parentRect.top - wRect.top + top,
            w,
            h,
          };
        } else {
          // In-flow (display:block/inline/inline-block) pseudo. We CANNOT use
          // the parent's full bounds here — that paints the pseudo's background
          // on top of the parent's text content (e.g. a `::before` dot with a
          // solid --accent fill ends up covering the whole `<div class="head">产能占用</div>`
          // and the title text disappears in PPTX).
          //
          // Only draw the pseudo if CSS gives it an explicit, small pixel size
          // we can safely place at the parent's origin. If size is auto/100%
          // we can't know its real bounds (no direct getBoundingClientRect on
          // pseudos), so skip it — losing a decorative flourish is a much
          // smaller loss than overwriting real content.
          const parentRect = el.getBoundingClientRect();
          const wRect = wrapperRect;
          const widthStr = cs.getPropertyValue('width');
          const heightStr = cs.getPropertyValue('height');
          const w = parseFloat(widthStr);
          const h = parseFloat(heightStr);
          const finite = Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0;
          const small = finite && w < parentRect.width * 0.9 && h < parentRect.height * 0.9;

          // H-i: 防御 —— 若伪元素 background 不透明（alpha > 0.5）并打算占满
          // 父元素 90%+，跳过。否则会盖住父元素的真实文字内容（前任血泪史）。
          let bgAlpha = 1;
          const bgRgba = bgColor.match(/rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\s*\)/);
          if (bgRgba) bgAlpha = parseFloat(bgRgba[1]);
          const wouldCoverParent = finite && w >= parentRect.width * 0.9 && h >= parentRect.height * 0.9 && bgAlpha > 0.5;
          if (wouldCoverParent) continue;

          if (small) {
            // 原路径：小尺寸的 inline 装饰
            const parentPadL = parseFloat(cs.getPropertyValue('padding-left')) || 0;
            const parentPadT = parseFloat(cs.getPropertyValue('padding-top')) || 0;
            const parentDisplay = cs.getPropertyValue('display');
            const align = cs.getPropertyValue('align-items');
            let bx = parentRect.left - wRect.left + parentPadL;
            let by = parentRect.top - wRect.top + parentPadT;
            if (parentDisplay.includes('flex') && align === 'center') {
              by = parentRect.top - wRect.top + (parentRect.height - h) / 2;
            }
            bounds = { x: bx, y: by, w, h };
          } else {
            // H-i 放宽：水平 accent-strip（卡片顶部/底部细长色条）
            // 条件：width 100% + height < 父高 30%
            const widthIsFull = widthStr === '100%'
              || (Number.isFinite(parseFloat(widthStr)) && parseFloat(widthStr) >= parentRect.width * 0.95);
            const heightIsShort = Number.isFinite(parseFloat(heightStr))
              && parseFloat(heightStr) > 0 && parseFloat(heightStr) < parentRect.height * 0.3;

            // H-i 放宽：垂直 connector-line（左/右边细长线，timeline 连接器）
            // 条件：height 100% + width < 父宽 30%
            const heightIsFull = heightStr === '100%'
              || (Number.isFinite(parseFloat(heightStr)) && parseFloat(heightStr) >= parentRect.height * 0.95);
            const widthIsShort = Number.isFinite(parseFloat(widthStr))
              && parseFloat(widthStr) > 0 && parseFloat(widthStr) < parentRect.width * 0.3;

            const isBefore = pseudo === '::before';
            if (widthIsFull && heightIsShort) {
              const stripH = parseFloat(heightStr);
              const stripY = isBefore
                ? parentRect.top - wRect.top
                : parentRect.top - wRect.top + parentRect.height - stripH;
              bounds = {
                x: parentRect.left - wRect.left,
                y: stripY,
                w: parentRect.width,
                h: stripH,
              };
            } else if (heightIsFull && widthIsShort) {
              const stripW = parseFloat(widthStr);
              const stripX = isBefore
                ? parentRect.left - wRect.left
                : parentRect.left - wRect.left + parentRect.width - stripW;
              bounds = {
                x: stripX,
                y: parentRect.top - wRect.top,
                w: stripW,
                h: parentRect.height,
              };
            } else {
              continue;
            }
          }
        }

        // 构建合成 styles 对象
        const styles = {};
        for (const prop of CSS_PROPS) {
          const val = cs.getPropertyValue(prop);
          if (val) {
            styles[kebabToCamel(prop)] = val;
          }
        }

        pseudos.push({
          tag: 'DIV',
          id: undefined,
          className: `_pseudo_${pseudo.replace('::', '')}`,
          bounds,
          styles,
          children: [],
          _isPseudo: true,
        });
      } catch (e) { /* 忽略 */ }
    }
    return pseudos;
  }

  /**
   * 递归提取单个 DOM 元素为 IR 节点。
   * @param {Element} el
   * @param {DOMRect} wrapperRect
   * @returns {Object|null}
   */
  function extractNode(el, wrapperRect) {
    if (el.nodeType !== 1) return null;

    const cs = window.getComputedStyle(el);
    if (shouldSkip(el, cs)) return null;

    const tag = el.tagName.toUpperCase();
    const node = {
      tag,
      id: el.id || undefined,
      className: el.className || undefined,
      bounds: extractBounds(el, wrapperRect),
      styles: extractStyles(el),
      children: [],
    };

    // --- 特殊元素处理 ---

    // IMG: 提取 src 和自然尺寸
    if (tag === 'IMG') {
      node.src = el.getAttribute('src') || undefined;
      node.naturalWidth = el.naturalWidth;
      node.naturalHeight = el.naturalHeight;
      return node;
    }

    // SVG: 提取 outerHTML，不递归子节点
    // 关键：HTML 里的 SVG 经常依赖 CSS 设置 fill/stroke（如 .icon { stroke: #fff }），
    // 单纯 outerHTML 不带 CSS 样式 → PowerPoint 渲染时 fill/stroke 缺失，
    // 图标变成黑方块。这里把 computed style 内联回 SVG 各元素的属性。
    if (tag === 'SVG') {
      node.svgContent = inlineSvgStyles(el);
      return node;
    }

    // TABLE: 提取 tableData，不递归子节点
    if (tag === 'TABLE') {
      node.tableData = extractTableData(el);
      return node;
    }

    // UL/OL: 提取 listData，不递归子节点
    if (tag === 'UL' || tag === 'OL') {
      node.listData = extractListData(el);
      node.listType = tag === 'OL' ? 'ordered' : 'unordered';
      // F-ii: 若 list bounds 被 flex 容器折叠（h < 4px），用 listData 估算高度。
      // 否则 builder 会把列表节点当 0 高度跳过，导致整个项目符号列表消失。
      if (node.bounds.h < 4 && node.listData.length > 0) {
        const firstFs = parseFloat(node.listData[0].styles?.fontSize) || 16;
        node.bounds = { ...node.bounds, h: node.listData.length * firstFs * 1.5 };
      }
      return node;
    }

    // 混合内容 → textRuns
    if (hasMixedContent(el)) {
      node.textRuns = extractTextRuns(el);
      // 装饰子元素（如 <span class="pill" style="background:yellow">01</span>）
      // 由独立 IR 节点处理，这样能输出独立 shape+text 双图层（pill 背景才不会丢）。
      // 它们的文字在 textRuns 中已被跳过（见 extractTextRuns 的 hasOwnDecoration 检测）。
      for (const child of el.children) {
        if (hasOwnDecoration(child)) {
          const childNode = extractNode(child, wrapperRect);
          if (childNode !== null) node.children.push(childNode);
        }
      }
      return node;
    }

    // 提取 ::before / ::after 伪元素（必须在叶子节点早期返回之前）
    const pseudoNodes = extractPseudoElements(el, wrapperRect);
    for (const pn of pseudoNodes) {
      node.children.push(pn);
    }

    // 叶子文本节点
    const childElements = Array.from(el.childNodes).filter(n => n.nodeType === 1);
    if (childElements.length === 0) {
      const text = el.innerText || el.textContent || '';
      if (text.trim()) {
        node.text = text;
      }
      return node;
    }

    // 递归子节点
    for (const child of el.children) {
      const childNode = extractNode(child, wrapperRect);
      if (childNode !== null) {
        node.children.push(childNode);
      }
    }

    return node;
  }

  function buildSyntheticBackground(rootEl, wrapperRect) {
    const styles = extractStyles(rootEl);
    const hasBackgroundColor = styles.backgroundColor
      && styles.backgroundColor !== 'rgba(0, 0, 0, 0)'
      && styles.backgroundColor !== 'transparent';
    const hasBackgroundImage = styles.backgroundImage && styles.backgroundImage !== 'none';
    if (!hasBackgroundColor && !hasBackgroundImage) {
      return null;
    }
    return {
      tag: 'DIV',
      id: 'bg',
      classList: ['synthetic-body-bg'],
      styles,
      bounds: {
        x: 0,
        y: 0,
        w: wrapperRect.width,
        h: wrapperRect.height,
      },
      children: [],
    };
  }

  // ---------------------------------------------------------------------------
  // 主提取逻辑
  // ---------------------------------------------------------------------------
  const wrapper = document.querySelector('.wrapper');
  const root = wrapper || document.body;
  if (!root) {
    return { error: 'No slide root element found' };
  }

  const wrapperRect = root.getBoundingClientRect();

  // 提取背景 (#bg)
  const bgEl = document.getElementById('bg');
  const bg = bgEl ? extractNode(bgEl, wrapperRect) : buildSyntheticBackground(root, wrapperRect);

  // 提取页头 (#header)
  const headerEl = document.getElementById('header');
  const header = headerEl ? extractNode(headerEl, wrapperRect) : null;

  // 提取内容区 (#ct)
  const ctEl = document.getElementById('ct');
  const ct = ctEl ? extractNode(ctEl, wrapperRect) : null;

  // 提取页脚 (#footer)
  const footerEl = document.getElementById('footer');
  const footer = footerEl ? extractNode(footerEl, wrapperRect) : null;

  // 提取 overlay 层（.wrapper 中非 #bg/#header/#ct/#footer 的绝对定位子元素）
  const overlays = [];
  // 提取 rest 层（.wrapper 中非已知 ID 的非绝对定位子元素，如 .header 等浮动区域）
  const rest = [];
  for (const child of root.children) {
    if (child === bgEl || child === headerEl || child === ctEl || child === footerEl) continue;
    const cs = window.getComputedStyle(child);
    if (cs.getPropertyValue('display') === 'none') continue;
    const pos = cs.getPropertyValue('position');
    if (pos === 'absolute' || pos === 'fixed') {
      const node = extractNode(child, wrapperRect);
      if (node) overlays.push(node);
    } else {
      // 非绝对定位的未知子元素（如 .header class 但无 id="header"）
      const node = extractNode(child, wrapperRect);
      if (node) rest.push(node);
    }
  }

  // 提取 body 背景色（用于 opacity < 1 的 #bg 底色填充）
  const bodyBgColor = window.getComputedStyle(document.body).getPropertyValue('background-color');
  // body 的 background-image（用于 gradient 背景）
  const bodyBgImage = window.getComputedStyle(document.body).getPropertyValue('background-image');

  // 提取 .wrapper 背景（当 #bg 为透明时的 fallback）
  let wrapperBgColor = null;
  let wrapperBgImage = null;
  if (wrapper) {
    const wcs = window.getComputedStyle(wrapper);
    wrapperBgColor = wcs.getPropertyValue('background-color');
    wrapperBgImage = wcs.getPropertyValue('background-image');
  }

  // 检测画布尺寸（可能不是 1280x720）
  const canvasWidth = wrapperRect.width;
  const canvasHeight = wrapperRect.height;

  return { bg, header, ct, footer, overlays, rest, bodyBgColor, bodyBgImage, wrapperBgColor, wrapperBgImage, canvasWidth, canvasHeight };
};

// ---------------------------------------------------------------------------
// extractPage — 从单个 HTML 文件提取 IR
// ---------------------------------------------------------------------------

/**
 * 使用已有的 Playwright page 对象提取单个 HTML 文件的 IR。
 * @param {import('playwright').Page} page - Playwright page 对象
 * @param {string} htmlPath - HTML 文件的绝对路径
 * @returns {Promise<{bg:Object|null, ct:Object|null, footer:Object|null}>}
 */
export async function extractPage(page, htmlPath) {
  const fileUrl = htmlPath.startsWith('file://')
    ? htmlPath
    : `file://${path.resolve(htmlPath)}`;

  // 先用较大 viewport 加载，以便检测实际画布尺寸
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(fileUrl, { waitUntil: 'load' });
  await page.waitForTimeout(200);

  // 检测 HTML 实际画布尺寸（.wrapper / .slide / body）
  const canvasSize = await page.evaluate(() => {
    const wrapper = document.querySelector('.wrapper') || document.querySelector('.slide');
    if (wrapper) {
      const r = wrapper.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) return { w: Math.round(r.width), h: Math.round(r.height) };
    }
    return { w: 1280, h: 720 };
  });

  // 用实际尺寸设置 viewport 并重新渲染
  await page.setViewportSize({ width: canvasSize.w, height: canvasSize.h });
  // G-ii: 强制 reflow，确保 CSS clamp / vw / 媒体查询基于新 viewport 重新计算
  await page.evaluate(() => {
    void document.body.offsetHeight;
    // 也清空所有 element 的 inline style cache（某些库会缓存）
    return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  });
  await page.waitForTimeout(200);

  // Wait for ECharts to finish rendering, if any charts are on the page.
  // The page contract (see prompts/page_html.md) is that each chart increments
  // `window.__pptxChartsReady`. We count expected charts by looking for divs
  // with id="chart_N" containing a canvas or svg child.
  await page.evaluate(async () => {
    // wait up to 5 s for charts to finish rendering
    const start = Date.now();
    while (Date.now() - start < 5000) {
      const expected = document.querySelectorAll('[id^="chart_"]').length;
      if (expected === 0) return;  // no charts
      const ready = (window.__pptxChartsReady || 0);
      if (ready >= expected) return;
      await new Promise(r => setTimeout(r, 100));
    }
  });

  // Extract ECharts options from each chart_N container BEFORE the generic
  // BROWSER_EXTRACT_FN walks the DOM. We attach them as a map keyed by
  // the container's id (e.g. "chart_1") so the IR walker can pick them up.
  const chartOptionsMap = await page.evaluate(() => {
    // ECharts exposes echarts.getInstanceByDom(el) to recover the chart from
    // its container. If echarts isn't loaded (no charts on this page), bail.
    if (typeof window.echarts === 'undefined') return {};
    const result = {};
    const containers = document.querySelectorAll('[id^="chart_"]');
    for (const el of containers) {
      try {
        const inst = window.echarts.getInstanceByDom(el);
        if (!inst) continue;
        const opt = inst.getOption();
        result[el.id] = {
          option: opt,
          bounds: (() => {
            const r = el.getBoundingClientRect();
            return { x: r.left, y: r.top, w: r.width, h: r.height };
          })(),
        };
      } catch (e) {
        // ignore; extractor can still fall back to SVG-as-PNG for this chart
      }
    }
    return result;
  });

  const ir = await page.evaluate(BROWSER_EXTRACT_FN);

  // Attach chart options to the IR so pptx_builder can emit native charts.
  if (Object.keys(chartOptionsMap).length > 0 && ir) {
    ir._chartOptions = chartOptionsMap;
  }

  return ir;
}

// Kept as a no-op shim so callers / tests that still import the symbol do
// not break. SVG-area screenshots captured whatever happened to render
// underneath the SVG's bounding rect (other z-layers, background motifs,
// etc.), which produced visually wrong PPTX chart tiles. SVGs now flow
// through pptx_builder's native svgBlip path instead.
function _attachSvgPngsToIR(_ir, _svgPngs) {
  return;
  /* legacy walker body below, intentionally unreachable. */
  // eslint-disable-next-line no-unreachable
  let svgIdx = 0;
  function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (node.tag === 'SVG' && node.svgContent) {
      svgIdx += 1;
    }
    const kids = node.children || node.overlays || node.rest;
    if (Array.isArray(kids)) for (const c of kids) walk(c);
    if (node.children) for (const c of node.children) walk(c);
    if (node.overlays) for (const c of node.overlays) walk(c);
    if (node.rest) for (const c of node.rest) walk(c);
  }
  // The IR root could be {bg, ct, footer, overlays, rest, ...}; walk all branches.
  for (const key of ['bg', 'ct', 'footer', 'header']) {
    if (ir[key]) walk(ir[key]);
  }
  for (const key of ['overlays', 'rest']) {
    if (Array.isArray(ir[key])) for (const c of ir[key]) walk(c);
  }
}

// ---------------------------------------------------------------------------
// extractPages — 批量提取多个 HTML 文件
// ---------------------------------------------------------------------------

/**
 * 批量提取多个 HTML 文件的 IR。
 * 自动启动/关闭浏览器。
 * @param {string[]} htmlPaths - HTML 文件路径数组
 * @returns {Promise<Array<{path:string, ir:Object|null, error?:string}>>}
 */
export async function extractPages(htmlPaths) {
  const browser = await chromium.launch({ headless: true });
  const results = [];

  try {
    const page = await browser.newPage();

    for (const htmlPath of htmlPaths) {
      try {
        const ir = await extractPage(page, htmlPath);
        results.push({ path: htmlPath, ir });
      } catch (err) {
        process.stderr.write(`[dom_extractor] Failed to extract ${htmlPath}: ${err.message}\n`);
        results.push({ path: htmlPath, ir: null, error: err.message });
      }
    }
  } finally {
    await browser.close();
  }

  return results;
}
