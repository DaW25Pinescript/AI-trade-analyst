// ---------------------------------------------------------------------------
// TanStack Query hook for GET /ops/agent-roster.
// Static architecture data — long stale time, no background refresh.
//
// Cache key convention (PR-UI-3): exported named constant, explicit return
// type, stale time documented.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchAgentRoster,
  type AgentRosterResponse,
} from "@shared/api/ops";

/** Cache key for agent roster query. */
export const AGENT_ROSTER_KEY = ["ops", "agent-roster"] as const;

export function useAgentRoster(): UseQueryResult<AgentRosterResponse, Error> {
  return useQuery<AgentRosterResponse, Error>({
    queryKey: AGENT_ROSTER_KEY,
    queryFn: async () => {
      const result = await fetchAgentRoster();
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Roster fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    staleTime: 5 * 60_000, // 5 min — roster is config-derived, rarely changes
  });
}
