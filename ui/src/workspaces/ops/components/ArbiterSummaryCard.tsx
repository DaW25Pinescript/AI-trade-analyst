// ---------------------------------------------------------------------------
// ArbiterSummaryCard — arbiter summary block per PR_OPS_5_SPEC §11.4.
// Rendered distinctly when present. Null arbiter → component not rendered.
// ---------------------------------------------------------------------------

import type { ArbiterTraceSummary } from "@shared/api/ops";

export interface ArbiterSummaryCardProps {
  arbiter: ArbiterTraceSummary;
}

export function ArbiterSummaryCard({ arbiter }: ArbiterSummaryCardProps) {
  if (!arbiter) return null;

  return (
    <section
      className="rounded-lg border border-purple-800/40 bg-purple-950/20 p-4"
      data-testid="arbiter-summary-card"
    >
      <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-purple-400">
        Arbiter Summary
      </h4>
      <div className="space-y-2">
        {/* Verdict */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-500 w-24 shrink-0">
            Verdict
          </span>
          <span className="text-sm font-semibold text-gray-200 uppercase">
            {arbiter.verdict ?? "—"}
          </span>
        </div>

        {/* Confidence */}
        {arbiter.confidence != null && (
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wider text-gray-500 w-24 shrink-0">
              Confidence
            </span>
            <span className="text-sm text-gray-300">
              {(arbiter.confidence * 100).toFixed(0)}%
            </span>
          </div>
        )}

        {/* Method */}
        {arbiter.method && (
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wider text-gray-500 w-24 shrink-0">
              Method
            </span>
            <span className="text-sm text-gray-300">{arbiter.method}</span>
          </div>
        )}

        {/* Override */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium uppercase tracking-wider text-gray-500 w-24 shrink-0">
            Override
          </span>
          {arbiter.override_applied ? (
            <span className="text-sm font-bold text-amber-400 uppercase" data-testid="arbiter-override-applied">
              Yes
            </span>
          ) : (
            <span className="text-sm text-gray-500">No</span>
          )}
        </div>

        {/* Dissent summary */}
        {arbiter.dissent_summary && (
          <div className="mt-2 border-t border-purple-800/30 pt-2">
            <span className="text-[10px] font-medium uppercase tracking-wider text-gray-600">
              Dissent
            </span>
            <p className="mt-1 text-xs text-gray-400">
              {arbiter.dissent_summary}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
