// ---------------------------------------------------------------------------
// Journal & Review workspace tests — PR-UI-6.
//
// Covers: adapter unit tests (normalization, type safety, header summaries,
// coverage derivation), component integration tests (loading, empty, error,
// ready states for both views), view toggle, navigation, review indicators.
// No snapshots. Explicit assertions.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import {
  buildJournalViewModel,
  buildReviewViewModel,
  mapDecisionRow,
  mapReviewRow,
  deriveJournalHeader,
  deriveOutcomeCoverage,
  deriveReviewHeader,
} from "../src/workspaces/journal/adapters/journalAdapter";
import type {
  DecisionSnapshot,
  ReviewRecord,
  JournalDecisionsResponse,
  ReviewRecordsResponse,
} from "../src/workspaces/journal/api/journalApi";
import { JournalReviewPage } from "../src/workspaces/journal/components/JournalReviewPage";

// ---- Mock API modules ----

vi.mock("../src/workspaces/journal/api/journalApi", () => ({
  fetchDecisions: vi.fn(),
  fetchReviewRecords: vi.fn(),
}));

import { fetchDecisions, fetchReviewRecords } from "../src/workspaces/journal/api/journalApi";

const mockFetchDecisions = vi.mocked(fetchDecisions);
const mockFetchReviewRecords = vi.mocked(fetchReviewRecords);

// ---- Test data ----

const DECISION_A: DecisionSnapshot = {
  snapshot_id: "snap-001",
  instrument: "EURUSD",
  saved_at: "2026-03-14T10:30:00Z",
  journey_status: "frozen",
  verdict: "bullish",
  user_decision: "long",
};

const DECISION_B: DecisionSnapshot = {
  snapshot_id: "snap-002",
  instrument: "XAUUSD",
  saved_at: "2026-03-14T11:00:00Z",
  journey_status: "frozen",
  verdict: "bearish",
  user_decision: null,
};

const REVIEW_A: ReviewRecord = {
  ...DECISION_A,
  has_result: true,
};

const REVIEW_B: ReviewRecord = {
  ...DECISION_B,
  has_result: false,
};

const DECISIONS_RESPONSE: JournalDecisionsResponse = {
  records: [DECISION_A, DECISION_B],
};

const REVIEW_RESPONSE: ReviewRecordsResponse = {
  records: [REVIEW_A, REVIEW_B],
};

// ---- Test helpers ----

function renderJournalPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const router = createMemoryRouter(
    [
      { path: "/journal", element: <JournalReviewPage /> },
      {
        path: "/journey/:asset",
        element: <div data-testid="journey-page">Journey</div>,
      },
    ],
    { initialEntries: ["/journal"] },
  );

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// ---- Setup ----

beforeEach(() => {
  vi.resetAllMocks();
});

// ===========================================================================
// ADAPTER UNIT TESTS
// ===========================================================================

