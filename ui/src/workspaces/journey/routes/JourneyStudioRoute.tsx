// ---------------------------------------------------------------------------
// JourneyStudioRoute — route wrapper for the Journey Studio workspace.
// Renders JourneyStudioPage with route parameter extraction handled by
// the page component via useParams.
// ---------------------------------------------------------------------------

import { JourneyStudioPage } from "../components/JourneyStudioPage";

export function JourneyStudioRoute() {
  return <JourneyStudioPage />;
}
