// ---------------------------------------------------------------------------
// AgentOpsPage — Agent Operations workspace main page.
//
// Org / Structure mode: roster hierarchy + health overlay.
// Answers: "Why should I trust this system right now?"
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

type OpsMode = "org" | "run" | "health";

export function AgentOpsPage() {
  const rosterQuery = useAgentRoster();
  const healthQuery = useAgentHealth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode] = useState<OpsMode>("org");

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
            title="Requires run trace endpoint (Phase 7)"
            className="rounded px-3 py-1 text-xs font-medium text-gray-600 cursor-not-allowed"
          >
            Run
          </button>
          <button
            type="button"
            disabled
            title="Requires run trace endpoint (Phase 7)"
            className="rounded px-3 py-1 text-xs font-medium text-gray-600 cursor-not-allowed"
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

          {/* Summary / trust region */}
          <OpsSummaryBar vm={vm} />

          {/* Main content + optional detail panel */}
          <div className="flex gap-4">
            {/* Left: hierarchy */}
            <div className="min-w-0 flex-1 space-y-6">
              {/* Governance layer */}
              <OpsLayerSection
                title="Governance Layer"
                entities={vm.governanceLayer}
                selectedId={selectedId}
                onSelect={handleSelect}
              />

              {/* Officer layer */}
              <OpsLayerSection
                title="Officer Layer"
                entities={vm.officerLayer}
                selectedId={selectedId}
                onSelect={handleSelect}
              />

              {/* Department sections */}
              {vm.departments.map((dept) => (
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
