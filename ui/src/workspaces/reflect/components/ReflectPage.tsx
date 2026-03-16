// ---------------------------------------------------------------------------
// ReflectPage — workspace orchestrator with two-tab navigation.
// Overview (default): persona performance + pattern summary tables.
// Runs: run history list with inline run detail panel.
// ---------------------------------------------------------------------------

import { useState, useMemo, useCallback } from "react";
import { PanelShell } from "@shared/components/layout/PanelShell";
import { LoadingSkeleton } from "@shared/components/feedback/LoadingSkeleton";
import { EmptyState } from "@shared/components/feedback/EmptyState";
import { ErrorState } from "@shared/components/feedback/ErrorState";
import { useRuns } from "@shared/hooks/useRuns";
import { normalizeRunForReflect } from "../adapters/reflectAdapter";
import { PersonaPerformanceTable } from "./PersonaPerformanceTable";
import { PatternSummaryTable } from "./PatternSummaryTable";
import { RunDetailView } from "./RunDetailView";

type Tab = "overview" | "runs";

export function ReflectPage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const tabClass = (tab: Tab) =>
    `px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
      activeTab === tab
        ? "border-blue-500 text-blue-300"
        : "border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-600"
    }`;

  return (
    <PanelShell>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-200">Reflect</h2>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-800" data-testid="reflect-tab-bar">
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          className={tabClass("overview")}
          data-testid="tab-overview"
        >
          Overview
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("runs")}
          className={tabClass("runs")}
          data-testid="tab-runs"
        >
          Runs
        </button>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "runs" && (
        <RunsTab
          selectedRunId={selectedRunId}
          onSelectRun={setSelectedRunId}
          page={page}
          onPageChange={setPage}
        />
      )}
    </PanelShell>
  );
}

function OverviewTab() {
  return (
    <div className="space-y-8" data-testid="overview-tab">
      <section>
        <h3 className="mb-3 text-sm font-medium text-gray-400">
          Persona Performance
        </h3>
        <PersonaPerformanceTable />
      </section>
      <section>
        <h3 className="mb-3 text-sm font-medium text-gray-400">
          Pattern Summary
        </h3>
        <PatternSummaryTable />
      </section>
    </div>
  );
}

interface RunsTabProps {
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
  page: number;
  onPageChange: (page: number) => void;
}

function RunsTab({ selectedRunId, onSelectRun, page, onPageChange }: RunsTabProps) {
  const { data, isLoading, isError, error, refetch } = useRuns({ page });

  const items = useMemo(
    () => (data?.items ?? []).map(normalizeRunForReflect),
    [data],
  );

  const handleSelectRun = useCallback(
    (runId: string) => {
      onSelectRun(runId);
    },
    [onSelectRun],
  );

  return (
    <div
      className="grid grid-cols-1 gap-4 lg:grid-cols-2"
      data-testid="runs-tab"
    >
      {/* Run History panel */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-400">Run History</h3>

        {isLoading && <LoadingSkeleton rows={6} />}
        {isError && (
          <ErrorState
            message="Failed to load run history"
            detail={error?.message}
            onRetry={() => refetch()}
          />
        )}

        {!isLoading && !isError && items.length === 0 && (
          <EmptyState
            message="No analysis runs yet"
            description="Runs will appear here after analyses are executed."
          />
        )}

        {!isLoading && !isError && items.length > 0 && (
          <>
            <div className="space-y-1">
              {items.map((item) => (
                <button
                  key={item.runId}
                  type="button"
                  onClick={() => handleSelectRun(item.runId)}
                  className={`w-full rounded px-3 py-2 text-left text-sm transition-colors ${
                    selectedRunId === item.runId
                      ? "bg-blue-900/30 text-blue-300"
                      : "text-gray-300 hover:bg-gray-800"
                  }`}
                  data-testid={`run-item-${item.runId}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">
                      {item.instrument} {item.session}
                    </span>
                    <span className="text-xs text-gray-500">
                      {item.relativeTime}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-500">
                    <span>{item.finalDecision}</span>
                    <span
                      className={
                        item.runStatus === "completed"
                          ? "text-emerald-500"
                          : item.runStatus === "failed"
                            ? "text-red-500"
                            : "text-amber-500"
                      }
                    >
                      {item.runStatus}
                    </span>
                  </div>
                </button>
              ))}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between text-xs text-gray-500">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => onPageChange(page - 1)}
                className="rounded px-2 py-1 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
                data-testid="prev-page"
              >
                &lt; Prev
              </button>
              <span>Page {page}</span>
              <button
                type="button"
                disabled={!data?.has_next}
                onClick={() => onPageChange(page + 1)}
                className="rounded px-2 py-1 hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
                data-testid="next-page"
              >
                Next &gt;
              </button>
            </div>
          </>
        )}
      </div>

      {/* Run Detail panel */}
      <div>
        <h3 className="mb-3 text-sm font-medium text-gray-400">Run Detail</h3>
        <RunDetailView runId={selectedRunId} />
      </div>
    </div>
  );
}
