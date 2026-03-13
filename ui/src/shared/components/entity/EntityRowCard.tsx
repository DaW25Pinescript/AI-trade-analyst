// ---------------------------------------------------------------------------
// EntityRowCard — generic ranked entity row with label, sublabel, metadata,
// and optional status indicators.
//
// Per DESIGN_NOTES §3: medium-density TradingView watchlist style.
// Entire row clickable with hover affordance.
//
// Decision (PR-UI-3): Made generic to remove triage-specific domain coupling.
// The triage workspace wraps this with TriageRowCard for domain-specific
// field mapping. See workspaces/triage/components/TriageRowCard.tsx.
// ---------------------------------------------------------------------------

import { StatusPill } from "@shared/components/state/StatusPill";
import type { StatusPillProps } from "@shared/components/state/StatusPill";

export interface EntityRowCardProps {
  /** Primary identifier displayed in the first column. */
  label: string;
  /** Optional status pill shown after the label. */
  pill?: StatusPillProps;
  /** Optional short metadata string shown right-aligned (e.g. "78%"). */
  meta?: string;
  /** Main descriptive text — gets the widest column. */
  description?: string;
  /** Optional trailing badge text (e.g. "STALE"). */
  badge?: { text: string; className: string };
  /** Row click handler. */
  onClick?: () => void;
}

export function EntityRowCard({
  label,
  pill,
  meta,
  description,
  badge,
  onClick,
}: EntityRowCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex w-full items-center gap-4 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-left transition-colors hover:border-gray-600 hover:bg-gray-800/70"
    >
      {/* Label */}
      <span className="w-20 shrink-0 text-sm font-semibold text-gray-100">
        {label}
      </span>

      {/* Status pill */}
      {pill && (
        <span className="w-20 shrink-0">
          <StatusPill label={pill.label} variant={pill.variant} />
        </span>
      )}

      {/* Meta */}
      {meta && (
        <span className="w-14 shrink-0 text-right text-xs tabular-nums text-gray-400">
          {meta}
        </span>
      )}

      {/* Description — widest column with breathing room */}
      <span className="min-w-0 flex-1 truncate text-sm text-gray-300">
        {description || (
          <span className="text-gray-600 italic">—</span>
        )}
      </span>

      {/* Optional trailing badge */}
      {badge && (
        <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium ${badge.className}`}>
          {badge.text}
        </span>
      )}

      {/* Arrow affordance */}
      <span className="shrink-0 text-gray-600 transition-colors group-hover:text-gray-400">
        ›
      </span>
    </button>
  );
}
