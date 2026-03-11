# AI Orientation — AI Trade Analyst

## What this is

AI Trade Analyst is a structured discretionary trade analysis system — not an auto-trading bot. It provides multi-analyst triage, verdict gates, and journaling to support human decision quality. Deterministic data and explicit contracts come first; LLM reasoning is a structured layer on top, never the foundation.

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

## What to read and when

The documents below are listed in priority order. Request what you need based on session scope — you rarely need all of them.

| # | Document | Role | When to request |
|---|----------|------|-----------------|
| 1 | `docs/AI_TradeAnalyst_Progress.md` | **Canonical status hub** — current phase, what's done, what's next, test counts, debt register | **Every session.** Read before proposing any work. |
| 2 | `docs/architecture/system_architecture.md` | Enduring architecture — lane descriptions, data flow, Mermaid diagram, known ambiguities | When touching architecture, cross-lane work, or unfamiliar subsystems. |
| 3 | `docs/architecture/repo_map.md` | Directory orientation — what lives where and how it connects | When navigating unfamiliar code areas or proposing new files. |
| 4 | `docs/architecture/technical_debt.md` | Debt ledger — open items, severity, status, linked phases | When picking up debt work, or to check if proposed work overlaps existing debt. |
| 5 | `docs/architecture/CONTRACTS.md` | API/UI contract expectations — casing, response shapes, boundary rules | When changing APIs, schemas, adapters, or anything crossing a module boundary. |
| 6 | `docs/specs/README.md` | Specs inventory — closed and active implementation specs | When writing or closing a spec, or checking acceptance history. |

## Operating rules (always apply)

- `docs/AI_TradeAnalyst_Progress.md` is the **only** status source of truth. Do not create competing trackers.
- Distinguish implemented vs planned. Do not overstate maturity or invent integrations.
- Keep deterministic logic in code and contracts, not in ad hoc LLM reasoning.
- Preserve explainability and auditability of verdicts, gates, and outputs.
- Respect casing contracts: snake_case backend/disk, camelCase JS store/components, adapters as translation boundary.
- If docs conflict or are ambiguous, state the ambiguity and defer to the Progress hub.

## After reading this file

Tell me what you're here to do. I'll request the documents I need from the list above and confirm my understanding before starting work.
