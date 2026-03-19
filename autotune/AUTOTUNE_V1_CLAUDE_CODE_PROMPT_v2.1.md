# AutoTune v1 — Claude Code Implementation Prompt (v2)

**Project:** AutoTune — Autonomous Lens Parameter Optimization (Side Quest)
**Scope:** Phase A1 harness build — structure_short and structure_medium evaluation loop
**Status:** Design locked. Gate review passed. This prompt is the implementation instruction.
**Revision:** v2.1 — v2 patches applied (manifest write ownership, session-scoped IDs, data-derived bar expectation, ATR formula, warmup rule, validation split, float precision, Outcome C hardening)

---

## What This Project Is

A governed research harness that runs the existing AI Trade Analyst production lens pipeline over historical price data, perturbs approved parameters, evaluates directional usefulness of the resulting lens outputs, and records versioned experiment results — without breaking production contracts.

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch): an AI agent iterates on parameters, runs experiments, keeps what improves the metric, discards what doesn't. The human iterates on the `program.md` skill file; the agent iterates on the parameters.

**This is a side quest.** It lives in a standalone `autotune/` directory. It consumes production lens code but does not modify it.
Repo location: This project lives at autotune/ in the root of the AI Trade Analyst repo (AI-trade-analyst/autotune/). The production lens code it imports is at ai_analyst/ in the same repo root. All paths in this prompt are relative to the repo root, not to the autotune/ directory.
---

## What Already Exists (Production Lens System)

The AI Trade Analyst has three deterministic lenses with clean contracts:

- **Structure lens** (`ai_analyst/lenses/structure.py`) — swing points, S/R, trend state (HH/HL/LH/LL), breakout/rejection
- **Trend lens** (`ai_analyst/lenses/trend.py`) — EMA alignment, slope, trend phase
- **Momentum lens** (`ai_analyst/lenses/momentum.py`) — ROC, impulse, acceleration, exhaustion

Each lens:
- Takes normalised OHLCV `dict[str, np.ndarray]` + a config dict
- Returns `LensOutput` (lens_id, version, status, error, data)
- Is deterministic, stateless, side-effect-free
- Never raises — `LensBase.run()` catches all exceptions

The snapshot builder (`ai_analyst/core/snapshot_builder.py`) assembles lens outputs into derived signals:
- `derived.alignment_score` (float 0.0–1.0)
- `derived.conflict_score` (float 0.0–1.0)
- `derived.signal_state` ("SIGNAL" | "NO_SIGNAL")

Direction extraction paths per lens:
- Structure: `trend.local_direction` → bullish | bearish | ranging
- Trend: `direction.overall` → bullish | bearish | ranging
- Momentum: `direction.state` → bullish | bearish | neutral

The data adapter (`ai_analyst/lenses/data_adapter.py`) normalises OHLCV into lens input format via `ohlcv_response_to_lens_input()`.

**For this build, only the Structure lens matters.** Trend and Momentum are out of scope for Phase A.

---

## What to Build

Six deliverables. Two are different kinds of work:

**Deterministic Python code** (components 1–5): Write code that runs reliably, loads data, executes lenses, scores outcomes, manages state. These are engineering artifacts.

**Agent skill file** (component 6): Write a `program.md` that instructs a future AI agent on how to run the iteration loop. This is a governance document, not code.

Do not confuse the two. The harness runs deterministically. The agent reads `program.md` and decides which parameter to change next — but the harness enforces all hard rules (bounds, acceptance policy, logging) regardless of what the agent tries.

---

### Component 1: Data Loader (`data_loader.py`)

**Purpose:** Pull historical 1H OHLCV for XAUUSD via yFinance. Cache locally for fast repeated access. Return raw dataframes — adaptation to lens input format happens downstream in the evaluator.

