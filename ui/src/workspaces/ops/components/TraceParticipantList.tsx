// ---------------------------------------------------------------------------
// TraceParticipantList — participant cards per PR_OPS_5_SPEC §11.2.
// Shows entity_type, participation_status, and available contribution fields.
// Renders what is present — does not fabricate missing fields.
// ---------------------------------------------------------------------------

import type { TraceParticipant } from "@shared/api/ops";

export interface TraceParticipantListProps {
  participants: TraceParticipant[];
}

const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  active: { label: "ACTIVE", className: "text-teal-400" },
  skipped: { label: "SKIPPED", className: "text-gray-500" },
  failed: { label: "FAILED", className: "text-red-400" },
};

export function TraceParticipantList({ participants }: TraceParticipantListProps) {
  if (participants.length === 0) return null;

  return (
    <section data-testid="trace-participant-list">
      <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-gray-500">
        Participants
      </h4>
      <div className="space-y-2">
        {participants.map((p) => {
          const style = STATUS_STYLES[p.participation_status] ?? STATUS_STYLES.skipped;
          const c = p.contribution;

          return (
            <div
              key={p.entity_id}
              className="rounded border border-gray-800/40 bg-gray-900/40 p-3"
              data-testid={`participant-${p.entity_id}`}
            >
              {/* Header row */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-semibold text-gray-200 truncate">
                    {p.display_name}
                  </span>
                  <span className="text-[10px] text-gray-500 uppercase">
                    {p.role}
                  </span>
                </div>
                <span className={`shrink-0 text-[10px] font-bold uppercase tracking-wider ${style.className}`}>
                  {style.label}
                </span>
              </div>

              {/* Contribution details — render what is present */}
              <div className="mt-2 space-y-1">
                {c.summary && (
                  <p className="text-xs text-gray-400">{c.summary}</p>
                )}
                <div className="flex flex-wrap gap-3">
                  {c.stance !== null && (
                    <span className="text-[10px] text-gray-500">
                      Stance:{" "}
                      <span className="font-medium text-gray-300 uppercase">
                        {c.stance}
                      </span>
                    </span>
                  )}
                  {c.confidence !== null && (
                    <span className="text-[10px] text-gray-500">
                      Confidence:{" "}
                      <span className="font-medium text-gray-300">
                        {(c.confidence * 100).toFixed(0)}%
                      </span>
                    </span>
                  )}
                  {c.was_overridden && (
                    <span className="text-[10px] font-bold uppercase text-amber-400" data-testid={`override-${p.entity_id}`}>
                      Overridden
                    </span>
                  )}
                </div>
                {c.override_reason && (
                  <p className="text-[10px] text-amber-500/80">
                    Override reason: {c.override_reason}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
