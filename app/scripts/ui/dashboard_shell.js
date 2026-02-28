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
    poi: '3348–3354',
  },
  plan: {
    entry: '3351–3354',
    invalidation: 'Below 3344',
    tp1: '3362',
    tp2: '3371',
    rr: '1 : 2.1',
  },
  evidence: [
    { label: 'HTF aligned', tone: 'positive' },
    { label: 'Demand POI', tone: 'positive' },
    { label: 'Session active', tone: 'positive' },
    { label: 'MSS pending', tone: 'neutral' },
    { label: 'News later', tone: 'warning' },
  ],
  agents: [
    { name: 'ICT Analyst', view: 'Bullish' },
    { name: 'Price Action', view: 'Bullish' },
    { name: 'Risk Officer', view: 'Conditional' },
    { name: 'Dissent', view: 'Needs LTF confirmation' },
  ],
  confluenceScore: '4 / 5',
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

function renderPhaseA(state = phaseAState) {
  setText('dashAsset', state.context.asset);
  setText('dashSession', state.context.session);
  setText('dashRegime', state.context.regime);
  setText('dashPoi', state.context.poi);

  setText('dashEntry', state.plan.entry);
  setText('dashInvalidation', state.plan.invalidation);
  setText('dashTp1', state.plan.tp1);
  setText('dashTp2', state.plan.tp2);
  setText('dashMinRr', state.plan.rr);

  setText('dashRulingConfidence', `${state.verdict.confidence}%`);
  setText('dashSetupQuality', state.verdict.setupQuality);
  setText('dashArbiterState', state.verdict.arbiter);
  setText('dashRiskState', state.verdict.riskState);
  setText('dashConfluenceScore', state.confluenceScore);

  const verdictBadge = document.getElementById('dashVerdictBadge');
  if (verdictBadge) {
    verdictBadge.textContent = state.verdict.bias;
    verdictBadge.classList.remove('bullish', 'bearish', 'neutral');
    verdictBadge.classList.add(classifyVerdict(state.verdict.bias));
  }

  const fill = document.getElementById('dashConfidenceFill');
  if (fill) fill.style.width = `${state.verdict.confidence}%`;

  renderChips(state.evidence);
  renderAgents(state.agents);
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
}

export function initOperatorDashboard() {
  renderPhaseA();
  setMode(false);
}
