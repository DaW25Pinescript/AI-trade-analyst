# MRO Runbook — Degraded Macro Mode

**Version:** 1.0
**Phase:** MRO-P4
**Updated:** 2026-03-02

This runbook documents the operator and developer actions to take when the
Macro Risk Officer (MRO) is in a degraded state. "Degraded" means one or more
data sources are unavailable or context freshness has exceeded the stale threshold.

---

## Degradation tiers

| Tier | Condition | Impact | Pipeline behavior |
|------|-----------|--------|-------------------|
| **Partial** | One source unavailable (e.g. Finnhub down, FRED key missing) | Reduced context quality; fewer events | Scheduler uses remaining sources; context is still produced |
| **Full** | All sources fail; no events retrieved | No MacroContext for this refresh cycle | Scheduler returns stale cache if available; otherwise returns `None` |
| **Stale** | Last successful refresh older than `stale_threshold_seconds` (default 60 min) | Context may not reflect recent market events | Arbiter receives stale context; `kpi` command flags as STALE |

The pipeline is **fail-soft**: `MacroContext = None` is a valid state. The Arbiter
prompt builder falls back to the macro-absent branch and continues without macro context.
No trade is ever blocked solely due to MRO unavailability.

---

## Key Timing Parameters

| Parameter | Default | Config location | Description |
|-----------|---------|-----------------|-------------|
| `scheduler.ttl_seconds` | 1800 (30 min) | `macro_risk_officer/config/thresholds.yaml` | How long a cached MacroContext is reused before re-fetching |
| `scheduler.stale_threshold_seconds` | 3600 (60 min) | `macro_risk_officer/config/thresholds.yaml` | Age after which context is flagged as STALE in `kpi` report |
| `FEEDER_STALE_SECONDS` | 3600 (60 min) | Environment variable | Age after which the `/feeder/health` endpoint reports `stale: true` |

**Expected polling cadence:** The scheduler refreshes context every 30 minutes (TTL).
The feeder bridge (`POST /feeder/ingest`) should be called by an external cron job or
monitoring script at a similar or faster interval (e.g. every 15–30 minutes) to keep
`/feeder/health` fresh. If no feeder payload is ingested within `FEEDER_STALE_SECONDS`,
the health endpoint returns `stale: true` and the operator dashboard shows a yellow warning.

---

## Diagnosis

### Step 1 — Check KPI report
```bash
python -m macro_risk_officer kpi
```
Review:
- `Macro availability %` — below 80% triggers the gate warning
- `Context freshness` — STALE flag means last fetch was over 60 minutes ago
- `FAILURE CAUSES` section — lists error class names from recent failures

### Step 2 — Check live context
```bash
python -m macro_risk_officer status --instrument XAUUSD
```
- **Returns context:** at least one source is working normally
- **Returns ERROR:** all sources are currently failing; see Step 3

### Step 3 — Isolate the failing source

**Finnhub:**
```bash
# Verify API key is set
echo $FINNHUB_API_KEY   # should be non-empty

# Test raw API (replace TOKEN with your key)
curl "https://finnhub.io/api/v1/calendar/economic?from=2026-01-01&to=2026-01-07&token=$FINNHUB_API_KEY"
```
Expected: JSON with `"economicCalendar"` key. Any non-200 response → Finnhub API outage or invalid key.

**FRED:**
```bash
echo $FRED_API_KEY   # should be non-empty

curl "https://api.stlouisfed.org/fred/series/observations?series_id=DFF&api_key=$FRED_API_KEY&file_type=json&limit=1"
```
Expected: JSON with `"observations"` key.

**GDELT (no key required):**
```bash
curl "https://api.gdeltproject.org/api/v2/doc/doc?query=war&mode=ArtList&maxrecords=5&format=json&timespan=1d"
```
Expected: JSON with `"articles"` key.

---

## Remediation actions

### API outage (external source down)

MRO is designed to tolerate individual source outages automatically. The scheduler
continues with the remaining sources. No operator action is required unless all
sources are simultaneously down.

