# V3 User Guide (G12)

This guide covers the day-to-day flow in the V3 browser app (`app/index.html`) and the G12 accessibility/print behaviors.

## 1) Ticket entry flow

1. Open the app and start at **Section 1 — Setup Context**.
2. Complete required fields in each section before moving forward.
3. Use **Next** / **Back** navigation controls to move between sections.
4. Use the **Clone Last Ticket** helper when you want to prefill from prior entries.

## 2) Section navigation and dynamic status

- The app surfaces dynamic status text in dedicated live regions so assistive technologies can announce changes.
- Pipeline and validation updates are announced politely to avoid interrupting active input.
- The final verdict area updates after analysis runs and announces new content.

## 3) Running AI analysis

1. Ensure the local API service is running (`/analyse` endpoint available).
2. Click **Run AI Analysis**.
3. The UI posts the current packet to the bridge endpoint.
4. On success, the **AI Multi-Model Verdict** card is populated with decision, confidence, setup details, and no-trade conditions.
5. If the service is unavailable, the UI shows a graceful error status in the same result region.

## 4) Print and export workflow

- Use browser print preview to produce a high-contrast report.
- G12 print styles enforce light background + dark text to avoid dark-theme bleed.
- Key blocks (header, major cards, tables) use page-break controls to reduce awkward splits.
- Export/import JSON backup remains available for roundtrip workflows.

## 5) Keyboard accessibility expectations

- All primary interactive controls are keyboard reachable.
- Focus indicators use `:focus-visible` and are clearly visible in dark and light contexts.
- Non-submit buttons are explicitly typed (`type="button"`) to prevent accidental submissions.
- Form controls are associated with stable labels (`label[for]` + matching `id`).

## 6) Quick troubleshooting

- If **Run AI Analysis** fails immediately, verify the API container/service is running.
- If no verdict is shown, check browser console/network for `/analyse` failures.
- If print output looks stale, refresh once before opening print preview.
