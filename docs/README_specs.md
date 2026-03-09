# Specs Index

Tracks active specs, current phase, and source of truth for each subsystem.

| Spec | Path | Phase | Status |
|------|------|-------|--------|
| Market Data Officer Phase 1A | `docs/MDO_Phase1A_Spec.md` | Phase 1A — EURUSD baseline spine | ✅ Complete |
| Market Data Officer Phase 1B | `docs/MDO_Phase1B_Spec.md` | Phase 1B — XAUUSD spine | ✅ Complete |
| Market Data Officer Phase E+ | `docs/MDO_PhaseE_Spec.md` | Phase E+ — instrument registry + GBPUSD/XAGUSD/XPTUSD | ✅ Complete |
| Provider Switchover | `docs/MDO_ProviderSwitchover_Spec.md` | yFinance fallback — vendor provenance in MarketPacketV2 | ✅ Complete |
| Instrument Promotion | `docs/MDO_PhaseF_InstrumentPromotion_Spec.md` | Phase F — GBPUSD/XAGUSD/XPTUSD trust-level promotion | ✅ Complete |
| Per-Instrument Provider Routing | `docs/MDO_ProviderRouting_Spec.md` | Per-instrument provider policy | ✅ Complete |
| Operationalise Phase 1 | `docs/MDO_Operationalise_Spec.md` | APScheduler feed refresh | ✅ Complete |
| Operationalise Phase 2 | `docs/MDO_Operationalise_Phase2_Spec.md` | Market-hours awareness, alerting, remote deployment | ⏳ Active |

---

## Current Phase

**Operationalise Phase 2** — market-hours awareness, alerting, remote deployment  
Spec: `docs/MDO_Operationalise_Phase2_Spec.md`  
Goal: market-hours gating, alerting on failure, and remote deployment readiness on top of the Phase 1 scheduler base

## Completed Phases

| Phase | Description | Session Doc |
|-------|-------------|-------------|
| Phase A | Single analyst smoke path | Session handoff 8 Mar 2026 |
| Phase B | Central provider/model config | Session handoff 8 Mar 2026 |
| Phase C | Quorum/degraded failure handling | Session handoff 8 Mar 2026 |
| Phase D | V1.1 snapshot patch H-1 → H-4 | Session handoff 8 Mar 2026 |
| Phase 1A | EURUSD baseline spine — 359/359 tests | `docs/MDO_Phase1A_Spec.md` |
| Phase 1B | XAUUSD spine — 364/364 tests | `docs/MDO_Phase1B_Spec.md` |
| Phase E+ | Instrument registry + GBPUSD/XAGUSD/XPTUSD — 404/404 tests | `docs/MDO_PhaseE_Spec.md` |
| Instrument Promotion | GBPUSD/XAGUSD/XPTUSD promoted to trusted — 419/419 tests | `docs/MDO_PhaseF_InstrumentPromotion_Spec.md` |
| Per-Instrument Provider Routing | Explicit per-instrument provider policy — 468/468 tests | `docs/MDO_ProviderRouting_Spec.md` |
| Operationalise Phase 1 | APScheduler feed refresh — 494/494 tests | `docs/MDO_Operationalise_Spec.md` |

## Pending / Next Candidates

| Phase | Description |
|-------|-------------|
| Tidy | Async marker cleanup (4 files) |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) |
| Security/API Hardening | API edge protection, timeout policy, error contracts |
| CI Seam Hardening | CI coverage for missing Python integration seams and `/analyse/stream` |
