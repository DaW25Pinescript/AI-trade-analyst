// ---------------------------------------------------------------------------
// OpsDataStateBanner — data_state warning banner per PR_OPS_5_SPEC §5.6.
// Renders stale/unavailable indicators for roster or health responses.
// ---------------------------------------------------------------------------

export interface OpsDataStateBannerProps {
  source: "Roster" | "Health";
  state: "stale" | "unavailable";
}

const MESSAGES: Record<
  string,
  Record<OpsDataStateBannerProps["state"], { title: string; detail: string }>
> = {
  Roster: {
    stale: {
      title: "Roster data is stale",
      detail:
        "Roster configuration loaded but may be outdated. A config reload may be pending.",
    },
    unavailable: {
      title: "Roster data unavailable",
      detail: "Roster configuration could not be loaded.",
    },
  },
  Health: {
    stale: {
      title: "Health data is stale",
      detail:
        "Health snapshot exists but observability sources may be outdated. Health badges may not reflect current state.",
    },
    unavailable: {
      title: "Health data unavailable",
      detail:
        "Health projection failed. Roster structure is shown without health indicators.",
    },
  },
};

export function OpsDataStateBanner({ source, state }: OpsDataStateBannerProps) {
  const msg = MESSAGES[source][state];
  const isUnavailable = state === "unavailable";

  return (
    <div
      className={`flex items-start gap-3 rounded border px-4 py-3 ${
        isUnavailable
          ? "border-red-800/50 bg-red-950/20"
          : "border-amber-800/50 bg-amber-950/20"
      }`}
      role="status"
      data-testid={`data-state-banner-${source.toLowerCase()}`}
    >
      <span
        className={`mt-0.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full ${
          isUnavailable
            ? "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]"
            : "bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.5)]"
        }`}
      />
      <div>
        <p
          className={`text-sm font-medium ${
            isUnavailable ? "text-red-300" : "text-amber-300"
          }`}
        >
          {msg.title}
        </p>
        <p
          className={`mt-1 text-xs ${
            isUnavailable ? "text-red-500/80" : "text-amber-500/80"
          }`}
        >
          {msg.detail}
        </p>
      </div>
    </div>
  );
}
