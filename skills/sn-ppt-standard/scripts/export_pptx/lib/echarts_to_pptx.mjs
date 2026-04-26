/**
 * Convert an ECharts option object into a pptxgenjs-native chart.
 *
 * Supported types: bar (vertical+horizontal), line, area, pie, doughnut,
 * radar, scatter, funnel, gauge (as doughnut+center label), combo (bar+line).
 *
 * Each mapping function returns:
 *   { chartType, data, options }
 *   - chartType : pptxgenjs ChartType enum value
 *   - data      : pptxgenjs chart data array
 *   - options   : pptxgenjs chart options (colors, labels, etc.)
 *
 * The caller does:
 *   slide.addChart(chartType, data, { x, y, w, h, ...options })
 *
 * Issues addressed (refer to docs/ppt-standard-html-to-pptx-issues_*.md):
 *   C2  combo bar+line                    → mapCombo
 *   C3  series colors palette             → extractSeriesColors / extractItemColors
 *   C5  data labels                       → extractDataLabelOptions
 *   C6  axis "%" formatter                → extractAxisFormatter
 *   C7  doughnut center label             → returned as `centerLabel` for the
 *                                           caller to render as overlay text
 *   C8  legend position                   → extractLegendOptions
 *   C13 horizontal bar (barH)             → detectBarOrientation
 *   C14 axis label rotate                 → extractAxisLabelRotate
 *   C12 radar axis name labels            → mapRadar passes them through
 */

// ---------------------------------------------------------------------------
// Type detection
// ---------------------------------------------------------------------------

function allSeries(option) {
  const series = option.series;
  if (!series) return [];
  return Array.isArray(series) ? series : [series];
}

/**
 * Pick the "primary" type. If multiple series with mixed types, return 'combo'.
 * Special cases:
 *   - line + areaStyle      → 'area'
 *   - pie with [r1,r2]      → 'doughnut'
 *   - gauge type            → 'gauge' (rendered as doughnut+center)
 *   - bar+line mix          → 'combo'
 */
function detectType(option) {
  const series = allSeries(option);
  if (series.length === 0) return null;

  const types = [...new Set(series.map(s => s.type).filter(Boolean))];
  if (types.length > 1) {
    // mixed series → combo (only bar+line is reasonable in pptx)
    if (types.every(t => t === 'bar' || t === 'line')) return 'combo';
    return null;
  }
  const t = types[0];

  if (t === 'line' && series[0].areaStyle) return 'area';
  if (t === 'pie') {
    const r = series[0].radius;
    if (Array.isArray(r) && r.length === 2) return 'doughnut';
    return 'pie';
  }
  return t || null;
}

/**
 * Detect whether a bar-type chart is horizontal.
 * ECharts convention: horizontal bars have yAxis.type='category' + xAxis.type='value'.
 */
function detectBarOrientation(option) {
  const xAxis = Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis;
  const yAxis = Array.isArray(option.yAxis) ? option.yAxis[0] : option.yAxis;
  const xCat = xAxis && (xAxis.type === 'category' || Array.isArray(xAxis.data));
  const yCat = yAxis && (yAxis.type === 'category' || Array.isArray(yAxis.data));
  if (yCat && !xCat) return 'horizontal';
  return 'vertical';
}

// ---------------------------------------------------------------------------
// Axis / label / color helpers
// ---------------------------------------------------------------------------

function extractCategoryLabels(option) {
  const xAxis = Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis;
  if (xAxis && Array.isArray(xAxis.data)) return xAxis.data.map(String);
  const yAxis = Array.isArray(option.yAxis) ? option.yAxis[0] : option.yAxis;
  if (yAxis && Array.isArray(yAxis.data)) return yAxis.data.map(String);
  return [];
}

