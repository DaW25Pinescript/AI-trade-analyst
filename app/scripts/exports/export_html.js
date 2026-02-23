import { state } from '../state/model.js';
import { buildPrompt } from '../generators/prompt_ticket.js';
import { _buildReportHTML } from '../generators/report_html.js';

export function exportHTML() {
  buildPrompt();
  const report = _buildReportHTML();
  const asset = (document.getElementById('asset').value || 'ASSET').replace(/[^a-z0-9_\-]/gi,'_');
  const blob = new Blob([report], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `AI_Trade_Brief_${state.ticketID || asset}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
