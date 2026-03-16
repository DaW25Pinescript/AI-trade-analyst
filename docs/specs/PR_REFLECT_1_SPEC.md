# AI Trade Analyst — PR-REFLECT-1: Reflective Intelligence Aggregation Endpoints Spec

**Status:** ⏳ Spec drafted — implementation pending
**Date:** 16 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Branch:** `pr-reflect-1-aggregation`
**Phase:** PR-REFLECT-1 (Phase 8)
**Depends on:** PR-RUN-1 complete (Run Browser shipped, 316 ops tests)
**Independent of:** PR-CHART-1 (runs in parallel)

---

## 1. Purpose

**After:** PR-RUN-1 (Run Browser — `GET /runs/` endpoint, RunBrowserPanel, +56 tests). Phase 7 Agent Ops read-side stack complete.

**Question this phase answers:** Can we compute meaningful persona performance statistics and pattern-level summaries from existing run artifacts, and provide a full-depth artifact inspection endpoint for the future Reflect workspace?

**From → To:**

- **From:** The operator can inspect individual runs via Agent Ops Run mode (trace view) but has no cross-run analysis surface. There is no way to answer "which analyst gets overridden most?" or "which instrument produces the most NO_TRADE verdicts?" without manually reviewing runs one by one. There is no single-fetch deep dive into a complete run artifact bundle.
- **To:** Three endpoints serve the reflective intelligence layer: `GET /reflect/persona-performance` surfaces per-persona participation, override rates, stance alignment, and average reported confidence; `GET /reflect/pattern-summary` surfaces instrument × session verdict distributions; `GET /reflect/run/{run_id}` returns the complete run artifact bundle for deep inspection.

> **Scope note:** PR-REFLECT-1 establishes the **descriptive read-side foundation** only. It computes what happened (participation, overrides, stance alignment, verdict distributions) — not whether the system was right. Evaluative and hindsight-aware conclusions (bias accuracy, confidence calibration against outcomes, decision quality scoring) come in later Reflect phases.

**What Reflect is:**

Reflect is the **AI system's self-evaluation layer** — an analysis intelligence lab for reviewing the AI decision pipeline itself. It allows the operator to examine: what the system concluded, why it concluded it, what inputs were used, which analysts contributed, what the Arbiter decided, and how these patterns aggregate over time.

Reflect is NOT the trade journal. It is NOT Agent Ops (system health). It occupies a distinct position:

| Workspace | Role |
|-----------|------|
| Triage | Market scanning |
| Journey | Trade construction |
| Analysis | AI execution |
| Journal / Review | Decision ledger |
| Agent Ops | System health + operator trust |
| **Reflect** | **AI decision evaluation + progressive improvement** |

**Workspace placement (LOCKED):** Reflect is a **new top-level `/reflect` workspace**, not a mode pill inside Agent Ops. PR-REFLECT-1 ships backend endpoints and tests only. The Reflect workspace frontend is PR-REFLECT-2.

**Design principle:** This is **aggregation, not ML.** Computes statistics (counts, percentages, distributions) over existing structured artifacts. No model training, no embeddings, no inference. Pure read-side projection — same philosophy as Phase 7 and PR-RUN-1.

---

## 2. Scope

### In scope

- `GET /reflect/persona-performance` — per-persona aggregated statistics across recent runs
- `GET /reflect/pattern-summary` — instrument × session verdict distribution across recent runs
- `GET /reflect/run/{run_id}` — full run artifact bundle for deep inspection
- Reflect aggregation service — bounded scan of run artifacts, statistical projection
- Reflect bundle service — load and assemble artifact bundle per run
- Pydantic response models for all three endpoints
- Contract tests for all three endpoints
- Diagnostic to confirm per-analyst data structure in `run_record.json`

### Target components

| Layer | Component | Role |
|-------|-----------|------|
| Backend | `GET /reflect/persona-performance` | Per-persona aggregated performance stats |
| Backend | `GET /reflect/pattern-summary` | Instrument × session verdict distribution |
| Backend | `GET /reflect/run/{run_id}` | Full artifact bundle for run deep dive |
| Backend | Reflect aggregation service | Scan runs, extract data, compute statistics |
| Backend | Reflect bundle service | Load run artifacts, assemble bundle |

### Out of scope (hard list)

- No frontend — the Reflect workspace UI is PR-REFLECT-2
- No ML, statistical inference, embeddings, or model training — aggregation only
- No config mutation — all output is advisory/informational, never auto-modifies system behavior
- No parameter suggestions — that is PR-REFLECT-3
- No chart binding or chart data — that is PR-CHART-1/2
- No bias accuracy scoring or outcome tracking — that is PR-REFLECT-2+
- No confidence calibration analysis — that is PR-REFLECT-2+
- No "why was this wrong?" or decision simulation — future phase
- No new persistence — no SQLite, no database, no index file. Read-side only.
- No new top-level module — work confined to `ai_analyst/api/`
- No changes to `run_record.json` format
- No changes to existing ops, runs, trace, detail, roster, or health endpoints
- No changes to MDO pipeline
- No WebSocket / SSE / live-push
- No premature abstraction — no generic "analytics engine," no shared aggregation framework
- No cross-endpoint coupling — reflect services read artifacts independently, do not import trace, browser, or ops services
- No anomaly detection beyond simple threshold flagging (>50% override, >80% NO_TRADE)

