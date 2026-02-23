import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const tickets = JSON.parse(fs.readFileSync(new URL('./fixtures/tickets_small_set.json', import.meta.url), 'utf8'));

function isChecklistComplete(checklist) {
  return Object.values(checklist).every((value) => value !== '');
}

function evaluateDeterministicGate({ checklist, noTradeToggle }) {
  if (!isChecklistComplete(checklist)) return 'INCOMPLETE';

  const isChopOrMessy = checklist.execQuality === 'Chop' || checklist.execQuality === 'Messy';
  const isConflict = checklist.ltfAlignment === 'Counter-trend' || checklist.ltfAlignment === 'Mixed';
  const isElevatedVol = checklist.volRisk === 'Elevated';

  if (isChopOrMessy && noTradeToggle) return 'WAIT';
  if (isConflict && isElevatedVol) return 'CAUTION';
  if (isConflict || isElevatedVol) return 'CAUTION';
  return 'PROCEED';
}

function parseConfluenceScore(input) {
  return Number.parseInt(input, 10) || 7;
}

test('deterministic gate outputs match fixture expectations', () => {
  for (const fixture of tickets) {
    const actual = evaluateDeterministicGate(fixture);
    assert.equal(actual, fixture.expectedGate, `Unexpected gate status for ${fixture.ticketId}`);
  }
});

test('confluence score parser uses deterministic fallback and valid integer handling', () => {
  assert.equal(parseConfluenceScore('8'), 8);
  assert.equal(parseConfluenceScore('0'), 7);
  assert.equal(parseConfluenceScore('abc'), 7);
  assert.equal(parseConfluenceScore(''), 7);
});
