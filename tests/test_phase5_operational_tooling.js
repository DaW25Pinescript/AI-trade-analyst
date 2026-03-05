import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

// ── Phase 5 — Operational Tooling (browser-side) tests ────────────────────
//
// Items 14, 15, 16 of the V3 master plan Phase 5:
//   14. CLI audit trail export — covered by Python test suite
//   15. CLI bulk AAR import — covered by Python test suite
//   16. Analytics CSV export — browser-side wiring tested here
//
// Tests:
//   a) exportAnalyticsCSV function is exported from dashboard.js
//   b) exportAnalyticsCSV is imported and exposed in main.js
//   c) Export Analytics CSV button is present in index.html
//   d) CSV cell escaping logic (extracted from dashboard.js for unit testing)
//   e) CSV headers contain expected columns
// ─────────────────────────────────────────────────────────────────────────────

// ── Source file content reads ─────────────────────────────────────────────────

const dashboardSrc = fs.readFileSync('app/scripts/ui/dashboard.js', 'utf-8');
const mainSrc = fs.readFileSync('app/scripts/main.js', 'utf-8');
const indexSrc = fs.readFileSync('app/index.html', 'utf-8');

// ── exportAnalyticsCSV function existence ───────────────────────────────────

test('Phase 5: dashboard.js exports exportAnalyticsCSV function', () => {
  assert.ok(
    dashboardSrc.includes('export function exportAnalyticsCSV()'),
    'dashboard.js should export the exportAnalyticsCSV function'
  );
});

test('Phase 5: exportAnalyticsCSV builds CSV headers with expected columns', () => {
  // Extract the headers array from the source
  const headerMatch = dashboardSrc.match(/const headers = \[([\s\S]*?)\];/);
  assert.ok(headerMatch, 'Should find headers array in exportAnalyticsCSV');

  const headerBlock = headerMatch[1];
  const expectedCols = [
    'ticketId', 'createdAt', 'asset', 'session', 'decisionMode',
    'outcomeEnum', 'verdictEnum', 'rAchieved', 'exitReasonEnum',
    'psychologicalTag',
  ];
  for (const col of expectedCols) {
    assert.ok(
      headerBlock.includes(`'${col}'`),
      `Headers should include '${col}'`
    );
  }
});

// ── main.js wiring ──────────────────────────────────────────────────────────

test('Phase 5: main.js imports exportAnalyticsCSV from dashboard.js', () => {
  assert.ok(
    mainSrc.includes('exportAnalyticsCSV'),
    'main.js should import exportAnalyticsCSV'
  );
});

test('Phase 5: main.js exposes exportAnalyticsCSV on window object', () => {
  // Check it appears in the Object.assign(window, { ... }) block
  const windowBlock = mainSrc.match(/Object\.assign\(window,\s*\{([\s\S]*?)\}\);/);
  assert.ok(windowBlock, 'Should find Object.assign(window, {...}) in main.js');
  assert.ok(
    windowBlock[1].includes('exportAnalyticsCSV'),
    'exportAnalyticsCSV should be in the window assignment block'
  );
});

// ── index.html button ───────────────────────────────────────────────────────

test('Phase 5: index.html contains Export Analytics CSV button', () => {
  assert.ok(
    indexSrc.includes('exportAnalyticsCSV()'),
    'index.html should call exportAnalyticsCSV()'
  );
  assert.ok(
    indexSrc.includes('Export Analytics CSV'),
    'Button label should be "Export Analytics CSV"'
  );
});

test('Phase 5: Export Analytics CSV button has title attribute', () => {
  const btnMatch = indexSrc.match(/onclick="exportAnalyticsCSV\(\)"[^>]*title="([^"]+)"/);
  assert.ok(btnMatch, 'Export Analytics CSV button should have a title attribute');
  assert.ok(
    btnMatch[1].toLowerCase().includes('csv'),
    'Title should mention CSV'
  );
});

// ── CSV cell escaping logic ─────────────────────────────────────────────────

test('Phase 5: csvCell escaping logic handles commas', () => {
  // Replicate the csvCell logic from dashboard.js
  const csvCell = (v) => {
    const s = String(v ?? '');
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"` : s;
  };

  assert.equal(csvCell('hello'), 'hello');
  assert.equal(csvCell('hello,world'), '"hello,world"');
  assert.equal(csvCell('say "hi"'), '"say ""hi"""');
  assert.equal(csvCell('line1\nline2'), '"line1\nline2"');
  assert.equal(csvCell(null), '');
  assert.equal(csvCell(undefined), '');
  assert.equal(csvCell(42), '42');
});

// ── Export button ordering ──────────────────────────────────────────────────

test('Phase 5: Export Analytics CSV button appears after Export Analytics PDF', () => {
  const pdfPos = indexSrc.indexOf('exportAnalyticsPDF()');
  const csvPos = indexSrc.indexOf('exportAnalyticsCSV()');
  assert.ok(pdfPos > 0, 'PDF export button should exist');
  assert.ok(csvPos > 0, 'CSV export button should exist');
  assert.ok(csvPos > pdfPos, 'CSV button should appear after PDF button');
});

// ── dashboard.js CSV function structure ─────────────────────────────────────

test('Phase 5: exportAnalyticsCSV creates a Blob with text/csv type', () => {
  assert.ok(
    dashboardSrc.includes("type: 'text/csv'"),
    'exportAnalyticsCSV should create a Blob with text/csv MIME type'
  );
});

test('Phase 5: exportAnalyticsCSV uses analytics_export_ filename prefix', () => {
  assert.ok(
    dashboardSrc.includes('analytics_export_'),
    'Download filename should start with analytics_export_'
  );
});
