# Release checklist

## G12 merged TODO (Codex baseline + Claude polish items)

Priority order: highest impact/risk first.

- [x] **P0 prerequisite:** Finish G11 UI verdict card + `/analyse` POST wiring (G12 starts only after this is complete).
- [x] **P1 accessibility labels:** Ensure all `input`/`textarea`/`select` controls have stable `id` + matching `<label for>`; use `fieldset`/`legend` for grouped radios/checkboxes.
- [x] **P1 form-safety hardening:** Add `type="button"` to all non-submit/navigation buttons.
- [x] **P1 keyboard UX:** Add clear `:focus-visible` styles (buttons, links, fields, custom controls) that work in dark/light themes.
- [x] **P1 dynamic announcements:** Add `aria-live` (`polite` default; `assertive` only if critical) to changing status/verdict/pipeline regions.
- [x] **P1 contrast polish:** Tune `--muted`/secondary text token(s) for WCAG AA-friendly readability.
- [x] **P1 print polish:** Remove dark-theme bleed in print, enforce readable print colors, add page-break controls for major blocks/tables.
- [x] **P2 docs/release snapshot:** Create G12 snapshot in `app/releases/` and add matching entry to `app/releases/README.md`.
- [x] **P2 user documentation:** Create/extend user guide (ticket flow, navigation, dynamic updates, print/export, keyboard a11y).
- [x] **P2 QA evidence:** Record quick manual QA notes (labels, keyboard focus, print preview) and exact changed-file list.

## Final release checks (run before merge)

- [x] Run tests: `node --test tests/*.js` (108/108 passing on 2026-03-03)
- [ ] Verify app loads from static server (`/app/`)
- [ ] Validate export/import roundtrip with sample data
- [ ] Confirm schemas match current enum/reference docs
- [x] Update `app/releases/README.md` for new milestone snapshot
- [ ] Commit + open PR with summary and test output
