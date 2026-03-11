# CONTRACTS.md — Trade Ideation Journey V1.1

## 1. Backend endpoint contracts

### GET /watchlist/triage

Returns a list of triage items for the dashboard.

**Source:** Read from `analyst/output/` — any available `*_multi_analyst_output.json` files. If none exist, return empty list with `data_state: "unavailable"`.

**Response shape:**
```json
{
  "data_state": "live | stale | unavailable",
  "generated_at": "ISO timestamp or null",
  "items": [
    {
      "symbol": "XAUUSD",
      "triage_status": "watch | active | blocked | no_data",
      "bias": "long | short | neutral | no_data",
      "confidence": "high | moderate | low | none",
      "why_interesting": ["string"],
      "rationale": "string or null",
      "verdict_at": "ISO timestamp or null"
    }
  ]
}
```

**Rules:**
- If `analyst/output/` is empty, return `{ data_state: "unavailable", items: [] }`
- Do not fabricate triage items
- `why_interesting` may be empty array if upstream data has no tags

---

### GET /journey/{asset}/bootstrap

Returns the full bootstrap payload for a journey entry screen.

**Source:** `analyst/output/{asset}_multi_analyst_output.json` + `analyst/output/{asset}_multi_analyst_explainability.json`

**Response shape:**
```json
{
  "data_state": "live | stale | partial | unavailable",
  "instrument": "XAUUSD",
  "generated_at": "ISO timestamp or null",
  "structure_digest": { },
  "analyst_verdict": {
    "verdict": "long_bias | short_bias | no_trade | conditional | no_data",
    "confidence": "high | moderate | low | none"
  },
  "arbiter_decision": { },
  "explanation": { },
  "reasoning_summary": "string or null"
}
```

**Rules:**
- If file does not exist, return `{ data_state: "unavailable", instrument: asset }`
- If explainability file missing but output file exists, return `data_state: "partial"`
- Never populate fields with invented analysis text

---

### POST /journey/draft

Saves a journey draft to disk.

**Request body:** Full journey state object (see store shape in CONTRACTS section 2)

**Response:**
```json
{
  "success": true,
  "journey_id": "string",
  "saved_at": "ISO timestamp",
  "path": "app/data/journeys/drafts/journey_<id>.json"
}
```

**Rules:**
- Create `app/data/journeys/drafts/` if it does not exist
- Return `success: false` with `error` field if write fails
- Never return `success: true` for in-memory-only operation

---

### POST /journey/decision

Saves a frozen decision snapshot to disk.

**Request body:** `decisionSnapshot` object (see section 2)

**Response:**
```json
{
  "success": true,
  "snapshot_id": "string",
  "saved_at": "ISO timestamp",
  "path": "app/data/journeys/decisions/decision_<id>.json"
}
```

**Rules:**
- Create directory if missing
- Snapshot is immutable — do not overwrite an existing ID
- Return error if ID collision detected

---

### POST /journey/result

Saves a result snapshot (planned vs actual) to disk.

**Request body:** `resultSnapshot` object

**Response:** Same shape as decision response, path under `app/data/journeys/results/`

---

### GET /journal/decisions

Returns list of saved decision snapshots.

**Source:** `app/data/journeys/decisions/*.json`

**Response:**
```json
{
  "records": [
    {
      "snapshot_id": "string",
      "instrument": "string",
      "saved_at": "ISO timestamp",
      "journey_status": "string",
      "verdict": "string",
      "user_decision": "string or null"
    }
  ]
}
```

**Rules:**
- If directory is empty or missing, return `{ records: [] }`
- Do not return full snapshot body in list — summary fields only

---

### GET /review/records

Returns list of saved decision + result records for the review surface.

**Response:** Same shape as journal/decisions but may include `has_result: bool` per record.

---

## 2. Frontend contracts

### decisionSnapshot (frozen at save time)

