# Dashboard-Aware Progress File Maintenance — Instructions for Claude

> Paste this into your Claude conversation (or add to your project knowledge) so that future Claude sessions know how to keep the progress file data-rich for the dashboard.

---

## Context

The repo has a **project dashboard** (`dashboard.html`) generated from `AI_TradeAnalyst_Progress.md` by `generate_dashboard.py`. The dashboard parses specific markdown sections and renders them as an interactive visual dashboard with tabs for Phases, Activity, Roadmap, Specs, Tests, Tech Debt, and Risks.

**When you close a phase, ship a PR, write a spec, or update the project in any way, you must also update the progress file so the dashboard stays current.**

---

## Sections the Dashboard Reads (and how to maintain them)

### 1. `## Recent Activity` (table)

**Format:**
```
| Date | Phase | Activity |
|------|-------|----------|
| DD Mon YYYY | Phase-Name | One-line summary with key metrics |
```

**Rules:**
- Add a new row at the TOP of the table (newest first) whenever you complete a PR, close a phase, or make any meaningful project change.
- Keep entries to one line — include test count deltas and key deliverables.
- Use the PR label (e.g., `PR-OPS-5`, `PR-UI-7`) or phase name as the Phase column.
- Example: `| 16 Mar 2026 | PR-OPS-5 | Frontend Agent Ops wiring — Run + Health + Detail modes, 45 new tests, 288 total |`

### 2. `## Roadmap` (table)

**Format:**
```
| Priority | Phase | Description | Status | Depends On |
|----------|-------|-------------|--------|------------|
| 1 | Phase-Name | What it delivers | Status-emoji | Dependency |
```

**Rules:**
- Status values: `📋 Planned` (solid teal on dashboard) or `💭 Concept` (dimmed/dashed on dashboard)
- When a roadmap item begins implementation, **remove it from the Roadmap table** and add it to the Phase Status Overview table as `🟢 Active`.
- When adding new future ideas, add them at the bottom with `💭 Concept` status.
- Re-number priorities when the list changes.
- The `Depends On` column helps the dashboard show dependency context.

### 3. `### Phase Status Overview` (table)

**Format:**
```
| Phase | Description | Status |
|-------|-------------|--------|
| Phase Name | What it does — key metrics | ✅ Complete / 🟢 Active / ▶️ Next / ⏳ Pending / ⏸️ Parked |
```

**Rules:**
- This is the primary source for the dashboard's timeline progress bar, task slots, and phase chips.
- When closing a phase: change status to `✅ Complete` and add test count to the description.
- When starting a new phase: change it to `🟢 Active`.
- The dashboard calculates completion % from this table (complete / total).

### 4. `### Test count progression` (table)

**Rules:**
- Add a new row when a phase closes with a new test count milestone.
- Format: `| Phase Name | COUNT | What it proved |`

### 5. `## 8) Technical Debt Register` (tables)

**Rules:**
- When resolving a debt item, update its Resolution timing column to `✅ Resolved — DD Month YYYY`.
- The dashboard counts resolved vs total to calculate the Tech Debt % card.

### 6. `## 5) Risks to Manage` (bullet list)

**Rules:**
- Each risk is a bullet with format: `- **Risk name:** description`
- Strike through resolved risks with `~~` or remove them.
- Add new risks as they emerge.

### 7. Header metadata

**Rules:**
- Always update `**Last updated:**` to today's date.
- Always update `**Current phase:**` to reflect the active phase.

---

## Workflow: What to Do After Completing a Phase

When you close a phase or deliver a PR, update the progress file in this order:

1. **Header** — Update `Last updated` and `Current phase`
2. **Recent Activity** — Add a new row at the top of the table
3. **Phase Status Overview** — Mark the phase `✅ Complete`, update any `🟢 Active` / `▶️ Next` labels
4. **Roadmap** — If the completed item was on the roadmap, remove it. If new future work was identified, add it.
5. **Test count progression** — Add a row if test count changed
6. **Tech Debt Register** — Mark any resolved items
7. **Risks** — Add/remove/strike risks as appropriate
8. **Phase Index (at-a-glance)** — Update the bullet summary at the top
9. **Latest increment section** — Add a detailed `### Latest increment` block below the Phase Index

---

## Workflow: What to Do When Writing a New Spec

When writing a new phase spec:

1. The dashboard reads spec files directly (passed via `--specs`), so the spec `.md` file itself feeds the Specs & ACs tab.
2. Update the **Roadmap** table to promote the item from `💭 Concept` to `📋 Planned` if applicable.
3. Add a **Recent Activity** entry: `| Date | Spec-Name | Spec written — X acceptance criteria defined |`

---

## Dashboard File Locations

All files live in the repo root:

- `AI_TradeAnalyst_Progress.md` — the source of truth the dashboard reads
- `generate_dashboard.py` — the parser/generator (don't modify unless adding features)
- `dashboard_server.py` — live auto-refresh server
- `run_dashboard.bat` — double-click launcher (starts server + opens browser)
- `dashboard.html` — generated output (don't edit directly, it gets overwritten)

---

## Quick Reference: Dashboard Data Sources

| Dashboard Section | Parsed From |
|-------------------|-------------|
| Timeline progress bar + 89% | Phase Status Overview table (complete / total) |
| Phase tooltip | Header `Current phase:` field |
| Task slots mini-map | Phase Status Overview table (status colors) |
| Summary cards | Computed from phases, debt, specs, tests |
| Phase chips (Phases tab) | Phase Status Overview table |
| Activity feed (Activity tab) | `## Recent Activity` table |
| Roadmap cards (Roadmap tab) | `## Roadmap` table |
| Spec cards + AC lists (Specs tab) | Spec `.md` files passed via `--specs` |
| Test bar chart (Tests tab) | Test count progression table |
| Tech debt items (Debt tab) | `## 8) Technical Debt Register` tables |
| Risk items (Risks tab) | `## 5) Risks to Manage` bullets |
| Three-lane display | Computed: previous complete → current active → next phase |
