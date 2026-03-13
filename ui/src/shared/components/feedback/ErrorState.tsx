// ---------------------------------------------------------------------------
// ErrorState — shown when a fetch fails entirely.
// Supports optional retry action.
// ---------------------------------------------------------------------------

export interface ErrorStateProps {
  message?: string;
  detail?: string;
  onRetry?: () => void;
}

export function ErrorState({
  message = "Failed to load data",
  detail,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-red-800/50 bg-red-950/20 p-12 text-center">
      <p className="text-sm font-medium text-red-400">{message}</p>
      {detail && <p className="mt-2 text-xs text-red-600">{detail}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded bg-red-900/50 px-4 py-1.5 text-xs font-medium text-red-300 hover:bg-red-900/70 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
