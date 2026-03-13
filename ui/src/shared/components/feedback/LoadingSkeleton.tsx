// ---------------------------------------------------------------------------
// LoadingSkeleton — placeholder skeleton for loading state.
// ---------------------------------------------------------------------------

export interface LoadingSkeletonProps {
  rows?: number;
}

export function LoadingSkeleton({ rows = 5 }: LoadingSkeletonProps) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="flex animate-pulse items-center gap-4 rounded-lg border border-gray-800 bg-gray-900 p-4"
        >
          <div className="h-4 w-16 rounded bg-gray-800" />
          <div className="h-4 w-12 rounded bg-gray-800" />
          <div className="h-4 w-10 rounded bg-gray-800" />
          <div className="h-4 flex-1 rounded bg-gray-800" />
        </div>
      ))}
    </div>
  );
}
