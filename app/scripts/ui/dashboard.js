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
  const container = document.getElementById('dashboardHeatmap');
  if (!container) return;
  if (!metrics.heatmap.length) {
    container.innerHTML = '<p class="hint">No trade data loaded yet.</p>';
    return;
  }

  const maxCount = Math.max(1, ...metrics.heatmap.flat().map((cell) => cell.count));
  const header = `<tr><th>Setup \u00d7 Session</th>${metrics.heatmapSessions.map((s) => `<th>${s}</th>`).join('')}</tr>`;
  const rows = metrics.heatmap.map((row, rowIndex) => {
    const setup = metrics.heatmapSetups[rowIndex] || 'Other';
    const cells = row.map((cell) => {
      const alpha = 0.15 + (cell.count / maxCount) * 0.5;
      return `<td style="background: rgba(34,197,94,${alpha.toFixed(3)});">${cell.count || '—'}</td>`;
    }).join('');
    return `<tr><th>${setup}</th>${cells}</tr>`;
  }).join('');

  container.innerHTML = `<table class="heatmap-table">${header}${rows}</table>`;
}

function renderStats(metrics) {
  const numericMapping = {
    dashAvgR: metrics.avgR,
    dashExpectancy: metrics.expectancy,
  };

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
    if (!el) return;
    el.textContent = String(value);
    const raw = numericMapping[id];
    if (raw !== undefined) {
      el.classList.toggle('stat-negative', Number.isFinite(raw) && raw < 0);
    }
  });

  const statusEl = document.getElementById('dashboardStatus');
  if (statusEl) {
    statusEl.textContent = metrics.tradeCount > 0
      ? `${metrics.tradeCount} trade(s) loaded — ${metrics.closedCount} closed with AAR.`
      : 'No trade data loaded yet.';
  }

  renderHeatmap(metrics);
}

export function initDashboard() {
  const input = document.getElementById('dashboardJsonFiles');
  if (!input) return;

  input.addEventListener('change', async (event) => {
    const files = Array.from(event.target.files || []);
    const allEntries = [];
    let skipped = 0;

    for (const file of files) {
      const raw = await file.text();
      try {
        const entries = parseUploadedPayload(raw);
        allEntries.push(...entries);
      } catch {
        skipped += 1;
      }
    }

    if (skipped > 0) {
      const statusEl = document.getElementById('dashboardStatus');
      if (statusEl) statusEl.textContent = `${skipped} file(s) skipped — invalid JSON.`;
    }

    const normalized = parseBackupEntries(allEntries);
    const tickets = normalized.map(({ ticket }) => ticket);
    const aars = normalized.map(({ aar }) => aar);
    const metrics = computeMetrics(tickets, aars);
    renderStats(metrics);
  });
}
