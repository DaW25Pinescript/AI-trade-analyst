/**
 * StageStepper — Journey progress navigation
 *
 * Clearly distinguishes completed, current, and future stages.
 * Structured, not gamified. Uses semantic stage keys.
 */

import { STAGE_ORDER, STAGE_LABELS, StageKey } from '../types/journey.js';

/**
 * Creates a stage stepper element.
 * @param {Object} options
 * @param {string} options.currentStage - Current StageKey
 * @param {Function} [options.onStageClick] - Called with stageKey when a completed/current stage is clicked
 * @param {boolean} [options.gateBlocked] - If true, stages after gate_checks are visually locked
 * @returns {HTMLElement}
 */
export function createStageStepper({ currentStage, onStageClick, gateBlocked = false }) {
  const stepper = document.createElement('div');
  stepper.className = 'stage-stepper';

  const currentIdx = STAGE_ORDER.indexOf(currentStage);
  const gateIdx = STAGE_ORDER.indexOf(StageKey.GATE_CHECKS);

  STAGE_ORDER.forEach((stageKey, idx) => {
    const step = document.createElement('div');
    const isCompleted = idx < currentIdx;
    const isCurrent = idx === currentIdx;
    const isFuture = idx > currentIdx;
    const isLocked = gateBlocked && idx > gateIdx;

    let stateClass = 'stage-stepper__step--future';
    if (isCompleted) stateClass = 'stage-stepper__step--completed';
    if (isCurrent) stateClass = 'stage-stepper__step--current';
    if (isLocked) stateClass = 'stage-stepper__step--locked';

    step.className = `stage-stepper__step ${stateClass}`;

    step.innerHTML = `
      <div class="stage-stepper__indicator">
        <span class="stage-stepper__number">${isCompleted ? '✓' : idx + 1}</span>
      </div>
      <span class="stage-stepper__label">${STAGE_LABELS[stageKey]}</span>
    `;

    if ((isCompleted || isCurrent) && !isLocked && onStageClick) {
      step.style.cursor = 'pointer';
      step.addEventListener('click', () => onStageClick(stageKey));
    }

    stepper.appendChild(step);

    // Add connector line between steps (except last)
    if (idx < STAGE_ORDER.length - 1) {
      const connector = document.createElement('div');
      connector.className = `stage-stepper__connector ${isCompleted ? 'stage-stepper__connector--completed' : ''}`;
      stepper.appendChild(connector);
    }
  });

  return stepper;
}