**Output contract:** `data_loader.py` returns a pandas DataFrame (or reads from parquet) with columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`. It does NOT convert to `dict[str, np.ndarray]` lens format. That conversion is the evaluator's responsibility — the evaluator must call the production adapter `ohlcv_response_to_lens_input()` (or an equivalent thin wrapper) so that format compatibility is owned by one component, not split across two.

**Provider policy (deterministic ticker selection):**
- Primary ticker: `GC=F` (gold futures continuous contract, 1H available on yFinance)
- Fallback ticker: `XAUUSD=X` (if `GC=F` returns empty or insufficient data)
- If both fail: hard error, no silent degradation
- **Acceptance rule:** Data is accepted only if it contains ≥ 95% of expected bars for the requested date range. Expected bars are computed from the fetched dataset itself, not from an exchange calendar model: group rows by trading date, count bars per trading day, compute the modal or median bars-per-day across sufficiently populated trading days, then multiply by the number of distinct trading days in the requested range represented in the fetched data. Do NOT build or import an exchange calendar model. If coverage falls below 95%, log actual vs expected bar count and halt. Record the actual bar count and expected bar count in `session_meta.json` under `data_source.bar_count` and `data_source.expected_bar_count`.
- **Reproducibility:** The selected ticker and actual date range must be written into `session_meta.json` under `data_source.ticker` and `data_source.actual_range`.

**Requirements:**
- Fetch 1H candle data for XAUUSD from yFinance
- Date range: at minimum 2020-01-01 through 2025-12-31
- Store as local parquet file in `autotune/data/` for fast reload
- Support date-range slicing for train/test splits
- If cached data exists and covers the requested range, load from cache — don't re-fetch
- Include a `--refresh` CLI flag to force re-fetch

**Train/test split for v1:**
- Training: 2020-01-01 to 2024-12-31
- Validation (held out): 2025-01-01 to 2025-12-31 (or latest available)
- The agent tunes against training data only. Validation is for human review.

**Validation in v1 scope:** The data loader stores the full date range (including 2025+) in the parquet cache. The evaluator CLI accepts `--split train` (default, uses training range from eval_config) or `--split validation` (uses held-out range). This is a simple date-range filter, not a separate mode — the evaluator logic is identical. Including `--split validation` costs near-zero implementation effort and avoids needing a separate script for human review of held-out accuracy. The runner must not update `instance_manifest.json` when invoked with `--split validation`; validation runs are read-only evaluation passes.

---

### Component 2: Windowed Evaluator (`evaluator.py`)

**Purpose:** Score a lens configuration against historical data. This is the "ruler" — it measures how good a parameter set is.

**Data adaptation responsibility:** The evaluator owns the conversion from raw DataFrame (from data_loader) to lens-compatible `dict[str, np.ndarray]` format. It must call the production adapter `ohlcv_response_to_lens_input()` or replicate its exact output shape. This keeps the boundary clean: data_loader handles fetching/caching, evaluator handles format adaptation and lens execution.

**Prediction extraction contract:**
- Source field: `LensOutput.data["trend"]["local_direction"]`
- Required `LensOutput.status`: must be `"success"`
- Valid direction values: `"bullish"`, `"bearish"`, `"ranging"`
- **If `LensOutput.status == "failed"`:** Do NOT score. Increment `lens_errors` diagnostic counter. Do NOT count as ranging, unresolved, or any scored category.
- **If `LensOutput.status == "success"` but `data["trend"]["local_direction"]` is missing or not a valid enum value:** Treat as lens error. Increment `lens_errors`. Log the anomaly.
- **Hard stop rule:** If `lens_errors` exceeds 5% of total evaluation steps, halt the evaluation run and return an error result. Do not produce metrics from a run where the lens is failing frequently — the config is likely invalid.

**Excursion measurement contract:**
- **Reference price:** `close[T]` — the closing price of the bar at which the prediction is issued.
- **Forward window:** Bars `T+1` through `T+horizon_bars` inclusive. The bar at T is NOT part of the forward window — the prediction is issued at close of bar T, so bar T's price action is already known.
- **Bullish excursion (favorable for bullish call):** `max(high[T+1], high[T+2], ..., high[T+horizon_bars]) - close[T]`
- **Bearish excursion (favorable for bearish call):** `close[T] - min(low[T+1], low[T+2], ..., low[T+horizon_bars])`
- **Adverse excursion (bullish call):** `close[T] - min(low[T+1], ..., low[T+horizon_bars])`
- **Adverse excursion (bearish call):** `max(high[T+1], ..., high[T+horizon_bars]) - close[T]`

**Outcome classification (bar-by-bar sequential scan):**
Do NOT compute max excursion across the whole window and then classify. Instead, scan bars T+1, T+2, ... T+horizon_bars **in order** and check thresholds at each bar:

```
atr = ATR(14) computed as of bar T
confirm_threshold = confirmation_atr_mult × atr
invalid_threshold = invalidation_atr_mult × atr

For each bar B from T+1 to T+horizon_bars, in order:
    If bullish call:
        favorable = high[B] - close[T]
        adverse   = close[T] - low[B]
    If bearish call:
        favorable = close[T] - low[B]
        adverse   = high[B] - close[T]
    
    If adverse >= invalid_threshold:
        → INVALIDATED (stop scanning, even if favorable also crossed)
    If favorable >= confirm_threshold:
        → CONFIRMED (stop scanning)

