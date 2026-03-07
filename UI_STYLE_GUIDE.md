# UI_STYLE_GUIDE.md
## AI Trade Analyst – V1 UI Style Guide
Version: 1.0  
Status: Approved Reference Direction  
Scope: V1 Trade Ideation Journey UI

---

## 1. Purpose

This document formalizes the **visual language, interface tone, and reusable design rules** for the V1 AI Trade Analyst UI.

It exists to prevent subjective drift and to make the approved mockup reproducible across contributors, tools, and implementation passes.

This guide should be used by:
- frontend engineers
- design contributors
- Codex / Claude / other codegen tools
- reviewers evaluating UI consistency

This is not a marketing brand guide. It is a **product interface guide** for a trading workspace.

---

## 2. V1 Reference Statement

The approved Trade Ideation Journey mockup is the **V1 visual north star** for the repo.

That mockup should be treated as the baseline reference for:
- interface tone
- panel treatment
- layout hierarchy
- state semantics
- stage flow presentation
- gate severity styling
- verdict / decision / execution separation
- review engine framing

This means future UI work should aim to feel like a coherent continuation of that mockup, not a redesign from scratch.

---

## 3. Product Aesthetic

### Desired overall feel
The UI should feel like:
- an institutional trading workspace
- a disciplined analyst terminal
- a premium dark-mode control surface
- a high-trust decision environment

### It should **not** feel like:
- a generic SaaS dashboard
- a playful productivity tool
- a neon cyberpunk toy
- a consumer trading app
- a bloated enterprise admin panel

### Core tone words
- serious
- structured
- calm
- high-signal
- premium
- auditable
- risk-aware
- deliberate

---

## 4. Design Principles

### 4.1 Triage-first, not form-first
The product opens with informed relevance, not empty inputs.

### 4.2 Risk moments should feel different
The Gate Checks surface must carry visibly more severity than normal content screens.

### 4.3 High hierarchy, low clutter
The user should immediately understand what matters most on each surface.

### 4.4 Panels over noise
Use well-defined cards, shells, and containers instead of loose floating elements.

### 4.5 Color is semantic, not decorative
Accent colors should convey state, emphasis, and system meaning.

### 4.6 Human and system must remain distinct
System-generated context and human override actions should be visually distinguishable.

### 4.7 Premium restraint
The interface may be polished, but never flashy for its own sake.

---

## 5. Color System

The V1 UI uses a **dark-first palette** with restrained accent usage.

### 5.1 Base palette roles
These are semantic roles, not hardcoded final token names.

- `bg.app` — deepest application background
- `bg.canvas` — main content background
- `bg.surface` — standard card / panel fill
- `bg.surfaceElevated` — slightly more pronounced container fill
- `bg.subtle` — low-emphasis fill for internal blocks
- `border.default` — standard border
- `border.emphasis` — stronger border for active or important surfaces
- `text.primary` — primary reading text
- `text.secondary` — secondary supporting text
- `text.muted` — low emphasis metadata text
- `text.inverse` — dark text on bright button surfaces

### 5.2 Accent roles
- **Indigo / blue-violet** → AI/system context, stage emphasis, active focus
- **Emerald / green** → passed, aligned, accepted, favorable
- **Amber** → conditional, caution, pending, requires interpretation
- **Rose / red** → blocked, conflict, severe gate state, invalidation
- **Sky / cool blue** → watch-state, observational relevance, low-commitment interest

### 5.3 Usage rules
- Do not flood screens with accent color.
- Most surfaces should remain neutral with accent applied to:
  - badges
  - status labels
  - active controls
  - progress highlights
  - important callouts
- Severe states should use both color and container treatment, not color alone.

### 5.4 Status semantics
#### Triage statuses
- `Actionable` → emerald
- `Conditional` → amber
- `Watch` → sky
- `Avoid` → rose

#### Gate states
- `passed` → emerald
- `conditional` → amber
- `blocked` → rose

#### Provenance markers
- `ai_prefill` → indigo-toned
- `user_confirm` → neutral-to-emerald
- `user_override` → amber-toned emphasis
- `user_manual` → neutral

---

## 6. Typography

Typography should be clean, modern, and highly legible.

### 6.1 Hierarchy
Use a restrained hierarchy with clear separation between:
- page title
- section title
- card title
- label / metadata
- body text
- tiny uppercase system labels

### 6.2 Style guidance
- Headlines should be strong but not oversized.
- Body copy should prioritize readability over density.
- Metadata should use muted tone and occasionally uppercase tracking for system framing.
- Avoid excessive font-size variety.

### 6.3 Tone
Written UI text should sound:
- precise
- controlled
- matter-of-fact
- audit-friendly

