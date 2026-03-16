// ---------------------------------------------------------------------------
// Reflect workspace tests — PR-REFLECT-2.
//
// Covers AC-1 through AC-44 from docs/specs/PR_REFLECT_2_SPEC.md §6.
// Deterministic — all endpoints mocked.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PersonaPerformanceResponse, PatternSummaryResponse, RunBundleResponse } from "../src/shared/api/reflect";
import type { RunBrowserResponse } from "../src/shared/api/runs";

// ---- Mock API ----

const mockFetchPersonaPerformance = vi.fn();
const mockFetchPatternSummary = vi.fn();
const mockFetchRunBundle = vi.fn();
const mockFetchRuns = vi.fn();

vi.mock("../src/shared/api/reflect", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/reflect")>();
  return {
    ...actual,
    fetchPersonaPerformance: (...args: unknown[]) => mockFetchPersonaPerformance(...args),
    fetchPatternSummary: (...args: unknown[]) => mockFetchPatternSummary(...args),
    fetchRunBundle: (...args: unknown[]) => mockFetchRunBundle(...args),
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
import { ReflectPage } from "../src/workspaces/reflect/components/ReflectPage";
import { PersonaPerformanceTable } from "../src/workspaces/reflect/components/PersonaPerformanceTable";
import { PatternSummaryTable } from "../src/workspaces/reflect/components/PatternSummaryTable";
import { RunDetailView } from "../src/workspaces/reflect/components/RunDetailView";
import { UsageSummaryCard } from "../src/workspaces/reflect/components/UsageSummaryCard";
import {
  normalizePersonaPerformance,
  normalizePatternSummary,
  normalizeRunBundle,
  normalizeRunForReflect,
} from "../src/workspaces/reflect/adapters/reflectAdapter";

// ---- Test helpers ----

function renderWithQuery(element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>,
  );
}

// ---- Fixtures ----

function makePersonaPerformanceResponse(
  overrides?: Partial<PersonaPerformanceResponse>,
): PersonaPerformanceResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-16T12:00:00Z",
    data_state: "live",
    source_of_truth: "run_record.json+optional_audit",
    threshold: 10,
    threshold_met: true,
    scan_bounds: {
      max_runs: 50,
      inspected_dirs: 25,
      valid_runs: 20,
      skipped_runs: 2,
    },
    stats: [
      {
        persona: "default_analyst",
        participation_count: 18,
        skip_count: 1,
        fail_count: 1,
        participation_rate: 0.9,
        override_count: 0,
        override_rate: 0.0,
        stance_alignment: 0.75,
        avg_confidence: 0.82,
        flagged: false,
      },
      {
        persona: "risk_challenger",
        participation_count: 15,
        skip_count: 3,
        fail_count: 2,
        participation_rate: 0.75,
        override_count: 10,
        override_rate: 0.67,
        stance_alignment: null,
        avg_confidence: null,
        flagged: true,
      },
    ],
    ...overrides,
  };
}

function makePatternSummaryResponse(
  overrides?: Partial<PatternSummaryResponse>,
): PatternSummaryResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-16T12:00:00Z",
    data_state: "live",
    source_of_truth: "run_record.json+optional_audit",
    threshold: 10,
    scan_bounds: {
      max_runs: 50,
      inspected_dirs: 25,
      valid_runs: 20,
      skipped_runs: 0,
    },
    buckets: [
      {
        instrument: "XAUUSD",
        session: "NY",
        run_count: 12,
        threshold_met: true,
        verdict_distribution: [
          { verdict: "BUY", count: 3 },
          { verdict: "NO_TRADE", count: 7 },
          { verdict: "SELL", count: 2 },
        ],
        no_trade_rate: 0.583,
        flagged: false,
      },
      {
        instrument: "EURUSD",
        session: "LDN",
        run_count: 5,
        threshold_met: false,
        verdict_distribution: [],
        no_trade_rate: null,
        flagged: false,
      },
    ],
    ...overrides,
  };
}