---

## 3. Repo-Aligned Assumptions

| Area | Assumption | Confidence |
|------|-----------|------------|
| Run storage | `ai_analyst/output/runs/{run_id}/run_record.json` | Confirmed (PR-RUN-1) |
| Run directory | Currently empty on disk — tests use fixtures in temp dirs | Confirmed (PR-RUN-1) |
| `run_id`, `timestamp` | Top-level fields | Confirmed |
| `request.instrument`, `request.session` | Nested in request block | Confirmed |
| `arbiter.ran`, `arbiter.verdict` | Nested in arbiter block | Confirmed |
| `analysts[]` array | Top-level, contains per-analyst objects | Confirmed exists — **internal field structure needs diagnostic** |
| `analysts_skipped[]`, `analysts_failed[]` | Top-level arrays | Confirmed |
| Per-analyst stance/confidence/override | Present in `analysts[]` entries and/or audit log — **exact fields need diagnostic** | **Partially confirmed** |
| Audit log | `logs/runs/{run_id}.jsonl` — secondary source per Phase 7 trace contract | **Needs diagnostic** |
| Additional run artifacts | `analysis_response.json` and `usage.json` may exist alongside `run_record.json` | **Needs diagnostic** |
| Backend package | `ai_analyst/api/` | Confirmed (PR-RUN-1) |
| Fixture file | `tests/fixtures/sample_run_record.json` | Confirmed |

### Current likely state

The `run_record.json` artifact contains per-analyst data in the `analysts[]` array. The Phase 7 trace contract shows that per-analyst entries include: `entity_id`, `display_name`, `participation_status`, `stance`, `confidence`, `was_overridden`, and `override_reason`. However, these are the trace endpoint's *projected* fields — the raw artifact may structure them differently, or some fields may require cross-referencing the arbiter block or audit log.

The run directory may also contain `analysis_response.json` (the full LLM analysis output) and `usage.json` (token/cost accounting). The diagnostic must confirm which artifact files exist per run.

### Core question

What per-analyst fields exist in `run_record.json`'s `analysts[]` array? Which additional artifact files exist per run? Are these sufficient to compute the aggregation metrics and assemble a complete run bundle without fabricating data?

---

## 4. Key File Paths

| Role | Path | Access |
|------|------|--------|
| Run artifacts root | `ai_analyst/output/runs/` | Read-only scan |
| Run record artifact | `ai_analyst/output/runs/{run_id}/run_record.json` | Read-only parse |
| Analysis response (hypothesis) | `ai_analyst/output/runs/{run_id}/analysis_response.json` | Diagnostic — confirm existence |
| Usage data (hypothesis) | `ai_analyst/output/runs/{run_id}/usage.json` | Diagnostic — confirm existence |
| Audit log (secondary) | `logs/runs/{run_id}.jsonl` (hypothesis) | Diagnostic — confirm existence and format |
| Test fixture | `tests/fixtures/sample_run_record.json` | Read-only — inspect for analyst field structure |
| Trace projection (reference) | `ai_analyst/api/services/ops_trace.py` | Read-only reference — how it extracts per-analyst data |
| Run browser (reference) | `ai_analyst/api/services/ops_run_browser.py` | Read-only reference — scan pattern to follow |
| Backend routes | `ai_analyst/api/routers/` | Modify — add reflect router |
| Backend services | `ai_analyst/api/services/` | Modify — add aggregation + bundle services |
| Backend models | `ai_analyst/api/models/` | Modify — add reflect response models |
| Backend main | `ai_analyst/api/main.py` | Modify — register reflect router |

---

## 5. Current State Audit Hypothesis

### What is already true

- `run_record.json` is produced per run and contains `analysts[]`, `analysts_skipped[]`, `analysts_failed[]`, `arbiter.*`, `request.*`
- The trace endpoint already parses per-analyst data from these artifacts
- The run browser implements a bounded directory scan pattern the reflect service can follow
- `ResponseMeta`, `OpsErrorEnvelope` patterns are established
- Reflect is confirmed as a separate `/reflect` workspace

### What is unknown (diagnostic must resolve)

- Exact per-analyst field structure inside `analysts[]` entries
- Whether `stance`, `confidence`, and `was_overridden` are stored per analyst in the run record or only derivable from the audit log
- Whether `analysis_response.json` and `usage.json` exist as separate artifact files per run
- If they exist, their internal structure and what they contain
- Whether the audit log (`logs/runs/{run_id}.jsonl`) exists and its format
- How the arbiter's override decisions map back to individual analysts
- Which identifier is the stable persona key across runs

---

## 6. Design

### 6.1 Reflective Layer Operating Rules (LOCKED for v1)

These rules are inherited from the Phase 8 plan and are not negotiable:

1. **Aggregation only.** Computes statistics over existing run artifacts. No ML, no statistical inference, no embeddings.
2. **Advisory only.** All output is operator information. No config mutation path. The system never auto-modifies its own behavior.
3. **Minimum threshold: 10 runs per bucket** before surfacing statistics. Below threshold → `"insufficient_data"`, not fabricated stats. Threshold is configurable but the principle is locked.
4. **Read-side only.** Read existing artifacts, project statistics, return them.

