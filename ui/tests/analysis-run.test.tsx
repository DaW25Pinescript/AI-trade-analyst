// ---------------------------------------------------------------------------
// Analysis Run workspace tests.
//
// Coverage:
//   - State machine unit tests
//   - Adapter unit tests
//   - Submission panel tests
//   - Execution panel tests
//   - Verdict panel tests
//   - Usage accordion tests
//   - Run lifecycle integration tests
//   - Error handling tests
//   - Escalation tests
//   - Tab persistence tests
//   - Navigation/route tests
//   - End-to-end submission → verdict test
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";

// ---- State machine tests ----

import {
  createInitialState,
  transition,
  isValidTransition,
  toValidating,
  toSubmitting,
  toRunning,
  toCompleted,
  toFailed,
  toIdle,
  canSubmit,
  canReset,
  isTerminal,
  isRunning as isRunningFn,
  type RunState,
  type RunLifecycleState,
} from "../src/workspaces/analysis/state/runLifecycle";

describe("Run Lifecycle State Machine", () => {
  let initial: RunLifecycleState;

  beforeEach(() => {
    initial = createInitialState();
  });

  it("starts in idle state with null fields", () => {
    expect(initial.state).toBe("idle");
    expect(initial.run_id).toBeNull();
    expect(initial.request_id).toBeNull();
    expect(initial.error).toBeNull();
    expect(initial.modifier).toBeNull();
    expect(initial.startedAt).toBeNull();
    expect(initial.completedAt).toBeNull();
  });

  describe("valid transitions", () => {
    it("idle → validating", () => {
      const next = toValidating(initial);
      expect(next.state).toBe("validating");
    });

    it("validating → submitting", () => {
      const validating = toValidating(initial);
      const submitting = toSubmitting(validating);
      expect(submitting.state).toBe("submitting");
      expect(submitting.startedAt).toBeGreaterThan(0);
    });

    it("validating → idle (validation failure)", () => {
      const validating = toValidating(initial);
      const idle = toIdle(validating);
      expect(idle.state).toBe("idle");
    });

    it("submitting → running", () => {
      const submitting = toSubmitting(toValidating(initial));
      const running = toRunning(submitting, { run_id: "run-123" });
      expect(running.state).toBe("running");
      expect(running.run_id).toBe("run-123");
    });

    it("running → completed", () => {
      const running = toRunning(toSubmitting(toValidating(initial)));
      const completed = toCompleted(running, { run_id: "run-456" });
      expect(completed.state).toBe("completed");
      expect(completed.run_id).toBe("run-456");
      expect(completed.completedAt).toBeGreaterThan(0);
    });

    it("running → failed", () => {
      const running = toRunning(toSubmitting(toValidating(initial)));
      const failed = toFailed(running, { message: "timeout" });
      expect(failed.state).toBe("failed");
      expect(failed.error?.message).toBe("timeout");
      expect(failed.completedAt).toBeGreaterThan(0);
    });

    it("completed → idle (reset)", () => {
      const running = toRunning(toSubmitting(toValidating(initial)));
      const completed = toCompleted(running);
      const idle = toIdle(completed);
      expect(idle.state).toBe("idle");
      expect(idle.run_id).toBeNull();
    });

    it("failed → idle (reset)", () => {
      const running = toRunning(toSubmitting(toValidating(initial)));
      const failed = toFailed(running, { message: "error" });
      const idle = toIdle(failed);
      expect(idle.state).toBe("idle");
      expect(idle.error).toBeNull();
    });
  });

  describe("invalid transitions", () => {
    it("rejects idle → running", () => {
      expect(() => transition(initial, "running")).toThrow(
        "Invalid run lifecycle transition: idle → running",
      );
    });

    it("rejects idle → completed", () => {
      expect(() => transition(initial, "completed")).toThrow();
    });

    it("rejects completed → running", () => {
      const running = toRunning(toSubmitting(toValidating(initial)));
      const completed = toCompleted(running);
      expect(() => transition(completed, "running")).toThrow();
    });

    it("rejects running → submitting", () => {
      const running = toRunning(toSubmitting(toValidating(initial)));
      expect(() => transition(running, "submitting")).toThrow();
    });
  });

  describe("run_id preservation", () => {
    it("preserves run_id across transitions", () => {
      const running = toRunning(toSubmitting(toValidating(initial)), {
        run_id: "r-999",
      });
      expect(running.run_id).toBe("r-999");
      const completed = toCompleted(running);
      expect(completed.run_id).toBe("r-999");
    });

    it("preserves run_id in failure state", () => {
      const running = toRunning(toSubmitting(toValidating(initial)), {
        run_id: "r-fail",
      });
      const failed = toFailed(running, { message: "err" });
      expect(failed.run_id).toBe("r-fail");
    });

    it("new run_id overrides existing", () => {
      const running = toRunning(toSubmitting(toValidating(initial)), {
        run_id: "r-1",
      });
      const completed = toCompleted(running, { run_id: "r-2" });
      expect(completed.run_id).toBe("r-2");
    });
  });

  describe("partial state exists in type", () => {
    it("partial is a valid RunState type", () => {
      const states: RunState[] = [
        "idle",
        "validating",
        "submitting",
        "running",
        "partial",
        "completed",
        "failed",
      ];
      expect(states).toContain("partial");
    });

    it("running → partial is a valid transition", () => {
      expect(isValidTransition("running", "partial")).toBe(true);
    });

    it("partial → completed is a valid transition", () => {
      expect(isValidTransition("partial", "completed")).toBe(true);
    });
  });

  describe("query helpers", () => {
    it("canSubmit is true only for idle", () => {
      expect(canSubmit("idle")).toBe(true);
      expect(canSubmit("running")).toBe(false);
      expect(canSubmit("completed")).toBe(false);
    });

    it("canReset is true for terminal states", () => {
      expect(canReset("completed")).toBe(true);
      expect(canReset("failed")).toBe(true);
      expect(canReset("running")).toBe(false);
    });

    it("isTerminal identifies completed and failed", () => {
      expect(isTerminal("completed")).toBe(true);
      expect(isTerminal("failed")).toBe(true);
      expect(isTerminal("running")).toBe(false);
    });

    it("isRunning identifies active states", () => {
      expect(isRunningFn("submitting")).toBe(true);
      expect(isRunningFn("running")).toBe(true);
      expect(isRunningFn("idle")).toBe(false);
    });
  });
});

