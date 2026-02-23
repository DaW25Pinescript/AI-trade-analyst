import { state } from '../state/model.js';

export function exportJSONBackup() {
  const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `AI_Trade_Backup_${state.ticketID || 'draft'}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