Avoid overly casual microcopy.

Examples:
- Good: `Forward progression blocked`
- Good: `Override justification required`
- Bad: `Oops, you need to fix this first`

---

## 7. Spacing and Shape Language

### 7.1 Layout rhythm
Use generous spacing to preserve a premium feel.
The product should breathe.

### 7.2 Container radius
The approved mockup uses a soft, premium rounded language.
Recommended hierarchy:
- major shells: large radius
- cards: medium-large radius
- badges / pills: fully rounded or soft pill
- small controls: medium radius

### 7.3 Density
Default density should feel deliberate rather than compressed.
This is not a trader scalping DOM interface; it is a structured analysis workspace.

---

## 8. Surface System

The interface should be composed from a clear set of reusable surface types.

### 8.1 App background
A deep dark background with subtle gradient/radial depth is appropriate.
It should support immersion without becoming visually noisy.

### 8.2 Standard card
Use for:
- triage items
- summaries
- review metrics
- snapshot preview blocks

Characteristics:
- dark neutral fill
- soft border
- strong readability
- moderate elevation

### 8.3 Elevated surface
Use for:
- major stage shells
- important split layouts
- dense, high-value work areas

Characteristics:
- slightly stronger fill and shadow presence
- more visual authority than standard cards

### 8.4 Internal module block
Use for:
- sub-panels inside cards
- evidence slots
- note areas
- metric sub-groups

Characteristics:
- lower contrast than major cards
- still clearly bounded

### 8.5 Severe risk surface
Reserved for gate/compliance/control-boundary moments.

Characteristics:
- stronger border contrast
- rose/red severity accents where appropriate
- stronger visual weight
- should feel intentionally more serious than surrounding screens

---

## 9. Layout Patterns

### 9.1 Triage board
Pattern:
- page header
- relevance framing copy
- asset card grid

Card anatomy:
- symbol
- triage badge
- bias hint
- mini-chart / placeholder
- why-interesting tags
- confidence indication
- rationale
- primary action

### 9.2 Journey stage shell
Pattern:
- top stepper / progress state
- left visual / chart / evidence area
- right interpretation / controls / notes area
- bottom action row

This is the core working layout of the product.

### 9.3 Gate boundary screen
Pattern:
- stronger title treatment
- global boundary state banner
- stacked gate rows
- justification area for conditional or blocked items
- disabled progression when policy requires it

### 9.4 Verdict split screen
Pattern:
- 3-column or 3-panel layout:
  - System Verdict
  - User Decision
  - Execution Plan

These must remain visually distinct.

### 9.5 Journal capture
Pattern:
- evidence and notes on one side
- frozen snapshot preview on the other

### 9.6 Review engine
Pattern:
- planned vs actual comparison panel
- metric / pattern cards
- refinement suggestions

---

## 10. Component Language

### 10.1 Cards
Cards should feel premium and clean.
Use:
- consistent padding
- consistent border language
- clear title and content zones

Avoid random card styles per page.

### 10.2 Badges
Badges communicate state and provenance.
Use them often, but carefully.
They should be compact, readable, and semantic.

### 10.3 Progress stepper
The stepper should clearly distinguish:
- completed stages
- current stage
- future stages

It should feel structured, not gamified.

### 10.4 AI context blocks
System-generated content should be clearly identifiable but not visually overpowering.
Recommended cues:
- indigo-toned badge or marker
- labeled section headers
- stable formatting

### 10.5 User override blocks
User-entered judgment should be clearly visible as human intervention.
Recommended cues:
- labeled note box
- provenance marker
- visible separation from AI summary

### 10.6 Evidence areas
For now, evidence containers can be simple.
But they should already communicate:
- files belong to the decision record
- attachments are part of auditability

### 10.7 Inputs
Inputs should feel calm and professional.
Avoid bright outlines or flashy focus effects.

### 10.8 Primary actions
Primary actions should be obvious without dominating the screen.
A bright neutral or restrained high-contrast CTA style is appropriate.

---

## 11. Severity Model

A critical part of the style guide is that not all screens carry the same emotional weight.

### 11.1 Normal analysis screens
Feel:
- thoughtful
- premium
- analytical

### 11.2 Control-boundary screens
Feel:
- serious
- policy-driven
- explicit
- harder to ignore

### 11.3 Review screens
Feel:
- reflective
- audit-oriented
- transparent

This changing emotional weight is intentional and should be preserved.

---

## 12. Motion and Interaction

Motion should be restrained.

### 12.1 Good motion
- soft hover elevation
- subtle tab transitions
- gentle content reveal
- minor progress-state transitions

### 12.2 Avoid
- exaggerated bounce
- flashy animated gradients
- attention-hijacking movement
- gimmicky chart-like motion outside real charts

