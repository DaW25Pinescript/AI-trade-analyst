// ---------------------------------------------------------------------------
// Agent Operations workspace tests — PR-OPS-3 + PR-OPS-5a + PR-OPS-5b.
//
// Explicit assertions (no snapshots) covering:
//   - healthy render
//   - degraded health state
//   - fresh-start empty health state
//   - roster error state
//   - entity selection detail behavior
//   - join safety / unknown health-only item ignored
//   - route render
//   - PR-OPS-5a: Health mode activation, data_state banners,
//     OpsErrorEnvelope parsing, typed adapters, mode switching
//   - PR-OPS-5b: Run mode (trace, stages, participants, edges, arbiter,
//     partial run, null arbiter, 404, stale), Detail sidebar (all 4
//     entity_type variants, 404, stale, unavailable health, dependencies,
//     recent participation, run navigation)
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type {
  AgentRosterResponse,
  AgentHealthSnapshotResponse,
  AgentHealthItem,
  AgentDetailResponse,
  AgentTraceResponse,
} from "../src/shared/api/ops";
import { parseOpsErrorEnvelope } from "../src/shared/api/ops";
import {
  buildOpsWorkspaceViewModel,
  resolveOpsCondition,
  mapEntityViewModel,
} from "../src/workspaces/ops/adapters/opsViewModel";

// ---- Mock API modules ----

const mockFetchRoster = vi.fn();
const mockFetchHealth = vi.fn();
const mockFetchDetail = vi.fn();
const mockFetchTrace = vi.fn();
const mockFetchRuns = vi.fn();

vi.mock("../src/shared/api/ops", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/ops")>();
  return {
    ...actual,
    fetchAgentRoster: (...args: unknown[]) => mockFetchRoster(...args),
    fetchAgentHealth: (...args: unknown[]) => mockFetchHealth(...args),
    fetchAgentDetail: (...args: unknown[]) => mockFetchDetail(...args),
    fetchAgentTrace: (...args: unknown[]) => mockFetchTrace(...args),
  };
});

vi.mock("../src/shared/api/runs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/runs")>();
  return {
    ...actual,
    fetchRuns: (...args: unknown[]) => mockFetchRuns(...args),
  };
});

// Import after mock
import { AgentOpsPage } from "../src/workspaces/ops/components/AgentOpsPage";
import { AgentOpsRoute } from "../src/workspaces/ops/routes/AgentOpsRoute";

// ---- Test fixtures ----

function makeRoster(overrides?: Partial<AgentRosterResponse>): AgentRosterResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-13T10:00:00Z",
    data_state: "live",
    governance_layer: [
      {
        id: "arbiter",
        display_name: "ARBITER",
        type: "arbiter",
        role: "Final Decision Maker",
        capabilities: ["SYNTHESIS", "OVERRIDE"],
        supports_verdict: true,
        initials: "AR",
        visual_family: "governance",
        orb_color: "teal",
      },
      {
        id: "senate",
        display_name: "SENATE",
        type: "subsystem",
        role: "Governance Synthesis",
        capabilities: ["VOTE"],
        supports_verdict: true,
        initials: "SN",
        visual_family: "governance",
        orb_color: "teal",
      },
    ],
    officer_layer: [
      {
        id: "mdo",
        display_name: "MARKET DATA OFFICER",
        type: "officer",
        role: "Market Data Officer",
        capabilities: ["DATA_FEED"],
        supports_verdict: false,
        initials: "MD",
        visual_family: "officer",
        orb_color: "teal",
      },
    ],
    departments: {
      TECHNICAL_ANALYSIS: [
        {
          id: "default-analyst",
          display_name: "DEFAULT ANALYST",
          type: "persona",
          department: "TECHNICAL_ANALYSIS",
          role: "Senior Analyst",
          capabilities: ["DIRECTIONAL", "BIAS"],
          supports_verdict: true,
          initials: "DA",
          visual_family: "technical",
          orb_color: "teal",
        },
      ],
      RISK_CHALLENGE: [
        {
          id: "risk-challenger",
          display_name: "RISK CHALLENGER",
          type: "persona",
          department: "RISK_CHALLENGE",
          role: "Risk Challenger",
          capabilities: ["CHALLENGE"],
          supports_verdict: false,
          initials: "RC",
          visual_family: "risk",
          orb_color: "amber",
        },
      ],
      REVIEW_GOVERNANCE: [
        {
          id: "reviewer",
          display_name: "REVIEWER",
          type: "persona",
          department: "REVIEW_GOVERNANCE",
          role: "Review Analyst",
          capabilities: ["REVIEW"],
          supports_verdict: false,
          initials: "RV",
          visual_family: "review",
          orb_color: "teal",
        },
      ],
      INFRA_HEALTH: [
        {
          id: "infra-monitor",
          display_name: "INFRA MONITOR",
          type: "subsystem",
          department: "INFRA_HEALTH",
          role: "Infrastructure Monitor",
          capabilities: ["MONITOR"],
          supports_verdict: false,
          initials: "IM",
          visual_family: "infra",
          orb_color: "teal",
        },
      ],
    },
    relationships: [
      { from: "arbiter", to: "senate", type: "synthesizes" },
      { from: "mdo", to: "default-analyst", type: "feeds" },
    ],
    ...overrides,
  };
}

