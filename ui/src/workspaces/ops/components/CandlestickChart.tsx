// ---------------------------------------------------------------------------
// CandlestickChart — OHLCV candlestick chart panel (PR-CHART-1).
//
// Self-contained, failure-tolerant component. If the chart errors,
// loading, or has no data, it does NOT affect trace rendering.
//
// Sources instrument from RunBrowserItem row, not trace endpoint.
// Spec: docs/specs/PR_CHART_1_SPEC.md §6.4
// ---------------------------------------------------------------------------

import { useRef, useEffect } from "react";
import { createChart, type IChartApi, type ISeriesApi, ColorType } from "lightweight-charts";
import { useMarketData } from "@shared/hooks";
import { LoadingSkeleton } from "@shared/components/feedback";

export interface CandlestickChartProps {
  instrument: string | null;
  timeframe?: string;
}

export function CandlestickChart({
  instrument,
  timeframe = "4h",
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const query = useMarketData({ instrument, timeframe });

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

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addHistogramSeries({
      color: "rgba(103, 232, 249, 0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });

    chart.priceScale("").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

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
    };
  }, []);

  // Update chart data when query data changes
  useEffect(() => {
    if (!query.data || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const candles = query.data.candles;
    if (candles.length === 0) return;

    candleSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.timestamp as import("lightweight-charts").UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    volumeSeriesRef.current.setData(
      candles.map((c) => ({
        time: c.timestamp as import("lightweight-charts").UTCTimestamp,
        value: c.volume,
        color:
          c.close >= c.open
            ? "rgba(34, 197, 94, 0.3)"
            : "rgba(239, 68, 68, 0.3)",
      })),
    );

    chartRef.current?.timeScale().fitContent();
  }, [query.data]);

  // No instrument selected
  if (!instrument) {
    return null;
  }

  // Loading
  if (query.isLoading) {
    return (
      <div
        className="rounded-lg border border-gray-700/40 bg-gray-900/40 p-4"
        data-testid="chart-loading"
      >
        <LoadingSkeleton rows={3} />
      </div>
    );
  }

  // Error — failure-tolerant: show error banner, don't block trace
  if (query.isError) {
    return (
      <div
        className="rounded-lg border border-amber-800/40 bg-amber-950/20 px-4 py-3"
        data-testid="chart-error"
      >
        <p className="text-xs text-amber-400">
          Chart unavailable: {query.error?.message ?? "Unknown error"}
        </p>
      </div>
    );
  }

  const data = query.data;

  // Empty candles
  if (!data || data.candles.length === 0) {
    return (
      <div
        className="rounded-lg border border-gray-700/40 bg-gray-900/40 px-4 py-3"
        data-testid="chart-empty"
      >
        <p className="text-xs text-gray-500">
          No candle data available for {instrument} {timeframe}
        </p>
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border border-gray-700/40 bg-gray-900/40 p-3"
      data-testid="chart-panel"
    >
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-gray-300">
          {instrument} {timeframe}
        </span>
        {data.data_state === "stale" && (
          <span className="text-[10px] text-amber-500" data-testid="chart-stale-badge">
            Stale data
          </span>
        )}
        <span className="text-[10px] text-gray-600">
          {data.candle_count} candles
        </span>
      </div>

      {/* Chart container */}
      <div ref={containerRef} data-testid="chart-container" />
    </div>
  );
}