describe("journalAdapter", () => {
  describe("mapDecisionRow", () => {
    it("maps all DecisionSnapshot fields to view model", () => {
      const row = mapDecisionRow(DECISION_A);
      expect(row.snapshotId).toBe("snap-001");
      expect(row.instrument).toBe("EURUSD");
      expect(row.savedAt).toBe("2026-03-14T10:30:00Z");
      expect(row.journeyStatus).toBe("frozen");
      expect(row.verdict).toBe("bullish");
      expect(row.userDecision).toBe("long");
      expect(row.journeyLink).toBe("/journey/EURUSD");
    });

    it("handles null user_decision", () => {
      const row = mapDecisionRow(DECISION_B);
      expect(row.userDecision).toBeNull();
    });

    it("encodes instrument in journey link", () => {
      const row = mapDecisionRow({
        ...DECISION_A,
        instrument: "EUR/USD",
      });
      expect(row.journeyLink).toBe("/journey/EUR%2FUSD");
    });

    it("defaults missing journey_status to unknown", () => {
      const row = mapDecisionRow({
        ...DECISION_A,
        journey_status: undefined as unknown as string,
      });
      expect(row.journeyStatus).toBe("unknown");
    });
  });

  describe("mapReviewRow", () => {
    it("extends DecisionSnapshot fields with has_result", () => {
      const row = mapReviewRow(REVIEW_A);
      expect(row.snapshotId).toBe("snap-001");
      expect(row.instrument).toBe("EURUSD");
      expect(row.hasResult).toBe(true);
      expect(row.resultIndicator).toBe("has-result");
    });

    it("marks needs-follow-up for records without result", () => {
      const row = mapReviewRow(REVIEW_B);
      expect(row.hasResult).toBe(false);
      expect(row.resultIndicator).toBe("needs-follow-up");
    });

    it("ReviewRecord type-safely extends DecisionSnapshot", () => {
      // Type-level test: ReviewRecord includes all DecisionSnapshot fields
      const review: ReviewRecord = {
        snapshot_id: "snap-003",
        instrument: "GBPUSD",
        saved_at: "2026-03-14T12:00:00Z",
        journey_status: "frozen",
        verdict: "neutral",
        user_decision: null,
        has_result: false,
      };
      const row = mapReviewRow(review);
      expect(row.instrument).toBe("GBPUSD");
      expect(row.hasResult).toBe(false);
    });
  });

  describe("deriveJournalHeader", () => {
    it("returns correct text for zero decisions", () => {
      expect(deriveJournalHeader(0).text).toBe("No frozen decisions");
    });

    it("returns singular for one decision", () => {
      expect(deriveJournalHeader(1).text).toBe("1 frozen decision");
    });

    it("returns plural for multiple decisions", () => {
      expect(deriveJournalHeader(12).text).toBe("12 frozen decisions");
    });
  });

  describe("deriveOutcomeCoverage", () => {
    it("counts records with results", () => {
      const coverage = deriveOutcomeCoverage([REVIEW_A, REVIEW_B]);
      expect(coverage.withResults).toBe(1);
      expect(coverage.total).toBe(2);
      expect(coverage.text).toBe("1 of 2 decisions have results");
    });

    it("handles empty records", () => {
      const coverage = deriveOutcomeCoverage([]);
      expect(coverage.withResults).toBe(0);
      expect(coverage.total).toBe(0);
      expect(coverage.text).toBe("No decisions to review");
    });

    it("handles all records with results", () => {
      const coverage = deriveOutcomeCoverage([REVIEW_A, { ...REVIEW_B, has_result: true }]);
      expect(coverage.withResults).toBe(2);
      expect(coverage.total).toBe(2);
      expect(coverage.text).toBe("2 of 2 decisions have results");
    });

    it("handles no records with results", () => {
      const coverage = deriveOutcomeCoverage([
        { ...REVIEW_A, has_result: false },
        REVIEW_B,
      ]);
      expect(coverage.withResults).toBe(0);
      expect(coverage.total).toBe(2);
      expect(coverage.text).toBe("0 of 2 decisions have results");
    });
  });

  describe("deriveReviewHeader", () => {
    it("derives header from outcome coverage", () => {
      const coverage = deriveOutcomeCoverage([REVIEW_A, REVIEW_B]);
      const header = deriveReviewHeader(coverage);
      expect(header.text).toBe("1 of 2 decisions have results");
    });
  });

  describe("buildJournalViewModel", () => {
    it("returns loading condition when isLoading", () => {
      const vm = buildJournalViewModel(null, true, false);
      expect(vm.condition).toBe("loading");
      expect(vm.rows).toHaveLength(0);
      expect(vm.header.text).toBe("");
    });

    it("returns error condition when isError", () => {
      const vm = buildJournalViewModel(null, false, true);
      expect(vm.condition).toBe("error");
      expect(vm.rows).toHaveLength(0);
    });

    it("returns error condition when data is null", () => {
      const vm = buildJournalViewModel(null, false, false);
      expect(vm.condition).toBe("error");
    });

    it("returns empty condition for empty records", () => {
      const vm = buildJournalViewModel({ records: [] }, false, false);
      expect(vm.condition).toBe("empty");
      expect(vm.rows).toHaveLength(0);
      expect(vm.header.text).toBe("No frozen decisions");
    });

    it("returns ready condition with mapped rows", () => {
      const vm = buildJournalViewModel(DECISIONS_RESPONSE, false, false);
      expect(vm.condition).toBe("ready");
      expect(vm.rows).toHaveLength(2);
      expect(vm.rows[0].instrument).toBe("EURUSD");
      expect(vm.rows[1].instrument).toBe("XAUUSD");
      expect(vm.header.text).toBe("2 frozen decisions");
    });
  });

  describe("buildReviewViewModel", () => {
    it("returns loading condition when isLoading", () => {
      const vm = buildReviewViewModel(null, true, false);
      expect(vm.condition).toBe("loading");
      expect(vm.rows).toHaveLength(0);
      expect(vm.outcomeCoverage.total).toBe(0);
    });

    it("returns error condition when isError", () => {
      const vm = buildReviewViewModel(null, false, true);
      expect(vm.condition).toBe("error");
    });

    it("returns empty condition for empty records", () => {
      const vm = buildReviewViewModel({ records: [] }, false, false);
      expect(vm.condition).toBe("empty");
      expect(vm.rows).toHaveLength(0);
      expect(vm.outcomeCoverage.text).toBe("No decisions to review");
    });

    it("returns ready condition with review rows and coverage", () => {
      const vm = buildReviewViewModel(REVIEW_RESPONSE, false, false);
      expect(vm.condition).toBe("ready");
      expect(vm.rows).toHaveLength(2);
      expect(vm.rows[0].hasResult).toBe(true);
      expect(vm.rows[0].resultIndicator).toBe("has-result");
      expect(vm.rows[1].hasResult).toBe(false);
      expect(vm.rows[1].resultIndicator).toBe("needs-follow-up");
      expect(vm.outcomeCoverage.withResults).toBe(1);
      expect(vm.outcomeCoverage.total).toBe(2);
      expect(vm.header.text).toBe("1 of 2 decisions have results");
    });
  });
});

