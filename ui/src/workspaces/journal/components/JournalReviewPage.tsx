// ---------------------------------------------------------------------------
// JournalReviewPage — main orchestrator with Journal | Review view toggle.
//
// Single /journal workspace route with two internal views.
// Structurally separable: if the review contract deepens later,
// these views can become distinct workspaces without a rewrite.
//
// Read-only workspace — no mutations, no result submission.
// ---------------------------------------------------------------------------

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PanelShell } from "@shared/components/layout";
import { LoadingSkeleton, EmptyState, ErrorState } from "@shared/components/feedback";
import { useJournalDecisions, useReviewRecords } from "../hooks/useJournalData";
import { buildJournalViewModel, buildReviewViewModel } from "../adapters/journalAdapter";
import { JournalHeader, type JournalView } from "./JournalHeader";
import { DecisionList } from "./DecisionList";

export function JournalReviewPage() {
  const [activeView, setActiveView] = useState<JournalView>("journal");
  const navigate = useNavigate();

  const handleRowClick = (instrument: string) => {
    navigate(`/journey/${encodeURIComponent(instrument)}`);
  };

  return (
    <PanelShell>
      {activeView === "journal" ? (
        <JournalViewContent
          activeView={activeView}
          onViewChange={setActiveView}
          onRowClick={handleRowClick}
        />
      ) : (
        <ReviewViewContent
          activeView={activeView}
          onViewChange={setActiveView}
          onRowClick={handleRowClick}
        />
      )}
    </PanelShell>
  );
}

// ---- Journal View (structurally separable) ----

interface ViewContentProps {
  activeView: JournalView;
  onViewChange: (view: JournalView) => void;
  onRowClick: (instrument: string) => void;
}

function JournalViewContent({ activeView, onViewChange, onRowClick }: ViewContentProps) {
  const query = useJournalDecisions();
  const vm = buildJournalViewModel(
    query.data ?? null,
    query.isLoading,
    query.isError,
  );

  return (
    <>
      <JournalHeader
        activeView={activeView}
        onViewChange={onViewChange}
        summary={vm.header}
      />

      {vm.condition === "loading" && <LoadingSkeleton rows={5} />}

      {vm.condition === "error" && (
        <ErrorState
          message="Failed to load decisions"
          detail={
            query.error instanceof Error ? query.error.message : undefined
          }
          onRetry={() => query.refetch()}
        />
      )}

      {vm.condition === "empty" && (
        <EmptyState
          message="No decisions recorded yet"
          description="Freeze a decision in Journey Studio to see it here."
        />
      )}

      {vm.condition === "ready" && (
        <DecisionList
          rows={vm.rows}
          showReviewIndicator={false}
          onRowClick={onRowClick}
        />
      )}
    </>
  );
}

// ---- Review View (structurally separable) ----

function ReviewViewContent({ activeView, onViewChange, onRowClick }: ViewContentProps) {
  const query = useReviewRecords();
  const vm = buildReviewViewModel(
    query.data ?? null,
    query.isLoading,
    query.isError,
  );

  return (
    <>
      <JournalHeader
        activeView={activeView}
        onViewChange={onViewChange}
        summary={vm.header}
      />

      {vm.condition === "loading" && <LoadingSkeleton rows={5} />}

      {vm.condition === "error" && (
        <ErrorState
          message="Failed to load review records"
          detail={
            query.error instanceof Error ? query.error.message : undefined
          }
          onRetry={() => query.refetch()}
        />
      )}

      {vm.condition === "empty" && (
        <EmptyState
          message="No review records yet"
          description="Freeze a decision in Journey Studio to see it here."
        />
      )}

      {vm.condition === "ready" && (
        <DecisionList
          rows={vm.rows}
          showReviewIndicator={true}
          onRowClick={onRowClick}
        />
      )}
    </>
  );
}