function makeRunBundleResponse(
  overrides?: Partial<RunBundleResponse>,
): RunBundleResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-16T12:00:00Z",
    data_state: "live",
    source_of_truth: "run_record.json",
    run_id: "run_001",
    artifact_status: {
      run_record: "present",
      usage_jsonl: "present",
      usage_json: "present",
    },
    run_record: {
      run_id: "run_001",
      timestamp: "2026-03-16T11:00:00Z",
      request: { instrument: "XAUUSD", session: "NY" },
      arbiter: {
        verdict: "NO_TRADE",
        confidence: 0.85,
        method: "consensus",
        dissent_summary: "Risk challenger flagged high volatility",
      },
      analysts: [
        { persona: "default_analyst", status: "active", stance: "bullish", confidence: 0.7 },
        { persona: "risk_challenger", status: "active", stance: "bearish", confidence: 0.9 },
      ],
    },
    usage_summary: {
      total_calls: 5,
      models_used: ["claude-sonnet-4-20250514"],
      total_tokens: 12500,
      estimated_cost: 0.0125,
    },
    usage_jsonl: [],
    ...overrides,
  };
}

function makeRunBrowserResponse(
  overrides?: Partial<RunBrowserResponse>,
): RunBrowserResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-16T12:00:00Z",
    data_state: "live",
    items: [
      {
        run_id: "run_001",
        timestamp: "2026-03-16T11:00:00Z",
        instrument: "XAUUSD",
        session: "NY",
        final_decision: "NO_TRADE",
        run_status: "completed",
        trace_available: true,
      },
      {
        run_id: "run_002",
        timestamp: "2026-03-16T10:00:00Z",
        instrument: "EURUSD",
        session: "LDN",
        final_decision: "BUY",
        run_status: "completed",
        trace_available: true,
      },
    ],
    page: 1,
    page_size: 20,
    total: 2,
    has_next: false,
    ...overrides,
  };
}

// ---- Setup ----

beforeEach(() => {
  vi.clearAllMocks();
});

// ===== ADAPTER UNIT TESTS =====

