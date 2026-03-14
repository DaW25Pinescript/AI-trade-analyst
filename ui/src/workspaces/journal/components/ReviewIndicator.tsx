// ---------------------------------------------------------------------------
// ReviewIndicator — visual distinction for result linkage status.
// Shows "Has result" vs "Needs follow-up" in Review view only.
// ---------------------------------------------------------------------------

export interface ReviewIndicatorProps {
  hasResult: boolean;
}

export function ReviewIndicator({ hasResult }: ReviewIndicatorProps) {
  if (hasResult) {
    return (
      <span className="inline-flex items-center rounded-full bg-emerald-900/50 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
        Has result
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-full bg-amber-900/50 px-2.5 py-0.5 text-xs font-medium text-amber-300">
      Needs follow-up
    </span>
  );
}
