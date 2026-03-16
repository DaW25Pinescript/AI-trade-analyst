// ---------------------------------------------------------------------------
// Run Browser tests — PR-RUN-1.
//
// Covers AC-21 through AC-29 from docs/specs/PR_RUN_1_SPEC.md §7.
// Deterministic — no live pipeline dependency.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { RunBrowserResponse } from "../src/shared/api/runs";

// ---- Mock API ----

const mockFetchRuns = vi.fn();
const mockFetchRoster = vi.fn();
const mockFetchHealth = vi.fn();
const mockFetchTrace = vi.fn();
const mockFetchDetail = vi.fn();

vi.mock("../src/shared/api/runs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/runs")>();
  return {
    ...actual,
    fetchRuns: (...args: unknown[]) => mockFetchRuns(...args),
  };
});

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

// Import after mocks
import { RunBrowserPanel } from "../src/workspaces/ops/components/RunBrowserPanel";
import { AgentOpsPage } from "../src/workspaces/ops/components/AgentOpsPage";

// ---- Test fixtures ----

function makeBrowserResponse(
  overrides?: Partial<RunBrowserResponse>,
): RunBrowserResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-14T12:00:00Z",
    data_state: "live",
    items: [
      {
        run_id: "run_001",
        timestamp: "2026-03-14T11:00:00Z",
        instrument: "XAUUSD",
        session: "NY",
        final_decision: "BUY",
        run_status: "completed",
        trace_available: true,
      },
      {
        run_id: "run_002",
        timestamp: "2026-03-14T10:00:00Z",
        instrument: "EURUSD",
        session: "LDN",
        final_decision: "NO_TRADE",
        run_status: "completed",
        trace_available: true,
      },
      {
        run_id: "run_003",
        timestamp: "2026-03-14T09:00:00Z",
        instrument: "XAUUSD",
        session: "ASIA",
        final_decision: null,
        run_status: "partial",
        trace_available: true,
      },
      {
        run_id: "run_004",
        timestamp: "2026-03-14T08:00:00Z",
        instrument: "GBPJPY",
        session: "NY",
        final_decision: null,
        run_status: "failed",
        trace_available: false,
      },
    ],
    page: 1,
    page_size: 20,
    total: 4,
    has_next: false,
    ...overrides,
  };
}

function makeRosterResponse() {
  return {
    ok: true as const,
    status: 200,
    data: {
      version: "2026.03",
      generated_at: "2026-03-14T12:00:00Z",
      data_state: "live" as const,
      governance_layer: [
        {
          id: "arbiter",
          display_name: "ARBITER",
          type: "arbiter" as const,
          role: "Final Decision Maker",
          capabilities: ["SYNTHESIS"],
          supports_verdict: true,
          initials: "AR",
          visual_family: "governance" as const,
          orb_color: "teal" as const,
        },
      ],
      officer_layer: [],
      departments: {
        TECHNICAL_ANALYSIS: [],
        RISK_CHALLENGE: [],
        REVIEW_GOVERNANCE: [],
        INFRA_HEALTH: [],
      },
      relationships: [],
    },
  };
}

function makeHealthResponse() {
  return {
    ok: true as const,
    status: 200,
    data: {
      version: "2026.03",
      generated_at: "2026-03-14T12:00:00Z",
      data_state: "live" as const,
      entities: [
        {
          entity_id: "arbiter",
          run_state: "completed" as const,
          health_state: "live" as const,
        },
      ],
    },
  };
}

// ---- Render helpers ----

function renderPanel(onSelectRun = vi.fn()) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={qc}>
      <RunBrowserPanel onSelectRun={onSelectRun} />
    </QueryClientProvider>,
  );

  return { onSelectRun };
}

function renderOpsPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={qc}>
      <AgentOpsPage />
    </QueryClientProvider>,
  );
}

// ---- Tests ----

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchRoster.mockResolvedValue(makeRosterResponse());
  mockFetchHealth.mockResolvedValue(makeHealthResponse());
});

// AC-21: browser panel renders
describe("RunBrowserPanel — renders list", () => {
  it("renders run items from API response", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    renderPanel();

    const rows = await screen.findAllByTestId("run-browser-row");
    expect(rows).toHaveLength(4);
    expect(rows[0].textContent).toContain("XAUUSD");
    expect(rows[0].textContent).toContain("NY");
    expect(rows[0].textContent).toContain("BUY");
  });

  it("shows run_status for each row", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    renderPanel();

    const rows = await screen.findAllByTestId("run-browser-row");
    expect(rows[0].textContent).toContain("OK");
    expect(rows[2].textContent).toContain("Partial");
    expect(rows[3].textContent).toContain("Failed");
  });
});