/**
 * Convert ECharts axis formatter to pptxgenjs format code.
 *
 * IMPORTANT: pptxgenjs uses Excel-style format codes. `'0%'` means
 * "multiply by 100 and append %" — i.e. it expects a fraction (0.68 → 68%).
 * But ECharts data is usually already in percentage form (68 not 0.68).
 * If we return `'0%'`, pptxgenjs writes 6800% for a 68 value.
 *
 * Therefore: for `{value}%`, return `'0"%"'` (a literal % suffix that does
 * NOT scale the number). All other suffixes are also literal text.
 */
function formatterToCode(fmt) {
  if (typeof fmt !== 'string') return null;
  if (!fmt.includes('{value}')) return null;
  const m = fmt.match(/^\s*\{value\}(.*)$/);
  if (!m) return null;
  const suffix = m[1];
  if (!suffix) return '0';
  return `0"${suffix.replace(/"/g, '\\"')}"`;
}

function extractValueAxisFormatCode(option, axisName) {
  const ax = Array.isArray(option[axisName]) ? option[axisName][0] : option[axisName];
  if (!ax || !ax.axisLabel) return null;
  return formatterToCode(ax.axisLabel.formatter);
}

function extractAxisLabelRotate(option, axisName) {
  const ax = Array.isArray(option[axisName]) ? option[axisName][0] : option[axisName];
  if (!ax || !ax.axisLabel) return null;
  const r = ax.axisLabel.rotate;
  return typeof r === 'number' ? r : null;
}

/**
 * Convert any CSS-like color string (hex / rgb / rgba) to 6-digit hex without '#'.
 * Returns null if unparseable.
 */
function colorToHex(c) {
  if (!c || typeof c !== 'string') return null;
  let s = c.trim();
  if (s.startsWith('#')) s = s.slice(1);
  if (/^[0-9a-fA-F]{6}$/.test(s)) return s.toUpperCase();
  if (/^[0-9a-fA-F]{3}$/.test(s)) return s.split('').map(ch => ch + ch).join('').toUpperCase();
  if (/^[0-9a-fA-F]{8}$/.test(s)) return s.slice(0, 6).toUpperCase();
  const m = c.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (m) {
    return [+m[1], +m[2], +m[3]]
      .map(n => Math.max(0, Math.min(255, n)).toString(16).padStart(2, '0'))
      .join('').toUpperCase();
  }
  return null;
}

/**
 * Extract axis-related styling colors (label / line / split-line) for a given axis.
 */
function extractAxisStyle(option, axisName) {
  const ax = Array.isArray(option[axisName]) ? option[axisName][0] : option[axisName];
  if (!ax) return {};
  const out = {};
  const labelColor = colorToHex(ax.axisLabel?.color);
  if (labelColor) out.labelColor = labelColor;
  const lineColor = colorToHex(ax.axisLine?.lineStyle?.color);
  if (lineColor) out.lineColor = lineColor;
  const splitColor = colorToHex(ax.splitLine?.lineStyle?.color);
  if (splitColor) out.splitColor = splitColor;
  return out;
}

/**
 * Extract legend text color.
 */
function extractLegendColor(option) {
  const leg = Array.isArray(option.legend) ? option.legend[0] : option.legend;
  if (!leg) return null;
  return colorToHex(leg.textStyle?.color);
}

/**
 * Extract series-level data label color (from series[0].label.color).
 */
function extractDataLabelColor(series) {
  for (const s of series) {
    const c = colorToHex(s.label?.color);
    if (c) return c;
  }
  return null;
}

/**
 * Apply chart text/line theme colors to pptxgenjs options. HTML 深色 deck 的
 * ECharts 通常把 axisLabel.color/legend.textStyle.color 显式设成浅色（白/灰）；
 * pptxgenjs 默认 Office 主题（黑字白底），需要把这些显式颜色透传。
 */
