// ---------------------------------------------------------------------------
// CandlestickChart — OHLCV candlestick chart panel (PR-CHART-1 + PR-CHART-2).
//
// Self-contained, failure-tolerant component. If the chart errors,
// loading, or has no data, it does NOT affect trace rendering.
//
// PR-CHART-2 additions: timeframe tabs, run-time marker, verdict annotation.
// Controlled component — TF state owned by AgentOpsPage.
//
// Sources instrument from RunBrowserItem row, not trace endpoint.
// Spec: docs/specs/PR_CHART_1_SPEC.md §6.4
//       docs/specs/PR_CHART_2_SPEC.md §5.2
// ---------------------------------------------------------------------------

import { useRef, useEffect, useCallback } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  ColorType,
  type UTCTimestamp,
} from "lightweight-charts";
import { useMarketData } from "@shared/hooks";
import { LoadingSkeleton } from "@shared/components/feedback";

// ---------------------------------------------------------------------------
// Verdict normalization per §4.4
// ---------------------------------------------------------------------------

type NormalizedVerdict = "BUY" | "SELL" | "NO_TRADE" | "UNKNOWN";

const VERDICT_MAP: Record<string, NormalizedVerdict> = {
  BUY: "BUY",
  LONG: "BUY",
  ENTER_LONG: "BUY",
  SELL: "SELL",
  SHORT: "SELL",
  ENTER_SHORT: "SELL",
  NO_TRADE: "NO_TRADE",
  FLAT: "NO_TRADE",
  SKIP: "NO_TRADE",
};

export function normalizeVerdict(raw: string | null | undefined): NormalizedVerdict {
  if (raw == null || typeof raw !== "string") return "UNKNOWN";
  const upper = raw.trim().toUpperCase();
  return VERDICT_MAP[upper] ?? "UNKNOWN";
}

const VERDICT_STYLES: Record<
  NormalizedVerdict,
  {
    color: string;
    shape: "arrowUp" | "arrowDown" | "circle";
    position: "aboveBar" | "belowBar";
    label: string;
    bgClass: string;
    textClass: string;
  }
> = {
  BUY: {
    color: "#22c55e",
    shape: "arrowUp",
    position: "aboveBar",
    label: "BUY",
    bgClass: "bg-emerald-900/30 border-emerald-700/40",
    textClass: "text-emerald-400",
  },
  SELL: {
    color: "#ef4444",
    shape: "arrowDown",
    position: "belowBar",
    label: "SELL",
    bgClass: "bg-red-900/30 border-red-700/40",
    textClass: "text-red-400",
  },
  NO_TRADE: {
    color: "#f59e0b",
    shape: "circle",
    position: "aboveBar",
    label: "NO_TRADE",
    bgClass: "bg-amber-900/30 border-amber-700/40",
    textClass: "text-amber-400",
  },
  UNKNOWN: {
    color: "#6b7280",
    shape: "circle",
    position: "aboveBar",
    label: "Unknown",
    bgClass: "bg-gray-800/30 border-gray-600/40",
    textClass: "text-gray-400",
  },
};

// ---------------------------------------------------------------------------
// Timestamp helpers
// ---------------------------------------------------------------------------

function parseRunTimestamp(iso: string | null | undefined): number | null {
  if (iso == null || typeof iso !== "string" || iso.trim() === "") return null;
  try {
    const ms = new Date(iso).getTime();
    if (Number.isNaN(ms)) return null;
    return Math.floor(ms / 1000);
  } catch {
    return null;
  }
}

