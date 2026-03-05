import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// ── HTML structure tests ──────────────────────────────────────────────────

const html = readFileSync(resolve('app/index.html'), 'utf8');

test('Phase 2b: version pill shows G12', () => {
  assert.ok(html.includes('V3 · G12'), 'version pill should read V3 · G12');
});

test('Phase 2b: operator dashboard contains session card', () => {
  assert.ok(html.includes('id="dashSessionClock"'), 'dashSessionClock element must exist');
  assert.ok(html.includes('id="dashSessionUtcClock"'), 'dashSessionUtcClock element must exist');
  assert.ok(html.includes('dash-session-card'), 'dash-session-card class must exist');
  assert.ok(html.includes('Market Sessions'), 'Market Sessions header must exist in operator dashboard');
});

test('Phase 2b: three nav tabs exist (Workflow, T.R.A.D.E., Scout)', () => {
  const navMatches = html.match(/data-view="(workflow|macro|scout)"/g);
  assert.equal(navMatches?.length, 3, 'should have exactly 3 nav view buttons');
});

test('Phase 2b: macroView section has session clock', () => {
  assert.ok(html.includes('id="sessionClock"'), 'sessionClock in macro view must exist');
});

test('Phase 2b: scoutView section has session grid and playbook', () => {
  assert.ok(html.includes('id="scoutSessionGrid"'), 'scoutSessionGrid must exist');
  assert.ok(html.includes('id="scoutPlaybook"'), 'scoutPlaybook must exist');
  assert.ok(html.includes('id="scoutAssetTable"'), 'scoutAssetTable must exist');
});

// ── CSS responsive breakpoint tests ───────────────────────────────────────

const themeCss = readFileSync(resolve('app/styles/theme.css'), 'utf8');
const macroCss = readFileSync(resolve('app/styles/macro.css'), 'utf8');
const dashCss  = readFileSync(resolve('app/styles/dashboard.css'), 'utf8');

test('Phase 2b: theme.css has 4 responsive breakpoints', () => {
  const breakpoints = themeCss.match(/@media\s*\(max-width:\s*(\d+)px\)/g) || [];
  assert.ok(breakpoints.length >= 4, `expected >= 4 breakpoints, got ${breakpoints.length}`);
  assert.ok(themeCss.includes('max-width: 860px'), '860px breakpoint');
  assert.ok(themeCss.includes('max-width: 680px'), '680px breakpoint');
  assert.ok(themeCss.includes('max-width: 620px'), '620px breakpoint');
  assert.ok(themeCss.includes('max-width: 480px'), '480px breakpoint');
});

test('Phase 2b: macro.css has mobile breakpoints for session-clock and playbook', () => {
  assert.ok(macroCss.includes('max-width: 620px'), 'macro 620px breakpoint');
  assert.ok(macroCss.includes('max-width: 480px'), 'macro 480px breakpoint');
  assert.ok(macroCss.includes('.session-clock'), 'session-clock is styled');
  assert.ok(macroCss.includes('.playbook-grid'), 'playbook-grid is styled');
});

test('Phase 2b: dashboard.css has mobile breakpoints for operator dashboard', () => {
  assert.ok(dashCss.includes('max-width: 1040px'), 'dashboard 1040px breakpoint');
  assert.ok(dashCss.includes('max-width: 620px'), 'dashboard 620px breakpoint');
  assert.ok(dashCss.includes('max-width: 480px'), 'dashboard 480px breakpoint');
});

test('Phase 2b: dashboard grid includes sessions area', () => {
  assert.ok(dashCss.includes('"sessions sessions"'), 'sessions grid area in 2-col layout');
  assert.ok(dashCss.includes('.dash-session-card'), 'dash-session-card styled');
});

// ── Session logic unit tests ──────────────────────────────────────────────

// Minimal DOM mock for macro_page.js import
function installMinimalDom() {
  const store = new Map();
  const makeEl = () => ({
    textContent: '',
    innerHTML: '',
    style: { display: '', width: '', background: '' },
    className: '',
  });
  global.document = {
    getElementById(id) {
      if (!store.has(id)) store.set(id, makeEl());
      return store.get(id);
    },
    querySelectorAll() { return []; },
  };
  global.fetch = async () => ({ ok: false, status: 404 });
  return store;
}

test('Phase 2b: session clock helpers compute active sessions correctly', async () => {
  const store = installMinimalDom();

  const mod = await import('../app/scripts/ui/macro_page.js');

  // renderDashboardSessions should populate dashSessionClock
  mod.renderDashboardSessions();
  const clockEl = store.get('dashSessionClock');
  assert.ok(clockEl.innerHTML.includes('Sydney'), 'session clock should include Sydney');
  assert.ok(clockEl.innerHTML.includes('Tokyo'), 'session clock should include Tokyo');
  assert.ok(clockEl.innerHTML.includes('London'), 'session clock should include London');
  assert.ok(clockEl.innerHTML.includes('New York'), 'session clock should include New York');

  const utcEl = store.get('dashSessionUtcClock');
  assert.ok(utcEl.textContent.startsWith('UTC'), 'UTC clock should start with UTC');
});

test('Phase 2b: session items have proper aria-label attributes', async () => {
  const store = installMinimalDom();
  const mod = await import('../app/scripts/ui/macro_page.js');
  mod.renderDashboardSessions();
  const clockHtml = store.get('dashSessionClock').innerHTML;
  assert.ok(clockHtml.includes('aria-label='), 'session items should have aria-label');
});

// ── UI polish verification ────────────────────────────────────────────────

test('Phase 2b: macro cards have hover transition style', () => {
  assert.ok(macroCss.includes('.macro-card:hover'), 'macro-card hover rule');
  assert.ok(macroCss.includes('.macro-card') && macroCss.includes('transition'), 'macro-card transition');
});

test('Phase 2b: dashboard cards have hover transition style', () => {
  assert.ok(dashCss.includes('.dash-card:hover'), 'dash-card hover rule');
  assert.ok(dashCss.includes('transition: border-color'), 'dash-card transition property');
});

test('Phase 2b: confidence bar styles exist', () => {
  assert.ok(macroCss.includes('.confidence-bar-fill'), 'confidence bar fill');
  assert.ok(macroCss.includes('.confidence-bar-wrap'), 'confidence bar wrap');
});

test('Phase 2b: regime color classes defined', () => {
  assert.ok(macroCss.includes('.macro-val--trending'), 'trending class');
  assert.ok(macroCss.includes('.macro-val--ranging'), 'ranging class');
  assert.ok(macroCss.includes('.macro-val--volatile'), 'volatile class');
  assert.ok(macroCss.includes('.macro-val--bullish'), 'bullish class');
  assert.ok(macroCss.includes('.macro-val--bearish'), 'bearish class');
});

test('Phase 2b: touch-friendly controls at 480px', () => {
  // The 480px breakpoint should include touch-friendly padding for form controls
  // Find the last 480px block (the one with mobile touch targets)
  const idx480 = themeCss.lastIndexOf('max-width: 480px');
  const blockAfter = themeCss.slice(idx480, idx480 + 1000);
  assert.ok(blockAfter.includes('.radio-opt'), '480px has radio-opt sizing');
  assert.ok(blockAfter.includes('.bias-btn'), '480px has bias-btn sizing');
});