If loop completes without either threshold crossed:
    → UNRESOLVED
```

**Same-bar rule:** Within a single bar, if BOTH thresholds are reachable (the bar's range is wide enough to cross both), classify as **INVALIDATED** conservatively. This is handled naturally by checking adverse BEFORE favorable within the same bar in the loop above.

**Invalidation-first rationale:** This is the conservative scoring philosophy for v1. A bar where both thresholds are geometrically reachable is ambiguous because OHLC data does not encode intrabar sequence. Defaulting to invalidation avoids inflating accuracy with ambiguous outcomes.

**ATR computation (locked formula):**
- True Range: `TR[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))`
- ATR: Wilder's smoothed moving average with period 14: `ATR[i] = ((ATR[i-1] × 13) + TR[i]) / 14`
- Initial ATR (bar 14): simple mean of TR[1..14]
- The evaluator may use an equivalent library implementation (e.g., `ta.volatility.AverageTrueRange` from the `ta` library or pandas-ta) as long as the output matches Wilder's method. If using a library, name it in a code comment.

**Core evaluator loop:**
**Warmup rule:** The first valid scoring index is `T_start = max(lookback_bars, atr_period + 1)` where `lookback_bars` comes from the current lens config and `atr_period` comes from `eval_config.json`. All bars before `T_start` are skipped — the evaluator does not attempt to run the lens or compute ATR on insufficient history. The stepping loop begins at `T_start` and increments by `step_bars` from there.

```
For each timestamp T in training data, starting at T_start, stepping by step_bars:
    1. Slice OHLCV data up to T (lens cannot see future bars)
    2. Ensure enough future bars exist: if T + horizon_bars > data length, skip
    3. Adapt sliced data to lens input format
    4. Compute ATR(14) as of bar T
    5. Run Structure lens with current config → get LensOutput
    6. If LensOutput.status != "success" → increment lens_errors, skip
    7. Extract prediction: data["trend"]["local_direction"]
    8. If prediction is "ranging" → increment ranging_calls, skip scoring
    9. Scan forward bars T+1..T+horizon_bars per sequential scan above
    10. Classify outcome: CONFIRMED / INVALIDATED / UNRESOLVED
    11. Record result
Return aggregate metrics
```

**Metrics to compute and return:**
- `total_calls`: int — bullish + bearish calls issued (excluding ranging and lens errors)
- `confirmed`: int
- `invalidated`: int
- `unresolved`: int
- `resolved_calls`: int — confirmed + invalidated (store explicitly, do not derive at query time)
- `accuracy`: float — confirmed / resolved_calls (if resolved_calls == 0, return 0.0)
- `resolve_rate`: float — resolved_calls / total_calls (if total_calls == 0, return 0.0)

**Diagnostics to compute and return:**
- `ranging_calls`: int — times the lens said "ranging"
- `ranging_pct`: float — ranging_calls / (total_calls + ranging_calls + lens_errors)
- `bullish_calls`: int
- `bearish_calls`: int
- `lens_errors`: int — times the lens returned status="failed" or had missing/invalid direction
- `mean_atr_at_call`: float — average ATR(14) across all scored calls
- `data_range`: str — date range of evaluation window
- `total_steps`: int — total evaluation steps attempted (including ranging and errors)

**Configuration:** Read all evaluator settings from `eval_config.json`. The evaluator does not hardcode any thresholds — everything comes from the config file. The eval_config must include date ranges for both splits:
- `train_date_range`: `{"start": "2020-01-01", "end": "2024-12-31"}`
- `validation_date_range`: `{"start": "2025-01-01", "end": "2025-12-31"}`

These are shared across all instances (not per-instance) and live at the top level of the eval_config alongside the `meta` block.

**The evaluator must be deterministic.** Same config + same data = same result, every time.

**Error handling:** If `eval_config.json` is missing, malformed, contains unknown instance IDs, or has wrong field types, the evaluator must raise a clear error immediately — no partial runs, no fallback defaults, no partial log writes.

---

### Component 3: Runner / Orchestrator (`run.py`)

**Purpose:** Orchestrate one iteration of the tuning loop. Load config, run evaluator, compare to baseline, accept or reject, log result.

**CLI interface (v1 — locked to CLI args only, no `next_change.json`):**
```bash
python run.py --instance structure_short --param lookback_bars --value 55
# Optional flags:
python run.py --instance structure_short --param lookback_bars --value 55 --reasoning "Testing more reactive lookback"
# Validation (read-only, no manifest update, no acceptance policy):
python run.py --instance structure_short --param lookback_bars --value 55 --split validation
```

**Manifest write ownership:** In v1, the runner is the sole writer of `instance_manifest.json`. The agent proposes changes via CLI arguments; the runner validates, evaluates, and applies (or rejects) them. The agent never directly edits the manifest file. The `program.md` instruction "you may only edit `instance_manifest.json`" should be understood as "you may only propose changes to manifest values via the runner CLI" — not as direct file editing.

**Single-iteration flow:**
```
1. Read instance_manifest.json (current best params)
2. Read eval_config.json (evaluator settings)
3. Validate both files: required keys present, correct types, instance_id exists
   → On any validation failure: hard error, no partial execution, no log write
