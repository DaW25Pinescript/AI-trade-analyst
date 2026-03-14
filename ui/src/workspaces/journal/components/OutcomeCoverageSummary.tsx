// ---------------------------------------------------------------------------
// OutcomeCoverageSummary — compact header element for Review view.
// Displays "X of Y decisions have results".
// ---------------------------------------------------------------------------

import type { OutcomeCoverage } from "../adapters/journalAdapter";

export interface OutcomeCoverageSummaryProps {
  coverage: OutcomeCoverage;
}

export function OutcomeCoverageSummary({ coverage }: OutcomeCoverageSummaryProps) {
  return (
    <span className="text-sm text-gray-400">
      {coverage.text}
    </span>
  );
}