```js
{
  snapshot_id: string,        // stable UUID
  journey_id: string,
  instrument: string,
  saved_at: ISO string,
  journey_status: string,
  stage_data: { ...per stage },
  gate_states: { gate_id: "passed|conditional|blocked" },
  gate_justifications: { gate_id: string },
  system_verdict: {
    verdict: string,
    confidence: string,
    reasoning_summary: string | null
  },
  user_decision: {
    direction: string,
    conviction: string,
    notes: string | null
  },
  execution_plan: {
    entry: string | null,
    stop: string | null,
    target: string | null,
    risk_reward: string | null,
    notes: string | null
  },
  provenance: { field_key: "ai_prefill|user_confirm|user_override|user_manual" },
  bootstrap_data_state: "live|stale|partial|unavailable"
}
```

### data_state values (used across all service responses)

| Value | Meaning |
|-------|---------|
| `live` | Data exists and is fresh |
| `stale` | Data exists but is old |
| `partial` | Some required fields missing |
| `unavailable` | No data exists at all |
| `error` | Read/write failure |

### Provenance markers

| Value | Meaning |
|-------|---------|
| `ai_prefill` | Field populated by system/analyst output |
| `user_confirm` | User confirmed AI-prefilled value |
| `user_override` | User changed AI-prefilled value |
| `user_manual` | User entered value with no AI prefill |

---

## 3. Adapter contracts

Adapters must:
- Accept sparse/partial backend payloads without throwing
- Map missing fields to typed null/default — never to fabricated values
- Pass `data_state` through to the UI shape so components can render truthful states
- Not invent `why_interesting` tags, rationale text, or analysis prose when upstream is absent

Adapters must not:
- Silently substitute demo values when real data is missing
- Suppress `data_state` from the component layer

---

## 5. Casing convention (locked)

This is the canonical casing rule for all V1.1 and later work. Do not deviate.

| Layer | Convention | Examples |
|-------|-----------|---------|
| Backend — FastAPI models, API responses, persisted JSON on disk | `snake_case` | `snapshot_id`, `journey_status`, `data_state`, `saved_at` |
| Frontend — JS store objects, component props, domain state | `camelCase` | `snapshotId`, `journeyStatus`, `dataState`, `savedAt` |
| Adapters — service layer and adapter files | Explicit translation boundary — converts both ways | `snake_case` in → `camelCase` out; `camelCase` in → `snake_case` out before POST/write |

**Rules:**

- Backend Pydantic models use `snake_case` field names
- Persisted JSON files on disk use `snake_case` (they are written by the backend)
- JS store state, `decisionSnapshot`, `journeyBootstrap`, and all component-facing objects use `camelCase`
- `app/lib/adapters.js` is the only place that knows about `snake_case` — it converts on read and on write
- `app/lib/services.js` passes raw backend responses to adapters before touching field names
- Components never reference `snake_case` field names directly
- The adapter conversion is not optional — it applies to every field in every payload, including nested objects

**Concrete examples:**

```
API response (snake_case)         Adapter output (camelCase)
─────────────────────────         ──────────────────────────
snapshot_id          →            snapshotId
journey_status       →            journeyStatus
data_state           →            dataState
saved_at             →            savedAt
bootstrap_data_state →            bootstrapDataState
system_verdict       →            systemVerdict
user_decision        →            userDecision
execution_plan       →            executionPlan
why_interesting      →            whyInteresting
reasoning_summary    →            reasoningSummary
```

**On save (camelCase → snake_case):**

```
Store object (camelCase)          POST body (snake_case)
────────────────────────          ──────────────────────
snapshotId           →            snapshot_id
journeyStatus        →            journey_status
savedAt              →            saved_at
systemVerdict        →            system_verdict
userDecision         →            user_decision
executionPlan        →            execution_plan
bootstrapDataState   →            bootstrap_data_state
```

**Existing V1 code that uses camelCase in store/components is correct — do not change it.**
**Existing backend code that uses snake_case in Python models is correct — do not change it.**
**Only the adapters need updating if they currently pass snake_case field names into the store.**

---

## 4. Service layer rules

- Real endpoint first, demo fallback only when backend returns `unavailable` or is unreachable
- Demo fallback must set `data_state: "demo"` on the returned shape
- Save calls must confirm backend write success before resolving
- Never resolve a save promise on in-memory mutation alone
