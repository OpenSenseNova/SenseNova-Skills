/**
 * Collect live ECharts instances from a rendered slide.
 *
 * ECharts marks its host element with `_echarts_instance_`. Keep the legacy
 * `chart_*` selector as a fallback for older generated pages, and assign a
 * temporary id only when the host has none so the DOM IR can reference it.
 */
export function discoverEchartsInstances(
  doc = globalThis.document,
  echartsApi = globalThis.window?.echarts,
) {
  if (!doc || !echartsApi) return {};

  const result = {};
  const containers = doc.querySelectorAll('[_echarts_instance_], [id^="chart_"]');
  let syntheticIndex = 1;

  for (const el of containers) {
    try {
      const instance = echartsApi.getInstanceByDom(el);
      if (!instance) continue;

      let key = el.id;
      if (!key) {
        do {
          key = `__pptx_echart_${syntheticIndex++}`;
        } while (doc.getElementById(key));
        el.id = key;
      }

      const rect = el.getBoundingClientRect();
      result[key] = {
        option: instance.getOption(),
        bounds: {
          x: rect.left,
          y: rect.top,
          w: rect.width,
          h: rect.height,
        },
      };
    } catch {
      // Let the existing DOM/SVG fallback handle unsupported chart instances.
    }
  }

  return result;
}
