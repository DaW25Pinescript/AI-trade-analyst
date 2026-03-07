# CONSTRAINTS.md — Trade Ideation Journey V1.1

## Hard constraints — never violate

### 1. No redesign
- Do not restyle, restructure, or reorder the accepted V1 UI
- Do not change visual language, routing shape, stage order, or gate boundary styling
- Component names from ARCHITECTURE.md are frozen: AppShell, PageHeader, SurfaceCard, SeverityCard, StatusBadge, ProvenanceBadge, StageStepper, EvidencePanel, SplitVerdictPanel, AIPrefillCard, GateChecklist, ChartAnnotationLayer, NotesTextarea

### 2. No invented data
- Do not fabricate backend payload fields
- Do not substitute analysis prose when the upstream source is absent
- If a field is missing, surface that as `null` or an explicit missing state — not a plausible-looking fake value
- Demo mode is only for when the backend is explicitly unreachable — not as a cover for missing data

### 3. No browser-only persistence
- `localStorage`, `sessionStorage`, and `IndexedDB` must not be the source of truth for saved records
- In-memory store mutation is not a save
- `success: true` must only be returned after a confirmed disk write via the backend
- Do not show "Saved successfully" for state that lives only in `journeyStore`

### 4. No direct Python calls from the browser
- The UI does not execute Python, import Python modules, or call analyst pipeline scripts directly
- All backend interaction goes through the FastAPI server at port 8000
- Pattern A (direct file reads from `analyst/output/`) is superseded in V1.1 — all reads go through FastAPI endpoints

### 5. No collapse of the three verdict layers
- `systemVerdict`, `userDecision`, and `executionPlan` must remain separate objects in the snapshot
- Do not merge them into a convenience object at save time

### 6. No new product surfaces
- Do not add screens, routes, or features outside the defined V1.1 scope
- Charting, multi-persona expansion, and cloud persistence are explicitly out of scope

---

## Casing convention (locked)

| Layer | Convention |
|-------|-----------|
| Backend FastAPI models, API responses, persisted JSON on disk | `snake_case` |
| Frontend JS store, component props, domain state | `camelCase` |
| Adapters | Explicit translation boundary — converts both ways |

- `app/lib/adapters.js` is the only place that touches `snake_case` field names
- Components never reference `snake_case` directly
- Save payloads are converted back to `snake_case` by the adapter before POST
- See CONTRACTS.md Section 5 for the full field mapping table

---

## Architecture constraints

### Backend
- New Journey endpoints must be added to the existing FastAPI app — do not create a second server
- All file writes use `app/data/journeys/` as the canonical root — no alternative locations
- Directories are created on first write if they do not exist
- Decision snapshots are immutable — once written, they are not overwritten

### Frontend
- Service layer is the only place that knows about transport — components never call `fetch` directly
- Adapters are the only place that knows about backend payload shapes — components consume typed UI shapes only
- `data_state` must flow from backend response → adapter → store → component — it must not be dropped at any layer

### API
- Ensure `load_dotenv()` is called before any config or client init in `ai_analyst/api/main.py`
- New Journey router should be a separate file, e.g. `ai_analyst/api/routers/journey.py`, registered in `main.py`
- Do not modify existing routes

---

## Data state display rules

| State | Dashboard behavior | Journey behavior |
|-------|--------------------|-----------------|
| `live` | Render normally | Render normally, no banner |
| `stale` | Show staleness indicator on card | Show amber banner with timestamp |
| `partial` | Show partial badge | Show partial banner, continue allowed |
| `unavailable` | Show empty state card | Show blocking unavailable state |
| `demo` | Show "Demo data" badge on each card | Show "Demo mode" banner in stage header |
| `error` | Show error state card | Show error banner, block progression |

---

## Save semantics

1. User triggers save/freeze action
2. Frontend calls `POST /journey/decision` with full snapshot object
3. Backend writes file, returns `{ success: true, snapshot_id, saved_at, path }`
4. Frontend resolves save promise only on confirmed success
5. UI shows success state only after step 4
6. If backend returns error, UI shows explicit failure — no silent fallback
