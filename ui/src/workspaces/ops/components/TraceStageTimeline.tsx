// ---------------------------------------------------------------------------
// TraceStageTimeline — ordered stage timeline per PR_OPS_5_SPEC §11.1.
// Stages ordered by stage.stage_index (ascending). Status-aware. Duration shown.
// ---------------------------------------------------------------------------

import type { TraceStage } from "@shared/api/ops";

export interface TraceStageTimelineProps {
  stages: TraceStage[];
  isPartial: boolean;
}

const STATUS_STYLES: Record<string, { dot: string; text: string }> = {
  completed: {
    dot: "bg-teal-400 shadow-[0_0_6px_rgba(45,212,191,0.5)]",
    text: "text-teal-400",
  },
  running: {
    dot: "bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.5)]",
    text: "text-cyan-400",
  },
  failed: {
    dot: "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]",
    text: "text-red-400",
  },
  skipped: {
    dot: "bg-gray-600",
    text: "text-gray-500",
  },
};

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatStageName(stage: string | undefined | null): string {
  if (!stage) return "UNKNOWN";
  return stage.replace(/_/g, " ").toUpperCase();
}

export function TraceStageTimeline({ stages, isPartial }: TraceStageTimelineProps) {
  const sorted = [...stages].sort((a, b) => (a.stage_index ?? 0) - (b.stage_index ?? 0));

  return (
    <section data-testid="trace-stage-timeline">
      <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-gray-500">
        Stage Timeline
      </h4>
      <div className="space-y-1">
        {sorted.map((stage, idx) => {
          const status = stage.status ?? "skipped";
          const style = STATUS_STYLES[status] ?? STATUS_STYLES.skipped;
          const stageKey = stage.stage ?? `stage-${idx}`;
          return (
            <div
              key={stageKey}
              className="flex items-center gap-3 rounded border border-gray-800/40 bg-gray-900/40 px-3 py-2"
              data-testid={`trace-stage-${stageKey}`}
            >
              {/* Order index */}
              <span className="w-5 shrink-0 text-center text-[10px] font-bold text-gray-600">
                {idx + 1}
              </span>
              {/* Status dot */}
              <span
                className={`inline-block h-2 w-2 shrink-0 rounded-full ${style.dot}`}
              />
              {/* Stage name */}
              <span className="min-w-0 flex-1 text-sm font-medium text-gray-300">
                {formatStageName(stage.stage)}
              </span>
              {/* Status label */}
              <span className={`shrink-0 text-[10px] font-bold uppercase tracking-wider ${style.text}`}>
                {status}
              </span>
              {/* Duration */}
              <span className="w-16 shrink-0 text-right text-xs text-gray-500">
                {formatDuration(stage.duration_ms)}
              </span>
            </div>
          );
        })}
      </div>
      {isPartial && (
        <div
          className="mt-2 flex items-center gap-2 rounded border border-amber-800/40 bg-amber-950/20 px-3 py-2"
          data-testid="partial-run-indicator"
        >
          <span className="inline-block h-2 w-2 rounded-full bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.5)]" />
          <span className="text-xs text-amber-400">
            Partial run — some stages may be incomplete
          </span>
        </div>
      )}
    </section>
  );
}
