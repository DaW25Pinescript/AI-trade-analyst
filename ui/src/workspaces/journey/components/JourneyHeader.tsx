// ---------------------------------------------------------------------------
// JourneyHeader — workspace header with asset identity, stage indicator,
// bootstrap freshness, and draft/frozen status.
//
// Per DESIGN_NOTES §1.5: header shows brief "loading" state on the bootstrap
// freshness badge during fetch. No full-page interstitial.
// ---------------------------------------------------------------------------

import { DataStateBadge } from "@shared/components/state";
import type { JourneyStage } from "../adapters/journeyViewModel";

export interface JourneyHeaderProps {
  instrument: string;
  dataState: string | null;
  generatedAt: string | null;
  stage: JourneyStage;
  isFrozen: boolean;
  frozenSnapshotId: string | null;
  draftSaved: boolean;
}

const STAGE_LABELS: Record<JourneyStage, string> = {
  explore: "Exploring",
  draft: "Drafting",
  frozen: "Frozen",
  result: "Result Captured",
};

export function JourneyHeader({
  instrument,
  dataState,
  generatedAt,
  stage,
  isFrozen,
  frozenSnapshotId,
  draftSaved,
}: JourneyHeaderProps) {
  const stageLabel = STAGE_LABELS[stage];

  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-semibold text-gray-200">
          Journey Studio
        </h2>
        <span className="rounded bg-gray-800 px-2.5 py-1 text-sm font-mono font-medium text-blue-300">
          {instrument || "—"}
        </span>
        <DataStateBadge dataState={dataState} />
      </div>

      <div className="flex items-center gap-3">
        {/* Stage pill */}
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold tracking-wide ${
            isFrozen
              ? "bg-emerald-900/60 text-emerald-300 border border-emerald-700/50"
              : stage === "draft"
                ? "bg-blue-900/60 text-blue-300 border border-blue-700/50"
                : "bg-gray-800 text-gray-400 border border-gray-700"
          }`}
          data-testid="stage-pill"
        >
          {stageLabel}
        </span>

        {/* Draft/frozen status */}
        {isFrozen && frozenSnapshotId ? (
          <span className="text-xs text-emerald-500" data-testid="frozen-status">
            Frozen · {frozenSnapshotId.slice(0, 8)}
          </span>
        ) : draftSaved ? (
          <span className="text-xs text-gray-500" data-testid="draft-status">
            Draft saved
          </span>
        ) : (
          <span className="text-xs text-gray-600" data-testid="unsaved-status">
            Unsaved
          </span>
        )}

        {/* Generated timestamp */}
        {generatedAt && (
          <span className="text-xs text-gray-600" title={generatedAt}>
            {new Date(generatedAt).toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}