// AC-22: click-to-load
describe("RunBrowserPanel — click-to-load", () => {
  it("clicking a row triggers trace load for that run_id", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    const { onSelectRun } = renderPanel();
    const user = userEvent.setup();

    const rows = await screen.findAllByTestId("run-browser-row");
    await user.click(rows[0]);

    expect(onSelectRun).toHaveBeenCalledWith("run_001", "XAUUSD");
  });
});

// AC-23: trace_available gating
describe("RunBrowserPanel — trace_available gating", () => {
  it("rows with trace_available=false are disabled", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    renderPanel();

    const rows = await screen.findAllByTestId("run-browser-row");
    // run_004 has trace_available = false
    expect(rows[3]).toBeDisabled();
    // run_001 has trace_available = true
    expect(rows[0]).not.toBeDisabled();
  });

  it("clicking a disabled row does not call onSelectRun", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    const { onSelectRun } = renderPanel();
    const user = userEvent.setup();

    const rows = await screen.findAllByTestId("run-browser-row");
    await user.click(rows[3]);

    expect(onSelectRun).not.toHaveBeenCalled();
  });
});

// AC-24: filter controls
describe("RunBrowserPanel — filter controls", () => {
  it("instrument and session filter controls are rendered", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    renderPanel();

    await screen.findByTestId("run-browser-filters");
    expect(screen.getByTestId("instrument-filter")).toBeDefined();
    expect(screen.getByTestId("session-filter")).toBeDefined();
  });

  it("changing instrument filter re-fetches", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    renderPanel();
    const user = userEvent.setup();

    await screen.findByTestId("instrument-filter");
    const instFilter = screen.getByTestId("instrument-filter");
    await user.selectOptions(instFilter, "XAUUSD");

    // Should have been called at least twice (initial + filter change)
    expect(mockFetchRuns.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

// AC-25: pagination
describe("RunBrowserPanel — pagination", () => {
  it("next/prev controls rendered", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse({ has_next: true }),
    });

    renderPanel();

    await screen.findByTestId("run-browser-pagination");
    expect(screen.getByTestId("pagination-prev")).toBeDefined();
    expect(screen.getByTestId("pagination-next")).toBeDefined();
  });

  it("next disabled when has_next is false", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse({ has_next: false }),
    });

    renderPanel();

    const nextBtn = await screen.findByTestId("pagination-next");
    expect(nextBtn).toBeDisabled();
  });

  it("prev disabled on page 1", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse({ page: 1 }),
    });

    renderPanel();

    const prevBtn = await screen.findByTestId("pagination-prev");
    expect(prevBtn).toBeDisabled();
  });
});

// AC-26: empty state
describe("RunBrowserPanel — empty state", () => {
  it("zero runs displays a welcoming empty state", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse({ items: [], total: 0 }),
    });

    renderPanel();

    const empty = await screen.findByTestId("run-browser-empty");
    expect(empty.textContent).toContain("No analysis runs found");
  });
});

// AC-27: loading state
describe("RunBrowserPanel — loading state", () => {
  it("loading skeleton shows while fetch is in-flight", async () => {
    // Never resolve to keep it loading
    mockFetchRuns.mockReturnValue(new Promise(() => {}));

    renderPanel();

    expect(screen.getByTestId("run-browser-loading")).toBeDefined();
  });
});

// AC-28: error state
describe("RunBrowserPanel — error state", () => {
  it("API error renders ErrorState component with retry", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Server error",
    });

    renderPanel();

    const errorEl = await screen.findByTestId("run-browser-error");
    expect(errorEl.textContent).toContain("Failed to load runs");
  });
});

// AC-29: paste-field retained in Agent Ops page
describe("AgentOpsPage — paste-field retained", () => {
  it("RunSelector paste-field remains in Run mode alongside browser panel", async () => {
    mockFetchRuns.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeBrowserResponse(),
    });

    renderOpsPage();
    const user = userEvent.setup();

    // Wait for roster to load, switch to Run mode
    await screen.findByText("Agent Operations");
    const runBtn = screen.getByRole("button", { name: "Run" });
    await user.click(runBtn);

    // Both browser panel and paste-field should be visible
    await screen.findByTestId("run-browser-panel");
    expect(screen.getByTestId("run-selector")).toBeDefined();
    expect(screen.getByTestId("run-id-input")).toBeDefined();
  });
});
