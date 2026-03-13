// ---------------------------------------------------------------------------
// View-model adapter for triage data.
//
// Thin mapping between raw API responses and view rendering so backend
// quirks do not leak into JSX. Per DESIGN_NOTES §1.1, per-row staleness
// is derived from verdict_at only — no invented per-row data_state.
// ---------------------------------------------------------------------------

import type { TriageItem, WatchlistTriageResponse } from "@shared/api/triage";

// ---- Board-level view model ----

/** The board-level data freshness state as reported by the backend. */
export type DataState = "live" | "stale" | "unavailable" | string;

/**
 * Resolved board condition — the UI state the board should render.
 * This collapses loading/fetch/data_state into a single discriminator.
 */
export type BoardCondition =
  | "loading"
  | "ready"
  | "empty"
  | "stale"
  | "unavailable"
  | "demo-fallback"
  | "error";

export interface TriageBoardViewModel {
  condition: BoardCondition;
  dataState: DataState | null;
  generatedAt: string | null;
  items: TriageRowViewModel[];
}

// ---- Per-row view model ----

export type RowFreshness = "fresh" | "stale";

export interface TriageRowViewModel {
  symbol: string;
  triageStatus: string;
  bias: string;
  confidence: number;
  whyInteresting: string;
  rationale: string;
  verdictAt: string | null;
  freshness: RowFreshness;
}

// ---- Staleness threshold ----

/** Rows with verdict_at older than this are considered stale (in milliseconds). */
const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 24 hours

// ---- Mapping functions ----

/**
 * Derive per-row freshness from verdict_at.
 * Per DESIGN_NOTES §1.1: fresh = no badge, stale = stale badge.
 */
export function deriveRowFreshness(verdictAt: string | null | undefined): RowFreshness {
  if (!verdictAt) return "stale";
  const age = Date.now() - new Date(verdictAt).getTime();
  if (Number.isNaN(age)) return "stale";
  return age > STALE_THRESHOLD_MS ? "stale" : "fresh";
}

/** Map a raw TriageItem to a row view model. */
export function mapTriageItem(item: TriageItem): TriageRowViewModel {
  return {
    symbol: item.symbol,
    triageStatus: item.triage_status ?? "unknown",
    bias: item.bias ?? "—",
    confidence: item.confidence ?? 0,
    whyInteresting: item.why_interesting ?? "",
    rationale: item.rationale ?? "",
    verdictAt: item.verdict_at ?? null,
    freshness: deriveRowFreshness(item.verdict_at),
  };
}

/**
 * Resolve the board condition from the API response.
 * This determines which of the 7 UI states to render.
 */
export function resolveBoardCondition(
  data: WatchlistTriageResponse | null,
  isLoading: boolean,
  isError: boolean,
): BoardCondition {
  if (isLoading) return "loading";
  if (isError || !data) return "error";

  const ds = data.data_state?.toLowerCase();

  if (ds === "unavailable") return "unavailable";

  // demo-fallback: if data_state indicates demo/fallback data
  if (ds === "demo-fallback" || ds === "demo" || ds === "fallback") return "demo-fallback";

  if (data.items.length === 0) return "empty";

  if (ds === "stale") return "stale";

  return "ready";
}

/** Build the full board view model from an API response. */
export function buildTriageBoardViewModel(
  data: WatchlistTriageResponse | null,
  isLoading: boolean,
  isError: boolean,
): TriageBoardViewModel {
  const condition = resolveBoardCondition(data, isLoading, isError);

  return {
    condition,
    dataState: data?.data_state ?? null,
    generatedAt: data?.generated_at ?? null,
    items: data?.items?.map(mapTriageItem) ?? [],
  };
}
