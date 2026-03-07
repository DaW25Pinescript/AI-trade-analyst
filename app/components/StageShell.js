/**
 * StageShell — Reusable journey stage layout wrapper
 *
 * Pattern from UI_STYLE_GUIDE.md Section 9.2:
 * - Top stepper / progress state
 * - Left visual / chart / evidence area
 * - Right interpretation / controls / notes area
 * - Bottom action row
 */

import { createStageStepper } from './StageStepper.js';
import { createPageHeader } from './PageHeader.js';
import { STAGE_LABELS } from '../types/journey.js';

/**
 * Creates a stage shell layout.
 * @param {Object} options
 * @param {string} options.stageKey - Current StageKey
 * @param {string} options.currentStage - Overall journey current stage
 * @param {string} [options.subtitle]
 * @param {Function} [options.onStageClick]
 * @param {Function} [options.onNext]
 * @param {Function} [options.onPrev]
 * @param {boolean} [options.nextDisabled]
 * @param {string} [options.nextLabel]
 * @param {boolean} [options.gateBlocked]
 * @returns {{ shell: HTMLElement, leftPanel: HTMLElement, rightPanel: HTMLElement }}
 */
export function createStageShell({
  stageKey,
  currentStage,
  subtitle,
  onStageClick,
  onNext,
  onPrev,
  nextDisabled = false,
  nextLabel = 'Continue',
  gateBlocked = false,
}) {
  const shell = document.createElement('div');
  shell.className = 'stage-shell';

  // Stepper
  const stepper = createStageStepper({ currentStage, onStageClick, gateBlocked });
  shell.appendChild(stepper);

  // Header
  const header = createPageHeader({
    title: STAGE_LABELS[stageKey] || stageKey,
    subtitle,
  });
  shell.appendChild(header);

  // Content area: left + right panels
  const content = document.createElement('div');
  content.className = 'stage-shell__content';

  const leftPanel = document.createElement('div');
  leftPanel.className = 'stage-shell__left';

  const rightPanel = document.createElement('div');
  rightPanel.className = 'stage-shell__right';

  content.appendChild(leftPanel);
  content.appendChild(rightPanel);
  shell.appendChild(content);

  // Action row
  const actions = document.createElement('div');
  actions.className = 'stage-shell__actions';

  if (onPrev) {
    const prevBtn = document.createElement('button');
    prevBtn.className = 'btn btn--secondary';
    prevBtn.textContent = 'Back';
    prevBtn.addEventListener('click', onPrev);
    actions.appendChild(prevBtn);
  } else {
    actions.appendChild(document.createElement('div')); // spacer
  }

  if (onNext) {
    const nextBtn = document.createElement('button');
    nextBtn.className = `btn btn--primary ${nextDisabled ? 'btn--disabled' : ''}`;
    nextBtn.textContent = nextLabel;
    nextBtn.disabled = nextDisabled;
    nextBtn.addEventListener('click', () => {
      if (!nextDisabled) onNext();
    });
    actions.appendChild(nextBtn);
  }

  shell.appendChild(actions);

  return { shell, leftPanel, rightPanel };
}
