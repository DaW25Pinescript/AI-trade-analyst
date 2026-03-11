# AI Trade Analyst — Reusable AI Briefing Prompt

You are working in the **AI Trade Analyst** repository.

## Mandatory orientation order
1. Read `docs/AI_TradeAnalyst_Progress.md` first (single canonical status/phase hub).
2. Read `docs/README.md` (documentation doctrine and ownership model).
3. Read `docs/architecture/repo_map.md` and `docs/architecture/system_architecture.md` (repo + architecture orientation).
4. Read `docs/architecture/CONTRACTS.md` and relevant `docs/specs/` assets before touching APIs, schemas, scoring, gates, verdicts, or prompt contracts.

## How to reason safely in this repo
- Treat this project as a **structured discretionary trade decision-support system**, not an auto-trading bot.
- Prefer deterministic, code-level computation and explicit contracts over free-form LLM inference.
- Preserve explainability, auditability, and schema-backed outputs.
- Do not invent architecture, integration maturity, or roadmap status.
- Distinguish implemented behavior vs planned/in-progress items.
- If uncertain, state ambiguity explicitly and anchor decisions to documented evidence.

## Documentation governance constraints
- `docs/AI_TradeAnalyst_Progress.md` is the only status/progress source of truth.
- Do not create competing progress trackers or duplicate canonical repo maps.
- Use docs folders by intent:
  - `docs/specs/` = implementation specs/acceptance/contracts assets
  - `docs/architecture/` = enduring architecture/contracts
  - `docs/runbooks/` = operational procedures
  - `docs/design-notes/` = working notes/history (non-canonical status)
  - `docs/archive/` = historical/superseded artifacts

## Output expectations
- Ground claims in current repository files.
- Keep terminology precise (bias, gates, verdict, confluence, invalidation, timeframe context).
- For changes, be explicit about scope, risks, and downstream contract impact.
