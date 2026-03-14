// ---------------------------------------------------------------------------
// JourneyStudioPage — main Journey Studio workspace component.
//
// Orchestrates bootstrap fetch, staged flow, draft/decision/result mutations,
// and the full freeze lifecycle. Uses existing shared components for state
// handling (loading, error, unavailable, empty).
//
// Layout per UI_WORKSPACES §6.4:
//   - Header: asset + stage + freshness + status
//   - Center: staged trade ideation flow
//   - Right rail: conditional panels from bootstrap
//   - Footer: action bar with Save Draft / Freeze / Save Result
// ---------------------------------------------------------------------------

import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { PanelShell } from "@shared/components/layout";
import {
  LoadingSkeleton,
  EmptyState,
  UnavailableState,
  ErrorState,
} from "@shared/components/feedback";
import { DataStateBadge } from "@shared/components/state";
import { useJourneyBootstrap } from "../hooks/useJourneyBootstrap";
import {
  useJourneyDraft,
  useJourneyDecision,
  useJourneyResult,
} from "../hooks/useJourneyMutations";
import {
  buildJourneyWorkspaceViewModel,
  type JourneyStage,
} from "../adapters/journeyViewModel";
import { JourneyHeader } from "./JourneyHeader";
import { JourneyStageFlow } from "./JourneyStageFlow";
import { JourneyRightRail } from "./JourneyRightRail";
import { JourneyActionBar } from "./JourneyActionBar";