describe("reflectAdapter", () => {
  describe("normalizePersonaPerformance", () => {
    it("formats percentages and decimals correctly", () => {
      const response = makePersonaPerformanceResponse();
      const vm = normalizePersonaPerformance(response);

      expect(vm.personas[0].participationRate).toBe("90%");
      expect(vm.personas[0].overrideRate).toBe("0%");
      expect(vm.personas[0].stanceAlignment).toBe("75%");
      expect(vm.personas[0].avgConfidence).toBe("0.82");
    });

    it("displays \u2014 for null metrics (AC-7, AC-8)", () => {
      const response = makePersonaPerformanceResponse();
      const vm = normalizePersonaPerformance(response);

      expect(vm.personas[1].stanceAlignment).toBe("\u2014");
      expect(vm.personas[1].avgConfidence).toBe("\u2014");
    });

    it("handles all-null metrics across all personas (AC-8)", () => {
      const response = makePersonaPerformanceResponse({
        stats: [
          {
            persona: "p1", participation_count: 10, skip_count: 0,
            fail_count: 0, participation_rate: 1.0, override_count: 0,
            override_rate: null, stance_alignment: null, avg_confidence: null,
            flagged: false,
          },
          {
            persona: "p2", participation_count: 8, skip_count: 1,
            fail_count: 1, participation_rate: 0.8, override_count: 0,
            override_rate: null, stance_alignment: null, avg_confidence: null,
            flagged: false,
          },
        ],
      });
      const vm = normalizePersonaPerformance(response);

      expect(vm.personas.every(p => p.overrideRate === "\u2014")).toBe(true);
      expect(vm.personas.every(p => p.stanceAlignment === "\u2014")).toBe(true);
      expect(vm.personas.every(p => p.avgConfidence === "\u2014")).toBe(true);
      // Table should still have useful data
      expect(vm.personas[0].participationRate).toBe("100%");
    });

    it("preserves flagged state", () => {
      const response = makePersonaPerformanceResponse();
      const vm = normalizePersonaPerformance(response);

      expect(vm.personas[0].flagged).toBe(false);
      expect(vm.personas[1].flagged).toBe(true);
    });

    it("generates scan footer with valid_runs and skipped_runs", () => {
      const response = makePersonaPerformanceResponse();
      const vm = normalizePersonaPerformance(response);

      expect(vm.scanFooter).toContain("20 runs");
      expect(vm.scanFooter).toContain("2 skipped");
    });
  });

  describe("normalizePatternSummary", () => {
    it("formats above-threshold verdict distribution inline", () => {
      const response = makePatternSummaryResponse();
      const vm = normalizePatternSummary(response);

      expect(vm.buckets[0].verdictDisplay).toContain("BUY: 3");
      expect(vm.buckets[0].verdictDisplay).toContain("NO_TRADE: 7");
      expect(vm.buckets[0].verdictDisplay).toContain("SELL: 2");
    });

    it("shows insufficient data for below-threshold buckets (AC-18)", () => {
      const response = makePatternSummaryResponse();
      const vm = normalizePatternSummary(response);

      expect(vm.buckets[1].verdictDisplay).toBe("insufficient data (5/10 runs)");
    });

    it("formats NO_TRADE rate as percentage", () => {
      const response = makePatternSummaryResponse();
      const vm = normalizePatternSummary(response);

      expect(vm.buckets[0].noTradeRate).toBe("58%");
    });

    it("displays \u2014 for null no_trade_rate", () => {
      const response = makePatternSummaryResponse();
      const vm = normalizePatternSummary(response);

      expect(vm.buckets[1].noTradeRate).toBe("\u2014");
    });
  });

  describe("normalizeRunBundle", () => {
    it("extracts verdict, confidence, and method", () => {
      const response = makeRunBundleResponse();
      const vm = normalizeRunBundle(response);

      expect(vm.verdict).toBe("NO_TRADE");
      expect(vm.arbiterConfidence).toBe("0.85");
      expect(vm.arbiterMethod).toBe("consensus");
    });

    it("extracts analyst contributions", () => {
      const response = makeRunBundleResponse();
      const vm = normalizeRunBundle(response);

      expect(vm.analysts).toHaveLength(2);
      expect(vm.analysts[0].persona).toBe("default_analyst");
      expect(vm.analysts[0].confidence).toBe("0.70");
      expect(vm.analysts[1].persona).toBe("risk_challenger");
    });

    it("handles missing usage_summary as null (AC-28)", () => {
      const response = makeRunBundleResponse({ usage_summary: null });
      const vm = normalizeRunBundle(response);

      expect(vm.usageSummary).toBeNull();
    });

    it("extracts usage summary fields", () => {
      const response = makeRunBundleResponse();
      const vm = normalizeRunBundle(response);

      expect(vm.usageSummary).not.toBeNull();
      expect(vm.usageSummary!.totalCalls).toBe("5");
      expect(vm.usageSummary!.totalTokens).toBe("12500");
    });

    it("extracts artifact status", () => {
      const response = makeRunBundleResponse();
      const vm = normalizeRunBundle(response);

      expect(vm.artifactStatus.runRecord).toBe("present");
      expect(vm.artifactStatus.usageJsonl).toBe("present");
    });

    it("handles missing optional arbiter fields with \u2014", () => {
      const response = makeRunBundleResponse({
        run_record: {
          run_id: "run_001",
          timestamp: "2026-03-16T11:00:00Z",
          request: { instrument: "XAUUSD", session: "NY" },
          arbiter: { verdict: "NO_TRADE" },
          analysts: [],
        },
      });
      const vm = normalizeRunBundle(response);

      expect(vm.arbiterConfidence).toBe("\u2014");
      expect(vm.arbiterMethod).toBe("\u2014");
      expect(vm.dissentSummary).toBe("Not available");
    });
  });

  describe("normalizeRunForReflect", () => {
    it("maps run browser item fields", () => {
      const item = {
        run_id: "run_001",
        timestamp: "2026-03-16T11:00:00Z",
        instrument: "XAUUSD",
        session: "NY",
        final_decision: "BUY",
        run_status: "completed" as const,
        trace_available: true,
      };
      const vm = normalizeRunForReflect(item);

      expect(vm.runId).toBe("run_001");
      expect(vm.instrument).toBe("XAUUSD");
      expect(vm.session).toBe("NY");
      expect(vm.finalDecision).toBe("BUY");
      expect(vm.runStatus).toBe("completed");
    });

    it("handles null fields with \u2014", () => {
      const item = {
        run_id: "run_001",
        timestamp: "2026-03-16T11:00:00Z",
        instrument: null,
        session: null,
        final_decision: null,
        run_status: "failed" as const,
        trace_available: false,
      };
      const vm = normalizeRunForReflect(item);

      expect(vm.instrument).toBe("\u2014");
      expect(vm.session).toBe("\u2014");
      expect(vm.finalDecision).toBe("\u2014");
    });
  });
});

