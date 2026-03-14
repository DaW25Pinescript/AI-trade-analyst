// ---------------------------------------------------------------------------
// JourneyStageFlow — the staged ideation flow in the center column.
//
// Stages: explore → draft → frozen → result
// Completed stages collapse to summary lines.
// Active stage is expanded with interactive affordances.
// Upcoming stages are muted.
//
// Per DESIGN_NOTES §1.3: post-freeze, form fields become non-editable text,
// stage flow loses interactive affordances.
// ---------------------------------------------------------------------------

import type { JourneyStage, JourneyWorkspaceViewModel } from "../adapters/journeyViewModel";

export interface JourneyStageFlowProps {
  vm: JourneyWorkspaceViewModel;
  onThesisChange: (value: string) => void;
  onConvictionChange: (value: string) => void;
  onNotesChange: (value: string) => void;
  onUserDecisionChange: (value: string) => void;
  onAdvanceToStage: (stage: JourneyStage) => void;
}

const STAGES: { key: JourneyStage; label: string; number: number }[] = [
  { key: "explore", label: "Explore Context", number: 1 },
  { key: "draft", label: "Draft Thesis", number: 2 },
  { key: "frozen", label: "Freeze Decision", number: 3 },
  { key: "result", label: "Capture Result", number: 4 },
];

const STAGE_ORDER: Record<JourneyStage, number> = {
  explore: 0,
  draft: 1,
  frozen: 2,
  result: 3,
};

const CONVICTION_OPTIONS = ["Low", "Medium", "High", "Very High"];
const DECISION_OPTIONS = ["ENTER_LONG", "ENTER_SHORT", "WAIT_FOR_CONFIRMATION", "NO_TRADE"];

