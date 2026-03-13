import {
  createHashRouter,
  Navigate,
  RouterProvider,
} from "react-router-dom";
import { AppShell } from "./AppShell";
import { TriageBoardPage } from "@workspaces/triage/routes/TriageBoardPage";
import { WorkspacePlaceholder } from "@shared/components/WorkspacePlaceholder";
import { NotFoundPage } from "@shared/components/NotFoundPage";

const router = createHashRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/triage" replace /> },
      { path: "triage", element: <TriageBoardPage /> },
      {
        path: "journey/:asset",
        element: <WorkspacePlaceholder name="Journey" />,
      },
      {
        path: "analysis",
        element: <WorkspacePlaceholder name="Analysis" />,
      },
      {
        path: "journal",
        element: <WorkspacePlaceholder name="Journal" />,
      },
      {
        path: "review",
        element: <WorkspacePlaceholder name="Review" />,
      },
      { path: "ops", element: <WorkspacePlaceholder name="Ops" /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
