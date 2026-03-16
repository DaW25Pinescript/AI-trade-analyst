// ---------------------------------------------------------------------------
// AgentOpsPage — Agent Operations workspace main page.
//
// Modes: Org (structural view), Health (operator attention view),
//        Run (trace-driven view for a selected run).
//
// State handling per AGENT_OPS_CONTRACT.md:
//   - loading
//   - healthy success (ready)
//   - roster success + health failure (degraded)
//   - roster success + empty health (empty-health)
//   - roster failure (error — workspace-level block)
// ---------------------------------------------------------------------------

import { useState, useMemo, useCallback, useEffect } from "react";
import { useAgentRoster, useAgentHealth, useTimeframes } from "@shared/hooks";
import { PanelShell } from "@shared/components/layout";
import { LoadingSkeleton, ErrorState } from "@shared/components/feedback";
import { buildOpsWorkspaceViewModel } from "../adapters/opsViewModel";
import type { OpsEntityViewModel } from "../adapters/opsViewModel";
import { OpsSummaryBar } from "./OpsSummaryBar";
import { OpsLayerSection } from "./OpsLayerSection";
import { OpsDepartmentSection } from "./OpsDepartmentSection";
import { OpsDegradedBanner } from "./OpsDegradedBanner";
import { OpsDataStateBanner } from "./OpsDataStateBanner";
import { RunSelector } from "./RunSelector";
import { RunBrowserPanel } from "./RunBrowserPanel";
import { RunTracePanel } from "./RunTracePanel";
import { CandlestickChart } from "./CandlestickChart";
import { AgentDetailSidebar } from "./AgentDetailSidebar";

type OpsMode = "org" | "run" | "health";

/** Sort entities to elevate non-healthy to the top for Health mode. */
function elevateDegraded(entities: OpsEntityViewModel[]): OpsEntityViewModel[] {
  const priority: Record<string, number> = {
    unavailable: 0,
    degraded: 1,
    stale: 2,
    recovered: 3,
    live: 4,
  };
  return [...entities].sort((a, b) => {
    const pa = a.hasHealth ? (priority[a.healthState ?? "live"] ?? 4) : -1;
    const pb = b.hasHealth ? (priority[b.healthState ?? "live"] ?? 4) : -1;
    return pa - pb;
  });
}

