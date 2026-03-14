# canFreeze contract — post-merge addendum (PR-UI-4a)

## Decision

Freeze is a **formally gated commitment action**, not a lightly gated UI convenience. Both frontend and backend must enforce the same gate independently.

## Frontend gate — `canFreeze`

`canFreeze` is `true` only when **all** of the following hold:

| Condition | Value required |
|---|---|
| `condition` (workspace) | `ready` \| `stale` \| `partial` |
| `stage` | `draft` |
| `isFrozen` | `false` |
| `thesis` | non-empty string (trimmed) |
| `userDecision` | non-empty string |

`conviction` and `notes` are quality signals only — they do not gate the Freeze action.

## Backend contract

Backend MUST independently validate the same conditions and reject freeze attempts that bypass frontend gating. The 409 conflict path remains live regardless of frontend state.

## Rationale

- Frontend gating gives workflow guidance — Freeze Decision button stays disabled
  until the minimum decision fields are present, preventing accidental empty freezes.
- Backend validation preserves integrity — protects against malformed requests
  and any bypass of the frontend gate.
- The 409 conflict path is a separate concern and must remain active regardless
  of whether the frontend gate was satisfied.

## Affected file

`ui/src/workspaces/journey/adapters/journeyViewModel.ts` — `buildJourneyWorkspaceViewModel()`, `canFreeze` field.
