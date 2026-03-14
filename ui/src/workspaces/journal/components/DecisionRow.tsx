// ---------------------------------------------------------------------------
// DecisionRow — single decision record row.
// Shows instrument, verdict summary, saved_at, journey_status,
// and lateral navigation link to Journey Studio.
// Optionally renders ReviewIndicator in Review view.
// ---------------------------------------------------------------------------

import { EntityRowCard } from "@shared/components/entity/EntityRowCard";
import type { DecisionRowViewModel, ReviewRowViewModel } from "../adapters/journalAdapter";
import { ReviewIndicator } from "./ReviewIndicator";

export interface DecisionRowProps {
  row: DecisionRowViewModel | ReviewRowViewModel;
  showReviewIndicator?: boolean;
  onClick: (instrument: string) => void;
}

function isReviewRow(row: DecisionRowViewModel | ReviewRowViewModel): row is ReviewRowViewModel {
  return "hasResult" in row;
}

function formatSavedAt(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return isoString;
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function DecisionRow({ row, showReviewIndicator, onClick }: DecisionRowProps) {
  const description = [
    row.verdict && `Verdict: ${row.verdict}`,
    row.userDecision && `Decision: ${row.userDecision}`,
  ]
    .filter(Boolean)
    .join(" · ") || undefined;

  const badge = showReviewIndicator && isReviewRow(row)
    ? undefined // ReviewIndicator handled separately below
    : undefined;

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1">
        <EntityRowCard
          label={row.instrument}
          pill={{ label: row.journeyStatus, variant: "default" }}
          meta={formatSavedAt(row.savedAt)}
          description={description}
          badge={badge}
          onClick={() => onClick(row.instrument)}
        />
      </div>
      {showReviewIndicator && isReviewRow(row) && (
        <div className="shrink-0">
          <ReviewIndicator hasResult={row.hasResult} />
        </div>
      )}
    </div>
  );
}
