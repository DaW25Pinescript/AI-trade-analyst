# Technical Debt Log

**Last updated:** 17 March 2026

---

## Active Items

### TD-PR-REFLECT-3-1: Mouse-click-only persona row navigation (AC-70)

**Source:** PR-REFLECT-3, 17 March 2026
**Severity:** Low (accessibility)
**Description:** Persona performance table rows navigate to Agent Ops Detail on mouse click only. Keyboard activation (`Enter`/`Space` on focused row) is not implemented in v0.
**Resolution:** Add `role="button"`, `tabIndex={0}`, and keyboard event handlers to navigable `<tr>` elements in `PersonaPerformanceTable.tsx`.

### TD-PR-REFLECT-3-2: Native title tooltip for suggestion evidence

**Source:** PR-REFLECT-3, 17 March 2026
**Severity:** Low (UX polish)
**Description:** Suggestion evidence is displayed via native HTML `title` attribute, which has limited formatting and inconsistent cross-browser behavior. A proper tooltip component would provide richer evidence display.
**Resolution:** Create a reusable `<Tooltip>` component (or adopt `@radix-ui/react-tooltip`) and replace `title` attributes on suggestion items.

### TD-PR-REFLECT-3-3: Persona→entity prefix mapping (Outcome B)

**Source:** PR-REFLECT-3 §13.2, 17 March 2026
**Severity:** Low (architectural)
**Description:** `navigable_entity_id` is computed as `f"persona_{persona}"` — a deterministic prefix mapping. This works because the ops roster uses the same prefix convention. If the roster ID scheme changes, this mapping will break.
**Resolution:** When entity identity is formalized (e.g., via a shared registry), replace the prefix convention with a proper lookup.
