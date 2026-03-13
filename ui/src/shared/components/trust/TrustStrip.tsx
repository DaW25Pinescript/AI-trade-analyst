// ---------------------------------------------------------------------------
// TrustStrip — data_state badge + feeder health chip + timestamp grouped.
// Per DESIGN_NOTES §2: these three must never be separated.
// ---------------------------------------------------------------------------

import type { FeederHealth } from "@shared/api/feeder";
import { DataStateBadge } from "@shared/components/state/DataStateBadge";
import { FeederHealthChip } from "./FeederHealthChip";

interface TrustStripProps {
  dataState: string | null;
  generatedAt: string | null;
  feederHealth: FeederHealth | undefined;
  feederLoading: boolean;
  feederError: boolean;
}

export function TrustStrip({
  dataState,
  generatedAt,
  feederHealth,
  feederLoading,
  feederError,
}: TrustStripProps) {
  return (
    <div className="flex items-center gap-3">
      <DataStateBadge dataState={dataState} />
      <FeederHealthChip
        health={feederHealth}
        isLoading={feederLoading}
        isError={feederError}
      />
      {generatedAt && (
        <span
          className="text-xs text-gray-500"
          title={`Generated: ${generatedAt}`}
        >
          {formatTimestamp(generatedAt)}
        </span>
      )}
    </div>
  );
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
