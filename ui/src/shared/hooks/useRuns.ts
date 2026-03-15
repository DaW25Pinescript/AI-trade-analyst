// ---------------------------------------------------------------------------
// TanStack Query hook for GET /runs/ (PR-RUN-1).
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchRuns,
  type FetchRunsParams,
  type RunBrowserResponse,
} from "@shared/api/runs";
import { parseOpsErrorEnvelope } from "@shared/api/ops";

/** Cache key factory for run browser queries. */
export const runsKey = (params: FetchRunsParams) =>
  ["runs", "browser", params] as const;

export const RUNS_KEY = "runs";

export function useRuns(
  params: FetchRunsParams = {},
): UseQueryResult<RunBrowserResponse, Error> {
  return useQuery<RunBrowserResponse, Error>({
    queryKey: runsKey(params),
    queryFn: async () => {
      const result = await fetchRuns(params);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Run browser fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    staleTime: 30_000,
  });
}
