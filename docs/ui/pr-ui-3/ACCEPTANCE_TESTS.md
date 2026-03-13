# ACCEPTANCE TESTS — PR-UI-3

## Merge criteria

### A. Scope integrity
- [ ] No backend files changed
- [ ] No new API endpoints introduced
- [ ] No Agent Ops UI added
- [ ] No non-triage workspaces implemented beyond existing placeholders
- [ ] No SSE/WebSocket/live-stream behavior introduced

### B. Triage Board regression safety
- [ ] Triage Board still renders real data from `GET /watchlist/triage`
- [ ] Run Triage action still works through `POST /triage`
- [ ] Existing state handling still works: loading, ready, empty, stale, unavailable, demo-fallback, error
- [ ] Trust strip / feeder health behavior still renders correctly

### C. Shared layer quality
- [ ] Reusable components/hooks/utilities have clearer ownership boundaries
- [ ] Triage-specific code is not left in `shared/` without justification
- [ ] Shared component props are more coherent and easier to reuse
- [ ] Import paths are reasonable and documented if materially changed

### D. Testing
- [ ] `cd ui && npm run typecheck` passes clean
- [ ] `cd ui && npm run build` succeeds
- [ ] `cd ui && npm run test` passes
- [ ] New or updated tests cover extraction-sensitive behavior and shared component branches

### E. Documentation
- [ ] `docs/AI_TradeAnalyst_Progress.md` marks PR-UI-3 / Phase 3 complete
- [ ] `docs/specs/ui_reentry_phase_plan.md` marks Phase 3 complete and the next phase correctly
- [ ] `ui/README.md` updated if the structure/ownership guidance changed

## Review questions
A reviewer should be able to answer “yes” to these:
1. Is the shared layer more disciplined after this PR?
2. Did the author avoid speculative abstraction?
3. Is the Triage Board still the clean proving workspace?
4. Does this make PR-OPS-1 and later workspaces easier without pretending they already exist?
