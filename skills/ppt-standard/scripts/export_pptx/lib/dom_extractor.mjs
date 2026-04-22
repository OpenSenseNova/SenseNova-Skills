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
            underline: cs.getPropertyValue('text-decoration').includes('underline'),
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
        const cs = window.getComputedStyle(node);
        const display = cs.getPropertyValue('display');
        if (display === 'none') return;

        const text = node.innerText || '';
        if (!text) return;

        const isBlock = ['block', 'flex', 'grid', 'table', 'list-item'].includes(display);

        runs.push({
          text,
          bold: cs.getPropertyValue('font-weight') >= 600 || cs.getPropertyValue('font-weight') === 'bold',
          italic: cs.getPropertyValue('font-style') === 'italic',
          fontSize: cs.getPropertyValue('font-size'),
          color: cs.getPropertyValue('color'),
          fontFamily: cs.getPropertyValue('font-family'),
          underline: cs.getPropertyValue('text-decoration').includes('underline'),
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
          bounds = extractBounds(el, wrapperRect);
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
    if (tag === 'SVG') {
      node.svgContent = el.outerHTML;
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
      return node;
    }

    // 混合内容 → textRuns
    if (hasMixedContent(el)) {
      node.textRuns = extractTextRuns(el);
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
  await page.waitForTimeout(200);

  const ir = await page.evaluate(BROWSER_EXTRACT_FN);

  return ir;
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
