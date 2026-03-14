// ---------------------------------------------------------------------------
// Analysis Run — domain types aligned with UI_CONTRACT §9.1–9.4
// ---------------------------------------------------------------------------

// ---- Backend response shapes ----

export interface ApprovedSetup {
  type: string;
  entry_zone: string;
  stop: string;
  targets: string[];
  rr_estimate: number;
  confidence: number;
  indicator_dependent?: boolean;
}

export interface AuditLog {
  run_id: string;
  analysts_received: number;
  analysts_valid: number;
  htf_consensus: boolean;
  setup_consensus: boolean;
  risk_override: boolean;
  overlay_provided: boolean;
  indicator_dependent_setups: number;
}

export interface FinalVerdict {
  final_bias: string;
  decision: string;
  approved_setups: ApprovedSetup[];
  no_trade_conditions: string[];
  overall_confidence: number;
  analyst_agreement_pct: number;
  risk_override_applied?: boolean;
  arbiter_notes: string;
  audit_log?: AuditLog;
  overlay_was_provided?: boolean;
  indicator_dependent?: boolean;
  indicator_dependency_notes?: string | null;
}

export interface TicketDraft {
  source_run_id?: string;
  source_ticket_id?: string;
  rawAIReadBias?: string;
  decisionMode?: string;
  aiEdgeScore?: number;
  aiEdgeScorePct?: number;
  [key: string]: unknown;
}

export interface UsageSummary {
  total_calls?: number;
  successful_calls?: number;
  failed_calls?: number;
  calls_by_stage?: Record<string, number>;
  calls_by_node?: Record<string, number>;
  calls_by_model?: Record<string, number>;
  calls_by_provider?: Record<string, number>;
  tokens?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  calls_with_token_usage?: number;
  calls_without_token_usage?: number;
  total_cost_usd?: number;
}

export interface AnalysisResponse {
  run_id: string;
  verdict: FinalVerdict;
  ticket_draft: TicketDraft;
  source_ticket_id?: string | null;
  usage_summary?: UsageSummary;
}

export interface RunUsageResponse {
  run_id: string;
  usage_summary: UsageSummary;
}

// ---- Submission form model ----

export interface AnalysisSubmission {
  instrument: string;
  session: string;
  timeframes: string[];
  account_balance: number;
  min_rr: number;
  max_risk_per_trade: number;
  max_daily_risk: number;
  no_trade_windows: string[];
  market_regime: string;
  news_risk: string;
  open_positions: string[];
  // Lens flags
  lens_ict_icc: boolean;
  lens_market_structure: boolean;
  lens_orderflow: boolean;
  lens_trendlines: boolean;
  lens_classical: boolean;
  lens_harmonic: boolean;
  lens_smt: boolean;
  lens_volume_profile: boolean;
  // Charts
  charts: { [key: string]: File };
  // Optional flags
  source_ticket_id?: string;
  enable_deliberation: boolean;
  triage_mode: boolean;
  smoke_mode: boolean;
}
