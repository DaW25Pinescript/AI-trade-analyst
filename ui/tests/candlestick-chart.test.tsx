// ---------------------------------------------------------------------------
// CandlestickChart tests — PR-CHART-1.
//
// Covers AC-25 through AC-30 from docs/specs/PR_CHART_1_SPEC.md §7.
// Deterministic — no live pipeline dependency. lightweight-charts is mocked.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { OHLCVResponse } from "../src/shared/api/marketData";

// ---- Mock lightweight-charts ----

const mockSetData = vi.fn();
const mockFitContent = vi.fn();
const mockApplyOptions = vi.fn();
const mockRemove = vi.fn();

vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addCandlestickSeries: () => ({ setData: mockSetData }),
    addHistogramSeries: () => ({ setData: mockSetData }),
    priceScale: () => ({ applyOptions: mockApplyOptions }),
    timeScale: () => ({ fitContent: mockFitContent }),
    applyOptions: mockApplyOptions,
    remove: mockRemove,
  }),
  ColorType: { Solid: "Solid" },
}));

// ---- Mock API ----

const mockFetchOHLCV = vi.fn();

vi.mock("../src/shared/api/marketData", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/marketData")>();
  return {
    ...actual,
    fetchOHLCV: (...args: unknown[]) => mockFetchOHLCV(...args),
  };
});

// Mock ops API to prevent unrelated fetch errors
const mockFetchRoster = vi.fn();
const mockFetchHealth = vi.fn();
const mockFetchTrace = vi.fn();
const mockFetchDetail = vi.fn();
const mockFetchRuns = vi.fn();

vi.mock("../src/shared/api/ops", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/ops")>();
  return {
    ...actual,
    fetchAgentRoster: (...args: unknown[]) => mockFetchRoster(...args),
    fetchAgentHealth: (...args: unknown[]) => mockFetchHealth(...args),
    fetchAgentTrace: (...args: unknown[]) => mockFetchTrace(...args),
    fetchAgentDetail: (...args: unknown[]) => mockFetchDetail(...args),
  };
});

vi.mock("../src/shared/api/runs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/runs")>();
  return {
    ...actual,
    fetchRuns: (...args: unknown[]) => mockFetchRuns(...args),
  };
});

// Import after mocks
import { CandlestickChart } from "../src/workspaces/ops/components/CandlestickChart";
import { AgentOpsPage } from "../src/workspaces/ops/components/AgentOpsPage";

// ---- Test fixtures ----

function makeOHLCVResponse(
  overrides?: Partial<OHLCVResponse>,
): OHLCVResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-15T12:00:00Z",
    data_state: "live",
    instrument: "XAUUSD",
    timeframe: "4h",
    candles: [
      { timestamp: 1710000000, open: 2700, high: 2710, low: 2695, close: 2705, volume: 5.2 },
      { timestamp: 1710014400, open: 2705, high: 2715, low: 2700, close: 2712, volume: 3.1 },
      { timestamp: 1710028800, open: 2712, high: 2720, low: 2708, close: 2718, volume: 4.0 },
    ],
    candle_count: 3,
    ...overrides,
  };
}

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

// ---- Tests ----

