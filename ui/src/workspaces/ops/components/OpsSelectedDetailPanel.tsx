// ---------------------------------------------------------------------------
// OpsSelectedDetailPanel — detail surface for a selected entity.
// Shows full identity, health, run state, and capabilities.
// ---------------------------------------------------------------------------

import type { OpsEntityViewModel } from "../adapters/opsViewModel";

export interface OpsSelectedDetailPanelProps {
  entity: OpsEntityViewModel;
  onClose: () => void;
}

const HEALTH_STATE_LABELS: Record<string, { text: string; className: string }> = {
  live: { text: "Live", className: "text-teal-400" },
  recovered: { text: "Recovered", className: "text-teal-400" },
  stale: { text: "Stale", className: "text-amber-400" },
  degraded: { text: "Degraded", className: "text-amber-400" },
  unavailable: { text: "Unavailable", className: "text-red-400" },
};

const RUN_STATE_LABELS: Record<string, { text: string; className: string }> = {
  idle: { text: "Idle", className: "text-gray-400" },
  running: { text: "Running", className: "text-cyan-400" },
  completed: { text: "Completed", className: "text-teal-400" },
  failed: { text: "Failed", className: "text-red-400" },
};

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="w-28 shrink-0 text-[11px] font-medium uppercase tracking-wider text-gray-600">
        {label}
      </span>
      <span className="text-sm text-gray-300">{children}</span>
    </div>
  );
}

export function OpsSelectedDetailPanel({
  entity,
  onClose,
}: OpsSelectedDetailPanelProps) {
  const healthLabel = entity.healthState
    ? HEALTH_STATE_LABELS[entity.healthState]
    : null;
  const runLabel = entity.runState
    ? RUN_STATE_LABELS[entity.runState]
    : null;

  return (
    <aside
      className="rounded-lg border border-gray-700/50 bg-gray-900/60 p-4"
      data-testid="selected-detail-panel"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">
          {entity.displayName}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          aria-label="Close detail panel"
        >
          Close
        </button>
      </div>

      {/* Identity */}
      <div className="space-y-0 divide-y divide-gray-800/50">
        <DetailRow label="ID">{entity.id}</DetailRow>
        <DetailRow label="Type">
          <span className="uppercase">{entity.type}</span>
        </DetailRow>
        <DetailRow label="Role">{entity.role}</DetailRow>
        <DetailRow label="Visual Family">
          <span className="uppercase">{entity.visualFamily}</span>
        </DetailRow>
        {entity.department && (
          <DetailRow label="Department">
            <span className="uppercase">{entity.department}</span>
          </DetailRow>
        )}
        <DetailRow label="Verdict">
          {entity.supportsVerdict ? "Yes" : "No"}
        </DetailRow>

        {/* Health */}
        {entity.hasHealth ? (
          <>
            <DetailRow label="Health">
              {healthLabel ? (
                <span className={healthLabel.className}>{healthLabel.text}</span>
              ) : (
                "—"
              )}
            </DetailRow>
            <DetailRow label="Run State">
              {runLabel ? (
                <span className={runLabel.className}>{runLabel.text}</span>
              ) : (
                "—"
              )}
            </DetailRow>
            {entity.lastActiveAt && (
              <DetailRow label="Last Active">
                {new Date(entity.lastActiveAt).toLocaleString()}
              </DetailRow>
            )}
            {entity.lastRunId && (
              <DetailRow label="Last Run">{entity.lastRunId}</DetailRow>
            )}
            {entity.healthSummary && (
              <DetailRow label="Summary">{entity.healthSummary}</DetailRow>
            )}
            {entity.recentEventSummary && (
              <DetailRow label="Recent">{entity.recentEventSummary}</DetailRow>
            )}
          </>
        ) : (
          <DetailRow label="Health">
            <span className="text-gray-600">No health data available</span>
          </DetailRow>
        )}
      </div>

      {/* Capabilities */}
      {entity.capabilities.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-gray-600">
            Capabilities
          </p>
          <div className="flex flex-wrap gap-1.5">
            {entity.capabilities.map((cap) => (
              <span
                key={cap}
                className="rounded bg-gray-800/60 px-2 py-0.5 text-xs text-gray-400"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
