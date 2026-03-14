// ---------------------------------------------------------------------------
// AnalysisRunPage — main orchestrator for the Analysis Run workspace.
//
// Three-panel tabbed layout with tab persistence (DESIGN_NOTES §1.6):
//   1. Submission — form inputs, read-only post-submit
//   2. Execution — run lifecycle state with spinner & elapsed time
//   3. Verdict — full verdict, ticket draft, usage accordion
//
// All tabs remain navigable post-run. Submission becomes read-only,
// verdict shows "No verdict — run failed" on failure.
// ---------------------------------------------------------------------------

import { useState, useCallback, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { PanelShell } from "@shared/components/layout";
import { useAnalysisRun } from "../hooks/useAnalysisRun";
import { deriveTabState } from "../adapters/analysisAdapter";
import { AnalysisHeader } from "./AnalysisHeader";
import { SubmissionPanel } from "./SubmissionPanel";
import { ExecutionPanel } from "./ExecutionPanel";
import { VerdictPanel } from "./VerdictPanel";
import { AnalysisActionBar } from "./AnalysisActionBar";
import type { AnalysisSubmission } from "../types";

type Tab = "submission" | "execution" | "verdict";

export function AnalysisRunPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Journey → Analysis escalation: ?asset=SYMBOL
  const assetParam = searchParams.get("asset");
  const escalatedFrom = assetParam ? "journey" : null;

  const [activeTab, setActiveTab] = useState<Tab>("submission");

  const {
    lifecycle,
    analysis,
    usage,
    error,
    elapsedMs,
    submit,
    retry,
    reset,
    lastSubmission,
  } = useAnalysisRun();

  const tabState = useMemo(() => deriveTabState(lifecycle), [lifecycle]);

  // Display instrument: from analysis result, last submission, or escalation param
  const displayInstrument =
    analysis?.runId ? (lastSubmission?.instrument ?? assetParam) :
    lastSubmission?.instrument ?? assetParam;

  const handleSubmit = useCallback(
    (submission: AnalysisSubmission) => {
      setActiveTab("execution");
      submit(submission);
    },
    [submit],
  );

  const handleRetry = useCallback(() => {
    setActiveTab("execution");
    retry();
  }, [retry]);

  const handleReset = useCallback(() => {
    setActiveTab("submission");
    reset();
  }, [reset]);

  const handleReturnToJourney = useCallback(() => {
    if (assetParam) {
      navigate(`/journey/${encodeURIComponent(assetParam)}`);
    }
  }, [assetParam, navigate]);

  // Tab styling
  const tabClass = (tab: Tab, enabled: boolean) =>
    `px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
      activeTab === tab
        ? "border-blue-500 text-blue-300"
        : enabled
          ? "border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-600"
          : "border-transparent text-gray-700 cursor-not-allowed"
    }`;

  return (
    <PanelShell>
      {/* Header */}
      <AnalysisHeader
        instrument={displayInstrument ?? null}
        lifecycle={lifecycle}
        escalatedFrom={escalatedFrom}
        onReturnToJourney={escalatedFrom ? handleReturnToJourney : null}
      />

      {/* Tab bar */}
      <div className="flex border-b border-gray-800" data-testid="tab-bar">
        <button
          type="button"
          onClick={() => setActiveTab("submission")}
          className={tabClass("submission", tabState.submissionEnabled)}
          data-testid="tab-submission"
        >
          Submission
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("execution")}
          className={tabClass("execution", tabState.executionEnabled)}
          data-testid="tab-execution"
        >
          Execution
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("verdict")}
          className={tabClass("verdict", true)}
          data-testid="tab-verdict"
        >
          Verdict
        </button>
      </div>

      {/* Tab content */}
      <div data-testid="tab-content">
        {activeTab === "submission" && (
          <SubmissionPanel
            readOnly={tabState.submissionReadOnly}
            initialInstrument={assetParam ?? ""}
            onSubmit={handleSubmit}
            lastSubmission={lastSubmission}
          />
        )}

        {activeTab === "execution" && (
          <ExecutionPanel
            lifecycle={lifecycle}
            elapsedMs={elapsedMs}
            error={error}
          />
        )}

        {activeTab === "verdict" && (
          <VerdictPanel
            verdict={analysis?.verdict ?? null}
            ticketDraft={analysis?.ticketDraft ?? null}
            usage={usage}
            disabled={!tabState.verdictEnabled}
            disabledReason={tabState.verdictDisabledReason}
          />
        )}
      </div>

      {/* Action bar */}
      <AnalysisActionBar
        runState={lifecycle.state}
        onRetry={handleRetry}
        onReset={handleReset}
      />
    </PanelShell>
  );
}
