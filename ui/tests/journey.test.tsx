// ---------------------------------------------------------------------------
// Journey Studio workspace tests — PR-UI-4.
//
// Explicit assertions (no snapshots) covering:
//   - adapter unit tests (condition resolution, right rail, setups, view model)
//   - page state tests (loading, ready, empty, unavailable, stale, error)
//   - freeze lifecycle (draft → freeze → post-freeze read-only)
//   - 409 conflict handling
//   - Save Result gating
//   - conditional right rail panel presence/absence
//   - navigation continuity (Triage → Journey, no-asset fallback)
//   - route render
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { JourneyBootstrapResponse } from "../src/shared/api/journey";
import {
  resolveJourneyCondition,
  deriveRightRailPanels,
  mapSetups,
  buildJourneyWorkspaceViewModel,
} from "../src/workspaces/journey/adapters/journeyViewModel";

// ---- Mock API modules ----

const mockFetchBootstrap = vi.fn();
const mockSaveDraft = vi.fn();
const mockSaveDecision = vi.fn();
const mockSaveResult = vi.fn();

vi.mock("../src/shared/api/journey", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/journey")>();
  return {
    ...actual,
    fetchJourneyBootstrap: (...args: unknown[]) => mockFetchBootstrap(...args),
    saveJourneyDraft: (...args: unknown[]) => mockSaveDraft(...args),
    saveJourneyDecision: (...args: unknown[]) => mockSaveDecision(...args),
    saveJourneyResult: (...args: unknown[]) => mockSaveResult(...args),
  };
});

// Import after mock
import { JourneyStudioPage } from "../src/workspaces/journey/components/JourneyStudioPage";
import { JourneyStudioRoute } from "../src/workspaces/journey/routes/JourneyStudioRoute";

// ---- Test fixtures ----

function makeBootstrap(
  overrides?: Partial<JourneyBootstrapResponse>,
): JourneyBootstrapResponse {
  return {
    data_state: "live",
    instrument: "XAUUSD",
    generated_at: "2026-03-14T10:00:00Z",
    structure_digest: { trend: "bullish" },
    analyst_verdict: { verdict: "bullish", confidence: "high" },
    arbiter_decision: {
      final_bias: "bullish",
      decision: "ENTER_LONG",
      overall_confidence: 0.82,
      analyst_agreement_pct: 85,
      risk_override_applied: false,
      arbiter_notes: "Strong trend alignment",
      no_trade_conditions: [],
      approved_setups: [
        {
          type: "ICT OTE",
          entry_zone: "2340.50",
          stop: "2335.00",
          targets: ["2350.00", "2360.00"],
          rr_estimate: 2.5,
          confidence: 0.78,
        },
      ],
    },
    explanation: { summary: "Confluent bullish signals" },
    reasoning_summary: "Multiple timeframe alignment with ICT structure",
    ...overrides,
  };
}

