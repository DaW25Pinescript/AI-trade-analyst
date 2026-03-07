# CLAUDE.md — Phase 3D: Officer Integration

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Phase 3D is the first cross-layer integration task. You are connecting the Structure Engine (Phases 3A–3C) into the Market Data Officer (Phase 2), producing Market Packet v2.

Read `ARCHITECTURE.md` first — it is the full system map. Then read this file and the supporting spec files before writing any code.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**Already complete — do not rewrite:**
- `market_data_officer/feed/` — feed pipeline, all phases
- `market_data_officer/officer/` — Market Data Officer, Phase 2
- `market_data_officer/structure/` — Structure Engine, Phases 3A–3C
- All existing JSON output packets and hot packages

**What you are building in Phase 3D:**
- `structure/reader.py` — NEW: structure read API (Officer-facing loader)
- `officer/contracts.py` — extend: add `StructureBlock`, `MarketPacketV2`
- `officer/service.py` — extend: integrate structure state into packet assembly
- `officer/loader.py` — minor: add structure manifest loading if needed
- `run_officer.py` — extend: emit v2 packets
- `tests/` — add 3D test groups

---

## Locked decisions across all prior phases

Do not reopen anything from 3A, 3B, 3C, Phase 2, or the feed pipeline. Specifically:

| Layer | Locked |
|---|---|
| Feed | All fetch, decode, validate, archive logic |
| Officer v1 | `MarketPacketV1` fields — do not rename or remove |
| Structure 3A | Swing detection, BOS/MSS, confirmed-only rule |
| Structure 3B | Reclaim logic, lifecycle, internal/external tagging |
| Structure 3C | FVG body-only, fill progression, invalidation rule |
| Output format | JSON only, atomic writes |
| Active TFs | 15m, 1h, 4h |

---

## 3D decisions locked in this spec

| Decision | Value |
|---|---|
| Packet schema | Bump to `market_packet_v2` |
| Structure placement | New top-level `structure` block |
| Structure contents | regime, recent_events, liquidity summary, active_fvg_zones |
| Officer reads structure via | `structure/reader.py` read API — not raw JSON file paths |
| Runtime unavailability | `structure.available = false`, all sub-fields null — no crash |
| v1 fields | All preserved unchanged in v2 |

---

## File reading order

1. `ARCHITECTURE.md` ← read first — full system map
2. `CLAUDE.md` ← you are here
3. `OBJECTIVE.md` — what 3D integrates and why
4. `CONSTRAINTS.md` — hard rules, boundary enforcement
5. `CONTRACTS.md` — v2 packet schema, StructureBlock, reader API
6. `ACCEPTANCE_TESTS.md` — test groups

---

## Repo placement

```
market_data_officer/
  structure/
    reader.py          ← NEW: Officer-facing structure read API
    ...                ← existing 3A/3B/3C modules, untouched
  officer/
    contracts.py       ← extend: StructureBlock, MarketPacketV2
    service.py         ← extend: integrate structure into packet assembly
    loader.py          ← minor extension if needed
    ...                ← existing Phase 2 modules
  tests/
    test_officer_v2.py          ← NEW: v2 packet tests
    test_structure_reader.py    ← NEW: reader API tests
    test_3d_integration.py      ← NEW: cross-layer integration tests
    ...                         ← all existing tests, must still pass
  run_officer.py       ← extend: emit v2 packet
```

---

## When you are done

Run Group 0 regression first — all prior tests must pass before any 3D tests run. Then Groups A through G. Report pass/fail per group before declaring Phase 3D complete.
