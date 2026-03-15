// ---------------------------------------------------------------------------
// TanStack Query hook for GET /runs/{run_id}/agent-trace.
// On-demand per run — enabled only when a run_id is provided.
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchAgentTrace,
  parseOpsErrorEnvelope,
  type AgentTraceResponse,
} from "@shared/api/ops";

/** Cache key factory for agent trace queries. */
export const agentTraceKey = (runId: string) =>
  ["ops", "agent-trace", runId] as const;

export function useAgentTrace(
  runId: string | null,
  enabled = true,
): UseQueryResult<AgentTraceResponse, Error> {
  return useQuery<AgentTraceResponse, Error>({
    queryKey: agentTraceKey(runId ?? ""),
    queryFn: async () => {
      if (!runId) throw new Error("No run_id provided");
      const result = await fetchAgentTrace(runId);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Trace fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    enabled: enabled && runId !== null && runId.length > 0,
    staleTime: 60_000, // trace data is immutable per run
  });
}