function applyChartTheme(options, option, series) {
  const xAx = extractAxisStyle(option, 'xAxis');
  const yAx = extractAxisStyle(option, 'yAxis');
  if (xAx.labelColor) options.catAxisLabelColor = xAx.labelColor;
  if (yAx.labelColor) options.valAxisLabelColor = yAx.labelColor;
  if (xAx.lineColor) options.catAxisLineColor = xAx.lineColor;
  if (yAx.lineColor) options.valAxisLineColor = yAx.lineColor;
  if (xAx.splitColor) options.catGridLine = { color: xAx.splitColor, style: 'solid', size: 1 };
  if (yAx.splitColor) options.valGridLine = { color: yAx.splitColor, style: 'solid', size: 1 };
  const legColor = extractLegendColor(option);
  if (legColor) options.legendColor = legColor;
  const dlColor = extractDataLabelColor(series);
  if (dlColor) options.dataLabelColor = dlColor;
  return options;
}

/**
 * Per-series color (from itemStyle.color or color property).
 * Returns 6-hex without '#' or null.
 */
function getSeriesColor(s) {
  let c = null;
  if (s.itemStyle && typeof s.itemStyle.color === 'string') c = s.itemStyle.color;
  else if (typeof s.color === 'string') c = s.color;
  if (!c) return null;
  if (c.startsWith('#')) c = c.slice(1);
  if (/^[0-9a-fA-F]{6}$/.test(c)) return c.toUpperCase();
  if (/^[0-9a-fA-F]{3}$/.test(c)) {
    // expand short hex
    return c.split('').map(ch => ch + ch).join('').toUpperCase();
  }
  // rgb()/rgba() → hex
  const rgb = c.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (rgb) {
    return [+rgb[1], +rgb[2], +rgb[3]]
      .map(n => Math.max(0, Math.min(255, n)).toString(16).padStart(2, '0'))
      .join('').toUpperCase();
  }
  return null;
}

/**
 * Per-data-point colors (from data[i].itemStyle.color).
 * Returns array aligned with data; null entries for points without override.
 */
function getDataItemColors(s) {
  if (!Array.isArray(s.data)) return [];
  return s.data.map(d => {
    if (d && typeof d === 'object' && d.itemStyle && typeof d.itemStyle.color === 'string') {
      let c = d.itemStyle.color;
      if (c.startsWith('#')) c = c.slice(1);
      return /^[0-9a-fA-F]{6}$/.test(c) ? c.toUpperCase() : null;
    }
    return null;
  });
}

/**
 * Extract data label options from series.label.
 *   { show: true, position: 'top' }     → { showValue: true }
 *   { show: true, formatter: '{c}%' }   → { showValue: true, dataLabelFormatCode: '0%' }
 */
function extractDataLabelOptions(series) {
  // If any series has label.show=true, enable
  const anyShow = series.some(s => s.label && s.label.show === true);
  if (!anyShow) return {};
  const out = { showValue: true };
  // Pick the first series' formatter
  const withFmt = series.find(s => s.label && s.label.formatter);
  if (withFmt) {
    const fmt = withFmt.label.formatter;
    if (typeof fmt === 'string') {
      // ECharts data is already in percentage form (e.g. 68 not 0.68);
      // use literal "%" suffix (not '0%' which would multiply by 100).
      const m = fmt.match(/^\s*\{c\}(.*)$/);
      if (m) {
        const suffix = m[1];
        out.dataLabelFormatCode = suffix ? `0"${suffix.replace(/"/g, '\\"')}"` : '0';
      }
    }
  }
  return out;
}

/**
 * Legend options.
 */
function extractLegendOptions(option, seriesCount) {
  const showLegend = !!option.legend && (option.legend.show !== false) && seriesCount > 0;
  if (!showLegend) return { showLegend: false };
  const leg = Array.isArray(option.legend) ? option.legend[0] : option.legend;
  // Position
  let legendPos = 'b';
  if (leg) {
    if (leg.bottom != null && leg.right == null && leg.left == null) legendPos = 'b';
    else if (leg.top != null && leg.right == null && leg.left == null) legendPos = 't';
    else if (leg.left != null) legendPos = 'l';
    else if (leg.right != null) legendPos = 'r';
    else if (leg.orient === 'vertical') legendPos = 'r';
  }
  return { showLegend: true, legendPos };
}