4. Load training data via data_loader
   → On data load failure (missing parquet, empty DataFrame): hard error
5. Run evaluator with current params → baseline_metrics
6. Read proposed change from CLI args (param name, new value)
7. Validate proposed change:
   - Parameter must exist in the instance's manifest and be mutable
   - New value must be within [min, max]
   - New value must land on step grid: (new_value - min) % step == 0
   - Only one parameter changed (enforced by CLI: one --param and one --value)
   → On any validation failure: hard error with clear message, no evaluator run
8. Run evaluator with proposed params → candidate_metrics
9. Apply acceptance policy (see below)
10. If accepted → update instance_manifest.json (overwrite the changed param's current value)
11. If rejected → no manifest change
12. Append experiment log entry to logs/experiment_log.jsonl
13. Return result summary to stdout
```

**Baseline definition:** The baseline for each iteration is the current manifest state immediately before the proposed change. NOT the original session seed. This means accepted changes compound — iteration 5's baseline reflects any improvements from iterations 1–4.

**Acceptance policy (hardened v1 rules):**

A candidate is ACCEPTED only if ALL of the following are true:
1. `candidate.accuracy > baseline.accuracy` (strict greater-than — ties are REJECTED)
2. `candidate.resolve_rate >= 0.70` (minimum resolve-rate floor — prevents gaming via ranging)
3. `candidate.resolved_calls >= 0.80 * baseline.resolved_calls` (prevents accuracy inflation from fewer decisive calls)

If any condition fails, the candidate is REJECTED. Log which condition(s) failed in the `rejection_reasons` list.

**Comparison precision:** All accuracy and resolve-rate comparisons use raw Python float values. Do NOT round before comparing. Rounding is only applied for display/logging (3 decimal places in log output). An accuracy improvement of 0.0001 is a valid strict improvement.

**Session management:**

Session lifecycle rules:
- A new session is created when the runner detects no active session for the target instance, OR when `--new-session` flag is passed.
- Detection: if `sessions/{instance_id}/active/session_meta.json` exists and is valid, resume that session. Otherwise, create new.
- Creating a session: generate `session_id` as `{instance_id}_{YYYYMMDD_HHMMSS}` (e.g., `structure_short_20260320_143200`), write session artifacts.
- There is exactly one active session per instance at any time.

Session artifacts (written once at session start):
- `sessions/{instance_id}/active/session_meta.json`:
  - `session_id`
  - `started_utc`
  - `target_instance` (e.g., "structure_short")
  - `train_date_range`
  - `seed_params` (copy of starting manifest values for this instance)
  - `eval_config_hash` (SHA256 of eval_config.json)
  - `harness_version` (from a VERSION constant)
  - `data_source.ticker` (which yFinance ticker was used)
  - `data_source.actual_range` (actual date range of cached data)
  - `data_source.bar_count` (actual number of bars in training split)
  - `data_source.expected_bar_count` (expected bars computed from data-derived trading calendar)
  - `pivot_mode` (`"continuous"` if Outcome A/B shim; `"enum_only"` if Outcome C degradation)
- `sessions/{instance_id}/active/seed_manifest.json`: immutable copy of instance params at session start

When a session is explicitly closed (future feature, not in v1 scope), move `active/` contents to `sessions/{instance_id}/closed/{session_id}/`.

**Error handling:** If any file (manifest, eval_config, data) is missing, malformed, or contains invalid types: hard error with clear message. No manifest mutation. No partial log write. The runner must be atomic in its effects — either a complete iteration (log + possible manifest update) or nothing.

---

### Component 4: Experiment Log Writer

**Purpose:** Append one JSON line per iteration to `logs/experiment_log.jsonl`.

**Experiment ID generation:** `{session_id}_EXP{NNN}` where NNN is zero-padded, incremented from the highest existing experiment **matching the current `session_id`** in the log file. The runner must filter by `session_id`, not by `instance_id` or global line count. Example: `structure_short_20260320_143200_EXP001`. If the log file doesn't exist or has no entries for this session, start at 001.

**Canonical log entry schema (this is the single source of truth — `experiment_log_schema.json` is reference documentation only):**

```json
{
  "experiment_id": "structure_short_20260320_143200_EXP001",
  "instance_id": "structure_short",
  "timestamp_utc": "2026-03-20T14:35:12Z",
  "session_id": "structure_short_20260320_143200",
  "iteration": 1,
  "change": {
    "parameter": "lookback_bars",
    "old_value": 60,
    "new_value": 55
  },
  "params_snapshot": {
    "lookback_bars": 55,
    "pivot_window": 3
  },
  "metrics": {
    "total_calls": 1842,
    "confirmed": 978,
    "invalidated": 714,
    "unresolved": 150,
    "resolved_calls": 1692,
    "accuracy": 0.578,
    "resolve_rate": 0.919
  },
  "diagnostics": {
    "ranging_calls": 623,
    "ranging_pct": 0.247,
    "bullish_calls": 1012,
    "bearish_calls": 830,
    "lens_errors": 0,
    "mean_atr_at_call": 18.45,
    "data_range": "2020-01-01 to 2024-12-31",
    "total_steps": 2465
  },
  "decision": "accepted",
  "rejection_reasons": [],
  "accuracy_before": 0.561,
  "accuracy_after": 0.578,
  "accuracy_delta": 0.017,
  "agent_reasoning": "Reducing lookback from 60 to 55 to test whether more reactive structure detection improves short-horizon confirmation rate"
}
```

**Required fields:** Every field above is mandatory on every log line. `rejection_reasons` is an empty list on accepted iterations. `agent_reasoning` may be an empty string on manual runs but the key must be present.

**The log is append-only.** Never overwrite, truncate, or edit existing entries.

---

### Component 5: Harness Shim (Pivot Window Adapter)

**Purpose:** Translate the numeric `pivot_window` value from the manifest into whatever form the Structure lens expects internally.

**Context:** The production Structure lens uses `swing_sensitivity` as a string enum ("low"/"medium"/"high") that maps to pivot window sizes (3/5/8). AutoTune exposes `pivot_window` as a direct integer for continuous search.

**This component has a go/no-go gate in the diagnostic protocol (Step 1).** The diagnostic must determine whether numeric injection is feasible without editing production code. Three possible outcomes:

**Outcome A — Clean injection point exists:** The lens converts the enum to an int early in one place. The harness can subclass or wrap the lens and override that single mapping. Build the shim as a thin wrapper class in `autotune/shims/structure_shim.py` that inherits from or wraps the Structure lens and injects the numeric value.

**Outcome B — Enum propagates deep, but config dict is read early:** The lens reads `swing_sensitivity` from the config dict and converts to int in `_compute()`. The harness can pass a modified config dict with the int value pre-injected under whatever internal key the lens uses after conversion. This is config-level injection — no subclassing needed.

**Outcome C — No clean injection is possible without production edits:** The enum string is used throughout the computation in ways that can't be intercepted externally without brittle monkeypatching. In this case, **Phase A degrades to enum-compatible values only**: `pivot_window` in the manifest is constrained to `{3, 5, 8}` (matching low/medium/high), `step` is removed (the three values are the complete domain), and the harness maps back to the enum string before calling the lens. Before tuning starts, the runner must validate that the manifest's `pivot_window.current` is one of {3, 5, 8} and reject any other value. `session_meta.json` must include `"pivot_mode": "enum_only"` (or `"continuous"` if Outcome A/B). Log this as a known limitation. File it as a Phase B item: "unlock continuous pivot_window requires a narrow production-side refactor to externalize the int."

**The diagnostic must report which outcome applies and show the exact code path.** Do not implement a shim based on assumptions — implement based on diagnostic evidence.

**Hard rule:** No monkeypatching. If the shim requires `unittest.mock.patch`, `setattr` on production classes, or any technique that modifies production objects at runtime, it is not acceptable. Use subclassing, wrapping, or config injection only.

---

### Component 6: Agent Skill File (`program.md`)

**Purpose:** Instruct a future AI agent on how to run the AutoTune iteration loop. This is the "program" the human iterates on (Karpathy's model: human writes the program, agent writes the code/params).

**What program.md must contain:**

1. **Role definition:** You are a parameter optimization agent. Your job is to improve the accuracy of a Structure lens instance by proposing one parameter change at a time.

2. **File governance rules:**
   - You may ONLY propose changes to `instance_manifest.json` values via the runner CLI (`python run.py --param ... --value ...`). You do not edit the manifest file directly — the runner validates and applies changes.
   - You may NOT edit: `eval_config.json`, `evaluator.py`, `data_loader.py`, `run.py`, `program.md`
   - You may NOT add, remove, or rename parameters
   - You may NOT change min, max, step, or mutable fields

3. **Candidate proposal rules (deterministic v1 policy):**
   - One parameter change per iteration
   - One step increment or decrement only (no jumping)
   - Alternate between parameters unless one has a clear signal from recent results
   - Test both directions (up and down) before moving on
   - Never propose a value outside declared bounds
   - Never propose a value off the step grid

4. **Acceptance rules (read-only — the harness enforces these, but the agent should understand them):**
   - Strict improvement required (ties rejected)
   - Minimum resolve rate: 0.70
   - Minimum resolved calls: 80% of baseline
   - All three conditions must pass

5. **Reasoning requirement:**
   - Before each proposal, write a brief rationale (1–2 sentences) explaining WHY this change might help, based on the previous iteration's results
   - After each result, note what you learned

6. **Session discipline:**
   - Start by reviewing `session_meta.json` and recent log entries
   - Do not repeat a change that was already tried and rejected in the same session
   - If 5 consecutive iterations are rejected, pause and reassess strategy
   - Target: 10–30 iterations per session

7. **What the agent must NOT do:**
   - Modify evaluator code or config
   - Skip the runner (no direct lens calls)
   - Propose multiple parameter changes at once
   - Change bounds or step sizes
   - Claim a result without running the evaluator

---

## Directory Structure

```
autotune/
├── program.md                  # Agent skill file (human edits, agent reads)
├── evaluator.py                # Windowed evaluator (read-only to agent)
├── data_loader.py              # Historical data fetcher (read-only to agent)
├── run.py                      # Orchestrator / runner (read-only to agent)
├── eval_config.json            # Evaluator configuration (read-only to agent)
├── instance_manifest.json      # Parameter manifest (agent edits current values only)
├── experiment_log_schema.json  # Schema reference documentation (not consumed by code)
├── AUTOTUNE_V1_DESIGN.md       # Design summary (reference only)
├── shims/
│   └── structure_shim.py       # Pivot window adapter (if Outcome A/B from diagnostic)
├── data/
│   └── XAUUSD_1H.parquet      # Cached OHLCV data
├── sessions/
│   └── {instance_id}/
│       └── active/
│           ├── session_meta.json
│           └── seed_manifest.json
├── logs/
│   └── experiment_log.jsonl    # Append-only iteration log (all sessions, all instances)
└── tests/
    └── ...                     # Tests for all harness components
```

---

## Pre-Code Diagnostic Protocol

Before writing any implementation code, run these steps and report findings:

### Step 1: Inspect the Structure lens source — SHIM FEASIBILITY (go/no-go gate)
- Read `ai_analyst/lenses/structure.py`
- Find where `swing_sensitivity` is converted to a numeric pivot window
- Trace the numeric value through the computation path
- **Report with conclusion:** Does Outcome A, B, or C from Component 5 apply?
- **Show proof:** Paste the exact code path demonstrating how a numeric `pivot_window` value can reach the computation without editing production code. If it cannot, state that clearly — Phase A will degrade to enum-only values.
- This is a go/no-go gate. Do not proceed to implementation until this is answered.

### Step 2: Inspect the LensBase contract
- Read `ai_analyst/lenses/base.py`
- Confirm: `LensBase.run()` signature, `LensOutput` fields, error handling pattern
- Confirm: what happens when `_compute()` raises — does `run()` return `status="failed"` with an error message?
- Report: any surprises vs the reference doc

### Step 3: Inspect the data adapter
- Read `ai_analyst/lenses/data_adapter.py`
- Confirm: `ohlcv_response_to_lens_input()` signature, input expectations, and output format
- Report: exact dict keys and array dtypes returned
- Report: whether the evaluator can call this function directly or needs a thin wrapper to bridge from pandas DataFrame

### Step 4: Test yFinance data availability
- Attempt to pull 1H XAUUSD data from yFinance using `GC=F` first, then `XAUUSD=X` if needed
- Report: which ticker works, any gaps, data quality issues, approximate row count
- Report: actual date range coverage — does 2020-01-01 to 2025-12-31 have ≥ 95% expected bars?
- If neither ticker provides adequate data, halt and report — do not invent workarounds

### Step 5: Confirm lens can run standalone
- Import the Structure lens
- Feed it a small slice of real OHLCV data (via the adapter confirmed in Step 3) with default config
- Confirm it returns a valid LensOutput with `status="success"`
- Confirm `data["trend"]["local_direction"]` exists and is one of: bullish, bearish, ranging
- Report: full output `data` dict shape (all top-level keys and one level of nesting)

### Step 6: Confirm evaluator math on a known case
- Using the data from Step 5, manually compute what ATR(14) should be at a specific bar
- Manually identify what the forward excursion would be over 4 bars
- Report: the expected outcome classification and why
- This verifies the evaluator logic is sound before it runs at scale

**Do not write implementation code until this diagnostic report is reviewed.**

---

## Acceptance Criteria

| # | Gate | Condition |
|---|------|-----------|
| **Data** | | |
| AC-1 | Data loads | `data_loader.py` fetches and caches 1H XAUUSD, returns raw DataFrame with expected columns |
| AC-2 | Data quality | Loader enforces ≥ 95% bar coverage or halts; ticker recorded in session metadata |
| **Evaluator — happy path** | | |
| AC-3 | Evaluator scores | `evaluator.py` runs Structure lens over training data, returns all metrics AND diagnostics fields with correct types |
| AC-4 | Non-overlapping windows | Evaluator steps by `step_bars`, no window overlap |
| AC-5 | ATR-scaled scoring | Confirmation/invalidation uses ATR(14) × multiplier, not fixed % |
| AC-6 | Reference price | Excursion measured from `close[T]`; forward window is `T+1` through `T+horizon_bars` |
| AC-7 | Sequential scan | Outcome determined by bar-by-bar scan, not whole-window max excursion |
| AC-8 | Invalidation-first | Adverse threshold checked before favorable within each bar; adverse hit first → INVALIDATED |
| AC-9 | Same-bar collision | If both thresholds reachable in one bar, classified as INVALIDATED |
| AC-10 | Ranging excluded | Ranging calls logged in diagnostics but not included in accuracy denominator |
| **Evaluator — failure paths** | | |
| AC-11 | Lens errors tracked | Failed LensOutput increments `lens_errors`, is not scored or counted as ranging |
| AC-12 | Error rate halt | If `lens_errors > 5%` of total steps, evaluator halts with error — no metrics produced |
| AC-13 | Config validation | Missing/malformed eval_config.json causes immediate hard error, no partial run |
| **Runner** | | |
| AC-14 | Runner accepts/rejects | `run.py` compares candidate to baseline, applies all 3 acceptance conditions |
| AC-15 | Tie rejected | accuracy_delta == 0 results in rejection |
| AC-16 | Low-resolve guard | Candidate with resolve_rate < 0.70 rejected regardless of accuracy |
| AC-17 | Low-sample guard | Candidate with resolved_calls < 80% of baseline rejected |
| AC-18 | Manifest updates | Accepted iteration overwrites `current` in manifest; rejected does not |
| AC-19 | Bounds enforced | Runner rejects proposed values outside [min, max] or off step grid |
| AC-20 | Baseline is current | Baseline for each iteration = current manifest state, not session seed |
| **Runner — failure paths** | | |
| AC-21 | Manifest validation | Missing/malformed manifest causes hard error — no evaluator run, no log write |
| AC-22 | Data validation | Missing parquet or empty train split causes hard error |
| AC-23 | Invalid proposal | Bad param name, out-of-bounds value, or off-grid value → hard error with message |
| AC-24 | Atomicity | Runner either completes fully (log + optional manifest update) or does nothing |
| **Logging and sessions** | | |
| AC-25 | Log appends | Every completed iteration appends one JSON line with ALL required fields |
| AC-26 | Log field completeness | Every log line has every field from the canonical schema; no optional keys |
| AC-27 | Session artifacts | First run for an instance writes session_meta.json and seed_manifest.json |
| AC-28 | Session resume | Subsequent runs for same instance detect and resume active session |
| AC-29 | Validation read-only | `--split validation` runs evaluator but never updates manifest, never applies acceptance policy |
| **Shim** | | |
| AC-30 | Pivot shim works | Structure lens receives numeric pivot_window via Outcome A or B — OR Phase A degrades to enum-only values if Outcome C (see diagnostic Step 1) |
| AC-31 | No monkeypatching | Shim uses subclassing, wrapping, or config injection only — no mock.patch or setattr |
| **Invariants** | | |
| AC-32 | Deterministic | Same params + same data = same evaluator output, every time |
| AC-33 | No production edits | Zero changes to any file under `ai_analyst/` |
| AC-34 | Tests pass | Harness has its own test suite in `autotune/tests/` covering: evaluator happy path, evaluator same-bar collision, evaluator lens-error handling, runner acceptance/rejection, runner tie handling, runner bounds enforcement, runner atomicity on bad input, validation read-only guard |

---

## Hard Constraints

- **No production code edits.** Nothing under `ai_analyst/` is touched. The harness imports and wraps — it does not modify.
- **No monkeypatching.** No `unittest.mock.patch`, no `setattr` on production classes, no runtime modification of production objects.
- **No database.** All state lives in JSON files and JSONL logs.
- **No scheduler.** The loop is driven manually (or by an agent) — no cron, no APScheduler, no background tasks.
- **No LLM calls in the harness.** The evaluator, runner, and data loader are pure Python. LLM calls only happen when a future agent reads `program.md` and interacts with the harness via CLI.
- **LensOutput contract preserved.** The harness must not produce, expect, or consume partial LensOutput data.
- **Append-only logging.** The experiment log is never overwritten, truncated, or edited by code.
- **Atomic runner.** A runner invocation either produces a complete iteration (log entry + optional manifest update) or produces nothing. No partial state changes on error.

---

## Implementation Sequence

1. **Data loader first.** Get data flowing and cached. Confirm ticker, date range, and bar coverage.
2. **Evaluator second.** Score the default Structure config against training data. This is the first real output — the baseline accuracy. Confirm excursion math, sequential scan, and same-bar handling with tests before scaling up.
3. **Runner third.** Wire up manifest I/O, acceptance policy, session management, and log writing. Run one manual iteration to prove the loop.
4. **Pivot shim fourth.** Only needed once you want to test non-enum pivot values. Approach determined by diagnostic Step 1 outcome. Can be a thin wrapper added to the evaluator's lens-call path.
5. **program.md last.** Write it after the harness works, because the skill instructions depend on the actual CLI interface, file paths, and any Outcome C limitations.
6. **Tests throughout.** Write tests as you build each component, not as a batch at the end. Specifically: evaluator tests must cover same-bar collision and lens-error halt before the evaluator is considered done.

---

## Documentation Closure

After the implementation PR is complete, update the following:

1. **`AUTOTUNE_V1_DESIGN.md`** — update status from "design phase complete" to "implementation complete," record baseline accuracy, note any deviations from spec (especially if Outcome C applied).
2. **`experiment_log_schema.json`** — verify it matches the actual implemented schema. If any fields were added or renamed during implementation, update the schema doc.
3. **Repo map** — if `autotune/` is a new top-level directory and a repo map exists, add it.
4. **Technical debt** — if the pivot shim required Outcome C (enum-only degradation), file a debt item: "AutoTune pivot_window limited to enum-compatible values; continuous search requires production-side refactor."
5. **This prompt** — annotate the header with implementation date and any findings that changed the design.

---

## What Success Looks Like

After this build, you should be able to:

1. Run `python data_loader.py` and get cached 1H XAUUSD parquet with verified bar coverage
2. Run `python evaluator.py --instance structure_short` and see baseline accuracy with all metric and diagnostic fields populated
3. Run `python run.py --instance structure_short --param lookback_bars --value 55` and see:
   - Evaluator runs twice (baseline + candidate)
   - Acceptance policy applied with all three conditions checked
   - Manifest updated (if accepted) or unchanged (if rejected)
   - One complete JSON line appended to experiment_log.jsonl
   - Session artifacts written on first run, resumed on subsequent runs
4. Open `logs/experiment_log.jsonl` and see a complete, self-contained record of the iteration with every field present
5. Run the same command again with the same value and get the exact same evaluator output (determinism)
6. Read `program.md` and understand exactly how an agent should drive the loop
7. Run `python run.py --instance structure_short --param lookback_bars --value 999` and see a clear bounds-violation error with no side effects
8. Introduce a broken lens config that causes failures and see the evaluator halt at the 5% error threshold

The harness is a tool. It does not think. It runs, measures, records, and enforces rules. Thinking comes later, from the agent.
