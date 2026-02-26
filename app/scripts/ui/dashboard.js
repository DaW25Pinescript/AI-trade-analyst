import { computeMetrics, parseBackupEntries } from '../metrics/metrics_engine.js';

function parseUploadedPayload(raw) {
  const parsed = JSON.parse(raw);
  if (Array.isArray(parsed)) return parsed;
  if (parsed?.ticket && parsed?.aar) return [parsed];
  if (parsed?.payload?.ticket && parsed?.payload?.aar) return [parsed.payload];
  return [];
}

function formatPct(n) {
  return `${(n * 100).toFixed(1)}%`;
}

function formatNum(n) {
  return Number.isFinite(n) ? n.toFixed(2) : '0.00';
}

function renderHeatmap(metrics) {
  const table = document.getElementById('dashboardHeatmap');
  if (!table) return;
  if (!metrics.heatmap.length) {
    table.innerHTML = '<p class="hint">No trade data loaded yet.</p>';
    return;
  }

  const maxCount = Math.max(1, ...metrics.heatmap.flat().map((cell) => cell.count));
  const header = `<tr><th>Setup \ Session</th>${metrics.heatmapSessions.map((s) => `<th>${s}</th>`).join('')}</tr>`;
  const rows = metrics.heatmap.map((row, rowIndex) => {
    const setup = metrics.heatmapSetups[rowIndex] || 'Other';
    const cells = row.map((cell) => {
      const alpha = 0.15 + (cell.count / maxCount) * 0.5;
      return `<td style="background: rgba(34,197,94,${alpha.toFixed(3)});">${cell.count}</td>`;
    }).join('');
    return `<tr><th>${setup}</th>${cells}</tr>`;
  }).join('');

  table.innerHTML = `<table class="heatmap-table">${header}${rows}</table>`;
}

function renderStats(metrics) {
  const mapping = {
    dashTrades: metrics.tradeCount,
    dashClosedTrades: metrics.closedCount,
    dashWinRate: formatPct(metrics.winRate),
    dashAvgR: formatNum(metrics.avgR),
    dashExpectancy: formatNum(metrics.expectancy),
    dashTradeFreq: formatNum(metrics.avgTradesPerDay),
    dashPsychLeak: formatNum(metrics.psychologicalLeakR),
  };

  Object.entries(mapping).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value);
  });

  renderHeatmap(metrics);
}

export function initDashboard() {
  const input = document.getElementById('dashboardJsonFiles');
  if (!input) return;

  input.addEventListener('change', async (event) => {
    const files = Array.from(event.target.files || []);
    const allEntries = [];

    for (const file of files) {
      const raw = await file.text();
      try {
        const entries = parseUploadedPayload(raw);
        allEntries.push(...entries);
      } catch {
        // Skip malformed files silently; dashboard is best-effort.
      }
    }

    const normalized = parseBackupEntries(allEntries);
    const tickets = normalized.map(({ ticket }) => ticket);
    const aars = normalized.map(({ aar }) => aar);
    const metrics = computeMetrics(tickets, aars);
    renderStats(metrics);
  });
}
