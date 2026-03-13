// ---------------------------------------------------------------------------
// UnavailableState — shown when data_state is "unavailable".
// Communicates that the data source is not available, not that the app failed.
// ---------------------------------------------------------------------------

export interface UnavailableStateProps {
  message?: string;
  description?: string;
}

export function UnavailableState({
  message = "Data unavailable",
  description = "The data source is currently unavailable. This may resolve on its own.",
}: UnavailableStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-amber-800/50 bg-amber-950/20 p-12 text-center">
      <p className="text-sm font-medium text-amber-400">{message}</p>
      {description && (
        <p className="mt-2 text-xs text-amber-600">{description}</p>
      )}
    </div>
  );
}
