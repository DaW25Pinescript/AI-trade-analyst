// ---------------------------------------------------------------------------
// SubmissionPanel — form inputs for analysis submission.
//
// Handles multipart/form-data fields: instrument, session, timeframes,
// account/risk settings, lens flags, chart uploads, and feature flags.
// Locks to read-only post-submission for "what did I submit?" verification.
//
// Backend field names discovered from FastAPI route:
//   instrument, session, timeframes, account_balance, min_rr,
//   max_risk_per_trade, max_daily_risk, no_trade_windows,
//   market_regime, news_risk, open_positions,
//   lens_ict_icc, lens_market_structure, lens_orderflow, lens_trendlines,
//   lens_classical, lens_harmonic, lens_smt, lens_volume_profile,
//   chart_h4, chart_h1, chart_m15, chart_m5,
//   source_ticket_id, enable_deliberation, triage_mode, smoke_mode
// ---------------------------------------------------------------------------

import { useState, useCallback, useRef, useMemo } from "react";
import { PanelShell } from "@shared/components/layout";
import { useWatchlistTriage } from "@shared/hooks/useWatchlistTriage";
import type { AnalysisSubmission } from "../types";

export interface SubmissionPanelProps {
  readOnly: boolean;
  initialInstrument: string;
  onSubmit: (submission: AnalysisSubmission) => void;
  lastSubmission: AnalysisSubmission | null;
}

export interface ValidationErrors {
  instrument?: string;
  session?: string;
  account_balance?: string;
  charts?: string;
}

const SESSIONS = ["NY", "London", "Asia"];
const TIMEFRAMES = ["H4", "H1", "M15", "M5"];
const MARKET_REGIMES = ["trending", "ranging", "unknown"];

