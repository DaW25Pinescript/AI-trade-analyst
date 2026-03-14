// ---------------------------------------------------------------------------
// TanStack Query mutations for journey write endpoints.
//
// POST /journey/draft    — mutable draft save
// POST /journey/decision — immutable freeze (409 on duplicate)
// POST /journey/result   — result linked to decision
//
// Error handling preserves §11.2 envelope: { success: false, error }.
// 409 on decision is surfaced as a distinct conflict error.
// ---------------------------------------------------------------------------

import { useMutation, type UseMutationResult } from "@tanstack/react-query";
import {
  saveJourneyDraft,
  saveJourneyDecision,
  saveJourneyResult,
  type JourneyDraftPayload,
  type JourneyDecisionPayload,
  type JourneyResultPayload,
  type JourneyWriteSuccess,
} from "@shared/api/journey";

// ---- Error types ----

export class JourneyWriteError extends Error {
  readonly status: number;
  readonly isConflict: boolean;

  constructor(message: string, status: number) {
    super(message);
    this.name = "JourneyWriteError";
    this.status = status;
    this.isConflict = status === 409;
  }
}

// ---- Draft mutation ----

export function useJourneyDraft(): UseMutationResult<
  JourneyWriteSuccess,
  JourneyWriteError,
  JourneyDraftPayload
> {
  return useMutation<JourneyWriteSuccess, JourneyWriteError, JourneyDraftPayload>({
    mutationFn: async (payload) => {
      const result = await saveJourneyDraft(payload);
      if (!result.ok) {
        const msg =
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? "Draft save failed";
        throw new JourneyWriteError(msg, result.status);
      }
      return result.data;
    },
  });
}

// ---- Decision mutation (freeze) ----

export function useJourneyDecision(): UseMutationResult<
  JourneyWriteSuccess,
  JourneyWriteError,
  JourneyDecisionPayload
> {
  return useMutation<JourneyWriteSuccess, JourneyWriteError, JourneyDecisionPayload>({
    mutationFn: async (payload) => {
      const result = await saveJourneyDecision(payload);
      if (!result.ok) {
        const msg =
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? "Decision freeze failed";
        throw new JourneyWriteError(msg, result.status);
      }
      return result.data;
    },
  });
}

// ---- Result mutation ----

export function useJourneyResult(): UseMutationResult<
  JourneyWriteSuccess,
  JourneyWriteError,
  JourneyResultPayload
> {
  return useMutation<JourneyWriteSuccess, JourneyWriteError, JourneyResultPayload>({
    mutationFn: async (payload) => {
      const result = await saveJourneyResult(payload);
      if (!result.ok) {
        const msg =
          typeof result.detail === "string"
            ? result.detail
            : result.detail.message ?? "Result save failed";
        throw new JourneyWriteError(msg, result.status);
      }
      return result.data;
    },
  });
}