### 6.2 Backend — `GET /reflect/persona-performance`

**Route:** `GET /reflect/persona-performance`

Registered in `routers/reflect.py`. Reflect surface — not ops, not runs.

**Query parameters:**

| Parameter | Type | Default | Constraint | Purpose |
|-----------|------|---------|------------|---------|
| `max_runs` | `int` | `50` | 10–200 | Maximum recent runs to scan |
| `instrument` | `string \| null` | `null` | Optional, exact match | Filter runs before aggregation |
| `session` | `string \| null` | `null` | Optional, exact match | Filter runs before aggregation |

**Response shape:**

```typescript
type PersonaPerformanceResponse = ResponseMeta & {
  run_count: number;
  skipped_runs: number;
  threshold: number;
  threshold_met: boolean;
  personas: PersonaStats[];       // empty if threshold not met
  scan_bounds: ScanBounds;
};

type PersonaStats = {
  persona_id: string;
  display_name: string;
  participation_count: number;
  participation_rate: number;     // participation_count / (participation_count + skip_count + fail_count) — share of opportunities
  skip_count: number;
  fail_count: number;
  override_count: number;
  override_rate: number | null;   // override_count / participation_count — null if participation_count == 0
  stance_alignment_rate: number | null;  // per §6.6.1 formula — null if no directional stances
  avg_confidence: number | null;  // mean reported confidence across participated runs — null if no confidence data
  flagged: boolean;               // true if override_rate > 0.5 (simple heuristic attention signal, not a significance test)
};

type ScanBounds = {
  max_runs_scanned: number;
  oldest_run_timestamp: string | null;
  newest_run_timestamp: string | null;
};
```

**Provisional metrics note:** The following fields are intended aggregation targets but depend on per-analyst data availability confirmed by the diagnostic: `override_count`, `override_rate`, `stance_alignment_rate`, `avg_confidence`. If the diagnostic shows the required raw fields are unavailable or unreliable in `run_record.json`, the endpoint must return `null` for the affected metric rather than derive from speculative logic. The endpoint must still ship with those fields present as `null` — do not block the phase on incomplete metric richness.

**Minimum threshold behavior:**

When `run_count < threshold`: `threshold_met = false`, `personas = []`. This is a 200 response — "insufficient data" is a valid state, not an error.

### 6.3 Backend — `GET /reflect/pattern-summary`

**Route:** `GET /reflect/pattern-summary`

Same router: `routers/reflect.py`.

**Query parameters:**

| Parameter | Type | Default | Constraint | Purpose |
|-----------|------|---------|------------|---------|
| `max_runs` | `int` | `50` | 10–200 | Maximum recent runs to scan |

No instrument/session filter — the purpose is to see distribution *across* instruments and sessions.

**Response shape:**

```typescript
type PatternSummaryResponse = ResponseMeta & {
  run_count: number;
  skipped_runs: number;
  threshold: number;
  buckets: PatternBucket[];
  scan_bounds: ScanBounds;
};

type PatternBucket = {
  instrument: string;
  session: string;
  run_count: number;
  threshold_met: boolean;         // per-bucket threshold
  verdict_distribution: VerdictCount[] | null;  // null if threshold not met
  no_trade_rate: number | null;
  flagged: boolean;               // true if no_trade_rate > 0.8 (simple heuristic attention signal, not a significance test)
};

type VerdictCount = {
  verdict: string;
  count: number;
  percentage: number;             // 0.0–1.0
};
```

**Per-bucket threshold:** A bucket with only 3 runs returns `threshold_met: false` with null stats even if the global scan covered 50+ runs. This prevents small-sample noise from masquerading as a pattern.

### 6.4 Backend — `GET /reflect/run/{run_id}`

**Route:** `GET /reflect/run/{run_id}`

Same router: `routers/reflect.py`.

**Purpose:** Return the complete run artifact bundle for deep inspection. This is different from the trace endpoint (`GET /runs/{run_id}/agent-trace`) which returns a *projected* view — this returns the raw artifacts assembled into a single response. The future Reflect frontend (PR-REFLECT-2) uses this for full run deep dives.

**Response shape:**

```typescript
type RunBundleResponse = ResponseMeta & {
  run_id: string;
  artifacts: {
    run_record: object | null;
    analysis_response: object | null;
    usage_summary: object | null;
  };
  artifact_status: {
    run_record: ArtifactStatus;
    analysis_response: ArtifactStatus;
    usage_summary: ArtifactStatus;
  };
};

type ArtifactStatus = "present" | "missing" | "malformed";
```