export function AgentOpsPage() {
  const rosterQuery = useAgentRoster();
  const healthQuery = useAgentHealth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<OpsMode>("org");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedInstrument, setSelectedInstrument] = useState<string | null>(null);
  const [selectedRunTimestamp, setSelectedRunTimestamp] = useState<string | null>(null);
  const [selectedRunVerdict, setSelectedRunVerdict] = useState<string | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState<string | null>(null);

  // Timeframe discovery for the selected instrument (PR-CHART-2)
  const tfQuery = useTimeframes(selectedInstrument);
  const availableTimeframes = tfQuery.data?.available_timeframes ?? null;

  // Deterministic TF fallback on instrument change per §4.3
  useEffect(() => {
    if (!availableTimeframes || availableTimeframes.length === 0) {
      setSelectedTimeframe(null);
      return;
    }
    // Keep current TF if still valid
    if (selectedTimeframe && availableTimeframes.includes(selectedTimeframe)) {
      return;
    }
    // Fallback: 4h → first available
    if (availableTimeframes.includes("4h")) {
      setSelectedTimeframe("4h");
    } else {
      setSelectedTimeframe(availableTimeframes[0]);
    }
  }, [availableTimeframes]); // intentionally only depends on availableTimeframes

  const vm = useMemo(
    () =>
      buildOpsWorkspaceViewModel(
        rosterQuery.data ?? null,
        healthQuery.data ?? null,
        rosterQuery.isLoading,
        healthQuery.isLoading,
        rosterQuery.isError,
        healthQuery.isError,
      ),
    [
      rosterQuery.data,
      healthQuery.data,
      rosterQuery.isLoading,
      healthQuery.isLoading,
      rosterQuery.isError,
      healthQuery.isError,
    ],
  );

  // In Health mode, elevate degraded/stale/unavailable entities
  const displayGovernance = useMemo(
    () =>
      mode === "health"
        ? elevateDegraded(vm.governanceLayer)
        : vm.governanceLayer,
    [mode, vm.governanceLayer],
  );
  const displayOfficers = useMemo(
    () =>
      mode === "health"
        ? elevateDegraded(vm.officerLayer)
        : vm.officerLayer,
    [mode, vm.officerLayer],
  );
  const displayDepartments = useMemo(
    () =>
      mode === "health"
        ? vm.departments.map((d) => ({
            ...d,
            entities: elevateDegraded(d.entities),
          }))
        : vm.departments,
    [mode, vm.departments],
  );

  const handleSelect = useCallback((id: string) => {
    setSelectedId((prev) => (prev === id ? null : id));
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedId(null);
  }, []);

  const handleModeChange = useCallback((newMode: OpsMode) => {
    setMode(newMode);
    // Selection preserved across mode switch per §7.4
  }, []);

  const handleSelectRun = useCallback((
    runId: string | null,
    instrument?: string | null,
    timestamp?: string | null,
    finalDecision?: string | null,
  ) => {
    setSelectedRunId(runId);
    setSelectedInstrument(instrument ?? null);
    setSelectedRunTimestamp(timestamp ?? null);
    setSelectedRunVerdict(finalDecision ?? null);
  }, []);

  // Navigate to Run mode from detail sidebar's "last run" link
  const handleNavigateToRun = useCallback((runId: string) => {
    setSelectedRunId(runId);
    setMode("run");
  }, []);

  // Determine whether to show the backend-backed detail sidebar
  // In Org/Health modes with a selected entity, show the full detail sidebar
  const showDetailSidebar = selectedId !== null && mode !== "run";

  return (
    <PanelShell>
      {/* Top bar: title + mode pills */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-gray-200">
          Agent Operations
        </h2>

        {/* Mode pills */}
        <div className="flex items-center gap-1 rounded-lg border border-gray-700/50 bg-gray-900/40 p-1">
          <button
            type="button"
            onClick={() => handleModeChange("org")}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
              mode === "org"
                ? "bg-cyan-900/40 text-cyan-300"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            Org
          </button>
          <button
            type="button"
            onClick={() => handleModeChange("run")}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
              mode === "run"
                ? "bg-cyan-900/40 text-cyan-300"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            Run
          </button>
          <button
            type="button"
            onClick={() => handleModeChange("health")}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
              mode === "health"
                ? "bg-cyan-900/40 text-cyan-300"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            Health
          </button>
        </div>
      </div>

      {/* Loading */}
      {vm.condition === "loading" && <LoadingSkeleton rows={6} />}

      {/* Roster error — workspace-level block */}
      {vm.condition === "error" && (
        <ErrorState
          message="Failed to load agent roster"
          detail={
            rosterQuery.error instanceof Error
              ? rosterQuery.error.message
              : undefined
          }
          onRetry={() => {
            rosterQuery.refetch();
            healthQuery.refetch();
          }}
        />
      )}

      {/* Roster succeeded — render workspace content */}
      {(vm.condition === "ready" ||
        vm.condition === "degraded" ||
        vm.condition === "empty-health") && (
        <>
          {/* Degraded banners (Org/Health modes) */}
          {mode !== "run" && vm.condition === "degraded" && (
            <OpsDegradedBanner variant="health-failed" />
          )}
          {mode !== "run" && vm.condition === "empty-health" && (
            <OpsDegradedBanner variant="empty-health" />
          )}

          {/* data_state banners per §5.6 (Org/Health modes) */}
          {mode !== "run" && vm.rosterDataState === "stale" && (
            <OpsDataStateBanner source="Roster" state="stale" />
          )}
          {mode !== "run" && vm.healthDataState === "stale" && (
            <OpsDataStateBanner source="Health" state="stale" />
          )}

          {/* Health mode attention header */}
          {mode === "health" && (
            <div
              className="flex items-center gap-2 rounded border border-cyan-800/40 bg-cyan-950/20 px-4 py-2"
              data-testid="health-mode-header"
            >
              <span className="text-xs font-bold uppercase tracking-widest text-cyan-400">
                Health Mode
              </span>
              <span className="text-xs text-cyan-600">
                Degraded and stale entities elevated for operator attention
              </span>
            </div>
          )}

          {/* Run mode */}
          {mode === "run" && (
            <div className="space-y-4" data-testid="run-mode-view">
              <RunBrowserPanel onSelectRun={handleSelectRun} />

              {/* Demoted paste-field — secondary input */}
              <div className="border-t border-gray-800/50 pt-3">
                <p className="mb-2 text-center text-xs text-gray-600">
                  — or enter run ID directly —
                </p>
                <RunSelector
                  currentRunId={selectedRunId}
                  onSelectRun={handleSelectRun}
                />
              </div>

              {selectedRunId && selectedInstrument && (
                <>
                  {/* TF discovery states per §5.3 */}
                  {tfQuery.isLoading && (
                    <div className="rounded-lg border border-gray-700/40 bg-gray-900/40 px-4 py-2" data-testid="tf-loading">
                      <p className="text-xs text-gray-500">Loading timeframes…</p>
                    </div>
                  )}
                  {tfQuery.isError && (
                    <div className="rounded-lg border border-amber-800/40 bg-amber-950/20 px-4 py-2" data-testid="tf-discovery-failed">
                      <p className="text-xs text-amber-400">Unable to load chart timeframes.</p>
                    </div>
                  )}
                  {!tfQuery.isLoading && !tfQuery.isError && availableTimeframes && availableTimeframes.length === 0 && (
                    <div className="rounded-lg border border-gray-700/40 bg-gray-900/40 px-4 py-2" data-testid="tf-no-timeframes">
                      <p className="text-xs text-gray-500">No chart timeframes available for this instrument.</p>
                    </div>
                  )}
                  <CandlestickChart
                    instrument={selectedInstrument}
                    selectedRunTimestamp={selectedRunTimestamp}
                    selectedRunVerdict={selectedRunVerdict}
                    availableTimeframes={availableTimeframes}
                    selectedTimeframe={selectedTimeframe}
                    onTimeframeChange={setSelectedTimeframe}
                  />
                </>
              )}

              {selectedRunId && <RunTracePanel runId={selectedRunId} />}
            </div>
          )}

          {/* Org/Health mode content */}
          {mode !== "run" && (
            <>
              {/* Summary / trust region */}
              <OpsSummaryBar vm={vm} />

              {/* Main content + optional detail panel */}
              <div className="flex gap-4">
                {/* Left: hierarchy */}
                <div className="min-w-0 flex-1 space-y-6">
                  {/* Governance layer */}
                  <OpsLayerSection
                    title="Governance Layer"
                    entities={displayGovernance}
                    selectedId={selectedId}
                    onSelect={handleSelect}
                  />

                  {/* Officer layer */}
                  <OpsLayerSection
                    title="Officer Layer"
                    entities={displayOfficers}
                    selectedId={selectedId}
                    onSelect={handleSelect}
                  />

                  {/* Department sections */}
                  {displayDepartments.map((dept) => (
                    <OpsDepartmentSection
                      key={dept.key}
                      department={dept}
                      selectedId={selectedId}
                      onSelect={handleSelect}
                    />
                  ))}
                </div>

                {/* Right: backend-backed detail sidebar */}
                {showDetailSidebar && (
                  <div className="hidden w-80 shrink-0 lg:block">
                    <AgentDetailSidebar
                      entityId={selectedId!}
                      onClose={handleCloseDetail}
                      onSelectRun={handleNavigateToRun}
                    />
                  </div>
                )}
              </div>

              {/* Detail sidebar for small screens — below content */}
              {showDetailSidebar && (
                <div className="lg:hidden">
                  <AgentDetailSidebar
                    entityId={selectedId!}
                    onClose={handleCloseDetail}
                    onSelectRun={handleNavigateToRun}
                  />
                </div>
              )}
            </>
          )}
        </>
      )}
    </PanelShell>
  );
}
