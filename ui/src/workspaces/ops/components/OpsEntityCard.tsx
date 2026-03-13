// ---------------------------------------------------------------------------
// OpsEntityCard — entity card with orb health indicator.
// Shows agent identity, role, health orb, and run state badge.
// Clickable for selection.
// ---------------------------------------------------------------------------

import type { OpsEntityViewModel } from "../adapters/opsViewModel";

export interface OpsEntityCardProps {
  entity: OpsEntityViewModel;
  selected: boolean;
  onClick: (id: string) => void;
}

const ORB_STYLES: Record<string, string> = {
  teal: "bg-teal-400 shadow-[0_0_8px_rgba(45,212,191,0.6)]",
  amber: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]",
  red: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]",
};

const HEALTH_ORB_OVERRIDE: Record<string, string> = {
  live: "bg-teal-400 shadow-[0_0_8px_rgba(45,212,191,0.6)]",
  recovered: "bg-teal-400 shadow-[0_0_8px_rgba(45,212,191,0.6)]",
  stale: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]",
  degraded: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]",
  unavailable: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]",
};

const RUN_STATE_LABELS: Record<string, { text: string; className: string }> = {
  idle: { text: "IDLE", className: "text-gray-500" },
  running: { text: "RUNNING", className: "text-cyan-400" },
  completed: { text: "COMPLETED", className: "text-teal-400" },
  failed: { text: "FAILED", className: "text-red-400" },
};

function resolveOrbStyle(entity: OpsEntityViewModel): string {
  if (entity.hasHealth && entity.healthState) {
    return HEALTH_ORB_OVERRIDE[entity.healthState] ?? ORB_STYLES[entity.orbColor] ?? ORB_STYLES.red;
  }
  if (!entity.hasHealth) {
    return "bg-gray-600 shadow-none";
  }
  return ORB_STYLES[entity.orbColor] ?? ORB_STYLES.red;
}

export function OpsEntityCard({ entity, selected, onClick }: OpsEntityCardProps) {
  const orbStyle = resolveOrbStyle(entity);
  const runLabel = entity.runState ? RUN_STATE_LABELS[entity.runState] : null;

  return (
    <button
      type="button"
      onClick={() => onClick(entity.id)}
      className={`w-full rounded-lg border p-3 text-left transition-colors ${
        selected
          ? "border-cyan-500/60 bg-cyan-950/30"
          : "border-gray-700/50 bg-gray-900/60 hover:border-cyan-600/40 hover:bg-gray-800/50"
      }`}
      aria-pressed={selected}
      data-testid={`entity-card-${entity.id}`}
    >
      <div className="flex items-center gap-3">
        {/* Orb indicator */}
        <span
          className={`inline-block h-3 w-3 shrink-0 rounded-full ${orbStyle}`}
          aria-hidden="true"
        />

        {/* Identity */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-gray-200">
              {entity.displayName}
            </span>
            {entity.supportsVerdict && (
              <span className="shrink-0 rounded bg-teal-900/40 px-1.5 py-0.5 text-[10px] font-medium uppercase text-teal-400">
                Verdict
              </span>
            )}
          </div>
          <p className="truncate text-xs text-gray-500">{entity.role}</p>
        </div>

        {/* Run state badge */}
        {runLabel && (
          <span className={`shrink-0 text-[10px] font-bold uppercase tracking-wider ${runLabel.className}`}>
            {runLabel.text}
          </span>
        )}

        {/* No health indicator */}
        {!entity.hasHealth && (
          <span className="shrink-0 text-[10px] font-medium uppercase tracking-wider text-gray-600">
            NO HEALTH
          </span>
        )}
      </div>

      {/* Capabilities */}
      {entity.capabilities.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {entity.capabilities.map((cap) => (
            <span
              key={cap}
              className="rounded bg-gray-800/60 px-1.5 py-0.5 text-[10px] text-gray-400"
            >
              {cap}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}
