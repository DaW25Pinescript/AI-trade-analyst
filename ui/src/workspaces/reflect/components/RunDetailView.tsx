// ---------------------------------------------------------------------------
// RunDetailView — full artifact bundle inspector for a selected run.
// Handles: loading, 404, stale+partial, no-selection states.
// ---------------------------------------------------------------------------

import { useMemo } from "react";
import { LoadingSkeleton } from "@shared/components/feedback/LoadingSkeleton";
import { ErrorState } from "@shared/components/feedback/ErrorState";
import { useRunBundle } from "@shared/hooks/useReflect";
import { normalizeRunBundle } from "../adapters/reflectAdapter";
import { UsageSummaryCard } from "./UsageSummaryCard";

interface RunDetailViewProps {
  runId: string | null;
}

export function RunDetailView({ runId }: RunDetailViewProps) {
  const { data, isLoading, isError, error, refetch } = useRunBundle(runId);

  const viewModel = useMemo(
    () => (data ? normalizeRunBundle(data) : null),
    [data],
  );

  if (!runId) {
    return (
      <div
        className="flex h-full items-center justify-center rounded border border-dashed border-gray-700 bg-gray-900/50 p-12"
        data-testid="run-detail-placeholder"
      >
        <p className="text-sm text-gray-500">
          Select a run from the history to inspect its details
        </p>
      </div>
    );
  }

  if (isLoading) return <LoadingSkeleton rows={8} />;

  if (isError) {
    const is404 =
      error?.message?.includes("not found") ||
      error?.message?.includes("RUN_NOT_FOUND");
    if (is404) {
      return (
        <div
          className="rounded border border-dashed border-gray-700 bg-gray-900/50 p-8 text-center"
          data-testid="run-not-found"
        >
          <p className="text-sm font-medium text-gray-400">
            This run could not be found. It may have been removed.
          </p>
          <p className="mt-2 text-xs text-gray-600">
            Select another run from the history to continue.
          </p>
        </div>
      );
    }
    return (
      <ErrorState
        message="Failed to load run details"
        detail={error?.message}
        onRetry={() => refetch()}
      />
    );
  }

  if (!viewModel) return null;

  return (
    <div className="space-y-4" data-testid="run-detail-view">
      {viewModel.dataState === "stale" && (
        <div
          className="rounded border border-amber-800/50 bg-amber-950/20 px-4 py-2 text-xs text-amber-300"
          data-testid="bundle-stale-banner"
        >
          Some artifacts are missing or malformed — details may be incomplete
        </div>
      )}

      {/* Run Header */}
      <div className="rounded border border-gray-800 bg-gray-900/50 p-4">
        <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
          Run Header
        </h4>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-gray-500">Run ID:</span>{" "}
            <span className="font-mono text-gray-300">{viewModel.runId}</span>
          </div>
          <div>
            <span className="text-gray-500">Timestamp:</span>{" "}
            <span className="text-gray-300">{viewModel.timestamp}</span>
          </div>
          <div>
            <span className="text-gray-500">Instrument:</span>{" "}
            <span className="text-gray-300">{viewModel.instrument}</span>
          </div>
          <div>
            <span className="text-gray-500">Session:</span>{" "}
            <span className="text-gray-300">{viewModel.session}</span>
          </div>
        </div>
      </div>

      {/* Verdict */}
      <div className="rounded border border-gray-800 bg-gray-900/50 p-4">
        <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
          Verdict
        </h4>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <span className="text-gray-500">Decision:</span>{" "}
            <span className="font-medium text-gray-200">
              {viewModel.verdict}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Confidence:</span>{" "}
            <span className="text-gray-300">{viewModel.arbiterConfidence}</span>
          </div>
          <div>
            <span className="text-gray-500">Method:</span>{" "}
            <span className="text-gray-300">{viewModel.arbiterMethod}</span>
          </div>
        </div>
      </div>

      {/* Analyst Contributions */}
      <div className="rounded border border-gray-800 bg-gray-900/50 p-4">
        <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
          Analyst Contributions
        </h4>
        {viewModel.analysts.length === 0 ? (
          <p className="text-sm text-gray-500">No analyst data available</p>
        ) : (
          <div className="space-y-2">
            {viewModel.analysts.map((a, i) => (
              <div
                key={i}
                className="flex items-center gap-4 text-sm text-gray-300"
              >
                <span className="min-w-[120px] font-medium">{a.persona}</span>
                <span className="text-gray-500">Status:</span>{" "}
                <span>{a.status}</span>
                <span className="text-gray-500">Stance:</span>{" "}
                <span>{a.stance}</span>
                <span className="text-gray-500">Confidence:</span>{" "}
                <span>{a.confidence}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Arbiter Notes */}
      <div className="rounded border border-gray-800 bg-gray-900/50 p-4">
        <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
          Arbiter Notes
        </h4>
        <div className="space-y-1 text-sm">
          <div>
            <span className="text-gray-500">Dissent Summary:</span>{" "}
            <span className="text-gray-300">{viewModel.dissentSummary}</span>
          </div>
          <div>
            <span className="text-gray-500">Override:</span>{" "}
            <span className="text-gray-300">{viewModel.overrideInfo}</span>
          </div>
        </div>
      </div>

      {/* Usage Summary */}
      <UsageSummaryCard usage={viewModel.usageSummary} />

      {/* Artifact Status */}
      <div
        className="rounded border border-gray-800 bg-gray-900/50 p-4"
        data-testid="artifact-status"
      >
        <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
          Artifact Status
        </h4>
        <div className="flex gap-4 text-sm">
          <ArtifactIndicator
            label="run_record"
            state={viewModel.artifactStatus.runRecord}
          />
          <ArtifactIndicator
            label="usage.jsonl"
            state={viewModel.artifactStatus.usageJsonl}
          />
          <ArtifactIndicator
            label="usage.json"
            state={viewModel.artifactStatus.usageJson}
          />
        </div>
      </div>
    </div>
  );
}

function ArtifactIndicator({
  label,
  state,
}: {
  label: string;
  state: string;
}) {
  const colorClass =
    state === "present"
      ? "text-emerald-400"
      : state === "malformed"
        ? "text-amber-400"
        : "text-gray-600";
  const icon = state === "present" ? "\u2713" : state === "malformed" ? "!" : "\u2717";

  return (
    <span className={`${colorClass}`}>
      <span className="mr-1">{icon}</span>
      {label}
    </span>
  );
}
