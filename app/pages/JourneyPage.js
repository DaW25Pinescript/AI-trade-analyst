/**
 * JourneyPage — Staged Trade Ideation Flow
 *
 * Implements all 7 journey stages with the StageShell layout.
 * Data sourced through typed service layer and journey store.
 *
 * V1.1: Wired to real backend. Save calls POST /journey/decision
 * and only shows success after backend confirmation.
 */

import { createStageShell } from '../components/StageShell.js';
import { createAIPrefillCard } from '../components/AIPrefillCard.js';
import { createChartAnnotationLayer } from '../components/ChartAnnotationLayer.js';
import { createGateChecklist } from '../components/GateChecklist.js';
import { createSplitVerdictPanel } from '../components/SplitVerdictPanel.js';
import { createEvidencePanel } from '../components/EvidencePanel.js';
import { createNotesTextarea } from '../components/NotesTextarea.js';
import { createSurfaceCard } from '../components/SurfaceCard.js';
import { createStatusBadge } from '../components/StatusBadge.js';
import { StageKey, STAGE_ORDER } from '../types/journey.js';
import * as store from '../stores/journeyStore.js';
import { loadJourneyBootstrap, saveDecision } from '../lib/services.js';

/** Track the bootstrap dataState for the current journey */
let _bootstrapDataState = null;

/**
 * Renders the journey page for a specific asset.
 * @param {HTMLElement} container
 * @param {string} asset - Instrument symbol
 */
export async function renderJourneyPage(container, asset) {
  container.innerHTML = '';
  _bootstrapDataState = null;

  // Loading
  const loadingEl = document.createElement('div');
  loadingEl.className = 'journey-loading';
  loadingEl.innerHTML = `<p class="text-muted">Loading journey for ${asset}...</p>`;
  container.appendChild(loadingEl);

  // Bootstrap journey data
  const bootstrap = await loadJourneyBootstrap(asset);
  _bootstrapDataState = bootstrap.dataState || null;

  loadingEl.remove();

  // Handle unavailable data state — block journey entry
  if (_bootstrapDataState === 'unavailable') {
    _renderUnavailableState(container, asset);
    return;
  }

  // Handle error data state
  if (_bootstrapDataState === 'error') {
    _renderErrorState(container, asset);
    return;
  }

  store.bootstrapJourney(bootstrap);

  // Render current stage
  _renderCurrentStage(container);

  // Subscribe to store changes for re-rendering
  store.subscribe(() => _renderCurrentStage(container));
}

function _renderUnavailableState(container, asset) {
  container.innerHTML = `
    <div class="data-state-block data-state-block--unavailable">
      <h2 class="text-secondary">Data Unavailable</h2>
      <p class="text-muted">No analyst output found for <strong>${_escapeHtml(asset)}</strong>.</p>
      <p class="text-muted">Run the multi-analyst pipeline for this instrument to generate the required data.</p>
      <a href="#/dashboard" class="btn btn--primary">Return to Dashboard</a>
    </div>
  `;
}

function _renderErrorState(container, asset) {
  container.innerHTML = `
    <div class="data-state-block data-state-block--error">
      <h2 class="text-secondary">Error Loading Data</h2>
      <p class="text-muted">Failed to load journey data for <strong>${_escapeHtml(asset)}</strong>.</p>
      <p class="text-muted">Check that the backend server is running at port 8000.</p>
      <a href="#/dashboard" class="btn btn--primary">Return to Dashboard</a>
    </div>
  `;
}

function _createDataStateBanner(dataState) {
  if (!dataState || dataState === 'live') return null;

  const banner = document.createElement('div');
  banner.className = `data-state-banner data-state-banner--${dataState}`;

  const messages = {
    stale: 'Analyst data may be outdated — consider re-running the pipeline.',
    partial: 'Some analysis data is missing — partial results are displayed. Journey may continue.',
    demo: 'Demo mode — backend is unreachable. Showing sample data for UI preview only.',
  };

  banner.innerHTML = `
    <span class="data-state-banner__icon">${dataState === 'demo' ? '&#9881;' : '&#9888;'}</span>
    <span class="data-state-banner__text">${messages[dataState] || `Data state: ${dataState}`}</span>
  `;
  return banner;
}

