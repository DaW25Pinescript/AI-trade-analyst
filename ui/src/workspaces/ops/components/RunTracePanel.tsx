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

  if (!trace.run_status || !trace.stages?.length) {
    return (
      <div data-testid="run-trace-contract-mismatch">
        <ErrorState
          message="Trace data unavailable"
          detail="Required trace fields are missing. The run may still be in progress or the trace is incomplete."
        />
      </div>
    );
  }

  const isStale = trace.data_state === "stale";
  const stages = trace.stages ?? [];
  const participants = trace.participants ?? [];
  const traceEdges = trace.trace_edges ?? [];
  const artifactRefs = trace.artifact_refs ?? [];

  const isPartial = trace.run_status === "partial";

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
              {trace.instrument ?? "—"}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Session
            </span>
            <p className="text-sm text-gray-300">
              {trace.session ?? "—"}
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

        {/* Trace summary — bias and decision */}
        <div className="mt-3 flex flex-wrap items-center gap-4 border-t border-gray-800/40 pt-3">
          {trace.summary?.final_bias && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Final Bias
              </span>
              <p className="text-sm font-semibold text-gray-200 uppercase">
                {trace.summary.final_bias}
              </p>
            </div>
          )}
          {trace.summary?.final_decision && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Decision
              </span>
              <p className="text-sm text-gray-300">
                {trace.summary.final_decision}
              </p>
            </div>
          )}
          {trace.finished_at && (
            <div>
              <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
                Completed
              </span>
              <p className="text-sm text-gray-300">
                {new Date(trace.finished_at).toLocaleString()}
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
      {traceEdges.length > 0 && <TraceEdgeList edges={traceEdges} />}

      {/* Arbiter summary — null → hidden per §11.5 */}
      {trace.arbiter_summary && (
        <ArbiterSummaryCard arbiter={trace.arbiter_summary} />
      )}

      {/* Artifact references */}
      {artifactRefs.length > 0 && (
        <section data-testid="trace-artifacts">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-widest text-gray-500">
            Artifacts
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {artifactRefs.map((a) => (
              <span
                key={a.artifact_key}
                className="rounded bg-gray-800/60 px-2 py-0.5 text-[10px] text-gray-400"
                title={a.artifact_key}
              >
                {a.artifact_type}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
