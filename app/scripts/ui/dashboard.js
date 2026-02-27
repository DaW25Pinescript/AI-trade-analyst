import { computeMetrics, parseBackupEntries } from '../metrics/metrics_engine.js';

// G8: module-level store so the weekly prompt generator can access loaded entries
let _loadedEntries = [];
export function getLoadedEntries() { return _loadedEntries; }

export function buildAnalyticsReportHTML(doc = document) {
  const getHTML = (id) => doc.getElementById(id)?.innerHTML || '<p>No data.</p>';
  const getText = (id, fallback = '0') => doc.getElementById(id)?.textContent?.trim() || fallback;

  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Analytics Export</title>
<style>
body{font-family:Arial,sans-serif;padding:20px;color:#111}h1{margin:0 0 12px}h2{margin:22px 0 8px;font-size:16px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0 18px}
.stat{border:1px solid #ddd;padding:10px}.stat strong{display:block;font-size:18px;margin-top:4px}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}
svg{border:1px solid #ddd;min-height:140px}
</style></head><body>
<h1>AI Trade Analyst — Performance Analytics</h1>
<p>Exported: ${new Date().toISOString()}</p>
<div class="grid">
  <div class="stat"><span>Total Trades</span><strong>${getText('dashTrades')}</strong></div>
  <div class="stat"><span>Closed Trades</span><strong>${getText('dashClosedTrades')}</strong></div>
  <div class="stat"><span>Win Rate</span><strong>${getText('dashWinRate')}</strong></div>
  <div class="stat"><span>Avg R</span><strong>${getText('dashAvgR')}</strong></div>
  <div class="stat"><span>Expectancy</span><strong>${getText('dashExpectancy')}</strong></div>
  <div class="stat"><span>Trades / Active Day</span><strong>${getText('dashTradeFreq')}</strong></div>
  <div class="stat"><span>Psychological Leakage R</span><strong>${getText('dashPsychLeak')}</strong></div>
</div>

<h2>Setup Type × Session Heatmap</h2>
${getHTML('dashboardHeatmap')}

<h2>Equity Curve (R-Based)</h2>
${getHTML('dashboardEquityCurve')}

<h2>Monthly Breakdown</h2>
${getHTML('dashboardMonthlyBreakdown')}

<h2>Quarterly Breakdown</h2>
${getHTML('dashboardQuarterlyBreakdown')}

</body></html>`;
}

export function exportAnalyticsPDF() {
  const report = buildAnalyticsReportHTML();
  const w = window.open('', '_blank');
  if (!w) { alert('Popup blocked — please allow popups and try again.'); return; }
  w.document.open();
  w.document.write(report);
  w.document.close();
  w.onload = () => { w.focus(); w.print(); };
}

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

function renderEquityCurve(metrics) {
  const container = document.getElementById('dashboardEquityCurve');
  if (!container) return;

  if (!metrics.equityCurve.length) {
    container.innerHTML = '<p class="hint">No closed trades yet — equity curve appears after AAR outcomes are recorded.</p>';
    return;
  }

  const points = metrics.equityCurve;
  const min = Math.min(0, ...points.map((p) => p.cumulativeR));
  const max = Math.max(0, ...points.map((p) => p.cumulativeR));
  const range = Math.max(1, max - min);

  const polylinePoints = points
    .map((p, idx) => {
      const x = points.length === 1 ? 0 : (idx / (points.length - 1)) * 100;
      const y = ((max - p.cumulativeR) / range) * 100;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');

  container.innerHTML = `
    <div class="curve-meta">Net R: <strong>${points.at(-1).cumulativeR.toFixed(2)}R</strong> across ${points.length} closed trade(s).</div>
    <svg class="equity-curve" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Equity curve cumulative R">
      <line x1="0" y1="0" x2="0" y2="100" class="axis" />
      <line x1="0" y1="100" x2="100" y2="100" class="axis" />
      <polyline points="${polylinePoints}" class="curve-line" />
    </svg>
  `;
}

function renderPeriodBreakdown(tableId, rows) {
  const container = document.getElementById(tableId);
  if (!container) return;

  if (!rows.length) {
    container.innerHTML = '<p class="hint">No closed trades available for this period.</p>';
    return;
  }

  const body = rows
    .map((row) => `
      <tr>
        <td>${row.period}</td>
        <td>${row.trades}</td>
        <td>${formatPct(row.winRate)}</td>
        <td>${formatNum(row.avgR)}</td>
        <td class="${row.netR < 0 ? 'stat-negative' : ''}">${formatNum(row.netR)}</td>
      </tr>
    `)
    .join('');

  container.innerHTML = `
    <table class="heatmap-table period-table">
      <thead>
        <tr>
          <th>Period</th>
          <th>Trades</th>
          <th>Win Rate</th>
          <th>Avg R</th>
          <th>Net R</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `;
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
  renderEquityCurve(metrics);
  renderPeriodBreakdown('dashboardMonthlyBreakdown', metrics.monthlyBreakdown);
  renderPeriodBreakdown('dashboardQuarterlyBreakdown', metrics.quarterlyBreakdown);
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
    _loadedEntries = normalized; // G8: expose for weekly prompt generator
    const tickets = normalized.map(({ ticket }) => ticket);
    const aars = normalized.map(({ aar }) => aar);
    const metrics = computeMetrics(tickets, aars);
    renderStats(metrics);
  });
}