function makeHealth(
  entities?: AgentHealthItem[],
  overrides?: Partial<AgentHealthSnapshotResponse>,
): AgentHealthSnapshotResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-13T10:00:00Z",
    data_state: "live",
    entities: entities ?? [
      {
        entity_id: "arbiter",
        run_state: "completed",
        health_state: "live",
        last_active_at: "2026-03-13T09:55:00Z",
        health_summary: "All systems operational",
      },
      {
        entity_id: "senate",
        run_state: "idle",
        health_state: "live",
      },
      {
        entity_id: "mdo",
        run_state: "completed",
        health_state: "live",
      },
      {
        entity_id: "default-analyst",
        run_state: "completed",
        health_state: "live",
      },
      {
        entity_id: "risk-challenger",
        run_state: "idle",
        health_state: "degraded",
        health_summary: "Dependency stale",
      },
      {
        entity_id: "reviewer",
        run_state: "idle",
        health_state: "live",
      },
      {
        entity_id: "infra-monitor",
        run_state: "running",
        health_state: "live",
      },
    ],
    ...overrides,
  };
}

function makeDetail(
  entityId: string,
  entityType: "persona" | "officer" | "arbiter" | "subsystem" = "arbiter",
  overrides?: Partial<AgentDetailResponse>,
): AgentDetailResponse {
  const base: AgentDetailResponse = {
    version: "2026.03",
    generated_at: "2026-03-15T10:00:00Z",
    data_state: "live",
    entity_id: entityId,
    entity_type: entityType,
    display_name: entityId.toUpperCase(),
    department: null,
    identity: {
      purpose: "Test purpose",
      role: "Test role",
      visual_family: "governance",
      capabilities: ["CAP1"],
      responsibilities: ["RESP1"],
      initials: "XX",
    },
    status: {
      run_state: "completed",
      health_state: "live",
      last_active_at: "2026-03-15T09:00:00Z",
      last_run_id: "run-001",
      health_summary: "All good",
    },
    dependencies: [],
    recent_participation: [],
    recent_warnings: [],
    type_specific: entityType === "persona"
      ? { variant: "persona" as const, analysis_focus: ["focus1"], verdict_style: "directional", department_role: "analyst", typical_outputs: ["output1"] }
      : entityType === "officer"
        ? { variant: "officer" as const, officer_domain: "market_data", data_sources: ["src1"], monitored_surfaces: ["surf1"], update_cadence: "1m" }
        : entityType === "arbiter"
          ? { variant: "arbiter" as const, synthesis_method: "weighted", veto_gates: ["gate1"], quorum_rule: "majority", override_capable: true, policy_summary: "Policy text" }
          : { variant: "subsystem" as const, subsystem_type: "monitor", monitored_resources: ["res1"], health_check_method: "ping", runtime_role: "monitor" },
  };
  return { ...base, ...overrides } as AgentDetailResponse;
}

function makeTrace(overrides?: Partial<AgentTraceResponse>): AgentTraceResponse {
  return {
    version: "2026.03",
    generated_at: "2026-03-15T10:00:00Z",
    data_state: "live",
    run_id: "run-001",
    summary: {
      instrument: "EURUSD",
      session: "session-001",
      timeframes: ["1H", "4H"],
      duration_ms: 5432,
      completed_at: "2026-03-15T09:55:00Z",
      final_verdict: "bullish",
      final_confidence: 0.82,
    },
    stages: [
      { stage: "validate_input", status: "completed", order: 0, duration_ms: 100 },
      { stage: "macro_context", status: "completed", order: 1, duration_ms: 800 },
      { stage: "analyst_execution", status: "completed", order: 2, duration_ms: 3000 },
      { stage: "arbiter", status: "completed", order: 3, duration_ms: 500 },
      { stage: "logging", status: "completed", order: 4, duration_ms: 32 },
    ],
    participants: [
      {
        entity_id: "default-analyst",
        display_name: "DEFAULT ANALYST",
        role: "Senior Analyst",
        participation_status: "active",
        contribution: {
          summary: "Bullish bias detected",
          stance: "bullish",
          confidence: 0.85,
          was_overridden: false,
          override_reason: null,
        },
      },
      {
        entity_id: "risk-challenger",
        display_name: "RISK CHALLENGER",
        role: "Risk Challenger",
        participation_status: "active",
        contribution: {
          summary: "Challenged bias",
          stance: "bearish",
          confidence: 0.6,
          was_overridden: true,
          override_reason: "Arbiter override",
        },
      },
    ],
    edges: [
      { from: "default-analyst", to: "arbiter", type: "supports", summary: "Supports verdict" },
      { from: "risk-challenger", to: "arbiter", type: "challenges", summary: null },
    ],
    arbiter_summary: {
      verdict: "bullish",
      confidence: 0.82,
      method: "weighted_synthesis",
      override_applied: true,
      dissent_summary: "Risk challenger dissented with bearish view",
    },
    artifacts: [
      { name: "run_record.json", path: "runs/run-001/run_record.json", type: "record" },
    ],
    ...overrides,
  };
}

