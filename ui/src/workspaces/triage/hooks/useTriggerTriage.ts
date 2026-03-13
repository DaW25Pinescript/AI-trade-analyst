// ---------------------------------------------------------------------------
// TanStack Query mutation hook for POST /triage.
// On success: invalidates the triage query cache so the board re-fetches.
// On failure: surfaces error for explicit retry — no auto-retry.
//
// Ownership (PR-UI-3): Moved from shared/hooks/ to workspaces/triage/hooks/
// because POST /triage is triage-specific — no other workspace will call it.
// ---------------------------------------------------------------------------

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  triggerTriage,
  type TriggerTriageResponse,
} from "@shared/api/triage";
import { WATCHLIST_TRIAGE_KEY } from "@shared/hooks";

export interface TriggerTriageError {
  message: string;
  partial?: boolean;
}

export function useTriggerTriage() {
  const queryClient = useQueryClient();

  return useMutation<TriggerTriageResponse, TriggerTriageError, string[] | undefined>({
    mutationFn: async (symbols) => {
      const result = await triggerTriage(symbols);
      if (!result.ok) {
        const detail = result.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail.message ?? `Triage failed (${result.status})`;
        const partial =
          typeof detail === "object" && "partial" in detail
            ? Boolean(detail.partial)
            : undefined;
        throw { message, partial } satisfies TriggerTriageError;
      }
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WATCHLIST_TRIAGE_KEY });
    },
  });
}
