// ---------------------------------------------------------------------------
// JournalHeader — workspace title, view toggle, and header summary.
// Displays decision count (Journal) or outcome coverage (Review).
// ---------------------------------------------------------------------------

import type { JournalHeaderSummary } from "../adapters/journalAdapter";

export type JournalView = "journal" | "review";

export interface JournalHeaderProps {
  activeView: JournalView;
  onViewChange: (view: JournalView) => void;
  summary: JournalHeaderSummary;
}

export function JournalHeader({ activeView, onViewChange, summary }: JournalHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-semibold text-gray-200">
          Journal & Review
        </h2>
        {summary.text && (
          <span className="text-sm text-gray-400">{summary.text}</span>
        )}
      </div>

      <div className="flex rounded-lg border border-gray-700 bg-gray-900">
        <button
          type="button"
          onClick={() => onViewChange("journal")}
          className={`px-4 py-1.5 text-sm font-medium transition-colors ${
            activeView === "journal"
              ? "bg-gray-700 text-gray-100"
              : "text-gray-400 hover:text-gray-200"
          } rounded-l-lg`}
        >
          Journal
        </button>
        <button
          type="button"
          onClick={() => onViewChange("review")}
          className={`px-4 py-1.5 text-sm font-medium transition-colors ${
            activeView === "review"
              ? "bg-gray-700 text-gray-100"
              : "text-gray-400 hover:text-gray-200"
          } rounded-r-lg`}
        >
          Review
        </button>
      </div>
    </div>
  );
}
