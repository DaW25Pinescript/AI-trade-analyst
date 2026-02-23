import { buildPrompt } from '../generators/prompt_ticket.js';
import { _buildReportHTML } from '../generators/report_html.js';

export function exportPDF() {
  buildPrompt();
  const report = _buildReportHTML();
  const w = window.open('', '_blank');
  if (!w) { alert('Popup blocked — please allow popups and try again.'); return; }
  w.document.open();
  w.document.write(report);
  w.document.close();
  w.focus();
  w.print();
}
