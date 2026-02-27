import test from 'node:test';
import assert from 'node:assert/strict';
import { computeMetrics, parseBackupEntries } from '../app/scripts/metrics/metrics_engine.js';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeBackup(ticketOverrides, aarOverrides) {
  const ticket = {
    ticketId: 'TX',
    createdAt: '2026-02-24T09:00:00.000Z',
    checklist: { edgeTag: 'Pullback', confluenceScore: 8 },
    ...ticketOverrides,
  };
  const aar = {
    ticketId: ticket.ticketId,
    outcomeEnum: 'WIN',
    rAchieved: 1.5,
    revisedConfidence: 4,
    psychologicalTag: 'CALM',
    ...aarOverrides,
  };
  return { ticket, aar };
}

// ── parseBackupEntries ────────────────────────────────────────────────────────

test('parseBackupEntries: returns paired entries from a flat array', () => {
  const raw = [
    { ticket: { ticketId: 'A' }, aar: { ticketId: 'A', outcomeEnum: 'WIN' } },
    { ticket: { ticketId: 'B' }, aar: { ticketId: 'B', outcomeEnum: 'LOSS' } },
  ];
  const result = parseBackupEntries(raw);
  assert.equal(result.length, 2);
  assert.equal(result[0].ticket.ticketId, 'A');
  assert.equal(result[1].aar.outcomeEnum, 'LOSS');
});

test('parseBackupEntries: drops entries missing ticket or aar', () => {
  const raw = [
    { ticket: { ticketId: 'A' }, aar: null },
    { ticket: null, aar: { ticketId: 'B' } },
    { ticket: { ticketId: 'C' }, aar: { ticketId: 'C', outcomeEnum: 'WIN' } },
  ];
  const result = parseBackupEntries(raw);
  assert.equal(result.length, 1);
  assert.equal(result[0].ticket.ticketId, 'C');
});

test('parseBackupEntries: empty input returns empty array', () => {
  assert.deepEqual(parseBackupEntries([]), []);
  assert.deepEqual(parseBackupEntries(), []);
});

// ── computeMetrics: basic counts ─────────────────────────────────────────────

test('computeMetrics: empty input returns all-zero metrics', () => {
  const m = computeMetrics([], []);
  assert.equal(m.tradeCount, 0);
  assert.equal(m.closedCount, 0);
  assert.equal(m.winRate, 0);
  assert.equal(m.avgR, 0);
  assert.equal(m.expectancy, 0);
  assert.equal(m.avgTradesPerDay, 0);
  assert.equal(m.psychologicalLeakR, 0);
  assert.deepEqual(m.heatmap, []);
});

test('computeMetrics: counts total and closed trades correctly', () => {
  const win   = makeBackup({ ticketId: 'T1' }, { outcomeEnum: 'WIN',   rAchieved: 2 });
  const loss  = makeBackup({ ticketId: 'T2' }, { outcomeEnum: 'LOSS',  rAchieved: -1 });
  const open  = makeBackup({ ticketId: 'T3' }, { outcomeEnum: 'OPEN',  rAchieved: 0 });

  const tickets = [win.ticket, loss.ticket, open.ticket];
  const aars    = [win.aar,    loss.aar,    open.aar];
  const m = computeMetrics(tickets, aars);

  assert.equal(m.tradeCount, 3);
  assert.equal(m.closedCount, 2);    // WIN + LOSS; OPEN is not closed
});

// ── computeMetrics: win rate ─────────────────────────────────────────────────