// ---- Adapter tests ----

import {
  normalizeAnalysisResponse,
  normalizeVerdict,
  normalizeUsageSummary,
  normalizeError,
  deriveTabState,
  buildFormData,
} from "../src/workspaces/analysis/adapters/analysisAdapter";
import type {
  AnalysisResponse,
  FinalVerdict,
  UsageSummary,
} from "../src/workspaces/analysis/types";

describe("Analysis Adapter", () => {
  const mockVerdict: FinalVerdict = {
    final_bias: "bullish",
    decision: "ENTER_LONG",
    approved_setups: [
      {
        type: "FVG",
        entry_zone: "2050.00",
        stop: "2045.00",
        targets: ["2060.00", "2070.00"],
        rr_estimate: 3.0,
        confidence: 0.85,
        indicator_dependent: false,
      },
    ],
    no_trade_conditions: ["FOMC in 2h"],
    overall_confidence: 0.82,
    analyst_agreement_pct: 75,
    arbiter_notes: "Strong bullish bias across multiple analysts.",
    risk_override_applied: false,
  };

  const mockResponse: AnalysisResponse = {
    run_id: "run-abc-123",
    verdict: mockVerdict,
    ticket_draft: { source_run_id: "run-abc-123", rawAIReadBias: "bullish" },
    source_ticket_id: "ticket-1",
    usage_summary: {
      total_calls: 5,
      successful_calls: 5,
      failed_calls: 0,
      tokens: {
        prompt_tokens: 10000,
        completion_tokens: 3000,
        total_tokens: 13000,
      },
      total_cost_usd: 0.25,
    },
  };

  describe("normalizeAnalysisResponse", () => {
    it("maps response to view model", () => {
      const vm = normalizeAnalysisResponse(mockResponse);
      expect(vm.runId).toBe("run-abc-123");
      expect(vm.verdict).not.toBeNull();
      expect(vm.ticketDraft).not.toBeNull();
      expect(vm.sourceTicketId).toBe("ticket-1");
    });
  });

  describe("normalizeVerdict", () => {
    it("maps all fields at expert density", () => {
      const vm = normalizeVerdict(mockVerdict);
      expect(vm.finalBias).toBe("bullish");
      expect(vm.decision).toBe("ENTER_LONG");
      expect(vm.approvedSetups).toHaveLength(1);
      expect(vm.noTradeConditions).toEqual(["FOMC in 2h"]);
      expect(vm.overallConfidence).toBe(0.82);
      expect(vm.analystAgreementPct).toBe(75);
      expect(vm.arbiterNotes).toBe("Strong bullish bias across multiple analysts.");
    });

    it("provides safe defaults for missing fields", () => {
      const minimal = normalizeVerdict({} as FinalVerdict);
      expect(minimal.finalBias).toBe("unknown");
      expect(minimal.decision).toBe("UNKNOWN");
      expect(minimal.approvedSetups).toEqual([]);
      expect(minimal.overallConfidence).toBe(0);
    });
  });

  describe("normalizeUsageSummary", () => {
    it("maps available usage", () => {
      const vm = normalizeUsageSummary(mockResponse.usage_summary);
      expect(vm.available).toBe(true);
      expect(vm.artifactMissing).toBe(false);
      expect(vm.totalTokens).toBe(13000);
      expect(vm.totalCost).toBe(0.25);
    });

    it("handles null (empty-but-valid)", () => {
      const vm = normalizeUsageSummary(null);
      expect(vm.available).toBe(false);
      expect(vm.artifactMissing).toBe(true);
      expect(vm.totalTokens).toBeNull();
    });

    it("handles undefined", () => {
      const vm = normalizeUsageSummary(undefined);
      expect(vm.available).toBe(false);
      expect(vm.artifactMissing).toBe(true);
    });

    it("handles loading state", () => {
      const vm = normalizeUsageSummary(null, true);
      expect(vm.loading).toBe(true);
      expect(vm.artifactMissing).toBe(false);
    });

    it("handles empty usage object", () => {
      const vm = normalizeUsageSummary({} as UsageSummary);
      expect(vm.available).toBe(true);
      expect(vm.totalTokens).toBeNull();
      expect(vm.totalCost).toBeNull();
    });
  });

  describe("normalizeError", () => {
    it("handles string detail", () => {
      const vm = normalizeError("Something went wrong");
      expect(vm.message).toBe("Something went wrong");
      expect(vm.code).toBeNull();
      expect(vm.runId).toBeNull();
    });

    it("handles object detail with all fields", () => {
      const vm = normalizeError({
        message: "Rate limited",
        code: "RATE_LIMIT",
        request_id: "req-1",
        run_id: "run-1",
      });
      expect(vm.message).toBe("Rate limited");
      expect(vm.code).toBe("RATE_LIMIT");
      expect(vm.runId).toBe("run-1");
      expect(vm.requestId).toBe("req-1");
    });

    it("handles object detail with missing fields", () => {
      const vm = normalizeError({});
      expect(vm.message).toBe("Analysis failed");
      expect(vm.code).toBeNull();
    });
  });

  describe("deriveTabState", () => {
    it("idle: submission editable, verdict disabled", () => {
      const ts = deriveTabState(createInitialState());
      expect(ts.submissionReadOnly).toBe(false);
      expect(ts.verdictEnabled).toBe(false);
      expect(ts.verdictDisabledReason).toBe("Submit to see verdict");
    });

    it("running: submission locked, verdict disabled", () => {
      const running = toRunning(toSubmitting(toValidating(createInitialState())));
      const ts = deriveTabState(running);
      expect(ts.submissionReadOnly).toBe(true);
      expect(ts.verdictEnabled).toBe(false);
    });

    it("completed: submission locked, verdict enabled", () => {
      const running = toRunning(toSubmitting(toValidating(createInitialState())));
      const completed = toCompleted(running);
      const ts = deriveTabState(completed);
      expect(ts.submissionReadOnly).toBe(true);
      expect(ts.verdictEnabled).toBe(true);
      expect(ts.verdictDisabledReason).toBeNull();
    });

    it("failed: submission locked, verdict disabled with reason", () => {
      const running = toRunning(toSubmitting(toValidating(createInitialState())));
      const failed = toFailed(running, { message: "err" });
      const ts = deriveTabState(failed);
      expect(ts.submissionReadOnly).toBe(true);
      expect(ts.verdictEnabled).toBe(false);
      expect(ts.verdictDisabledReason).toBe("No verdict — run failed");
    });
  });

  describe("buildFormData", () => {
    it("creates FormData with correct field names", () => {
      const fd = buildFormData({
        instrument: "XAUUSD",
        session: "NY",
        timeframes: ["H4", "M15"],
        account_balance: 10000,
        min_rr: 2.0,
        max_risk_per_trade: 0.5,
        max_daily_risk: 2.0,
        no_trade_windows: ["FOMC"],
        market_regime: "trending",
        news_risk: "none_noted",
        open_positions: [],
        lens_ict_icc: true,
        lens_market_structure: true,
        lens_orderflow: false,
        lens_trendlines: false,
        lens_classical: false,
        lens_harmonic: false,
        lens_smt: false,
        lens_volume_profile: false,
        charts: {},
        enable_deliberation: false,
        triage_mode: false,
        smoke_mode: false,
      });

      expect(fd.get("instrument")).toBe("XAUUSD");
      expect(fd.get("session")).toBe("NY");
      expect(fd.get("timeframes")).toBe('["H4","M15"]');
      expect(fd.get("account_balance")).toBe("10000");
      expect(fd.get("min_rr")).toBe("2");
      expect(fd.get("lens_ict_icc")).toBe("true");
      expect(fd.get("lens_orderflow")).toBe("false");
      expect(fd.get("enable_deliberation")).toBe("false");
    });

    it("appends source_ticket_id when present", () => {
      const fd = buildFormData({
        instrument: "EURUSD",
        session: "London",
        timeframes: ["H4"],
        account_balance: 5000,
        min_rr: 2.0,
        max_risk_per_trade: 0.5,
        max_daily_risk: 2.0,
        no_trade_windows: [],
        market_regime: "unknown",
        news_risk: "none_noted",
        open_positions: [],
        lens_ict_icc: true,
        lens_market_structure: true,
        lens_orderflow: false,
        lens_trendlines: false,
        lens_classical: false,
        lens_harmonic: false,
        lens_smt: false,
        lens_volume_profile: false,
        charts: {},
        source_ticket_id: "TK-42",
        enable_deliberation: true,
        triage_mode: false,
        smoke_mode: false,
      });

      expect(fd.get("source_ticket_id")).toBe("TK-42");
      expect(fd.get("enable_deliberation")).toBe("true");
    });
  });
});

