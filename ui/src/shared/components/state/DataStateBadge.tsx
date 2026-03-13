// ---------------------------------------------------------------------------
// DataStateBadge — renders the board-level data_state as a compact badge.
// Values: LIVE / STALE / UNAVAILABLE / DEMO-FALLBACK.
// Per DESIGN_NOTES §1.2: read-only — no dropdown, tooltip-expandable only.
// ---------------------------------------------------------------------------

interface DataStateBadgeProps {
  dataState: string | null;
}

const BADGE_STYLES: Record<string, string> = {
  live: "bg-emerald-900/60 text-emerald-300 border-emerald-700/50",
  stale: "bg-amber-900/60 text-amber-300 border-amber-700/50",
  unavailable: "bg-red-900/60 text-red-300 border-red-700/50",
  "demo-fallback": "bg-purple-900/60 text-purple-300 border-purple-700/50",
};

const DEFAULT_STYLE = "bg-gray-800 text-gray-400 border-gray-700";

export function DataStateBadge({ dataState }: DataStateBadgeProps) {
  const key = dataState?.toLowerCase() ?? "";
  const label = dataState?.toUpperCase() ?? "UNKNOWN";
  const style = BADGE_STYLES[key] ?? DEFAULT_STYLE;

  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold tracking-wide ${style}`}
      title={`Data state: ${label}`}
    >
      {label}
    </span>
  );
}
