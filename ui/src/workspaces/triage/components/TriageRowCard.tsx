// ---------------------------------------------------------------------------
// TriageRowCard — triage-specific wrapper around the shared EntityRowCard.
//
// Maps TriageRowViewModel fields to the generic EntityRowCard props.
// Per DESIGN_NOTES §3: medium-density TradingView watchlist style.
// Per DESIGN_NOTES §1.1: fresh rows show no badge, stale rows show badge.
// ---------------------------------------------------------------------------

import { EntityRowCard } from "@shared/components/entity/EntityRowCard";
import type { TriageRowViewModel } from "../adapters/triageViewModel";

export interface TriageRowCardProps {
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

export function TriageRowCard({ row, onClick }: TriageRowCardProps) {
  return (
    <EntityRowCard
      label={row.symbol}
      pill={{ label: row.bias, variant: biasVariant(row.bias) }}
      meta={formatConfidence(row.confidence)}
      description={row.whyInteresting}
      badge={
        row.freshness === "stale"
          ? {
              text: "STALE",
              className:
                "border-amber-700/50 bg-amber-900/40 text-amber-400",
            }
          : undefined
      }
      onClick={() => onClick(row.symbol)}
    />
  );
}