// ---- Component tests ----

// Mock the API module
vi.mock("../src/workspaces/analysis/api/analysisApi", () => ({
  submitAnalysis: vi.fn(),
  fetchRunUsage: vi.fn(),
}));

import { submitAnalysis, fetchRunUsage } from "../src/workspaces/analysis/api/analysisApi";
import { AnalysisRunPage } from "../src/workspaces/analysis/components/AnalysisRunPage";
import { ExecutionPanel } from "../src/workspaces/analysis/components/ExecutionPanel";
import { VerdictPanel } from "../src/workspaces/analysis/components/VerdictPanel";
import { UsageAccordion } from "../src/workspaces/analysis/components/UsageAccordion";
import { AnalysisActionBar } from "../src/workspaces/analysis/components/AnalysisActionBar";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderWithRouter(
  ui: React.ReactElement,
  { initialEntries = ["/analysis"] }: { initialEntries?: string[] } = {},
) {
  const qc = createQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/analysis" element={ui} />
          <Route path="/journey/:asset" element={<div>Journey Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ExecutionPanel", () => {
  it("renders idle state", () => {
    render(
      <ExecutionPanel
        lifecycle={createInitialState()}
        elapsedMs={0}
        error={null}
      />,
    );
    expect(
      screen.getByText("Configure and submit an analysis to begin"),
    ).toBeInTheDocument();
  });

  it("renders running state with spinner and elapsed time", () => {
    const running = toRunning(toSubmitting(toValidating(createInitialState())));
    render(
      <ExecutionPanel lifecycle={running} elapsedMs={15000} error={null} />,
    );
    expect(screen.getByTestId("run-spinner")).toBeInTheDocument();
    expect(screen.getByText("Analysis running...")).toBeInTheDocument();
    expect(screen.getByTestId("elapsed-time")).toHaveTextContent("15s");
  });

  it("renders completed state with run_id", () => {
    const running = toRunning(toSubmitting(toValidating(createInitialState())), {
      run_id: "run-done",
    });
    const completed = toCompleted(running);
    render(
      <ExecutionPanel lifecycle={completed} elapsedMs={30000} error={null} />,
    );
    expect(screen.getByText("Analysis complete")).toBeInTheDocument();
    expect(screen.getByTestId("completed-run-id")).toHaveTextContent("run-done");
  });

  it("renders failed state with error detail", () => {
    const running = toRunning(toSubmitting(toValidating(createInitialState())));
    const failed = toFailed(running, { message: "Server error" });
    render(
      <ExecutionPanel
        lifecycle={failed}
        elapsedMs={5000}
        error={{ message: "Server error", code: "500", runId: null, requestId: "req-1" }}
      />,
    );
    expect(screen.getByText("Analysis failed")).toBeInTheDocument();
    expect(screen.getByTestId("error-message")).toHaveTextContent("Server error");
  });

  it("preserves run_id in failed state", () => {
    const running = toRunning(toSubmitting(toValidating(createInitialState())), {
      run_id: "fail-run",
    });
    const failed = toFailed(running, { message: "err" });
    render(
      <ExecutionPanel lifecycle={failed} elapsedMs={0} error={null} />,
    );
    expect(screen.getByTestId("failed-run-id")).toHaveTextContent("fail-run");
  });
});