/**
 * Extract data values from a series. Handles:
 *   [1, 2, 3]
 *   [{value: 1, itemStyle: {...}}]
 *   [[x, y]]  — for scatter
 */
function toNumbers(arr) {
  if (!Array.isArray(arr)) return [];
  return arr.map(v => {
    if (typeof v === 'number') return v;
    if (v && typeof v === 'object' && 'value' in v) {
      const x = v.value;
      return typeof x === 'number' ? x : (Array.isArray(x) ? x[x.length - 1] : 0);
    }
    return 0;
  });
}

/**
 * Doughnut/pie center label — pulled from option.graphic[].style.text or
 * series[0].label (when position='center'). The caller renders this as a
 * separate text frame overlaid on the chart bounds.
 */
function extractCenterLabel(option) {
  // Try graphic elements first (ECharts native center label pattern)
  if (Array.isArray(option.graphic)) {
    for (const g of option.graphic) {
      if (g && g.style && typeof g.style.text === 'string') {
        return { text: g.style.text, fontSize: g.style.fontSize, color: g.style.fill };
      }
      // graphic group
      if (g && Array.isArray(g.children)) {
        for (const ch of g.children) {
          if (ch && ch.style && typeof ch.style.text === 'string') {
            return { text: ch.style.text, fontSize: ch.style.fontSize, color: ch.style.fill };
          }
        }
      }
    }
  }
  // Fallback: series[0].label with position center
  const s0 = allSeries(option)[0];
  if (s0 && s0.label && s0.label.position === 'center' && typeof s0.label.formatter === 'string') {
    return { text: s0.label.formatter };
  }
  return null;
}

// ---------------------------------------------------------------------------
// Mappers
// ---------------------------------------------------------------------------

function mapBar(option, ChartType) {
  const labels = extractCategoryLabels(option);
  const series = allSeries(option).filter(s => s.type === 'bar');
  if (series.length === 0 || labels.length === 0) return null;

  const data = series.map(s => ({
    name: s.name || 'Series',
    labels,
    values: toNumbers(s.data || []),
  }));

  const orient = detectBarOrientation(option);
  // Color priority:
  //   1) per-data-point colors from series[0].data[i].itemStyle.color (single series)
  //   2) per-series colors from series[i].itemStyle.color
  //   3) option.color array
  let chartColors;
  if (series.length === 1) {
    const itemCols = getDataItemColors(series[0]);
    if (itemCols.length === labels.length && itemCols.every(Boolean)) chartColors = itemCols;
  }
  if (!chartColors) {
    const seriesCols = series.map(getSeriesColor).filter(Boolean);
    if (seriesCols.length === series.length) chartColors = seriesCols;
  }
  if (!chartColors && Array.isArray(option.color)) {
    chartColors = option.color.map(c => typeof c === 'string' ? c.replace('#', '').toUpperCase() : null).filter(Boolean);
  }

  const valFmt = extractValueAxisFormatCode(option, orient === 'horizontal' ? 'xAxis' : 'yAxis');
  const catRotate = extractAxisLabelRotate(option, orient === 'horizontal' ? 'yAxis' : 'xAxis');

  const options = {
    barDir: orient === 'horizontal' ? 'bar' : 'col',
    chartColors,
    ...extractLegendOptions(option, series.length),
    ...extractDataLabelOptions(series),
  };
  if (valFmt) options.valAxisLabelFormatCode = valFmt;
  if (catRotate != null) options.catAxisLabelRotate = catRotate;
  applyChartTheme(options, option, series);

  return { chartType: ChartType.bar, data, options };
}

