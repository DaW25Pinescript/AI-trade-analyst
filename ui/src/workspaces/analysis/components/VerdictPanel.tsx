// ---------------------------------------------------------------------------
// VerdictPanel — full FinalVerdict at expert density.
//
// All fields visible — no "show more" collapse. Expert execution surface.
// Disabled with "No verdict — run failed" on failure state.
// Never implies partial output exists on a terminal failed state.
// ---------------------------------------------------------------------------

import { PanelShell } from "@shared/components/layout";
import { StatusPill } from "@shared/components/state";
import type { VerdictViewModel, UsageViewModel } from "../adapters/analysisAdapter";
import type { TicketDraft } from "../types";
import { UsageAccordion } from "./UsageAccordion";

export interface VerdictPanelProps {
  verdict: VerdictViewModel | null;
  ticketDraft: TicketDraft | null;
  usage: UsageViewModel;
  disabled: boolean;
  disabledReason: string | null;
}

const BIAS_VARIANTS: Record<string, "positive" | "negative" | "neutral" | "default"> = {
  bullish: "positive",
  bearish: "negative",
  neutral: "neutral",
  ranging: "neutral",
};

const DECISION_VARIANTS: Record<string, "positive" | "negative" | "warning" | "neutral"> = {
  ENTER_LONG: "positive",
  ENTER_SHORT: "negative",
  WAIT_FOR_CONFIRMATION: "warning",
  NO_TRADE: "neutral",
};

export function VerdictPanel({
  verdict,
  ticketDraft,
  usage,
  disabled,
  disabledReason,
}: VerdictPanelProps) {
  if (disabled || !verdict) {
    return (
      <PanelShell>
        <div
          className="rounded-lg border border-dashed border-gray-700 bg-gray-900/50 p-12 text-center opacity-60"
          data-testid="verdict-disabled"
        >
          <p className="text-sm font-medium text-gray-500">
            {disabledReason ?? "Submit to see verdict"}
          </p>
        </div>
      </PanelShell>
    );
  }

  return (
    <PanelShell>
      <div className="space-y-5" data-testid="verdict-panel">
        {/* Decision + Bias header */}
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill
            label={verdict.decision.replace(/_/g, " ")}
            variant={DECISION_VARIANTS[verdict.decision] ?? "default"}
          />
          <StatusPill
            label={verdict.finalBias}
            variant={BIAS_VARIANTS[verdict.finalBias] ?? "default"}
          />
          <span className="text-xs text-gray-500" data-testid="confidence-display">
            Confidence: {(verdict.overallConfidence * 100).toFixed(0)}%
          </span>
          <span className="text-xs text-gray-500" data-testid="agreement-display">
            Agreement: {verdict.analystAgreementPct}%
          </span>
        </div>

        {/* Approved Setups */}
        {verdict.approvedSetups.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Approved Setups
            </h4>
            <div className="space-y-2">
              {verdict.approvedSetups.map((setup, i) => (
                <div
                  key={i}
                  className="rounded border border-gray-700 bg-gray-900 p-3 text-sm"
                  data-testid={`setup-${i}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-gray-200">
                      {setup.type}
                    </span>
                    <span className="text-xs text-gray-500">
                      R:R {setup.rr_estimate?.toFixed(1)} · Conf{" "}
                      {((setup.confidence ?? 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs text-gray-400">
                    <span>Entry: {setup.entry_zone}</span>
                    <span>Stop: {setup.stop}</span>
                    <span>
                      Targets: {setup.targets?.join(", ") ?? "—"}
                    </span>
                  </div>
                  {setup.indicator_dependent && (
                    <span className="mt-1 inline-block rounded bg-amber-900/40 px-2 py-0.5 text-xs text-amber-400">
                      Indicator-dependent
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No Trade Conditions */}
        {verdict.noTradeConditions.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              No-Trade Conditions
            </h4>
            <ul className="list-disc list-inside space-y-1">
              {verdict.noTradeConditions.map((cond, i) => (
                <li key={i} className="text-sm text-red-400" data-testid={`no-trade-${i}`}>
                  {cond}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Arbiter Notes */}
        {verdict.arbiterNotes && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Arbiter Notes
            </h4>
            <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap" data-testid="arbiter-notes">
              {verdict.arbiterNotes}
            </p>
          </div>
        )}

        {/* Risk Override */}
        {verdict.riskOverrideApplied && (
          <div className="rounded border border-amber-800/50 bg-amber-950/20 px-3 py-2">
            <span className="text-xs text-amber-400">
              Risk override was applied to this verdict
            </span>
          </div>
        )}

        {/* Indicator Dependency */}
        {verdict.indicatorDependent && verdict.indicatorDependencyNotes && (
          <div className="rounded border border-blue-800/50 bg-blue-950/20 px-3 py-2">
            <span className="text-xs text-blue-400">
              {verdict.indicatorDependencyNotes}
            </span>
          </div>
        )}

        {/* Ticket Draft — secondary output */}
        {ticketDraft && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Ticket Draft
            </h4>
            <div className="rounded border border-gray-700 bg-gray-900 p-3">
              <pre
                className="text-xs text-gray-400 whitespace-pre-wrap overflow-x-auto"
                data-testid="ticket-draft"
              >
                {JSON.stringify(ticketDraft, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* Usage Accordion — inline below verdict (DESIGN_NOTES §1.7) */}
        <UsageAccordion usage={usage} />
      </div>
    </PanelShell>
  );
}
