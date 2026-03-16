// ---------------------------------------------------------------------------
// UsageSummaryCard — token/model/cost display from run bundle usage data.
// Shows "Not available" when usage_summary is null.
// ---------------------------------------------------------------------------

interface UsageData {
  totalCalls: string;
  modelsUsed: string;
  totalTokens: string;
  estimatedCost: string;
}

interface UsageSummaryCardProps {
  usage: UsageData | null;
}

export function UsageSummaryCard({ usage }: UsageSummaryCardProps) {
  if (!usage) {
    return (
      <div className="rounded border border-gray-800 bg-gray-900/50 p-4">
        <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
          Usage Summary
        </h4>
        <p className="text-sm text-gray-500">Not available</p>
      </div>
    );
  }

  return (
    <div
      className="rounded border border-gray-800 bg-gray-900/50 p-4"
      data-testid="usage-summary-card"
    >
      <h4 className="mb-3 text-xs font-medium uppercase text-gray-500">
        Usage Summary
      </h4>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-gray-500">Calls:</span>{" "}
          <span className="text-gray-300">{usage.totalCalls}</span>
        </div>
        <div>
          <span className="text-gray-500">Models:</span>{" "}
          <span className="text-gray-300">{usage.modelsUsed}</span>
        </div>
        <div>
          <span className="text-gray-500">Tokens:</span>{" "}
          <span className="text-gray-300">{usage.totalTokens}</span>
        </div>
        <div>
          <span className="text-gray-500">Cost:</span>{" "}
          <span className="text-gray-300">{usage.estimatedCost}</span>
        </div>
      </div>
    </div>
  );
}