function renderWithRouter(element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(
    [{ path: "/", element }],
    { initialEntries: ["/"] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// ---- Adapter unit tests ----

describe("opsViewModel adapter", () => {
  const roster = makeRoster();
  const health = makeHealth();

  it("resolves 'loading' when roster is loading", () => {
    expect(resolveOpsCondition(null, null, true, true, false, false)).toBe("loading");
  });

  it("resolves 'error' when roster fails", () => {
    expect(resolveOpsCondition(null, null, false, false, true, false)).toBe("error");
  });

  it("resolves 'degraded' when health fails", () => {
    expect(resolveOpsCondition(roster, null, false, false, false, true)).toBe("degraded");
  });

  it("resolves 'degraded' when health data_state is unavailable", () => {
    const unavailableHealth = makeHealth([], { data_state: "unavailable" });
    expect(resolveOpsCondition(roster, unavailableHealth, false, false, false, false)).toBe("degraded");
  });

  it("resolves 'empty-health' when health entities is empty", () => {
    const emptyHealth = makeHealth([]);
    expect(resolveOpsCondition(roster, emptyHealth, false, false, false, false)).toBe("empty-health");
  });

  it("resolves 'ready' on healthy success", () => {
    expect(resolveOpsCondition(roster, health, false, false, false, false)).toBe("ready");
  });

  it("builds full view model with correct entity count", () => {
    const vm = buildOpsWorkspaceViewModel(roster, health, false, false, false, false);
    expect(vm.condition).toBe("ready");
    expect(vm.entityCount).toBe(7);
    expect(vm.governanceLayer).toHaveLength(2);
    expect(vm.officerLayer).toHaveLength(1);
    expect(vm.departments).toHaveLength(4);
  });

  it("counts healthy and degraded entities correctly", () => {
    const vm = buildOpsWorkspaceViewModel(roster, health, false, false, false, false);
    expect(vm.healthyCount).toBe(6);
    expect(vm.degradedCount).toBe(1); // risk-challenger
    expect(vm.unavailableCount).toBe(0);
  });

  it("marks missing-health roster entities as hasHealth=false", () => {
    const partialHealth = makeHealth([
      { entity_id: "arbiter", run_state: "idle", health_state: "live" },
    ]);
    const vm = buildOpsWorkspaceViewModel(roster, partialHealth, false, false, false, false);
    const arbiter = vm.governanceLayer.find((e) => e.id === "arbiter");
    const senate = vm.governanceLayer.find((e) => e.id === "senate");
    expect(arbiter?.hasHealth).toBe(true);
    expect(senate?.hasHealth).toBe(false);
  });

  it("ignores unknown health-only entities (join safety)", () => {
    const healthWithUnknown = makeHealth([
      { entity_id: "arbiter", run_state: "idle", health_state: "live" },
      { entity_id: "unknown-phantom", run_state: "idle", health_state: "live" },
    ]);
    const vm = buildOpsWorkspaceViewModel(roster, healthWithUnknown, false, false, false, false);
    // unknown-phantom should not appear in any layer
    const allIds = [
      ...vm.governanceLayer,
      ...vm.officerLayer,
      ...vm.departments.flatMap((d) => d.entities),
    ].map((e) => e.id);
    expect(allIds).not.toContain("unknown-phantom");
    expect(allIds).toContain("arbiter");
  });

  it("maps entity view model correctly with health data", () => {
    const healthMap = new Map([
      [
        "arbiter",
        {
          entity_id: "arbiter",
          run_state: "completed" as const,
          health_state: "live" as const,
          health_summary: "All good",
        },
      ],
    ]);
    const entity = mapEntityViewModel(roster.governance_layer[0], healthMap);
    expect(entity.displayName).toBe("ARBITER");
    expect(entity.hasHealth).toBe(true);
    expect(entity.runState).toBe("completed");
    expect(entity.healthState).toBe("live");
    expect(entity.healthSummary).toBe("All good");
  });

  it("maps entity view model without health data", () => {
    const emptyMap = new Map();
    const entity = mapEntityViewModel(roster.governance_layer[0], emptyMap);
    expect(entity.hasHealth).toBe(false);
    expect(entity.runState).toBeUndefined();
    expect(entity.healthState).toBeUndefined();
  });

  it("builds degraded vm when health fails — roster structure preserved", () => {
    const vm = buildOpsWorkspaceViewModel(roster, null, false, false, false, true);
    expect(vm.condition).toBe("degraded");
    expect(vm.governanceLayer).toHaveLength(2);
    expect(vm.officerLayer).toHaveLength(1);
    expect(vm.departments).toHaveLength(4);
    expect(vm.entityCount).toBe(7);
  });
});

// ---- Component integration tests ----

describe("AgentOpsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default detail mock — returns a valid detail for any entity
    mockFetchDetail.mockImplementation((entityId: string) =>
      Promise.resolve({
        ok: true,
        data: makeDetail(entityId),
        status: 200,
      }),
    );
  });

  it("renders healthy state with roster and health data", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    // Title should be present
    expect(screen.getByText("Agent Operations")).toBeInTheDocument();

    // Mode pills should exist
    expect(screen.getByText("Org")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
    expect(screen.getByText("Health")).toBeInTheDocument();

    // Wait for data to load
    expect(await screen.findByText("ARBITER")).toBeInTheDocument();
    expect(screen.getByText("SENATE")).toBeInTheDocument();
    expect(screen.getByText("MARKET DATA OFFICER")).toBeInTheDocument();
    expect(screen.getByText("DEFAULT ANALYST")).toBeInTheDocument();

    // Layer section titles
    expect(screen.getByText("Governance Layer")).toBeInTheDocument();
    expect(screen.getByText("Officer Layer")).toBeInTheDocument();

    // Department section titles
    expect(screen.getByText("TECHNICAL ANALYSIS")).toBeInTheDocument();
    expect(screen.getByText("RISK CHALLENGE")).toBeInTheDocument();
  });

  it("shows loading state initially", () => {
    mockFetchRoster.mockReturnValue(new Promise(() => {})); // never resolves
    mockFetchHealth.mockReturnValue(new Promise(() => {}));

    renderWithRouter(<AgentOpsPage />);

    expect(screen.getByText("Agent Operations")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });

  it("shows error state when roster fails", async () => {
    mockFetchRoster.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "ROSTER_UNAVAILABLE",
    });
    mockFetchHealth.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "HEALTH_PROJECTION_FAILED",
    });

    renderWithRouter(<AgentOpsPage />);

    expect(await screen.findByText("Failed to load agent roster")).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("shows degraded banner when roster succeeds but health fails", async () => {
    const roster = makeRoster();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({
      ok: false,
      status: 500,
      detail: "HEALTH_PROJECTION_FAILED",
    });

    renderWithRouter(<AgentOpsPage />);

    // Roster structure should still render
    expect(await screen.findByText("ARBITER")).toBeInTheDocument();
    expect(screen.getByText("Health data unavailable")).toBeInTheDocument();
  });

  it("shows empty-health banner on fresh-start (empty entities)", async () => {
    const roster = makeRoster();
    const emptyHealth = makeHealth([]);
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: emptyHealth, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    expect(await screen.findByText("ARBITER")).toBeInTheDocument();
    expect(screen.getByText("Health data not yet available")).toBeInTheDocument();
  });

  it("opens detail panel on entity selection", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    // Wait for entities to render
    const arbiterCard = await screen.findByTestId("entity-card-arbiter");
    expect(arbiterCard).toBeInTheDocument();

    // Click to select
    await userEvent.click(arbiterCard);

    // Detail panel should appear
    const panels = screen.getAllByTestId("agent-detail-sidebar");
    expect(panels.length).toBeGreaterThan(0);

    // Check detail content in any panel
    const panel = panels[0];
    expect(within(panel).getByText("ARBITER")).toBeInTheDocument();
    // "arbiter" appears in both ID and Type rows — use getAllByText
    expect(within(panel).getAllByText("arbiter").length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("Test role")).toBeInTheDocument();
  });

  it("closes detail panel on close click", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    // Select an entity
    const arbiterCard = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(arbiterCard);

    // Panel should exist
    expect(screen.getAllByTestId("agent-detail-sidebar").length).toBeGreaterThan(0);

    // Close it
    const closeButtons = screen.getAllByLabelText("Close detail panel");
    await userEvent.click(closeButtons[0]);

    // Panel should be gone
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });

  it("toggles selection when clicking the same entity twice", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    const arbiterCard = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(arbiterCard);
    expect(screen.getAllByTestId("agent-detail-sidebar").length).toBeGreaterThan(0);

    // Click again to deselect
    await userEvent.click(arbiterCard);
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });

  it("enables Run and Health mode pills", async () => {
    mockFetchRoster.mockReturnValue(new Promise(() => {}));
    mockFetchHealth.mockReturnValue(new Promise(() => {}));

    renderWithRouter(<AgentOpsPage />);

    const runButton = screen.getByRole("button", { name: "Run" });
    const healthButton = screen.getByRole("button", { name: "Health" });

    expect(runButton).not.toBeDisabled();
    expect(healthButton).not.toBeDisabled();
  });
});