function mapLine(option, ChartType) {
  const labels = extractCategoryLabels(option);
  const series = allSeries(option).filter(s => s.type === 'line');
  if (series.length === 0 || labels.length === 0) return null;

  const data = series.map(s => ({
    name: s.name || 'Series',
    labels,
    values: toNumbers(s.data || []),
  }));

  const seriesCols = series.map(getSeriesColor).filter(Boolean);
  const chartColors = seriesCols.length === series.length ? seriesCols : undefined;

  const valFmt = extractValueAxisFormatCode(option, 'yAxis');
  const catRotate = extractAxisLabelRotate(option, 'xAxis');

  const options = {
    lineSmooth: series.some(s => s.smooth),
    chartColors,
    ...extractLegendOptions(option, series.length),
    ...extractDataLabelOptions(series),
  };
  if (valFmt) options.valAxisLabelFormatCode = valFmt;
  if (catRotate != null) options.catAxisLabelRotate = catRotate;
  applyChartTheme(options, option, series);

  return { chartType: ChartType.line, data, options };
}

function mapArea(option, ChartType) {
  const labels = extractCategoryLabels(option);
  const series = allSeries(option).filter(s => s.type === 'line' && s.areaStyle);
  if (series.length === 0 || labels.length === 0) return null;

  const data = series.map(s => ({
    name: s.name || 'Series',
    labels,
    values: toNumbers(s.data || []),
  }));

  const seriesCols = series.map(getSeriesColor).filter(Boolean);
  const chartColors = seriesCols.length === series.length ? seriesCols : undefined;

  const options = {
    chartColors,
    ...extractLegendOptions(option, series.length),
    ...extractDataLabelOptions(series),
  };
  const valFmt = extractValueAxisFormatCode(option, 'yAxis');
  if (valFmt) options.valAxisLabelFormatCode = valFmt;
  applyChartTheme(options, option, series);

  return { chartType: ChartType.area, data, options };
}

function mapPie(option, ChartType, hollow) {
  const series = allSeries(option).filter(s => s.type === 'pie');
  if (series.length === 0) return null;
  const s0 = series[0];
  const items = (s0.data || []).filter(d => d && typeof d === 'object');
  if (items.length === 0) return null;

  const labels = items.map(d => String(d.name || ''));
  const values = items.map(d => typeof d.value === 'number' ? d.value : 0);
  const data = [{ name: s0.name || 'Series', labels, values }];

  // Per-slice colors from items[*].itemStyle.color, fallback to option.color
  let sliceColors = items.map(d => {
    if (d.itemStyle && typeof d.itemStyle.color === 'string') return d.itemStyle.color.replace('#', '').toUpperCase();
    return null;
  });
  if (sliceColors.some(c => !c) && Array.isArray(option.color)) {
    sliceColors = items.map((_, i) => {
      const c = option.color[i % option.color.length];
      return typeof c === 'string' ? c.replace('#', '').toUpperCase() : null;
    });
  }
  const chartColors = sliceColors.every(Boolean) ? sliceColors : undefined;

  const options = {
    chartColors,
    ...extractLegendOptions(option, items.length),
    ...extractDataLabelOptions([s0]),
  };
  if (hollow) {
    // ECharts radius like ['60%', '80%'] → hole 60%
    const r = s0.radius;
    if (Array.isArray(r) && typeof r[0] === 'string') {
      const inner = parseFloat(r[0]);
      if (!Number.isNaN(inner)) options.holeSize = Math.round(inner);
    } else {
      options.holeSize = 50;
    }
  }
  // Default data label format for pie: percentages
  if (!options.dataLabelFormatCode) options.dataLabelFormatCode = '0"%"';
  applyChartTheme(options, option, [s0]);

  const result = {
    chartType: hollow ? ChartType.doughnut : ChartType.pie,
    data,
    options,
  };
  // Center label (for doughnut) is returned as metadata; the caller (pptx_builder)
  // overlays it as a text frame on top of the chart bounds.
  const center = extractCenterLabel(option);
  if (center && hollow) result.centerLabel = center;
  return result;
}

