// ---------------------------------------------------------------------------
// Agent Operations workspace tests — PR-OPS-3 + PR-OPS-5a.
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

vi.mock("../src/shared/api/ops", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/shared/api/ops")>();
  return {
    ...actual,
    fetchAgentRoster: (...args: unknown[]) => mockFetchRoster(...args),
    fetchAgentHealth: (...args: unknown[]) => mockFetchHealth(...args),
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
    const panels = screen.getAllByTestId("selected-detail-panel");
    expect(panels.length).toBeGreaterThan(0);

    // Check detail content in any panel
    const panel = panels[0];
    expect(within(panel).getByText("ARBITER")).toBeInTheDocument();
    // "arbiter" appears in both ID and Type rows — use getAllByText
    expect(within(panel).getAllByText("arbiter").length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("Final Decision Maker")).toBeInTheDocument();
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
    expect(screen.getAllByTestId("selected-detail-panel").length).toBeGreaterThan(0);

    // Close it
    const closeButtons = screen.getAllByLabelText("Close detail panel");
    await userEvent.click(closeButtons[0]);

    // Panel should be gone
    expect(screen.queryByTestId("selected-detail-panel")).not.toBeInTheDocument();
  });

  it("toggles selection when clicking the same entity twice", async () => {
    const roster = makeRoster();
    const health = makeHealth();
    mockFetchRoster.mockResolvedValue({ ok: true, data: roster, status: 200 });
    mockFetchHealth.mockResolvedValue({ ok: true, data: health, status: 200 });

    renderWithRouter(<AgentOpsPage />);

    const arbiterCard = await screen.findByTestId("entity-card-arbiter");
    await userEvent.click(arbiterCard);
    expect(screen.getAllByTestId("selected-detail-panel").length).toBeGreaterThan(0);

    // Click again to deselect
    await userEvent.click(arbiterCard);
    expect(screen.queryByTestId("selected-detail-panel")).not.toBeInTheDocument();
  });

  it("disables Run mode pill, enables Health mode pill", async () => {
    mockFetchRoster.mockReturnValue(new Promise(() => {}));
    mockFetchHealth.mockReturnValue(new Promise(() => {}));

    renderWithRouter(<AgentOpsPage />);

    const runButton = screen.getByRole("button", { name: "Run" });
    const healthButton = screen.getByRole("button", { name: "Health" });

    expect(runButton).toBeDisabled();
    expect(runButton).toHaveAttribute("title", "Requires run trace wiring (PR-OPS-5b)");
    expect(healthButton).not.toBeDisabled();
  });
});

// ---- Route integration test ----

describe("AgentOpsRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    expect(screen.getAllByTestId("selected-detail-panel").length).toBeGreaterThan(0);

    // Switch to Health mode — use getByRole to target button specifically
    const healthPill = screen.getByRole("button", { name: "Health" });
    await userEvent.click(healthPill);

    // Selection should be preserved
    expect(screen.getAllByTestId("selected-detail-panel").length).toBeGreaterThan(0);
    const panel = screen.getAllByTestId("selected-detail-panel")[0];
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
