import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const tickets = JSON.parse(fs.readFileSync(new URL('./fixtures/tickets_small_set.json', import.meta.url), 'utf8'));
const aars = JSON.parse(fs.readFileSync(new URL('./fixtures/aars_small_set.json', import.meta.url), 'utf8'));

function computeCoreMetrics(aarRows) {
  const closed = aarRows.filter((row) => ['WIN', 'LOSS', 'BREAKEVEN'].includes(row.outcomeEnum));
  const wins = closed.filter((row) => row.outcomeEnum === 'WIN');
  const losses = closed.filter((row) => row.outcomeEnum === 'LOSS');

  const winRate = closed.length ? wins.length / closed.length : 0;
  const lossRate = closed.length ? losses.length / closed.length : 0;
  const avgWin = wins.length ? wins.reduce((acc, row) => acc + row.rAchieved, 0) / wins.length : 0;
  const avgLossMagnitude = losses.length
    ? Math.abs(losses.reduce((acc, row) => acc + row.rAchieved, 0) / losses.length)
    : 0;
  const expectancy = (winRate * avgWin) - (lossRate * avgLossMagnitude);

  return { winRate, expectancy };
}

function buildCalibrationInputs(ticketRows, aarRows) {
  const ticketById = new Map(ticketRows.map((row) => [row.ticketId, row]));
  return aarRows
    .filter((row) => ['WIN', 'LOSS', 'BREAKEVEN'].includes(row.outcomeEnum))
    .map((row) => ({
      ticketId: row.ticketId,
      confluenceScore: ticketById.get(row.ticketId)?.checklist?.confluenceScore ?? null,
      revisedConfidence: row.revisedConfidence,
      outcomeEnum: row.outcomeEnum,
      rAchieved: row.rAchieved
    }));
}

test('core metrics return expected win rate and expectancy', () => {
  const metrics = computeCoreMetrics(aars);
  assert.equal(metrics.winRate, 1 / 3);
  assert.equal(metrics.expectancy, (1 / 3) * 1.5 - (1 / 3) * 1);
});

test('calibration inputs align confluence/revisedConfidence with each closed trade', () => {
  const inputs = buildCalibrationInputs(tickets, aars);
  assert.deepEqual(inputs, [
    { ticketId: 'T1', confluenceScore: 9, revisedConfidence: 4, outcomeEnum: 'WIN', rAchieved: 1.5 },
    { ticketId: 'T2', confluenceScore: 4, revisedConfidence: 2, outcomeEnum: 'LOSS', rAchieved: -1 },
    { ticketId: 'T3', confluenceScore: 6, revisedConfidence: 3, outcomeEnum: 'BREAKEVEN', rAchieved: 0 }
  ]);
});