describe("VerdictPanel", () => {
  const verdict = normalizeVerdict({
    final_bias: "bearish",
    decision: "ENTER_SHORT",
    approved_setups: [
      {
        type: "Order Block",
        entry_zone: "1.1050",
        stop: "1.1080",
        targets: ["1.1000"],
        rr_estimate: 1.67,
        confidence: 0.7,
      },
    ],
    no_trade_conditions: ["NFP tomorrow"],
    overall_confidence: 0.65,
    analyst_agreement_pct: 60,
    arbiter_notes: "Moderate bearish signal.",
  });

  const emptyUsage = normalizeUsageSummary(null);

  it("renders full verdict at expert density", () => {
    render(
      <VerdictPanel
        verdict={verdict}
        ticketDraft={{ source_run_id: "run-1" }}
        usage={emptyUsage}
        disabled={false}
        disabledReason={null}
      />,
    );
    expect(screen.getByTestId("verdict-panel")).toBeInTheDocument();
    expect(screen.getByTestId("confidence-display")).toHaveTextContent("65%");
    expect(screen.getByTestId("agreement-display")).toHaveTextContent("60%");
    expect(screen.getByTestId("setup-0")).toBeInTheDocument();
    expect(screen.getByTestId("no-trade-0")).toHaveTextContent("NFP tomorrow");
    expect(screen.getByTestId("arbiter-notes")).toHaveTextContent(
      "Moderate bearish signal.",
    );
    expect(screen.getByTestId("ticket-draft")).toBeInTheDocument();
  });

  it("shows disabled state on failure", () => {
    render(
      <VerdictPanel
        verdict={null}
        ticketDraft={null}
        usage={emptyUsage}
        disabled={true}
        disabledReason="No verdict — run failed"
      />,
    );
    expect(screen.getByTestId("verdict-disabled")).toBeInTheDocument();
    expect(screen.getByText("No verdict — run failed")).toBeInTheDocument();
  });

  it("shows placeholder when not yet submitted", () => {
    render(
      <VerdictPanel
        verdict={null}
        ticketDraft={null}
        usage={emptyUsage}
        disabled={true}
        disabledReason="Submit to see verdict"
      />,
    );
    expect(screen.getByText("Submit to see verdict")).toBeInTheDocument();
  });
});

