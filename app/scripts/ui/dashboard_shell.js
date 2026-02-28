import { state } from '../state/model.js';

const phaseAState = {
  verdict: {
    bias: 'Bullish',
    confidence: 78,
    setupQuality: 'A-',
    arbiter: 'Approved with conditions',
    riskState: 'Controlled',
  },
  context: {
    asset: 'XAUUSD',
    session: 'NY AM',
    regime: 'Trending',
    poi: 'Awaiting POI input',
  },
  plan: {
    entry: 'Awaiting entry zone',
    invalidation: 'Awaiting stop logic',
    tp1: 'Awaiting TP1',
    tp2: 'Awaiting TP2',
    rr: '1 : 2.1',
  },
  evidence: [
    { label: 'HTF aligned', tone: 'positive' },
    { label: 'Demand POI', tone: 'positive' },
    { label: 'Session active', tone: 'positive' },
    { label: 'MSS pending', tone: 'neutral' },
  ],
  agents: [
    { name: 'ICT Analyst', view: 'Bullish' },
    { name: 'Price Action', view: 'Bullish' },
    { name: 'Risk Officer', view: 'Conditional' },
    { name: 'Dissent', view: 'Needs LTF confirmation' },
  ],
  confluenceScore: '0 / 4',
  chart: {
    timeframe: 'D',
    viewMode: 'Clean',
  },
};

const timeframeFallbacks = {
  D: 'Daily chart stream',
  '4H': '4H structure map',
  '1H': '1H execution context',
  '15m': '15m trigger chart',
};

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function classifyVerdict(value) {
  const lowered = String(value || '').toLowerCase();
  if (lowered.includes('bull')) return 'bullish';
  if (lowered.includes('bear')) return 'bearish';
  return 'neutral';
}

function classifyAgentView(value) {
  const lowered = String(value || '').toLowerCase();
  if (lowered.includes('bull')) return 'bullish';
  if (lowered.includes('bear')) return 'bearish';
  if (lowered.includes('condition')) return 'conditional';
  return '';
}

function renderChips(entries) {
  const wrap = document.getElementById('dashEvidenceChips');
  if (!wrap) return;
  wrap.innerHTML = entries
    .map((entry) => `<span class="dash-chip ${entry.tone}">${entry.label}</span>`)
    .join('');
}

function renderAgents(entries) {
  const wrap = document.getElementById('dashAgentRows');
  if (!wrap) return;
  wrap.innerHTML = entries
    .map((entry) => `
      <div class="dash-agent-row">
        <span>${entry.name}</span>
        <strong class="dash-agent-view ${classifyAgentView(entry.view)}">${entry.view}</strong>
      </div>
    `)
    .join('');
}

function renderPhaseA(nextState = phaseAState) {
  setText('dashAsset', nextState.context.asset);
  setText('dashSession', nextState.context.session);
  setText('dashRegime', nextState.context.regime);
  setText('dashPoi', nextState.context.poi);

  setText('dashEntry', nextState.plan.entry);
  setText('dashInvalidation', nextState.plan.invalidation);
  setText('dashTp1', nextState.plan.tp1);
  setText('dashTp2', nextState.plan.tp2);
  setText('dashMinRr', nextState.plan.rr);

  setText('dashRulingConfidence', `${nextState.verdict.confidence}%`);
  setText('dashSetupQuality', nextState.verdict.setupQuality);
  setText('dashArbiterState', nextState.verdict.arbiter);
  setText('dashRiskState', nextState.verdict.riskState);
  setText('dashConfluenceScore', nextState.confluenceScore);

  const verdictBadge = document.getElementById('dashVerdictBadge');
  if (verdictBadge) {
    verdictBadge.textContent = nextState.verdict.bias;
    verdictBadge.classList.remove('bullish', 'bearish', 'neutral');
    verdictBadge.classList.add(classifyVerdict(nextState.verdict.bias));
  }

  const fill = document.getElementById('dashConfidenceFill');
  if (fill) fill.style.width = `${nextState.verdict.confidence}%`;

  renderChips(nextState.evidence);
  renderAgents(nextState.agents);
  renderChartState(nextState.chart);
}

function renderChartState(chartState = phaseAState.chart) {
  const stage = document.getElementById('dashChartPlaceholder');
  if (stage) {
    const tfLabel = chartState.timeframe || 'D';
    const contextLabel = timeframeFallbacks[tfLabel] || 'Chart context';
    const modeLabel = chartState.viewMode || 'Clean';
    stage.textContent = `${contextLabel} · ${modeLabel} view`;
  }

  document.querySelectorAll('.dash-tab').forEach((btn) => {
    const active = btn.dataset.tf === chartState.timeframe;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  });

  document.querySelectorAll('.dash-chip-btn').forEach((btn) => {
    const active = btn.dataset.view === chartState.viewMode;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', String(active));
  });
}

function pullInputValue(id) {
  const el = document.getElementById(id);
  return (el?.value || '').trim();
}

function toNumber(value) {
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : null;
}

function inferVerdictBias() {
  const decisionMode = pullInputValue('decisionMode').toLowerCase();
  const userBias = String(state.currentBias || '').toLowerCase();
  if (decisionMode.includes('short') || userBias.includes('bear')) return 'Bearish';
  if (decisionMode.includes('long') || userBias.includes('bull')) return 'Bullish';
  return 'Neutral';
}

