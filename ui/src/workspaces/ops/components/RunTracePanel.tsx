// ---------------------------------------------------------------------------
// RunTracePanel — orchestrates the Run mode view per PR_OPS_5_SPEC §8.3.
// Driven by useAgentTrace(runId). Shows run header, trace summary,
// stage timeline, participants, edges, arbiter summary.
// ---------------------------------------------------------------------------

import { useAgentTrace } from "@shared/hooks";
import { LoadingSkeleton, ErrorState } from "@shared/components/feedback";
import { OpsDataStateBanner } from "./OpsDataStateBanner";
import { TraceStageTimeline } from "./TraceStageTimeline";
import { TraceParticipantList } from "./TraceParticipantList";
import { TraceEdgeList } from "./TraceEdgeList";
import { ArbiterSummaryCard } from "./ArbiterSummaryCard";

export interface RunTracePanelProps {
  runId: string;
}

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function RunTracePanel({ runId }: RunTracePanelProps) {
  const traceQuery = useAgentTrace(runId);

  if (traceQuery.isLoading) {
    return <LoadingSkeleton rows={4} />;
  }

  if (traceQuery.isError) {
    const msg = traceQuery.error?.message ?? "Failed to load trace";
    const isNotFound =
      msg.includes("not found") || msg.includes("RUN_NOT_FOUND");
    return (
      <div data-testid="run-trace-error">
        <ErrorState
          message={isNotFound ? "Run not found" : "Trace unavailable"}
          detail={msg}
          onRetry={() => traceQuery.refetch()}
        />
      </div>
    );
  }

  const trace = traceQuery.data;
  if (!trace) return null;

  const isStale = trace.data_state === "stale";
  const stages = trace.stages ?? [];
  const participants = trace.participants ?? [];
  const edges = trace.edges ?? [];
  const artifacts = trace.artifacts ?? [];
  const timeframes = trace.summary?.timeframes ?? [];

  const isPartial = stages.some(
    (s) => s.status === "running" || s.status === "pending",
  );

  return (
    <div className="space-y-4" data-testid="run-trace-panel">
      {/* data_state banner */}
      {isStale && <OpsDataStateBanner source="Health" state="stale" />}

      {/* Run header */}
      <div
        className="rounded-lg border border-gray-700/40 bg-gray-900/40 p-4"
        data-testid="run-header"
      >
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Run ID
            </span>
            <p className="text-sm font-semibold text-gray-200 font-mono">
              {trace.run_id}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Instrument
            </span>
            <p className="text-sm font-semibold text-gray-200">
              {trace.summary?.instrument ?? "—"}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Session
            </span>
            <p className="text-sm text-gray-300">
              {trace.summary?.session ?? "—"}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Duration
            </span>
            <p className="text-sm text-gray-300">
              {formatDuration(trace.summary?.duration_ms ?? null)}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Data State
            </span>
            <p
              className={`text-sm font-medium uppercase ${
                trace.data_state === "live"
                  ? "text-teal-400"
                  : trace.data_state === "stale"
                    ? "text-amber-400"
                    : "text-red-400"
              }`}
            >
              {trace.data_state}
            </p>
          </div>
        </div>

        {/* Trace summary — verdict and confidence */}
        <div className="mt-3 flex flex-wrap items-center gap-4 border-t border-gray-800/40 pt-3">
          {trace.summary?.final_verdict && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Final Verdict
              </span>
              <p className="text-sm font-semibold text-gray-200 uppercase">
                {trace.summary.final_verdict}
              </p>
            </div>
          )}
          {trace.summary?.final_confidence != null && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Confidence
              </span>
              <p className="text-sm text-gray-300">
                {(trace.summary.final_confidence * 100).toFixed(0)}%
              </p>
            </div>
          )}
          {timeframes.length > 0 && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Timeframes
              </span>
              <p className="text-sm text-gray-300">
                {timeframes.join(", ")}
              </p>
            </div>
          )}
          {trace.summary?.completed_at && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Completed
              </span>
              <p className="text-sm text-gray-300">
                {new Date(trace.summary.completed_at).toLocaleString()}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Stage timeline */}
      {stages.length > 0 && (
        <TraceStageTimeline stages={stages} isPartial={isPartial} />
      )}

      {/* Participants */}
      {participants.length > 0 && (
        <TraceParticipantList participants={participants} />
      )}

      {/* Trace edges */}
      {edges.length > 0 && <TraceEdgeList edges={edges} />}

      {/* Arbiter summary — null → hidden per §11.5 */}
      {trace.arbiter_summary && (
        <ArbiterSummaryCard arbiter={trace.arbiter_summary} />
      )}

      {/* Artifact references */}
      {artifacts.length > 0 && (
        <section data-testid="trace-artifacts">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-widest text-gray-500">
            Artifacts
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {artifacts.map((a) => (
              <span
                key={a.path}
                className="rounded bg-gray-800/60 px-2 py-0.5 text-[10px] text-gray-400"
                title={a.path}
              >
                {a.name}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