// ---- Route integration test ----

describe("AgentOpsRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default detail mock — returns a valid detail for any entity
    mockFetchDetail.mockImplementation((entityId: string) =>
      Promise.resolve({
        ok: true,
        data: makeDetail(entityId),
        status: 200,
      }),
    );
  });

  it("renders the ops workspace at /ops route", async () => {
    mockFetchRoster.mockReturnValue(new Promise(() => {}));
    mockFetchHealth.mockReturnValue(new Promise(() => {}));

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const router = createMemoryRouter(
      [{ path: "/ops", element: <AgentOpsRoute /> }],
      { initialEntries: ["/ops"] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(screen.getByText("Agent Operations")).toBeInTheDocument();
  });
});

// ---- PR-OPS-5a: OpsErrorEnvelope parsing ----

describe("parseOpsErrorEnvelope", () => {
  it("parses direct OpsError shape", () => {
    const result = parseOpsErrorEnvelope({
      error: "ROSTER_UNAVAILABLE",
      message: "Config could not be loaded",
    });
    expect(result).toEqual({
      error: "ROSTER_UNAVAILABLE",
      message: "Config could not be loaded",
      entity_id: undefined,
    });
  });

  it("parses OpsError with entity_id", () => {
    const result = parseOpsErrorEnvelope({
      error: "ENTITY_NOT_FOUND",
      message: "Entity not found",
      entity_id: "phantom",
    });
    expect(result).toEqual({
      error: "ENTITY_NOT_FOUND",
      message: "Entity not found",
      entity_id: "phantom",
    });
  });

  it("parses wrapped OpsErrorEnvelope { detail: { error, message } }", () => {
    const result = parseOpsErrorEnvelope({
      detail: {
        error: "HEALTH_PROJECTION_FAILED",
        message: "Projection failed",
      },
    });
    expect(result).toEqual({
      error: "HEALTH_PROJECTION_FAILED",
      message: "Projection failed",
      entity_id: undefined,
    });
  });

  it("returns null for non-object input", () => {
    expect(parseOpsErrorEnvelope("just a string")).toBeNull();
    expect(parseOpsErrorEnvelope(null)).toBeNull();
    expect(parseOpsErrorEnvelope(42)).toBeNull();
  });

  it("returns null for unrecognized object shape", () => {
    expect(parseOpsErrorEnvelope({ foo: "bar" })).toBeNull();
  });
});

