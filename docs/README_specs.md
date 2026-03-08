# Specs Index

Tracks active specs, current phase, and source of truth for each subsystem.

| Spec | Path | Phase | Status |
|------|------|-------|--------|
| Market Data Officer Phase 1A | `docs/MDO_Phase1A_Spec.md` | Phase 1A — EURUSD baseline spine | ✅ Complete |
| Market Data Officer Phase 1B | `docs/MDO_Phase1B_Spec.md` | Phase 1B — XAUUSD spine | ✅ Complete |

---

## Current Phase

**Phase E+ — Additional Instruments / Provider Abstraction**  
Spec: TBD — draft before implementation  
Goal: extend proven spine to further instruments, formalise provider abstraction (yFinance as Dukascopy alternative, alias config)

## Completed Phases

| Phase | Description | Session Doc |
|-------|-------------|-------------|
| Phase A | Single analyst smoke path | Session handoff 8 Mar 2026 |
| Phase B | Central provider/model config | Session handoff 8 Mar 2026 |
| Phase C | Quorum/degraded failure handling | Session handoff 8 Mar 2026 |
| Phase D | V1.1 snapshot patch H-1 → H-4 | Session handoff 8 Mar 2026 |
| Phase 1A | EURUSD baseline spine — 359/359 tests | `docs/MDO_Phase1A_Spec.md` |
| Phase 1B | XAUUSD spine — 364/364 tests | `docs/MDO_Phase1B_Spec.md` |

## Pending

| Phase | Description |
|-------|-------------|
| Phase E+ | Additional instruments, provider abstraction — draft spec before coding |
| Operationalise | Scheduler / APScheduler integration |
| Tidy | Async marker cleanup (4 files) |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) |