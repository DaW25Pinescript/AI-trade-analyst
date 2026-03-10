# MDO Scheduler — Runtime Guide

**Version:** 1.0
**Phase:** Operationalise Phase 2 — PR 3
**Updated:** 10 March 2026

This guide documents the implemented runtime behavior of the Market Data Officer scheduler. Every statement describes what the system actually does — not aspirational future behavior.

---

## 1. Starting the Scheduler

### Command

```bash
cd market_data_officer
python run_scheduler.py
```

### What happens on startup

1. **Config load.** `load_runtime_config()` returns a frozen `RuntimeConfig` with defaults matching the hardcoded schedule, alert thresholds, and artifact paths.
2. **Config validation.** `validate_runtime_config()` checks:
   - Schedule config is non-empty
   - Every instrument has valid `interval_hours`, `window_hours`, and `family`
   - Every instrument exists in `INSTRUMENT_FAMILY` (market_hours.py)
   - Every family is covered by `FAMILY_SESSION_POLICY` (market_hours.py)
   - Alert thresholds are positive integers with `warn < critical` for stale-live
3. **Fail-fast.** If validation fails, a `ConfigValidationError` is logged and the process exits with code 1. The scheduler never starts with invalid config.
4. **Startup posture banner.** A structured log block states:
   - Whether market-hours policy is active
   - Whether alert logging is active
   - Artifact root path
   - Number of instruments and per-instrument cadence/window/family
   - Alert threshold values
5. **Scheduler start.** APScheduler `BackgroundScheduler` starts with one interval job per instrument.
6. **Signal handlers installed.** SIGINT and SIGTERM trigger graceful shutdown.

### Example startup log

```
[2026-03-10 14:00:00] ============================================================
[2026-03-10 14:00:00] MDO Scheduler — startup posture
[2026-03-10 14:00:00] ------------------------------------------------------------
[2026-03-10 14:00:00]   market_hours_enabled : True
[2026-03-10 14:00:00]   alert_logging_enabled: True
[2026-03-10 14:00:00]   artifact_root        : market_data
[2026-03-10 14:00:00]   instruments          : 5
[2026-03-10 14:00:00]     EURUSD  every 1h  window=24h  family=FX
[2026-03-10 14:00:00]     GBPUSD  every 1h  window=24h  family=FX
[2026-03-10 14:00:00]     XAUUSD  every 4h  window=48h  family=Metals
[2026-03-10 14:00:00]     XAGUSD  every 4h  window=48h  family=Metals
[2026-03-10 14:00:00]     XPTUSD  every 4h  window=48h  family=Metals
[2026-03-10 14:00:00]   alert thresholds     : warn_stale=2  crit_stale=4  crit_fail=2
[2026-03-10 14:00:00] ============================================================
[2026-03-10 14:00:00] Scheduler running — Ctrl-C or SIGTERM to stop
```

---

## 2. Stopping the Scheduler

### How to stop

- **Interactive:** Press Ctrl-C (sends SIGINT)
- **Remote/background:** Send SIGTERM to the process (`kill <pid>`)

### What happens on shutdown

1. Signal handler logs the received signal name (e.g. `signal=SIGINT`)
2. APScheduler `shutdown(wait=False)` is called — in-progress jobs may be interrupted
3. Process logs `Scheduler stopped — clean exit` and exits with code 0

### Safe restart

Restarting the scheduler is always safe:
- **Artifacts are preserved.** Last-known-good market data packages are never deleted by the scheduler.
- **Alert state resets.** Per-instrument alert counters (`consecutive_stale_live`, `consecutive_failures`) are process-local and reset to zero on restart. This means any in-progress alert escalation starts fresh.
- **Cadence resumes.** Each instrument's interval timer starts from the moment the scheduler starts.

---

## 3. Steady-State Log Patterns

### Successful refresh