// ---- PR-OPS-5a: Health mode activation ----

describe("AgentOpsPage — Health mode (PR-OPS-5a)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default detail mock — returns a valid detail for any entity
    mockFetchDetail.mockImplementation((entityId: string) =>
      Promise.resolve({
        ok: true,
        data: makeDetail(entityId),
        status: 200,
      }),
    );
  });

  it("activates Health mode and shows health mode header", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    // Wait for entities
    await screen.findByText("ARBITER");

    // Click Health pill
    const healthButton = screen.getByRole("button", { name: "Health" });
    await userEvent.click(healthButton);

    // Health mode header should appear
    expect(screen.getByTestId("health-mode-header")).toBeInTheDocument();
    expect(screen.getByText("Health Mode")).toBeInTheDocument();
  });

  it("preserves selection when switching from Org to Health mode", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    // Select entity in Org mode
    const arbiterCard = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(arbiterCard);
    expect(screen.getAllByTestId("agent-detail-sidebar").length).toBeGreaterThan(0);

    // Switch to Health mode — use getByRole to target button specifically
    const healthPill = screen.getByRole("button", { name: "Health" });
    await userEvent.click(healthPill);

    // Selection should be preserved
    expect(screen.getAllByTestId("agent-detail-sidebar").length).toBeGreaterThan(0);
    const panel = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(panel).getByText("ARBITER")).toBeInTheDocument();
  });

  it("switches back to Org mode from Health mode", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    // Switch to Health then back to Org
    await userEvent.click(screen.getByRole("button", { name: "Health" }));
    expect(screen.getByTestId("health-mode-header")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Org" }));
    expect(screen.queryByTestId("health-mode-header")).not.toBeInTheDocument();
  });

  it("shows data_state stale banner when roster is stale", async () => {
    const roster = makeRoster({ data_state: "stale" });
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    expect(screen.getByTestId("data-state-banner-roster")).toBeInTheDocument();
    expect(screen.getByText("Roster data is stale")).toBeInTheDocument();
  });

  it("shows data_state stale banner when health is stale", async () => {
    const roster = makeRoster();
    const health = makeHealth(undefined, { data_state: "stale" });
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    expect(screen.getByTestId("data-state-banner-health")).toBeInTheDocument();
    expect(screen.getByText("Health data is stale")).toBeInTheDocument();
  });

  it("renders without data_state banners when both are live", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    expect(screen.queryByTestId("data-state-banner-roster")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-state-banner-health")).not.toBeInTheDocument();
  });
});

// ---- PR-OPS-5a: Typed adapters contract compliance ----

describe("PR-OPS-5a contract compliance", () => {
  it("roster-health join: unknown health IDs discarded (§5.10 rule 1)", () => {
    const roster = makeRoster();
    const health = makeHealth([
      { entity_id: "arbiter", run_state: "idle", health_state: "live" },
      { entity_id: "ghost", run_state: "idle", health_state: "degraded" },
    ]);
    const vm = buildOpsWorkspaceViewModel(roster, health, false, false, false, false);
    const allIds = [
      ...vm.governanceLayer,
      ...vm.officerLayer,
      ...vm.departments.flatMap((d) => d.entities),
    ].map((e) => e.id);
    expect(allIds).not.toContain("ghost");
  });

  it("roster-health join: missing health for known entity is valid (§5.10 rule 2)", () => {
    const roster = makeRoster();
    const health = makeHealth([
      { entity_id: "arbiter", run_state: "idle", health_state: "live" },
    ]);
    const vm = buildOpsWorkspaceViewModel(roster, health, false, false, false, false);
    const senate = vm.governanceLayer.find((e) => e.id === "senate");
    expect(senate).toBeDefined();
    expect(senate!.hasHealth).toBe(false);
  });

  it("roster is structural source of truth (§5.10 rule 3)", () => {
    const roster = makeRoster();
    const vm = buildOpsWorkspaceViewModel(roster, null, false, false, false, true);
    expect(vm.condition).toBe("degraded");
    // All roster entities should still exist
    expect(vm.entityCount).toBe(7);
    expect(vm.governanceLayer).toHaveLength(2);
    expect(vm.officerLayer).toHaveLength(1);
    expect(vm.departments).toHaveLength(4);
  });

  it("health failure → roster without badges + degraded banner (§5.9)", async () => {
    const roster = makeRoster();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({
      ok: false,
      status: 500,
      detail: { error: "HEALTH_PROJECTION_FAILED", message: "Failed" },
    });

    renderWithRouter(<AgentOpsPage />);

    // Roster still renders
    expect(await screen.findByText("ARBITER")).toBeInTheDocument();
    expect(screen.getByText("Health data unavailable")).toBeInTheDocument();

    // NO HEALTH indicators should appear for entities
    const noHealthBadges = screen.getAllByText("NO HEALTH");
    expect(noHealthBadges.length).toBeGreaterThan(0);
  });

  it("relationships array is preserved in view model", () => {
    const roster = makeRoster();
    const health = makeHealth();
    const vm = buildOpsWorkspaceViewModel(roster, health, false, false, false, false);
    expect(vm.relationships).toHaveLength(2);
    expect(vm.relationships[0]).toEqual({
      from: "arbiter",
      to: "senate",
      type: "synthesizes",
    });
  });
});

