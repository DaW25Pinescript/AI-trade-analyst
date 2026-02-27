import { state, generateTicketID } from '../state/model.js';
import { evaluateGate } from './gates.js';
import { syncOutput } from './sync_output.js';

function onAssetInput() {
  generateTicketID();
  syncOutput();
}

// ═══════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════

function setAsset(val) {
  document.getElementById('asset').value = val;
  generateTicketID();
  syncOutput();
}

function setBias(el) {
  document.querySelectorAll('.bias-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  state.currentBias = el.dataset.val;
  syncOutput();
}

// ═══════════════════════════════════════
// FILE UPLOAD
// ═══════════════════════════════════════

function triggerUpload(id) { document.getElementById(id).click(); }

function handleUpload(input, zoneId, labelId, key) {
  const file = input.files[0];
  if (!file) return;
  state.uploads[key] = file.name;
  document.getElementById(zoneId).classList.add('has-file');
  document.getElementById(labelId).textContent = file.name;
  const reader = new FileReader();
  reader.onload = e => {
    state.imgSrcs[key] = e.target.result;
    document.getElementById('prev-' + key).src = e.target.result;
  };
  reader.onerror = () => {
    alert('Failed to read image file. Please try another image.');
  };
  reader.readAsDataURL(file);
}

// ═══════════════════════════════════════
// 15M ICT OVERLAY TOGGLE
// Progressive disclosure: the overlay slot is hidden by default and
// revealed when the trader opts in. The overlay is optional — the system
// produces a complete analysis from clean price charts alone.
// ═══════════════════════════════════════

function toggleOverlaySlot(enabled) {
  state.overlayEnabled = enabled;
  const wrap = document.getElementById('overlaySlotWrap');
  if (wrap) wrap.style.display = enabled ? 'block' : 'none';

  // Clear overlay state when disabled so it is not included in the output
  if (!enabled) {
    const overlayKeys = ['m15overlay', 'm15structure', 'm15trendline', 'customoverlay'];
    overlayKeys.forEach(key => {
      state.uploads[key] = null;
      state.imgSrcs[key] = '';
      const zone = document.getElementById('zone-' + key);
      if (zone) zone.classList.remove('has-file');
      const label = document.getElementById('label-' + key);
      if (label) label.textContent = '';
      const preview = document.getElementById('prev-' + key);
      if (preview) preview.src = '';
      const input = document.getElementById('upload-' + key);
      if (input) input.value = '';
    });
  }

  syncOutput();
}

// ═══════════════════════════════════════
// CHECKBOXES
// ═══════════════════════════════════════

function toggleCheck(el) {
  el.classList.toggle('checked');
  el.querySelector('.check-box').textContent = el.classList.contains('checked') ? '✓' : '';
}

function getChecked() {
  return Array.from(document.querySelectorAll('#requests .checkbox-item.checked .check-text'))
              .map(i => i.textContent);
}

// ═══════════════════════════════════════
// PRE-TICKET RADIO LOGIC
// ═══════════════════════════════════════

function selectRadio(field, el) {
  const group = document.getElementById('rg-' + field);
  group.querySelectorAll('.radio-opt').forEach(o => {
    o.className = 'radio-opt'; // reset
  });
  el.classList.add(el.dataset.sel);
  state.ptcState[field] = el.dataset.val;
  evaluateGate();
  syncOutput();
}

function onSlider() {
  const v = document.getElementById('confluenceScore').value;
  document.getElementById('confVal').textContent = v;
  syncOutput();
}

// ═══════════════════════════════════════
// R:R EXCEPTION TOGGLE
// ═══════════════════════════════════════

function toggleRRJustification() {
  const show = document.getElementById('rrException').value === 'yes';
  document.getElementById('rrJustWrap').style.display = show ? 'block' : 'none';
}

// ═══════════════════════════════════════
// G2: DECISION MODE TOGGLE
// ═══════════════════════════════════════

function onDecisionModeChange(el) {
  const wrap = document.getElementById('conditionalWrap');
  if (wrap) wrap.style.display = el.value === 'CONDITIONAL' ? 'block' : 'none';
  syncOutput();
}

// ═══════════════════════════════════════
// G3: AFTER-ACTION REVIEW (AAR)
// ═══════════════════════════════════════

function selectAARRadio(field, el) {
  const group = document.getElementById('rg-aar-' + field);
  if (group) group.querySelectorAll('.radio-opt').forEach(o => { o.className = 'radio-opt'; });
  el.classList.add(el.dataset.sel);
  state.aarState[field] = el.dataset.val;
  updateEdgeScore();
}

function onAAROutcomeChange(el) {
  const showWouldHaveWon = el.value === 'MISSED' || el.value === 'SCRATCH';
  const wrap = document.getElementById('wouldHaveWonWrap');
  if (wrap) wrap.style.display = showWouldHaveWon ? 'block' : 'none';
  updateEdgeScore();
}

function onAARSlider() {
  const v = document.getElementById('aarConfidence').value;
  const display = document.getElementById('aarConfVal');
  if (display) display.textContent = v;
  updateEdgeScore();
}

const VERDICT_MULTIPLIER = {
  PLAN_FOLLOWED: 1.0,
  PROCESS_GOOD: 0.8,
  PROCESS_POOR: 0.5,
  PLAN_VIOLATION: 0.2
};

function updateEdgeScore() {
  const conf = Number.parseInt(document.getElementById('aarConfidence')?.value || '3', 10);
  const verdict = document.getElementById('aarVerdict')?.value || '';
  const multiplier = VERDICT_MULTIPLIER[verdict] ?? 0.5;
  const score = (conf * multiplier).toFixed(1);

  const display = document.getElementById('edgeScoreDisplay');
  if (!display) return;

  display.textContent = score;
  display.className = 'edge-score-display';
  if (score >= 4.0) display.classList.add('edge-high');
  else if (score >= 2.5) display.classList.add('edge-mid');
  else display.classList.add('edge-low');
}

function handleAARPhotoUpload(input) {
  const file = input.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = e => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.getElementById('aarPhotoCanvas');
      if (!canvas) return;

      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);

      // Watermark: semi-transparent banner at bottom
      const ticketId = state.ticketID || 'UNKNOWN';
      const ts = new Date().toISOString().slice(0, 16).replace('T', ' ') + 'Z';
      const label = `${ticketId} · ${ts}`;
      const fontSize = Math.max(14, Math.floor(img.height * 0.025));
      ctx.font = `${fontSize}px IBM Plex Mono, monospace`;

      const padding = fontSize * 0.6;
      const bannerH = fontSize + padding * 2;

      ctx.fillStyle = 'rgba(0,0,0,0.65)';
      ctx.fillRect(0, img.height - bannerH, img.width, bannerH);

      ctx.fillStyle = '#d4a843';
      ctx.fillText(label, padding, img.height - padding);

      const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
      state.aarState.photoDataUrl = dataUrl;

      const preview = document.getElementById('prev-aarPhoto');
      if (preview) { preview.src = dataUrl; preview.style.display = 'block'; }

      const labelEl = document.getElementById('label-aarPhoto');
      if (labelEl) labelEl.textContent = file.name + ' (watermarked)';

      const zone = document.getElementById('zone-aarPhoto');
      if (zone) zone.classList.add('has-file');
    };
    img.onerror = () => alert('Failed to load image for watermarking.');
    img.src = e.target.result;
  };
  reader.onerror = () => alert('Failed to read image file.');
  reader.readAsDataURL(file);
}

