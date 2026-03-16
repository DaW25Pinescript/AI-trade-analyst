import {
  createHashRouter,
  Navigate,
  RouterProvider,
} from "react-router-dom";
import { AppShell } from "./AppShell";
import { TriageBoardPage } from "@workspaces/triage/routes/TriageBoardPage";
import { JourneyStudioRoute } from "@workspaces/journey/routes/JourneyStudioRoute";
import { AnalysisRunRoute } from "@workspaces/analysis/routes/AnalysisRunRoute";
import { AgentOpsRoute } from "@workspaces/ops/routes/AgentOpsRoute";
import { JournalReviewRoute } from "@workspaces/journal/routes/JournalReviewRoute";
import { ReflectRoute } from "@workspaces/reflect/routes/ReflectRoute";
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
        element: <JourneyStudioRoute />,
      },
      {
        path: "analysis",
        element: <AnalysisRunRoute />,
      },
      {
        path: "journal",
        element: <JournalReviewRoute />,
      },
      { path: "ops", element: <AgentOpsRoute /> },
      { path: "reflect", element: <ReflectRoute /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