// ---- PR-OPS-5b: Run mode ----

describe("AgentOpsPage — Run mode (PR-OPS-5b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchDetail.mockImplementation((entityId: string) =>
      Promise.resolve({ ok: true, data: makeDetail(entityId), status: 200 }),
    );
    mockFetchRuns.mockResolvedValue({
      ok: true, status: 200,
      data: {
        version: "2026.03", generated_at: "2026-03-14T12:00:00Z",
        data_state: "live", items: [], page: 1, page_size: 20, total: 0, has_next: false,
      },
    });
  });

  function setupReady() {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });
  }

  it("shows run selector and browser panel when switching to Run mode", async () => {
    setupReady();
    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    expect(screen.getByTestId("run-selector")).toBeInTheDocument();
    // Browser panel shows empty state when no runs exist
    expect(screen.getByTestId("run-browser-empty")).toBeInTheDocument();
    expect(screen.getByText("No analysis runs found")).toBeInTheDocument();
  });

  it("loads and displays trace after entering run ID", async () => {
    setupReady();
    const trace = makeTrace();
    mockFetchTrace.mockResolvedValue({ ok: true, data: trace, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    const input = screen.getByTestId("run-id-input");
    await userEvent.type(input, "run-001");

    const loadButton = screen.getByRole("button", { name: /load/i });
    await userEvent.click(loadButton);

    const tracePanel = await screen.findByTestId("run-trace-panel");
    expect(tracePanel).toBeInTheDocument();
  });

  it("renders trace summary fields (instrument, verdict, confidence)", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    const input = screen.getByTestId("run-id-input");
    await userEvent.type(input, "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const header = await screen.findByTestId("run-header");
    expect(within(header).getByText("EURUSD")).toBeInTheDocument();
    expect(within(header).getByText("bullish")).toBeInTheDocument();
    expect(within(header).getByText("82%")).toBeInTheDocument();
  });

  it("renders stage timeline with all stages", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const timeline = await screen.findByTestId("trace-stage-timeline");
    expect(timeline).toBeInTheDocument();
    expect(screen.getByTestId("trace-stage-validate_input")).toBeInTheDocument();
    expect(screen.getByTestId("trace-stage-macro_context")).toBeInTheDocument();
    expect(screen.getByTestId("trace-stage-analyst_execution")).toBeInTheDocument();
    expect(screen.getByTestId("trace-stage-arbiter")).toBeInTheDocument();
    expect(screen.getByTestId("trace-stage-logging")).toBeInTheDocument();
  });

  it("renders participants with override indicator", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const participants = await screen.findByTestId("trace-participant-list");
    expect(participants).toBeInTheDocument();

    expect(screen.getByTestId("participant-default-analyst")).toBeInTheDocument();
    expect(screen.getByTestId("participant-risk-challenger")).toBeInTheDocument();

    // Risk challenger was overridden
    expect(screen.getByTestId("override-risk-challenger")).toBeInTheDocument();
  });

  it("renders trace edges", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const edgeList = await screen.findByTestId("trace-edge-list");
    expect(edgeList).toBeInTheDocument();
    expect(screen.getByTestId("trace-edge-default-analyst-arbiter")).toBeInTheDocument();
    expect(screen.getByTestId("trace-edge-risk-challenger-arbiter")).toBeInTheDocument();
  });

  it("renders arbiter summary card with override applied", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const arbiterCard = await screen.findByTestId("arbiter-summary-card");
    expect(arbiterCard).toBeInTheDocument();
    expect(screen.getByTestId("arbiter-override-applied")).toBeInTheDocument();
    expect(within(arbiterCard).getByText("weighted_synthesis")).toBeInTheDocument();
  });

  it("hides arbiter summary when null", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({
      ok: true,
      data: makeTrace({ arbiter_summary: null }),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    await screen.findByTestId("run-trace-panel");
    expect(screen.queryByTestId("arbiter-summary-card")).not.toBeInTheDocument();
  });

  it("shows partial run indicator when stages are pending/running", async () => {
    setupReady();
    const trace = makeTrace({
      stages: [
        { stage: "validate_input", status: "completed", order: 0, duration_ms: 100 },
        { stage: "macro_context", status: "running", order: 1, duration_ms: null },
        { stage: "analyst_execution", status: "pending", order: 2, duration_ms: null },
      ],
    });
    mockFetchTrace.mockResolvedValue({ ok: true, data: trace, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    await screen.findByTestId("run-trace-panel");
    expect(screen.getByTestId("partial-run-indicator")).toBeInTheDocument();
  });

  it("shows 404 error for unknown run ID", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({
      ok: false,
      status: 404,
      detail: { error: "RUN_NOT_FOUND", message: "Run not found" },
    });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "bad-run");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const errorEl = await screen.findByTestId("run-trace-error");
    expect(errorEl).toBeInTheDocument();
    expect(within(errorEl).getAllByText("Run not found").length).toBeGreaterThan(0);
  });

  it("shows stale banner when trace data_state is stale", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({
      ok: true,
      data: makeTrace({ data_state: "stale" }),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    await screen.findByTestId("run-trace-panel");
    expect(screen.getByTestId("data-state-banner-health")).toBeInTheDocument();
  });

  it("hides Org/Health banners in Run mode", async () => {
    const roster = makeRoster({ data_state: "stale" });
    const health = makeHealth(undefined, { data_state: "stale" });
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");

    // Stale banners visible in Org mode
    expect(screen.getByTestId("data-state-banner-roster")).toBeInTheDocument();
    expect(screen.getByTestId("data-state-banner-health")).toBeInTheDocument();

    // Switch to Run mode — banners should hide
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(screen.queryByTestId("data-state-banner-roster")).not.toBeInTheDocument();
    expect(screen.queryByTestId("data-state-banner-health")).not.toBeInTheDocument();
  });

  it("renders artifacts section", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    await screen.findByText("ARBITER");
    await userEvent.click(screen.getByRole("button", { name: "Run" }));

    await userEvent.type(screen.getByTestId("run-id-input"), "run-001");
    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    const artifacts = await screen.findByTestId("trace-artifacts");
    expect(artifacts).toBeInTheDocument();
    expect(screen.getByText("run_record.json")).toBeInTheDocument();
  });
});