function renderWithRoute(
  path: string,
  element: React.ReactElement,
  initialEntry: string,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path, element }],
    { initialEntries: [initialEntry] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function renderJourney(asset: string = "XAUUSD") {
  return renderWithRoute(
    "/journey/:asset",
    <JourneyStudioPage />,
    `/journey/${asset}`,
  );
}

// ===========================================================================
// Adapter unit tests
// ===========================================================================

describe("journeyViewModel adapter", () => {
  describe("resolveJourneyCondition", () => {
    it("returns 'loading' when loading", () => {
      expect(resolveJourneyCondition(null, true, false)).toBe("loading");
    });

    it("returns 'error' when error", () => {
      expect(resolveJourneyCondition(null, false, true)).toBe("error");
    });

    it("returns 'error' when data is null and not loading", () => {
      expect(resolveJourneyCondition(null, false, false)).toBe("error");
    });

    it("returns 'unavailable' when data_state is unavailable", () => {
      const data = makeBootstrap({ data_state: "unavailable" });
      expect(resolveJourneyCondition(data, false, false)).toBe("unavailable");
    });

    it("returns 'stale' when data_state is stale", () => {
      const data = makeBootstrap({ data_state: "stale" });
      expect(resolveJourneyCondition(data, false, false)).toBe("stale");
    });

    it("returns 'partial' when data_state is partial", () => {
      const data = makeBootstrap({ data_state: "partial" });
      expect(resolveJourneyCondition(data, false, false)).toBe("partial");
    });

    it("returns 'empty' when no meaningful content", () => {
      const data = makeBootstrap({
        analyst_verdict: undefined as unknown as JourneyBootstrapResponse["analyst_verdict"],
        arbiter_decision: undefined as unknown as JourneyBootstrapResponse["arbiter_decision"],
        reasoning_summary: null,
      });
      expect(resolveJourneyCondition(data, false, false)).toBe("empty");
    });

    it("returns 'ready' on live data with content", () => {
      const data = makeBootstrap();
      expect(resolveJourneyCondition(data, false, false)).toBe("ready");
    });
  });

  describe("deriveRightRailPanels", () => {
    it("returns allUnavailable when data is null", () => {
      const panels = deriveRightRailPanels(null);
      expect(panels.allUnavailable).toBe(true);
      expect(panels.showArbiterSummary).toBe(false);
      expect(panels.showExplanation).toBe(false);
      expect(panels.showSetups).toBe(false);
      expect(panels.showNoTradeWarning).toBe(false);
    });

    it("shows arbiter panel when arbiter_decision has data", () => {
      const data = makeBootstrap();
      const panels = deriveRightRailPanels(data);
      expect(panels.showArbiterSummary).toBe(true);
      expect(panels.allUnavailable).toBe(false);
    });

    it("shows setups panel when approved_setups has entries", () => {
      const data = makeBootstrap();
      const panels = deriveRightRailPanels(data);
      expect(panels.showSetups).toBe(true);
    });

    it("hides setups panel when no approved setups", () => {
      const data = makeBootstrap({
        arbiter_decision: {
          final_bias: "bullish",
          decision: "WAIT_FOR_CONFIRMATION",
          approved_setups: [],
        },
      });
      const panels = deriveRightRailPanels(data);
      expect(panels.showSetups).toBe(false);
    });

    it("shows no-trade panel when conditions exist", () => {
      const data = makeBootstrap({
        arbiter_decision: {
          final_bias: "neutral",
          decision: "NO_TRADE",
          no_trade_conditions: ["NFP release", "High spread"],
          approved_setups: [],
        },
      });
      const panels = deriveRightRailPanels(data);
      expect(panels.showNoTradeWarning).toBe(true);
    });

    it("shows explanation panel when reasoning_summary exists", () => {
      const data = makeBootstrap();
      const panels = deriveRightRailPanels(data);
      expect(panels.showExplanation).toBe(true);
    });

    it("hides explanation when neither explanation nor reasoning exists", () => {
      const data = makeBootstrap({
        explanation: {},
        reasoning_summary: null,
      });
      const panels = deriveRightRailPanels(data);
      expect(panels.showExplanation).toBe(false);
    });
  });

  describe("mapSetups", () => {
    it("maps approved setups correctly", () => {
      const result = mapSetups([
        {
          type: "ICT OTE",
          entry_zone: "2340",
          stop: "2335",
          targets: ["2350"],
          rr_estimate: 2.5,
          confidence: 0.78,
        },
      ]);
      expect(result).toHaveLength(1);
      expect(result[0].type).toBe("ICT OTE");
      expect(result[0].entryZone).toBe("2340");
      expect(result[0].rrEstimate).toBe(2.5);
    });

    it("returns empty array for undefined", () => {
      expect(mapSetups(undefined)).toEqual([]);
    });
  });

  describe("buildJourneyWorkspaceViewModel", () => {
    it("builds full view model on ready state", () => {
      const data = makeBootstrap();
      const vm = buildJourneyWorkspaceViewModel(data, false, false);
      expect(vm.condition).toBe("ready");
      expect(vm.instrument).toBe("XAUUSD");
      expect(vm.arbiterBias).toBe("bullish");
      expect(vm.arbiterDecision).toBe("ENTER_LONG");
      expect(vm.arbiterConfidence).toBe(0.82);
      expect(vm.analystAgreement).toBe(85);
      expect(vm.approvedSetups).toHaveLength(1);
      expect(vm.stage).toBe("explore");
      expect(vm.isFrozen).toBe(false);
      expect(vm.canSaveDraft).toBe(true);
      expect(vm.canFreeze).toBe(false); // must be in draft stage
      expect(vm.canSaveResult).toBe(false); // must be frozen
    });

    it("enables canFreeze in draft stage", () => {
      const data = makeBootstrap();
      const vm = buildJourneyWorkspaceViewModel(data, false, false, "draft");
      expect(vm.canFreeze).toBe(true);
      expect(vm.canSaveResult).toBe(false);
    });

    it("marks frozen state correctly", () => {
      const data = makeBootstrap();
      const vm = buildJourneyWorkspaceViewModel(
        data, false, false, "frozen", "snap-123",
      );
      expect(vm.isFrozen).toBe(true);
      expect(vm.frozenSnapshotId).toBe("snap-123");
      expect(vm.canSaveDraft).toBe(false);
      expect(vm.canFreeze).toBe(false);
      expect(vm.canSaveResult).toBe(true);
    });

    it("preserves form state", () => {
      const data = makeBootstrap();
      const vm = buildJourneyWorkspaceViewModel(
        data, false, false, "draft", null, null,
        { thesis: "my thesis", conviction: "High", notes: "some notes", userDecision: "ENTER_LONG" },
      );
      expect(vm.thesis).toBe("my thesis");
      expect(vm.conviction).toBe("High");
      expect(vm.notes).toBe("some notes");
      expect(vm.userDecision).toBe("ENTER_LONG");
    });

    it("handles loading state with empty defaults", () => {
      const vm = buildJourneyWorkspaceViewModel(null, true, false);
      expect(vm.condition).toBe("loading");
      expect(vm.instrument).toBe("");
      expect(vm.rightRail.allUnavailable).toBe(true);
    });

    it("disables actions on unavailable data", () => {
      const data = makeBootstrap({ data_state: "unavailable" });
      const vm = buildJourneyWorkspaceViewModel(data, false, false);
      expect(vm.condition).toBe("unavailable");
      expect(vm.canSaveDraft).toBe(false);
      expect(vm.canFreeze).toBe(false);
      expect(vm.canSaveResult).toBe(false);
    });
  });
});

// ===========================================================================
// Component integration tests
// ===========================================================================

describe("JourneyStudioPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state with skeleton", () => {
    mockFetchBootstrap.mockReturnValue(new Promise(() => {})); // never resolves

    renderJourney();

    expect(screen.getByText("Journey Studio")).toBeInTheDocument();
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });

  it("renders error state with retry button", async () => {
    mockFetchBootstrap.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Bootstrap not found",
    });

    renderJourney();

    expect(await screen.findByText("Failed to load journey context")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders unavailable state when data_state is unavailable", async () => {
    const data = makeBootstrap({ data_state: "unavailable" });
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    expect(await screen.findByText("Journey context unavailable")).toBeInTheDocument();
    expect(screen.getByText("Back to Triage")).toBeInTheDocument();
  });

  it("renders empty state when bootstrap has no content", async () => {
    const data = makeBootstrap({
      analyst_verdict: undefined as unknown as JourneyBootstrapResponse["analyst_verdict"],
      arbiter_decision: undefined as unknown as JourneyBootstrapResponse["arbiter_decision"],
      reasoning_summary: null,
    });
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    expect(await screen.findByText("No analysis context available")).toBeInTheDocument();
  });

  it("renders ready state with stage flow and right rail", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    // Header
    expect(await screen.findByText("Journey Studio")).toBeInTheDocument();
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();

    // Stage flow (wait for data to load)
    expect(await screen.findByTestId("stage-flow")).toBeInTheDocument();
    expect(screen.getByText("Explore Context")).toBeInTheDocument();
    expect(screen.getByText("Draft Thesis")).toBeInTheDocument();

    // Right rail panels
    expect(screen.getByTestId("panel-arbiter")).toBeInTheDocument();
    expect(screen.getByTestId("panel-setups")).toBeInTheDocument();
    expect(screen.getByTestId("panel-explanation")).toBeInTheDocument();
  });

  it("renders stale banner when data_state is stale", async () => {
    const data = makeBootstrap({ data_state: "stale" });
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    expect(await screen.findByText(/Bootstrap data may be outdated/)).toBeInTheDocument();
  });

  it("shows no-trade panel when no_trade_conditions present", async () => {
    const data = makeBootstrap({
      arbiter_decision: {
        final_bias: "neutral",
        decision: "NO_TRADE",
        no_trade_conditions: ["NFP release", "FOMC"],
        approved_setups: [],
      },
    });
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    expect(await screen.findByTestId("panel-no-trade")).toBeInTheDocument();
    expect(screen.getByText("NFP release")).toBeInTheDocument();
    expect(screen.getByText("FOMC")).toBeInTheDocument();
  });

  it("shows rail-unavailable when bootstrap has no panels", async () => {
    const data = makeBootstrap({
      arbiter_decision: {} as JourneyBootstrapResponse["arbiter_decision"],
      explanation: {},
      reasoning_summary: null,
    });
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    expect(await screen.findByTestId("rail-unavailable")).toBeInTheDocument();
  });

  it("advances from explore to draft stage", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });
    const user = userEvent.setup();

    renderJourney();

    const beginDraft = await screen.findByTestId("advance-to-draft");
    await user.click(beginDraft);

    // Draft stage should now be active with form inputs
    expect(screen.getByTestId("thesis-input")).toBeInTheDocument();
    expect(screen.getByTestId("decision-select")).toBeInTheDocument();
    expect(screen.getByTestId("conviction-select")).toBeInTheDocument();
    expect(screen.getByTestId("notes-input")).toBeInTheDocument();
  });

  it("Save Result button is disabled before freeze", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    const saveResult = await screen.findByTestId("save-result-btn");
    expect(saveResult).toBeDisabled();
    expect(saveResult).toHaveAttribute("title", "Only available after freeze succeeds");
  });

  it("Freeze button is disabled in explore stage", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    const freezeBtn = await screen.findByTestId("freeze-btn");
    expect(freezeBtn).toBeDisabled();
  });

  it("Freeze button is enabled in draft stage", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });
    const user = userEvent.setup();

    renderJourney();

    // Advance to draft
    const beginDraft = await screen.findByTestId("advance-to-draft");
    await user.click(beginDraft);

    const freezeBtn = screen.getByTestId("freeze-btn");
    expect(freezeBtn).not.toBeDisabled();
  });

  it("saves draft successfully", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });
    mockSaveDraft.mockResolvedValue({
      ok: true,
      data: { success: true, journey_id: "j-123", saved_at: "2026-03-14T10:05:00Z", path: "/tmp/j.json" },
      status: 200,
    });
    const user = userEvent.setup();

    renderJourney();

    // Advance to draft
    const beginDraft = await screen.findByTestId("advance-to-draft");
    await user.click(beginDraft);

    // Fill form
    await user.type(screen.getByTestId("thesis-input"), "Test thesis");

    // Save draft
    const saveDraftBtn = screen.getByTestId("save-draft-btn");
    await user.click(saveDraftBtn);

    expect(mockSaveDraft).toHaveBeenCalledTimes(1);
  });

  it("freezes decision and transitions to frozen state", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });
    mockSaveDecision.mockResolvedValue({
      ok: true,
      data: { success: true, snapshot_id: "XAUUSD-1710410000000", saved_at: "2026-03-14T10:10:00Z", path: "/tmp/d.json" },
      status: 200,
    });
    const user = userEvent.setup();

    renderJourney();

    // Advance to draft
    const beginDraft = await screen.findByTestId("advance-to-draft");
    await user.click(beginDraft);

    // Freeze
    const freezeBtn = screen.getByTestId("freeze-btn");
    await user.click(freezeBtn);

    // After freeze, stage pill should show Frozen
    expect(await screen.findByText("Frozen")).toBeInTheDocument();

    // Save Draft and Freeze buttons should disappear
    expect(screen.queryByTestId("save-draft-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("freeze-btn")).not.toBeInTheDocument();

    // Save Result should now be enabled
    const saveResultBtn = screen.getByTestId("save-result-btn");
    expect(saveResultBtn).not.toBeDisabled();
  });

  it("shows conflict error on 409 during freeze", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });
    mockSaveDecision.mockResolvedValue({
      ok: false,
      status: 409,
      detail: "Duplicate snapshot_id",
    });
    const user = userEvent.setup();

    renderJourney();

    // Advance to draft
    const beginDraft = await screen.findByTestId("advance-to-draft");
    await user.click(beginDraft);

    // Attempt freeze
    const freezeBtn = screen.getByTestId("freeze-btn");
    await user.click(freezeBtn);

    // Should show conflict-specific error
    const error = await screen.findByTestId("freeze-error");
    expect(error).toBeInTheDocument();
    expect(error.textContent).toContain("Conflict");
  });

  it("shows generic error on non-409 freeze failure", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });
    mockSaveDecision.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "Internal error",
    });
    const user = userEvent.setup();

    renderJourney();

    const beginDraft = await screen.findByTestId("advance-to-draft");
    await user.click(beginDraft);

    const freezeBtn = screen.getByTestId("freeze-btn");
    await user.click(freezeBtn);

    const error = await screen.findByTestId("freeze-error");
    expect(error.textContent).toContain("Freeze failed");
    expect(error.textContent).not.toContain("Conflict");
  });
});

