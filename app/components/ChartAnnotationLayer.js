/**
 * ChartAnnotationLayer — Placeholder chart area
 *
 * Initial implementation is a placeholder. Real chart integration deferred.
 * Should look like a real analysis surface, not an empty box.
 */

/**
 * Creates a chart annotation layer placeholder.
 * @param {Object} options
 * @param {string} [options.instrument]
 * @param {string} [options.timeframe]
 * @param {string[]} [options.annotations] - Annotation labels
 * @returns {HTMLElement}
 */
export function createChartAnnotationLayer({ instrument, timeframe, annotations = [] } = {}) {
  const layer = document.createElement('div');
  layer.className = 'chart-annotation-layer';

  layer.innerHTML = `
    <div class="chart-annotation-layer__header">
      <span class="chart-annotation-layer__instrument">${instrument || '—'}</span>
      <span class="chart-annotation-layer__timeframe">${timeframe || ''}</span>
    </div>
    <div class="chart-annotation-layer__canvas">
      <div class="chart-annotation-layer__placeholder">
        <span class="text-muted">Chart area — integration pending</span>
      </div>
    </div>
    ${annotations.length > 0 ? `
      <div class="chart-annotation-layer__annotations">
        ${annotations.map(a => `<span class="badge badge--ai-prefill">${a}</span>`).join(' ')}
      </div>
    ` : ''}
  `;

  return layer;
}
