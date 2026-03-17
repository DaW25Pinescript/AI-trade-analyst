// ---------------------------------------------------------------------------
// View-model adapter for Reflect workspace (PR-REFLECT-2).
// Pure functions — no side effects. All formatting happens here.
// ---------------------------------------------------------------------------

import type {
  PersonaPerformanceResponse,
  PersonaStats,
  PatternSummaryResponse,
  PatternBucket,
  RunBundleResponse,
  Suggestion,
} from "@shared/api/reflect";
import type { RunBrowserItem } from "@shared/api/runs";

// ---- Formatting helpers ----

function formatPct(value: number | null): string {
  if (value == null) return "\u2014";
  return `${Math.round(value * 100)}%`;
}

function formatDecimal2(value: number | null): string {
  if (value == null) return "\u2014";
  return value.toFixed(2);
}

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  if (isNaN(then)) return iso;
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

// ---- Persona Performance view model ----

export interface PersonaViewModel {
  persona: string;
  participationRate: string;
  skipCount: number;
  failCount: number;
  overrideRate: string;
  stanceAlignment: string;
  avgConfidence: string;
  flagged: boolean;
  navigableEntityId: string | null;
}

export interface PersonaPerformanceViewModel {
  thresholdMet: boolean;
  threshold: number;
  dataState: string;
  personas: PersonaViewModel[];
  scanFooter: string;
}

export function normalizePersonaPerformance(
  response: PersonaPerformanceResponse,
): PersonaPerformanceViewModel {
  const personas: PersonaViewModel[] = response.stats.map(
    (s: PersonaStats) => ({
      persona: s.persona,
      participationRate: formatPct(s.participation_rate),
      skipCount: s.skip_count,
      failCount: s.fail_count,
      overrideRate: formatPct(s.override_rate),
      stanceAlignment: formatPct(s.stance_alignment),
      avgConfidence: formatDecimal2(s.avg_confidence),
      flagged: s.flagged,
      navigableEntityId: s.navigable_entity_id ?? null,
    }),
  );

  const scanFooter = `Based on ${response.scan_bounds.valid_runs} runs (${response.scan_bounds.skipped_runs} skipped), generated ${formatRelativeTime(response.generated_at)}`;

  return {
    thresholdMet: response.threshold_met,
    threshold: response.threshold,
    dataState: response.data_state,
    personas,
    scanFooter,
  };
}

// ---- Pattern Summary view model ----

export interface PatternBucketViewModel {
  instrument: string;
  session: string;
  runCount: number;
  thresholdMet: boolean;
  verdictDisplay: string;
  noTradeRate: string;
  flagged: boolean;
}

export interface PatternSummaryViewModel {
  threshold: number;
  dataState: string;
  buckets: PatternBucketViewModel[];
}

export function normalizePatternSummary(
  response: PatternSummaryResponse,
): PatternSummaryViewModel {
  const buckets: PatternBucketViewModel[] = response.buckets.map(
    (b: PatternBucket) => {
      let verdictDisplay: string;
      if (!b.threshold_met) {
        verdictDisplay = `insufficient data (${b.run_count}/${response.threshold} runs)`;
      } else {
        const total = b.verdict_distribution.reduce(
          (acc, v) => acc + v.count,
          0,
        );
        verdictDisplay = b.verdict_distribution
          .map((v) => {
            const pct = total > 0 ? Math.round((v.count / total) * 100) : 0;
            return `${v.verdict}: ${v.count} (${pct}%)`;
          })
          .join(", ");
      }

      return {
        instrument: b.instrument,
        session: b.session,
        runCount: b.run_count,
        thresholdMet: b.threshold_met,
        verdictDisplay,
        noTradeRate: formatPct(b.no_trade_rate),
        flagged: b.flagged,
      };
    },
  );

  return {
    threshold: response.threshold,
    dataState: response.data_state,
    buckets,
  };
}

// ---- Run Bundle view model ----

export interface AnalystContribution {
  persona: string;
  status: string;
  stance: string;
  confidence: string;
}

export interface RunBundleViewModel {
  runId: string;
  instrument: string;
  session: string;
  timestamp: string;
  dataState: string;
  verdict: string;
  arbiterConfidence: string;
  arbiterMethod: string;
  analysts: AnalystContribution[];
  dissentSummary: string;
  overrideInfo: string;
  usageSummary: {
    totalCalls: string;
    modelsUsed: string;
    totalTokens: string;
    estimatedCost: string;
  } | null;
  artifactStatus: {
    runRecord: string;
    usageJsonl: string;
    usageJson: string;
  };
}