export function SubmissionPanel({
  readOnly,
  initialInstrument,
  onSubmit,
  lastSubmission,
}: SubmissionPanelProps) {
  // Instrument list from watchlist triage
  const { data: triageData, isLoading: instrumentsLoading } = useWatchlistTriage();
  const instruments = useMemo(
    () =>
      triageData?.items
        ?.map((item) => item.symbol)
        .filter(Boolean)
        .sort() ?? [],
    [triageData],
  );

  // Form state — use last submission values if read-only, else initial values
  const [instrument, setInstrument] = useState(
    lastSubmission?.instrument ?? initialInstrument ?? "",
  );
  const [session, setSession] = useState(lastSubmission?.session ?? "NY");
  const [timeframes, setTimeframes] = useState<string[]>(
    lastSubmission?.timeframes ?? ["H4", "M15", "M5"],
  );
  const [accountBalance, setAccountBalance] = useState(
    lastSubmission?.account_balance ?? 10000,
  );
  const [minRr, setMinRr] = useState(lastSubmission?.min_rr ?? 2.0);
  const [maxRiskPerTrade, setMaxRiskPerTrade] = useState(
    lastSubmission?.max_risk_per_trade ?? 0.5,
  );
  const [maxDailyRisk, setMaxDailyRisk] = useState(
    lastSubmission?.max_daily_risk ?? 2.0,
  );
  const [marketRegime, setMarketRegime] = useState(
    lastSubmission?.market_regime ?? "unknown",
  );
  const [newsRisk, setNewsRisk] = useState(
    lastSubmission?.news_risk ?? "none_noted",
  );
  const [sourceTicketId, setSourceTicketId] = useState(
    lastSubmission?.source_ticket_id ?? "",
  );
  const [enableDeliberation, setEnableDeliberation] = useState(
    lastSubmission?.enable_deliberation ?? false,
  );
  const [smokeMode, setSmokeMode] = useState(
    lastSubmission?.smoke_mode ?? false,
  );

  // Lens flags
  const [lensIctIcc, setLensIctIcc] = useState(lastSubmission?.lens_ict_icc ?? true);
  const [lensMarketStructure, setLensMarketStructure] = useState(lastSubmission?.lens_market_structure ?? true);
  const [lensOrderflow, setLensOrderflow] = useState(lastSubmission?.lens_orderflow ?? false);
  const [lensTrendlines, setLensTrendlines] = useState(lastSubmission?.lens_trendlines ?? false);
  const [lensClassical, setLensClassical] = useState(lastSubmission?.lens_classical ?? false);
  const [lensHarmonic, setLensHarmonic] = useState(lastSubmission?.lens_harmonic ?? false);
  const [lensSmt, setLensSmt] = useState(lastSubmission?.lens_smt ?? false);
  const [lensVolumeProfile, setLensVolumeProfile] = useState(lastSubmission?.lens_volume_profile ?? false);

  // Chart files
  const [charts, setCharts] = useState<Record<string, File>>(
    lastSubmission?.charts ?? {},
  );
  const chartInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const [errors, setErrors] = useState<ValidationErrors>({});

  const handleTimeframeToggle = useCallback((tf: string) => {
    setTimeframes((prev) =>
      prev.includes(tf) ? prev.filter((t) => t !== tf) : [...prev, tf],
    );
  }, []);

  const handleChartChange = useCallback((key: string, file: File | null) => {
    if (file) {
      setCharts((prev) => ({ ...prev, [key]: file }));
    } else {
      setCharts((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  }, []);

  const validate = useCallback((): boolean => {
    const errs: ValidationErrors = {};

    if (!instrument.trim()) {
      errs.instrument = "Instrument is required";
    }
    if (!session) {
      errs.session = "Session is required";
    }
    if (accountBalance <= 0) {
      errs.account_balance = "Account balance must be positive";
    }
    if (Object.keys(charts).length === 0 && !smokeMode) {
      errs.charts = "At least one chart is required (or enable Smoke Mode)";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [instrument, session, accountBalance, charts, smokeMode]);

  const handleSubmit = useCallback(() => {
    if (readOnly) return;
    if (!validate()) return;

    const submission: AnalysisSubmission = {
      instrument: instrument.trim().toUpperCase(),
      session,
      timeframes,
      account_balance: accountBalance,
      min_rr: minRr,
      max_risk_per_trade: maxRiskPerTrade,
      max_daily_risk: maxDailyRisk,
      no_trade_windows: ["FOMC", "NFP"],
      market_regime: marketRegime,
      news_risk: newsRisk,
      open_positions: [],
      lens_ict_icc: lensIctIcc,
      lens_market_structure: lensMarketStructure,
      lens_orderflow: lensOrderflow,
      lens_trendlines: lensTrendlines,
      lens_classical: lensClassical,
      lens_harmonic: lensHarmonic,
      lens_smt: lensSmt,
      lens_volume_profile: lensVolumeProfile,
      charts,
      source_ticket_id: sourceTicketId || undefined,
      enable_deliberation: enableDeliberation,
      triage_mode: false,
      smoke_mode: smokeMode,
    };

    onSubmit(submission);
  }, [
    readOnly, validate, instrument, session, timeframes, accountBalance,
    minRr, maxRiskPerTrade, maxDailyRisk, marketRegime, newsRisk,
    lensIctIcc, lensMarketStructure, lensOrderflow, lensTrendlines,
    lensClassical, lensHarmonic, lensSmt, lensVolumeProfile,
    charts, sourceTicketId, enableDeliberation, smokeMode, onSubmit,
  ]);

  const inputClass =
    "w-full rounded border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60";

  const labelClass = "block text-xs font-medium text-gray-400 mb-1";

  return (
    <PanelShell>
      <div className="space-y-4" data-testid="submission-panel">
        {readOnly && (
          <div className="rounded border border-gray-700 bg-gray-800/50 px-3 py-2 text-xs text-gray-400">
            Submission locked — review what was submitted
          </div>
        )}

        {/* Market Identity */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className={labelClass}>Instrument</label>
            <select
              value={instrument}
              onChange={(e) => setInstrument(e.target.value)}
              disabled={readOnly || instrumentsLoading}
              className={inputClass}
              data-testid="input-instrument"
            >
              <option value="">
                {instrumentsLoading ? "Loading instruments…" : "Select instrument"}
              </option>
              {instruments.map((sym) => (
                <option key={sym} value={sym}>{sym}</option>
              ))}
            </select>
            {errors.instrument && (
              <p className="mt-1 text-xs text-red-400" data-testid="error-instrument">
                {errors.instrument}
              </p>
            )}
          </div>
          <div>
            <label className={labelClass}>Session</label>
            <select
              value={session}
              onChange={(e) => setSession(e.target.value)}
              disabled={readOnly}
              className={inputClass}
              data-testid="input-session"
            >
              {SESSIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            {errors.session && (
              <p className="mt-1 text-xs text-red-400">{errors.session}</p>
            )}
          </div>
          <div>
            <label className={labelClass}>Market Regime</label>
            <select
              value={marketRegime}
              onChange={(e) => setMarketRegime(e.target.value)}
              disabled={readOnly}
              className={inputClass}
              data-testid="input-market-regime"
            >
              {MARKET_REGIMES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Timeframes */}
        <div>
          <label className={labelClass}>Timeframes</label>
          <div className="flex gap-2">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => handleTimeframeToggle(tf)}
                disabled={readOnly}
                className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  timeframes.includes(tf)
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                } disabled:cursor-not-allowed disabled:opacity-60`}
                data-testid={`tf-${tf}`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>

        {/* Account / Risk */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <label className={labelClass}>Account Balance</label>
            <input
              type="number"
              value={accountBalance}
              onChange={(e) => setAccountBalance(Number(e.target.value))}
              disabled={readOnly}
              className={inputClass}
              data-testid="input-account-balance"
            />
            {errors.account_balance && (
              <p className="mt-1 text-xs text-red-400">{errors.account_balance}</p>
            )}
          </div>
          <div>
            <label className={labelClass}>Min R:R</label>
            <input
              type="number"
              step="0.1"
              value={minRr}
              onChange={(e) => setMinRr(Number(e.target.value))}
              disabled={readOnly}
              className={inputClass}
              data-testid="input-min-rr"
            />
          </div>
          <div>
            <label className={labelClass}>Max Risk/Trade %</label>
            <input
              type="number"
              step="0.1"
              value={maxRiskPerTrade}
              onChange={(e) => setMaxRiskPerTrade(Number(e.target.value))}
              disabled={readOnly}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Max Daily Risk %</label>
            <input
              type="number"
              step="0.1"
              value={maxDailyRisk}
              onChange={(e) => setMaxDailyRisk(Number(e.target.value))}
              disabled={readOnly}
              className={inputClass}
            />
          </div>
        </div>

        {/* News Risk */}
        <div>
          <label className={labelClass}>News Risk</label>
          <input
            type="text"
            value={newsRisk}
            onChange={(e) => setNewsRisk(e.target.value)}
            disabled={readOnly}
            placeholder="e.g. none_noted"
            className={inputClass}
            data-testid="input-news-risk"
          />
        </div>

        {/* Lens Configuration */}
        <div>
          <label className={labelClass}>Analysis Lenses</label>
          <div className="flex flex-wrap gap-2">
            {[
              { key: "lens_ict_icc", label: "ICT/ICC", value: lensIctIcc, set: setLensIctIcc },
              { key: "lens_market_structure", label: "Market Structure", value: lensMarketStructure, set: setLensMarketStructure },
              { key: "lens_orderflow", label: "Order Flow", value: lensOrderflow, set: setLensOrderflow },
              { key: "lens_trendlines", label: "Trendlines", value: lensTrendlines, set: setLensTrendlines },
              { key: "lens_classical", label: "Classical", value: lensClassical, set: setLensClassical },
              { key: "lens_harmonic", label: "Harmonic", value: lensHarmonic, set: setLensHarmonic },
              { key: "lens_smt", label: "SMT", value: lensSmt, set: setLensSmt },
              { key: "lens_volume_profile", label: "Volume Profile", value: lensVolumeProfile, set: setLensVolumeProfile },
            ].map(({ key, label, value, set }) => (
              <button
                key={key}
                type="button"
                onClick={() => set(!value)}
                disabled={readOnly}
                className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  value
                    ? "bg-emerald-700/60 text-emerald-200"
                    : "bg-gray-800 text-gray-500 hover:bg-gray-700"
                } disabled:cursor-not-allowed disabled:opacity-60`}
                data-testid={`lens-${key}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Chart Upload */}
        <div>
          <label className={labelClass}>Charts</label>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(["chart_h4", "chart_h1", "chart_m15", "chart_m5"] as const).map((chartKey) => (
              <div key={chartKey}>
                <label className="block text-xs text-gray-500 mb-1">
                  {chartKey.replace("chart_", "").toUpperCase()}
                </label>
                <input
                  ref={(el) => { chartInputRefs.current[chartKey] = el; }}
                  type="file"
                  accept="image/*"
                  disabled={readOnly}
                  onChange={(e) =>
                    handleChartChange(chartKey, e.target.files?.[0] ?? null)
                  }
                  className="block w-full text-xs text-gray-400 file:mr-2 file:rounded file:border-0 file:bg-gray-800 file:px-3 file:py-1.5 file:text-xs file:text-gray-300 hover:file:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                  data-testid={`input-${chartKey}`}
                />
                {charts[chartKey] && (
                  <span className="text-xs text-emerald-500">
                    {charts[chartKey].name}
                  </span>
                )}
              </div>
            ))}
          </div>
          {errors.charts && (
            <p className="mt-1 text-xs text-red-400" data-testid="error-charts">
              {errors.charts}
            </p>
          )}
        </div>

        {/* Optional Flags */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className={labelClass}>Source Ticket ID</label>
            <input
              type="text"
              value={sourceTicketId}
              onChange={(e) => setSourceTicketId(e.target.value)}
              disabled={readOnly}
              placeholder="Optional traceability reference"
              className={inputClass}
              data-testid="input-source-ticket"
            />
          </div>
          <div className="flex items-end gap-4">
            <label className="flex items-center gap-2 text-xs text-gray-400">
              <input
                type="checkbox"
                checked={enableDeliberation}
                onChange={(e) => setEnableDeliberation(e.target.checked)}
                disabled={readOnly}
                className="rounded border-gray-600 bg-gray-800"
                data-testid="input-deliberation"
              />
              Deliberation
            </label>
            <label className="flex items-center gap-2 text-xs text-gray-400">
              <input
                type="checkbox"
                checked={smokeMode}
                onChange={(e) => setSmokeMode(e.target.checked)}
                disabled={readOnly}
                className="rounded border-gray-600 bg-gray-800"
                data-testid="input-smoke-mode"
              />
              Smoke Mode
            </label>
          </div>
        </div>

        {/* Submit Button — only when not read-only */}
        {!readOnly && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSubmit}
              className="rounded bg-blue-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
              data-testid="submit-analysis-btn"
            >
              Submit Analysis
            </button>
          </div>
        )}
      </div>
    </PanelShell>
  );
}
