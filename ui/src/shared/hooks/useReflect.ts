// ---------------------------------------------------------------------------
// TanStack Query hooks for Reflect endpoints (PR-REFLECT-2).
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchPersonaPerformance,
  fetchPatternSummary,
  fetchRunBundle,
  type FetchPersonaPerformanceParams,
  type FetchPatternSummaryParams,
  type PersonaPerformanceResponse,
  type PatternSummaryResponse,
  type RunBundleResponse,
} from "@shared/api/reflect";
import { parseOpsErrorEnvelope } from "@shared/api/ops";

export const PERSONA_PERFORMANCE_KEY = "reflect-persona-performance";
export const PATTERN_SUMMARY_KEY = "reflect-pattern-summary";
export const RUN_BUNDLE_KEY = "reflect-run-bundle";

export const personaPerformanceKey = (params: FetchPersonaPerformanceParams) =>
  [PERSONA_PERFORMANCE_KEY, params] as const;

export const patternSummaryKey = (params: FetchPatternSummaryParams) =>
  [PATTERN_SUMMARY_KEY, params] as const;

export const runBundleKey = (runId: string | null) =>
  [RUN_BUNDLE_KEY, runId] as const;

export function usePersonaPerformance(
  params: FetchPersonaPerformanceParams = {},
): UseQueryResult<PersonaPerformanceResponse, Error> {
  return useQuery<PersonaPerformanceResponse, Error>({
    queryKey: personaPerformanceKey(params),
    queryFn: async () => {
      const result = await fetchPersonaPerformance(params);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Persona performance fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    staleTime: 60_000,
  });
}

export function usePatternSummary(
  params: FetchPatternSummaryParams = {},
): UseQueryResult<PatternSummaryResponse, Error> {
  return useQuery<PatternSummaryResponse, Error>({
    queryKey: patternSummaryKey(params),
    queryFn: async () => {
      const result = await fetchPatternSummary(params);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        throw new Error(
          opsError
            ? opsError.message
            : typeof result.detail === "string"
              ? result.detail
              : `Pattern summary fetch failed (${result.status})`,
        );
      }
      return result.data;
    },
    staleTime: 60_000,
  });
}

export function useRunBundle(
  runId: string | null,
): UseQueryResult<RunBundleResponse, Error> {
  return useQuery<RunBundleResponse, Error>({
    queryKey: runBundleKey(runId),
    queryFn: async () => {
      const result = await fetchRunBundle(runId!);
      if (!result.ok) {
        const opsError = parseOpsErrorEnvelope(result.detail);
        const message = opsError
          ? `[${opsError.error}] ${opsError.message}`
          : typeof result.detail === "string"
            ? result.detail
            : `Run bundle fetch failed (${result.status})`;
        throw new Error(message);
      }
      return result.data;
    },
    staleTime: 30_000,
    enabled: runId != null,
  });
}
