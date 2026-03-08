# Specs Index

Tracks active specs, current phase, and source of truth for each subsystem.

| Spec | Path | Phase | Status |
|------|------|-------|--------|
| Market Data Officer Phase 1A | `docs/MDO_Phase1A_Spec.md` | Phase 1A — EURUSD baseline spine | ✅ Complete |
| Market Data Officer Phase 1B+ | TBD | Phase 1B+ — XAUUSD spine | ⏳ Next |

---

## Current Phase

**Phase 1B+ — Market Data Officer (XAUUSD)**  
Spec: TBD — to be drafted before implementation  
Goal: extend proven EURUSD spine to XAUUSD (`15m`, `1h`, `4h`, `1d`)

## Completed Phases

| Phase | Description | Session Doc |
|-------|-------------|-------------|
| Phase A | Single analyst smoke path | Session handoff 8 Mar 2026 |
| Phase B | Central provider/model config | Session handoff 8 Mar 2026 |
| Phase C | Quorum/degraded failure handling | Session handoff 8 Mar 2026 |
| Phase D | V1.1 snapshot patch H-1 → H-4 | Session handoff 8 Mar 2026 |
| Phase 1A | EURUSD baseline spine — 359/359 tests | `docs/MDO_Phase1A_Spec.md` |

## Pending

| Phase | Description |
|-------|-------------|
| Phase 1B+ | XAUUSD data spine (`15m`, `1h`, `4h`, `1d`) — draft spec before coding |
| Phase E+ | Additional instruments, provider abstraction |
| Operationalise | Scheduler / APScheduler integration |
| Tidy | Async marker cleanup (4 files) |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) |
