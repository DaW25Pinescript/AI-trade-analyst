// ---------------------------------------------------------------------------
// AgentDetailSidebar — backend-backed detail sidebar per PR_OPS_5_SPEC §10.
// Fetches from GET /ops/agent-detail/{entity_id} via useAgentDetail hook.
// Discriminated rendering: switch on entity_type, NOT type_specific.variant.
// ---------------------------------------------------------------------------

import { useAgentDetail } from "@shared/hooks";
import { LoadingSkeleton } from "@shared/components/feedback";
import type {
  AgentDetailResponse,
  PersonaDetail,
  OfficerDetail,
  ArbiterDetail,
  SubsystemDetail,
} from "@shared/api/ops";

export interface AgentDetailSidebarProps {
  entityId: string;
  onClose: () => void;
  onSelectRun?: (runId: string) => void;
}

// ---- Health/run state labels ----

const HEALTH_LABELS: Record<string, { text: string; className: string }> = {
  live: { text: "Live", className: "text-teal-400" },
  recovered: { text: "Recovered", className: "text-teal-400" },
  stale: { text: "Stale", className: "text-amber-400" },
  degraded: { text: "Degraded", className: "text-amber-400" },
  unavailable: { text: "Unavailable", className: "text-red-400" },
};

const RUN_LABELS: Record<string, { text: string; className: string }> = {
  idle: { text: "Idle", className: "text-gray-400" },
  running: { text: "Running", className: "text-cyan-400" },
  completed: { text: "Completed", className: "text-teal-400" },
  failed: { text: "Failed", className: "text-red-400" },
};

// ---- Detail row component ----

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="w-28 shrink-0 text-[11px] font-medium uppercase tracking-wider text-gray-600">
        {label}
      </span>
      <span className="text-sm text-gray-300">{children}</span>
    </div>
  );
}

// ---- Type-specific sections — switch on entity_type ----

function PersonaSection({ detail }: { detail: PersonaDetail }) {
  return (
    <div data-testid="detail-persona-section">
      <DetailRow label="Analysis Focus">
        {detail.analysis_focus.join(", ") || "—"}
      </DetailRow>
      <DetailRow label="Verdict Style">{detail.verdict_style}</DetailRow>
      <DetailRow label="Dept Role">{detail.department_role}</DetailRow>
      {detail.typical_outputs.length > 0 && (
        <DetailRow label="Outputs">
          {detail.typical_outputs.join(", ")}
        </DetailRow>
      )}
    </div>
  );
}

function OfficerSection({ detail }: { detail: OfficerDetail }) {
  return (
    <div data-testid="detail-officer-section">
      <DetailRow label="Domain">{detail.officer_domain}</DetailRow>
      <DetailRow label="Data Sources">
        {detail.data_sources.join(", ") || "—"}
      </DetailRow>
      <DetailRow label="Monitored">
        {detail.monitored_surfaces.join(", ") || "—"}
      </DetailRow>
      {detail.update_cadence && (
        <DetailRow label="Cadence">{detail.update_cadence}</DetailRow>
      )}
    </div>
  );
}

function ArbiterSection({ detail }: { detail: ArbiterDetail }) {
  return (
    <div data-testid="detail-arbiter-section">
      <DetailRow label="Method">{detail.synthesis_method}</DetailRow>
      <DetailRow label="Veto Gates">
        {detail.veto_gates.join(", ") || "None"}
      </DetailRow>
      <DetailRow label="Quorum">{detail.quorum_rule}</DetailRow>
      <DetailRow label="Override">
        {detail.override_capable ? "Yes" : "No"}
      </DetailRow>
      <DetailRow label="Policy">{detail.policy_summary}</DetailRow>
    </div>
  );
}

function SubsystemSection({ detail }: { detail: SubsystemDetail }) {
  return (
    <div data-testid="detail-subsystem-section">
      <DetailRow label="Type">{detail.subsystem_type}</DetailRow>
      <DetailRow label="Resources">
        {detail.monitored_resources.join(", ") || "—"}
      </DetailRow>
      {detail.health_check_method && (
        <DetailRow label="Health Check">{detail.health_check_method}</DetailRow>
      )}
      <DetailRow label="Runtime Role">{detail.runtime_role}</DetailRow>
    </div>
  );
}

/** Render type-specific section — switches on entity_type per §10.3 */
function TypeSpecificSection({ detail }: { detail: AgentDetailResponse }) {
  switch (detail.entity_type) {
    case "persona":
      return <PersonaSection detail={detail.type_specific as PersonaDetail} />;
    case "officer":
      return <OfficerSection detail={detail.type_specific as OfficerDetail} />;
    case "arbiter":
      return <ArbiterSection detail={detail.type_specific as ArbiterDetail} />;
    case "subsystem":
      return <SubsystemSection detail={detail.type_specific as SubsystemDetail} />;
    default:
      return null;
  }
}

// ---- Main sidebar component ----

