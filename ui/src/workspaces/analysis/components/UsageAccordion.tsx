// ---------------------------------------------------------------------------
// UsageAccordion — inline below verdict (DESIGN_NOTES §1.7).
//
// Closed by default, expandable on click.
// Tolerates empty-but-valid usage (artifact-missing modifier, not error).
// Usage fetch failure is a warning only — must not block verdict rendering.
// ---------------------------------------------------------------------------

import { useState } from "react";
import type { UsageViewModel } from "../adapters/analysisAdapter";

export interface UsageAccordionProps {
  usage: UsageViewModel;
}

export function UsageAccordion({ usage }: UsageAccordionProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-gray-700 rounded" data-testid="usage-accordion">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-gray-400 hover:bg-gray-800/50 transition-colors"
        data-testid="usage-toggle"
      >
        <span>Usage Summary</span>
        <span className="text-gray-600">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-700 px-3 py-3" data-testid="usage-content">
          {usage.loading && (
            <p className="text-xs text-gray-500">Loading usage data...</p>
          )}

          {!usage.loading && usage.artifactMissing && (
            <p className="text-xs text-gray-500" data-testid="usage-unavailable">
              Usage data unavailable
            </p>
          )}

          {!usage.loading && usage.available && (
            <div className="space-y-2 text-xs">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div>
                  <span className="text-gray-500">Total Tokens</span>
                  <p className="text-gray-300 font-mono" data-testid="usage-total-tokens">
                    {usage.totalTokens?.toLocaleString() ?? "—"}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">Prompt</span>
                  <p className="text-gray-300 font-mono">
                    {usage.promptTokens?.toLocaleString() ?? "—"}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">Completion</span>
                  <p className="text-gray-300 font-mono">
                    {usage.completionTokens?.toLocaleString() ?? "—"}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">Cost</span>
                  <p className="text-gray-300 font-mono" data-testid="usage-cost">
                    {usage.totalCost != null
                      ? `$${usage.totalCost.toFixed(4)}`
                      : "—"}
                  </p>
                </div>
              </div>
              {usage.totalCalls != null && (
                <div className="flex gap-4 text-gray-400">
                  <span>
                    Calls: {usage.totalCalls}
                  </span>
                  <span>
                    Successful: {usage.successfulCalls ?? 0}
                  </span>
                  <span>
                    Failed: {usage.failedCalls ?? 0}
                  </span>
                </div>
              )}
              {usage.modelBreakdown && Object.keys(usage.modelBreakdown).length > 0 && (
                <div>
                  <span className="text-gray-500">By Model</span>
                  <div className="mt-1 space-y-1">
                    {Object.entries(usage.modelBreakdown).map(([model, count]) => (
                      <div key={model} className="flex justify-between text-gray-400">
                        <span className="font-mono">{model}</span>
                        <span>{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