export function normalizeRunBundle(
  response: RunBundleResponse,
): RunBundleViewModel {
  const rr = response.run_record;
  const request =
    typeof rr.request === "object" && rr.request != null
      ? (rr.request as Record<string, unknown>)
      : {};
  const arbiter =
    typeof rr.arbiter === "object" && rr.arbiter != null
      ? (rr.arbiter as Record<string, unknown>)
      : {};

  const analystsList = Array.isArray(rr.analysts)
    ? (rr.analysts as Record<string, unknown>[])
    : [];

  const analysts: AnalystContribution[] = analystsList.map((a) => ({
    persona: typeof a.persona === "string" ? a.persona : (typeof a.entity_id === "string" ? a.entity_id : "\u2014"),
    status: typeof a.status === "string" ? a.status : "\u2014",
    stance:
      typeof a.stance === "string"
        ? a.stance
        : typeof a.htf_bias === "string"
          ? a.htf_bias
          : "\u2014",
    confidence:
      typeof a.confidence === "number" ? a.confidence.toFixed(2) : "\u2014",
  }));

  const usage = response.usage_summary;
  const usageSummary = usage
    ? {
        totalCalls:
          typeof usage.total_calls === "number"
            ? String(usage.total_calls)
            : "\u2014",
        modelsUsed: Array.isArray(usage.models_used)
          ? (usage.models_used as string[]).join(", ")
          : "\u2014",
        totalTokens:
          typeof usage.total_tokens === "number"
            ? String(usage.total_tokens)
            : "\u2014",
        estimatedCost:
          typeof usage.estimated_cost === "number"
            ? `$${(usage.estimated_cost as number).toFixed(4)}`
            : "\u2014",
      }
    : null;

  return {
    runId: response.run_id,
    instrument: typeof request.instrument === "string" ? request.instrument : "\u2014",
    session: typeof request.session === "string" ? request.session : "\u2014",
    timestamp: typeof rr.timestamp === "string" ? rr.timestamp : "\u2014",
    dataState: response.data_state,
    verdict: typeof arbiter.verdict === "string" ? arbiter.verdict : "\u2014",
    arbiterConfidence:
      typeof arbiter.confidence === "number"
        ? (arbiter.confidence as number).toFixed(2)
        : "\u2014",
    arbiterMethod:
      typeof arbiter.method === "string" ? arbiter.method : "\u2014",
    analysts,
    dissentSummary:
      typeof arbiter.dissent_summary === "string"
        ? arbiter.dissent_summary
        : "Not available",
    overrideInfo:
      typeof arbiter.risk_override_applied === "boolean" &&
      arbiter.risk_override_applied
        ? "Risk override applied"
        : "Not available",
    usageSummary,
    artifactStatus: {
      runRecord: response.artifact_status.run_record,
      usageJsonl: response.artifact_status.usage_jsonl,
      usageJson: response.artifact_status.usage_json,
    },
  };
}

// ---- Suggestion normalization (PR-REFLECT-3) ----

const VALID_RULE_IDS = new Set(["OVERRIDE_FREQ_HIGH", "NO_TRADE_CONCENTRATION"]);

export interface SuggestionViewModel {
  ruleId: string;
  severity: string;
  category: string;
  target: string;
  message: string;
  evidenceTooltip: string;
}

function isValidSuggestion(s: unknown): s is Suggestion {
  if (typeof s !== "object" || s == null) return false;
  const obj = s as Record<string, unknown>;
  if (typeof obj.rule_id !== "string" || !VALID_RULE_IDS.has(obj.rule_id)) return false;
  if (typeof obj.message !== "string") return false;
  if (typeof obj.target !== "string") return false;
  if (typeof obj.category !== "string") return false;
  if (typeof obj.severity !== "string") return false;
  if (typeof obj.evidence !== "object" || obj.evidence == null) return false;
  const ev = obj.evidence as Record<string, unknown>;
  if (typeof ev.metric_name !== "string") return false;
  if (typeof ev.metric_value !== "number") return false;
  if (typeof ev.threshold !== "number") return false;
  if (typeof ev.sample_size !== "number") return false;
  return true;
}

function formatEvidenceTooltip(evidence: Suggestion["evidence"]): string {
  return `${evidence.metric_name}: ${(evidence.metric_value * 100).toFixed(0)}%, threshold: ${(evidence.threshold * 100).toFixed(0)}%, sample: ${evidence.sample_size}`;
}

export function normalizeSuggestions(raw: unknown[] | undefined): SuggestionViewModel[] {
  if (!Array.isArray(raw)) return [];
  const valid: SuggestionViewModel[] = [];
  for (const item of raw) {
    if (isValidSuggestion(item)) {
      valid.push({
        ruleId: item.rule_id,
        severity: item.severity,
        category: item.category,
        target: item.target,
        message: item.message,
        evidenceTooltip: formatEvidenceTooltip(item.evidence),
      });
    } else {
      console.warn("Dropping malformed suggestion item:", item);
    }
  }
  return valid;
}

export function mergeSuggestions(
  personaSuggestions: SuggestionViewModel[],
  patternSuggestions: SuggestionViewModel[],
): SuggestionViewModel[] {
  return [...personaSuggestions, ...patternSuggestions];
}

// ---- Run list item adapter (thin formatter for useRuns output) ----

export interface RunListItemViewModel {
  runId: string;
  timestamp: string;
  relativeTime: string;
  instrument: string;
  session: string;
  finalDecision: string;
  runStatus: string;
}

export function normalizeRunForReflect(
  item: RunBrowserItem,
): RunListItemViewModel {
  return {
    runId: item.run_id,
    timestamp: item.timestamp,
    relativeTime: formatRelativeTime(item.timestamp),
    instrument: item.instrument ?? "\u2014",
    session: item.session ?? "\u2014",
    finalDecision: item.final_decision ?? "\u2014",
    runStatus: item.run_status,
  };
}
