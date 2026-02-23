import { state } from '../state/model.js';

export function ptcComplete() {
  return Object.values(state.ptcState).every((v) => v !== '');
}

export function evaluateGate() {
  const badge = document.getElementById('gateBadge');
  const gateEl = document.getElementById('gateStatus');
  const gateText = document.getElementById('gateText');
  const waitPanel = document.getElementById('waitPanel');

  const complete = ptcComplete();
  badge.textContent = complete ? 'READY' : 'INCOMPLETE';
  badge.className = complete ? 'gate-badge ok' : 'gate-badge';

  if (!complete) {
    gateEl.className = 'gate-status';
    gateText.textContent = 'Complete all 8 fields to see gate decision.';
    waitPanel.classList.remove('visible');
    return;
  }

  const eq = state.ptcState.execQuality;
  const ltf = state.ptcState.ltfAlignment;
  const vol = state.ptcState.volRisk;
  const noTradeOK = document.getElementById('noTradeToggle').checked;

  const isChopOrMessy = eq === 'Chop' || eq === 'Messy';
  const isConflict = ltf === 'Counter-trend' || ltf === 'Mixed';
  const isElevatedVol = vol === 'Elevated';

  if (isChopOrMessy && noTradeOK) {
    gateEl.className = 'gate-status wait';
    gateText.textContent = 'GATE → DEFAULT WAIT. Execution quality is poor. Proceed only with a specific conditional trigger.';
    waitPanel.classList.add('visible');
  } else if (isConflict && isElevatedVol) {
    gateEl.className = 'gate-status caution';
    gateText.textContent = 'GATE → CAUTION. HTF/LTF conflict + elevated volatility. Lower confidence — consider sizing down or conditional entry only.';
    waitPanel.classList.remove('visible');
  } else if (isConflict || isElevatedVol) {
    gateEl.className = 'gate-status caution';
    gateText.textContent = 'GATE → CAUTION. One risk flag present. Ensure entry trigger is tight and kill-switch is defined.';
    waitPanel.classList.remove('visible');
  } else {
    gateEl.className = 'gate-status proceed';
    gateText.textContent = 'GATE → PROCEED. Conditions acceptable. Generate ticket.';
    waitPanel.classList.remove('visible');
  }
}
