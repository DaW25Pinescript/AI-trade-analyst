// ---------------------------------------------------------------------------
// PersonaPerformanceTable — persona stats table for Reflect Overview tab.
// Displays persona performance metrics from the aggregation endpoint.
// Null metrics display as "—". Below-threshold shows welcoming message.
// ---------------------------------------------------------------------------

import { useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { LoadingSkeleton } from "@shared/components/feedback/LoadingSkeleton";
import { EmptyState } from "@shared/components/feedback/EmptyState";
import { ErrorState } from "@shared/components/feedback/ErrorState";
import { usePersonaPerformance } from "@shared/hooks/useReflect";
import {
  normalizePersonaPerformance,
  type PersonaViewModel,
} from "../adapters/reflectAdapter";

export function PersonaPerformanceTable() {
  const { data, isLoading, isError, error, refetch } =
    usePersonaPerformance();
  const navigate = useNavigate();

  const viewModel = useMemo(
    () => (data ? normalizePersonaPerformance(data) : null),
    [data],
  );

  const handleRowClick = useCallback(
    (p: PersonaViewModel) => {
      if (p.navigableEntityId) {
        navigate(`/ops?entity_id=${encodeURIComponent(p.navigableEntityId)}&mode=detail`);
      }
    },
    [navigate],
  );

  if (isLoading) return <LoadingSkeleton rows={5} />;
  if (isError) {
    return (
      <ErrorState
        message="Failed to load persona performance"
        detail={error?.message}
        onRetry={() => refetch()}
      />
    );
  }
  if (!viewModel) return null;

  if (!viewModel.thresholdMet) {
    return (
      <EmptyState
        message="Not enough run history yet"
        description={`Need at least ${viewModel.threshold} runs to show persona statistics.`}
      />
    );
  }

  return (
    <div data-testid="persona-performance-table">
      {viewModel.dataState === "stale" && (
        <div
          className="mb-3 rounded border border-amber-800/50 bg-amber-950/20 px-4 py-2 text-xs text-amber-300"
          data-testid="persona-stale-banner"
        >
          Some run records could not be parsed — statistics may be based on
          incomplete data
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-xs font-medium uppercase text-gray-500">
              <th className="px-3 py-2">Persona</th>
              <th className="px-3 py-2">Participation</th>
              <th className="px-3 py-2">Skipped</th>
              <th className="px-3 py-2">Failed</th>
              <th className="px-3 py-2">Override Rate</th>
              <th className="px-3 py-2">Stance Alignment</th>
              <th className="px-3 py-2">Avg Confidence</th>
            </tr>
          </thead>
          <tbody>
            {viewModel.personas.map((p: PersonaViewModel) => (
              <tr
                key={p.persona}
                className={`border-b border-gray-800 ${p.flagged ? "text-amber-300" : "text-gray-300"} ${p.navigableEntityId ? "cursor-pointer hover:bg-gray-800/50" : ""}`}
                onClick={p.navigableEntityId ? () => handleRowClick(p) : undefined}
                data-testid={`persona-row-${p.persona}`}
              >
                <td className="px-3 py-2 font-medium">
                  {p.flagged ? `⚠ ${p.persona}` : p.persona}
                </td>
                <td className="px-3 py-2">{p.participationRate}</td>
                <td className="px-3 py-2">{p.skipCount}</td>
                <td className="px-3 py-2">{p.failCount}</td>
                <td className="px-3 py-2">{p.overrideRate}</td>
                <td className="px-3 py-2">{p.stanceAlignment}</td>
                <td className="px-3 py-2">{p.avgConfidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p
        className="mt-3 text-xs text-gray-600"
        data-testid="persona-scan-footer"
      >
        {viewModel.scanFooter}
      </p>
    </div>
  );
}
