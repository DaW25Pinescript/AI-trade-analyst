# UI Phase 3 — Visual Design Decisions

**File:** `docs/ui/DESIGN_NOTES.md`  
**Status:** Active  
**Depends on:** `UI_CONTRACT.md`, `UI_WORKSPACES.md`, and the wireframe + component system artifacts generated during Phase 3 design.

These notes capture the key visual and interaction decisions made during the design phase so that implementation (or future Codex runs) can stay faithful without reverse-engineering images.

---

## 1. Core Design Decisions (contract-grounded)

1. **Per-row staleness on Triage Board**  
   Derived from `TriageItem.verdict_at?` (UI_CONTRACT §9.5). Fresh rows show no badge (absence of badge is the trust signal). Only stale rows show the stale badge. Per-row `data_state` is never invented — the backend only exposes board-level `data_state`.

2. **`data_state` is read-only, not a dropdown**  
   The `data_state` badge in the Triage Board header must use a tooltip or expandable info chip to show freshness detail, not a dropdown/chevron affordance. A dropdown implies the user can change the state, but `data_state` is a backend-reported read-only signal.

3. **Freeze Decision behavior (Journey Studio)**  
   Freezing (`POST /journey/decision`) locks the **entire** center column to read-only review state. The immutable snapshot captures full staged context. Post-freeze visual shift: form fields become non-editable text, stage flow loses interactive affordances, header shifts from "Draft · unsaved" to "Frozen · snapshot_id," footer simplifies (Save Draft disappears, Freeze shows as confirmed, Save Result becomes active).

4. **Save Result gating**  
   "Save Result" button is disabled/greyed with tooltip "Only after freeze succeeds" until a frozen `snapshot_id` exists. Matches contract sequencing: draft → freeze → result.

5. **Triage → Journey handoff**  
   Entire row is clickable (hover border + arrow affordance). On click, Journey Studio header shows brief "loading" state on the bootstrap freshness badge (fast synchronous GET). No full-page interstitial needed.

6. **Analysis Run tabs**  
   Submission | Execution | Verdict tabs remain navigable post-run. Submission becomes read-only but accessible for "what did I submit?" verification. Verdict tab is disabled/greyed with "No verdict — run failed" on failure — it never implies partial output exists on a terminal failed state (UI_CONTRACT §7.1, §9.3).

7. **Usage panel**  
   Inline accordion toggle directly below Verdict (secondary artifact read). Handles empty-but-valid and artifact-missing gracefully. No navigation away from the workspace.

8. **Header context on Analysis Run**  
   Always shows provenance: "Analysis Run · AAPL · Escalated from Journey Studio" breadcrumb plus "Return to Journey" button when the entry point was Journey Studio.

9. **Journal & Review: no fake detail screens**  
   Do not create a deep detail screen for decisions or reviews unless there is a backed contract to populate it (UI_WORKSPACES §8.5). The current backend exposes list-level data only. Building a richer detail view against aspirational fields violates the contract-first rule.

---

## 2. Component System Usage Rules

- **Trust strip (Triage header):** `data_state` badge + feeder health chip + timestamp always appear side-by-side as a single grouped element. Never separated.
- **Execution stack (Analysis Run):** lifecycle label → spinner → preserved run_id, arranged as a vertical stack inside the execution panel.
- **Conditional rail (Journey Studio):** stack panels when bootstrap fields exist (`arbiter_decision`, `explanation`/`reasoning_summary`, `no_trade_conditions`). Collapse to single "Bootstrap unavailable" fallback when `data_state` = unavailable. No stacked empty panels.
- **Post-action lock:** read-only indicator + disabled buttons + greyed panels applied uniformly after Freeze (Journey Studio) or Completed (Analysis Run).

---

## 3. Density and Scanability Rule

Medium-density TradingView watchlist style across all workspaces. "Why interesting" and narrative fields always get the widest column and breathing room. Hover affordances (entire row, entire stage, entire panel) are mandatory on all clickable surfaces. Content expansion pushes content downward rather than overlaying — preserves scanability during exploration.

---

## 4. Contract Traceability

All decisions map directly to:

- UI_WORKSPACES sections 5–7 (recommended layouts)
- UI_CONTRACT sections 6, 7, 9–12 (states, lifecycle, error handling, retry rules)

This file is the single source of visual truth when the wireframes are not open.
