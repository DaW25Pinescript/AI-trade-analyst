# Specs Index

Tracks active specs, current phase, and source of truth for each subsystem.

| Spec | Path | Phase | Status |
|------|------|-------|--------|
| Market Data Officer Phase 1A | `docs/MDO_Phase1A_Spec.md` | Phase 1A — EURUSD baseline spine | ✅ Complete |
| Market Data Officer Phase 1B | `docs/MDO_Phase1B_Spec.md` | Phase 1B — XAUUSD spine | ✅ Complete |
| Market Data Officer Phase E+ | `docs/MDO_PhaseE_Spec.md` | Phase E+ — instrument registry + GBPUSD/XAGUSD/XPTUSD | ✅ Complete |
| Provider Switchover | `docs/MDO_ProviderSwitchover_Spec.md` | yFinance fallback — vendor provenance in MarketPacketV2 | ✅ Complete |
| Instrument Promotion | `docs/MDO_PhaseF_InstrumentPromotion_Spec.md` | Phase F — GBPUSD/XAGUSD/XPTUSD trust-level promotion | ✅ Complete |

---

## Current Phase

**Per-Instrument Provider Routing** — explicit per-instrument provider selection  
Spec: TBD — draft before implementation  
Goal: build on the now-working fallback to support explicit per-instrument provider config (e.g. EURUSD always yFinance)

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

## Pending

| Phase | Description |
|-------|-------------|
| Per-Instrument Routing | Explicit per-instrument provider config — draft spec before coding |
| Operationalise | Scheduler / APScheduler integration |
| Tidy | Async marker cleanup (4 files) |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) |
