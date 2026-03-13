// ---------------------------------------------------------------------------
// EntityRowCard — triage row with symbol, bias, confidence, why_interesting.
//
// Per DESIGN_NOTES §3: medium-density TradingView watchlist style.
// Entire row clickable with hover affordance.
// why_interesting gets widest column and breathing room.
// Per DESIGN_NOTES §1.1: fresh rows show no badge, stale rows show badge.
// ---------------------------------------------------------------------------

import type { TriageRowViewModel } from "@workspaces/triage/adapters/triageViewModel";
import { StatusPill } from "@shared/components/state/StatusPill";

interface EntityRowCardProps {
  row: TriageRowViewModel;
  onClick: (symbol: string) => void;
}

function biasVariant(
  bias: string,
): "positive" | "negative" | "neutral" | "warning" {
  const b = bias.toLowerCase();
  if (b === "bullish" || b === "long") return "positive";
  if (b === "bearish" || b === "short") return "negative";
  if (b === "neutral" || b === "flat") return "neutral";
  return "warning";
}

function formatConfidence(c: number): string {
  if (c >= 1 && c <= 100) return `${Math.round(c)}%`;
  if (c > 0 && c <= 1) return `${Math.round(c * 100)}%`;
  return `${c}`;
}

export function EntityRowCard({ row, onClick }: EntityRowCardProps) {
  return (
    <button
      type="button"
      onClick={() => onClick(row.symbol)}
      className="group flex w-full items-center gap-4 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-left transition-colors hover:border-gray-600 hover:bg-gray-800/70"
    >
      {/* Symbol */}
      <span className="w-20 shrink-0 text-sm font-semibold text-gray-100">
        {row.symbol}
      </span>

      {/* Bias pill */}
      <span className="w-20 shrink-0">
        <StatusPill label={row.bias} variant={biasVariant(row.bias)} />
      </span>

      {/* Confidence */}
      <span className="w-14 shrink-0 text-right text-xs tabular-nums text-gray-400">
        {formatConfidence(row.confidence)}
      </span>

      {/* Why interesting — widest column with breathing room */}
      <span className="min-w-0 flex-1 truncate text-sm text-gray-300">
        {row.whyInteresting || (
          <span className="text-gray-600 italic">—</span>
        )}
      </span>

      {/* Per-row stale badge — only shown for stale rows */}
      {row.freshness === "stale" && (
        <span className="shrink-0 rounded border border-amber-700/50 bg-amber-900/40 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
          STALE
        </span>
      )}

      {/* Arrow affordance */}
      <span className="shrink-0 text-gray-600 transition-colors group-hover:text-gray-400">
        ›
      </span>
    </button>
  );
}
