// ---------------------------------------------------------------------------
// EmptyState — shown when a valid response returns zero items.
// This is NOT an error — it means no items exist yet.
// ---------------------------------------------------------------------------

export interface EmptyStateProps {
  message?: string;
  description?: string;
}

export function EmptyState({
  message = "No triage items",
  description = "Run triage to generate items for your watchlist.",
}: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-gray-700 bg-gray-900/50 p-12 text-center">
      <p className="text-sm font-medium text-gray-400">{message}</p>
      {description && (
        <p className="mt-2 text-xs text-gray-600">{description}</p>
      )}
    </div>
  );
}
