// ---------------------------------------------------------------------------
// RunBrowserPanel — browsable, paginated, filterable run index (PR-RUN-1).
//
// Primary run selector for Agent Ops Run mode. Replaces paste-field as
// the default entry point. Click a row to load its trace.
//
// Spec: docs/specs/PR_RUN_1_SPEC.md §6.6
// ---------------------------------------------------------------------------

import { useState, useCallback } from "react";
import { useRuns } from "@shared/hooks";
import { LoadingSkeleton, EmptyState, ErrorState } from "@shared/components/feedback";
import type { RunBrowserItem } from "@shared/api/runs";

export interface RunBrowserPanelProps {
  onSelectRun: (runId: string | null) => void;
}

const STATUS_LABELS: Record<string, { text: string; className: string }> = {
  completed: { text: "OK", className: "text-emerald-400" },
  partial: { text: "Partial", className: "text-amber-400" },
  failed: { text: "Failed", className: "text-red-400" },
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  } catch {
    return iso;
  }
}

export function RunBrowserPanel({ onSelectRun }: RunBrowserPanelProps) {
  const [page, setPage] = useState(1);
  const [instrument, setInstrument] = useState<string | null>(null);
  const [session, setSession] = useState<string | null>(null);
  const pageSize = 20;

  const query = useRuns({ page, pageSize, instrument, session });

  const handleInstrumentChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const val = e.target.value || null;
      setInstrument(val);
      setPage(1);
    },
    [],
  );

  const handleSessionChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const val = e.target.value || null;
      setSession(val);
      setPage(1);
    },
    [],
  );

  const handleRowClick = useCallback(
    (item: RunBrowserItem) => {
      if (!item.trace_available) return;
      onSelectRun(item.run_id);
    },
    [onSelectRun],
  );

  // Loading
  if (query.isLoading) {
    return (
      <div data-testid="run-browser-loading">
        <LoadingSkeleton rows={5} />
      </div>
    );
  }

  // Error
  if (query.isError) {
    return (
      <div data-testid="run-browser-error">
        <ErrorState
          message="Failed to load runs"
          detail={query.error?.message}
          onRetry={() => query.refetch()}
        />
      </div>
    );
  }

  const data = query.data;
  if (!data) return null;

  // Empty
  if (data.total === 0) {
    return (
      <div data-testid="run-browser-empty">
        <EmptyState
          message="No analysis runs found"
          description="Runs will appear here after the analysis pipeline completes."
        />
      </div>
    );
  }

  // Build filter option sets from current results for convenience
  const instruments = [...new Set(data.items.map((i) => i.instrument).filter(Boolean))] as string[];
  const sessions = [...new Set(data.items.map((i) => i.session).filter(Boolean))] as string[];

  return (
    <div className="space-y-3" data-testid="run-browser-panel">
      {/* Filter controls */}
      <div className="flex items-center gap-3" data-testid="run-browser-filters">
        <select
          value={instrument ?? ""}
          onChange={handleInstrumentChange}
          className="rounded border border-gray-700/50 bg-gray-900/60 px-2 py-1 text-xs text-gray-300 focus:border-cyan-600/50 focus:outline-none"
          data-testid="instrument-filter"
        >
          <option value="">All instruments</option>
          {instruments.map((inst) => (
            <option key={inst} value={inst}>
              {inst}
            </option>
          ))}
        </select>

        <select
          value={session ?? ""}
          onChange={handleSessionChange}
          className="rounded border border-gray-700/50 bg-gray-900/60 px-2 py-1 text-xs text-gray-300 focus:border-cyan-600/50 focus:outline-none"
          data-testid="session-filter"
        >
          <option value="">All sessions</option>
          {sessions.map((sess) => (
            <option key={sess} value={sess}>
              {sess}
            </option>
          ))}
        </select>
      </div>

      {/* Run list */}
      <div className="space-y-1">
        {data.items.map((item) => {
          const statusInfo = STATUS_LABELS[item.run_status] ?? {
            text: item.run_status,
            className: "text-gray-500",
          };

          return (
            <button
              key={item.run_id}
              type="button"
              onClick={() => handleRowClick(item)}
              disabled={!item.trace_available}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                item.trace_available
                  ? "border-gray-700/40 bg-gray-900/40 hover:border-cyan-700/50 hover:bg-gray-800/60 cursor-pointer"
                  : "border-gray-800/30 bg-gray-950/30 opacity-50 cursor-not-allowed"
              }`}
              data-testid="run-browser-row"
            >
              <span className="w-16 shrink-0 font-mono text-gray-400">
                {item.instrument ?? "—"}
              </span>
              <span className="w-12 shrink-0 text-gray-500">
                {item.session ?? "—"}
              </span>
              <span className="w-16 shrink-0 text-gray-500">
                {formatTimestamp(item.timestamp)}
              </span>
              <span className={`w-14 shrink-0 font-medium ${statusInfo.className}`}>
                {statusInfo.text}
              </span>
              <span className="flex-1 truncate text-gray-400">
                {item.final_decision ?? "—"}
              </span>
            </button>
          );
        })}
      </div>

      {/* Pagination */}
      <div
        className="flex items-center justify-between text-xs text-gray-500"
        data-testid="run-browser-pagination"
      >
        <button
          type="button"
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="rounded px-2 py-1 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          data-testid="pagination-prev"
        >
          Prev
        </button>
        <span>
          Page {data.page} ({data.total} runs)
        </span>
        <button
          type="button"
          onClick={() => setPage((p) => p + 1)}
          disabled={!data.has_next}
          className="rounded px-2 py-1 hover:text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          data-testid="pagination-next"
        >
          Next
        </button>
      </div>
    </div>
  );
}
