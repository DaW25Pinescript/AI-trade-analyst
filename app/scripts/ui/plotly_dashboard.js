const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: false,
  scrollZoom: false,
  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
};

function getContainer(id) {
  const container = document.getElementById(id);
  return container || null;
}

function renderEmptyState(container, message) {
  container.innerHTML = `<p class="hint">${message}</p>`;
}

function prepareContainer(container) {
  if (window.Plotly?.purge) {
    try {
      window.Plotly.purge(container);
    } catch {
      // Best effort cleanup only.
    }
  }
}

function renderPlot(container, data, layout) {
  if (typeof window.Plotly?.react === 'function') {
    window.Plotly.react(container, data, layout, PLOTLY_CONFIG);
    return;
  }
  window.Plotly.newPlot(container, data, layout, PLOTLY_CONFIG);
}

function isValidTimestamp(value) {
  if (!value) return false;
  const date = new Date(value);
  return !Number.isNaN(date.getTime());
}

export function isPlotlyAvailable() {
  return typeof window.Plotly === 'object' && window.Plotly !== null;
}

export function renderHeatmapPlotly(metrics) {
  const container = getContainer('dashboardHeatmap');
  if (!container) return;

  const heatmapRows = Array.isArray(metrics?.heatmap) ? metrics.heatmap : [];
  const x = Array.isArray(metrics?.heatmapSessions) ? metrics.heatmapSessions : [];
  const y = Array.isArray(metrics?.heatmapSetups) ? metrics.heatmapSetups : [];

  if (!heatmapRows.length || !x.length || !y.length) {
    renderEmptyState(container, 'No trade data loaded yet.');
    return;
  }

  const z = heatmapRows.map((row) => row.map((cell) => Number(cell?.count ?? 0)));
  const text = heatmapRows.map((row) => row.map((cell) => `Setup: ${cell?.setup || 'Other'}<br>Session: ${cell?.session || 'Unknown'}<br>Count: ${Number(cell?.count ?? 0)}`));

  prepareContainer(container);
  renderPlot(container, [{
    type: 'heatmap',
    x,
    y,
    z,
    text,
    hovertemplate: '%{text}<extra></extra>',
    colorscale: 'Viridis',
  }], {
    title: { text: 'Setup Type × Session', font: { size: 14 } },
    margin: { t: 42, r: 16, b: 46, l: 90 },
    xaxis: { title: { text: 'Session' } },
    yaxis: { title: { text: 'Setup' }, automargin: true },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
  });
}

export function renderEquityCurvePlotly(metrics) {
  const container = getContainer('dashboardEquityCurve');
  if (!container) return;

  const points = Array.isArray(metrics?.equityCurve) ? metrics.equityCurve : [];
  if (!points.length) {
    renderEmptyState(container, 'No closed trades yet — equity curve appears after AAR outcomes are recorded.');
    return;
  }

  const useTimestamps = points.every((point) => isValidTimestamp(point?.timestamp));
  const x = points.map((point, idx) => (useTimestamps ? point.timestamp : idx + 1));
  const y = points.map((point) => Number(point?.cumulativeR ?? 0));

  prepareContainer(container);
  renderPlot(container, [{
    type: 'scatter',
    mode: 'lines+markers',
    x,
    y,
    line: { width: 2 },
    marker: { size: 5 },
    customdata: points.map((point) => [
      point?.ticketId || 'UNKNOWN',
      point?.timestamp || 'N/A',
      Number(point?.r ?? 0),
      Number(point?.cumulativeR ?? 0),
    ]),
    hovertemplate: 'Ticket: %{customdata[0]}<br>Timestamp: %{customdata[1]}<br>Trade R: %{customdata[2]:.2f}<br>Cumulative R: %{customdata[3]:.2f}<extra></extra>',
    name: 'Cumulative R',
  }], {
    title: { text: 'Equity Curve (R-Based)', font: { size: 14 } },
    margin: { t: 42, r: 20, b: 44, l: 52 },
    xaxis: {
      title: { text: useTimestamps ? 'Timestamp' : 'Trade #' },
      type: useTimestamps ? 'date' : 'linear',
    },
    yaxis: { title: { text: 'Cumulative R' }, zeroline: true, zerolinewidth: 1.5 },
    shapes: [{
      type: 'line',
      xref: 'paper',
      yref: 'y',
      x0: 0,
      x1: 1,
      y0: 0,
      y1: 0,
      line: { color: '#999', width: 1, dash: 'dot' },
    }],
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
  });
}

export function renderPeriodBreakdownPlotly(containerId, rows, title) {
  const container = getContainer(containerId);
  if (!container) return;

  const safeRows = Array.isArray(rows) ? rows : [];
  if (!safeRows.length) {
    renderEmptyState(container, 'No closed trades available for this period.');
    return;
  }

  const periods = safeRows.map((row) => row?.period || 'Unknown');
  const netR = safeRows.map((row) => Number(row?.netR ?? 0));
  const avgR = safeRows.map((row) => Number(row?.avgR ?? 0));

  prepareContainer(container);
  renderPlot(container, [
    { type: 'bar', name: 'Net R', x: periods, y: netR },
    { type: 'bar', name: 'Avg R', x: periods, y: avgR },
  ], {
    title: { text: title, font: { size: 14 } },
    barmode: 'group',
    margin: { t: 42, r: 20, b: 48, l: 52 },
    xaxis: { title: { text: 'Period' } },
    yaxis: { title: { text: 'R' }, zeroline: true, zerolinewidth: 1.5 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
  });
}

export async function capturePlotlyChartsForExport() {
  if (!isPlotlyAvailable()) return null;

  const overrides = {};
  const tasks = [
    { id: 'dashboardHeatmap', format: 'png', scale: 1.5 },
    { id: 'dashboardEquityCurve', format: 'png', scale: 1.5 },
    { id: 'dashboardMonthlyBreakdown', format: 'png', scale: 1.3 },
    { id: 'dashboardQuarterlyBreakdown', format: 'png', scale: 1.3 },
  ];

  await Promise.all(tasks.map(async ({ id, format, scale }) => {
    const gd = document.getElementById(id);
    if (!gd || !gd.data) return;

    try {
      const url = await window.Plotly.toImage(gd, {
        format,
        width: Math.max(1, Math.round(gd.clientWidth * scale)),
        height: Math.max(1, Math.round(gd.clientHeight * scale)),
      });
      overrides[id] = `<img src="${url}" style="max-width:100%;height:auto;display:block;margin:1em auto;" />`;
    } catch (err) {
      console.warn(`Plotly.toImage failed for ${id}:`, err);
    }
  }));

  return Object.keys(overrides).length > 0 ? overrides : null;
}