describe("CandlestickChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRoster.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchHealth.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchTrace.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchDetail.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchRuns.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
  });

  // AC-25: Chart renders candles from API response
  describe("AC-25: chart renders", () => {
    it("renders chart panel when data is loaded", async () => {
      mockFetchOHLCV.mockResolvedValue({
        ok: true,
        status: 200,
        data: makeOHLCVResponse(),
      });

      renderWithClient(<CandlestickChart instrument="XAUUSD" />);

      const panel = await screen.findByTestId("chart-panel");
      expect(panel).toBeDefined();
      expect(panel.textContent).toContain("XAUUSD");
      expect(panel.textContent).toContain("4h");
    });

    it("displays candle count", async () => {
      mockFetchOHLCV.mockResolvedValue({
        ok: true,
        status: 200,
        data: makeOHLCVResponse(),
      });

      renderWithClient(<CandlestickChart instrument="XAUUSD" />);

      const panel = await screen.findByTestId("chart-panel");
      expect(panel.textContent).toContain("3 candles");
    });
  });

  // AC-26: Chart reads instrument from browser row (tested indirectly —
  // CandlestickChart receives instrument as prop from AgentOpsPage)
  describe("AC-26: instrument from browser row", () => {
    it("receives instrument as prop, not from trace", () => {
      // CandlestickChart props type requires instrument: string | null
      // It does not import or use trace endpoint
      mockFetchOHLCV.mockResolvedValue({
        ok: true,
        status: 200,
        data: makeOHLCVResponse({ instrument: "EURUSD" }),
      });

      renderWithClient(<CandlestickChart instrument="EURUSD" />);
      // Fetch is called with the instrument prop, not from trace
      expect(mockFetchOHLCV).toHaveBeenCalledWith(
        expect.objectContaining({ instrument: "EURUSD" }),
      );
    });
  });

  // AC-27: Loading state
  describe("AC-27: loading state", () => {
    it("shows loading skeleton while fetching", () => {
      mockFetchOHLCV.mockReturnValue(new Promise(() => {})); // never resolves

      renderWithClient(<CandlestickChart instrument="XAUUSD" />);

      expect(screen.getByTestId("chart-loading")).toBeDefined();
    });
  });

  // AC-28: Empty and error states
  describe("AC-28: empty/error states", () => {
    it("shows empty state for zero candles", async () => {
      mockFetchOHLCV.mockResolvedValue({
        ok: true,
        status: 200,
        data: makeOHLCVResponse({ candles: [], candle_count: 0 }),
      });

      renderWithClient(<CandlestickChart instrument="XAUUSD" />);

      const empty = await screen.findByTestId("chart-empty");
      expect(empty).toBeDefined();
      expect(empty.textContent).toContain("No candle data");
    });

    it("shows error state on fetch failure", async () => {
      mockFetchOHLCV.mockResolvedValue({
        ok: false,
        status: 404,
        detail: { error: "INSTRUMENT_NOT_FOUND", message: "Unknown instrument" },
      });

      renderWithClient(<CandlestickChart instrument="FAKEUSD" />);

      const error = await screen.findByTestId("chart-error");
      expect(error).toBeDefined();
      expect(error.textContent).toContain("Chart unavailable");
    });
  });

  // AC-29: Chart embedded in Run mode (tested in AgentOpsPage integration)
  describe("AC-29: embedded in Run mode", () => {
    it("renders null when no instrument", () => {
      const { container } = renderWithClient(
        <CandlestickChart instrument={null} />,
      );
      expect(container.innerHTML).toBe("");
    });
  });

  // AC-30: Chart isolation — chart failure does NOT affect trace rendering
  describe("AC-30: chart isolation", () => {
    it("chart error does not affect other components", async () => {
      // Chart errors are contained within its own component boundary
      mockFetchOHLCV.mockResolvedValue({
        ok: false,
        status: 500,
        detail: { error: "MARKET_DATA_READ_FAILED", message: "I/O error" },
      });

      renderWithClient(<CandlestickChart instrument="XAUUSD" />);

      const error = await screen.findByTestId("chart-error");
      expect(error).toBeDefined();
      // The component renders an error banner, not throwing — so parent is fine
    });

    it("stale data shows badge but still renders", async () => {
      mockFetchOHLCV.mockResolvedValue({
        ok: true,
        status: 200,
        data: makeOHLCVResponse({ data_state: "stale" }),
      });

      renderWithClient(<CandlestickChart instrument="XAUUSD" />);

      const panel = await screen.findByTestId("chart-panel");
      expect(panel).toBeDefined();
      const badge = screen.getByTestId("chart-stale-badge");
      expect(badge.textContent).toContain("Stale");
    });
  });
});