// ═══════════════════════════════════════
// G9: SHADOW MODE
// ═══════════════════════════════════════

function onShadowModeChange() {
  const toggle = document.getElementById('shadowModeToggle');
  state.shadowMode = toggle?.checked ?? false;

  const badge = document.getElementById('shadowBadge');
  if (badge) badge.style.display = state.shadowMode ? 'inline-block' : 'none';

  const card = document.getElementById('shadowOutcomeCard');
  if (card) card.style.display = state.shadowMode ? 'block' : 'none';

  if (state.shadowMode) {
    _updateShadowDeadline();
  } else {
    // Clear shadow outcome when toggled off
    state.shadowOutcome = null;
  }

  syncOutput();
}

function _updateShadowDeadline() {
  const windowEl = document.getElementById('shadowCaptureWindow');
  const hours = Number.parseInt(windowEl?.value || '24', 10);
  const deadline = new Date(Date.now() + hours * 60 * 60 * 1000);
  const display = document.getElementById('shadowDeadlineDisplay');
  if (display) {
    display.textContent = deadline.toISOString().replace('T', ' ').slice(0, 16) + 'Z';
  }
}

function onShadowCaptureWindowChange() {
  _updateShadowDeadline();
}

function onShadowOutcomeInput() {
  const priceEl = document.getElementById('shadowOutcomePrice');
  const outcomePrice = Number.parseFloat(priceEl?.value || '');
  if (!Number.isFinite(outcomePrice)) {
    document.getElementById('shadowPnlDisplay').textContent = '—';
    document.getElementById('shadowPnlDisplay').style.color = 'var(--muted)';
    const hitRow = document.getElementById('shadowHitRow');
    if (hitRow) hitRow.style.display = 'none';
    return;
  }

  // Read ticket price levels from the Pre-Ticket form
  const stopPrice = Number.parseFloat(document.getElementById('stopPrice')?.value || '');
  const tp1Price  = Number.parseFloat(document.getElementById('tp1Price')?.value || '');
  const entryMin  = Number.parseFloat(document.getElementById('entryPriceMin')?.value || '');
  const entryMax  = Number.parseFloat(document.getElementById('entryPriceMax')?.value || '');
  const decisionMode = document.getElementById('decisionMode')?.value || '';

  const entryMid = Number.isFinite(entryMin) && Number.isFinite(entryMax) ? (entryMin + entryMax) / 2 : NaN;

  let pnlR = null;
  let hitTarget = null;
  let hitStop = null;

  if (Number.isFinite(entryMid) && Number.isFinite(stopPrice) && Number.isFinite(tp1Price)) {
    const riskR = Math.abs(entryMid - stopPrice);
    if (riskR > 0) {
      if (decisionMode === 'LONG') {
        pnlR = (outcomePrice - entryMid) / riskR;
        hitTarget = tp1Price > entryMid ? outcomePrice >= tp1Price : false;
        hitStop   = stopPrice < entryMid ? outcomePrice <= stopPrice : false;
      } else if (decisionMode === 'SHORT') {
        pnlR = (entryMid - outcomePrice) / riskR;
        hitTarget = tp1Price < entryMid ? outcomePrice <= tp1Price : false;
        hitStop   = stopPrice > entryMid ? outcomePrice >= stopPrice : false;
      }
    }
  }

  const pnlDisplay = document.getElementById('shadowPnlDisplay');
  if (pnlDisplay) {
    if (pnlR !== null) {
      pnlDisplay.textContent = (pnlR >= 0 ? '+' : '') + pnlR.toFixed(2) + 'R';
      pnlDisplay.style.color = pnlR >= 0 ? 'var(--green)' : 'var(--red)';
    } else {
      pnlDisplay.textContent = '— (set entry/stop/TP1)';
      pnlDisplay.style.color = 'var(--muted)';
    }
  }

  const hitRow = document.getElementById('shadowHitRow');
  if (hitRow) hitRow.style.display = (hitTarget !== null || hitStop !== null) ? 'grid' : 'none';

  const hitTargetEl = document.getElementById('shadowHitTarget');
  if (hitTargetEl) {
    hitTargetEl.textContent = hitTarget === null ? '—' : (hitTarget ? '✓ YES' : '✗ NO');
    hitTargetEl.style.color = hitTarget ? 'var(--green)' : (hitTarget === false ? 'var(--red)' : 'var(--muted)');
  }

  const hitStopEl = document.getElementById('shadowHitStop');
  if (hitStopEl) {
    hitStopEl.textContent = hitStop === null ? '—' : (hitStop ? '✓ YES' : '✗ NO');
    hitStopEl.style.color = hitStop ? 'var(--red)' : (hitStop === false ? 'var(--green)' : 'var(--muted)');
  }

  // Cache interim values for saveShadowOutcome
  state._shadowOutcomeBuffer = { outcomePrice, pnlR, hitTarget, hitStop };
}

