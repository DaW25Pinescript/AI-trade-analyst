import test from 'node:test';
import assert from 'node:assert/strict';

function classList() {
  const set = new Set();
  return {
    add: (...names) => names.forEach((n) => set.add(n)),
    remove: (...names) => names.forEach((n) => set.delete(n)),
    toggle: (name, force) => {
      if (force === undefined) {
        if (set.has(name)) set.delete(name);
        else set.add(name);
      } else if (force) set.add(name);
      else set.delete(name);
    },
    contains: (name) => set.has(name),
  };
}

function makeElement(value = '') {
  return {
    value,
    textContent: '',
    hidden: false,
    style: {},
    classList: classList(),
    attrs: {},
    addEventListener() {},
    setAttribute(name, val) { this.attrs[name] = String(val); },
  };
}

function installDashboardDom() {
  const ids = [
    'dashAsset', 'dashSession', 'dashRegime', 'dashPoi', 'dashEntry', 'dashInvalidation',
    'dashTp1', 'dashTp2', 'dashMinRr', 'dashRulingConfidence', 'dashSetupQuality',
    'dashArbiterState', 'dashRiskState', 'dashConfluenceScore', 'dashVerdictBadge',
    'dashConfidenceFill', 'dashEvidenceChips', 'dashAgentRows', 'dashChartPlaceholder',
    'operatorModeBtn', 'operatorDashboard', 'asset', 'session', 'regime', 'entryPriceMin',
    'entryPriceMax', 'stopPrice', 'tp1Price', 'tp2Price', 'minRR', 'decisionMode'
  ];

  const store = new Map(ids.map((id) => [id, makeElement('')]));
  store.get('asset').value = 'EURUSD';
  store.get('session').value = 'London Open';
  store.get('regime').value = 'Trending';
  store.get('entryPriceMin').value = '1.08';
  store.get('entryPriceMax').value = '1.081';
  store.get('stopPrice').value = '1.076';
  store.get('tp1Price').value = '1.084';
  store.get('tp2Price').value = '1.087';
  store.get('minRR').value = '2.5';
  store.get('decisionMode').value = 'LONG';

  const tabs = ['D', '4H'].map((tf) => ({ ...makeElement(), dataset: { tf } }));
  const chips = ['Clean', 'Lens'].map((view) => ({ ...makeElement(), dataset: { view } }));

  global.document = {
    body: { classList: classList() },
    getElementById(id) { return store.get(id) || null; },
    querySelectorAll(sel) {
      if (sel === '.dash-tab') return tabs;
      if (sel === '.dash-chip-btn') return chips;
      return [];
    },
  };

  return store;
}

test('operator dashboard syncs form values and bridge verdict', async () => {
  const store = installDashboardDom();
  const { initOperatorDashboard, toggleOperatorDashboard, refreshOperatorDashboardFromForm, applyBridgeVerdictToDashboard } = await import('../app/scripts/ui/dashboard_shell.js');

  initOperatorDashboard();
  toggleOperatorDashboard();
  refreshOperatorDashboardFromForm();

  assert.equal(store.get('dashAsset').textContent, 'EURUSD');
  assert.equal(store.get('dashSession').textContent, 'London Open');
  assert.equal(store.get('dashMinRr').textContent, '1 : 2.5');

  applyBridgeVerdictToDashboard({
    decision: 'LONG',
    overall_confidence: 0.83,
    setup_quality: 'A',
    arbiter_status: 'Consensus pass',
  });

  assert.equal(store.get('dashRulingConfidence').textContent, '83%');
  assert.equal(store.get('dashSetupQuality').textContent, 'A');
  assert.equal(store.get('dashArbiterState').textContent, 'Consensus pass');
});