function _renderCurrentStage(container) {
  container.innerHTML = '';
  const state = store.getState();

  // Add data state banner if applicable
  const banner = _createDataStateBanner(_bootstrapDataState);
  if (banner) {
    container.appendChild(banner);
  }

  const stageRenderers = {
    [StageKey.MARKET_OVERVIEW]: _renderMarketOverview,
    [StageKey.ASSET_CONTEXT]: _renderAssetContext,
    [StageKey.STRUCTURE_LIQUIDITY]: _renderStructureLiquidity,
    [StageKey.MACRO_ALIGNMENT]: _renderMacroAlignment,
    [StageKey.GATE_CHECKS]: _renderGateChecks,
    [StageKey.VERDICT_PLAN]: _renderVerdictPlan,
    [StageKey.JOURNAL_CAPTURE]: _renderJournalCapture,
  };

  const renderer = stageRenderers[state.currentStage];
  if (renderer) {
    renderer(container, state);
  }
}

// ── Stage 1: Market Overview ────────────────────────────────────────────────

function _renderMarketOverview(container, state) {
  const data = state.stageData[StageKey.MARKET_OVERVIEW];
  const { shell, leftPanel, rightPanel } = createStageShell({
    stageKey: StageKey.MARKET_OVERVIEW,
    currentStage: state.currentStage,
    subtitle: `${state.selectedAsset} — Why this asset matters now`,
    onStageClick: (key) => store.setStage(key),
    onNext: () => store.nextStage(),
    gateBlocked: store.hasBlockedGate(),
  });

  // Left: Overview summary
  leftPanel.appendChild(createAIPrefillCard({
    title: 'Market Context',
    fields: [
      { label: 'Instrument', value: state.selectedAsset },
      { label: 'Directional Bias', value: data?.biasHint || '—' },
      { label: 'Confidence', value: data?.confidence || '—' },
      { label: 'Consensus', value: data?.consensusState || '—' },
    ],
  }));

  // Left: placeholder chart
  leftPanel.appendChild(createChartAnnotationLayer({
    instrument: state.selectedAsset,
    timeframe: 'Overview',
  }));

  // Right: quick system summary
  if (state.systemVerdict) {
    rightPanel.appendChild(createAIPrefillCard({
      title: 'System Summary',
      summary: state.systemVerdict.winningSummary || 'No summary available.',
    }));
  }

  container.appendChild(shell);
}

// ── Stage 2: Asset Context ──────────────────────────────────────────────────

function _renderAssetContext(container, state) {
  const data = state.stageData[StageKey.ASSET_CONTEXT];
  const { shell, leftPanel, rightPanel } = createStageShell({
    stageKey: StageKey.ASSET_CONTEXT,
    currentStage: state.currentStage,
    subtitle: 'Base analytical context and signal overview',
    onStageClick: (key) => store.setStage(key),
    onNext: () => store.nextStage(),
    onPrev: () => store.prevStage(),
    gateBlocked: store.hasBlockedGate(),
  });

  // Left: Digest overview
  const digest = data?.digest;
  if (digest) {
    leftPanel.appendChild(createAIPrefillCard({
      title: 'Structure Digest',
      fields: [
        { label: 'HTF Bias', value: digest.htf_bias },
        { label: 'Source Timeframe', value: digest.htf_source_timeframe },
        { label: 'Structure Gate', value: digest.structure_gate },
        { label: 'BOS/MSS Alignment', value: digest.bos_mss_alignment },
        { label: 'Liquidity Bias', value: digest.liquidity_bias },
        { label: 'FVG Context', value: digest.active_fvg_context },
        { label: 'Recent Sweep', value: digest.recent_sweep_signal },
      ],
    }));
  }

  // Right: Signal ranking if available
  if (data?.signalRanking) {
    const rankingCard = createSurfaceCard({ title: 'Signal Influence Ranking' });
    const signals = data.signalRanking.signals || [];
    rankingCard.bodyElement.innerHTML = signals.map(s => `
      <div class="signal-row">
        <span class="signal-row__name">${s.signal}</span>
        <span class="badge badge--${_influenceBadge(s.influence)}">${s.influence}</span>
        <span class="text-muted">${s.note}</span>
      </div>
    `).join('');
    rightPanel.appendChild(rankingCard);
  }

  container.appendChild(shell);
}

