// ---------------------------------------------------------------------------
// AgentOpsPage — Agent Operations workspace main page.
//
// Modes: Org (structural view), Health (operator attention view).
// Run mode is disabled pending PR-OPS-5b.
//
// State handling per AGENT_OPS_CONTRACT.md:
//   - loading
//   - healthy success (ready)
//   - roster success + health failure (degraded)
//   - roster success + empty health (empty-health)
//   - roster failure (error — workspace-level block)
// ---------------------------------------------------------------------------

import { useState, useMemo, useCallback } from "react";
import { useAgentRoster, useAgentHealth } from "@shared/hooks";
import { PanelShell } from "@shared/components/layout";
import { LoadingSkeleton, ErrorState } from "@shared/components/feedback";
import { buildOpsWorkspaceViewModel } from "../adapters/opsViewModel";
import type { OpsEntityViewModel } from "../adapters/opsViewModel";
import { OpsSummaryBar } from "./OpsSummaryBar";
import { OpsLayerSection } from "./OpsLayerSection";
import { OpsDepartmentSection } from "./OpsDepartmentSection";
import { OpsSelectedDetailPanel } from "./OpsSelectedDetailPanel";
import { OpsDegradedBanner } from "./OpsDegradedBanner";
import { OpsDataStateBanner } from "./OpsDataStateBanner";

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

  // Find selected entity across all layers
  const selectedEntity = useMemo((): OpsEntityViewModel | null => {
    if (!selectedId) return null;
    const all = [
      ...vm.governanceLayer,
      ...vm.officerLayer,
      ...vm.departments.flatMap((d) => d.entities),
    ];
    return all.find((e) => e.id === selectedId) ?? null;
  }, [selectedId, vm]);

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
            disabled
            title="Requires run trace wiring (PR-OPS-5b)"
            className="rounded px-3 py-1 text-xs font-medium text-gray-600 cursor-not-allowed"
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
          {/* Degraded banners */}
          {vm.condition === "degraded" && (
            <OpsDegradedBanner variant="health-failed" />
          )}
          {vm.condition === "empty-health" && (
            <OpsDegradedBanner variant="empty-health" />
          )}

          {/* data_state banners per §5.6 */}
          {vm.rosterDataState === "stale" && (
            <OpsDataStateBanner source="Roster" state="stale" />
          )}
          {vm.healthDataState === "stale" && (
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

            {/* Right: selected detail panel */}
            {selectedEntity && (
              <div className="hidden w-80 shrink-0 lg:block">
                <OpsSelectedDetailPanel
                  entity={selectedEntity}
                  onClose={handleCloseDetail}
                />
              </div>
            )}
          </div>

          {/* Detail panel for small screens — below content */}
          {selectedEntity && (
            <div className="lg:hidden">
              <OpsSelectedDetailPanel
                entity={selectedEntity}
                onClose={handleCloseDetail}
              />
            </div>
          )}
        </>
      )}
    </PanelShell>
  );
}
