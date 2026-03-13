// ---------------------------------------------------------------------------
// FeederHealthChip — compact feeder freshness signal.
// Part of the trust strip per DESIGN_NOTES §2.
// ---------------------------------------------------------------------------

import type { FeederHealth } from "@shared/api/feeder";

export interface FeederHealthChipProps {
  health: FeederHealth | undefined;
  isLoading: boolean;
  isError: boolean;
}

export function FeederHealthChip({
  health,
  isLoading,
  isError,
}: FeederHealthChipProps) {
  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-gray-700 bg-gray-800 px-2 py-0.5 text-xs text-gray-500">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gray-500" />
        Feeder…
      </span>
    );
  }

  if (isError || !health) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded border border-red-800/50 bg-red-900/30 px-2 py-0.5 text-xs text-red-400"
        title="Feeder health unavailable"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
        Feeder
      </span>
    );
  }

  const isStale = health.stale;
  const dotColor = isStale ? "bg-amber-400" : "bg-emerald-400";
  const chipStyle = isStale
    ? "border-amber-700/50 bg-amber-900/30 text-amber-300"
    : "border-emerald-700/50 bg-emerald-900/30 text-emerald-300";

  const ageLabel = formatAge(health.age_seconds);

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs ${chipStyle}`}
      title={`Feeder ${health.status} · ingested ${ageLabel} ago${health.regime ? ` · ${health.regime}` : ""}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
      Feeder {ageLabel}
    </span>
  );
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}
