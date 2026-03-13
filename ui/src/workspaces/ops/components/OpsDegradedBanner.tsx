// ---------------------------------------------------------------------------
// OpsDegradedBanner — workspace-level degraded banner.
// Shown when roster succeeds but health fails or is unavailable.
// Per AGENT_OPS_CONTRACT.md §5.9.
// ---------------------------------------------------------------------------

export interface OpsDegradedBannerProps {
  variant: "health-failed" | "empty-health";
}

const MESSAGES: Record<OpsDegradedBannerProps["variant"], { title: string; detail: string }> = {
  "health-failed": {
    title: "Health data unavailable",
    detail:
      "Agent health snapshot could not be loaded. Roster structure is shown without health status. This is expected if the system has not completed a run.",
  },
  "empty-health": {
    title: "Health data not yet available",
    detail:
      "The system has started but no health data has been projected yet. Roster structure is shown without health indicators.",
  },
};

export function OpsDegradedBanner({ variant }: OpsDegradedBannerProps) {
  const msg = MESSAGES[variant];
  return (
    <div
      className="flex items-start gap-3 rounded border border-amber-800/50 bg-amber-950/20 px-4 py-3"
      role="status"
      aria-label="Degraded health status"
    >
      <span className="mt-0.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.5)]" />
      <div>
        <p className="text-sm font-medium text-amber-300">{msg.title}</p>
        <p className="mt-1 text-xs text-amber-500/80">{msg.detail}</p>
      </div>
    </div>
  );
}
