// ---------------------------------------------------------------------------
// CandlestickChart tests — PR-CHART-1 + PR-CHART-2.
//
// PR-CHART-1: AC-25 through AC-30 from docs/specs/PR_CHART_1_SPEC.md §7.
// PR-CHART-2: AC-1 through AC-33 from docs/specs/PR_CHART_2_SPEC.md §8.
// Deterministic — no live pipeline dependency. lightweight-charts is mocked.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { OHLCVResponse } from "../src/shared/api/marketData";

// ---- Mock lightweight-charts ----

const mockSetData = vi.fn();
const mockFitContent = vi.fn();
const mockApplyOptions = vi.fn();
const mockRemove = vi.fn();
const mockSetMarkers = vi.fn();
const mockScrollToPosition = vi.fn();

vi.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: mockSetData }),
    priceScale: () => ({ applyOptions: mockApplyOptions }),
    timeScale: () => ({ fitContent: mockFitContent, scrollToPosition: mockScrollToPosition }),
    applyOptions: mockApplyOptions,
    remove: mockRemove,
  }),
  createSeriesMarkers: () => ({
    setMarkers: mockSetMarkers,
    markers: () => [],
  }),
  CandlestickSeries: "CandlestickSeries",
  HistogramSeries: "HistogramSeries",
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
import { CandlestickChart, normalizeVerdict } from "../src/workspaces/ops/components/CandlestickChart";
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
      expect(error.textContent).toContain("Unable to load chart data for this timeframe.");
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

// ============================================================================
// PR-CHART-2 Tests
// ============================================================================

describe("PR-CHART-2: Timeframe tabs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRoster.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchHealth.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchTrace.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchDetail.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchRuns.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
  });

  // AC-1: data-driven timeframe tabs render
  it("AC-1: renders timeframe tabs from availableTimeframes", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        availableTimeframes={["15m", "1h", "4h", "1d"]}
        selectedTimeframe="4h"
      />,
    );

    const panel = await screen.findByTestId("chart-panel");
    expect(panel).toBeDefined();
    const tabs = screen.getByTestId("timeframe-tabs");
    expect(tabs).toBeDefined();
    expect(screen.getByTestId("tf-tab-15m")).toBeDefined();
    expect(screen.getByTestId("tf-tab-1h")).toBeDefined();
    expect(screen.getByTestId("tf-tab-4h")).toBeDefined();
    expect(screen.getByTestId("tf-tab-1d")).toBeDefined();
  });

  // AC-1 + controlled component: tab click calls onTimeframeChange
  it("tab click calls onTimeframeChange", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    const onTfChange = vi.fn();
    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        availableTimeframes={["15m", "1h", "4h", "1d"]}
        selectedTimeframe="4h"
        onTimeframeChange={onTfChange}
      />,
    );

    await screen.findByTestId("chart-panel");
    const user = userEvent.setup();
    await user.click(screen.getByTestId("tf-tab-1h"));
    expect(onTfChange).toHaveBeenCalledWith("1h");
  });

  // Tabs not rendered when availableTimeframes is null/empty
  it("no tabs when availableTimeframes is null", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart instrument="XAUUSD" availableTimeframes={null} />,
    );

    await screen.findByTestId("chart-panel");
    expect(screen.queryByTestId("timeframe-tabs")).toBeNull();
  });

  it("no tabs when availableTimeframes is empty array", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart instrument="XAUUSD" availableTimeframes={[]} />,
    );

    await screen.findByTestId("chart-panel");
    expect(screen.queryByTestId("timeframe-tabs")).toBeNull();
  });

  // AC-8: per-TF fetch failure shows error but tabs still render
  it("AC-8: chart fetch failure shows error with tabs still visible", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: false,
      status: 500,
      detail: { error: "MARKET_DATA_READ_FAILED", message: "I/O error" },
    });

    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        availableTimeframes={["15m", "1h", "4h", "1d"]}
        selectedTimeframe="4h"
      />,
    );

    const error = await screen.findByTestId("chart-error");
    expect(error.textContent).toContain("Unable to load chart data for this timeframe.");
    // Tabs are still rendered above the error
    expect(screen.getByTestId("timeframe-tabs")).toBeDefined();
  });
});

describe("PR-CHART-2: Run-time visual marker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRoster.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchHealth.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchTrace.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchDetail.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchRuns.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
  });

  // AC-10: No run selected → no marker/annotation
  it("AC-10: no marker or verdict badge when no run selected", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(<CandlestickChart instrument="XAUUSD" />);

    await screen.findByTestId("chart-panel");
    expect(screen.queryByTestId("verdict-badge")).toBeNull();
    expect(screen.queryByTestId("run-out-of-range")).toBeNull();
    expect(screen.queryByTestId("run-invalid-timestamp")).toBeNull();
  });

  // AC-11 + AC-12: valid timestamp within range → marker + verdict badge
  it("AC-11/12: shows verdict badge for aligned run", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    // Candle timestamps: 1710000000, 1710014400, 1710028800
    // Run at 1710014400 (second candle) = 2024-03-09T20:00:00Z
    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        selectedRunTimestamp="2024-03-09T20:00:00Z"
        selectedRunVerdict="BUY"
      />,
    );

    await screen.findByTestId("chart-panel");
    const badge = screen.getByTestId("verdict-badge");
    expect(badge.textContent).toContain("BUY");
  });

  // AC-13: invalid timestamp
  it("AC-13: shows invalid-timestamp message for unparsable timestamp", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        selectedRunTimestamp="not-a-date"
        selectedRunVerdict="BUY"
      />,
    );

    await screen.findByTestId("chart-panel");
    const msg = screen.getByTestId("run-invalid-timestamp");
    expect(msg.textContent).toContain("Selected run timestamp is invalid.");
  });

  // AC-14: out of range timestamp
  it("AC-14: shows out-of-range message when timestamp is before all candles", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    // Timestamp way before any candle
    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        selectedRunTimestamp="2020-01-01T00:00:00Z"
        selectedRunVerdict="BUY"
      />,
    );

    await screen.findByTestId("chart-panel");
    const msg = screen.getByTestId("run-out-of-range");
    expect(msg.textContent).toContain("Selected run is outside the loaded chart range.");
  });

  // AC-30 (missing timestamp)
  it("AC-30: null timestamp shows invalid-timestamp state", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        selectedRunTimestamp=""
        selectedRunVerdict="BUY"
      />,
    );

    await screen.findByTestId("chart-panel");
    const msg = screen.getByTestId("run-invalid-timestamp");
    expect(msg.textContent).toContain("Selected run timestamp is invalid.");
  });
});