function findNearestCandleIndex(
  candles: { timestamp: number }[],
  targetEpoch: number,
): number {
  // Find the candle at or before the target timestamp (§4.5)
  let best = -1;
  for (let i = 0; i < candles.length; i++) {
    if (candles[i].timestamp <= targetEpoch) {
      best = i;
    } else {
      break; // candles are sorted ascending
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Props interface per §5.2
// ---------------------------------------------------------------------------

export interface CandlestickChartProps {
  instrument: string | null;
  timeframe?: string;
  selectedRunTimestamp?: string | null;
  selectedRunVerdict?: string | null;
  availableTimeframes?: string[] | null;
  selectedTimeframe?: string | null;
  onTimeframeChange?: (tf: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CandlestickChart({
  instrument,
  timeframe = "4h",
  selectedRunTimestamp,
  selectedRunVerdict,
  availableTimeframes,
  selectedTimeframe,
  onTimeframeChange,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<UTCTimestamp> | null>(null);

  // Use selectedTimeframe from parent if available, else fall back to prop default
  const activeTf = selectedTimeframe ?? timeframe;

  const query = useMarketData({ instrument, timeframe: activeTf });

  // Create and manage chart lifecycle
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(55, 65, 81, 0.3)" },
        horzLines: { color: "rgba(55, 65, 81, 0.3)" },
      },
      width: containerRef.current.clientWidth,
      height: 300,
      timeScale: {
        borderColor: "rgba(55, 65, 81, 0.5)",
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: "rgba(55, 65, 81, 0.5)",
      },
      crosshair: {
        horzLine: { color: "rgba(103, 232, 249, 0.3)" },
        vertLine: { color: "rgba(103, 232, 249, 0.3)" },
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "rgba(103, 232, 249, 0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    chart.priceScale("").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Create markers plugin for run-time markers
    const markersPlugin = createSeriesMarkers(candleSeries, []);
    markersPluginRef.current = markersPlugin as ISeriesMarkersPluginApi<UTCTimestamp>;

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      markersPluginRef.current = null;
    };
  }, []);

  // Update chart data when query data changes
  useEffect(() => {
    if (!query.data || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    let candles: typeof query.data.candles;
    try {
      candles = query.data.candles;
      if (!Array.isArray(candles) || candles.length === 0) return;
    } catch {
      return; // malformed OHLCV — degrade silently
    }

    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.timestamp as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    volumeSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.timestamp as UTCTimestamp,
        value: c.volume,
        color:
          c.close >= c.open
            ? "rgba(34, 197, 94, 0.3)"
            : "rgba(239, 68, 68, 0.3)",
      })),
    );

    chartRef.current?.timeScale().fitContent();
  }, [query.data]);

  // Compute marker/alignment state
  const markerState = useMarkerState(query.data?.candles ?? null, selectedRunTimestamp, selectedRunVerdict);

  // Update markers when marker state changes
  useEffect(() => {
    if (!markersPluginRef.current) return;

    if (markerState.type !== "aligned" || !markerState.marker) {
      markersPluginRef.current.setMarkers([]);
      return;
    }

    try {
      markersPluginRef.current.setMarkers([markerState.marker]);
      // Ensure target candle is visible per §4.6
      if (chartRef.current && markerState.marker) {
        chartRef.current.timeScale().scrollToPosition(0, false);
        chartRef.current.timeScale().fitContent();
      }
    } catch {
      // Marker failure must NOT block candlestick rendering
      markersPluginRef.current.setMarkers([]);
    }
  }, [markerState]);

  // Timeframe tab handler
  const handleTabClick = useCallback(
    (tf: string) => {
      onTimeframeChange?.(tf);
    },
    [onTimeframeChange],
  );

  // No instrument selected
  if (!instrument) {
    return null;
  }

  // Determine display state — chart container is ALWAYS rendered
  // so the chart creation useEffect fires on first mount.
  const isLoading = query.isLoading;
  const isError = query.isError;
  const data = query.data;
  const hasCandles = data && Array.isArray(data.candles) && data.candles.length > 0;

  return (
    <div
      className="rounded-lg border border-gray-700/40 bg-gray-900/40 p-3"
      data-testid="chart-panel"
    >
      {/* Header — shown when we have data */}
      {hasCandles && (
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-300">
            {instrument} {activeTf}
          </span>
          <div className="flex items-center gap-2">
            {/* Verdict annotation */}
            {markerState.type === "aligned" && markerState.verdict && (
              <VerdictBadge verdict={markerState.verdict} />
            )}
            {data.data_state === "stale" && (
              <span className="text-[10px] text-amber-500" data-testid="chart-stale-badge">
                Stale data
              </span>
            )}
            <span className="text-[10px] text-gray-600">
              {data.candle_count} candles
            </span>
          </div>
        </div>
      )}

      {/* Timeframe tabs */}
      <TimeframeTabs
        availableTimeframes={availableTimeframes}
        selectedTimeframe={activeTf}
        onSelect={handleTabClick}
      />

      {/* Alignment status messages */}
      {markerState.type === "out-of-range" && (
        <p className="text-[10px] text-gray-500 mt-1" data-testid="run-out-of-range">
          Selected run is outside the loaded chart range.
        </p>
      )}
      {markerState.type === "invalid-timestamp" && (
        <p className="text-[10px] text-gray-500 mt-1" data-testid="run-invalid-timestamp">
          Selected run timestamp is invalid.
        </p>
      )}

      {/* Loading overlay */}
      {isLoading && (
        <div className="py-2" data-testid="chart-loading">
          <LoadingSkeleton rows={3} />
        </div>
      )}

      {/* Error overlay */}
      {isError && !isLoading && (
        <div
          className="rounded border border-amber-800/40 bg-amber-950/20 px-4 py-3 mt-2"
          data-testid="chart-error"
        >
          <p className="text-xs text-amber-400">
            Unable to load chart data for this timeframe.
          </p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && !hasCandles && (
        <p className="text-xs text-gray-500 py-2" data-testid="chart-empty">
          No candle data available for {instrument} {activeTf}
        </p>
      )}

      {/* Chart container — ALWAYS in DOM so useEffect can create the chart.
          Uses min-height to guarantee non-zero dimensions for lightweight-charts. */}
      <div
        ref={containerRef}
        className="mt-2"
        style={{ minHeight: hasCandles || isLoading ? 300 : 0 }}
        data-testid="chart-container"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Marker state computation hook
// ---------------------------------------------------------------------------

type MarkerStateResult =
  | { type: "no-run" }
  | { type: "invalid-timestamp" }
  | { type: "out-of-range" }
  | { type: "aligned"; marker: SeriesMarker<UTCTimestamp>; verdict: NormalizedVerdict };

function useMarkerState(
  candles: { timestamp: number }[] | null,
  runTimestamp: string | null | undefined,
  runVerdict: string | null | undefined,
): MarkerStateResult {
  // No run selected
  if (runTimestamp == null) {
    return { type: "no-run" };
  }

  // Parse timestamp
  const epoch = parseRunTimestamp(runTimestamp);
  if (epoch === null) {
    return { type: "invalid-timestamp" };
  }

  // No candle data
  if (!candles || candles.length === 0) {
    return { type: "out-of-range" };
  }

  // Find nearest candle at or before
  const idx = findNearestCandleIndex(candles, epoch);
  if (idx < 0) {
    return { type: "out-of-range" };
  }

  const verdict = normalizeVerdict(runVerdict);
  const style = VERDICT_STYLES[verdict];
  const targetCandle = candles[idx];

  return {
    type: "aligned",
    verdict,
    marker: {
      time: targetCandle.timestamp as UTCTimestamp,
      position: style.position,
      shape: style.shape,
      color: style.color,
      text: style.label,
      size: 2,
    },
  };
}

// ---------------------------------------------------------------------------
// Timeframe tabs sub-component
// ---------------------------------------------------------------------------

function TimeframeTabs({
  availableTimeframes,
  selectedTimeframe,
  onSelect,
}: {
  availableTimeframes?: string[] | null;
  selectedTimeframe: string;
  onSelect: (tf: string) => void;
}) {
  if (!availableTimeframes || !Array.isArray(availableTimeframes) || availableTimeframes.length === 0) {
    return null;
  }

  return (
    <div className="mb-2 flex items-center gap-1" data-testid="timeframe-tabs">
      {availableTimeframes.map((tf) => (
        <button
          key={tf}
          type="button"
          onClick={() => onSelect(tf)}
          className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
            tf === selectedTimeframe
              ? "bg-cyan-900/40 text-cyan-300 border border-cyan-700/40"
              : "text-gray-500 hover:text-gray-300 border border-transparent"
          }`}
          data-testid={`tf-tab-${tf}`}
        >
          {tf}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Verdict badge sub-component
// ---------------------------------------------------------------------------

function VerdictBadge({ verdict }: { verdict: NormalizedVerdict }) {
  const style = VERDICT_STYLES[verdict];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${style.bgClass} ${style.textClass}`}
      data-testid="verdict-badge"
    >
      {style.label}
    </span>
  );
}
