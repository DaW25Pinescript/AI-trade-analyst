// ---------------------------------------------------------------------------
// JourneyActionBar — footer action rail with Save Draft, Freeze Decision,
// Save Result, and navigation actions.
//
// Per DESIGN_NOTES §1.3-1.4:
//   - Save Draft: lightweight secondary (disappears post-freeze)
//   - Freeze Decision: primary action, visually prominent
//   - Save Result: disabled until freeze succeeds
//   - 409 conflict: explicit conflict message, not generic error
// ---------------------------------------------------------------------------

export interface JourneyActionBarProps {
  canSaveDraft: boolean;
  canFreeze: boolean;
  canSaveResult: boolean;
  isFrozen: boolean;
  isSavingDraft: boolean;
  isFreezing: boolean;
  isSavingResult: boolean;
  freezeError: { message: string; isConflict: boolean } | null;
  draftError: string | null;
  resultError: string | null;
  onSaveDraft: () => void;
  onFreeze: () => void;
  onSaveResult: () => void;
  onNavigateToTriage: () => void;
}

export function JourneyActionBar({
  canSaveDraft,
  canFreeze,
  canSaveResult,
  isFrozen,
  isSavingDraft,
  isFreezing,
  isSavingResult,
  freezeError,
  draftError,
  resultError,
  onSaveDraft,
  onFreeze,
  onSaveResult,
  onNavigateToTriage,
}: JourneyActionBarProps) {
  return (
    <div className="space-y-2" data-testid="action-bar">
      {/* Error feedback */}
      {freezeError && (
        <div
          className={`rounded border px-3 py-2 text-xs ${
            freezeError.isConflict
              ? "border-amber-800/50 bg-amber-950/20 text-amber-400"
              : "border-red-800/50 bg-red-950/20 text-red-400"
          }`}
          data-testid="freeze-error"
        >
          {freezeError.isConflict
            ? `Conflict: This decision was already frozen. ${freezeError.message}`
            : `Freeze failed: ${freezeError.message}`}
        </div>
      )}
      {draftError && (
        <div
          className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2 text-xs text-red-400"
          data-testid="draft-error"
        >
          Draft save failed: {draftError}
        </div>
      )}
      {resultError && (
        <div
          className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2 text-xs text-red-400"
          data-testid="result-error"
        >
          Result save failed: {resultError}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onNavigateToTriage}
          className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
        >
          Back to Triage
        </button>

        <div className="flex items-center gap-3">
          {/* Save Draft — disappears post-freeze */}
          {!isFrozen && (
            <button
              type="button"
              onClick={onSaveDraft}
              disabled={!canSaveDraft || isSavingDraft}
              className="rounded border border-gray-700 px-4 py-1.5 text-sm font-medium text-gray-400 transition-colors hover:border-gray-600 hover:text-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="save-draft-btn"
            >
              {isSavingDraft ? "Saving..." : "Save Draft"}
            </button>
          )}

          {/* Freeze Decision — primary action */}
          {!isFrozen && (
            <button
              type="button"
              onClick={onFreeze}
              disabled={!canFreeze || isFreezing}
              className="rounded bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="freeze-btn"
              title={
                !canFreeze
                  ? "Complete draft stage before freezing"
                  : undefined
              }
            >
              {isFreezing ? "Freezing..." : "Freeze Decision"}
            </button>
          )}

          {/* Save Result — gated until freeze succeeds */}
          <button
            type="button"
            onClick={onSaveResult}
            disabled={!canSaveResult || isSavingResult}
            className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="save-result-btn"
            title={
              !canSaveResult
                ? "Only available after freeze succeeds"
                : undefined
            }
          >
            {isSavingResult ? "Saving..." : "Save Result"}
          </button>
        </div>
      </div>
    </div>
  );
}