export function JourneyStageFlow({
  vm,
  onThesisChange,
  onConvictionChange,
  onNotesChange,
  onUserDecisionChange,
  onAdvanceToStage,
}: JourneyStageFlowProps) {
  const currentIndex = STAGE_ORDER[vm.stage];

  return (
    <div className="space-y-3" data-testid="stage-flow">
      {STAGES.map((s) => {
        const index = STAGE_ORDER[s.key];
        const isCompleted = index < currentIndex;
        const isActive = index === currentIndex;
        return (
          <div
            key={s.key}
            className={`rounded-lg border transition-colors ${
              isActive
                ? "border-blue-700/50 bg-gray-900/80"
                : isCompleted
                  ? "border-gray-800 bg-gray-900/40"
                  : "border-gray-800/50 bg-gray-950/30"
            }`}
            data-testid={`stage-${s.key}`}
          >
            {/* Stage header */}
            <div className="flex items-center gap-3 px-4 py-3">
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                  isCompleted
                    ? "bg-emerald-800/60 text-emerald-300"
                    : isActive
                      ? "bg-blue-800/60 text-blue-300"
                      : "bg-gray-800 text-gray-600"
                }`}
              >
                {isCompleted ? "✓" : s.number}
              </span>
              <span
                className={`text-sm font-medium ${
                  isActive
                    ? "text-gray-200"
                    : isCompleted
                      ? "text-gray-400"
                      : "text-gray-600"
                }`}
              >
                {s.label}
              </span>
            </div>

            {/* Active stage content */}
            {isActive && (
              <div className="border-t border-gray-800/50 px-4 py-4">
                {s.key === "explore" && (
                  <ExploreContent vm={vm} onAdvance={() => onAdvanceToStage("draft")} />
                )}
                {s.key === "draft" && (
                  <DraftContent
                    vm={vm}
                    onThesisChange={onThesisChange}
                    onConvictionChange={onConvictionChange}
                    onNotesChange={onNotesChange}
                    onUserDecisionChange={onUserDecisionChange}
                  />
                )}
                {s.key === "frozen" && <FrozenContent vm={vm} />}
                {s.key === "result" && <ResultContent />}
              </div>
            )}

            {/* Completed stage summary */}
            {isCompleted && (
              <div className="border-t border-gray-800/50 px-4 py-2">
                {s.key === "explore" && (
                  <p className="text-xs text-gray-500">
                    Context reviewed for {vm.instrument}
                  </p>
                )}
                {s.key === "draft" && (
                  <p className="text-xs text-gray-500">
                    Thesis: {vm.thesis || "—"} · Conviction: {vm.conviction || "—"} · Decision: {vm.userDecision || "—"}
                  </p>
                )}
                {s.key === "frozen" && (
                  <p className="text-xs text-emerald-600">
                    Decision frozen · {vm.frozenSnapshotId?.slice(0, 8) ?? "—"}
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---- Stage content sub-components ----

function ExploreContent({
  vm,
  onAdvance,
}: {
  vm: JourneyWorkspaceViewModel;
  onAdvance: () => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Review the bootstrap context below and in the right panel. When ready,
        proceed to draft your trade thesis.
      </p>

      {/* Analyst summary */}
      {vm.analystVerdict && (
        <div className="rounded border border-gray-800 bg-gray-950/50 p-3">
          <p className="text-xs font-medium text-gray-400 mb-1">Analyst Verdict</p>
          <p className="text-sm text-gray-200">{vm.analystVerdict}</p>
          {vm.analystConfidence && (
            <p className="text-xs text-gray-500 mt-1">
              Confidence: {vm.analystConfidence}
            </p>
          )}
        </div>
      )}

      {/* Reasoning summary */}
      {vm.reasoningSummary && (
        <div className="rounded border border-gray-800 bg-gray-950/50 p-3">
          <p className="text-xs font-medium text-gray-400 mb-1">Reasoning Summary</p>
          <p className="text-sm text-gray-300 whitespace-pre-wrap">
            {vm.reasoningSummary}
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={onAdvance}
        className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-500"
        data-testid="advance-to-draft"
      >
        Begin Draft
      </button>
    </div>
  );
}

function DraftContent({
  vm,
  onThesisChange,
  onConvictionChange,
  onNotesChange,
  onUserDecisionChange,
}: {
  vm: JourneyWorkspaceViewModel;
  onThesisChange: (v: string) => void;
  onConvictionChange: (v: string) => void;
  onNotesChange: (v: string) => void;
  onUserDecisionChange: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Trade Thesis
        </label>
        <textarea
          value={vm.thesis}
          onChange={(e) => onThesisChange(e.target.value)}
          placeholder="What is your thesis for this trade?"
          className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-600 focus:outline-none"
          rows={3}
          data-testid="thesis-input"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Decision
          </label>
          <select
            value={vm.userDecision}
            onChange={(e) => onUserDecisionChange(e.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-200 focus:border-blue-600 focus:outline-none"
            data-testid="decision-select"
          >
            <option value="">Select decision...</option>
            {DECISION_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Conviction
          </label>
          <select
            value={vm.conviction}
            onChange={(e) => onConvictionChange(e.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-200 focus:border-blue-600 focus:outline-none"
            data-testid="conviction-select"
          >
            <option value="">Select conviction...</option>
            {CONVICTION_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Notes
        </label>
        <textarea
          value={vm.notes}
          onChange={(e) => onNotesChange(e.target.value)}
          placeholder="Additional notes, observations, or risk considerations..."
          className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-600 focus:outline-none"
          rows={2}
          data-testid="notes-input"
        />
      </div>
    </div>
  );
}

function FrozenContent({ vm }: { vm: JourneyWorkspaceViewModel }) {
  return (
    <div className="space-y-3">
      <div className="rounded border border-emerald-800/50 bg-emerald-950/20 p-3">
        <p className="text-xs font-medium text-emerald-400 mb-2">Decision Frozen</p>
        <div className="space-y-1 text-sm text-gray-300">
          <p><span className="text-gray-500">Thesis:</span> {vm.thesis || "—"}</p>
          <p><span className="text-gray-500">Decision:</span> {vm.userDecision || "—"}</p>
          <p><span className="text-gray-500">Conviction:</span> {vm.conviction || "—"}</p>
          {vm.notes && (
            <p><span className="text-gray-500">Notes:</span> {vm.notes}</p>
          )}
        </div>
      </div>
      {vm.frozenSnapshotId && (
        <p className="text-xs text-emerald-600">
          Snapshot: {vm.frozenSnapshotId}
        </p>
      )}
    </div>
  );
}

function ResultContent() {
  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-500">
        Record the outcome of this trade decision. This captures what
        actually happened after freezing your decision.
      </p>
    </div>
  );
}
