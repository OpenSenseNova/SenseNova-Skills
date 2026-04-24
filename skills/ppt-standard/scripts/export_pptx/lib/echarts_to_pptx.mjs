/**
 * Convert an ECharts option object into a pptxgenjs-native chart.
 *
 * Supported types: bar, line, pie, doughnut, radar, scatter, area.
 * Anything else -> null (caller falls back to SVG screenshot / PNG).
 *
 * Each mapping function returns:
 *   { chartType, data, options }
 *   - chartType : pptxgenjs ChartType enum value
 *   - data      : pptxgenjs chart data array
 *   - options   : pptxgenjs chart options (colors, labels, etc.)
 *
 * The caller then does:
 *   slide.addChart(chartType, data, { x, y, w, h, ...options })
 */

/**
 * Pick the primary series type. ECharts options can have multiple series with
 * mixed types; we take the first one's type as the driver. Area charts are
 * identified by `series[0].type === 'line'` plus `series[0].areaStyle`.
 */
function detectType(option) {
  const series = option.series;
  if (!series) return null;
  const s0 = Array.isArray(series) ? series[0] : series;
  if (!s0 || !s0.type) return null;
  if (s0.type === 'line' && s0.areaStyle) return 'area';
  if (s0.type === 'pie') {
    const r = s0.radius;
    if (Array.isArray(r) && r.length === 2) return 'doughnut';
    return 'pie';
  }
  return s0.type;
}

/**
 * Helper: coerce an ECharts category axis data into string labels.
 */
function extractCategoryLabels(option) {
  const xAxis = Array.isArray(option.xAxis) ? option.xAxis[0] : option.xAxis;
  if (xAxis && Array.isArray(xAxis.data)) return xAxis.data.map(String);
  const yAxis = Array.isArray(option.yAxis) ? option.yAxis[0] : option.yAxis;
  if (yAxis && Array.isArray(yAxis.data)) return yAxis.data.map(String);
  return [];
}

/**
 * Best-effort color extraction from a series item.
 */
function getSeriesColor(s) {
  if (s.itemStyle && s.itemStyle.color && typeof s.itemStyle.color === 'string') {
    return s.itemStyle.color.replace('#', '');
  }
  if (s.color && typeof s.color === 'string') return s.color.replace('#', '');
  return null;
}

function allSeries(option) {
  const series = option.series;
  if (!series) return [];
  return Array.isArray(series) ? series : [series];
}

/**
 * Extract a list of numbers from an ECharts series data item. Data can be:
 *   [1, 2, 3]
 *   [{value: 1}, {value: 2}]
 *   [[x1, y1], [x2, y2]]  (for scatter)
 */
function toNumbers(arr) {
  return arr.map(v => {
    if (typeof v === 'number') return v;
    if (v && typeof v === 'object' && 'value' in v) {
      const x = v.value;
      return typeof x === 'number' ? x : (Array.isArray(x) ? x[x.length - 1] : 0);
    }
    return 0;
  });
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

  const colors = series.map(getSeriesColor).filter(Boolean);
  const options = {
    barDir: series[0].orient === 'horizontal' ? 'bar' : 'col',
    showLegend: series.length > 1,
    chartColors: colors.length > 0 ? colors : undefined,
    showValue: false,
  };

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

  const colors = series.map(getSeriesColor).filter(Boolean);
  const options = {
    lineSmooth: series.some(s => s.smooth),
    showLegend: series.length > 1,
    chartColors: colors.length > 0 ? colors : undefined,
  };
  return { chartType: ChartType.line, data, options };
}

function mapArea(option, ChartType) {
  // Area = line + areaStyle. pptxgenjs has ChartType.area
  const labels = extractCategoryLabels(option);
  const series = allSeries(option).filter(s => s.type === 'line' && s.areaStyle);
  if (series.length === 0 || labels.length === 0) return null;

  const data = series.map(s => ({
    name: s.name || 'Series',
    labels,
    values: toNumbers(s.data || []),
  }));

  const colors = series.map(getSeriesColor).filter(Boolean);
  return {
    chartType: ChartType.area,
    data,
    options: {
      showLegend: series.length > 1,
      chartColors: colors.length > 0 ? colors : undefined,
    },
  };
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
  // Collect per-slice colors if provided on items
  const sliceColors = items.map(d => {
    if (d.itemStyle && typeof d.itemStyle.color === 'string') return d.itemStyle.color.replace('#', '');
    return null;
  }).filter(Boolean);

  const options = {
    showLegend: true,
    chartColors: sliceColors.length === items.length ? sliceColors : undefined,
    dataLabelFormatCode: '0"%"',
  };
  if (hollow) options.holeSize = 50;

  return {
    chartType: hollow ? ChartType.doughnut : ChartType.pie,
    data,
    options,
  };
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
    let values;
    let name = 'Series';
    if (Array.isArray(item)) values = item.map(v => Number(v) || 0);
    else if (item && typeof item === 'object') {
      values = Array.isArray(item.value) ? item.value.map(v => Number(v) || 0) : [];
      name = item.name || name;
    } else values = [];
    return { name, labels, values };
  }).filter(d => d.values.length === labels.length);

  if (data.length === 0) return null;
  return {
    chartType: ChartType.radar,
    data,
    options: { radarStyle: 'standard', showLegend: data.length > 1 },
  };
}

function mapScatter(option, ChartType) {
  const series = allSeries(option).filter(s => s.type === 'scatter');
  if (series.length === 0) return null;

  // pptxgenjs scatter expects: [{name:'X-Axis', values:[x1,x2,...]},
  //                             {name:'series 1', values:[y1,y2,...]}, ...]
  const xValues = [];
  const yLists = [];
  for (const s of series) {
    const pairs = (s.data || []).filter(d => Array.isArray(d) && d.length >= 2);
    if (pairs.length === 0) continue;
    // Use first series' x values as the shared X axis
    if (xValues.length === 0) {
      for (const p of pairs) xValues.push(Number(p[0]) || 0);
    }
    yLists.push({ name: s.name || 'Series', values: pairs.map(p => Number(p[1]) || 0) });
  }
  if (xValues.length === 0 || yLists.length === 0) return null;

  const data = [{ name: 'X-Axis', values: xValues }, ...yLists];
  return {
    chartType: ChartType.scatter,
    data,
    options: { showLegend: yLists.length > 1 },
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Convert an ECharts option into pptxgenjs chart args.
 * @param {Object} option - ECharts option (as returned by chart.getOption()).
 * @param {Object} ChartType - pptxgenjs ChartType enum (passed in to avoid
 *                             importing pptxgenjs from this leaf module).
 * @returns {Object|null} - {chartType, data, options} or null if unsupported.
 */
export function echartsOptionToPptx(option, ChartType) {
  if (!option || !ChartType) return null;
  const type = detectType(option);
  if (!type) return null;

  switch (type) {
    case 'bar':     return mapBar(option, ChartType);
    case 'line':    return mapLine(option, ChartType);
    case 'area':    return mapArea(option, ChartType);
    case 'pie':     return mapPie(option, ChartType, false);
    case 'doughnut':return mapPie(option, ChartType, true);
    case 'radar':   return mapRadar(option, ChartType);
    case 'scatter': return mapScatter(option, ChartType);
    default:        return null;
  }
}
