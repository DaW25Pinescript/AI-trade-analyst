// ---------------------------------------------------------------------------
// Triage Board — PR-UI-2 implementation, PR-UI-3 barrel imports.
//
// Renders real triage data from GET /watchlist/triage with all 7 state
// conditions handled. Trust strip always visible. Per-row staleness from
// verdict_at only. Row click navigates to #/journey/{symbol}.
//
// Layout per UI_WORKSPACES §5 and DESIGN_NOTES §3:
// - Top bar: title + TrustStrip + "Run Triage" button
// - Main board: ranked TriageRowCard list
// ---------------------------------------------------------------------------

import { useNavigate } from "react-router-dom";
import { useWatchlistTriage, useFeederHealth } from "@shared/hooks";
import { PanelShell } from "@shared/components/layout";
import { TrustStrip } from "@shared/components/trust";
import { DataStateBadge } from "@shared/components/state";
import {
  LoadingSkeleton,
  EmptyState,
  UnavailableState,
  ErrorState,
} from "@shared/components/feedback";
import { buildTriageBoardViewModel } from "../adapters/triageViewModel";
import { useTriggerTriage } from "../hooks/useTriggerTriage";
import { TriageRowCard } from "../components/TriageRowCard";

export function TriageBoardPage() {
  const navigate = useNavigate();
  const triageQuery = useWatchlistTriage();
  const feederQuery = useFeederHealth();
  const triggerMutation = useTriggerTriage();

  const vm = buildTriageBoardViewModel(
    triageQuery.data ?? null,
    triageQuery.isLoading,
    triageQuery.isError,
  );

  const handleRowClick = (symbol: string) => {
    navigate(`/journey/${encodeURIComponent(symbol)}`);
  };

  const handleRunTriage = () => {
    if (!triggerMutation.isPending) {
      triggerMutation.mutate(undefined);
    }
  };

  return (
    <PanelShell>
      {/* Top bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-gray-200">
            Triage Board
          </h2>
          <TrustStrip
            dataState={vm.dataState}
            generatedAt={vm.generatedAt}
            feederHealth={feederQuery.data}
            feederLoading={feederQuery.isLoading}
            feederError={feederQuery.isError}
          />
        </div>

        <button
          type="button"
          onClick={handleRunTriage}
          disabled={triggerMutation.isPending}
          className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {triggerMutation.isPending ? "Running\u2026" : "Run Triage"}
        </button>
      </div>

      {/* Trigger error feedback */}
      {triggerMutation.isError && (
        <div className="rounded border border-red-800/50 bg-red-950/30 px-4 py-3">
          <p className="text-sm text-red-400">
            Triage failed: {triggerMutation.error.message}
          </p>
          {triggerMutation.error.partial && (
            <p className="mt-1 text-xs text-red-500">
              Partial results may have been written.
            </p>
          )}
          <button
            type="button"
            onClick={handleRunTriage}
            className="mt-2 text-xs font-medium text-red-300 underline hover:text-red-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* Stale warning banner */}
      {vm.condition === "stale" && (
        <div className="flex items-center gap-2 rounded border border-amber-800/50 bg-amber-950/20 px-4 py-2">
          <DataStateBadge dataState="stale" />
          <span className="text-xs text-amber-400">
            Triage data may be outdated. Run triage to refresh.
          </span>
        </div>
      )}

      {/* Demo-fallback banner */}
      {vm.condition === "demo-fallback" && (
        <div className="flex items-center gap-2 rounded border border-purple-800/50 bg-purple-950/20 px-4 py-2">
          <DataStateBadge dataState="demo-fallback" />
          <span className="text-xs text-purple-400">
            Showing demo/fallback data — not live triage results.
          </span>
        </div>
      )}

      {/* Board content — 7 state conditions */}
      {vm.condition === "loading" && <LoadingSkeleton rows={5} />}

      {vm.condition === "error" && (
        <ErrorState
          message="Failed to load triage data"
          detail={
            triageQuery.error instanceof Error
              ? triageQuery.error.message
              : undefined
          }
          onRetry={() => triageQuery.refetch()}
        />
      )}

      {vm.condition === "unavailable" && (
        <UnavailableState message="Triage data unavailable" />
      )}

      {vm.condition === "empty" && (
        <EmptyState
          message="No triage items"
          description="Run triage to generate items for your watchlist."
        />
      )}

      {(vm.condition === "ready" ||
        vm.condition === "stale" ||
        vm.condition === "demo-fallback") && (
        <div className="space-y-2">
          {vm.items.map((row) => (
            <TriageRowCard
              key={row.symbol}
              row={row}
              onClick={handleRowClick}
            />
          ))}
        </div>
      )}
    </PanelShell>
  );
}
