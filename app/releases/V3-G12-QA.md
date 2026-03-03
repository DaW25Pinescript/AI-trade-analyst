# V3 G12 QA Notes

Date: 2026-03-03

## Scope

- Final G12 polish tracking updates
- Release snapshot creation
- User guide documentation update

## Manual QA notes

- Labels: prior G12 a11y updates already ensure labeled controls across the primary intake flow.
- Keyboard: prior G12 keyboard pass confirms visible `:focus-visible` treatment on primary controls.
- Print preview: prior print pass confirms light-background readable output and reduced awkward block splitting.
- Analysis flow: G11 verdict card/POST integration is already merged and available in current baseline.

## Automated checks

- `node --test tests/*.js` (pass)

## Changed files in this increment

- `app/releases/V3-G12.html`
- `app/releases/V3-G12-QA.md`
- `app/releases/README.md`
- `docs/V3_user_guide.md`
- `docs/V3_master_plan.md`
- `tooling/release_checklist.md`