```
EURUSD  SUCCESS  duration=2.3s  market_state=OPEN  freshness=FRESH  reason=open_and_fresh  evaluation_ts=2026-03-10T14:00:00+00:00
```

### Market-closed skip (expected — not a fault)

```
EURUSD  SKIPPED  market_state=CLOSED_EXPECTED  evaluation_ts=2026-03-10T23:30:00+00:00
```

This is normal behavior during weekends and outside session hours. FX and Metals sessions run Sunday 22:00 UTC through Friday 22:00 UTC.

### Refresh failure

```
EURUSD  FAILURE  error='ConnectionTimeout'  duration=30.1s  market_state=OPEN  freshness=MISSING_BAD  reason=open_and_missing  evaluation_ts=2026-03-10T14:00:00+00:00
```

On failure, last-known-good artifacts are preserved. The scheduler continues with the next scheduled cycle.

---

## 4. Alert Escalation and Recovery

Alerts are edge-triggered structured log entries — they are emitted when the alert level changes, not on every cycle.

### Alert escalation

```
EURUSD  ALERT  alert_level=warn  reason_code=stale_live_warn  market_state=OPEN  freshness=STALE_BAD  refresh_outcome=success  consecutive_stale_live=2  consecutive_failures=0  last_success_ts=...  eval_ts=...
```

| Level | Trigger condition |
|-------|-------------------|
| `warn` | 2+ consecutive stale-live evaluations, or 1+ refresh failure during live market |
| `critical` | 4+ consecutive stale-live evaluations, or 2+ consecutive refresh failures |

### Recovery

```
EURUSD  ALERT  alert_level=none  reason_code=recovery  recovered_from_level=warn  recovered_from_reason=stale_live_warn  ...
```

Recovery logs are emitted once when a previously alerted instrument returns to healthy state.

### Behavior during market closure

- Alert counters **hold** (freeze) during `CLOSED_EXPECTED` and `OFF_SESSION_EXPECTED`.
- No alerts are emitted while the market is closed.
- Counters resume from their held values when the market reopens.
- This prevents false recovery/re-escalation on session boundaries.

---

## 5. Weekends and Holidays

### What to expect

- **Friday after 22:00 UTC:** Instruments transition to `CLOSED_EXPECTED`. Refreshes are skipped.
- **Saturday:** Instruments are `OFF_SESSION_EXPECTED`. All refreshes are skipped.
- **Sunday before 22:00 UTC:** Instruments remain `CLOSED_EXPECTED`.
- **Sunday at 22:00 UTC:** FX and Metals session opens. Refreshes resume.

### Stale artifacts during closure are normal

If the scheduler was running during the week, the last successful artifacts remain in `market_data/packages/latest/`. These artifacts become increasingly old over the weekend, but this is expected — the freshness classification will report `STALE_EXPECTED` or `MISSING_EXPECTED`, not `STALE_BAD`.

No operator action is needed for weekend staleness.

---

## 6. Health Check

The scheduler exposes a programmatic health-check function:

```python
from scheduler import get_scheduler_health

health = get_scheduler_health()
```

This returns a read-only snapshot:

```python
{
    "configured_instruments": 5,
    "instruments_with_state": 3,  # instruments evaluated at least once
    "instruments": {
        "EURUSD": {
            "alert_level": "none",
            "alert_reason": "healthy",
            "consecutive_stale_live": 0,
            "consecutive_failures": 0,
            "last_success_ts": "2026-03-10T14:00:00+00:00"
        },
        ...
    }
}
```

Calling `get_scheduler_health()` does not trigger a refresh, alter alert state, or cause any side effects. It reads the current in-memory alert state.

**Note:** This is a callable function, not an HTTP endpoint. Future phases (Security/API Hardening) may expose it as an endpoint.

---

## 7. Runtime Configuration

### Current config surface

Runtime configuration is defined in `market_data_officer/runtime_config.py` as a frozen `RuntimeConfig` dataclass. Current defaults:

| Parameter | Default | Source |
|-----------|---------|--------|
| `schedule_config` | 5 instruments (EURUSD, GBPUSD, XAUUSD, XAGUSD, XPTUSD) | Matches `scheduler.SCHEDULE_CONFIG` |
| `artifact_root` | `market_data` | Matches `feed/config.DATA_ROOT` |
| `warn_stale_live_threshold` | 2 | Matches `alert_policy.WARN_STALE_LIVE_THRESHOLD` |
| `critical_stale_live_threshold` | 4 | Matches `alert_policy.CRITICAL_STALE_LIVE_THRESHOLD` |
| `critical_failure_threshold` | 2 | Matches `alert_policy.CRITICAL_FAILURE_THRESHOLD` |
| `market_hours_enabled` | True | Market-hours gating active |
| `alert_logging_enabled` | True | Alert log emission active |

### Validation rules

Startup validation enforces:
- At least one instrument is configured
- Each instrument has valid positive `interval_hours` and `window_hours`
- Each instrument exists in `INSTRUMENT_FAMILY` (market_hours.py)
- Each family has a matching `FAMILY_SESSION_POLICY` entry
- Alert thresholds are positive integers
- `warn_stale_live_threshold < critical_stale_live_threshold`

If any check fails, the process exits immediately with a clear error message.

---

## 8. Troubleshooting

### Scheduler won't start

**Symptom:** Process exits with `STARTUP FAILED — config validation error`

**Action:** Read the error message — it lists every validation failure. Common causes:
- An instrument in `schedule_config` is missing from `INSTRUMENT_FAMILY`
- A family string doesn't match any `FAMILY_SESSION_POLICY` entry
- A cadence value is zero or negative

### Repeated alerts for an instrument

**Symptom:** `ALERT` log lines with increasing `consecutive_stale_live` or `consecutive_failures`

**Action:**
1. Check whether the market is actually open (alerts only fire during live market hours)
2. Check network connectivity to the data provider (Dukascopy)
3. Check disk space at `artifact_root` — pipeline writes fail silently if disk is full
4. If the provider is temporarily down, the scheduler will recover automatically when the provider returns. Recovery is logged.

### All instruments showing SKIPPED

**Symptom:** Every refresh cycle logs `SKIPPED  market_state=CLOSED_EXPECTED`

**Action:** This is normal if it's outside FX/Metals session hours (Friday 22:00 UTC through Sunday 22:00 UTC). If this happens during expected session hours, check that the system clock is set correctly and reporting UTC.

### Stale artifacts after restart

**Symptom:** Artifacts in `market_data/packages/latest/` have old timestamps after a scheduler restart

**Action:** This is expected. The scheduler preserves last-known-good artifacts across restarts. Fresh artifacts will be written on the next successful refresh cycle.

---

## 9. Architecture Notes

### Process model

The scheduler runs as a single Python process with one background thread per instrument. There is no multi-worker or distributed coordination.

### Data flow

```
run_scheduler.py
  → load_runtime_config() → validate_runtime_config()
  → build_scheduler(schedule_config)
  → APScheduler BackgroundScheduler
    → per-instrument interval jobs
      → refresh_instrument()
        → get_market_state()      [market_hours.py — skip if closed]
        → run_pipeline()          [feed/pipeline.py — fetch + process]
        → classify_freshness()    [market_hours.py — FRESH/STALE/MISSING]
        → _evaluate_alert()       [alert_policy.py — edge-triggered logs]
```

### Key invariants

- **Last-known-good preservation:** Artifacts are never deleted by the scheduler. A failed refresh leaves the previous successful output in place.
- **Job isolation:** A failure in one instrument's refresh does not affect other instruments or crash the scheduler.
- **Alert isolation:** Alert evaluation failure is caught and logged — it never prevents the next refresh cycle.
- **No external state:** All alert state is process-local. No database, no Redis, no file-based state.