// ---- PR-OPS-5b: Detail sidebar ----

describe("AgentOpsPage — Detail sidebar (PR-OPS-5b)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchDetail.mockImplementation((entityId: string) =>
      Promise.resolve({ ok: true, data: makeDetail(entityId), status: 200 }),
    );
    mockFetchRuns.mockResolvedValue({
      ok: true, status: 200,
      data: {
        version: "2026.03", generated_at: "2026-03-14T12:00:00Z",
        data_state: "live", items: [], page: 1, page_size: 20, total: 0, has_next: false,
      },
    });
  });

  function setupReady() {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });
  }

  it("renders arbiter type-specific section via entity_type switch", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("arbiter", "arbiter"),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(sidebar).getByTestId("detail-arbiter-section")).toBeInTheDocument();
    expect(within(sidebar).getByText("weighted")).toBeInTheDocument();
    expect(within(sidebar).getByText("majority")).toBeInTheDocument();
  });

  it("renders persona type-specific section", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("default-analyst", "persona"),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-default-analyst");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(sidebar).getByTestId("detail-persona-section")).toBeInTheDocument();
    expect(within(sidebar).getByText("directional")).toBeInTheDocument();
    expect(within(sidebar).getByText("analyst")).toBeInTheDocument();
  });

  it("renders officer type-specific section", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("mdo", "officer"),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-mdo");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(sidebar).getByTestId("detail-officer-section")).toBeInTheDocument();
    expect(within(sidebar).getByText("market_data")).toBeInTheDocument();
  });

  it("renders subsystem type-specific section", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("infra-monitor", "subsystem"),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-infra-monitor");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    const subsystemSection = within(sidebar).getByTestId("detail-subsystem-section");
    expect(subsystemSection).toBeInTheDocument();
    // subsystem_type and runtime_role both "monitor" — verify section renders them
    expect(within(subsystemSection).getAllByText("monitor").length).toBeGreaterThanOrEqual(1);
  });

  it("shows 404 error when entity not found", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: false,
      status: 404,
      detail: { error: "ENTITY_NOT_FOUND", message: "Entity not found" },
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    const error = await within(sidebar).findByTestId("detail-error");
    expect(error).toBeInTheDocument();
    expect(within(error).getAllByText("Entity not found").length).toBeGreaterThan(0);
  });

  it("shows stale indicator when detail data_state is stale", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("arbiter", "arbiter", { data_state: "stale" }),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(sidebar).getByTestId("detail-stale-indicator")).toBeInTheDocument();
  });

  it("shows unavailable health state indicator", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("arbiter", "arbiter", {
        status: {
          run_state: "idle",
          health_state: "unavailable",
          last_active_at: null,
          last_run_id: null,
          health_summary: null,
        },
      }),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(sidebar).getByTestId("detail-health-unavailable")).toBeInTheDocument();
  });

  it("renders dependencies list", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("arbiter", "arbiter", {
        dependencies: [
          { entity_id: "senate", display_name: "SENATE", direction: "upstream", relationship_type: "synthesizes" },
          { entity_id: "mdo", display_name: "MDO", direction: "downstream", relationship_type: "feeds" },
        ],
      }),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    expect(within(sidebar).getByText("SENATE")).toBeInTheDocument();
    expect(within(sidebar).getByText("MDO")).toBeInTheDocument();
  });

  it("renders recent participation with override indicator", async () => {
    setupReady();
    mockFetchDetail.mockResolvedValue({
      ok: true,
      data: makeDetail("arbiter", "arbiter", {
        recent_participation: [
          { run_id: "run-001", run_completed_at: "2026-03-15T09:55:00Z", verdict_direction: "bullish", was_overridden: true, contribution_summary: "Bullish call" },
          { run_id: "run-002", run_completed_at: "2026-03-15T09:50:00Z", verdict_direction: "bearish", was_overridden: false, contribution_summary: "Bearish call" },
        ],
      }),
      status: 200,
    });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    const participation = within(sidebar).getByTestId("detail-recent-participation");
    expect(participation).toBeInTheDocument();
    expect(within(participation).getByText("Overridden")).toBeInTheDocument();
  });

  it("hides detail sidebar in Run mode", async () => {
    setupReady();
    renderWithRouter(<AgentOpsPage />);

    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);
    expect(screen.getAllByTestId("agent-detail-sidebar").length).toBeGreaterThan(0);

    // Switch to Run mode — sidebar hides
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });

  it("navigates to Run mode from detail sidebar last-run link", async () => {
    setupReady();
    mockFetchTrace.mockResolvedValue({ ok: true, data: makeTrace(), status: 200 });

    renderWithRouter(<AgentOpsPage />);
    const card = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(card);

    // Find and click the last run link in the detail sidebar
    const sidebar = screen.getAllByTestId("agent-detail-sidebar")[0];
    const content = await within(sidebar).findByTestId("detail-content");

    // The detail mock has last_run_id: "run-001" — should render as clickable link
    const runLink = within(content).getByText("run-001");
    await userEvent.click(runLink);

    // Should switch to Run mode and show trace
    expect(screen.getByTestId("run-mode-view")).toBeInTheDocument();
  });
});

