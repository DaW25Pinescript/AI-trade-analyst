// ---------------------------------------------------------------------------
// Generic typed fetch wrapper for the AI Trade Analyst backend.
//
// Error handling preserves the mixed `detail` patterns defined in
// UI_CONTRACT.md §11:
//   - detail may be a string
//   - detail may be an object (with optional message, code, request_id, run_id)
//   - responses may use envelope-style errors ({ success: false, error })
//   - valid responses may signal unavailability via data_state
//
// This wrapper intentionally does NOT normalise errors to a single string.
// ---------------------------------------------------------------------------

/** Successful API response envelope. */
export interface ApiResponse<T> {
  data: T;
  status: number;
  ok: true;
}

/**
 * Structured error detail object.
 * Fields are optional — the backend may include any subset.
 */
export interface ApiErrorDetail {
  message?: string;
  code?: string;
  request_id?: string;
  run_id?: string;
  [key: string]: unknown;
}

/**
 * API error — `detail` preserves the shape returned by the backend.
 * It may be a plain string OR a structured object.
 */
export interface ApiError {
  status: number;
  detail: string | ApiErrorDetail;
  ok: false;
}

export type ApiResult<T> = ApiResponse<T> | ApiError;

/**
 * Low-level typed fetch wrapper.
 *
 * Returns an {@link ApiResult} discriminated on `ok`.  Callers should
 * narrow via `if (!result.ok)` to access error details without losing
 * type information.
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<ApiResult<T>> {
  let response: Response;

  try {
    response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch (networkError: unknown) {
    // Network-level failure (DNS, connection refused, etc.)
    const message =
      networkError instanceof Error
        ? networkError.message
        : "Network request failed";

    return {
      status: 0,
      detail: message,
      ok: false,
    };
  }

  if (!response.ok) {
    let detail: string | ApiErrorDetail;

    try {
      const body: unknown = await response.json();

      // FastAPI returns { detail: ... } on error responses.
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
        // Non-standard error body — preserve as structured detail.
        detail = body as ApiErrorDetail;
      }
    } catch {
      detail = response.statusText || "Unknown error";
    }

    return { status: response.status, detail, ok: false };
  }

  const data = (await response.json()) as T;

  return { data, status: response.status, ok: true };
}
