// ---------------------------------------------------------------------------
// Run Browser endpoint client — shapes from PR_RUN_1_SPEC.md §6.1.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";
import type { ResponseMeta } from "./ops";

// ---- Run Browser types ----

export type RunBrowserStatus = "completed" | "partial" | "failed";

export type RunBrowserItem = {
  run_id: string;
  timestamp: string;
  instrument: string | null;
  session: string | null;
  final_decision: string | null;
  run_status: RunBrowserStatus;
  trace_available: boolean;
};

export type RunBrowserResponse = ResponseMeta & {
  items: RunBrowserItem[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
};

// ---- Endpoint function ----

export type FetchRunsParams = {
  page?: number;
  pageSize?: number;
  instrument?: string | null;
  session?: string | null;
};

/** Fetch paginated, filterable run browser index. */
export function fetchRuns(
  params: FetchRunsParams = {},
): Promise<ApiResult<RunBrowserResponse>> {
  const searchParams = new URLSearchParams();

  if (params.page != null) searchParams.set("page", String(params.page));
  if (params.pageSize != null)
    searchParams.set("page_size", String(params.pageSize));
  if (params.instrument) searchParams.set("instrument", params.instrument);
  if (params.session) searchParams.set("session", params.session);

  const query = searchParams.toString();
  const path = query ? `/runs/?${query}` : "/runs/";

  return apiFetch<RunBrowserResponse>(path);
}
