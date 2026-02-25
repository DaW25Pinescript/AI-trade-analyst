import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const html = fs.readFileSync(new URL('../app/index.html', import.meta.url), 'utf8');
const ticketSchema = JSON.parse(fs.readFileSync(new URL('../docs/schema/ticket.schema.json', import.meta.url), 'utf8'));

function extractSelectValues(sourceHtml, id) {
  const selectMatch = sourceHtml.match(new RegExp(`<select\\s+id=["']${id}["'][\\s\\S]*?<\\/select>`));
  assert.ok(selectMatch, `select#${id} should exist`);

  const values = [...selectMatch[0].matchAll(/<option([^>]*)>([\s\S]*?)<\/option>/g)].map((m) => {
    const attrs = m[1] || '';
    const textContent = m[2].replace(/<[^>]+>/g, '').trim();
    const valueMatch = attrs.match(/value="([^"]*)"/);
    return valueMatch ? valueMatch[1] : textContent;
  });
  assert.ok(values.length > 0, `select#${id} should define option values`);
  return values;
}

test('G2 form select options remain aligned with ticket schema enums', () => {
  assert.deepEqual(extractSelectValues(html, 'decisionMode'), ticketSchema.properties.decisionMode.enum);
  assert.deepEqual(extractSelectValues(html, 'ticketType'), ticketSchema.properties.ticketType.enum);
  assert.deepEqual(extractSelectValues(html, 'entryType'), ticketSchema.properties.entryType.enum);
  assert.deepEqual(extractSelectValues(html, 'entryTrigger'), ticketSchema.properties.entryTrigger.enum);
  assert.deepEqual(extractSelectValues(html, 'confTF'), ticketSchema.properties.confirmationTF.enum);
  assert.deepEqual(extractSelectValues(html, 'timeInForce'), ticketSchema.properties.timeInForce.enum);
  assert.deepEqual(extractSelectValues(html, 'stopLogic'), ticketSchema.properties.stop.properties.logic.enum);
  assert.deepEqual(extractSelectValues(html, 'waitReason'), ticketSchema.properties.gate.properties.waitReasonCode.enum);
});

test('G2 form maxAttempts options are within schema bounds', () => {
  const values = extractSelectValues(html, 'maxAttempts').map((value) => Number.parseInt(value, 10));
  assert.deepEqual(values, [1, 2]);

  const schema = ticketSchema.properties.maxAttempts;
  values.forEach((value) => {
    assert.ok(Number.isInteger(value));
    assert.ok(value >= schema.minimum && value <= schema.maximum);
  });
});
