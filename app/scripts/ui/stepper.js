import { state } from '../state/model.js';

let buildPromptRef = null;

export function setBuildPromptRef(fn) {
  buildPromptRef = fn;
}

export function goTo(step) {
  document.querySelectorAll('.section').forEach((s, i) => s.classList.toggle('active', i === step));
  document.querySelectorAll('.step').forEach((s, i) => {
    s.classList.remove('active', 'done');
    if (i === step) s.classList.add('active');
    if (i < step) s.classList.add('done');
  });
  state.currentStep = step;
  if (step === 5 && typeof buildPromptRef === 'function') buildPromptRef();
  if (step === 6) {
    const label = document.getElementById('aarTicketIdLabel');
    if (label) label.textContent = state.ticketID || '—';
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

export function goToChartsNext() {
  const anyUploaded = Object.values(state.uploads).some((v) => v !== null);
  const warn = document.getElementById('uploadWarning');
  if (!anyUploaded) {
    warn.classList.add('visible');
    setTimeout(() => {
      warn.classList.remove('visible');
      goTo(2);
    }, 2200);
  } else {
    goTo(2);
  }
}
