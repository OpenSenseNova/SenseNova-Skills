/**
 * style_parser.mjs
 * 纯 CSS 值解析工具函数，无外部依赖。
 * 供 PPTX builder 将 CSS 值转换为 pptxgenjs 兼容格式。
 */

// ---------------------------------------------------------------------------
// 内部辅助：CSS 命名颜色表（仅常用子集）
// ---------------------------------------------------------------------------
const NAMED_COLORS = {
  black:   '000000',
  white:   'FFFFFF',
  red:     'FF0000',
  green:   '008000',
  blue:    '0000FF',
  yellow:  'FFFF00',
  cyan:    '00FFFF',
  magenta: 'FF00FF',
  orange:  'FFA500',
  purple:  '800080',
  pink:    'FFC0CB',
  brown:   'A52A2A',
  gray:    '808080',
  grey:    '808080',
  silver:  'C0C0C0',
  lime:    '00FF00',
  navy:    '000080',
  teal:    '008080',
  maroon:  '800000',
  olive:   '808000',
  aqua:    '00FFFF',
  fuchsia: 'FF00FF',
  coral:   'FF7F50',
  salmon:  'FA8072',
  gold:    'FFD700',
  khaki:   'F0E68C',
  violet:  'EE82EE',
  indigo:  '4B0082',
  beige:   'F5F5DC',
  ivory:   'FFFFF0',
  lavender:'E6E6FA',
  mint:    '98FF98',
};

// ---------------------------------------------------------------------------
// isTransparent — 检测透明颜色值
// ---------------------------------------------------------------------------
/**
 * 判断 CSS 颜色值是否为完全透明。
 * @param {string} cssColor
 * @returns {boolean}
 */
export function isTransparent(cssColor) {
  if (!cssColor) return false;
  const v = cssColor.trim().toLowerCase();
  if (v === 'transparent') return true;
  // rgba(r, g, b, 0) 形式
  const m = v.match(/^rgba\s*\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)\s*\)$/);
  if (m && parseFloat(m[1]) === 0) return true;
  return false;
}

// ---------------------------------------------------------------------------
// cssColorToHex — CSS 颜色转 6 位大写十六进制（不含 #）
// ---------------------------------------------------------------------------
/**
 * 将 CSS 颜色值转为 6 位大写十六进制字符串（不含 #）。
 * 对透明颜色返回 null。
 * @param {string} cssColor
 * @returns {string|null}
 */
export function cssColorToHex(cssColor) {
  if (!cssColor) return null;
  const v = cssColor.trim();

  // 透明处理
  if (isTransparent(v)) return null;

  const lower = v.toLowerCase();

  // --- 命名颜色 ---
  if (NAMED_COLORS[lower]) return NAMED_COLORS[lower];

  // --- #rrggbb 或 #rgb ---
  const hex6 = v.match(/^#([0-9a-fA-F]{6})$/);
  if (hex6) return hex6[1].toUpperCase();

  const hex3 = v.match(/^#([0-9a-fA-F]{3})$/);
  if (hex3) {
    const [r, g, b] = hex3[1].split('').map(c => c + c);
    return (r + g + b).toUpperCase();
  }

  // --- rgb(r, g, b) 或 rgba(r, g, b, a) ---
  const rgbMatch = v.match(
    /^rgba?\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*[\d.]+)?\s*\)$/i
  );
  if (rgbMatch) {
    const r = Math.round(parseFloat(rgbMatch[1]));
    const g = Math.round(parseFloat(rgbMatch[2]));
    const b = Math.round(parseFloat(rgbMatch[3]));
    return [r, g, b].map(n => n.toString(16).padStart(2, '0')).join('').toUpperCase();
  }

  return null;
}

// ---------------------------------------------------------------------------
// pxToInch — 像素转英寸（基准：canvasWidth px = 10 英寸）
// ---------------------------------------------------------------------------

// 画布宽度（px），默认 1280。每页提取时通过 setCanvasWidth 更新。
let _canvasWidth = 1280;

/**
 * 设置当前页面的画布宽度（px），用于坐标换算。
 * @param {number} w
 */
export function setCanvasWidth(w) {
  if (w > 0) _canvasWidth = w;
}

/**
 * 将像素值转换为英寸。
 * 换算比例：1px = 10/canvasWidth inch
 * @param {number} px
 * @returns {number}
 */