// ===========================================================================
// COMPONENT INTEGRATION TESTS
// ===========================================================================

describe("JournalReviewPage", () => {
  // ---- Journal View ----

  describe("Journal view", () => {
    it("shows loading skeleton during initial fetch", () => {
      mockFetchDecisions.mockReturnValue(new Promise(() => {}));
      mockFetchReviewRecords.mockReturnValue(new Promise(() => {}));
      renderJournalPage();
      expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument();
    });

    it("renders decision records in ready state", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });
      expect(screen.getByText("XAUUSD")).toBeInTheDocument();
      expect(screen.getByText("2 frozen decisions")).toBeInTheDocument();
    });

    it("renders empty state when no decisions exist", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: { records: [] },
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("No decisions recorded yet")).toBeInTheDocument();
      });
      expect(
        screen.getByText("Freeze a decision in Journey Studio to see it here."),
      ).toBeInTheDocument();
    });

    it("renders error state with retry on fetch failure", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: false,
        status: 500,
        detail: "Internal server error",
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("Failed to load decisions")).toBeInTheDocument();
      });
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });

    it("displays header summary with decision count", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("2 frozen decisions")).toBeInTheDocument();
      });
    });

    it("does not show review indicators in journal view", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });
      expect(screen.queryByText("Has result")).not.toBeInTheDocument();
      expect(screen.queryByText("Needs follow-up")).not.toBeInTheDocument();
    });

    it("navigates to Journey on row click", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("EURUSD"));

      await waitFor(() => {
        expect(screen.getByTestId("journey-page")).toBeInTheDocument();
      });
    });
  });

  // ---- View toggle ----

  describe("View toggle", () => {
    it("defaults to Journal view", () => {
      mockFetchDecisions.mockReturnValue(new Promise(() => {}));
      renderJournalPage();
      expect(screen.getByText("Journal")).toBeInTheDocument();
      expect(screen.getByText("Review")).toBeInTheDocument();
    });

    it("switches to Review view when toggle clicked", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: REVIEW_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("Has result")).toBeInTheDocument();
      });
      expect(screen.getByText("Needs follow-up")).toBeInTheDocument();
    });

    it("switches back to Journal view from Review", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: REVIEW_RESPONSE,
      });
      renderJournalPage();

      // Switch to Review
      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("Has result")).toBeInTheDocument();
      });

      // Switch back to Journal
      fireEvent.click(screen.getByText("Journal"));

      await waitFor(() => {
        expect(screen.queryByText("Has result")).not.toBeInTheDocument();
      });
    });

    it("Journal view fetches from /journal/decisions", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(mockFetchDecisions).toHaveBeenCalled();
      });
    });

    it("Review view fetches from /review/records", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: REVIEW_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(mockFetchReviewRecords).toHaveBeenCalled();
      });
    });
  });

  // ---- Review View ----

  describe("Review view", () => {
    it("renders review records with result indicators", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: REVIEW_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("Has result")).toBeInTheDocument();
      });
      expect(screen.getByText("Needs follow-up")).toBeInTheDocument();
      expect(screen.getByText("EURUSD")).toBeInTheDocument();
      expect(screen.getByText("XAUUSD")).toBeInTheDocument();
    });

    it("shows outcome coverage summary in header", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: REVIEW_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("1 of 2 decisions have results")).toBeInTheDocument();
      });
    });

    it("renders empty state in review view", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: { records: [] },
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("No review records yet")).toBeInTheDocument();
      });
    });

    it("renders error state in review view", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: false,
        status: 500,
        detail: "Server error",
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("Failed to load review records")).toBeInTheDocument();
      });
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });

    it("navigates to Journey on review row click", async () => {
      mockFetchDecisions.mockResolvedValue({
        ok: true,
        status: 200,
        data: DECISIONS_RESPONSE,
      });
      mockFetchReviewRecords.mockResolvedValue({
        ok: true,
        status: 200,
        data: REVIEW_RESPONSE,
      });
      renderJournalPage();

      await waitFor(() => {
        expect(screen.getByText("EURUSD")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Review"));

      await waitFor(() => {
        expect(screen.getByText("Has result")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("XAUUSD"));

      await waitFor(() => {
        expect(screen.getByTestId("journey-page")).toBeInTheDocument();
      });
    });
  });

  // ---- Route ----

  describe("Route", () => {
    it("renders at /journal path", () => {
      mockFetchDecisions.mockReturnValue(new Promise(() => {}));
      renderJournalPage();
      expect(screen.getByText("Journal & Review")).toBeInTheDocument();
    });
  });
});