If all sources are down for an extended period (> 2 hours):
1. Run `python -m macro_risk_officer kpi` to confirm the availability % drop
2. The pipeline will use the last valid cache until it expires (TTL = 30 min)
3. After TTL expires, `MacroContext` becomes `None` — Arbiter continues without macro section
4. Monitor upstream status pages: [Finnhub status](https://status.finnhub.io/) / [FRED](https://fred.stlouisfed.org/)
5. No code changes needed — sources recover automatically and the next scheduler
   refresh (every 30 min) will populate a fresh context

### Missing API keys

Symptoms: Finnhub or FRED source missing from `source_mask` in the KPI report.

```bash
# Check which keys are set
python -c "import os; print('Finnhub:', bool(os.getenv('FINNHUB_API_KEY'))); print('FRED:', bool(os.getenv('FRED_API_KEY')))"
```

Resolution:
1. Add the missing key to your `.env` file (see `docs/api_key_setup.md`)
2. Restart any long-lived processes (FastAPI server, scheduled jobs)
3. Run `python -m macro_risk_officer status` to confirm context is now produced

Free-tier keys are sufficient for V1 (< 30 req/min for Finnhub; FRED has no rate limit under normal usage).

### Upstream schema shift (API response format changed)

Symptoms: `KeyError` or `ValueError` in the `FAILURE CAUSES` section of the KPI report.

1. Run the smoke tests to reproduce the failure:
   ```bash
   MRO_SMOKE_TESTS=1 pytest macro_risk_officer/tests/test_smoke.py -v
   ```
2. Identify which client is failing (Finnhub, FRED, or GDELT)
3. Inspect the raw API response with `curl` (see Step 3 above)
4. Update the affected client in `macro_risk_officer/ingestion/clients/`
5. Update the corresponding mock data in unit tests if field names changed
6. Re-run `MRO_SMOKE_TESTS=1 pytest macro_risk_officer/tests/test_smoke.py` to confirm fix

### Context freshness breach (STALE alert)

Symptoms: `kpi` command shows `STALE (N min ago; threshold 60 min)`.

This means the last successful refresh was more than 60 minutes ago, indicating
a persistent failure across multiple TTL cycles.

1. Diagnose root cause using Steps 1–3 above
2. Once the source is restored, force an immediate refresh:
   ```python
   from macro_risk_officer.ingestion.scheduler import MacroScheduler
   scheduler = MacroScheduler()
   scheduler.invalidate()   # clears cache; next get_context() call fetches fresh
   ctx = scheduler.get_context(instrument="XAUUSD")
   print(ctx)
   ```
3. Alternatively restart the FastAPI process — each new process creates a fresh scheduler

### Cache hit ratio below 60%

The cache hit ratio is in-process only (resets on each CLI invocation). A low ratio
in a long-running process (e.g. FastAPI server with many `/analyse` requests) means
the TTL is too short relative to request volume.

Resolution: increase `scheduler.ttl_seconds` in `macro_risk_officer/config/thresholds.yaml`:
```yaml
scheduler:
  ttl_seconds: 3600   # increase from 1800 to 3600 (1 hour) if needed
```

Note: longer TTL means older macro context. Do not exceed `stale_threshold_seconds`.

---

## Escalation paths

| Condition | Action |
|-----------|--------|
| Finnhub / FRED key expired | Regenerate key at provider portal; update `.env` |
| GDELT API unresponsive for > 24h | Open issue in repo; disable GDELT in scheduler temporarily by setting `_ESCALATION_THRESHOLD` to a value that can never be crossed |
| All sources down for > 4h during high-impact event week | Manually inject a `MacroContext` stub via `MacroScheduler._cache` for the session; document in run notes |
| Upstream schema shift that breaks a client | File bug report with Finnhub/FRED; apply hotfix to client parser; deploy updated `macro_risk_officer/` |

---

## Preventing false alerts

**CI smoke tests are opt-in.** The default test suite (`pytest macro_risk_officer/tests/`)
never hits external APIs, so CI will never fail due to source outages. To run live
smoke tests manually:

```bash
FINNHUB_API_KEY=... FRED_API_KEY=... MRO_SMOKE_TESTS=1 pytest macro_risk_officer/tests/test_smoke.py -v
```

**KPI gate is informational.** The availability gate (≥ 80%) in `kpi` output is a
monitoring signal, not a hard blocker. The Arbiter continues to function at
`macro_availability = 0%` — it simply operates without macro context.