export function pxToInch(px) {
  return px * (10 / _canvasWidth);
}

// ---------------------------------------------------------------------------
// parseLinearGradient — 解析 CSS linear-gradient()
// ---------------------------------------------------------------------------
/**
 * 解析 linear-gradient() CSS 值。
 * 仅处理 linear-gradient，radial/conic/none 返回 null。
 * @param {string} cssValue
 * @returns {{type:'linear', angle:number, stops:Array<{position:number, color:string}>}|null}
 */
export function parseLinearGradient(cssValue) {
  if (!cssValue) return null;
  const trimmed = cssValue.trim();

  // 必须以 linear-gradient( 开头
  if (!/^linear-gradient\s*\(/i.test(trimmed)) return null;

  // 提取括号内容
  const inner = trimmed.replace(/^linear-gradient\s*\(\s*/i, '').replace(/\s*\)$/, '');

  // 将 rgb()/rgba() 内部逗号临时替换，避免干扰顶层分割
  let safeInner = inner.replace(/rgba?\s*\([^)]*\)/gi, m => m.replace(/,/g, '§'));

  // 按顶层逗号分割
  const parts = safeInner.split(',').map(p => p.replace(/§/g, ',').trim());

  if (parts.length < 2) return null;

  // 第一部分判断是否为方向/角度
  let angle = 180; // 默认 to bottom = 180deg
  let stopParts = parts;

  const firstPart = parts[0].trim();
  const angleDeg = firstPart.match(/^(-?[\d.]+)deg$/i);
  if (angleDeg) {
    angle = parseFloat(angleDeg[1]);
    stopParts = parts.slice(1);
  } else if (/^to\s+/i.test(firstPart)) {
    // to top/bottom/left/right 等转为角度
    const dir = firstPart.toLowerCase().replace(/^to\s+/, '');
    const DIR_MAP = {
      'top': 0,
      'right': 90,
      'bottom': 180,
      'left': 270,
      'top right': 45,
      'right top': 45,
      'bottom right': 135,
      'right bottom': 135,
      'bottom left': 225,
      'left bottom': 225,
      'top left': 315,
      'left top': 315,
    };
    angle = DIR_MAP[dir] ?? 180;
    stopParts = parts.slice(1);
  }

  // 解析颜色停止点（保留 transparent / rgba alpha=0 的 stop，用于 SVG 渲染）
  const stops = [];
  for (const part of stopParts) {
    const p = part.trim();
    if (!p) continue;

    const stopMatch = p.match(/^(.*?)\s+([\d.]+)%\s*$/);
    if (stopMatch) {
      const rawColor = stopMatch[1].trim();
      const colorHex = cssColorToHex(rawColor);
      // 保留 transparent stop：hex 为 null 时用 '000000' 占位，alpha 为 0
      stops.push({
        position: parseFloat(stopMatch[2]),
        color: colorHex || '000000',
        rawColor,
        isTransparent: colorHex === null,
      });
    } else {
      const colorHex = cssColorToHex(p);
      stops.push({
        color: colorHex || '000000',
        rawColor: p,
        isTransparent: colorHex === null,
      });
    }
  }

  if (stops.length === 0) return null;

  // direction: 保留原始方向文本（用于 mask-image SVG 生成等场景）
  const direction = /^to\s+/i.test(parts[0].trim()) ? parts[0].trim().toLowerCase() : null;

  return { type: 'linear', angle, stops, direction };
}

// ---------------------------------------------------------------------------
// parseRadialGradient — 解析 CSS radial-gradient()
// ---------------------------------------------------------------------------
/**
 * 解析 radial-gradient() CSS 值，提取颜色停止点。
 * pptxgenjs 不支持径向渐变，提取 stops 后可用线性渐变近似。
 * @param {string} cssValue
 * @returns {{type:'radial', stops:Array<{position?:number, color:string}>}|null}
 */
