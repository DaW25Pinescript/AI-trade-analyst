// ---------------------------------------------------------------------------
// DecisionList — renders decision records for both Journal and Review views.
// Receives either DecisionRowViewModel[] or ReviewRowViewModel[].
// ---------------------------------------------------------------------------

import type { DecisionRowViewModel, ReviewRowViewModel } from "../adapters/journalAdapter";
import { DecisionRow } from "./DecisionRow";

export interface DecisionListProps {
  rows: DecisionRowViewModel[] | ReviewRowViewModel[];
  showReviewIndicator?: boolean;
  onRowClick: (instrument: string) => void;
}

export function DecisionList({ rows, showReviewIndicator, onRowClick }: DecisionListProps) {
  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <DecisionRow
          key={row.snapshotId}
          row={row}
          showReviewIndicator={showReviewIndicator}
          onClick={onRowClick}
        />
      ))}
    </div>
  );
}
