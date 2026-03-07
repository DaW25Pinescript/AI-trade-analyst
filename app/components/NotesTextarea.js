/**
 * NotesTextarea — User note input with provenance framing
 */

import { createProvenanceBadge } from './StatusBadge.js';

/**
 * Creates a notes textarea with provenance marker.
 * @param {Object} options
 * @param {string} [options.value]
 * @param {string} [options.placeholder]
 * @param {string} [options.label]
 * @param {string} [options.provenance] - Default 'user_manual'
 * @param {Function} [options.onChange]
 * @returns {HTMLElement}
 */
export function createNotesTextarea({
  value = '',
  placeholder = 'Add notes...',
  label = 'Notes',
  provenance = 'user_manual',
  onChange,
}) {
  const wrapper = document.createElement('div');
  wrapper.className = 'notes-textarea';

  const headerDiv = document.createElement('div');
  headerDiv.className = 'notes-textarea__header';
  headerDiv.innerHTML = `<label class="form-label">${label}</label>`;
  headerDiv.appendChild(createProvenanceBadge(provenance));
  wrapper.appendChild(headerDiv);

  const textarea = document.createElement('textarea');
  textarea.className = 'form-textarea notes-textarea__input';
  textarea.placeholder = placeholder;
  textarea.rows = 4;
  textarea.value = value;

  if (onChange) {
    textarea.addEventListener('change', (e) => onChange(e.target.value));
  }

  wrapper.appendChild(textarea);
  return wrapper;
}
