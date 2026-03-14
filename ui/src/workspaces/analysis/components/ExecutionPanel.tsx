// ---------------------------------------------------------------------------
// ExecutionPanel — run lifecycle state display.
//
// Shows idle/running/completed/failed states with appropriate visual cues.
// Running state shows spinner with elapsed time counter.
// No fake progress indicators (UI_CONTRACT §7, §8).
//
// Streaming extensibility: vertical layout accommodates a future event log
// below the spinner. A comment marks where streaming events would render.
// ---------------------------------------------------------------------------

import { PanelShell } from "@shared/components/layout";
import { StatusPill } from "@shared/components/state";
import type { RunLifecycleState } from "../state/runLifecycle";
import type { ErrorViewModel } from "../adapters/analysisAdapter";

export interface ExecutionPanelProps {
  lifecycle: RunLifecycleState;
  elapsedMs: number;
  error: ErrorViewModel | null;
}

function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  }
  return `${secs}s`;
}

export function ExecutionPanel({
  lifecycle,
  elapsedMs,
  error,
}: ExecutionPanelProps) {
  const { state, run_id, request_id } = lifecycle;

  return (
    <PanelShell>
      <div className="space-y-4" data-testid="execution-panel">
        {/* Idle state */}
        {state === "idle" && (
          <div className="rounded-lg border border-dashed border-gray-700 bg-gray-900/50 p-8 text-center">
            <p className="text-sm text-gray-500">
              Configure and submit an analysis to begin
            </p>
          </div>
        )}

        {/* Validating state */}
        {state === "validating" && (
          <div className="rounded-lg border border-amber-800/30 bg-amber-950/10 p-6 text-center">
            <p className="text-sm text-amber-400">Validating submission...</p>
          </div>
        )}

        {/* Submitting / Running state */}
        {(state === "submitting" || state === "running") && (
          <div className="rounded-lg border border-blue-800/30 bg-blue-950/10 p-8">
            <div className="flex flex-col items-center gap-4">
              {/* Spinner */}
              <div
                className="h-8 w-8 animate-spin rounded-full border-2 border-blue-800 border-t-blue-400"
                data-testid="run-spinner"
              />
              <p className="text-sm font-medium text-blue-300">
                Analysis running...
              </p>
              <p className="text-xs text-gray-500" data-testid="elapsed-time">
                Elapsed: {formatElapsed(elapsedMs)}
              </p>
              {run_id && (
                <p className="text-xs text-gray-600 font-mono">
                  Run: {run_id}
                </p>
              )}
              {request_id && (
                <p className="text-xs text-gray-600 font-mono">
                  Request: {request_id}
                </p>
              )}
            </div>

            {/* ---- Streaming event log placeholder ----
             * Future streaming implementation (Phase 3B) will render
             * analyst_done, heartbeat, and progress events here.
             * The vertical layout accommodates an event list below
             * the spinner without redesign.
             */}
          </div>
        )}

        {/* Completed state */}
        {state === "completed" && (
          <div className="rounded-lg border border-emerald-800/30 bg-emerald-950/10 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <StatusPill label="Completed" variant="positive" />
                <span className="text-sm text-gray-300">
                  Analysis complete
                </span>
              </div>
              <div className="text-right">
                {run_id && (
                  <p className="text-xs text-gray-500 font-mono" data-testid="completed-run-id">
                    Run: {run_id}
                  </p>
                )}
                {elapsedMs > 0 && (
                  <p className="text-xs text-gray-600">
                    Duration: {formatElapsed(elapsedMs)}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Failed state */}
        {state === "failed" && (
          <div className="rounded-lg border border-red-800/30 bg-red-950/10 p-6">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <StatusPill label="Failed" variant="negative" />
                <span className="text-sm text-red-300">Analysis failed</span>
              </div>
              {error && (
                <div className="rounded border border-red-800/30 bg-red-950/20 px-3 py-2">
                  <p className="text-sm text-red-400" data-testid="error-message">
                    {error.message}
                  </p>
                  {error.code && (
                    <p className="mt-1 text-xs text-red-600">
                      Code: {error.code}
                    </p>
                  )}
                </div>
              )}
              <div className="text-right space-y-1">
                {(run_id || error?.runId) && (
                  <p className="text-xs text-gray-600 font-mono" data-testid="failed-run-id">
                    Run: {run_id ?? error?.runId}
                  </p>
                )}
                {(request_id || error?.requestId) && (
                  <p className="text-xs text-gray-600 font-mono" data-testid="failed-request-id">
                    Request: {request_id ?? error?.requestId}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </PanelShell>
  );
}