describe("UsageAccordion", () => {
  it("is closed by default", () => {
    const usage = normalizeUsageSummary({
      tokens: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
      total_cost_usd: 0.01,
    } as UsageSummary);
    render(<UsageAccordion usage={usage} />);
    expect(screen.queryByTestId("usage-content")).not.toBeInTheDocument();
  });

  it("opens on click and shows data", async () => {
    const user = userEvent.setup();
    const usage = normalizeUsageSummary({
      tokens: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
      total_cost_usd: 0.01,
      total_calls: 3,
      successful_calls: 3,
      failed_calls: 0,
    } as UsageSummary);
    render(<UsageAccordion usage={usage} />);
    await user.click(screen.getByTestId("usage-toggle"));
    expect(screen.getByTestId("usage-content")).toBeInTheDocument();
    expect(screen.getByTestId("usage-total-tokens")).toHaveTextContent("150");
    expect(screen.getByTestId("usage-cost")).toHaveTextContent("$0.0100");
  });

  it("shows unavailable message for artifact-missing", async () => {
    const user = userEvent.setup();
    const usage = normalizeUsageSummary(null);
    render(<UsageAccordion usage={usage} />);
    await user.click(screen.getByTestId("usage-toggle"));
    expect(screen.getByTestId("usage-unavailable")).toHaveTextContent(
      "Usage data unavailable",
    );
  });

  it("shows loading state", async () => {
    const user = userEvent.setup();
    const usage = normalizeUsageSummary(null, true);
    render(<UsageAccordion usage={usage} />);
    await user.click(screen.getByTestId("usage-toggle"));
    expect(screen.getByText("Loading usage data...")).toBeInTheDocument();
  });
});

