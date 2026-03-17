// ---------------------------------------------------------------------------
// TraceEdgeList — conservative trace edge rendering per PR_OPS_5_SPEC §11.3.
// Uses backend from, to, type — no semantic invention beyond contract.
// Distinct from roster relationships (run-scoped only).
// ---------------------------------------------------------------------------

import type { TraceEdge } from "@shared/api/ops";

export interface TraceEdgeListProps {
  edges: TraceEdge[];
}

const EDGE_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  supports: { label: "SUPPORTS", className: "text-teal-400" },
  challenges: { label: "CHALLENGES", className: "text-amber-400" },
  feeds: { label: "FEEDS", className: "text-cyan-400" },
  synthesizes: { label: "SYNTHESIZES", className: "text-purple-400" },
  overrides: { label: "OVERRIDES", className: "text-red-400" },
  degraded_dependency: { label: "DEGRADED DEP", className: "text-amber-500" },
  recovered_dependency: { label: "RECOVERED DEP", className: "text-teal-500" },
};

export function TraceEdgeList({ edges }: TraceEdgeListProps) {
  if (edges.length === 0) return null;

  return (
    <section data-testid="trace-edge-list">
      <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-gray-500">
        Trace Edges
      </h4>
      <div className="space-y-1">
        {edges.map((edge, idx) => {
          const edgeType = edge.type ?? "unknown";
          const edgeFrom = edge.from ?? "unknown";
          const edgeTo = edge.to ?? "unknown";
          const style = EDGE_TYPE_STYLES[edgeType] ?? {
            label: edgeType.toUpperCase(),
            className: "text-gray-400",
          };
          return (
            <div
              key={`${edgeFrom}-${edgeTo}-${idx}`}
              className="flex items-center gap-2 rounded border border-gray-800/40 bg-gray-900/40 px-3 py-1.5"
              data-testid={`trace-edge-${edgeFrom}-${edgeTo}`}
              title={edge.summary ?? undefined}
            >
              <span className="text-xs text-gray-300 font-medium truncate">
                {edgeFrom}
              </span>
              <span className={`shrink-0 text-[10px] font-bold uppercase tracking-wider ${style.className}`}>
                {style.label}
              </span>
              <span className="text-[10px] text-gray-600">&rarr;</span>
              <span className="text-xs text-gray-300 font-medium truncate">
                {edgeTo}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
