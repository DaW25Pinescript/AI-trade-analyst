// ---------------------------------------------------------------------------
// useAnalysisRun — orchestrates the full analysis run lifecycle.
//
// Manages state machine transitions, API calls, and post-completion
// usage fetching. Designed so streaming can be added later by introducing
// a useAnalysisStream hook alongside this one.
// ---------------------------------------------------------------------------

import { useState, useCallback, useRef } from "react";
import { submitAnalysis, fetchRunUsage } from "../api/analysisApi";
import {
  type RunLifecycleState,
  type RunErrorDetail,
  createInitialState,
  toValidating,
  toSubmitting,
  toRunning,
  toCompleted,
  toFailed,
  toIdle,
} from "../state/runLifecycle";
import {
  normalizeAnalysisResponse,
  normalizeError,
  normalizeUsageSummary,
  buildFormData,
  type AnalysisViewModel,
  type UsageViewModel,
  type ErrorViewModel,
} from "../adapters/analysisAdapter";
import type { AnalysisSubmission, UsageSummary } from "../types";

export interface UseAnalysisRunResult {
  lifecycle: RunLifecycleState;
  analysis: AnalysisViewModel | null;
  usage: UsageViewModel;
  usageLoading: boolean;
  error: ErrorViewModel | null;
  elapsedMs: number;
  submit: (submission: AnalysisSubmission) => Promise<void>;
  retry: () => void;
  reset: () => void;
  lastSubmission: AnalysisSubmission | null;
}

export function useAnalysisRun(): UseAnalysisRunResult {
  const [lifecycle, setLifecycle] = useState<RunLifecycleState>(createInitialState);
  const [analysis, setAnalysis] = useState<AnalysisViewModel | null>(null);
  const [usageSummary, setUsageSummary] = useState<UsageSummary | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  const [error, setError] = useState<ErrorViewModel | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [lastSubmission, setLastSubmission] = useState<AnalysisSubmission | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);

  const startTimer = useCallback(() => {
    startTimeRef.current = Date.now();
    setElapsedMs(0);
    timerRef.current = setInterval(() => {
      setElapsedMs(Date.now() - startTimeRef.current);
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setElapsedMs(Date.now() - startTimeRef.current);
  }, []);

  const submit = useCallback(
    async (submission: AnalysisSubmission) => {
      setLastSubmission(submission);
      setError(null);
      setAnalysis(null);
      setUsageSummary(null);

      // validating
      setLifecycle((prev) => toValidating(prev));

      // Build FormData
      const formData = buildFormData(submission);

      // submitting
      setLifecycle((prev) => toSubmitting(prev));
      startTimer();

      // running
      setLifecycle((prev) => toRunning(prev));

      const result = await submitAnalysis(formData);

      stopTimer();

      if (!result.ok) {
        const errVm = normalizeError(result.detail);
        setError(errVm);
        const errDetail: RunErrorDetail = {
          message: errVm.message,
          code: errVm.code ?? undefined,
          request_id: errVm.requestId ?? undefined,
          run_id: errVm.runId ?? undefined,
        };
        setLifecycle((prev) =>
          toFailed(prev, errDetail, {
            run_id: errVm.runId ?? undefined,
            request_id: errVm.requestId ?? undefined,
          }),
        );
        return;
      }

      // completed
      const vm = normalizeAnalysisResponse(result.data);
      setAnalysis(vm);
      setLifecycle((prev) => toCompleted(prev, { run_id: result.data.run_id }));

      // Inline usage from response if available
      if (result.data.usage_summary) {
        setUsageSummary(result.data.usage_summary);
      }

      // Also fetch usage via dedicated endpoint
      if (result.data.run_id) {
        setUsageLoading(true);
        const usageResult = await fetchRunUsage(result.data.run_id);
        setUsageLoading(false);
        if (usageResult.ok) {
          setUsageSummary(usageResult.data.usage_summary);
        }
        // Usage failure is a warning only — does not block verdict
      }
    },
    [startTimer, stopTimer],
  );

  const retry = useCallback(() => {
    if (lastSubmission) {
      // Reset to idle first, then re-submit
      setLifecycle(createInitialState());
      // Defer to avoid state machine violation
      setTimeout(() => {
        submit(lastSubmission);
      }, 0);
    }
  }, [lastSubmission, submit]);

  const reset = useCallback(() => {
    stopTimer();
    setLifecycle((prev) => {
      // Only reset from terminal states
      if (prev.state === "completed" || prev.state === "failed") {
        return toIdle(prev);
      }
      return createInitialState();
    });
    setAnalysis(null);
    setUsageSummary(null);
    setUsageLoading(false);
    setError(null);
    setElapsedMs(0);
    setLastSubmission(null);
  }, [stopTimer]);

  const usageVm = normalizeUsageSummary(usageSummary, usageLoading);

  return {
    lifecycle,
    analysis,
    usage: usageVm,
    usageLoading,
    error,
    elapsedMs,
    submit,
    retry,
    reset,
    lastSubmission,
  };
}
