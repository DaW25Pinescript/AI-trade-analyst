# CLAUDE.md — Market Data Officer Feed: Phase 1B

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Your job in this task is to extend the Phase 1A ingestion spine to **XAUUSD**. The architecture is already proven. Your task is instrument verification and safe extension — not redesign.

Read this file first. Then read the supporting spec files in order before writing any code.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**What already exists (do not touch):**
- `market_data_officer/feed/` — Phase 1A feed pipeline, fully working for EURUSD
- `market_data_officer/officer/` — Phase 2 Market Data Officer, emitting validated EURUSD packets
- `market_data/canonical/EURUSD_1m.parquet` — trusted canonical archive
- All Phase 1A acceptance tests — must remain passing after Phase 1B

**What you are extending:**
- `feed/config.py` — add verified XAUUSD `InstrumentMeta` (only after external verification)
- `feed/decode.py` — confirm or adjust parsing for XAUUSD tick struct if needed
- `tests/` — add XAUUSD-specific acceptance tests mirroring Phase 1A

---

## The verification gate — most important rule in this task

**Do not populate `InstrumentMeta` for XAUUSD until the external verification gate is passed.**

This is not optional. This is the entire point of Phase 1B being a separate phase.

The verification gate requires:
1. Decode a raw XAUUSD bi5 sample from Dukascopy
2. Compare at least **5 decoded bars** against **both TradingView and CMC Markets**
3. Verify for each bar: timestamp, open, high, low, close
4. Explicitly document price scale and volume semantics
5. Only then commit values to `InstrumentMeta`

Until that gate is passed, XAUUSD must remain behind the stub comment in `config.py` exactly as written in Phase 1A.

---

## File reading order

Before writing any code, read these files in order:

1. `CLAUDE.md` ← you are here
2. `OBJECTIVE.md` — what Phase 1B must deliver and why XAUUSD is high-risk
3. `CONSTRAINTS.md` — hard rules, verification protocol, known risk areas
4. `ACCEPTANCE_TESTS.md` — exit criteria including the mandatory verification checkpoint

---

## Repo placement

No new modules required. Extensions only:

```
market_data_officer/
  feed/
    config.py          ← add XAUUSD InstrumentMeta (after verification only)
    decode.py          ← confirm or adjust tick struct handling for XAUUSD
  tests/
    test_validate.py   ← existing, must still pass
    test_resample.py   ← existing, must still pass
    test_decode.py     ← extend with XAUUSD-specific decode tests
    test_xauusd.py     ← new: XAUUSD end-to-end and verification tests
```

---

## When you are done

Run every criterion in `ACCEPTANCE_TESTS.md` — both the XAUUSD-specific tests and the full Phase 1A regression suite. Report pass/fail per group before declaring Phase 1B complete.

Do not touch the Officer layer. Do not touch Phase 1C, 1D, or Phase 2 scope.
