# CLAUDE.md — AI Trade Analyst

## Local Claude Max Proxy + Task-Based Model Routing

### Repo-Level Operating Guide for Claude Code

---

## How to read this document

This is the authoritative operating guide for Claude Code implementing the local Claude Max proxy mode, Claude-first task routing, and chart-safe two-step flow in this repo.

Think of this like a cockpit checklist — work through the numbered passes in order. Do not skip Phase 0. Do not start writing files until the audit is complete and mapped.

---

## Architecture

```
AI Trade Analyst pipeline
        │
        ▼
  router.resolve(task_type)
        │
        ▼
  llm_routing.yaml
  (model + base_url resolved)
        │
        ▼
  litellm.completion(
      model=...,
      api_base="http://127.0.0.1:8317/v1",
      api_key="not-needed",
      ...
  )
        │
        ▼
  CLIProxyAPI (local)
        │
        ▼
  Claude Max
```

The router sits between the application and LiteLLM. LiteLLM remains untouched. The proxy is transparent to the application layer.

## Key module locations

| Component | Path |
|---|---|
| Router module | `ai_analyst/llm_router/` |
| Task type constants | `ai_analyst/llm_router/task_types.py` |
| Router interface | `ai_analyst/llm_router/router.py` |
| Config loader | `ai_analyst/llm_router/config_loader.py` |
| Routing config | `config/llm_routing.yaml` (gitignored) |
| Example config | `config/llm_routing.example.yaml` (committed) |
| Chart two-step flow | `ai_analyst/core/chart_two_step.py` |
| Proxy setup docs | `docs/local_claude_proxy_setup.md` |
| Routing docs | `docs/model_routing.md` |
| Helper scripts | `scripts/*.ps1` |

## Task routing reference

| Task | Primary Model | Rationale |
|---|---|---|
| `chart_extract` | Opus | Higher vision fidelity; image ambiguity is highest here |
| `chart_interpret` | Sonnet | Text reasoning from structured input; Opus not needed |
| `analyst_reasoning` | Sonnet | Sufficient for text-based analysis |
| `arbiter_decision` | Sonnet | Sufficient for structured arbitration |
| `json_repair` | Sonnet | Lightweight repair task |

## Constraints (hard rules)

- **No broad refactors** — touch only files required for each pass
- **No new dependencies without approval** — stop and ask first
- **No silent fallbacks** — every fallback must produce a WARNING log
- **No magic strings** — all task types referenced via `task_types.py` constants
- **Router is the only YAML consumer** — no other module parses `llm_routing.yaml`
- **Preserve existing conventions** — match import style, logging, file naming

## Quick start

```bash
# Smoke test the router
python -c "
from ai_analyst.llm_router import router
r = router.resolve('chart_extract')
assert 'opus' in r['model']
r2 = router.resolve('analyst_reasoning')
assert 'sonnet' in r2['model']
print('Router smoke test passed.')
"
```

This document is the source of truth for this implementation.
