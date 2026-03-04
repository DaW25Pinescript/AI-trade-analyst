/**
 * C4 — Unified Export
 *
 * Builds a single JSON artifact containing:
 *   - ticket snapshot (same as regular JSON backup)
 *   - AAR snapshot
 *   - AI verdict + usage from the most recent bridge analysis run
 *   - Plotly dashboard chart captures (data URLs) when Plotly is available
 *
 * The export can be re-imported via import_unified.js to restore verdict state.
 */

import { state } from '../state/model.js';
import { buildBackupPayload } from './export_json_backup.js';
import { capturePlotlyChartsForExport } from '../ui/plotly_dashboard.js';

export const UNIFIED_EXPORT_VERSION = 1;

/**
 * Extract data-URL src attributes from the img-HTML strings returned by
 * capturePlotlyChartsForExport(), producing a plain { id → dataURL } map.
 * @param {Object|null} overrides  Result of capturePlotlyChartsForExport()
 * @returns {Object|null}
 */
function extractChartDataUrls(overrides) {
  if (!overrides) return null;
  const charts = {};
  let any = false;
  for (const [id, imgHtml] of Object.entries(overrides)) {
    const match = typeof imgHtml === 'string' ? imgHtml.match(/src="([^"]+)"/) : null;
    if (match) {
      charts[id] = match[1];
      any = true;
    }
  }
  return any ? charts : null;
}

/**
 * Build the unified export payload.
 * Async because Plotly chart capture is async (best-effort; never blocks).
 *
 * @returns {Promise<{ok:boolean, payload?:Object, errors?:string[]}>}
 */
export async function buildUnifiedPayload() {
  const backupResult = buildBackupPayload();
  if (!backupResult.ok) {
    return { ok: false, errors: backupResult.errors };
  }

  let dashboardCharts = null;
  try {
    const overrides = await capturePlotlyChartsForExport();
    dashboardCharts = extractChartDataUrls(overrides);
  } catch {
    // Plotly capture is best-effort — failure never blocks the export.
  }

  const payload = {
    exportVersion: UNIFIED_EXPORT_VERSION,
    exportFormat: 'unified',
    exportedAt: new Date().toISOString(),
    ticket: backupResult.payload.ticket,
    aar: backupResult.payload.aar,
    verdict: state.bridgeVerdict || null,
    dashboardCharts: dashboardCharts || null,
  };

  return { ok: true, payload };
}

/**
 * Build and immediately download the unified export as a JSON file.
 *
 * @returns {Promise<Object|null>}  The exported payload, or null on validation failure.
 */
export async function exportUnified() {
  const result = await buildUnifiedPayload();
  if (!result.ok) {
    alert(`Unified export blocked by schema validation:\n${result.errors.join('\n')}`);
    return null;
  }

  const payload = result.payload;
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `AI_Trade_Unified_${state.ticketID || 'draft'}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);

  return payload;
}
