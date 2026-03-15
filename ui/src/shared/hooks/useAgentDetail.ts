// ---------------------------------------------------------------------------
// TanStack Query hook for GET /ops/agent-detail/{entity_id}.
// On-demand per entity — enabled only when an entity_id is provided.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchAgentDetail,
  parseOpsErrorEnvelope,
  type AgentDetailResponse,
} from "@shared/api/ops";

/** Cache key factory for agent detail queries. */
export const agentDetailKey = (entityId: string) =>
  ["ops", "agent-detail", entityId] as const;

export function useAgentDetail(
  entityId: string | null,
  enabled = true,
): UseQueryResult<AgentDetailResponse, Error> {
  return useQuery<AgentDetailResponse, Error>({
    queryKey: agentDetailKey(entityId ?? ""),
    queryFn: async () => {
      if (!entityId) throw new Error("No entity_id provided");
      const result = await fetchAgentDetail(entityId);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Detail fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    enabled: enabled && entityId !== null && entityId.length > 0,
    staleTime: 60_000,
  });
}
