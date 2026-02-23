import { state, generateTicketID } from '../state/model.js';
import { evaluateGate } from './gates.js';

function onAssetInput() {
  generateTicketID();
  window.syncOutput?.();
}

// ═══════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════

function setAsset(val) {
  document.getElementById('asset').value = val;
  generateTicketID();
  window.syncOutput?.();
}

function setBias(el) {
  document.querySelectorAll('.bias-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  state.currentBias = el.dataset.val;
  window.syncOutput?.();
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
  reader.onerror = () => alert(`Failed to read file: ${file.name}`);
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
  window.syncOutput?.();
}

function onSlider() {
  const v = document.getElementById('confluenceScore').value;
  document.getElementById('confVal').textContent = v;
  window.syncOutput?.();
}

// ═══════════════════════════════════════
// R:R EXCEPTION TOGGLE
// ═══════════════════════════════════════

function toggleRRJustification() {
  const show = document.getElementById('rrException').value === 'yes';
  document.getElementById('rrJustWrap').style.display = show ? 'block' : 'none';
}

// ═══════════════════════════════════════
// BUILD PROMPT
// ═══════════════════════════════════════

export { onAssetInput, setAsset, setBias, triggerUpload, handleUpload, toggleCheck, getChecked, selectRadio, onSlider, toggleRRJustification };