function mapRadar(option, ChartType) {
  const radarDef = Array.isArray(option.radar) ? option.radar[0] : option.radar;
  if (!radarDef || !Array.isArray(radarDef.indicator)) return null;
  const labels = radarDef.indicator.map(i => String(i.name || ''));
  if (labels.length === 0) return null;

  const series = allSeries(option).filter(s => s.type === 'radar');
  if (series.length === 0) return null;
  const s0 = series[0];
  const rawItems = s0.data || [];
  const items = Array.isArray(rawItems) ? rawItems : [];

  const data = items.map(item => {
    let values, name = 'Series';
    if (Array.isArray(item)) values = item.map(v => Number(v) || 0);
    else if (item && typeof item === 'object') {
      values = Array.isArray(item.value) ? item.value.map(v => Number(v) || 0) : [];
      name = item.name || name;
    } else values = [];
    return { name, labels, values };
  }).filter(d => d.values.length === labels.length);

  if (data.length === 0) return null;

  const seriesCols = series.map(getSeriesColor).filter(Boolean);
  const chartColors = seriesCols.length === series.length ? seriesCols : undefined;

  const radarOpts = {
    radarStyle: 'standard',
    chartColors,
    ...extractLegendOptions(option, data.length),
  };
  applyChartTheme(radarOpts, option, series);

  return {
    chartType: ChartType.radar,
    data,
    options: radarOpts,
  };
}

function mapScatter(option, ChartType) {
  const series = allSeries(option).filter(s => s.type === 'scatter');
  if (series.length === 0) return null;

  const xValues = [];
  const yLists = [];
  for (const s of series) {
    const pairs = (s.data || []).filter(d => Array.isArray(d) && d.length >= 2);
    if (pairs.length === 0) continue;
    if (xValues.length === 0) {
      for (const p of pairs) xValues.push(Number(p[0]) || 0);
    }
    yLists.push({ name: s.name || 'Series', values: pairs.map(p => Number(p[1]) || 0) });
  }
  if (xValues.length === 0 || yLists.length === 0) return null;

  const data = [{ name: 'X-Axis', values: xValues }, ...yLists];
  const seriesCols = series.map(getSeriesColor).filter(Boolean);
  const chartColors = seriesCols.length === series.length ? seriesCols : undefined;

  const scatterOpts = {
    chartColors,
    ...extractLegendOptions(option, yLists.length),
  };
  applyChartTheme(scatterOpts, option, series);

  return {
    chartType: ChartType.scatter,
    data,
    options: scatterOpts,
  };
}

function mapFunnel(option, ChartType) {
  // pptxgenjs 的 ChartType 枚举没有 'funnel'（funnel 仅是 ShapeType）。
  // 之前传 `ChartType.funnel` (undefined) 会让 pptxgenjs 写出空 plotArea
  // （没 <c:xxxChart>）→ schema 违规 → PowerPoint 报"需修复"并删页
  // （用户运营 p3 的 chart_2 即此问题）。
  // 退化方案：funnel → 横向条形图（barH），各项作单独类目，长度反映 value。
  // 视觉近似漏斗（自上而下递减条），数据语义保留。
  const series = allSeries(option).filter(s => s.type === 'funnel');
  if (series.length === 0) return null;
  const s0 = series[0];
  const items = (s0.data || []).filter(d => d && typeof d === 'object');
  if (items.length === 0) return null;
  const labels = items.map(d => String(d.name || ''));
  const values = items.map(d => Number(d.value) || 0);
  const data = [{ name: s0.name || 'Series', labels, values }];

  // 用 per-item 颜色（每个漏斗段一种颜色），更接近原始 ECharts 视觉
  let sliceColors = items.map(d => {
    if (d.itemStyle && typeof d.itemStyle.color === 'string') return d.itemStyle.color.replace('#', '').toUpperCase();
    return null;
  });
  if (sliceColors.some(c => !c) && Array.isArray(option.color)) {
    sliceColors = items.map((_, i) => option.color[i % option.color.length]?.replace('#', '').toUpperCase() || null);
  }
  const chartColors = sliceColors.every(Boolean) ? sliceColors : undefined;

  const funnelOpts = {
    barDir: 'bar',  // 横向条形（漏斗近似）
    chartColors,
    ...extractDataLabelOptions([s0]),
    ...extractLegendOptions(option, 1),
  };
  applyChartTheme(funnelOpts, option, [s0]);
  return {
    chartType: ChartType.bar,
    data,
    options: funnelOpts,
  };
}

