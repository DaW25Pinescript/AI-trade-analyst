// ---------------------------------------------------------------------------
// TanStack Query hook for GET /ops/agent-health.
// Snapshot health data — moderate stale time, optional background refresh.
//
// Cache key convention (PR-UI-3): exported named constant, explicit return
// type, stale time documented.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchAgentHealth,
  type AgentHealthSnapshotResponse,
} from "@shared/api/ops";

/** Cache key for agent health query. */
export const AGENT_HEALTH_KEY = ["ops", "agent-health"] as const;

export function useAgentHealth(): UseQueryResult<
  AgentHealthSnapshotResponse,
  Error
> {
  return useQuery<AgentHealthSnapshotResponse, Error>({
    queryKey: AGENT_HEALTH_KEY,
    queryFn: async () => {
      const result = await fetchAgentHealth();
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Health fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    staleTime: 30_000,       // 30s — health snapshots change more frequently
    refetchInterval: 60_000, // background refresh every 60s
  });
}
