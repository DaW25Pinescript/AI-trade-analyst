export function TriageBoardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-200">Triage Board</h2>
        <p className="mt-1 text-sm text-gray-500">
          Phase 1 foundation shell — real data rendering in PR-UI-2
        </p>
      </div>

      <div className="rounded-lg border border-dashed border-gray-700 bg-gray-900 p-8">
        <div className="mx-auto max-w-md text-center">
          <p className="text-sm font-medium text-gray-400">
            Triage workspace placeholder
          </p>
          <p className="mt-2 text-xs text-gray-600">
            The typed API client for <code>/watchlist/triage</code> and{" "}
            <code>/triage</code> is compiled and ready. This page will render
            triage items, status badges, and action controls once PR-UI-2 lands.
          </p>
        </div>
      </div>
    </div>
  );
}