// ── Stage 3: Structure & Liquidity ──────────────────────────────────────────

function _renderStructureLiquidity(container, state) {
  const data = state.stageData[StageKey.STRUCTURE_LIQUIDITY];
  const { shell, leftPanel, rightPanel } = createStageShell({
    stageKey: StageKey.STRUCTURE_LIQUIDITY,
    currentStage: state.currentStage,
    subtitle: 'Chart structure, liquidity levels, and evidence',
    onStageClick: (key) => store.setStage(key),
    onNext: () => store.nextStage(),
    onPrev: () => store.prevStage(),
    gateBlocked: store.hasBlockedGate(),
  });

  // Left: Chart placeholder with annotations
  const annotations = [];
  if (data?.recentSweepSignal && data.recentSweepSignal !== 'none') annotations.push(data.recentSweepSignal);
  if (data?.activeFvgContext && data.activeFvgContext !== 'none') annotations.push(data.activeFvgContext);

  leftPanel.appendChild(createChartAnnotationLayer({
    instrument: state.selectedAsset,
    timeframe: data?.digest?.htf_source_timeframe || 'H4',
    annotations,
  }));

  // Right: Structure details
  if (data) {
    rightPanel.appendChild(createAIPrefillCard({
      title: 'Structure State',
      fields: [
        { label: 'HTF Bias', value: data.htfBias },
        { label: 'Last BOS', value: data.lastBos },
        { label: 'Last MSS', value: data.lastMss },
        { label: 'Alignment', value: data.bosMssAlignment },
        { label: 'Liquidity Bias', value: data.liquidityBias },
        { label: 'Active FVGs', value: data.digest?.active_fvg_count },
      ],
    }));

    // Supports & conflicts
    if (data.structureSupports?.length > 0 || data.structureConflicts?.length > 0) {
      const signalCard = createSurfaceCard({ title: 'Structure Signals' });
      let html = '';
      if (data.structureSupports?.length > 0) {
        html += `<div class="signal-group"><h5 class="text-secondary">Supports</h5>${data.structureSupports.map(s => `<span class="badge badge--passed">${s}</span>`).join(' ')}</div>`;
      }
      if (data.structureConflicts?.length > 0) {
        html += `<div class="signal-group"><h5 class="text-secondary">Conflicts</h5>${data.structureConflicts.map(s => `<span class="badge badge--blocked">${s}</span>`).join(' ')}</div>`;
      }
      signalCard.bodyElement.innerHTML = html;
      rightPanel.appendChild(signalCard);
    }

    // Liquidity levels
    if (data.nearestLiquidityAbove || data.nearestLiquidityBelow) {
      rightPanel.appendChild(createAIPrefillCard({
        title: 'Nearest Liquidity',
        fields: [
          { label: 'Above', value: data.nearestLiquidityAbove ? `${data.nearestLiquidityAbove.type} @ ${data.nearestLiquidityAbove.price}` : '—' },
          { label: 'Below', value: data.nearestLiquidityBelow ? `${data.nearestLiquidityBelow.type} @ ${data.nearestLiquidityBelow.price}` : '—' },
        ],
      }));
    }
  }

  container.appendChild(shell);
}

// ── Stage 4: Macro Alignment ────────────────────────────────────────────────

