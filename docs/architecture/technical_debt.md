# Technical Debt Ledger

This document is the enduring repository ledger for technical debt items.

> Execution priority, active phase sequencing, and near-term next actions remain owned by the canonical progress hub: [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md).

> **Note:** The superset debt register is maintained in `AI_TradeAnalyst_Progress.md` §8. This file tracks the subset relevant to architecture decisions.

## Rules of use

- Keep entries factual and traceable to code, tests, or existing docs.
- Use this ledger to track debt lifecycle (`Open`, `Planned`, `In Progress`, `Resolved`), not to run the phase roadmap.
- When a debt item materially changes phase priority, reflect that decision in `AI_TradeAnalyst_Progress.md`.
- Prefer stable IDs so PRs/specs can cross-reference items without ambiguity.

## Debt register

| ID | Area | Description | Impact | Priority | Status | Linked phase / owner / note |
|---|---|---|---|---|---|---|
| TD-3 | Packaging / Imports | `sys.path.insert` dependency wiring removed; pyproject.toml fixed; all packages installable via `pip install -e .`. | ~~Deployment/reproducibility fragility~~ | High | **✅ Resolved** | Completed 12 March 2026. Spec: `docs/specs/td3_packaging_import_stability.md`. |
| TD-4 | Analyst orchestration | Duplication across single-analyst and multi-analyst service orchestration paths. | Drift risk and duplicated lifecycle changes. | Medium | Planned | Candidate named cleanup after seam confidence work. |
| TD-5 | Contracts / enums | ~~Magic-string enum duplication across analyst/persona/arbiter modules.~~ | ~~Validation drift and inconsistent contract enforcement risk.~~ | Medium | **✅ Resolved** | Completed 13 March 2026. Canonical source `analyst/enums.py`; 5 duplicated definitions removed from 4 modules. |
| TD-9 | Market data packet assembly | ~~Unused variables in `build_market_packet()` reduce intent clarity.~~ | ~~Maintainability noise and misleading future edits.~~ | Low | **✅ Resolved** | Completed 13 March 2026. All four dead locals removed in PR-3. |
| TD-11 | Packaging test coverage | 16 import stability tests added in `tests/test_import_stability.py` including negative packaging test. | ~~Packaging regressions undetected~~ | Medium | **✅ Resolved** | Completed 12 March 2026 as part of TD-3 closure. |
| TD-12 | Architecture contracts docs | Cross-module ownership/fallback/scaling boundaries under-documented. | Harder onboarding and seam reasoning for contributors/agents. | Medium | Open | Address alongside runtime-lane convergence or next architecture review. |

| TD-13 | Agent Ops run selector | Run selector is paste-field only in Agent Ops Run mode. Operators must know `run_id` to inspect a run — no browse/search. | Operator friction; reduces discoverability of run artifacts. | Medium | **✅ Resolved — 15 March 2026** | PR-RUN-1 shipped. `GET /runs/` endpoint + RunBrowserPanel. Paste-field retained as fallback. |
| TD-14 | Reflect artifact richness gap | `run_record.json` analyst entries currently omit per-analyst stance/confidence/override fields; reflect metrics rely on optional audit-log enrichment for these provisional fields. | Some persona metrics can be null when audit logs are absent. | Medium | Open | Consider adding non-breaking enriched analyst metadata in future observability phase (without changing existing contract semantics). |

## See also

- Canonical status/progress hub: [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md)
- Architecture index: [README.md](README.md)