function mapGauge(option, ChartType) {
  // ECharts gauge → render as doughnut + center label.
  // Series.data[0].value is the gauge percentage.
  const series = allSeries(option).filter(s => s.type === 'gauge');
  if (series.length === 0) return null;
  const s0 = series[0];
  const items = Array.isArray(s0.data) ? s0.data : [];
  if (items.length === 0) return null;
  const first = items[0];
  const value = typeof first === 'number' ? first
    : (first && typeof first === 'object' ? Number(first.value) : 0);
  const max = typeof s0.max === 'number' ? s0.max : 100;
  const filled = Math.max(0, Math.min(value, max));
  const remaining = Math.max(0, max - filled);
  // 2-slice doughnut: filled + remaining
  const data = [{
    name: 'Gauge',
    labels: ['Value', 'Rest'],
    values: [filled, remaining],
  }];
  const fillColor = getSeriesColor(s0) || '4472C4';
  const trackColor = 'E0E0E0';
  return {
    chartType: ChartType.doughnut,
    data,
    options: {
      chartColors: [fillColor, trackColor],
      showLegend: false,
      holeSize: 60,
      showValue: false,
    },
    centerLabel: {
      text: `${filled}${typeof first === 'object' && first.name ? '\n' + first.name : ''}`,
      fontSize: 28,
    },
  };
}

