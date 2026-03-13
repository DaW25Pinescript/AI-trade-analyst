// ---------------------------------------------------------------------------
// Triage Board tests — PR-UI-2.
//
// Covers: loading, ready, empty, unavailable, error, demo-fallback, stale,
//         mutation flow, row click navigation, and view-model adapter.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TriageBoardPage } from "../src/workspaces/triage/routes/TriageBoardPage";
import {
  buildTriageBoardViewModel,
  deriveRowFreshness,
  mapTriageItem,
  resolveBoardCondition,
} from "../src/workspaces/triage/adapters/triageViewModel";
import type { WatchlistTriageResponse } from "../src/shared/api/triage";

// ---- Mock API modules ----

vi.mock("../src/shared/api/triage", () => ({
  fetchWatchlistTriage: vi.fn(),
  triggerTriage: vi.fn(),
}));

vi.mock("../src/shared/api/feeder", () => ({
  fetchFeederHealth: vi.fn(),
}));

import { fetchWatchlistTriage, triggerTriage } from "../src/shared/api/triage";
import { fetchFeederHealth } from "../src/shared/api/feeder";

const mockFetchTriage = vi.mocked(fetchWatchlistTriage);
const mockTriggerTriage = vi.mocked(triggerTriage);
const mockFetchFeederHealth = vi.mocked(fetchFeederHealth);

// ---- Test helpers ----

function renderTriageBoard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const router = createMemoryRouter(
    [
      { path: "/triage", element: <TriageBoardPage /> },
      { path: "/journey/:asset", element: <div data-testid="journey-page">Journey</div> },
    ],
    { initialEntries: ["/triage"] },
  );

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const LIVE_RESPONSE: WatchlistTriageResponse = {
  data_state: "live",
  generated_at: "2026-03-13T10:00:00Z",
  items: [
    {
      symbol: "EURUSD",
      triage_status: "active",
      bias: "bullish",
      confidence: 78,
      why_interesting: "Strong trend continuation",
      verdict_at: new Date().toISOString(),
    },
    {
      symbol: "XAUUSD",
      triage_status: "active",
      bias: "bearish",
      confidence: 65,
      why_interesting: "Reversal pattern forming",
      verdict_at: new Date().toISOString(),
    },
  ],
};

const FEEDER_HEALTH_RESPONSE = {
  status: "ok",
  ingested_at: new Date().toISOString(),
  age_seconds: 120,
  stale: false,
  source_health: {},
};

// ---- Tests ----

beforeEach(() => {
  vi.resetAllMocks();
  mockFetchFeederHealth.mockResolvedValue({
    ok: true,
    status: 200,
    data: FEEDER_HEALTH_RESPONSE,
  });
});

describe("TriageBoardPage", () => {
  it("shows loading skeleton during initial fetch", () => {
    // Never resolves — stays in loading state
    mockFetchTriage.mockReturnValue(new Promise(() => {}));
    renderTriageBoard();
    expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument();
  });

  it("renders ready state with triage items", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: LIVE_RESPONSE,
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("EURUSD")).toBeInTheDocument();
    });
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
    expect(screen.getByText("Strong trend continuation")).toBeInTheDocument();
    expect(screen.getByText("Reversal pattern forming")).toBeInTheDocument();
    expect(screen.getByText("Triage Board")).toBeInTheDocument();
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });

  it("renders empty state when items array is empty", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: { data_state: "live", generated_at: "2026-03-13T10:00:00Z", items: [] },
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("No triage items")).toBeInTheDocument();
    });
  });

  it("renders unavailable state when data_state is unavailable", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: { data_state: "unavailable", items: [] },
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("Triage data unavailable")).toBeInTheDocument();
    });
  });

  it("renders error state when fetch fails", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Internal server error",
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("Failed to load triage data")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders stale warning when data_state is stale", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: {
        data_state: "stale",
        generated_at: "2026-03-12T10:00:00Z",
        items: [
          {
            symbol: "EURUSD",
            bias: "bullish",
            confidence: 50,
            verdict_at: new Date().toISOString(),
          },
        ],
      },
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText(/may be outdated/)).toBeInTheDocument();
    });
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
  });

  it("renders demo-fallback banner when data_state is demo-fallback", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: {
        data_state: "demo-fallback",
        items: [{ symbol: "DEMO1", bias: "neutral", confidence: 50 }],
      },
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText(/demo\/fallback data/)).toBeInTheDocument();
    });
  });

  it("navigates to journey on row click", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: LIVE_RESPONSE,
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("EURUSD")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("EURUSD"));

    await waitFor(() => {
      expect(screen.getByTestId("journey-page")).toBeInTheDocument();
    });
  });

  it("Run Triage triggers mutation and refreshes", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: LIVE_RESPONSE,
    });
    mockTriggerTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: { status: "completed", artifacts_written: 2, symbols_processed: 2 },
    });

    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("Run Triage")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Run Triage"));

    await waitFor(() => {
      expect(mockTriggerTriage).toHaveBeenCalled();
    });
  });

  it("shows error when triage mutation fails", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: LIVE_RESPONSE,
    });
    mockTriggerTriage.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Triage engine unavailable",
    });

    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("Run Triage")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Run Triage"));

    await waitFor(() => {
      expect(screen.getByText(/Triage failed/)).toBeInTheDocument();
    });
  });

  it("always shows trust strip with data_state badge", async () => {
    mockFetchTriage.mockResolvedValue({
      ok: true,
      status: 200,
      data: LIVE_RESPONSE,
    });
    renderTriageBoard();

    await waitFor(() => {
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });
    // Feeder chip should also be present
    expect(screen.getByText(/Feeder/)).toBeInTheDocument();
  });
});