describe("AnalysisActionBar", () => {
  it("shows nothing in idle state", () => {
    const { container } = render(
      <AnalysisActionBar runState="idle" onRetry={vi.fn()} onReset={vi.fn()} />,
    );
    expect(container.querySelector("[data-testid='action-bar']")).toBeNull();
  });

  it("shows retry on failed", () => {
    render(
      <AnalysisActionBar
        runState="failed"
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByTestId("retry-btn")).toBeInTheDocument();
    expect(screen.getByTestId("reset-btn")).toBeInTheDocument();
  });

  it("shows reset on completed", () => {
    render(
      <AnalysisActionBar
        runState="completed"
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("retry-btn")).not.toBeInTheDocument();
    expect(screen.getByTestId("reset-btn")).toBeInTheDocument();
  });

  it("shows running message during execution", () => {
    render(
      <AnalysisActionBar
        runState="running"
        onRetry={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByText("Analysis in progress...")).toBeInTheDocument();
  });
});

describe("AnalysisRunPage", () => {
  beforeEach(() => {
    vi.mocked(submitAnalysis).mockReset();
    vi.mocked(fetchRunUsage).mockReset();
  });

  it("renders with three tabs", () => {
    renderWithRouter(<AnalysisRunPage />);
    expect(screen.getByTestId("tab-submission")).toBeInTheDocument();
    expect(screen.getByTestId("tab-execution")).toBeInTheDocument();
    expect(screen.getByTestId("tab-verdict")).toBeInTheDocument();
  });

  it("starts on submission tab", () => {
    renderWithRouter(<AnalysisRunPage />);
    expect(screen.getByTestId("submission-panel")).toBeInTheDocument();
  });

  it("switches tabs on click", async () => {
    const user = userEvent.setup();
    renderWithRouter(<AnalysisRunPage />);

    await user.click(screen.getByTestId("tab-execution"));
    expect(screen.getByTestId("execution-panel")).toBeInTheDocument();

    await user.click(screen.getByTestId("tab-verdict"));
    expect(screen.getByTestId("verdict-disabled")).toBeInTheDocument();
  });

  it("shows header with Analysis Run title", () => {
    renderWithRouter(<AnalysisRunPage />);
    expect(screen.getByText("Analysis Run")).toBeInTheDocument();
  });

  it("shows validation error on empty instrument submit", async () => {
    const user = userEvent.setup();
    renderWithRouter(<AnalysisRunPage />);
    await user.click(screen.getByTestId("submit-analysis-btn"));
    expect(screen.getByTestId("error-instrument")).toHaveTextContent(
      "Instrument is required",
    );
  });
});

describe("Escalation: Journey → Analysis", () => {
  beforeEach(() => {
    vi.mocked(submitAnalysis).mockReset();
    vi.mocked(fetchRunUsage).mockReset();
  });

  it("pre-populates instrument from asset parameter", () => {
    renderWithRouter(<AnalysisRunPage />, {
      initialEntries: ["/analysis?asset=XAUUSD"],
    });
    const input = screen.getByTestId("input-instrument") as HTMLInputElement;
    expect(input.value).toBe("XAUUSD");
  });

  it("shows provenance breadcrumb when escalated", () => {
    renderWithRouter(<AnalysisRunPage />, {
      initialEntries: ["/analysis?asset=EURUSD"],
    });
    expect(screen.getByTestId("provenance-breadcrumb")).toHaveTextContent(
      "Escalated from Journey Studio",
    );
  });

  it("shows Return to Journey link when escalated", () => {
    renderWithRouter(<AnalysisRunPage />, {
      initialEntries: ["/analysis?asset=AAPL"],
    });
    expect(screen.getByTestId("return-to-journey")).toBeInTheDocument();
  });

  it("no provenance breadcrumb without asset", () => {
    renderWithRouter(<AnalysisRunPage />);
    expect(screen.queryByTestId("provenance-breadcrumb")).not.toBeInTheDocument();
    expect(screen.queryByTestId("return-to-journey")).not.toBeInTheDocument();
  });

  it("handles invalid asset gracefully — form usable", () => {
    renderWithRouter(<AnalysisRunPage />, {
      initialEntries: ["/analysis?asset="],
    });
    // No crash, form still usable
    expect(screen.getByTestId("submit-analysis-btn")).toBeInTheDocument();
  });
});

describe("Tab persistence", () => {
  beforeEach(() => {
    vi.mocked(submitAnalysis).mockReset();
    vi.mocked(fetchRunUsage).mockReset();
  });

  it("all tabs navigable after submission attempt", async () => {
    const user = userEvent.setup();
    renderWithRouter(<AnalysisRunPage />);

    // Navigate through all tabs
    await user.click(screen.getByTestId("tab-submission"));
    expect(screen.getByTestId("submission-panel")).toBeInTheDocument();

    await user.click(screen.getByTestId("tab-execution"));
    expect(screen.getByTestId("execution-panel")).toBeInTheDocument();

    await user.click(screen.getByTestId("tab-verdict"));
    // Verdict shows disabled state before submission
    expect(screen.getByTestId("verdict-disabled")).toBeInTheDocument();
  });
});

describe("End-to-end: submit → verdict", () => {
  const mockVerdictResponse: AnalysisResponse = {
    run_id: "e2e-run-1",
    verdict: {
      final_bias: "bullish",
      decision: "ENTER_LONG",
      approved_setups: [
        {
          type: "FVG",
          entry_zone: "2050",
          stop: "2045",
          targets: ["2060"],
          rr_estimate: 3.0,
          confidence: 0.9,
        },
      ],
      no_trade_conditions: [],
      overall_confidence: 0.88,
      analyst_agreement_pct: 80,
      arbiter_notes: "Strong consensus.",
    },
    ticket_draft: { source_run_id: "e2e-run-1" },
    usage_summary: {
      tokens: { prompt_tokens: 5000, completion_tokens: 2000, total_tokens: 7000 },
      total_cost_usd: 0.15,
      total_calls: 4,
      successful_calls: 4,
      failed_calls: 0,
    },
  };

  beforeEach(() => {
    vi.mocked(submitAnalysis).mockResolvedValue({
      ok: true,
      data: mockVerdictResponse,
      status: 200,
    });
    vi.mocked(fetchRunUsage).mockResolvedValue({
      ok: true,
      data: {
        run_id: "e2e-run-1",
        usage_summary: mockVerdictResponse.usage_summary!,
      },
      status: 200,
    });
  });

  it("submits, shows running, then displays verdict", async () => {
    const user = userEvent.setup();
    renderWithRouter(<AnalysisRunPage />);

    // Fill in instrument
    const instrumentInput = screen.getByTestId("input-instrument");
    await user.clear(instrumentInput);
    await user.type(instrumentInput, "XAUUSD");

    // Enable smoke mode to bypass chart requirement
    await user.click(screen.getByTestId("input-smoke-mode"));

    // Submit
    await user.click(screen.getByTestId("submit-analysis-btn"));

    // Should auto-switch to execution tab
    // Wait for API resolution
    await screen.findByText("Analysis complete");

    expect(screen.getByTestId("completed-run-id")).toHaveTextContent("e2e-run-1");

    // Navigate to verdict tab
    await user.click(screen.getByTestId("tab-verdict"));
    expect(screen.getByTestId("verdict-panel")).toBeInTheDocument();
    expect(screen.getByTestId("confidence-display")).toHaveTextContent("88%");
    expect(screen.getByTestId("agreement-display")).toHaveTextContent("80%");

    // Submission should be read-only
    await user.click(screen.getByTestId("tab-submission"));
    expect(
      screen.getByText("Submission locked — review what was submitted"),
    ).toBeInTheDocument();

    // Submit button should not be present
    expect(
      screen.queryByTestId("submit-analysis-btn"),
    ).not.toBeInTheDocument();
  });

  it("handles failed submission and preserves error details", async () => {
    vi.mocked(submitAnalysis).mockResolvedValue({
      ok: false,
      status: 500,
      detail: {
        message: "Internal server error",
        code: "INTERNAL",
        run_id: "fail-run-1",
        request_id: "req-fail-1",
      },
    });

    const user = userEvent.setup();
    renderWithRouter(<AnalysisRunPage />);

    await user.clear(screen.getByTestId("input-instrument"));
    await user.type(screen.getByTestId("input-instrument"), "GBPUSD");
    await user.click(screen.getByTestId("input-smoke-mode"));
    await user.click(screen.getByTestId("submit-analysis-btn"));

    // Wait for failed state
    await screen.findByText("Analysis failed");
    expect(screen.getByTestId("error-message")).toHaveTextContent(
      "Internal server error",
    );

    // Retry button visible
    expect(screen.getByTestId("retry-btn")).toBeInTheDocument();

    // Verdict tab shows disabled message
    await user.click(screen.getByTestId("tab-verdict"));
    expect(screen.getByText("No verdict — run failed")).toBeInTheDocument();
  });
});