function _renderMacroAlignment(container, state) {
  const data = state.stageData[StageKey.MACRO_ALIGNMENT];
  const { shell, leftPanel, rightPanel } = createStageShell({
    stageKey: StageKey.MACRO_ALIGNMENT,
    currentStage: state.currentStage,
    subtitle: 'Macro and news alignment — conflict or confluence?',
    onStageClick: (key) => store.setStage(key),
    onNext: () => store.nextStage(),
    onPrev: () => store.prevStage(),
    gateBlocked: store.hasBlockedGate(),
  });

  if (data) {
    // Left: Macro context
    leftPanel.appendChild(createAIPrefillCard({
      title: 'Macro Context',
      fields: [
        { label: 'Regime', value: data.regime },
        { label: 'Volatility Bias', value: data.volBias },
        { label: 'Directional Pressure', value: data.directionalPressure },
        { label: 'Confidence', value: data.confidence },
        { label: 'Conflict Score', value: data.conflictScore },
      ],
    }));

    // Left: Events
    if (data.events?.length > 0) {
      const eventsCard = createSurfaceCard({ title: 'Macro Events' });
      eventsCard.bodyElement.innerHTML = data.events.map(e => `
        <div class="macro-event">
          <span class="badge badge--${e.importance === 'high' ? 'blocked' : 'watch'}">${e.importance}</span>
          <span class="text-primary">${e.title}</span>
          <span class="text-muted">${e.source}</span>
        </div>
      `).join('');
      leftPanel.appendChild(eventsCard);
    }

    // Right: Explanation
    if (data.explanation?.length > 0) {
      const explCard = createSurfaceCard({ title: 'Macro Assessment' });
      explCard.bodyElement.innerHTML = data.explanation.map(e => `<p class="text-secondary">${e}</p>`).join('');
      rightPanel.appendChild(explCard);
    }

    // Right: Top drivers
    if (data.topDrivers?.length > 0) {
      const driversCard = createSurfaceCard({ title: 'Top Drivers' });
      driversCard.bodyElement.innerHTML = data.topDrivers.map(d => `<div class="badge badge--ai-prefill">${d}</div>`).join(' ');
      rightPanel.appendChild(driversCard);
    }
  } else {
    leftPanel.innerHTML = '<p class="text-muted">No macro data available.</p>';
  }

  container.appendChild(shell);
}

// ── Stage 5: Gate Checks ────────────────────────────────────────────────────

function _renderGateChecks(container, state) {
  const isBlocked = store.hasBlockedGate();
  const { shell, leftPanel, rightPanel } = createStageShell({
    stageKey: StageKey.GATE_CHECKS,
    currentStage: state.currentStage,
    subtitle: 'Control boundary — all gates must be addressed before proceeding',
    onStageClick: (key) => store.setStage(key),
    onNext: () => store.nextStage(),
    onPrev: () => store.prevStage(),
    nextDisabled: isBlocked,
    nextLabel: isBlocked ? 'Blocked' : 'Continue',
    gateBlocked: isBlocked,
  });

  // Full-width gate checklist
  const gateChecklist = createGateChecklist({
    gates: state.gateStates,
    onGateUpdate: (gateId, newState, justification) => {
      store.updateGateState(gateId, newState, justification);
    },
  });
  leftPanel.appendChild(gateChecklist);

  // Right: summary
  const summaryCard = createSurfaceCard({ title: 'Gate Summary' });
  const passed = state.gateStates.filter(g => g.state === 'passed').length;
  const conditional = state.gateStates.filter(g => g.state === 'conditional').length;
  const blocked = state.gateStates.filter(g => g.state === 'blocked').length;
  summaryCard.bodyElement.innerHTML = `
    <div class="gate-summary">
      <div class="gate-summary__row"><span class="badge badge--passed">Passed</span><span>${passed}</span></div>
      <div class="gate-summary__row"><span class="badge badge--conditional">Conditional</span><span>${conditional}</span></div>
      <div class="gate-summary__row"><span class="badge badge--blocked">Blocked</span><span>${blocked}</span></div>
    </div>
  `;
  rightPanel.appendChild(summaryCard);

  container.appendChild(shell);
}

// ── Stage 6: Verdict & Plan ─────────────────────────────────────────────────

