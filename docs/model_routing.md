# Model Routing Guide

## 1. Why Tasks Route to Different Models

Not all tasks in the AI Trade Analyst pipeline have the same requirements. Some tasks require high vision fidelity (chart reading), while others are pure text reasoning that a lighter model handles equally well. Routing tasks to the right model optimises for:

- **Accuracy**: Vision-heavy tasks get the most capable vision model.
- **Cost efficiency**: Text-only reasoning tasks use a sufficient (not maximal) model.
- **Latency**: Lighter models respond faster for tasks that don't need Opus-level capability.

## 2. Task Type Reference

| Task Type | Primary Model | Rationale |
|---|---|---|
| `chart_extract` | `claude-opus-4-20250514` | Higher vision fidelity; image ambiguity is highest here. Extraction accuracy is critical — hallucinated values propagate downstream. |
| `chart_interpret` | `claude-sonnet-4-5-20250929` | Text reasoning from structured input; Opus not needed since input is already extracted text. |
| `analyst_reasoning` | `claude-sonnet-4-5-20250929` | Sufficient for text-based analysis of price action and market structure. |
| `arbiter_decision` | `claude-sonnet-4-5-20250929` | Sufficient for structured arbitration from JSON evidence objects. |
| `json_repair` | `claude-sonnet-4-5-20250929` | Lightweight repair task; Opus would be overkill. |

All task types are defined as constants in `ai_analyst/llm_router/task_types.py`. No magic strings — always import from there.

## 3. How to Change Models

Edit `config/llm_routing.yaml` (copy from `config/llm_routing.example.yaml` if it doesn't exist):

```yaml
task_routing:
  chart_extract:
    primary_model: "claude-opus-4-20250514"      # ← change this
    fallback_model: "claude-sonnet-4-5-20250929"  # ← and/or this
    retries: 1
```

**No code changes required.** The router reads the YAML at startup and resolves models dynamically.

To change the proxy base URL, either edit the YAML:

```yaml
llm_backend:
  base_url: "http://127.0.0.1:8317/v1"  # ← change this
```

Or set the environment variable:

```bash
export CLAUDE_PROXY_BASE_URL="http://your-host:port/v1"
```

The env var takes precedence over the YAML value.

## 3b. Analyst Roster

The analyst fan-out roster (which models + personas are used for parallel analysis) is also defined in `llm_routing.yaml`:

```yaml
analyst_roster:
  - model: "gpt-4o"
    persona: "default_analyst"
  - model: "claude-sonnet-4-6"
    persona: "risk_officer"
  - model: "gemini/gemini-1.5-pro"
    persona: "prosecutor"
  - model: "xai/grok-vision-beta"
    persona: "ict_purist"
```

To change the analyst models, edit this section. The persona values must match `PersonaType` enum values in `ai_analyst/models/persona.py`. If the `analyst_roster` key is absent, hardcoded defaults matching the above are used.

## 4. Why Chart Work Is Split Into Two Phases

Chart analysis is split into **extract** and **interpret** — two separate LLM calls that are never collapsed into one. The analogy:

- **`chart_extract`** = the witness gives only observable facts under oath ("I saw X, Y, Z")
- **`chart_interpret`** = the analyst reasons from those facts ("therefore the bias is...")

**Why this matters:**

1. **Hallucination reduction**: Vision models sometimes invent price levels or misread annotations. By forcing the extraction step to report only observable facts with explicit uncertainty markers ("cannot determine", "partially visible"), hallucinated values are caught before they propagate into trading conclusions.

2. **Auditability**: The extraction output is a structured JSON record of exactly what the model claims to have seen. This can be reviewed independently of the interpretation, making it possible to identify whether errors originate from misreading the chart or from flawed reasoning.

3. **Model specialisation**: Extraction uses Opus (best vision fidelity) while interpretation uses Sonnet (sufficient for text reasoning). This avoids paying the Opus premium for work that doesn't need it.

## 5. Fallback Behaviour

### What triggers a fallback

When the primary model fails after the configured number of retries (default: 1 retry = 2 total attempts), the router automatically falls back to the secondary model defined in `llm_routing.yaml`.

### How it is logged

Fallbacks are **never silent**. Every fallback produces a `WARNING`-level log entry:

```
WARNING [router] chart_extract falling back from claude-opus-4-20250514 to claude-sonnet-4-5-20250929 after 2 failed attempt(s)
```

Individual retry failures are also logged at WARNING:

```
WARNING [router] chart_extract primary model claude-opus-4-20250514 failed (attempt 1/2): <error details>
```

### Where to find logs

Logs are emitted through Python's standard `logging` module under the `ai_analyst.llm_router.router` logger name. They appear in:

- Console output (if logging is configured to output to stderr/stdout)
- The application's log files (if file logging is configured)
- The run-specific `usage.jsonl` file in the run output directory (for metered calls)

### Fallback chain

The current fallback strategy is intentionally simple:

1. Try primary model (with retries)
2. Try fallback model (single attempt)
3. If both fail, raise an error

There is no multi-provider cascade in this phase. Both primary and fallback models route through the same local Claude proxy.
