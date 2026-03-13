// ---------------------------------------------------------------------------
// OpsSummaryBar — summary / trust region.
// Shows entity counts and health breakdown at a glance.
// Answers: "Why should I trust this system right now?"
// ---------------------------------------------------------------------------

import type { OpsWorkspaceViewModel } from "../adapters/opsViewModel";

export interface OpsSummaryBarProps {
  vm: OpsWorkspaceViewModel;
}

export function OpsSummaryBar({ vm }: OpsSummaryBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-700/40 bg-gray-900/40 px-4 py-3">
      {/* Entity count */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wider text-gray-500">
          Entities
        </span>
        <span className="text-sm font-semibold text-gray-200">
          {vm.entityCount}
        </span>
      </div>

      <span className="text-gray-700">|</span>

      {/* Healthy */}
      <div className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 rounded-full bg-teal-400 shadow-[0_0_6px_rgba(45,212,191,0.5)]" />
        <span className="text-xs text-gray-400">
          {vm.healthyCount} healthy
        </span>
      </div>

      {/* Degraded */}
      {vm.degradedCount > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]" />
          <span className="text-xs text-gray-400">
            {vm.degradedCount} degraded
          </span>
        </div>
      )}

      {/* Unavailable */}
      {vm.unavailableCount > 0 && (
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]" />
          <span className="text-xs text-gray-400">
            {vm.unavailableCount} unavailable
          </span>
        </div>
      )}

      <span className="text-gray-700">|</span>

      {/* Data state */}
      <span className="text-[10px] font-medium uppercase tracking-widest text-gray-600">
        Roster: {vm.rosterDataState ?? "—"}
      </span>
      <span className="text-[10px] font-medium uppercase tracking-widest text-gray-600">
        Health: {vm.healthDataState ?? "—"}
      </span>

      {/* Generated at */}
      {vm.generatedAt && (
        <span className="ml-auto text-[10px] text-gray-600">
          {new Date(vm.generatedAt).toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}