function _renderVerdictPlan(container, state) {
  const { shell, leftPanel } = createStageShell({
    stageKey: StageKey.VERDICT_PLAN,
    currentStage: state.currentStage,
    subtitle: 'System recommendation vs your commitment — three distinct layers',
    onStageClick: (key) => store.setStage(key),
    onNext: () => store.nextStage(),
    onPrev: () => store.prevStage(),
    gateBlocked: store.hasBlockedGate(),
  });

  // Full-width split verdict panel
  const verdictPanel = createSplitVerdictPanel({
    systemVerdict: state.systemVerdict,
    userDecision: state.userDecision,
    executionPlan: state.executionPlan,
    onUserDecisionChange: (decision) => store.setUserDecision(decision),
    onExecutionPlanChange: (plan) => store.setExecutionPlan(plan),
  });
  leftPanel.appendChild(verdictPanel);
  leftPanel.style.gridColumn = '1 / -1'; // Full width for this stage

  container.appendChild(shell);
}

// ── Stage 7: Journal Capture ────────────────────────────────────────────────

function _renderJournalCapture(container, state) {
  const { shell, leftPanel, rightPanel } = createStageShell({
    stageKey: StageKey.JOURNAL_CAPTURE,
    currentStage: state.currentStage,
    subtitle: 'Freeze the decision record — evidence, notes, and snapshot preview',
    onStageClick: (key) => store.setStage(key),
    onPrev: () => store.prevStage(),
    onNext: async () => {
      // Create snapshot in store
      const snapshot = store.createSnapshot();

      // Enrich snapshot with bootstrap data state
      snapshot.bootstrapDataState = _bootstrapDataState || 'live';

      // Save to backend — only show success after confirmed write
      const result = await saveDecision(snapshot);
      if (result.success) {
        alert('Decision snapshot saved successfully.');
      } else {
        // Revert journey status since save failed
        store.setJourneyStatus('draft');
        alert(`Save failed: ${result.error || 'Unknown error'}`);
      }
    },
    nextLabel: 'Save & Freeze',
    gateBlocked: store.hasBlockedGate(),
  });

  // Left: Evidence and notes
  leftPanel.appendChild(createEvidencePanel({
    evidenceRefs: state.evidenceRefs,
    onAdd: (ref) => store.addEvidence(ref),
    onRemove: (ref) => store.removeEvidence(ref),
  }));

  leftPanel.appendChild(createNotesTextarea({
    value: state.journalNotes,
    label: 'Journal Notes',
    placeholder: 'Record your reasoning, context, and any additional observations...',
    onChange: (val) => store.setJournalNotes(val),
  }));

  // Right: Snapshot preview
  const preview = store.getSnapshotPreview();
  const previewCard = createSurfaceCard({ title: 'Snapshot Preview', elevated: true });
  previewCard.bodyElement.innerHTML = `
    <div class="snapshot-preview">
      <div class="snapshot-preview__row">
        <span class="text-muted">Instrument</span>
        <span class="text-primary">${preview.instrument || '—'}</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">Status</span>
        <span class="text-primary">${preview.journeyStatus}</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">System Verdict</span>
        <span class="text-primary">${preview.systemVerdict?.verdict || '—'}</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">User Decision</span>
        <span class="text-primary">${preview.userDecision?.action || 'Not decided'}</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">Execution Direction</span>
        <span class="text-primary">${preview.executionPlan?.direction || '—'}</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">Gates</span>
        <span class="text-primary">${preview.gateStates?.length || 0} checks</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">Evidence</span>
        <span class="text-primary">${preview.evidenceCount} items</span>
      </div>
      <div class="snapshot-preview__row">
        <span class="text-muted">Notes</span>
        <span class="text-primary">${preview.hasNotes ? 'Yes' : 'None'}</span>
      </div>
    </div>
    <p class="text-muted snapshot-preview__note">This snapshot will be frozen at save time and cannot be modified later.</p>
  `;
  rightPanel.appendChild(previewCard);

  container.appendChild(shell);
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function _influenceBadge(influence) {
  if (influence === 'dominant') return 'actionable';
  if (influence === 'supporting') return 'passed';
  if (influence === 'conflicting') return 'blocked';
  if (influence === 'neutral') return 'watch';
  return 'user-manual';
}

function _escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
