import test from 'node:test';
import assert from 'node:assert/strict';

import { buildAnalyticsReportHTML } from '../app/scripts/ui/dashboard.js';

test('buildAnalyticsReportHTML includes key analytics values and sections', () => {
  const values = new Map([
    ['dashTrades', { textContent: '12' }],
    ['dashClosedTrades', { textContent: '10' }],
    ['dashWinRate', { textContent: '60.0%' }],
    ['dashAvgR', { textContent: '0.45' }],
    ['dashExpectancy', { textContent: '0.22' }],
    ['dashTradeFreq', { textContent: '1.50' }],
    ['dashPsychLeak', { textContent: '0.37' }],
    ['dashboardHeatmap', { innerHTML: '<table><tr><td>heat</td></tr></table>' }],
    ['dashboardEquityCurve', { innerHTML: '<svg><polyline></polyline></svg>' }],
    ['dashboardMonthlyBreakdown', { innerHTML: '<table><tr><td>Jan</td></tr></table>' }],
    ['dashboardQuarterlyBreakdown', { innerHTML: '<table><tr><td>Q1</td></tr></table>' }],
  ]);

  const doc = {
    getElementById(id) {
      return values.get(id) || null;
    }
  };

  const html = buildAnalyticsReportHTML(doc);
  assert.match(html, /Performance Analytics/);
  assert.match(html, /Total Trades<\/span><strong>12<\/strong>/);
  assert.match(html, /Closed Trades<\/span><strong>10<\/strong>/);
  assert.match(html, /Psychological Leakage R<\/span><strong>0\.37<\/strong>/);
  assert.match(html, /<h2>Equity Curve \(R-Based\)<\/h2>/);
  assert.match(html, /<td>Q1<\/td>/);
});
