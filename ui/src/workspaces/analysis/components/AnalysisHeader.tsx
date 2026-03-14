// ---------------------------------------------------------------------------
// AnalysisHeader — workspace header with instrument, provenance breadcrumb,
// and "Return to Journey" link when escalated.
//
// Per DESIGN_NOTES §1.8: always shows provenance when escalated.
// ---------------------------------------------------------------------------

import { StatusPill } from "@shared/components/state";
import type { RunLifecycleState } from "../state/runLifecycle";

export interface AnalysisHeaderProps {
  instrument: string | null;
  lifecycle: RunLifecycleState;
  escalatedFrom: string | null;
  onReturnToJourney: (() => void) | null;
}

const STATE_VARIANTS: Record<string, "default" | "positive" | "negative" | "neutral" | "warning"> = {
  idle: "neutral",
  validating: "warning",
  submitting: "warning",
  running: "warning",
  completed: "positive",
  failed: "negative",
};

const STATE_LABELS: Record<string, string> = {
  idle: "Ready",
  validating: "Validating",
  submitting: "Submitting",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

export function AnalysisHeader({
  instrument,
  lifecycle,
  escalatedFrom,
  onReturnToJourney,
}: AnalysisHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4" data-testid="analysis-header">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-semibold text-gray-200">
          Analysis Run
        </h2>
        {instrument && (
          <span className="rounded bg-gray-800 px-2.5 py-1 text-sm font-mono font-medium text-blue-300">
            {instrument}
          </span>
        )}
        {escalatedFrom && (
          <span className="text-xs text-gray-500" data-testid="provenance-breadcrumb">
            Escalated from Journey Studio
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <StatusPill
          label={STATE_LABELS[lifecycle.state] ?? lifecycle.state}
          variant={STATE_VARIANTS[lifecycle.state] ?? "default"}
        />
        {lifecycle.run_id && (
          <span className="text-xs text-gray-600 font-mono" data-testid="run-id-display">
            {lifecycle.run_id.slice(0, 12)}
          </span>
        )}
        {onReturnToJourney && (
          <button
            type="button"
            onClick={onReturnToJourney}
            className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
            data-testid="return-to-journey"
          >
            Return to Journey
          </button>
        )}
      </div>
    </div>
  );
}