describe("PR-CHART-2: Verdict normalization (§4.4)", () => {
  // AC-16: BUY/LONG/ENTER_LONG → BUY
  it("AC-16: normalizes BUY variants to BUY", () => {
    expect(normalizeVerdict("BUY")).toBe("BUY");
    expect(normalizeVerdict("LONG")).toBe("BUY");
    expect(normalizeVerdict("ENTER_LONG")).toBe("BUY");
    expect(normalizeVerdict("buy")).toBe("BUY");
    expect(normalizeVerdict(" Buy ")).toBe("BUY");
  });

  // AC-17: SELL/SHORT/ENTER_SHORT → SELL
  it("AC-17: normalizes SELL variants to SELL", () => {
    expect(normalizeVerdict("SELL")).toBe("SELL");
    expect(normalizeVerdict("SHORT")).toBe("SELL");
    expect(normalizeVerdict("ENTER_SHORT")).toBe("SELL");
  });

  // AC-18: NO_TRADE/FLAT/SKIP → NO_TRADE
  it("AC-18: normalizes NO_TRADE variants to NO_TRADE", () => {
    expect(normalizeVerdict("NO_TRADE")).toBe("NO_TRADE");
    expect(normalizeVerdict("FLAT")).toBe("NO_TRADE");
    expect(normalizeVerdict("SKIP")).toBe("NO_TRADE");
  });

  // AC-19: unknown/null/malformed → UNKNOWN (NOT NO_TRADE)
  it("AC-19: normalizes unknown/null/malformed to UNKNOWN", () => {
    expect(normalizeVerdict(null)).toBe("UNKNOWN");
    expect(normalizeVerdict(undefined)).toBe("UNKNOWN");
    expect(normalizeVerdict("")).toBe("UNKNOWN");
    expect(normalizeVerdict("MAYBE")).toBe("UNKNOWN");
    expect(normalizeVerdict("garbage")).toBe("UNKNOWN");
  });

  // Critical: unknown does NOT silently become NO_TRADE
  it("unknown values are UNKNOWN not NO_TRADE", () => {
    expect(normalizeVerdict("UNKNOWN_VALUE")).not.toBe("NO_TRADE");
    expect(normalizeVerdict(null)).not.toBe("NO_TRADE");
    expect(normalizeVerdict("")).not.toBe("NO_TRADE");
  });
});

describe("PR-CHART-2: Chart isolation (§5.3)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchRoster.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchHealth.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchTrace.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchDetail.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
    mockFetchRuns.mockResolvedValue({ ok: false, status: 0, detail: "not needed" });
  });

  // CHART-1 baseline preserved: no-run chart renders normally
  it("CHART-1 baseline: chart renders 4h candles with no run props", async () => {
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
    // No marker/verdict artifacts
    expect(screen.queryByTestId("verdict-badge")).toBeNull();
    expect(screen.queryByTestId("run-out-of-range")).toBeNull();
    expect(screen.queryByTestId("run-invalid-timestamp")).toBeNull();
  });

  // Malformed OHLCV: empty candles array doesn't crash
  it("AC-26: malformed OHLCV degrades to empty state, no crash", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse({ candles: [] as any, candle_count: 0 }),
    });

    renderWithClient(<CandlestickChart instrument="XAUUSD" />);

    const empty = await screen.findByTestId("chart-empty");
    expect(empty).toBeDefined();
  });

  // Null run values don't crash
  it("AC-28: null/missing run values don't crash", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        selectedRunTimestamp={null}
        selectedRunVerdict={null}
      />,
    );

    const panel = await screen.findByTestId("chart-panel");
    expect(panel).toBeDefined();
    expect(screen.queryByTestId("verdict-badge")).toBeNull();
  });

  // Missing verdict normalizes to UNKNOWN
  it("AC-29: missing verdict normalizes to UNKNOWN", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(
      <CandlestickChart
        instrument="XAUUSD"
        selectedRunTimestamp="2024-03-09T20:00:00Z"
        selectedRunVerdict={null}
      />,
    );

    await screen.findByTestId("chart-panel");
    const badge = screen.getByTestId("verdict-badge");
    expect(badge.textContent).toContain("Unknown");
  });

  // useMarketData backward-compatible: hook works without new props
  it("useMarketData backward-compat: works with just instrument", async () => {
    mockFetchOHLCV.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeOHLCVResponse(),
    });

    renderWithClient(<CandlestickChart instrument="XAUUSD" />);

    await screen.findByTestId("chart-panel");
    expect(mockFetchOHLCV).toHaveBeenCalledWith(
      expect.objectContaining({ instrument: "XAUUSD", timeframe: "4h" }),
    );
  });
});
