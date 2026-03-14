// ---------------------------------------------------------------------------
// JourneyRightRail — conditional context panels driven by bootstrap field
// presence. Per UI_WORKSPACES §6.4: panels appear for present fields only;
// single "Bootstrap unavailable" fallback when data_state = unavailable.
// ---------------------------------------------------------------------------

import type { JourneyWorkspaceViewModel } from "../adapters/journeyViewModel";

export interface JourneyRightRailProps {
  vm: JourneyWorkspaceViewModel;
}

export function JourneyRightRail({ vm }: JourneyRightRailProps) {
  const { rightRail } = vm;

  if (rightRail.allUnavailable) {
    return (
      <div
        className="rounded-lg border border-dashed border-gray-700 bg-gray-900/50 p-6 text-center"
        data-testid="rail-unavailable"
      >
        <p className="text-sm text-gray-500">Bootstrap context unavailable</p>
        <p className="mt-1 text-xs text-gray-600">
          No analysis data available for this asset yet.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="right-rail">
      {rightRail.showArbiterSummary && (
        <ArbiterPanel vm={vm} />
      )}
      {rightRail.showSetups && (
        <SetupsPanel vm={vm} />
      )}
      {rightRail.showNoTradeWarning && (
        <NoTradePanel conditions={vm.noTradeConditions} />
      )}
      {rightRail.showExplanation && (
        <ExplanationPanel vm={vm} />
      )}
    </div>
  );
}

// ---- Panel sub-components ----

function ArbiterPanel({ vm }: { vm: JourneyWorkspaceViewModel }) {
  return (
    <div
      className="rounded-lg border border-gray-800 bg-gray-900/60 p-4"
      data-testid="panel-arbiter"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
        Arbiter Decision
      </h3>
      <div className="space-y-2">
        {vm.arbiterBias && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Bias</span>
            <span
              className={`text-sm font-medium ${
                vm.arbiterBias === "bullish"
                  ? "text-emerald-400"
                  : vm.arbiterBias === "bearish"
                    ? "text-red-400"
                    : "text-gray-400"
              }`}
            >
              {vm.arbiterBias.toUpperCase()}
            </span>
          </div>
        )}
        {vm.arbiterDecision && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Decision</span>
            <span className="text-sm text-gray-300">
              {vm.arbiterDecision.replace(/_/g, " ")}
            </span>
          </div>
        )}
        {vm.arbiterConfidence !== null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Confidence</span>
            <span className="text-sm text-gray-300">
              {(vm.arbiterConfidence * 100).toFixed(0)}%
            </span>
          </div>
        )}
        {vm.analystAgreement !== null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Agreement</span>
            <span className="text-sm text-gray-300">
              {vm.analystAgreement}%
            </span>
          </div>
        )}
        {vm.riskOverride && (
          <div className="mt-2 rounded border border-amber-800/50 bg-amber-950/20 px-2 py-1">
            <span className="text-xs text-amber-400">Risk override applied</span>
          </div>
        )}
        {vm.arbiterNotes && (
          <p className="mt-2 text-xs text-gray-500 italic">{vm.arbiterNotes}</p>
        )}
      </div>
    </div>
  );
}

function SetupsPanel({ vm }: { vm: JourneyWorkspaceViewModel }) {
  return (
    <div
      className="rounded-lg border border-gray-800 bg-gray-900/60 p-4"
      data-testid="panel-setups"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
        Approved Setups ({vm.approvedSetups.length})
      </h3>
      <div className="space-y-2">
        {vm.approvedSetups.map((setup, i) => (
          <div
            key={i}
            className="rounded border border-gray-800/50 bg-gray-950/50 p-2"
          >
            <p className="text-xs font-medium text-gray-300">{setup.type}</p>
            <div className="mt-1 grid grid-cols-2 gap-1 text-xs text-gray-500">
              <span>Entry: {setup.entryZone}</span>
              <span>Stop: {setup.stop}</span>
              <span>R:R {setup.rrEstimate.toFixed(1)}</span>
              <span>Conf: {(setup.confidence * 100).toFixed(0)}%</span>
            </div>
            {setup.targets.length > 0 && (
              <p className="mt-1 text-xs text-gray-600">
                Targets: {setup.targets.join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function NoTradePanel({ conditions }: { conditions: string[] }) {
  return (
    <div
      className="rounded-lg border border-red-800/50 bg-red-950/20 p-4"
      data-testid="panel-no-trade"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-red-500 mb-2">
        No-Trade Conditions
      </h3>
      <ul className="space-y-1">
        {conditions.map((c, i) => (
          <li key={i} className="text-xs text-red-400">
            {c}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ExplanationPanel({ vm }: { vm: JourneyWorkspaceViewModel }) {
  return (
    <div
      className="rounded-lg border border-gray-800 bg-gray-900/60 p-4"
      data-testid="panel-explanation"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
        Reasoning
      </h3>
      {vm.reasoningSummary ? (
        <p className="text-xs text-gray-400 whitespace-pre-wrap">
          {vm.reasoningSummary}
        </p>
      ) : (
        <p className="text-xs text-gray-600 italic">
          Explanation data available but no summary text.
        </p>
      )}
    </div>
  );
}