The product should feel calm and competent.

---

## 13. Chart and Data Visualization Treatment

The chart area in V1 may initially use placeholders or lightweight containers.
Even then, visual treatment matters.

### Rules
- Chart panels should feel like real analysis surfaces, not empty boxes.
- Annotation layers should look intentionally integrated.
- Supporting labels like `sweep + reclaim` or `discount FVG` should use semantic pill styling.
- Do not overload the panel with drawing-tool aesthetics before real chart integration exists.

### Mini-charts
Mini-charts on triage cards should:
- be simple
- convey motion or trend impression
- avoid fake precision
- support triage, not replace full chart analysis

---

## 14. Accessibility and Readability

This is a dark UI, so contrast discipline matters.

### Requirements
- primary text must remain easily readable
- muted text must still be legible
- status differences must not rely on color alone
- blocked / conditional / passed states should also differ via iconography, labels, and container treatment

### Accessibility stance
The interface should aim for strong practical readability even when exact accessibility compliance work is deferred to later polish.

---

## 15. Do / Don’t Rules

### Do
- keep the palette restrained
- use consistent rounded panel treatment
- preserve clear hierarchy
- make gate states visually unmistakable
- separate AI content from human action
- preserve snapshot / audit framing
- keep layouts modular and repeatable

### Don’t
- redesign each page independently
- mix playful and institutional styles
- overuse gradients
- use neon accents everywhere
- turn every metric into a visual gimmick
- collapse verdict / decision / plan into one blob
- make the review engine feel mystical or opaque

---

## 16. Repo Implementation Guidance

This guide should inform implementation in:
- `app/components/`
- `app/routes/` or `app/pages/`
- `app/styles/`
- shared theme tokens / CSS variables / Tailwind config

### Recommended next technical step
Translate this guide into concrete reusable tokens and primitives such as:
- color tokens
- spacing scale
- radius scale
- surface variants
- badge variants
- state variants
- layout shell patterns

### Recommended primitive families

The canonical component name list is defined in `ARCHITECTURE.md` Section 6.2. The primitive families from this guide map to those names as follows:

| Style guide primitive | Canonical name in ARCHITECTURE.md |
|---|---|
| `AppShell` | `AppShell` |
| `PageHeader` | `PageHeader` |
| `SurfaceCard` | `SurfaceCard` |
| `SeverityCard` | `SeverityCard` |
| `StatusBadge` | `StatusBadge` |
| `ProvenanceBadge` | `ProvenanceBadge` |
| `StageStepper` | `StageStepper` |
| `EvidencePanel` | `EvidencePanel` |
| `SplitVerdictPanel` | `SplitVerdictPanel` |

Additional components (`AIPrefillCard`, `GateChecklist`, `ChartAnnotationLayer`, `NotesTextarea`) are defined in `ARCHITECTURE.md` Section 6.2. Use those names in all implementation work.

---

## 17. Review Standard

A UI pass should be considered visually aligned only if it satisfies all of the following:
- clearly resembles the approved V1 mockup aesthetic
- preserves the dark premium workspace tone
- uses semantic state colors consistently
- treats gates with visibly higher severity
- preserves the verdict / decision / plan separation
- preserves audit and snapshot framing
- avoids unnecessary visual invention outside the established language

---

## 18. Suggested Prompting Language for Codex / Claude

Use wording like:

- “Match the V1 Trade Ideation Journey visual language defined in `UI_STYLE_GUIDE.md`.”
- “Preserve the institutional dark workspace aesthetic and restrained semantic accent usage.”
- “Treat Gate Checks as a severe control-boundary screen, not a normal form step.”
- “Keep System Verdict, User Decision, and Execution Plan visually distinct.”
- “Do not redesign the product language; extend the approved V1 design system.”
- “Favor modular reusable surfaces and status badges over page-specific styling hacks.”

---

## 19. Future Evolution

This is a V1 guide, not a permanent ceiling.

Later versions may expand:
- tokenized theme system
- chart integration rules
- responsive/mobile treatment
- analyst persona panels
- richer review analytics UI
- design QA checklist with screenshots

But future refinement should evolve from this base, not discard it casually.

---

## 20. Summary

The V1 AI Trade Analyst UI should look and feel like a premium, dark, disciplined trading workspace.
It should be structured, high-trust, and risk-aware.

Its defining characteristics are:
- triage-first entry
- premium panel-based layout
- restrained semantic color
- severe gate treatment
- strict separation of system judgment and human decision
- explicit snapshot / audit framing
- transparent review-oriented architecture

This guide exists so the approved mockup becomes a reproducible interface language rather than a one-time visual impression.
