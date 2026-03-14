// ---------------------------------------------------------------------------
// Analysis API layer — transport for POST /analyse and GET /runs/{run_id}/usage
//
// POST /analyse uses multipart/form-data (UI_CONTRACT §5.2, §10.1).
// This is workspace-local because the shared apiFetch assumes JSON Content-Type
// and would set incorrect headers for FormData. A dedicated multipart submit
// function avoids contaminating the shared layer.
//
// GET /runs/{run_id}/usage uses the shared apiFetch (JSON transport).
//
// Error handling: /analyse returns mixed detail patterns — string or structured
// object (UI_CONTRACT §11.1). Both shapes are handled without crash.
//
// Timeout: No auto-retry on timeout (UI_CONTRACT §12.2). Preserves run_id /
// request_id from failure payloads.
// ---------------------------------------------------------------------------

import type { ApiErrorDetail } from "@shared/api/client";
import type { AnalysisResponse, RunUsageResponse } from "../types";

/** Result type mirroring the shared ApiResult pattern. */
export type AnalysisApiResult<T> =
  | { ok: true; data: T; status: number }
  | { ok: false; status: number; detail: string | ApiErrorDetail };

/**
 * Submit analysis as multipart/form-data.
 *
 * Does NOT set Content-Type header — the browser sets the correct
 * multipart boundary automatically when body is FormData.
 *
 * Backend fields discovered from FastAPI route inspection:
 *   Required: instrument, session, timeframes, account_balance,
 *             min_rr, max_risk_per_trade, max_daily_risk
 *   Files:    chart_h4, chart_h1, chart_m15, chart_m5, chart_m15_overlay
 *   Optional: market_regime, news_risk, no_trade_windows, open_positions,
 *             lens_*, source_ticket_id, enable_deliberation, triage_mode,
 *             smoke_mode, overlay_*
 */
export async function submitAnalysis(
  formData: FormData,
): Promise<AnalysisApiResult<AnalysisResponse>> {
  let response: Response;

  try {
    response = await fetch("/analyse", {
      method: "POST",
      body: formData,
      // No Content-Type header — browser sets multipart boundary automatically
    });
  } catch (networkError: unknown) {
    const message =
      networkError instanceof Error
        ? networkError.message
        : "Network request failed";
    return { ok: false, status: 0, detail: message };
  }

  if (!response.ok) {
    return parseErrorResponse(response);
  }

  const data = (await response.json()) as AnalysisResponse;
  return { ok: true, data, status: response.status };
}

/**
 * Fetch usage summary for a completed run.
 * Uses JSON transport (standard GET).
 */
export async function fetchRunUsage(
  runId: string,
): Promise<AnalysisApiResult<RunUsageResponse>> {
  let response: Response;

  try {
    response = await fetch(`/runs/${encodeURIComponent(runId)}/usage`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
  } catch (networkError: unknown) {
    const message =
      networkError instanceof Error
        ? networkError.message
        : "Network request failed";
    return { ok: false, status: 0, detail: message };
  }

  if (!response.ok) {
    return parseErrorResponse(response);
  }

  const data = (await response.json()) as RunUsageResponse;
  return { ok: true, data, status: response.status };
}

/**
 * Parse error response handling mixed detail patterns (UI_CONTRACT §11.1).
 * Preserves run_id, request_id, code from structured error objects.
 */
async function parseErrorResponse<T>(
  response: Response,
): Promise<AnalysisApiResult<T>> {
  let detail: string | ApiErrorDetail;

  try {
    const body: unknown = await response.json();

    if (
      body !== null &&
      typeof body === "object" &&
      "detail" in (body as Record<string, unknown>)
    ) {
      const raw = (body as Record<string, unknown>).detail;

      if (typeof raw === "string") {
        detail = raw;
      } else if (raw !== null && typeof raw === "object") {
        detail = raw as ApiErrorDetail;
      } else {
        detail = String(raw);
      }
    } else {
      // Non-standard error body — preserve as structured detail
      detail = body as ApiErrorDetail;
    }
  } catch {
    detail = response.statusText || "Unknown error";
  }

  return { ok: false, status: response.status, detail };
}
