# OBJECTIVE.md — Trade Ideation Journey V1.1

## What this phase is

V1 UI is accepted visually. It runs. All data is placeholder.

V1.1 makes it real:
- dashboard triage reads real repo artifacts
- journey bootstrap reads real analyst output
- saves write JSON to local disk
- journal and review read those saved records

The visual design, routing shape, stage order, and gate logic are frozen. Do not touch them.

---

## Stack context (confirmed)

| Port | Service |
|------|---------|
| 8080 | UI — vanilla ES modules, served by `python -m http.server` |
| 8000 | Repo backend — FastAPI (`ai_analyst/api/main.py`) |
| 8317 | Model proxy — local Claude proxy, OpenAI-compatible |

The UI cannot write files directly — it is a static browser page. All persistence must go through the FastAPI backend at port 8000.

---

## What the backend currently has

Existing FastAPI routes (confirmed via OpenAPI docs):
- health, feeder, analyse/analyse-stream, metrics/dashboard, analytics, backtest, plugins

**Missing — must be added in this phase:**

| Endpoint | Purpose |
|----------|---------|
| `GET /watchlist/triage` | Read triage artifacts for dashboard |
| `GET /journey/{asset}/bootstrap` | Read bootstrap payload for journey entry |
| `POST /journey/draft` | Save journey draft to disk |
| `POST /journey/decision` | Save decision snapshot to disk |
| `POST /journey/result` | Save result snapshot to disk |
| `GET /journal/decisions` | List saved decision records |
| `GET /review/records` | List saved decision + result records |

---

## What the frontend currently has

- Service layer (`app/lib/services.js`) — Pattern A file reads + demo mode fallback
- Adapter layer (`app/lib/adapters.js`) — normalises backend JSON to typed UI shapes
- Journey store (`app/stores/journeyStore.js`) — pub/sub state, in-memory snapshot only
- All data paths currently return demo/mock data

**Frontend work in this phase:**
- Wire service layer to real backend endpoints
- Replace active mock paths with real reads
- Add truthful loading / stale / missing / unavailable states
- Wire save action to backend POST — not in-memory only
- Wire journal + review reads to backend GET

---

## Persistence layout (locked)

```
app/data/journeys/
  drafts/       journey_<journeyId>.json
  decisions/    decision_<snapshotId>.json
  results/      result_<snapshotId>.json
```

All three directories created by the backend on first write if they do not exist.

---

## Output of this phase

At the end of V1.1:

1. Dashboard populates from real triage artifacts (or shows truthful unavailable state)
2. Begin Journey loads real bootstrap payload for the selected asset
3. Save/freeze writes a JSON file to `app/data/journeys/decisions/`
4. Journal page lists real saved records from disk
5. Review page reads real saved records from disk
6. Saved records survive refresh, route change, and app restart
7. V1 visual design is unchanged

---

## What this phase is NOT

- Not a UI redesign
- Not charting implementation
- Not multi-persona UI expansion
- Not cloud or database persistence
- Not a new product surface
- Not fake browser-only persistence dressed as real saves
