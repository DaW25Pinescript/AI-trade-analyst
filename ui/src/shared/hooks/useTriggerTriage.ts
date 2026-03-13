// ---------------------------------------------------------------------------
// TanStack Query mutation hook for POST /triage.
// On success: invalidates the triage query cache so the board re-fetches.
// On failure: surfaces error for explicit retry — no auto-retry.
// ---------------------------------------------------------------------------

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  triggerTriage,
  type TriggerTriageResponse,
} from "@shared/api/triage";
import { TRIAGE_QUERY_KEY } from "./useWatchlistTriage";

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
      queryClient.invalidateQueries({ queryKey: TRIAGE_QUERY_KEY });
    },
  });
}