// ===== PR-REFLECT-3: URL PARAM CONSUMPTION =====

describe("AgentOpsPage — URL param consumption (PR-REFLECT-3)", () => {
  beforeEach(() => {
    mockFetchRoster.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRoster(),
    });
    mockFetchHealth.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeHealth(),
    });
    mockFetchDetail.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeDetail("persona_default_analyst", "persona"),
    });
  });

  function renderWithParams(path: string) {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const router = createMemoryRouter(
      [{ path: "/ops", element: <AgentOpsPage /> }],
      { initialEntries: [path] },
    );
    return render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
  }

  it("consumes entity_id+mode=detail and selects entity", async () => {
    renderWithParams("/ops?entity_id=persona_default_analyst&mode=detail");

    // Wait for the detail sidebar to appear (entity was consumed from URL params)
    // Desktop + mobile sidebars both render
    await screen.findAllByTestId("agent-detail-sidebar");
    const sidebars = screen.getAllByTestId("agent-detail-sidebar");
    expect(sidebars.length).toBeGreaterThan(0);
  });

  it("zero-param initialises to default state", async () => {
    renderWithParams("/ops");
    await screen.findByText("Agent Operations");

    // No detail sidebar with zero params
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });

  it("mode=detail without entity shows no sidebar", async () => {
    renderWithParams("/ops?mode=detail");
    await screen.findByText("Agent Operations");

    // No entity selected = no sidebar
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });

  it("entity_id without mode is ignored", async () => {
    renderWithParams("/ops?entity_id=persona_default_analyst");
    await screen.findByText("Agent Operations");

    // entity_id alone is ignored per spec
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });

  it("empty string entity_id treated as absent", async () => {
    renderWithParams("/ops?entity_id=&mode=detail");
    await screen.findByText("Agent Operations");

    // Empty entity_id = absent → no entity selected
    expect(screen.queryByTestId("agent-detail-sidebar")).not.toBeInTheDocument();
  });
});

// ===== PR-REFLECT-3: C-6 MODE CHANGE CLEARS RUN STATE =====

describe("AgentOpsPage — C-6 run state clear on mode change", () => {
  beforeEach(() => {
    mockFetchRoster.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeRoster(),
    });
    mockFetchHealth.mockResolvedValue({
      ok: true,
      status: 200,
      data: makeHealth(),
    });
  });

  it("switching from Run to Org clears run mode view on return", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const router = createMemoryRouter(
      [{ path: "/ops", element: <AgentOpsPage /> }],
      { initialEntries: ["/ops"] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await screen.findByText("Agent Operations");

    // Switch to Run mode
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(screen.getByTestId("run-mode-view")).toBeInTheDocument();

    // Switch to Org mode
    await userEvent.click(screen.getByRole("button", { name: "Org" }));
    expect(screen.queryByTestId("run-mode-view")).not.toBeInTheDocument();

    // Switch back to Run mode — should be clean (no selected run)
    await userEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(screen.getByTestId("run-mode-view")).toBeInTheDocument();
    // No trace panel should be visible (selectedRunId was cleared)
    expect(screen.queryByTestId("trace-panel")).not.toBeInTheDocument();
  });
});
