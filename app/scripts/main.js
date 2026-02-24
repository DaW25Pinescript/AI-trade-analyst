import { generateTicketID } from './state/model.js';
import { goTo, goToChartsNext, setBuildPromptRef } from './ui/stepper.js';
import { onAssetInput, setAsset, setBias, triggerUpload, handleUpload, toggleCheck, selectRadio, onSlider, toggleRRJustification } from './ui/form_bindings.js';
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

function syncOutputImpl() { if (document.getElementById('section-4')?.classList.contains('active')) buildPrompt(); }
function buildAndShow() { buildPrompt(); goTo(4); }
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

Object.assign(window, {
  goTo, goToChartsNext, onAssetInput, setAsset, setBias, triggerUpload, handleUpload,
  toggleCheck, selectRadio, onSlider, toggleRRJustification, syncOutput, buildAndShow,
  copyPrompt, exportHTML, exportPDF, exportJSONBackup, importJSONBackup,
  exportCSV, buildAARPrompt, buildWeeklyPrompt, resetForm
});

window.onload = () => {
  setSyncOutputHandler(syncOutputImpl);
  setBuildPromptRef(buildPrompt);
  generateTicketID();
  bindShortcuts({ goTo, buildAndShow });
};
