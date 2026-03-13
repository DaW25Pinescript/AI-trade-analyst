// ---------------------------------------------------------------------------
// Shared component isolated tests — PR-UI-3.
//
// Covers: DataStateBadge, StatusPill, TrustStrip, FeederHealthChip,
//         PanelShell, EmptyState, UnavailableState, ErrorState,
//         LoadingSkeleton, EntityRowCard.
//
// All tests use explicit assertions — no snapshots.
// ---------------------------------------------------------------------------

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { DataStateBadge } from "../src/shared/components/state";
import { StatusPill } from "../src/shared/components/state";
import { TrustStrip } from "../src/shared/components/trust";
import { FeederHealthChip } from "../src/shared/components/trust";
import { PanelShell } from "../src/shared/components/layout";
import {
  EmptyState,
  ErrorState,
  UnavailableState,
  LoadingSkeleton,
} from "../src/shared/components/feedback";
import { EntityRowCard } from "../src/shared/components/entity";

// ---------------------------------------------------------------------------
// DataStateBadge
// ---------------------------------------------------------------------------
describe("DataStateBadge", () => {
  it("renders LIVE badge with emerald styling", () => {
    render(<DataStateBadge dataState="live" />);
    const badge = screen.getByText("LIVE");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("emerald");
  });

  it("renders STALE badge with amber styling", () => {
    render(<DataStateBadge dataState="stale" />);
    const badge = screen.getByText("STALE");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("amber");
  });

  it("renders UNAVAILABLE badge with red styling", () => {
    render(<DataStateBadge dataState="unavailable" />);
    const badge = screen.getByText("UNAVAILABLE");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("red");
  });

  it("renders DEMO-FALLBACK badge with purple styling", () => {
    render(<DataStateBadge dataState="demo-fallback" />);
    const badge = screen.getByText("DEMO-FALLBACK");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("purple");
  });

  it("renders UNKNOWN for null dataState", () => {
    render(<DataStateBadge dataState={null} />);
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// StatusPill
// ---------------------------------------------------------------------------
describe("StatusPill", () => {
  it("renders label text", () => {
    render(<StatusPill label="bullish" />);
    expect(screen.getByText("bullish")).toBeInTheDocument();
  });

  it("renders with positive variant styling", () => {
    render(<StatusPill label="long" variant="positive" />);
    const pill = screen.getByText("long");
    expect(pill.className).toContain("emerald");
  });

  it("renders with negative variant styling", () => {
    render(<StatusPill label="short" variant="negative" />);
    const pill = screen.getByText("short");
    expect(pill.className).toContain("red");
  });

  it("renders with warning variant styling", () => {
    render(<StatusPill label="caution" variant="warning" />);
    const pill = screen.getByText("caution");
    expect(pill.className).toContain("amber");
  });

  it("returns null for empty label", () => {
    const { container } = render(<StatusPill label="" />);
    expect(container.innerHTML).toBe("");
  });
});

// ---------------------------------------------------------------------------
// TrustStrip
// ---------------------------------------------------------------------------
describe("TrustStrip", () => {
  it("renders data_state badge and feeder chip", () => {
    render(
      <TrustStrip
        dataState="live"
        generatedAt="2026-03-13T10:00:00Z"
        feederHealth={{
          status: "ok",
          ingested_at: "2026-03-13T10:00:00Z",
          age_seconds: 120,
          stale: false,
          source_health: {},
        }}
        feederLoading={false}
        feederError={false}
      />,
    );
    expect(screen.getByText("LIVE")).toBeInTheDocument();
    expect(screen.getByText(/Feeder/)).toBeInTheDocument();
  });

  it("renders without timestamp when generatedAt is null", () => {
    render(
      <TrustStrip
        dataState="live"
        generatedAt={null}
        feederHealth={undefined}
        feederLoading={true}
        feederError={false}
      />,
    );
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });

  it("renders with all optional props missing", () => {
    render(
      <TrustStrip
        dataState={null}
        generatedAt={null}
        feederHealth={undefined}
        feederLoading={false}
        feederError={true}
      />,
    );
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
    expect(screen.getByText("Feeder")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// FeederHealthChip
// ---------------------------------------------------------------------------
describe("FeederHealthChip", () => {
  it("renders healthy state with emerald dot", () => {
    const { container } = render(
      <FeederHealthChip
        health={{
          status: "ok",
          ingested_at: "2026-03-13T10:00:00Z",
          age_seconds: 30,
          stale: false,
          source_health: {},
        }}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByText(/Feeder 30s/)).toBeInTheDocument();
    expect(container.querySelector(".bg-emerald-400")).not.toBeNull();
  });

  it("renders stale state with amber dot", () => {
    const { container } = render(
      <FeederHealthChip
        health={{
          status: "ok",
          ingested_at: "2026-03-12T10:00:00Z",
          age_seconds: 7200,
          stale: true,
          source_health: {},
        }}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByText(/Feeder 2h/)).toBeInTheDocument();
    expect(container.querySelector(".bg-amber-400")).not.toBeNull();
  });

  it("renders unavailable state on error", () => {
    render(
      <FeederHealthChip health={undefined} isLoading={false} isError={true} />,
    );
    expect(screen.getByText("Feeder")).toBeInTheDocument();
    expect(screen.getByTitle("Feeder health unavailable")).toBeInTheDocument();
  });

  it("renders loading state with pulse animation", () => {
    const { container } = render(
      <FeederHealthChip health={undefined} isLoading={true} isError={false} />,
    );
    expect(screen.getByText(/Feeder/)).toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
  });

  it("renders unavailable when health is undefined and not loading", () => {
    render(
      <FeederHealthChip
        health={undefined}
        isLoading={false}
        isError={false}
      />,
    );
    expect(screen.getByTitle("Feeder health unavailable")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PanelShell
// ---------------------------------------------------------------------------
describe("PanelShell", () => {
  it("renders children", () => {
    render(
      <PanelShell>
        <div data-testid="child">Hello</div>
      </PanelShell>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(
      <PanelShell className="custom-class">
        <span>Content</span>
      </PanelShell>,
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });
});

// ---------------------------------------------------------------------------
// EmptyState
// ---------------------------------------------------------------------------
describe("EmptyState", () => {
  it("renders default message", () => {
    render(<EmptyState />);
    expect(screen.getByText("No triage items")).toBeInTheDocument();
  });

  it("renders custom message and description", () => {
    render(
      <EmptyState message="Nothing here" description="Try again later." />,
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try again later.")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// UnavailableState
// ---------------------------------------------------------------------------
describe("UnavailableState", () => {
  it("renders default message", () => {
    render(<UnavailableState />);
    expect(screen.getByText("Data unavailable")).toBeInTheDocument();
  });

  it("renders custom message", () => {
    render(<UnavailableState message="Source offline" />);
    expect(screen.getByText("Source offline")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ErrorState
// ---------------------------------------------------------------------------
describe("ErrorState", () => {
  it("renders default error message", () => {
    render(<ErrorState />);
    expect(screen.getByText("Failed to load data")).toBeInTheDocument();
  });

  it("renders custom message and detail", () => {
    render(<ErrorState message="Request failed" detail="500 Server Error" />);
    expect(screen.getByText("Request failed")).toBeInTheDocument();
    expect(screen.getByText("500 Server Error")).toBeInTheDocument();
  });

  it("fires onRetry callback when retry button clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not show retry button when onRetry is not provided", () => {
    render(<ErrorState />);
    expect(screen.queryByText("Retry")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// LoadingSkeleton
// ---------------------------------------------------------------------------
describe("LoadingSkeleton", () => {
  it("renders without error", () => {
    const { container } = render(<LoadingSkeleton />);
    expect(screen.getByRole("status", { name: /loading/i })).toBeInTheDocument();
    // Default 5 rows
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(5);
  });

  it("renders custom row count", () => {
    const { container } = render(<LoadingSkeleton rows={3} />);
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// EntityRowCard
// ---------------------------------------------------------------------------
describe("EntityRowCard", () => {
  it("renders label and description", () => {
    render(
      <EntityRowCard label="EURUSD" description="Strong trend" />,
    );
    expect(screen.getByText("EURUSD")).toBeInTheDocument();
    expect(screen.getByText("Strong trend")).toBeInTheDocument();
  });

  it("renders with pill and meta", () => {
    render(
      <EntityRowCard
        label="XAUUSD"
        pill={{ label: "bearish", variant: "negative" }}
        meta="65%"
        description="Reversal pattern"
      />,
    );
    expect(screen.getByText("XAUUSD")).toBeInTheDocument();
    expect(screen.getByText("bearish")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("renders badge when provided", () => {
    render(
      <EntityRowCard
        label="TEST"
        badge={{ text: "STALE", className: "border-amber-700/50 bg-amber-900/40 text-amber-400" }}
      />,
    );
    expect(screen.getByText("STALE")).toBeInTheDocument();
  });

  it("fires onClick handler", () => {
    const onClick = vi.fn();
    render(<EntityRowCard label="CLICK" onClick={onClick} />);
    fireEvent.click(screen.getByText("CLICK"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders dash placeholder when no description", () => {
    render(<EntityRowCard label="EMPTY" />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("has hover affordance arrow", () => {
    render(<EntityRowCard label="ARROW" />);
    expect(screen.getByText("›")).toBeInTheDocument();
  });
});