**Graceful degradation:** The endpoint returns whatever artifacts are available. Missing artifacts get `null` in `artifacts` and `"missing"` in `artifact_status`. Malformed artifacts (file exists but won't parse) get `null` and `"malformed"`. The endpoint does NOT return a 500 for missing or malformed individual artifacts — it assembles what it can.

**`usage_summary` source precedence:** `usage_summary` is sourced from `usage.json` if that file exists as a separate artifact; otherwise from the embedded `usage_summary` block inside `run_record.json` if present; otherwise `null`. The diagnostic (Step 3) must confirm which source exists.

**Minimum viable response:** The endpoint returns 200 as long as at least `run_record` is `"present"`. If even `run_record` is missing or malformed, return 404 `RUN_NOT_FOUND`.

**Error responses:**

| HTTP status | `error` code | When |
|------------|-------------|------|
| 404 | `RUN_NOT_FOUND` | Run directory doesn't exist or `run_record.json` is missing/malformed |
| 500 | `BUNDLE_LOAD_FAILED` | Unexpected I/O error reading run directory |

### 6.5 Shared Design Decisions

**Response envelope:** All three endpoints use the flat `ResponseMeta & {}` inheritance pattern, consistent with all prior endpoints.

**`data_state` semantics (aggregation endpoints):**

| Value | Meaning |
|-------|---------|
| `live` | All scanned run records parsed cleanly |
| `stale` | Scan completed but some records could not be parsed — stats based on incomplete data |
| `unavailable` | Run directory could not be accessed |

**`data_state` semantics (bundle endpoint):**

| Value | Meaning |
|-------|---------|
| `live` | All requested artifacts loaded cleanly |
| `stale` | Some artifacts missing or malformed — partial bundle |
| `unavailable` | Run directory inaccessible |

**Error responses (aggregation endpoints):**

| HTTP status | `error` code | When |
|------------|-------------|------|
| 500 | `REFLECT_SCAN_FAILED` | Run directory could not be scanned |
| 422 | `INVALID_PARAMS` | Query parameter validation failure (e.g. `max_runs=5`) |

All error responses use `OpsErrorEnvelope` shape.

**Scan discipline (aggregation endpoints):** Same bounded pattern as run browser and agent-detail:

1. Scan `ai_analyst/output/runs/` — immediate child directories only
2. Read `run_record.json` from each — deeper read than browser (needs analyst-level data)
3. Bound: scan newest-first candidate directories, **stop after inspecting `max_runs` directories** (default 50, max 200). Aggregate only valid parsed runs from that inspected window.
4. Malformed individual runs: skip, do not crash scan
5. Skipped runs reduce effective `run_count` but are tracked separately
6. **Valid parsed run:** A run counts toward `run_count` only if `run_record.json` parses as valid JSON AND contains the minimum fields needed for that endpoint's aggregation (at minimum: `run_id`, `timestamp`, `request.instrument`, `request.session`). A file that parses as JSON but lacks required fields is skipped.
7. **Timestamp ordering fallback:** If a run lacks a valid `timestamp` field, skip it during ordering. Do not attempt to infer a timestamp from directory name or file modification time.

**Response count semantics (both aggregation endpoints):**

| Field | Meaning |
|-------|---------|
| `run_count` | Successfully parsed runs actually included in aggregation |
| `skipped_runs` | Runs that were inspected but could not be parsed (malformed/missing) |
| `scan_bounds.max_runs_scanned` | Total directories inspected (= `run_count + skipped_runs`, capped at `max_runs`) |

**Cross-service coupling rule:** Reflect services must NOT import the run browser, trace, or any ops service. They read `run_record.json` (and other artifacts) directly. If a shared parsing utility already exists from PR-RUN-1 (e.g., header reader), it may be reused, but reflect must not depend on browser or trace projection internals.

### 6.6 Aggregation Field Mapping (Hypothesis — Diagnostic to Confirm)

| Aggregation metric | Required field | Hypothesized source | Fallback |
|-------------------|---------------|--------------------| ---------|
| Participation count | Presence in `analysts[]` | `run_record["analysts"]` | Count entries |
| Skip count | Presence in `analysts_skipped[]` | `run_record["analysts_skipped"]` | Count entries |
| Fail count | Presence in `analysts_failed[]` | `run_record["analysts_failed"]` | Count entries |
| Analyst stance | Per-analyst stance field | `analysts[n]["stance"]` or `analysts[n]["direction"]` (hypothesis) | `null` — exclude from alignment calc |
| Analyst confidence | Per-analyst confidence | `analysts[n]["confidence"]` (hypothesis) | `null` — exclude from avg calc |
| Was overridden | Per-analyst override indicator | Derivable from arbiter block or per-analyst field | `false` — undercount overrides |
| Final verdict | Arbiter verdict | `arbiter["verdict"]` when `arbiter["ran"] == true` | Skip from stance alignment calc |

The trace service (`ops_trace.py`) is the best reference for how these fields are currently parsed.

#### 6.6.1 Stance Alignment Formula (LOCKED)

Stance alignment measures how often a persona's directional call matched the arbiter's final verdict. The formula is:

```
stance_alignment_rate = matching_directional_stances / total_directional_stances
```

**Inclusion rules:** Only include a run in the alignment calculation when BOTH:
- The analyst produced a directional stance (bullish, bearish, long, short — normalised to a direction)
- The arbiter produced a directional verdict (BUY/ENTER_LONG, SELL/ENTER_SHORT — normalised to a direction)

**Alignment:** bullish/long stances match BUY/ENTER_LONG verdicts; bearish/short stances match SELL/ENTER_SHORT verdicts.

**Exclusion:** Neutral stances and NO_TRADE verdicts are excluded from both numerator and denominator. Including them would produce mushy alignment rates that don't mean anything useful.

**If no directional stances exist for a persona:** `stance_alignment_rate = null`.

The exact stance vocabulary will be confirmed by the diagnostic. If normalisation between stance labels and verdict labels is non-trivial, document the mapping in §13.

### 6.7 Persona Identification

The aggregation needs a stable persona identifier across runs. The diagnostic must confirm which identifier is available in the raw artifact.

**Fallback order (use first available):**

1. `entity_id` — preferred, matches roster
2. `persona_id` — explicit ID field
3. `persona` — name field
4. Normalised analyst name string — last resort

The aggregation groups by whichever identifier is found first in this order. `display_name` is derived from the identifier (or from the roster registry if a clean mapping exists). The diagnostic must report which level was found.

### 6.8 Router Ownership

| Router | Surface | Concern |
|--------|---------|---------|
| `routers/ops.py` | `/ops/*` | Agent operations |
| `routers/runs.py` | `/runs/*` | Run discovery + trace |
| `routers/market_data.py` | `/market-data/*` | Market data (PR-CHART-1) |
| `routers/reflect.py` | `/reflect/*` | Reflective intelligence (new) |

---

## 7. Acceptance Criteria

### Diagnostic ACs (mandatory)

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Per-analyst fields confirmed | Exact field names and types inside `analysts[]` entries documented | ⏳ Pending |
| AC-2 | Override derivation confirmed | How to determine per-persona override is documented | ⏳ Pending |
| AC-3 | Stance/confidence availability | Whether stance and confidence are per-analyst in `run_record.json` or only in audit log | ⏳ Pending |
| AC-4 | Audit log assessed | Whether audit log exists, its format, and whether it's needed | ⏳ Pending |
| AC-5 | Persona identifier confirmed | Stable persona identifier documented | ⏳ Pending |
| AC-6 | Artifact inventory | Which additional files exist per run directory (analysis_response.json, usage.json, etc.) | ⏳ Pending |

### Backend ACs — Persona Performance

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-7 | Endpoint exists | `GET /reflect/persona-performance` returns 200 with valid response shape | ⏳ Pending |
| AC-8 | ResponseMeta present | Flat `ResponseMeta & {}` with `version`, `generated_at`, `data_state` | ⏳ Pending |
| AC-9 | Participation counts | `participation_count`, `skip_count`, `fail_count` correct from fixtures | ⏳ Pending |
| AC-10 | Override rate | `override_count / participation_count`, `null` when 0 participation | ⏳ Pending |
| AC-11 | Stance alignment | % of stances matching final verdict, `null` when no stances | ⏳ Pending |
| AC-12 | Avg confidence | Correctly averaged, `null` when no data | ⏳ Pending |
| AC-13 | Threshold: below | `run_count < threshold` → `threshold_met: false`, `personas: []` | ⏳ Pending |
| AC-14 | Threshold: above | `run_count >= threshold` → `threshold_met: true`, personas populated | ⏳ Pending |
| AC-15 | Flagged anomaly | `override_rate > 0.5` → `flagged: true` | ⏳ Pending |
| AC-16 | Instrument filter | `?instrument=XAUUSD` scopes to XAUUSD runs only | ⏳ Pending |
| AC-17 | Session filter | `?session=NY` scopes to NY runs only | ⏳ Pending |
| AC-18 | max_runs bounds | `max_runs=5` → 422; `max_runs=200` accepted; default 50 | ⏳ Pending |
| AC-19 | Scan bounds reported | `scan_bounds` with count and timestamp range | ⏳ Pending |
| AC-20 | Skipped runs reported | `skipped_runs` count present and accurate in both aggregation responses | ⏳ Pending |

### Backend ACs — Pattern Summary

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-21 | Endpoint exists | `GET /reflect/pattern-summary` returns 200 with valid response shape | ⏳ Pending |
| AC-22 | ResponseMeta present | Flat `ResponseMeta & {}` | ⏳ Pending |
| AC-23 | Bucket grouping | Runs grouped by instrument × session | ⏳ Pending |
| AC-24 | Verdict distribution | Per-bucket counts and percentages accurate | ⏳ Pending |
| AC-25 | Per-bucket threshold | Bucket with `run_count < threshold` → `threshold_met: false`, `null` stats | ⏳ Pending |
| AC-26 | No-trade rate | `NO_TRADE count / bucket run_count` | ⏳ Pending |
| AC-27 | Flagged anomaly | `no_trade_rate > 0.8` → `flagged: true` | ⏳ Pending |
| AC-28 | max_runs bounds | Same validation as persona-performance | ⏳ Pending |

### Backend ACs — Run Bundle

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-29 | Endpoint exists | `GET /reflect/run/{run_id}` returns 200 with valid `RunBundleResponse` | ⏳ Pending |
| AC-30 | ResponseMeta present | Flat `ResponseMeta & {}` | ⏳ Pending |
| AC-31 | All artifacts present | When all files exist → all `artifact_status` = `"present"`, all `artifacts` populated | ⏳ Pending |
| AC-32 | Missing artifact tolerance | Missing `analysis_response.json` → `"missing"` status, `null` artifact, endpoint still 200 | ⏳ Pending |
| AC-33 | Malformed artifact tolerance | Unparseable artifact → `"malformed"` status, `null` artifact, endpoint still 200 | ⏳ Pending |
| AC-34 | Missing run_record | If `run_record.json` itself is missing → 404 `RUN_NOT_FOUND` | ⏳ Pending |
| AC-35 | data_state: stale on partial | Some artifacts missing → `data_state: "stale"` | ⏳ Pending |
| AC-36 | usage_summary source precedence | usage.json file → embedded usage_summary in run_record → null | ⏳ Pending |

### Shared / Structural ACs

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-37 | Malformed run tolerance | Malformed `run_record.json` skipped in aggregation scan, not a 500 | ⏳ Pending |
| AC-38 | Empty runs directory | Zero runs → 200 with `run_count: 0`, `threshold_met: false`, empty results | ⏳ Pending |
| AC-39 | data_state: live | All records parsed cleanly → `"live"` | ⏳ Pending |
| AC-40 | data_state: stale | Some records skipped → `"stale"` | ⏳ Pending |
| AC-41 | Error envelope | Scan failures use `OpsErrorEnvelope` with `REFLECT_SCAN_FAILED` | ⏳ Pending |
| AC-42 | Stance alignment formula | Alignment computed per §6.6.1: directional stances vs directional verdicts only, neutral/NO_TRADE excluded | ⏳ Pending |
| AC-43 | Persona key fallback | Persona grouping uses fallback order per §6.7: entity_id → persona_id → persona → normalised name | ⏳ Pending |
| AC-44 | Router separation | All three endpoints in `routers/reflect.py` | ⏳ Pending |
| AC-45 | No cross-service coupling | Reflect services do not import trace, browser, or ops services | ⏳ Pending |
| AC-46 | No new persistence | No SQLite, no database, no index file | ⏳ Pending |
| AC-47 | No new top-level module | Work confined to `ai_analyst/api/` | ⏳ Pending |
| AC-48 | No existing endpoint changes | ops, runs, trace, detail, roster, health endpoints unchanged | ⏳ Pending |
| AC-49 | No run_record.json changes | Artifact format unmodified | ⏳ Pending |
| AC-50 | No premature abstraction | No generic analytics engine or shared aggregation framework | ⏳ Pending |
| AC-51 | Regression safety | All pre-existing ops-domain tests pass; pre-existing failure count unchanged | ⏳ Pending |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this diagnostic is reviewed.**

### Step 1: Inspect per-analyst data in run_record.json

```bash
python -c "
import json
with open('tests/fixtures/sample_run_record.json') as f:
    data = json.load(f)
for key in ['analysts', 'analysts_skipped', 'analysts_failed']:
    entries = data.get(key, [])
    print(f'\n=== {key} ({len(entries)} entries) ===')
    if entries:
        print(json.dumps(entries[0], indent=2))
"
```

**Report:**
- Full field list of a representative `analysts[]` entry
- Whether `stance` (or equivalent) exists per analyst
- Whether `confidence` exists per analyst
- Whether `was_overridden` or equivalent exists, or must be derived
- Structure of `analysts_skipped[]` and `analysts_failed[]` entries
- Persona identifier field (e.g., `persona`, `entity_id`, `name`)

### Step 2: Determine override derivation

```bash
# Inspect arbiter block for override fields
python -c "
import json
with open('tests/fixtures/sample_run_record.json') as f:
    data = json.load(f)
print(json.dumps(data.get('arbiter', {}), indent=2))
"

# Check how trace service derives override
grep -n "override\|overridden" ai_analyst/api/services/ops_trace.py | head -15
```

**Report:**
- Whether override is per-analyst or per-verdict
- How trace currently derives `was_overridden`
- Whether same derivation can be used in aggregation

### Step 3: Inventory run directory artifacts

```bash
# Check what files exist per run (using fixture or any real run)
ls -la tests/fixtures/ | grep -i "run\|analysis\|usage"

# Check run artifact references in existing code
grep -rn "analysis_response\|usage\.json\|usage_summary" ai_analyst/ --include="*.py" | head -15

# Check the artifacts block in run_record.json
python -c "
import json
with open('tests/fixtures/sample_run_record.json') as f:
    data = json.load(f)
print(json.dumps(data.get('artifacts', {}), indent=2))
print(json.dumps(data.get('usage_summary', {}), indent=2))
"
```

**Report:**
- Which artifact files exist per run directory (or are referenced)
- Whether `analysis_response.json` and `usage.json` are separate files or embedded in `run_record.json`
- Structure of usage data (tokens, models, costs)
- Whether the bundle endpoint needs to read 1 file or 3

### Step 4: Assess audit log

```bash
ls -la logs/runs/ 2>/dev/null || echo "No logs/runs/ directory"
grep -n "audit\|jsonl\|log.*run" ai_analyst/api/services/ops_trace.py | head -10
find tests/ -name "*.jsonl" | head -5
```

**Report:**
- Whether audit log directory exists
- What role it plays in trace projection
- Whether aggregation needs it, or can work from `run_record.json` alone

### Step 5: Confirm persona identification

```bash
grep -n "persona\|entity_id\|display_name" ai_analyst/api/services/ops_roster.py | head -10
grep -n "persona\|entity_id\|roster\|map" ai_analyst/api/services/ops_trace.py | head -15
```

**Report:**
- Persona identifier in run artifacts
- Whether mapping from artifact name to roster entity_id exists

### Step 6: Run baseline tests

```bash
python -m pytest tests/ -q --tb=no
cd ui && npx vitest run --reporter=verbose 2>&1 | tail -20
```

**Report:** Backend ops count (~239), frontend ops count (~77), pre-existing failures noted.

### Step 7: Propose smallest patch set

- Determine: can all endpoints be built from `run_record.json` alone?
- If audit log or extra artifacts are needed, add graceful degradation
- Files to create / modify, line estimates
- Any metric reductions if data is sparser than expected

**Smallest safe option:** If a metric cannot be reliably computed, return `null` rather than fabricating. Document reductions in §13.

**No premature abstraction:** One aggregation service, one bundle service, one model file, one router, tests.

---

## 9. Implementation Constraints

### 9.1 General rule

The reflect endpoints are **read-side projections** over existing run artifacts. They scan `run_record.json` files (and optionally other artifacts), extract per-analyst and per-verdict data, compute bounded statistics, and return them. No writes, no mutations, no ML, no config changes.

### 9.1b Implementation Sequence

1. **Diagnostic** — confirm per-analyst field structure, override derivation, artifact inventory, persona identification
   - Gate: diagnostic reviewed and approved

2. **Backend aggregation service** — scan runs, extract analyst/verdict data, compute statistics
   - Verify: baseline backend tests still pass

3. **Backend bundle service** — load and assemble artifact bundle per run with graceful degradation
   - Verify: baseline still passes

4. **Backend models** — Pydantic models for all three response shapes (flat `ResponseMeta & {}`)

5. **Backend endpoints + router** — `routers/reflect.py` with all three endpoints, register in `main.py`
   - Verify: baseline + new tests pass

6. **Backend contract tests** — deterministic tests using temp dirs with fixture copies
   - Fixtures should include: N clean runs (above threshold), sparse runs (below threshold), mixed instruments/sessions, malformed runs, runs with missing analyst data, runs with missing secondary artifacts
   - Gate: all backend tests pass

7. **Full regression** — ops-domain zero regressions (AC-51)

### 9.2 Code change surface

**New files:**

| File | Role | Est. lines |
|------|------|-----------|
| `ai_analyst/api/services/reflect_aggregation.py` | Scan runs, compute persona + pattern stats | ~250 |
| `ai_analyst/api/services/reflect_bundle.py` | Load artifact bundle per run | ~80 |
| `ai_analyst/api/models/reflect.py` | Pydantic models for all three endpoints | ~100 |
| `ai_analyst/api/routers/reflect.py` | All three endpoints | ~90 |
| `tests/test_reflect_endpoints.py` | Backend contract tests | ~400 |

**Modified files:**

| File | Change | Est. delta |
|------|--------|-----------|
| `ai_analyst/api/main.py` | Register `reflect` router | +3 |

**No changes expected to:**
- `ai_analyst/api/routers/ops.py`, `runs.py` — unchanged
- `ai_analyst/api/services/ops_*.py`, `ops_run_browser.py` — unchanged
- `market_data_officer/` — unchanged
- `run_record.json` artifacts — format unchanged
- `ui/` — no frontend changes

### 9.3 Out of scope (repeat + negative scope lock)

**Hard constraints:**
- No frontend (PR-REFLECT-2)
- No ML, inference, or embeddings — aggregation only
- No config mutation — advisory only
- No new persistence — read-side only
- No new top-level module
- No changes to existing endpoints
- Deterministic fixture tests only

**No premature abstraction:**
- No generic analytics engine
- No shared aggregation framework
- No cross-service imports

**PR-REFLECT-1 does not:**
- Build the Reflect workspace UI (PR-REFLECT-2)
- Add bias accuracy or outcome tracking (PR-REFLECT-2)
- Add confidence calibration analysis (PR-REFLECT-2)
- Add parameter suggestions (PR-REFLECT-3)
- Add analyst influence analysis (PR-REFLECT-3)
- Add chart integration (PR-CHART-2 + PR-REFLECT-3)
- Add decision simulation or "why was this wrong?" (future)
- Modify persona configurations based on performance data

---

## 10. Success Definition

PR-REFLECT-1 is done when: `GET /reflect/persona-performance` returns per-persona aggregated statistics (participation, override rate, stance alignment per §6.6.1, confidence) with `skipped_runs` tracking; `GET /reflect/pattern-summary` returns instrument × session verdict distributions with per-bucket thresholds and `skipped_runs`; `GET /reflect/run/{run_id}` returns the complete artifact bundle with graceful degradation for missing files and usage_summary source precedence; the minimum threshold (10 runs per bucket) is enforced; anomaly flagging works as heuristic attention signals (>50% override, >80% NO_TRADE); persona grouping uses the confirmed fallback order; all 51 acceptance criteria pass with deterministic fixture-based tests; no regressions; no new persistence, no ML, no config mutation, no frontend, no premature abstraction.

---

## 11. Why This Phase Matters

| Without Reflective Aggregation | With Reflective Aggregation |
|-------------------------------|---------------------------|
| Operator reviews runs one at a time | "Persona X overridden in 70% of runs" at a glance |
| No instrument/session performance patterns | "XAUUSD NY produces NO_TRADE 85% of the time" surfaces immediately |
| Can't answer "which analyst should I trust?" | Stance alignment and average reported confidence give descriptive trust proxies |
| No foundation for parameter suggestions | Aggregation data feeds PR-REFLECT-3's rules-based suggestions |
| No full artifact deep dive from one endpoint | Bundle endpoint gives complete run inspection in a single fetch |
| The system never observes itself | First step: **observe → suggest → adapt → refine** |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 7 — Agent Ops | 4 endpoints, 3 modes, detail sidebar | ✅ Done |
| PR-RUN-1 — Run Browser | `GET /runs/` + RunBrowserPanel | ✅ Done — +56 tests |
| PR-CHART-1 — OHLCV seam + chart | Diagnostic + conditional chart endpoint | ⏳ In parallel |
| **PR-REFLECT-1 — Aggregation endpoints** | **Persona perf + pattern summary + run bundle** | **⏳ Spec drafted** |
| PR-REFLECT-2 — Reflect workspace UI | `/reflect` frontend + decision readback | 📋 Planned — depends on PR-REFLECT-1 |
| PR-REFLECT-3 — Analyst influence + suggestions | Override detection, rules-based suggestions | 📋 Planned |
| PR-REFLECT-4 — Decision quality + simulation | Outcome tracking, "why was this wrong?" | 💭 Concept |

---

## 13. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 8).*

*Must include: per-analyst field structure, override derivation method, persona identifier (which fallback level), artifact inventory (which files exist per run, usage_summary source), audit log assessment, stance vocabulary for alignment normalisation, any metric reductions.*

---

## 14. Doc Corrections to Apply on Branch

1. **`docs/AI_TradeAnalyst_Progress.md`** — header, Recent Activity row, Phase Index, Roadmap, §6 Next Actions
2. **`PHASE_8_PLAN.md`** — update Reflect section status

### Review for update:

3. **`docs/architecture/system_architecture.md`** — new `/reflect` API surface
4. **`docs/architecture/repo_map.md`** — new files
5. **`docs/architecture/technical_debt.md`** — add entry if data gaps limit aggregation quality
6. **`docs/architecture/AI_ORIENTATION.md`** — update only if onboarding-critical

---

## 15. Appendix — Recommended Agent Prompt

```
Read `docs/specs/PR_REFLECT_1_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report
findings before changing any code:

1. Inspect per-analyst data: field names/types in analysts[] entries
2. Determine override derivation: per-analyst field, arbiter cross-ref, or audit log?
3. Inventory run directory artifacts: which files exist per run?
   Do analysis_response.json and usage.json exist as separate files?
4. Assess audit log: exists? format? needed?
5. Confirm persona identification: stable identifier for grouping
6. Run baseline tests: record counts
7. Propose smallest patch set, noting metric reductions if data is sparse

Report per-analyst field structure and artifact inventory prominently
at the top of the diagnostic report.

Hard constraints:
- Aggregation only — no ML, no inference, no embeddings
- Advisory only — no config mutation
- Minimum threshold: 10 runs per bucket, below → empty stats, NOT error
- Read-side only — no writes, no new persistence
- No new top-level module — ai_analyst/api/ only
- No frontend — backend endpoints and tests only (PR-REFLECT-2 does UI)
- No cross-service coupling — do not import trace, browser, or ops services
- No premature abstraction — one aggregation service, one bundle service,
  one model file, one router, tests
- All endpoints use flat ResponseMeta & {} pattern
- Scan semantics: scan newest-first dirs, stop after max_runs dirs inspected,
  aggregate only valid parsed runs. Report skipped_runs count.
- Stance alignment per §6.6.1: directional stances vs directional verdicts only,
  exclude neutral/NO_TRADE from both numerator and denominator
- Persona grouping: use fallback order per §6.7 (entity_id → persona_id →
  persona → normalised name)
- flagged fields are simple heuristic attention signals, not significance tests
- Provisional metrics (override, stance alignment, confidence): return null
  if raw fields unavailable. Do not block the phase on incomplete richness.
- Bundle endpoint: graceful degradation for missing artifacts,
  404 only when run_record.json itself is missing.
  usage_summary source: usage.json file → embedded in run_record → null
- Malformed runs: skip in scan, do not crash
- Deterministic fixture tests — create fixtures with: clean runs above
  threshold, sparse runs below threshold, mixed instruments/sessions,
  malformed runs, missing analyst data, missing secondary artifacts
- No changes to existing endpoints or run_record.json format

Do not change any code until diagnostic is reviewed and approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/PR_REFLECT_1_SPEC.md` — ✅ Complete, flip all 51 AC cells,
   populate §13
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update
3. Apply doc corrections from §14
4. Review architecture docs per §14 criteria
5. Cross-document sanity check
6. Return Phase Completion Report

Commit all doc changes on the same branch.
```
