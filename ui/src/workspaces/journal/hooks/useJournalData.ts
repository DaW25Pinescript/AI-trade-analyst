// ---------------------------------------------------------------------------
// TanStack Query hooks for Journal & Review data — PR-UI-6.
//
// Cache key convention: exported named constants, explicit return types.
// Error discrimination: if (!result.ok) throw Error(...)
// Both hooks follow the graceful empty pattern (UI_CONTRACT §11.4).
// ---------------------------------------------------------------------------

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchDecisions,
  fetchReviewRecords,
  type JournalDecisionsResponse,
  type ReviewRecordsResponse,
} from "../api/journalApi";

/** Cache key for journal decisions query. */
export const JOURNAL_DECISIONS_KEY = ["journal", "decisions"] as const;

/** Cache key for review records query. */
export const REVIEW_RECORDS_KEY = ["review", "records"] as const;

/** Fetch frozen decision summaries from GET /journal/decisions. */
export function useJournalDecisions(): UseQueryResult<JournalDecisionsResponse, Error> {
  return useQuery<JournalDecisionsResponse, Error>({
    queryKey: JOURNAL_DECISIONS_KEY,
    queryFn: async () => {
      const result = await fetchDecisions();
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Request failed (${result.status})`,
        );
      }
      return result.data;
    },
  });
}

/** Fetch decisions with result linkage from GET /review/records. */
export function useReviewRecords(): UseQueryResult<ReviewRecordsResponse, Error> {
  return useQuery<ReviewRecordsResponse, Error>({
    queryKey: REVIEW_RECORDS_KEY,
    queryFn: async () => {
      const result = await fetchReviewRecords();
      if (!result.ok) {
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? `Request failed (${result.status})`,
        );
      }
      return result.data;
    },
  });
}