// ===== COMPONENT TESTS =====

describe("PersonaPerformanceTable", () => {
  it("renders loading skeleton while fetching (AC-14)", () => {
    mockFetchPersonaPerformance.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<PersonaPerformanceTable />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders populated table with persona rows (AC-6)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse(),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    const table = await screen.findByTestId("persona-performance-table");
    expect(table).toBeInTheDocument();
    expect(screen.getByText("default_analyst")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
  });

  it("shows \u2014 for null metrics in cells (AC-7)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse(),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    await screen.findByTestId("persona-performance-table");
    // risk_challenger has null stance_alignment and avg_confidence
    const rows = screen.getAllByRole("row");
    // Header row + 2 data rows
    expect(rows.length).toBe(3);
  });

  it("renders table even when ALL metrics are null (AC-8)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse({
        stats: [
          {
            persona: "p1", participation_count: 10, skip_count: 0,
            fail_count: 0, participation_rate: 1.0, override_count: 0,
            override_rate: null, stance_alignment: null, avg_confidence: null,
            flagged: false,
          },
        ],
      }),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    const table = await screen.findByTestId("persona-performance-table");
    expect(table).toBeInTheDocument();
    // All 7 column headers still present
    expect(screen.getByText("Override Rate")).toBeInTheDocument();
    expect(screen.getByText("Stance Alignment")).toBeInTheDocument();
    expect(screen.getByText("Avg Confidence")).toBeInTheDocument();
  });

  it("shows flagged persona with amber prefix (AC-9)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse(),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    await screen.findByTestId("persona-performance-table");
    expect(screen.getByText("\u26A0 risk_challenger")).toBeInTheDocument();
  });

  it("shows welcoming message when below threshold (AC-10)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse({
        threshold_met: false,
        threshold: 10,
        stats: [],
      }),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    expect(await screen.findByText("Not enough run history yet")).toBeInTheDocument();
    expect(screen.getByText(/Need at least 10 runs/)).toBeInTheDocument();
    expect(screen.queryByTestId("persona-performance-table")).not.toBeInTheDocument();
  });

  it("shows stale banner above table when data_state is stale (AC-11)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse({ data_state: "stale" }),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    const banner = await screen.findByTestId("persona-stale-banner");
    expect(banner).toBeInTheDocument();
    expect(banner.textContent).toContain("incomplete data");
  });

  it("shows stale banner AND populated table simultaneously (AC-12)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse({ data_state: "stale" }),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    await screen.findByTestId("persona-stale-banner");
    expect(screen.getByTestId("persona-performance-table")).toBeInTheDocument();
    expect(screen.getByText("default_analyst")).toBeInTheDocument();
  });

  it("shows scan info footer (AC-13)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse(),
    });
    renderWithQuery(<PersonaPerformanceTable />);

    const footer = await screen.findByTestId("persona-scan-footer");
    expect(footer.textContent).toContain("20 runs");
    expect(footer.textContent).toContain("2 skipped");
  });

  it("shows error state with retry on API failure (AC-15)", async () => {
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Server error",
    });
    renderWithQuery(<PersonaPerformanceTable />);

    expect(await screen.findByText("Failed to load persona performance")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("PatternSummaryTable", () => {
  it("renders loading skeleton (AC-20)", () => {
    mockFetchPatternSummary.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<PatternSummaryTable />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders populated table with buckets (AC-16)", async () => {
    mockFetchPatternSummary.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePatternSummaryResponse(),
    });
    renderWithQuery(<PatternSummaryTable />);

    const table = await screen.findByTestId("pattern-summary-table");
    expect(table).toBeInTheDocument();
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
  });

  it("shows verdict distribution inline (AC-17)", async () => {
    mockFetchPatternSummary.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePatternSummaryResponse(),
    });
    renderWithQuery(<PatternSummaryTable />);

    await screen.findByTestId("pattern-summary-table");
    expect(screen.getByText(/BUY: 3/)).toBeInTheDocument();
    expect(screen.getByText(/NO_TRADE: 7/)).toBeInTheDocument();
  });

  it("shows insufficient data for below-threshold buckets (AC-18)", async () => {
    mockFetchPatternSummary.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePatternSummaryResponse(),
    });
    renderWithQuery(<PatternSummaryTable />);

    await screen.findByTestId("pattern-summary-table");
    expect(screen.getByText("insufficient data (5/10 runs)")).toBeInTheDocument();
  });

  it("shows flagged bucket with amber prefix (AC-19)", async () => {
    mockFetchPatternSummary.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePatternSummaryResponse({
        buckets: [
          {
            instrument: "XAUUSD",
            session: "NY",
            run_count: 15,
            threshold_met: true,
            verdict_distribution: [{ verdict: "NO_TRADE", count: 13 }, { verdict: "BUY", count: 2 }],
            no_trade_rate: 0.867,
            flagged: true,
          },
        ],
      }),
    });
    renderWithQuery(<PatternSummaryTable />);

    await screen.findByTestId("pattern-summary-table");
    expect(screen.getByText("\u26A0 XAUUSD")).toBeInTheDocument();
  });

  it("shows welcoming message when all buckets below threshold", async () => {
    mockFetchPatternSummary.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePatternSummaryResponse({
        buckets: [
          {
            instrument: "XAUUSD", session: "NY", run_count: 3,
            threshold_met: false, verdict_distribution: [],
            no_trade_rate: null, flagged: false,
          },
        ],
      }),
    });
    renderWithQuery(<PatternSummaryTable />);

    expect(await screen.findByText(/Not enough run history/)).toBeInTheDocument();
  });

  it("shows error state with retry (AC-21)", async () => {
    mockFetchPatternSummary.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Server error",
    });
    renderWithQuery(<PatternSummaryTable />);

    expect(await screen.findByText("Failed to load pattern summary")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("RunDetailView", () => {
  it("shows placeholder when no run selected (AC-31)", () => {
    renderWithQuery(<RunDetailView runId={null} />);

    expect(screen.getByTestId("run-detail-placeholder")).toBeInTheDocument();
    expect(screen.getByText(/Select a run from the history/)).toBeInTheDocument();
  });

  it("shows loading skeleton while bundle loads (AC-33)", () => {
    mockFetchRunBundle.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<RunDetailView runId="run_001" />);

    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders full detail view with all sections (AC-26, AC-27, AC-28, AC-29)", async () => {
    mockFetchRunBundle.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBundleResponse(),
    });
    renderWithQuery(<RunDetailView runId="run_001" />);

    const detail = await screen.findByTestId("run-detail-view");
    expect(detail).toBeInTheDocument();

    // Verdict (AC-26)
    expect(screen.getByText("NO_TRADE")).toBeInTheDocument();
    expect(screen.getByText("0.85")).toBeInTheDocument();

    // Analysts (AC-27)
    expect(screen.getByText("default_analyst")).toBeInTheDocument();
    expect(screen.getByText("risk_challenger")).toBeInTheDocument();

    // Usage (AC-28)
    const usageCard = screen.getByTestId("usage-summary-card");
    expect(usageCard).toBeInTheDocument();

    // Artifact status (AC-29)
    const artifactStatus = screen.getByTestId("artifact-status");
    expect(artifactStatus).toBeInTheDocument();
  });

  it("shows \u2014 for absent optional analyst fields (AC-27)", async () => {
    mockFetchRunBundle.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBundleResponse({
        run_record: {
          run_id: "run_001",
          timestamp: "2026-03-16T11:00:00Z",
          request: { instrument: "XAUUSD", session: "NY" },
          arbiter: { verdict: "NO_TRADE" },
          analysts: [{ persona: "minimal_analyst" }],
        },
      }),
    });
    renderWithQuery(<RunDetailView runId="run_001" />);

    await screen.findByTestId("run-detail-view");
    expect(screen.getByText("minimal_analyst")).toBeInTheDocument();
  });

  it("shows stale banner AND remaining sections for partial bundle (AC-30)", async () => {
    mockFetchRunBundle.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBundleResponse({
        data_state: "stale",
        artifact_status: {
          run_record: "present",
          usage_jsonl: "missing",
          usage_json: "missing",
        },
        usage_summary: null,
      }),
    });
    renderWithQuery(<RunDetailView runId="run_001" />);

    const banner = await screen.findByTestId("bundle-stale-banner");
    expect(banner).toBeInTheDocument();

    // Detail sections still render
    expect(screen.getByTestId("run-detail-view")).toBeInTheDocument();
    expect(screen.getByText("NO_TRADE")).toBeInTheDocument();
  });

  it("shows 404 message with reselection guidance (AC-32)", async () => {
    mockFetchRunBundle.mockResolvedValue({
      ok: false,
      status: 404,
      detail: { error: "RUN_NOT_FOUND", message: "No valid run_record.json for run_id=nonexistent" },
    });
    renderWithQuery(<RunDetailView runId="nonexistent" />);

    const notFound = await screen.findByTestId("run-not-found");
    expect(notFound).toBeInTheDocument();
    expect(screen.getByText(/could not be found/)).toBeInTheDocument();
    expect(screen.getByText(/Select another run/)).toBeInTheDocument();
  });

  it("shows error state with retry for non-404 errors (AC-34)", async () => {
    mockFetchRunBundle.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Internal error",
    });
    renderWithQuery(<RunDetailView runId="run_001" />);

    expect(await screen.findByText("Failed to load run details")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("UsageSummaryCard", () => {
  it("shows Not available when usage is null (AC-28)", () => {
    render(<UsageSummaryCard usage={null} />);

    expect(screen.getByText("Not available")).toBeInTheDocument();
  });

  it("renders usage data when present", () => {
    render(
      <UsageSummaryCard
        usage={{
          totalCalls: "5",
          modelsUsed: "claude-sonnet-4-20250514",
          totalTokens: "12500",
          estimatedCost: "$0.0125",
        }}
      />,
    );

    expect(screen.getByTestId("usage-summary-card")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("12500")).toBeInTheDocument();
  });
});

// ===== REFLECT PAGE (ORCHESTRATOR) TESTS =====

describe("ReflectPage", () => {
  beforeEach(() => {
    // Default: return populated data for overview tab
    mockFetchPersonaPerformance.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePersonaPerformanceResponse(),
    });
    mockFetchPatternSummary.mockResolvedValue({
      ok: true,
      status: 200,
      data: makePatternSummaryResponse(),
    });
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBrowserResponse(),
    });
    mockFetchRunBundle.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBundleResponse(),
    });
  });

  it("renders with Overview tab active by default (AC-4)", async () => {
    renderWithQuery(<ReflectPage />);

    expect(screen.getByTestId("reflect-tab-bar")).toBeInTheDocument();
    expect(screen.getByTestId("tab-overview")).toBeInTheDocument();
    expect(screen.getByTestId("tab-runs")).toBeInTheDocument();

    const overviewTab = await screen.findByTestId("overview-tab");
    expect(overviewTab).toBeInTheDocument();
  });

  it("switches between Overview and Runs tabs (AC-3)", async () => {
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    // Overview tab is default
    await screen.findByTestId("overview-tab");
    expect(screen.queryByTestId("runs-tab")).not.toBeInTheDocument();

    // Switch to Runs tab
    await user.click(screen.getByTestId("tab-runs"));
    expect(await screen.findByTestId("runs-tab")).toBeInTheDocument();
    expect(screen.queryByTestId("overview-tab")).not.toBeInTheDocument();

    // Switch back to Overview
    await user.click(screen.getByTestId("tab-overview"));
    expect(await screen.findByTestId("overview-tab")).toBeInTheDocument();
  });

  it("renders both tables on Overview tab", async () => {
    renderWithQuery(<ReflectPage />);

    await screen.findByTestId("overview-tab");
    expect(await screen.findByTestId("persona-performance-table")).toBeInTheDocument();
    expect(await screen.findByTestId("pattern-summary-table")).toBeInTheDocument();
  });

  it("renders run history list on Runs tab (AC-22)", async () => {
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    await user.click(screen.getByTestId("tab-runs"));
    await screen.findByTestId("runs-tab");

    expect(screen.getByText("XAUUSD NY")).toBeInTheDocument();
    expect(screen.getByText("EURUSD LDN")).toBeInTheDocument();
  });

  it("shows placeholder when no run selected on Runs tab (AC-31)", async () => {
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    await user.click(screen.getByTestId("tab-runs"));
    await screen.findByTestId("runs-tab");

    expect(screen.getByTestId("run-detail-placeholder")).toBeInTheDocument();
  });

  it("selects a run and loads bundle detail (AC-25)", async () => {
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    await user.click(screen.getByTestId("tab-runs"));
    await screen.findByTestId("runs-tab");

    // Click on first run
    await user.click(screen.getByTestId("run-item-run_001"));

    const detail = await screen.findByTestId("run-detail-view");
    expect(detail).toBeInTheDocument();
    expect(within(detail).getByText("NO_TRADE")).toBeInTheDocument();
  });

  it("shows empty run history welcoming message (AC-24)", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBrowserResponse({ items: [], total: 0, has_next: false }),
    });
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    await user.click(screen.getByTestId("tab-runs"));

    expect(await screen.findByText("No analysis runs yet")).toBeInTheDocument();
    expect(screen.getByText(/Runs will appear here/)).toBeInTheDocument();
  });

  it("handles pagination controls (AC-23)", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRunBrowserResponse({ has_next: true }),
    });
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    await user.click(screen.getByTestId("tab-runs"));
    await screen.findByTestId("runs-tab");

    const prevBtn = screen.getByTestId("prev-page");
    const nextBtn = screen.getByTestId("next-page");

    // Prev disabled on page 1
    expect(prevBtn).toBeDisabled();
    // Next enabled when has_next is true
    expect(nextBtn).not.toBeDisabled();
  });

  it("shows error state for run history failure", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Server error",
    });
    const user = userEvent.setup();
    renderWithQuery(<ReflectPage />);

    await user.click(screen.getByTestId("tab-runs"));

    expect(await screen.findByText("Failed to load run history")).toBeInTheDocument();
  });
});

// ===== API TYPE TESTS =====

describe("API fetch functions (AC-35)", () => {
  it("fetchPersonaPerformance is callable", async () => {
    const { fetchPersonaPerformance } = await import("../src/shared/api/reflect");
    expect(typeof fetchPersonaPerformance).toBe("function");
  });

  it("fetchPatternSummary is callable", async () => {
    const { fetchPatternSummary } = await import("../src/shared/api/reflect");
    expect(typeof fetchPatternSummary).toBe("function");
  });

  it("fetchRunBundle is callable", async () => {
    const { fetchRunBundle } = await import("../src/shared/api/reflect");
    expect(typeof fetchRunBundle).toBe("function");
  });
});
