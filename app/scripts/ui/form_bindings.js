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

export { onAssetInput, setAsset, setBias, triggerUpload, handleUpload, toggleCheck, getChecked, selectRadio, onSlider, toggleRRJustification, onDecisionModeChange };