export function parseRadialGradient(cssValue) {
  if (!cssValue) return null;
  const trimmed = cssValue.trim();

  if (!/radial-gradient\s*\(/i.test(trimmed)) return null;

  // 提取括号内容
  const inner = trimmed.replace(/^.*?radial-gradient\s*\(\s*/i, '').replace(/\s*\)$/, '');

  // 将 rgb()/rgba() 内部逗号临时替换
  let safeInner = inner.replace(/rgba?\s*\([^)]*\)/gi, m => m.replace(/,/g, '§'));

  const parts = safeInner.split(',').map(p => p.replace(/§/g, ',').trim());

  if (parts.length < 2) return null;

  // 第一部分可能是 shape/position 描述（circle at 80% 20%），跳过
  let stopParts = parts;
  const firstPart = parts[0].trim().toLowerCase();
  if (firstPart.includes('circle') || firstPart.includes('ellipse') ||
      firstPart.includes('at ') || firstPart.includes('closest') ||
      firstPart.includes('farthest')) {
    stopParts = parts.slice(1);
  }

  // 解析颜色停止点（保留 transparent stop）
  const stops = [];
  for (const part of stopParts) {
    const p = part.trim();
    if (!p) continue;

    const stopMatch = p.match(/^(.*?)\s+([\d.]+)%\s*$/);
    if (stopMatch) {
      const rawColor = stopMatch[1].trim();
      const colorHex = cssColorToHex(rawColor);
      stops.push({
        position: parseFloat(stopMatch[2]),
        color: colorHex || '000000',
        rawColor,
        isTransparent: colorHex === null,
      });
    } else {
      const colorHex = cssColorToHex(p);
      stops.push({
        color: colorHex || '000000',
        rawColor: p,
        isTransparent: colorHex === null,
      });
    }
  }

  if (stops.length === 0) return null;

  return { type: 'radial', stops };
}

// ---------------------------------------------------------------------------
// parseBoxShadow — 解析 CSS box-shadow
// ---------------------------------------------------------------------------
/**
 * 解析 box-shadow CSS 值。
 * 跳过 inset 阴影。none/空 返回 null。
 * @param {string} cssValue
 * @returns {{type:'outer', offsetX:number, offsetY:number, blur:number, color:string, opacity:number}|null}
 */
export function parseBoxShadow(cssValue) {
  if (!cssValue) return null;
  const trimmed = cssValue.trim().toLowerCase();
  if (trimmed === 'none') return null;

  // 过滤 inset
  if (/^\s*inset\b/.test(trimmed)) return null;

  // 将 rgba?()/rgb?() 颜色部分替换为占位符，避免其内部空格干扰解析
  let safe = cssValue.trim();
  let colorValue = null;

  // 提取 rgba?() 颜色
  const rgbaMatch = safe.match(/rgba?\s*\([^)]*\)/i);
  if (rgbaMatch) {
    colorValue = rgbaMatch[0];
    safe = safe.replace(colorValue, '__COLOR__');
  }

  const tokens = safe.trim().split(/\s+/);

  // 提取数值 token（以 px 结尾或纯数字）
  const pxNums = [];
  let resolvedColor = null;

  for (const tok of tokens) {
    if (tok === '__COLOR__') {
      resolvedColor = colorValue;
      continue;
    }
    const pxMatch = tok.match(/^(-?[\d.]+)px$/i);
    if (pxMatch) {
      pxNums.push(parseFloat(pxMatch[1]));
      continue;
    }
    // 纯数字（0）
    if (/^-?[\d.]+$/.test(tok)) {
      pxNums.push(parseFloat(tok));
      continue;
    }
    // 可能是 hex 颜色
    if (/^#[0-9a-fA-F]{3,6}$/.test(tok)) {
      resolvedColor = tok;
      continue;
    }
    // named color 或其它忽略
  }

  if (pxNums.length < 2) return null;

  const offsetX = pxNums[0];
  const offsetY = pxNums[1];
  const blur = pxNums.length >= 3 ? pxNums[2] : 0;

  // 解析颜色和透明度
  let color = '000000';
  let opacity = 1;

  if (resolvedColor) {
    // 尝试从 rgba() 中提取 opacity
    const rgbaFull = resolvedColor.match(
      /rgba\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)/i
    );
    if (rgbaFull) {
      const r = Math.round(parseFloat(rgbaFull[1]));
      const g = Math.round(parseFloat(rgbaFull[2]));
      const b = Math.round(parseFloat(rgbaFull[3]));
      opacity = parseFloat(rgbaFull[4]);
      color = [r, g, b].map(n => n.toString(16).padStart(2, '0')).join('').toUpperCase();
    } else {
      const hex = cssColorToHex(resolvedColor);
      if (hex) color = hex;
    }
  }

  return { type: 'outer', offsetX, offsetY, blur, color, opacity };
}

