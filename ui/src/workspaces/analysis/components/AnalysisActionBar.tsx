// ---------------------------------------------------------------------------
// AnalysisActionBar — submit, retry, and reset actions.
//
// No auto-retry on submission failure (UI_CONTRACT §12.2).
// Retry is explicit user action only.
// ---------------------------------------------------------------------------

import type { RunState } from "../state/runLifecycle";
import { canSubmit, canReset, isRunning } from "../state/runLifecycle";

export interface AnalysisActionBarProps {
  runState: RunState;
  onRetry: () => void;
  onReset: () => void;
}

export function AnalysisActionBar({
  runState,
  onRetry,
  onReset,
}: AnalysisActionBarProps) {
  const showRetry = runState === "failed";
  const showReset = canReset(runState);
  const running = isRunning(runState);

  if (canSubmit(runState)) return null;

  return (
    <div className="flex items-center justify-end gap-3" data-testid="action-bar">
      {running && (
        <span className="text-xs text-gray-500">
          Analysis in progress...
        </span>
      )}

      {showRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded border border-red-700 px-4 py-1.5 text-sm font-medium text-red-300 transition-colors hover:bg-red-900/30"
          data-testid="retry-btn"
        >
          Retry
        </button>
      )}

      {showReset && (
        <button
          type="button"
          onClick={onReset}
          className="rounded border border-gray-700 px-4 py-1.5 text-sm font-medium text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200"
          data-testid="reset-btn"
        >
          New Analysis
        </button>
      )}
    </div>
  );
}
