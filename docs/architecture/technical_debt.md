# Technical Debt Ledger

This document is the enduring repository ledger for technical debt items.

> Execution priority, active phase sequencing, and near-term next actions remain owned by the canonical progress hub: [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md).

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
| TD-5 | Contracts / enums | Magic-string enum duplication across analyst/persona/arbiter modules. | Validation drift and inconsistent contract enforcement risk. | Medium | Open | Candidate micro-PR for shared contract constants. |
| TD-9 | Market data packet assembly | Unused variables in `build_market_packet()` reduce intent clarity. | Maintainability noise and misleading future edits. | Low | Open | Candidate micro-PR (remove or document intent). |
| TD-11 | Packaging test coverage | 16 import stability tests added in `tests/test_import_stability.py` including negative packaging test. | ~~Packaging regressions undetected~~ | Medium | **✅ Resolved** | Completed 12 March 2026 as part of TD-3 closure. |
| TD-12 | Architecture contracts docs | Cross-module ownership/fallback/scaling boundaries under-documented. | Harder onboarding and seam reasoning for contributors/agents. | Medium | Open | Address alongside runtime-lane convergence or next architecture review. |

## See also

- Canonical status/progress hub: [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md)
- Architecture index: [README.md](README.md)