// ---------------------------------------------------------------------------
// parseFontFamily — 解析 CSS font-family
// ---------------------------------------------------------------------------
/**
 * 提取 CSS font-family 列表中第一个非通用字体。
 * 若所有字体均为通用族，则映射为对应的 fallback 字体名。
 * @param {string} cssValue
 * @returns {string|null}
 */
export function parseFontFamily(cssValue) {
  if (!cssValue) return null;

  const GENERIC_MAP = {
    'sans-serif': 'Arial',
    'serif':      'Times New Roman',
    'monospace':  'Courier New',
    'cursive':    'Comic Sans MS',
    'fantasy':    'Impact',
    'system-ui':  'Arial',
    '-apple-system': 'Arial',
  };

  const GENERIC_NAMES = new Set(Object.keys(GENERIC_MAP));

  // 按逗号分割，去掉引号，trim
  const families = cssValue.split(',').map(f => f.trim().replace(/^['"]|['"]$/g, ''));

  // 先找第一个非通用字体
  for (const f of families) {
    if (!GENERIC_NAMES.has(f.toLowerCase()) && f.length > 0) {
      return f;
    }
  }

  // 全是通用族，返回第一个映射值
  if (families.length > 0) {
    const lower = families[0].toLowerCase();
    return GENERIC_MAP[lower] ?? null;
  }

  return null;
}

// ---------------------------------------------------------------------------
// extractCssAlpha — 提取 CSS 颜色的 alpha 通道
// ---------------------------------------------------------------------------
/**
 * 从 CSS 颜色值中提取 alpha 通道值。
 * rgba() → alpha 值；transparent → 0；其它 → 1。
 * @param {string} cssColor
 * @returns {number}
 */
export function extractCssAlpha(cssColor) {
  if (!cssColor) return 1;
  const m = cssColor.match(/rgba\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)\s*\)/);
  if (m) return parseFloat(m[1]);
  if (cssColor.trim().toLowerCase() === 'transparent') return 0;
  return 1;
}

// ---------------------------------------------------------------------------
// parseBorder — 解析 CSS border shorthand
// ---------------------------------------------------------------------------
/**
 * 解析 border shorthand CSS 值。
 * none 或 0px 宽度返回 null。
 * @param {string} cssValue
 * @returns {{width:number, style:string, color:string}|null}
 */
export function parseBorder(cssValue) {
  if (!cssValue) return null;
  const trimmed = cssValue.trim().toLowerCase();
  if (trimmed === 'none') return null;

  // 提取颜色（rgb()/rgba() 或 hex）
  let safe = cssValue.trim();
  let resolvedColor = null;

  const rgbMatch = safe.match(/rgba?\s*\([^)]*\)/i);
  if (rgbMatch) {
    resolvedColor = rgbMatch[0];
    safe = safe.replace(resolvedColor, '');
  }

  // 剩余 token 解析
  const tokens = safe.trim().split(/\s+/);
  let width = null;
  let style = null;

  const BORDER_STYLES = new Set([
    'none','hidden','dotted','dashed','solid','double',
    'groove','ridge','inset','outset','initial','inherit',
  ]);

  for (const tok of tokens) {
    if (!tok) continue;
    const pxMatch = tok.match(/^([\d.]+)px$/i);
    if (pxMatch) {
      width = parseFloat(pxMatch[1]);
      continue;
    }
    if (BORDER_STYLES.has(tok.toLowerCase())) {
      style = tok.toLowerCase();
      continue;
    }
    // hex color
    if (/^#[0-9a-fA-F]{3,6}$/.test(tok)) {
      resolvedColor = tok;
      continue;
    }
  }

  // 0px 宽度视为 null
  if (width === 0) return null;
  // style 为 none 时返回 null
  if (style === 'none') return null;
  // 必须有宽度
  if (width === null) return null;

  const colorHex = resolvedColor ? cssColorToHex(resolvedColor) : null;

  return {
    width,
    style: style ?? 'solid',
    color: colorHex ?? '000000',
  };
}