export function JourneyStudioPage() {
  const { asset } = useParams<{ asset: string }>();
  const navigate = useNavigate();

  // ---- Data fetching ----
  const bootstrapQuery = useJourneyBootstrap(asset);

  // ---- Mutations ----
  const draftMutation = useJourneyDraft();
  const decisionMutation = useJourneyDecision();
  const resultMutation = useJourneyResult();

  // ---- Local UI state (stages are UI-only, NOT backend) ----
  const [stage, setStage] = useState<JourneyStage>("explore");
  const [frozenSnapshotId, setFrozenSnapshotId] = useState<string | null>(null);
  const [draftJourneyId, setDraftJourneyId] = useState<string | null>(null);
  const [thesis, setThesis] = useState("");
  const [conviction, setConviction] = useState("");
  const [notes, setNotes] = useState("");
  const [userDecision, setUserDecision] = useState("");

  // ---- Build view model ----
  const vm = buildJourneyWorkspaceViewModel(
    bootstrapQuery.data ?? null,
    bootstrapQuery.isLoading,
    bootstrapQuery.isError,
    stage,
    frozenSnapshotId,
    draftJourneyId,
    { thesis, conviction, notes, userDecision },
  );

  // ---- Handlers ----

  const handleAdvanceToStage = useCallback((nextStage: JourneyStage) => {
    setStage(nextStage);
  }, []);

  const handleSaveDraft = useCallback(() => {
    if (!asset) return;
    draftMutation.mutate(
      {
        journey_id: draftJourneyId ?? undefined,
        instrument: asset,
        stage,
        thesis,
        conviction,
        notes,
      },
      {
        onSuccess: (data) => {
          if (data.journey_id) {
            setDraftJourneyId(data.journey_id);
          }
        },
      },
    );
  }, [asset, draftJourneyId, stage, thesis, conviction, notes, draftMutation]);

  const handleFreeze = useCallback(() => {
    if (!asset) return;
    const snapshotId = `${asset}-${Date.now()}`;
    decisionMutation.mutate(
      {
        snapshot_id: snapshotId,
        instrument: asset,
        decision: userDecision,
        thesis,
        conviction,
        notes,
        bootstrap_summary: {
          arbiter_bias: vm.arbiterBias,
          arbiter_decision: vm.arbiterDecision,
          analyst_verdict: vm.analystVerdict,
        },
      },
      {
        onSuccess: (data) => {
          setFrozenSnapshotId(data.snapshot_id ?? snapshotId);
          setStage("frozen");
        },
      },
    );
  }, [asset, userDecision, thesis, conviction, notes, vm.arbiterBias, vm.arbiterDecision, vm.analystVerdict, decisionMutation]);

  const handleSaveResult = useCallback(() => {
    if (!frozenSnapshotId || !asset) return;
    resultMutation.mutate({
      snapshot_id: frozenSnapshotId,
      instrument: asset,
      outcome: "",
      notes: "",
    }, {
      onSuccess: () => {
        setStage("result");
      },
    });
  }, [frozenSnapshotId, asset, resultMutation]);

  const handleNavigateToTriage = useCallback(() => {
    navigate("/triage");
  }, [navigate]);

  // ---- No asset parameter fallback ----
  if (!asset) {
    return (
      <PanelShell>
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-gray-200">Journey Studio</h2>
        </div>
        <EmptyState
          message="No asset selected"
          description="Select an asset from the Triage Board to begin a journey."
        />
      </PanelShell>
    );
  }

  // ---- State handling: loading / error / unavailable / empty ----
  if (vm.condition === "loading") {
    return (
      <PanelShell>
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-gray-200">Journey Studio</h2>
          <span className="rounded bg-gray-800 px-2.5 py-1 text-sm font-mono font-medium text-blue-300">
            {asset}
          </span>
          <DataStateBadge dataState={null} />
        </div>
        <LoadingSkeleton rows={4} />
      </PanelShell>
    );
  }

  if (vm.condition === "error") {
    return (
      <PanelShell>
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-gray-200">Journey Studio</h2>
          <span className="rounded bg-gray-800 px-2.5 py-1 text-sm font-mono font-medium text-blue-300">
            {asset}
          </span>
        </div>
        <ErrorState
          message="Failed to load journey context"
          detail={
            bootstrapQuery.error instanceof Error
              ? bootstrapQuery.error.message
              : undefined
          }
          onRetry={() => bootstrapQuery.refetch()}
        />
      </PanelShell>
    );
  }

  if (vm.condition === "unavailable") {
    return (
      <PanelShell>
        <JourneyHeader
          instrument={asset}
          dataState={vm.dataState}
          generatedAt={vm.generatedAt}
          stage={vm.stage}
          isFrozen={vm.isFrozen}
          frozenSnapshotId={vm.frozenSnapshotId}
          draftSaved={draftMutation.isSuccess}
        />
        <UnavailableState
          message="Journey context unavailable"
          description="No analysis data exists for this asset. Run triage or analysis first."
        />
        <div>
          <button
            type="button"
            onClick={handleNavigateToTriage}
            className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            Back to Triage
          </button>
        </div>
      </PanelShell>
    );
  }

  if (vm.condition === "empty") {
    return (
      <PanelShell>
        <JourneyHeader
          instrument={asset}
          dataState={vm.dataState}
          generatedAt={vm.generatedAt}
          stage={vm.stage}
          isFrozen={vm.isFrozen}
          frozenSnapshotId={vm.frozenSnapshotId}
          draftSaved={draftMutation.isSuccess}
        />
        <EmptyState
          message="No analysis context available"
          description="Bootstrap returned empty data. Run triage or analysis for this asset first."
        />
        <div>
          <button
            type="button"
            onClick={handleNavigateToTriage}
            className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            Back to Triage
          </button>
        </div>
      </PanelShell>
    );
  }

  // ---- Ready / stale / partial — full workspace ----

  return (
    <PanelShell>
      {/* Stale warning banner */}
      {vm.condition === "stale" && (
        <div className="flex items-center gap-2 rounded border border-amber-800/50 bg-amber-950/20 px-4 py-2">
          <DataStateBadge dataState="stale" />
          <span className="text-xs text-amber-400">
            Bootstrap data may be outdated. Analysis context could be stale.
          </span>
        </div>
      )}

      {/* Partial data banner */}
      {vm.condition === "partial" && (
        <div className="flex items-center gap-2 rounded border border-blue-800/50 bg-blue-950/20 px-4 py-2">
          <DataStateBadge dataState="partial" />
          <span className="text-xs text-blue-400">
            Partial bootstrap data. Some context panels may not be available.
          </span>
        </div>
      )}

      {/* Header */}
      <JourneyHeader
        instrument={vm.instrument}
        dataState={vm.dataState}
        generatedAt={vm.generatedAt}
        stage={vm.stage}
        isFrozen={vm.isFrozen}
        frozenSnapshotId={vm.frozenSnapshotId}
        draftSaved={draftMutation.isSuccess}
      />

      {/* Main content: center + right rail */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Center column — 2/3 width */}
        <div className="lg:col-span-2">
          <JourneyStageFlow
            vm={vm}
            onThesisChange={setThesis}
            onConvictionChange={setConviction}
            onNotesChange={setNotes}
            onUserDecisionChange={setUserDecision}
            onAdvanceToStage={handleAdvanceToStage}
          />
        </div>

        {/* Right rail — 1/3 width */}
        <div className="lg:col-span-1">
          <JourneyRightRail vm={vm} />
        </div>
      </div>

      {/* Action bar */}
      <JourneyActionBar
        canSaveDraft={vm.canSaveDraft}
        canFreeze={vm.canFreeze}
        canSaveResult={vm.canSaveResult}
        isFrozen={vm.isFrozen}
        isSavingDraft={draftMutation.isPending}
        isFreezing={decisionMutation.isPending}
        isSavingResult={resultMutation.isPending}
        freezeError={
          decisionMutation.isError
            ? {
                message: decisionMutation.error.message,
                isConflict: decisionMutation.error.isConflict,
              }
            : null
        }
        draftError={draftMutation.isError ? draftMutation.error.message : null}
        resultError={resultMutation.isError ? resultMutation.error.message : null}
        onSaveDraft={handleSaveDraft}
        onFreeze={handleFreeze}
        onSaveResult={handleSaveResult}
        onNavigateToTriage={handleNavigateToTriage}
      />
    </PanelShell>
  );
}