function listActiveEvidence() {
  const checks = [
    { value: state.ptcState.htfState, label: 'HTF state tagged', tone: 'positive' },
    { value: state.ptcState.ltfAlignment, label: 'LTF alignment confirmed', tone: 'positive' },
    { value: state.ptcState.liquidityContext, label: 'Liquidity context mapped', tone: 'neutral' },
    { value: state.ptcState.volRisk, label: 'Volatility risk reviewed', tone: 'warning' },
  ];

  const active = checks
    .filter((item) => item.value)
    .map(({ label, tone }) => ({ label, tone }));

  return active.length ? active : phaseAState.evidence;
}

function computeConfluenceScore() {
  const score = [
    state.ptcState.htfState,
    state.ptcState.ltfAlignment,
    state.ptcState.liquidityContext,
    state.ptcState.volRisk,
  ].filter(Boolean).length;
  return `${score} / 4`;
}

function derivePlan() {
  const entryMin = toNumber(pullInputValue('entryPriceMin'));
  const entryMax = toNumber(pullInputValue('entryPriceMax'));
  const stop = pullInputValue('stopPrice');
  const tp1 = pullInputValue('tp1Price');
  const tp2 = pullInputValue('tp2Price');

  let entry = phaseAState.plan.entry;
  if (entryMin !== null || entryMax !== null) {
    const low = entryMin ?? entryMax;
    const high = entryMax ?? entryMin;
    entry = `${low} - ${high}`;
  }

  return {
    entry,
    invalidation: stop ? `Below ${stop}` : phaseAState.plan.invalidation,
    tp1: tp1 || phaseAState.plan.tp1,
    tp2: tp2 || phaseAState.plan.tp2,
    rr: pullInputValue('minRR') ? `1 : ${pullInputValue('minRR')}` : phaseAState.plan.rr,
  };
}

export function refreshOperatorDashboardFromForm() {
  renderPhaseA({
    ...phaseAState,
    verdict: {
      ...phaseAState.verdict,
      bias: inferVerdictBias(),
    },
    context: {
      asset: pullInputValue('asset') || phaseAState.context.asset,
      session: pullInputValue('session') || phaseAState.context.session,
      regime: pullInputValue('regime') || phaseAState.context.regime,
      poi: state.ptcState.htfLocation || phaseAState.context.poi,
    },
    plan: derivePlan(),
    evidence: listActiveEvidence(),
    confluenceScore: computeConfluenceScore(),
    chart: { ...phaseAState.chart },
  });
}

export function applyBridgeVerdictToDashboard(verdict = {}) {
  const decision = String(verdict.decision || verdict.final_decision || '').toLowerCase();
  const shouldBearish = decision.includes('short') || decision.includes('no_trade') || decision.includes('wait');
  const setupQuality = verdict.setup_quality || verdict.setupGrade || phaseAState.verdict.setupQuality;
  const confidence = Number(verdict.overall_confidence ?? verdict.confidence);
  const confidencePct = Number.isFinite(confidence)
    ? Math.max(0, Math.min(100, Math.round(confidence * 100)))
    : phaseAState.verdict.confidence;

  renderPhaseA({
    ...phaseAState,
    verdict: {
      ...phaseAState.verdict,
      bias: shouldBearish ? 'Bearish' : 'Bullish',
      confidence: confidencePct,
      setupQuality,
      arbiter: verdict.arbiter_status || verdict.reason || 'AI verdict loaded',
      riskState: verdict.risk_state || phaseAState.verdict.riskState,
    },
    chart: { ...phaseAState.chart },
  });
}

function bindChartControls() {
  document.querySelectorAll('.dash-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      phaseAState.chart.timeframe = btn.dataset.tf || phaseAState.chart.timeframe;
      renderChartState(phaseAState.chart);
    });
  });

  document.querySelectorAll('.dash-chip-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      phaseAState.chart.viewMode = btn.dataset.view || phaseAState.chart.viewMode;
      renderChartState(phaseAState.chart);
    });
  });
}

function bindFormSync() {
  const ids = ['asset', 'session', 'regime', 'entryPriceMin', 'entryPriceMax', 'stopPrice', 'tp1Price', 'tp2Price', 'minRR', 'decisionMode'];
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', refreshOperatorDashboardFromForm);
    el.addEventListener('change', refreshOperatorDashboardFromForm);
  });
}

function setMode(active) {
  document.body.classList.toggle('operator-dashboard-mode', active);
  const btn = document.getElementById('operatorModeBtn');
  if (btn) {
    btn.classList.toggle('active', active);
    btn.textContent = `Operator Dashboard: ${active ? 'ON' : 'OFF'}`;
    btn.setAttribute('aria-pressed', String(active));
  }
  const panel = document.getElementById('operatorDashboard');
  if (panel) panel.hidden = !active;
}

export function toggleOperatorDashboard() {
  const next = !document.body.classList.contains('operator-dashboard-mode');
  setMode(next);
  if (next) refreshOperatorDashboardFromForm();
}

export function initOperatorDashboard() {
  bindChartControls();
  bindFormSync();
  renderPhaseA();
  refreshOperatorDashboardFromForm();
  setMode(false);
}
