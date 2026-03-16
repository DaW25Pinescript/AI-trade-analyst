// ---------------------------------------------------------------------------
// PatternSummaryTable — instrument × session verdict distribution table.
// Below-threshold buckets show "insufficient data". Flagged rows in amber.
// ---------------------------------------------------------------------------

import { useMemo } from "react";
import { LoadingSkeleton } from "@shared/components/feedback/LoadingSkeleton";
import { EmptyState } from "@shared/components/feedback/EmptyState";
import { ErrorState } from "@shared/components/feedback/ErrorState";
import { usePatternSummary } from "@shared/hooks/useReflect";
import {
  normalizePatternSummary,
  type PatternBucketViewModel,
} from "../adapters/reflectAdapter";

export function PatternSummaryTable() {
  const { data, isLoading, isError, error, refetch } = usePatternSummary();

  const viewModel = useMemo(
    () => (data ? normalizePatternSummary(data) : null),
    [data],
  );

  if (isLoading) return <LoadingSkeleton rows={4} />;
  if (isError) {
    return (
      <ErrorState
        message="Failed to load pattern summary"
        detail={error?.message}
        onRetry={() => refetch()}
      />
    );
  }
  if (!viewModel) return null;

  if (viewModel.buckets.length === 0) {
    return (
      <EmptyState
        message="No pattern data available"
        description="Run history is needed to generate pattern summaries."
      />
    );
  }

  const allBelowThreshold = viewModel.buckets.every((b) => !b.thresholdMet);
  if (allBelowThreshold) {
    return (
      <EmptyState
        message="Not enough run history in any instrument/session combination yet"
        description="More runs are needed before pattern summaries become available."
      />
    );
  }

  return (
    <div data-testid="pattern-summary-table">
      {viewModel.dataState === "stale" && (
        <div
          className="mb-3 rounded border border-amber-800/50 bg-amber-950/20 px-4 py-2 text-xs text-amber-300"
          data-testid="pattern-stale-banner"
        >
          Some run records could not be parsed — pattern data may be incomplete
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-xs font-medium uppercase text-gray-500">
              <th className="px-3 py-2">Instrument</th>
              <th className="px-3 py-2">Session</th>
              <th className="px-3 py-2">Runs</th>
              <th className="px-3 py-2">Verdicts</th>
              <th className="px-3 py-2">NO_TRADE %</th>
            </tr>
          </thead>
          <tbody>
            {viewModel.buckets.map((b: PatternBucketViewModel) => (
              <tr
                key={`${b.instrument}-${b.session}`}
                className={`border-b border-gray-800 ${b.flagged ? "text-amber-300" : "text-gray-300"}`}
              >
                <td className="px-3 py-2 font-medium">
                  {b.flagged ? `⚠ ${b.instrument}` : b.instrument}
                </td>
                <td className="px-3 py-2">{b.session}</td>
                <td className="px-3 py-2">{b.runCount}</td>
                <td className="px-3 py-2 text-xs">{b.verdictDisplay}</td>
                <td className="px-3 py-2">{b.noTradeRate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
