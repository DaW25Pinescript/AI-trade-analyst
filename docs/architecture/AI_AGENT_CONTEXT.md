# AI Agent Context — AI Trade Analyst

## 1) Purpose

AI Trade Analyst is a **data-first, structured discretionary trade analysis system**.
It supports trader decision quality (triage, analysis, gates, verdicts, journaling/review) rather than acting as a naive auto-execution bot.

Key posture:
- Structured numerical market/macro context is primary.
- Multi-analyst / arbiter outputs are decision-support artifacts.
- Human workflow and review/audit surfaces are first-class.

See project-level framing in `README.md` and enduring architecture context in `docs/architecture/system_architecture.md`.

## 2) Canonical source of truth (status / phase)

**`docs/AI_TradeAnalyst_Progress.md` is the single canonical progress/status hub.**

AI agents should read it first to determine:
- current phase
- active priorities
- what is complete vs pending
- current risk/debt focus

Do **not** treat other docs as competing phase trackers.

## 3) Documentation governance

Use docs by intent:

- `docs/specs/` → implementation specs, acceptance artifacts, schemas, scoring references.
- `docs/architecture/` → enduring architecture, contracts, constraints, repo map, system-level references.
- `docs/runbooks/` → operator/developer procedures (setup, runtime, security, local ops).
- `docs/design-notes/` → working notes/history/iteration context (non-canonical status).
- `docs/archive/` → historical snapshots/audits/superseded artifacts (not live status).

Rules for AI agents:
- Update the canonical hub for status changes; do not start parallel progress documents.
- Prefer linking to existing docs over duplicating maps/contracts.
- If proposing roadmap/phase claims, ground them in the canonical hub.

## 4) Repo orientation (practical)

High-value roots:

- `ai_analyst/` — active FastAPI + LangGraph analysis runtime and API surface (`/analyse`, stream, triage/journey routes).
- Dev diagnostics are intentionally env-gated (`AI_ANALYST_DEV_DIAGNOSTICS` or `DEBUG`) and should remain local-first, production-conservative.
- `market_data_officer/` — deterministic market-data feed/scheduler/canonical packet lane.
- `macro_risk_officer/` — macro context ingestion/reasoning lane and supporting metrics/history.
- `app/` — browser workflow surfaces (dashboard/journey/journal/review) and adapter boundary.
- `analyst/` — legacy analyst/orchestration assets still relevant to some governance/seam behavior.
- `tests/` (+ subsystem test dirs) — cross-surface contract/integration coverage.
- `docs/` — documentation system with clear source-of-truth hierarchy.

For a maintained structure view, use `docs/architecture/repo_map.md` (do not create a second repo map).

## 5) System architecture summary (implemented vs in-progress)

Repo-grounded end-to-end flow:

1. **Market/context sources**
   - Price/timeframe inputs and macro/event inputs feed deterministic lanes.
2. **Ingestion/feed layer**
   - `market_data_officer/feed/*` + scheduler/market-hours logic maintain data freshness and policy behavior.
3. **Canonicalization (Market Data Officer)**
   - Canonical packet assembly and contracts live in MDO service/contracts modules.
4. **AI analysis engine (multi-analyst orchestration)**
   - `ai_analyst` API + graph pipeline handles orchestration, lenses, deliberation paths, and analysis outputs.
5. **Arbiter/verdict/governance layer**
   - Arbiter contracts and scoring/governance semantics are enforced via graph models plus scoring/spec references.
6. **UI trade-ideation + review journey**
   - `app/` consumes API responses through adapters and persists journey artifacts for journal/review flows.

Current-state caution:
- Lane-level architecture is implemented and coherent.
- Full direct runtime convergence of active `ai_analyst` graph execution with MDO packet coupling is documented as **emerging/in-progress**, not universally complete.

## 6) Engineering philosophy / operating rules for AI agents

When editing code/docs in this repo:

- Keep deterministic numerical/scoring logic in code/contracts, not improvised in prompts.
- Prefer explicit schemas/contracts/enums over implicit text conventions.
- Preserve explainability and auditability of verdicts, gates, and outputs.
- Avoid hidden prompt-only logic when a typed contract or validator is more appropriate.
- Do not overstate implementation maturity or claim integrations not evidenced in code/docs.
- Do not invent missing architecture; mark unknowns explicitly.
- Respect casing and response-shape contracts across backend ↔ adapter ↔ UI boundaries.

## 7) Read these first (AI onboarding order)

1. `docs/AI_TradeAnalyst_Progress.md` (canonical status/phase hub)
2. `docs/README.md` (documentation doctrine + navigation)
3. `docs/architecture/repo_map.md` (repo orientation)
4. `docs/architecture/system_architecture.md` (current-state architecture)
5. `docs/architecture/CONTRACTS.md` (API/UI contract expectations)
6. `docs/specs/README.md` (spec inventory and acceptance references)
7. `README.md` (project framing and data-first doctrine)

## 8) Current-phase caution

This file is a durable orientation layer, **not** a phase tracker.
Always defer to `docs/AI_TradeAnalyst_Progress.md` for “what is current now.”
Do not hardcode stale roadmap assumptions into architecture context updates.

---

## Reusable AI Briefing Prompt

You are working in the **AI Trade Analyst** repository.

Before proposing or changing anything:
1. Read `docs/AI_TradeAnalyst_Progress.md` first — it is the single canonical status/phase source.
2. Use `docs/README.md` for documentation governance.
3. Use `docs/architecture/repo_map.md` and `docs/architecture/system_architecture.md` for architecture orientation.
4. Use contracts/specs (`docs/architecture/CONTRACTS.md`, `docs/specs/`) before changing APIs, schemas, scoring, verdict, or gate behavior.

Operating rules:
- Treat AI Trade Analyst as a **structured discretionary decision-support system**, not an auto-trading bot.
- Keep deterministic calculations in code/contracts, not ad hoc LLM reasoning.
- Preserve explainability/auditability and explicit schema-backed artifacts.
- Do not invent project state, maturity claims, or missing integrations.
- If docs conflict or are ambiguous, call out ambiguity and defer to the canonical progress hub.
- Do not create competing progress trackers; update/link canonical docs instead.