// ===========================================================================
// Navigation continuity tests
// ===========================================================================

describe("Journey navigation continuity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders no-asset fallback when route has no asset", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const router = createMemoryRouter(
      [{ path: "/journey", element: <JourneyStudioPage /> }],
      { initialEntries: ["/journey"] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(screen.getByText("No asset selected")).toBeInTheDocument();
    expect(screen.getByText(/Select an asset from the Triage Board/)).toBeInTheDocument();
  });

  it("fetches bootstrap for route asset parameter", () => {
    mockFetchBootstrap.mockReturnValue(new Promise(() => {}));

    renderJourney("NAS100");

    expect(screen.getByText("NAS100")).toBeInTheDocument();
    expect(mockFetchBootstrap).toHaveBeenCalledWith("NAS100");
  });

  it("Back to Triage link is present in ready state", async () => {
    const data = makeBootstrap();
    mockFetchBootstrap.mockResolvedValue({ ok: true, data, status: 200 });

    renderJourney();

    expect(await screen.findByText("Back to Triage")).toBeInTheDocument();
  });
});

// ===========================================================================
// Route integration test
// ===========================================================================

describe("JourneyStudioRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the journey workspace at /journey/:asset route", () => {
    mockFetchBootstrap.mockReturnValue(new Promise(() => {}));

    renderWithRoute(
      "/journey/:asset",
      <JourneyStudioRoute />,
      "/journey/XAUUSD",
    );

    expect(screen.getByText("Journey Studio")).toBeInTheDocument();
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
  });
});
