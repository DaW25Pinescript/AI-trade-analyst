import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TriageBoardPage } from "../src/workspaces/triage/routes/TriageBoardPage";
import { WorkspacePlaceholder } from "../src/shared/components/WorkspacePlaceholder";
import { NotFoundPage } from "../src/shared/components/NotFoundPage";

function renderWithProviders(element: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>,
  );
}

describe("TriageBoardPage", () => {
  it("renders the triage placeholder", () => {
    const router = createMemoryRouter(
      [{ path: "/", element: <TriageBoardPage /> }],
      { initialEntries: ["/"] },
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("Triage Board")).toBeInTheDocument();
    expect(
      screen.getByText(/Phase 1 foundation shell/),
    ).toBeInTheDocument();
  });
});

describe("WorkspacePlaceholder", () => {
  it("renders the workspace name", () => {
    renderWithProviders(<WorkspacePlaceholder name="Analysis" />);
    expect(screen.getByText("Analysis")).toBeInTheDocument();
    expect(screen.getByText(/Workspace shell/)).toBeInTheDocument();
  });
});

describe("NotFoundPage", () => {
  it("renders 404 with link to triage", () => {
    const router = createMemoryRouter(
      [{ path: "/", element: <NotFoundPage /> }],
      { initialEntries: ["/"] },
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("Go to Triage")).toBeInTheDocument();
  });
});

describe("API types compile", () => {
  it("triage types are importable", async () => {
    const mod = await import("../src/shared/api/triage");
    expect(typeof mod.fetchWatchlistTriage).toBe("function");
    expect(typeof mod.triggerTriage).toBe("function");
  });

  it("client types are importable", async () => {
    const mod = await import("../src/shared/api/client");
    expect(typeof mod.apiFetch).toBe("function");
  });
});
