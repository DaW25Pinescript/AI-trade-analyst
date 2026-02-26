import { generateTicketID } from './state/model.js';
import { goTo, goToChartsNext, setBuildPromptRef } from './ui/stepper.js';
import { onAssetInput, setAsset, setBias, triggerUpload, handleUpload, toggleOverlaySlot, toggleCheck, selectRadio, onSlider, toggleRRJustification, onDecisionModeChange, selectAARRadio, onAAROutcomeChange, onAARSlider, updateEdgeScore, handleAARPhotoUpload } from './ui/form_bindings.js';
import { buildPrompt } from './generators/prompt_ticket.js';
import { exportHTML } from './exports/export_html.js';
import { exportPDF } from './exports/export_pdf_print.js';
import { exportJSONBackup } from './exports/export_json_backup.js';
import { importJSONBackup } from './exports/import_json_backup.js';
import { exportCSV } from './exports/export_csv.js';
import { buildAARPrompt } from './generators/prompt_aar.js';
import { buildWeeklyPrompt } from './generators/prompt_weekly.js';
import { bindShortcuts } from './ui/shortcuts.js';
import { setSyncOutputHandler, syncOutput } from './ui/sync_output.js';
import { runSenateArbiter } from './generators/senateArbiter.js';
import { generateAnalystPromptTemplate } from './generators/promptGenerator.js';
import { initSenatePanel, renderSenatePanel, clearSenatePanel } from './ui/arbiterPanel.js';
import { initDashboard } from './ui/dashboard.js';

function syncOutputImpl() { if (document.getElementById('section-5')?.classList.contains('active')) buildPrompt(); }
function buildAndShow() {
  buildPrompt();
  goTo(5);

  const now = new Date();
  const stamp = [
    now.getFullYear().toString(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0')
  ].join('') + '_' + [
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0')
  ].join('');

  exportJSONBackup({ silent: true, filenamePrefix: `AI_Trade_Journal_Backup_${stamp}` });
}
function copyPrompt() {
  const text = document.getElementById('outputText').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.copy-btn');
    const orig = btn.textContent;
    btn.textContent = 'COPIED ✓';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => { btn.textContent = orig; btn.style.borderColor = ''; btn.style.color = ''; }, 1800);
  });
}
function resetForm(){ location.reload(); }

function showAARPrompt() {
  const prompt = buildAARPrompt();
  const out = document.getElementById('aarOutputText');
  const wrap = document.getElementById('aarOutputWrap');
  if (out) out.textContent = prompt;
  if (wrap) wrap.style.display = 'block';
}

function copyAARPrompt() {
  const text = document.getElementById('aarOutputText')?.textContent;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.aar-copy-btn');
    if (!btn) return;
    const orig = btn.textContent;
    btn.textContent = 'COPIED ✓';
    btn.style.borderColor = 'var(--green)';
    btn.style.color = 'var(--green)';
    setTimeout(() => { btn.textContent = orig; btn.style.borderColor = ''; btn.style.color = ''; }, 1800);
  });
}

function runSenateArb() {
  const textarea = document.getElementById('senateAnalystInput');
  if (!textarea) return;
  let analystOutputs;
  try {
    analystOutputs = JSON.parse(textarea.value.trim());
  } catch (e) {
    alert('Invalid JSON in analyst input. Please check formatting.\n\n' + e.message);
    return;
  }
  if (!Array.isArray(analystOutputs)) {
    alert('Analyst input must be a JSON array of analyst objects.');
    return;
  }

  // Derive userSettings from current form state where available
  const get = id => (document.getElementById(id) ? document.getElementById(id).value : '') || '';
  const userSettings = {
    minRR:                  parseFloat(get('minRR')) || 2.0,
    maxRiskPercent:         parseFloat(get('maxStop')) || 1.0,
    sessionVolatilityState: get('volRisk') || 'Normal',
    regime:                 get('regime')  || 'Trending',
    instrument:             get('asset')   || 'Unknown',
    timestamp:              new Date().toISOString(),
    newsEventImminent:      false
  };

  const decision = runSenateArbiter(analystOutputs, userSettings);
  renderSenatePanel(decision);
}

function clearSenateArb() {
  clearSenatePanel();
  const textarea = document.getElementById('senateAnalystInput');
  if (textarea) textarea.value = '';
}

Object.assign(window, {
  goTo, goToChartsNext, onAssetInput, setAsset, setBias, triggerUpload, handleUpload,
  toggleOverlaySlot, toggleCheck, selectRadio, onSlider, toggleRRJustification, onDecisionModeChange,
  selectAARRadio, onAAROutcomeChange, onAARSlider, updateEdgeScore, handleAARPhotoUpload,
  syncOutput, buildAndShow, copyPrompt, exportHTML, exportPDF, exportJSONBackup,
  importJSONBackup, exportCSV, buildAARPrompt, buildWeeklyPrompt, resetForm,
  showAARPrompt, copyAARPrompt,
  runSenateArb, clearSenateArb,
  runSenateArbiter, generateAnalystPromptTemplate, renderSenatePanel
});

window.onload = () => {
  setSyncOutputHandler(syncOutputImpl);
  setBuildPromptRef(buildPrompt);
  generateTicketID();
  bindShortcuts({ goTo, buildAndShow });
  initSenatePanel();
  initDashboard();
};