// ---- View-model adapter unit tests ----

describe("triageViewModel", () => {
  describe("deriveRowFreshness", () => {
    it("returns stale for null verdict_at", () => {
      expect(deriveRowFreshness(null)).toBe("stale");
    });

    it("returns stale for undefined verdict_at", () => {
      expect(deriveRowFreshness(undefined)).toBe("stale");
    });

    it("returns fresh for recent verdict_at", () => {
      expect(deriveRowFreshness(new Date().toISOString())).toBe("fresh");
    });

    it("returns stale for old verdict_at", () => {
      const old = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();
      expect(deriveRowFreshness(old)).toBe("stale");
    });
  });

  describe("mapTriageItem", () => {
    it("maps all fields and defaults missing optional fields", () => {
      const row = mapTriageItem({ symbol: "GBPUSD" });
      expect(row.symbol).toBe("GBPUSD");
      expect(row.bias).toBe("—");
      expect(row.confidence).toBe(0);
      expect(row.whyInteresting).toBe("");
      expect(row.verdictAt).toBeNull();
    });
  });

  describe("resolveBoardCondition", () => {
    it("returns loading when isLoading", () => {
      expect(resolveBoardCondition(null, true, false)).toBe("loading");
    });

    it("returns error when isError", () => {
      expect(resolveBoardCondition(null, false, true)).toBe("error");
    });

    it("returns unavailable for data_state unavailable", () => {
      expect(
        resolveBoardCondition(
          { data_state: "unavailable", items: [] },
          false,
          false,
        ),
      ).toBe("unavailable");
    });

    it("returns empty for live with no items", () => {
      expect(
        resolveBoardCondition(
          { data_state: "live", items: [] },
          false,
          false,
        ),
      ).toBe("empty");
    });

    it("returns stale for stale data_state with items", () => {
      expect(
        resolveBoardCondition(
          { data_state: "stale", items: [{ symbol: "X" }] },
          false,
          false,
        ),
      ).toBe("stale");
    });

    it("returns ready for live data_state with items", () => {
      expect(
        resolveBoardCondition(
          { data_state: "live", items: [{ symbol: "X" }] },
          false,
          false,
        ),
      ).toBe("ready");
    });

    it("returns demo-fallback for demo data_state", () => {
      expect(
        resolveBoardCondition(
          { data_state: "demo-fallback", items: [{ symbol: "X" }] },
          false,
          false,
        ),
      ).toBe("demo-fallback");
    });
  });

  describe("buildTriageBoardViewModel", () => {
    it("builds complete view model from API response", () => {
      const vm = buildTriageBoardViewModel(LIVE_RESPONSE, false, false);
      expect(vm.condition).toBe("ready");
      expect(vm.dataState).toBe("live");
      expect(vm.items).toHaveLength(2);
      expect(vm.items[0].symbol).toBe("EURUSD");
      expect(vm.items[0].bias).toBe("bullish");
    });
  });
});
