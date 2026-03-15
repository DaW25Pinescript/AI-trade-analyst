// ---------------------------------------------------------------------------
// RunSelector — lightweight paste field for entering a run_id.
// Per PR_OPS_5_SPEC §9: accept explicit run_id, no run browser.
// ---------------------------------------------------------------------------

import { useState, useCallback } from "react";

export interface RunSelectorProps {
  currentRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

export function RunSelector({ currentRunId, onSelectRun }: RunSelectorProps) {
  const [inputValue, setInputValue] = useState(currentRunId ?? "");

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = inputValue.trim();
      onSelectRun(trimmed.length > 0 ? trimmed : null);
    },
    [inputValue, onSelectRun],
  );

  const handleClear = useCallback(() => {
    setInputValue("");
    onSelectRun(null);
  }, [onSelectRun]);

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-2"
      data-testid="run-selector"
    >
      <label
        htmlFor="run-id-input"
        className="text-xs font-medium uppercase tracking-wider text-gray-500"
      >
        Run ID
      </label>
      <input
        id="run-id-input"
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder="Paste run ID..."
        className="rounded border border-gray-700/50 bg-gray-900/60 px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:border-cyan-600/50 focus:outline-none"
        data-testid="run-id-input"
      />
      <button
        type="submit"
        className="rounded bg-cyan-900/40 px-3 py-1.5 text-xs font-medium text-cyan-300 hover:bg-cyan-900/60 transition-colors"
      >
        Load
      </button>
      {currentRunId && (
        <button
          type="button"
          onClick={handleClear}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Clear
        </button>
      )}
    </form>
  );
}