test('computeMetrics: win rate is wins / closed trades', () => {
  const entries = [
    makeBackup({ ticketId: 'T1' }, { outcomeEnum: 'WIN',       rAchieved:  2 }),
    makeBackup({ ticketId: 'T2' }, { outcomeEnum: 'WIN',       rAchieved:  1 }),
    makeBackup({ ticketId: 'T3' }, { outcomeEnum: 'LOSS',      rAchieved: -1 }),
    makeBackup({ ticketId: 'T4' }, { outcomeEnum: 'BREAKEVEN', rAchieved:  0 }),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  assert.equal(m.winRate, 2 / 4);       // 2 wins out of 4 closed
  assert.equal(m.closedCount, 4);
});

// ── computeMetrics: avgR and expectancy ─────────────────────────────────────

test('computeMetrics: avgR is simple average of closed R values', () => {
  const entries = [
    makeBackup({ ticketId: 'T1' }, { outcomeEnum: 'WIN',  rAchieved:  2 }),
    makeBackup({ ticketId: 'T2' }, { outcomeEnum: 'LOSS', rAchieved: -1 }),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  assert.equal(m.avgR, 0.5);
});

// ── computeMetrics: psychological leakage R ──────────────────────────────────

test('computeMetrics: psychologicalLeakR averages absolute R of psych-tagged losses', () => {
  const entries = [
    makeBackup({ ticketId: 'T1' }, { outcomeEnum: 'WIN',  rAchieved:  2,  psychologicalTag: 'CALM'   }),
    makeBackup({ ticketId: 'T2' }, { outcomeEnum: 'LOSS', rAchieved: -1,  psychologicalTag: 'FOMO'   }),
    makeBackup({ ticketId: 'T3' }, { outcomeEnum: 'LOSS', rAchieved: -2,  psychologicalTag: 'REVENGE' }),
    makeBackup({ ticketId: 'T4' }, { outcomeEnum: 'LOSS', rAchieved: -0.5, psychologicalTag: 'CALM'   }),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  // Only FOMO (-1) and REVENGE (-2) count as psych leakage; avg |R| = (1 + 2) / 2 = 1.5
  assert.equal(m.psychologicalLeakR, 1.5);
});

test('computeMetrics: psychologicalLeakR is 0 when no psych-tagged losses', () => {
  const entries = [
    makeBackup({ ticketId: 'T1' }, { outcomeEnum: 'WIN',  rAchieved:  2,  psychologicalTag: 'CALM' }),
    makeBackup({ ticketId: 'T2' }, { outcomeEnum: 'LOSS', rAchieved: -1,  psychologicalTag: 'CALM' }),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  assert.equal(m.psychologicalLeakR, 0);
});

// ── computeMetrics: heatmap ───────────────────────────────────────────────────

test('computeMetrics: heatmap groups by edgeTag and derived session', () => {
  // T1 and T2 share edgeTag 'Pullback'; T1 is NY Open hour (13 UTC), T2 is London Open (07 UTC)
  const entries = [
    makeBackup({ ticketId: 'T1', createdAt: '2026-02-24T13:30:00.000Z', checklist: { edgeTag: 'Pullback', confluenceScore: 9 } },
               { outcomeEnum: 'WIN', rAchieved: 1 }),
    makeBackup({ ticketId: 'T2', createdAt: '2026-02-24T07:00:00.000Z', checklist: { edgeTag: 'Pullback', confluenceScore: 7 } },
               { outcomeEnum: 'LOSS', rAchieved: -1 }),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  assert.ok(m.heatmapSetups.includes('Pullback'));
  assert.ok(m.heatmapSessions.includes('NY Open') || m.heatmapSessions.includes('London Open'));

  // Each trade should appear exactly once in the grid
  const totalCells = m.heatmap.flat().reduce((sum, c) => sum + c.count, 0);
  assert.equal(totalCells, 2);
});

// ── computeMetrics: trade frequency ─────────────────────────────────────────

test('computeMetrics: avgTradesPerDay divides by unique calendar days', () => {
  const entries = [
    makeBackup({ ticketId: 'T1', createdAt: '2026-02-24T09:00:00.000Z' }, {}),
    makeBackup({ ticketId: 'T2', createdAt: '2026-02-24T14:00:00.000Z' }, {}),
    makeBackup({ ticketId: 'T3', createdAt: '2026-02-25T09:00:00.000Z' }, {}),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  // 3 trades over 2 unique days = 1.5 trades/day
  assert.equal(m.avgTradesPerDay, 1.5);
});

// ── computeMetrics: calibration output ───────────────────────────────────────

test('computeMetrics: calibration contains closed trades with correct fields', () => {
  const entries = [
    makeBackup(
      { ticketId: 'T1', checklist: { edgeTag: 'Pullback', confluenceScore: 9 } },
      { outcomeEnum: 'WIN', rAchieved: 1.5, revisedConfidence: 4 }
    ),
    makeBackup(
      { ticketId: 'T2', checklist: { edgeTag: 'Other', confluenceScore: 5 } },
      { outcomeEnum: 'LOSS', rAchieved: -1, revisedConfidence: 2 }
    ),
  ];
  const tickets = entries.map((e) => e.ticket);
  const aars    = entries.map((e) => e.aar);
  const m = computeMetrics(tickets, aars);

  assert.equal(m.calibration.length, 2);
  assert.deepEqual(m.calibration[0], { ticketId: 'T1', confluenceScore: 9, revisedConfidence: 4, outcomeEnum: 'WIN', rAchieved: 1.5 });
  assert.deepEqual(m.calibration[1], { ticketId: 'T2', confluenceScore: 5, revisedConfidence: 2, outcomeEnum: 'LOSS', rAchieved: -1 });
});


test('computeMetrics: equityCurve tracks cumulative R in chronological order', () => {
  const entries = [
    makeBackup({ ticketId: 'T2', createdAt: '2026-02-24T12:00:00.000Z' }, { outcomeEnum: 'LOSS', rAchieved: -1 }),
    makeBackup({ ticketId: 'T1', createdAt: '2026-02-24T09:00:00.000Z' }, { outcomeEnum: 'WIN', rAchieved: 2 }),
    makeBackup({ ticketId: 'T3', createdAt: '2026-02-25T09:00:00.000Z' }, { outcomeEnum: 'WIN', rAchieved: 1.5 }),
  ];
  const m = computeMetrics(entries.map((e) => e.ticket), entries.map((e) => e.aar));

  assert.equal(m.equityCurve.length, 3);
  assert.deepEqual(m.equityCurve.map((p) => p.ticketId), ['T1', 'T2', 'T3']);
  assert.deepEqual(m.equityCurve.map((p) => p.cumulativeR), [2, 1, 2.5]);
});

test('computeMetrics: monthly and quarterly breakdown aggregate closed outcomes', () => {
  const entries = [
    makeBackup({ ticketId: 'JAN1', createdAt: '2026-01-05T10:00:00.000Z' }, { outcomeEnum: 'WIN', rAchieved: 1 }),
    makeBackup({ ticketId: 'JAN2', createdAt: '2026-01-18T10:00:00.000Z' }, { outcomeEnum: 'LOSS', rAchieved: -0.5 }),
    makeBackup({ ticketId: 'APR1', createdAt: '2026-04-03T10:00:00.000Z' }, { outcomeEnum: 'WIN', rAchieved: 2 }),
  ];
  const m = computeMetrics(entries.map((e) => e.ticket), entries.map((e) => e.aar));

  assert.deepEqual(m.monthlyBreakdown, [
    { period: '2026-01', trades: 2, wins: 1, netR: 0.5, winRate: 0.5, avgR: 0.25 },
    { period: '2026-04', trades: 1, wins: 1, netR: 2, winRate: 1, avgR: 2 },
  ]);

  assert.deepEqual(m.quarterlyBreakdown, [
    { period: '2026-Q1', trades: 2, wins: 1, netR: 0.5, winRate: 0.5, avgR: 0.25 },
    { period: '2026-Q2', trades: 1, wins: 1, netR: 2, winRate: 1, avgR: 2 },
  ]);
});