export function AgentDetailSidebar({
  entityId,
  onClose,
  onSelectRun,
}: AgentDetailSidebarProps) {
  const detailQuery = useAgentDetail(entityId);

  return (
    <aside
      className="rounded-lg border border-gray-700/50 bg-gray-900/60 p-4"
      data-testid="agent-detail-sidebar"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-200">
          {detailQuery.data?.display_name ?? entityId}
        </h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          aria-label="Close detail panel"
        >
          Close
        </button>
      </div>

      {/* Loading */}
      {detailQuery.isLoading && <LoadingSkeleton rows={4} />}

      {/* Error — 404 or fetch failure */}
      {detailQuery.isError && (
        <div data-testid="detail-error">
          <p className="text-sm text-red-400">
            {detailQuery.error?.message?.includes("not found") ||
            detailQuery.error?.message?.includes("ENTITY_NOT_FOUND")
              ? "Entity not found \u2014 it may no longer be in the active roster."
              : "Detail unavailable"}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {detailQuery.error?.message}
          </p>
        </div>
      )}

      {/* Success — full detail rendering */}
      {detailQuery.data && (
        <DetailContent
          detail={detailQuery.data}
          onSelectRun={onSelectRun}
        />
      )}
    </aside>
  );
}

function DetailContent({
  detail,
  onSelectRun,
}: {
  detail: AgentDetailResponse;
  onSelectRun?: (runId: string) => void;
}) {
  const healthLabel = HEALTH_LABELS[detail.status.health_state];
  const runLabel = RUN_LABELS[detail.status.run_state];
  const isStale = detail.data_state === "stale";
  const isHealthUnavailable = detail.status.health_state === "unavailable";

  return (
    <div className="space-y-0 divide-y divide-gray-800/50" data-testid="detail-content">
      {/* Stale indicator */}
      {isStale && (
        <div className="pb-2">
          <span className="text-[10px] font-bold uppercase text-amber-400" data-testid="detail-stale-indicator">
            Data may be stale
          </span>
        </div>
      )}

      {/* Identity block */}
      <DetailRow label="ID">{detail.entity_id}</DetailRow>
      <DetailRow label="Type">
        <span className="uppercase">{detail.entity_type}</span>
      </DetailRow>
      <DetailRow label="Role">{detail.identity.role}</DetailRow>
      <DetailRow label="Purpose">{detail.identity.purpose}</DetailRow>
      {detail.department && (
        <DetailRow label="Department">
          <span className="uppercase">{detail.department}</span>
        </DetailRow>
      )}

      {/* Status block */}
      <DetailRow label="Health">
        {isHealthUnavailable ? (
          <span className="text-red-400" data-testid="detail-health-unavailable">
            Unavailable — health data not projected
          </span>
        ) : healthLabel ? (
          <span className={healthLabel.className}>{healthLabel.text}</span>
        ) : (
          "—"
        )}
      </DetailRow>
      <DetailRow label="Run State">
        {runLabel ? (
          <span className={runLabel.className}>{runLabel.text}</span>
        ) : (
          "—"
        )}
      </DetailRow>
      {detail.status.last_active_at && (
        <DetailRow label="Last Active">
          {new Date(detail.status.last_active_at).toLocaleString()}
        </DetailRow>
      )}
      {detail.status.last_run_id && (
        <DetailRow label="Last Run">
          {onSelectRun ? (
            <button
              type="button"
              onClick={() => onSelectRun(detail.status.last_run_id!)}
              className="text-cyan-400 hover:text-cyan-300 underline"
            >
              {detail.status.last_run_id}
            </button>
          ) : (
            detail.status.last_run_id
          )}
        </DetailRow>
      )}
      {detail.status.health_summary && (
        <DetailRow label="Summary">{detail.status.health_summary}</DetailRow>
      )}

      {/* Dependencies */}
      {detail.dependencies.length > 0 && (
        <div className="py-2">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-gray-600">
            Dependencies
          </p>
          {detail.dependencies.map((dep) => (
            <div
              key={`${dep.direction}-${dep.entity_id}`}
              className="flex items-center gap-2 py-0.5"
            >
              <span className="text-[10px] uppercase text-gray-600 w-20 shrink-0">
                {dep.direction}
              </span>
              <span className="text-xs text-gray-300">{dep.display_name}</span>
              <span className="text-[10px] text-gray-500 uppercase">
                {dep.relationship_type}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Recent participation */}
      {detail.recent_participation.length > 0 && (
        <div className="py-2" data-testid="detail-recent-participation">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-gray-600">
            Recent Participation
          </p>
          {detail.recent_participation.map((rp) => (
            <div
              key={rp.run_id}
              className="flex items-center gap-2 py-0.5"
            >
              <span className="text-xs text-gray-400 font-mono truncate max-w-[120px]">
                {rp.run_id}
              </span>
              {rp.verdict_direction && (
                <span className="text-[10px] uppercase text-gray-500">
                  {rp.verdict_direction}
                </span>
              )}
              {rp.was_overridden && (
                <span className="text-[10px] font-bold uppercase text-amber-400">
                  Overridden
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Recent warnings */}
      {detail.recent_warnings.length > 0 && (
        <div className="py-2">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-gray-600">
            Warnings
          </p>
          {detail.recent_warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-400/80 py-0.5">
              {w}
            </p>
          ))}
        </div>
      )}

      {/* Capabilities */}
      {detail.identity.capabilities.length > 0 && (
        <div className="py-2">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-gray-600">
            Capabilities
          </p>
          <div className="flex flex-wrap gap-1.5">
            {detail.identity.capabilities.map((cap) => (
              <span
                key={cap}
                className="rounded bg-gray-800/60 px-2 py-0.5 text-xs text-gray-400"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Type-specific section */}
      <div className="py-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-cyan-600">
          {detail.entity_type} Details
        </p>
        <TypeSpecificSection detail={detail} />
      </div>
    </div>
  );
}