function mapCombo(option, ChartType) {
  // bar+line combo. pptxgenjs supports combo via addChart with an array of
  // { type, data, options } per series, but only at the slide level — see
  // https://github.com/gitbrent/PptxGenJS#combo-charts
  // For now, fall back to whichever has more data points, with a warning.
  // True combo support requires pptx_builder to call addChart differently.
  const labels = extractCategoryLabels(option);
  const barSeries = allSeries(option).filter(s => s.type === 'bar');
  const lineSeries = allSeries(option).filter(s => s.type === 'line');
  if (labels.length === 0) return null;

  // Each series becomes a tuple { type, data, options } for pptxgenjs combo.
  const types = [];
  const seriesAll = [];
  for (const s of barSeries) {
    types.push({
      type: ChartType.bar,
      data: [{ name: s.name || 'Bar', labels, values: toNumbers(s.data || []) }],
      options: { barDir: 'col', chartColors: [getSeriesColor(s) || '4472C4'] },
    });
    seriesAll.push(s);
  }
  for (const s of lineSeries) {
    // line series may use yAxisIndex=1 (secondary y-axis)
    const opts = {
      chartColors: [getSeriesColor(s) || 'ED7D31'],
      lineSmooth: !!s.smooth,
    };
    // 走次轴时，pptxgenjs 要求 chart 元素引用的 axId 自洽：
    // line 必须同时引用次 catAx + 次 valAx。否则 lineChart 引用混合
    // (主 catAx + 次 valAx)，PowerPoint 严格校验拒绝 → 报需修复 → 删页。
    if (s.yAxisIndex === 1) {
      opts.secondaryValAxis = true;
      opts.secondaryCatAxis = true;
    }
    types.push({
      type: ChartType.line,
      data: [{ name: s.name || 'Line', labels, values: toNumbers(s.data || []) }],
      options: opts,
    });
    seriesAll.push(s);
  }

  const valFmt = extractValueAxisFormatCode(option, 'yAxis');
  const valFmt2 = (Array.isArray(option.yAxis) && option.yAxis[1])
    ? formatterToCode(option.yAxis[1].axisLabel?.formatter)
    : null;
  const catRotate = extractAxisLabelRotate(option, 'xAxis');

  // 检测是否有 series 用次值轴（ECharts: yAxisIndex === 1）
  const hasSecondaryAxis = lineSeries.some(s => s.yAxisIndex === 1);

  const sharedOptions = {
    ...extractLegendOptions(option, seriesAll.length),
    ...extractDataLabelOptions(seriesAll),
  };
  if (valFmt) sharedOptions.valAxisLabelFormatCode = valFmt;
  if (catRotate != null) sharedOptions.catAxisLabelRotate = catRotate;

  // 修 PowerPoint "需修复"错误（iPhone p3 / 用户运营 p3）：
  //
  // pptxgenjs 在 makeChartType 写 BAR/LINE chart 元素时，会根据每个 entry 的
  // options.secondaryValAxis 决定 axId 引用的是 PRIMARY (2094734552) 还是
  // SECONDARY (2094734553)；但只有当 sharedOptions.valAxes 数组里**确实
  // 存在 valAxes[1]** 时，pptxgenjs 才会写出对应的 secondary <c:valAx>。
  // 之前我们只在 entry.options 里设了 secondaryValAxis: true 但没传
  // sharedOptions.valAxes，导致 lineChart 引用 axId=2094734553 但 chart 元素
  // 层缺 valAx → schema 违规 → PowerPoint 拒绝打开整页。
  //
  // 解：当任一 line series 用次轴时，显式传 valAxes [primary, secondary]
  // 让 pptxgenjs 同时生成两个 valAx 元素。同时通过 catAxes 保持单 catAxis。
  if (hasSecondaryAxis) {
    sharedOptions.valAxes = [
      {
        showValAxisTitle: false,
        valAxisLabelFormatCode: valFmt || 'General',
      },
      {
        showValAxisTitle: false,
        valAxisLabelFormatCode: valFmt2 || valFmt || 'General',
      },
    ];
    sharedOptions.catAxes = [
      { showCatAxisTitle: false, catAxisLabelRotate: catRotate || 0 },
      { showCatAxisTitle: false, catAxisHidden: true },  // pptxgenjs 要求 catAxes.length == valAxes.length
    ];
  }
  applyChartTheme(sharedOptions, option, seriesAll);

  return {
    chartType: 'combo',  // sentinel — pptx_builder routes this to slide.addChart with type array
    data: types,
    options: sharedOptions,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Convert an ECharts option into pptxgenjs chart args.
 *
 * @param {Object} option - ECharts option (as returned by chart.getOption()).
 * @param {Object} ChartType - pptxgenjs ChartType enum.
 * @returns {Object|null} {chartType, data, options, centerLabel?} or null.
 *   For combo charts, chartType is the literal string 'combo' and `data` is
 *   an array of {type, data, options} entries (one per series).
 */
export function echartsOptionToPptx(option, ChartType) {
  if (!option || !ChartType) return null;
  let type;
  try {
    type = detectType(option);
  } catch (err) {
    process.stderr.write(`[echarts] type detect failed: ${err.message}\n`);
    return null;
  }
  if (!type) return null;

  try {
    switch (type) {
      case 'bar':      return mapBar(option, ChartType);
      case 'line':     return mapLine(option, ChartType);
      case 'area':     return mapArea(option, ChartType);
      case 'pie':      return mapPie(option, ChartType, false);
      case 'doughnut': return mapPie(option, ChartType, true);
      case 'radar':    return mapRadar(option, ChartType);
      case 'scatter':  return mapScatter(option, ChartType);
      case 'funnel':   return mapFunnel(option, ChartType);
      case 'gauge':    return mapGauge(option, ChartType);
      case 'combo':    return mapCombo(option, ChartType);
      default:
        process.stderr.write(`[echarts] unsupported series type: ${type}\n`);
        return null;
    }
  } catch (err) {
    process.stderr.write(`[echarts] mapping ${type} failed: ${err.message}\n`);
    return null;
  }
}