function saveShadowOutcome() {
  const buf = state._shadowOutcomeBuffer;
  if (!buf || !Number.isFinite(buf.outcomePrice)) {
    alert('Enter an actual price before saving the shadow outcome.');
    return;
  }

  const windowEl = document.getElementById('shadowCaptureWindow');
  const captureWindowHours = Number.parseInt(windowEl?.value || '24', 10) === 48 ? 48 : 24;

  state.shadowOutcome = {
    captureWindowHours,
    outcomePrice: buf.outcomePrice,
    outcomeCapturedAt: new Date().toISOString(),
    hitTarget: buf.hitTarget,
    hitStop: buf.hitStop,
    pnlR: buf.pnlR
  };

  const btn = document.querySelector('.shadow-save-btn');
  if (btn) {
    const orig = btn.textContent;
    btn.textContent = 'SAVED ✓';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => { btn.textContent = orig; btn.style.borderColor = ''; btn.style.color = ''; }, 2000);
  }
}

export { onAssetInput, setAsset, setBias, triggerUpload, handleUpload, toggleOverlaySlot, toggleCheck, getChecked, selectRadio, onSlider, toggleRRJustification, onDecisionModeChange, selectAARRadio, onAAROutcomeChange, onAARSlider, updateEdgeScore, handleAARPhotoUpload, onShadowModeChange, onShadowCaptureWindowChange, onShadowOutcomeInput, saveShadowOutcome };
