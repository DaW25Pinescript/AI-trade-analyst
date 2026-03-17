// ---------------------------------------------------------------------------
// SuggestionPanel — advisory suggestions on Reflect Overview (PR-REFLECT-3).
//
// States per §6.10:
//   - Both loading → hidden
//   - No suggestions → hidden
//   - Suggestions present → amber left-border, ⚠ per item
//   - One error + suggestions → panel + partial-results warning
//   - Both error → hidden (tables show their own ErrorState)
//   - All malformed → hidden
// ---------------------------------------------------------------------------

import { useMemo } from "react";
import { usePersonaPerformance, usePatternSummary } from "@shared/hooks/useReflect";
import {
  normalizeSuggestions,
  mergeSuggestions,
  type SuggestionViewModel,
} from "../adapters/reflectAdapter";

export function SuggestionPanel() {
  const personaQuery = usePersonaPerformance();
  const patternQuery = usePatternSummary();

  const bothLoading = personaQuery.isLoading && patternQuery.isLoading;
  const personaError = personaQuery.isError;
  const patternError = patternQuery.isError;
  const bothError = personaError && patternError;

  const personaSuggestions = useMemo(
    () => normalizeSuggestions(personaQuery.data?.suggestions),
    [personaQuery.data?.suggestions],
  );

  const patternSuggestions = useMemo(
    () => normalizeSuggestions(patternQuery.data?.suggestions),
    [patternQuery.data?.suggestions],
  );

  const merged = useMemo(
    () => mergeSuggestions(personaSuggestions, patternSuggestions),
    [personaSuggestions, patternSuggestions],
  );

  const hasPartialError =
    (personaError && !patternError) || (!personaError && patternError);

  // Hidden states
  if (bothLoading) return null;
  if (bothError) return null;
  if (merged.length === 0 && !hasPartialError) return null;
  if (merged.length === 0 && hasPartialError) return null;

  return (
    <div
      className="rounded border-l-4 border-amber-500 bg-amber-950/20 px-4 py-3"
      data-testid="suggestion-panel"
    >
      {hasPartialError && (
        <p
          className="mb-2 text-xs text-amber-400"
          data-testid="suggestion-partial-warning"
        >
          Some suggestion sources unavailable — showing partial results
        </p>
      )}

      <ul className="space-y-2">
        {merged.map((s: SuggestionViewModel, i: number) => (
          <li
            key={`${s.ruleId}-${s.target}-${i}`}
            className="text-sm text-amber-200"
            title={s.evidenceTooltip}
            data-testid="suggestion-item"
          >
            <span className="mr-1">⚠</span>
            {s.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
