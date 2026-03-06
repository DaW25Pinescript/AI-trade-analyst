# AI Trade Analyst

![AI Trade Analyst](docs/assets/ai-trade-analyst-banner.svg)

AI Trade Analyst is a data-first AI trading analysis system designed to assist discretionary traders with structured trade planning, multi-model analysis, and post-trade review.

The system combines:

- A structured browser workflow for discretionary trading decisions
- A multi-model AI analysis engine
- A canonical market data pipeline used as the primary analytical substrate

Unlike screenshot-driven AI trading tools, AI Trade Analyst prioritizes structured numerical market data. Chart screenshots remain optional supporting evidence, not the system’s core input.

## System Architecture

AI Trade Analyst is organized into three cooperating layers.

```text
Market Data Layer
        │
        ▼
AI Analysis Layer
        │
        ▼
Trader Workflow Layer
```

### Market Data Layer

Maintains canonical price data and derived timeframes.

Responsibilities:

- Tick ingestion
- Candle generation
- Derived timeframe generation
- Gap detection
- Incremental updates
- Market data packaging for AI agents

### AI Analysis Layer

Runs multi-persona AI analysis over structured market state.

Responsibilities:

- AI model orchestration
- Persona-based analysis
- Arbiter decision synthesis
- Macro context injection
- Trade verdict generation

### Trader Workflow Layer

Provides the human interface for structured trade planning and review.

Responsibilities:

- Ticket generation
- Gate evaluation
- Structured prompts
- AI analysis bridge
- Post-trade review (AAR)

## Data-First Design Doctrine

Earlier versions of AI Trade Analyst centered on chart screenshots as the primary input to AI analysis.

This repository now formally adopts a data-first architecture.

### Primary input

Structured market data:

- OHLCV candles
- Multi-timeframe price history
- Derived indicators
- Computed market features

### Secondary input

Trader context:

- Trade thesis
- Session
- Risk parameters
- Setup classification

### Supporting evidence

Chart screenshots:

- Optional confirmation
- Visual sanity check
- Discretionary annotation
- Audit artifact

Screenshots are therefore evidence, not the analytical substrate.

## Project Purpose

AI Trade Analyst exists to:

- Standardize discretionary trade planning
- Preserve a structured lifecycle for trade decisions
- Combine human judgment with multi-model AI analysis
- Provide repeatable analysis workflows
- Create auditable trade decision records

## Current Status

### Browser App

The repository ships a runnable static web application under:

```text
app/
```

Capabilities:

- Structured ticket workflow
- Gate evaluation
- AI analysis integration
- Verdict display
- Export/import backups
- After-action review (AAR)

### Python AI Analyst

Location:

```text
ai_analyst/
```

Current version: v2.1

Capabilities:

- Multi-model analysis
- Multi-persona reasoning
- Arbiter synthesis
- Manual / hybrid / automated execution modes
- CLI execution and replay

Model routing is centralized under:

```text
llm_router/
```

### Macro Risk Officer

Location:

```text
macro_risk_officer/
```

Status: complete

Features:

- Macro regime classification
- Volatility bias assessment
- Cross-asset pressure context
- SQLite outcome tracking
- KPI telemetry

The MRO is advisory only.

It provides macro context to the Arbiter but never generates trade signals or overrides price-structure conclusions.

## Test Suite Status

As of 2026-03-06:

- 703+ tests passing
- 0 failing

Breakdown:

| Component | Tests |
| --- | --- |
| Browser app | 234 JS |
| AI analyst | 469 Python |
| Macro Risk Officer | 153 |
| Intentional skips | 16 |

## Directory Map

```text
.
├── ai_analyst/
│   ├── cli.py
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── api/
│   ├── core/
│   ├── graph/
│   ├── models/
│   ├── output/
│   ├── prompt_library/
│   ├── data/
│   └── tests/
│
├── app/
│   ├── index.html
│   ├── scripts/
│   │   ├── exports/
│   │   ├── generators/
│   │   ├── schema/
│   │   ├── state/
│   │   └── ui/
│   ├── styles/
│   └── releases/
│
├── docs/
│   ├── schema/
│   ├── scoring/
│   ├── architecture/
│   └── V3_*.md
│
├── macro_risk_officer/
│   ├── core/
│   ├── ingestion/
│   ├── config/
│   ├── history/
│   ├── data/
│   └── tests/
│
├── examples/
├── tests/
├── tooling/
├── run_ai_trade_analyst_python.bat
├── LICENSE
└── README.md
```

## Static Browser App

### Running Locally

#### Option A — Python

```bash
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000/app/
```

#### Option B — Node

```bash
npx serve .
```

Navigate to `/app`.

#### Option C — Windows Launcher

Double click:

```text
run_ai_trade_analyst_python.bat
```

#### Option D — Docker

```bash
docker compose up
```

Open:

```text
http://localhost:8080/app/
```

## Testing

### Browser Tests

```bash
node --test tests/*.js
```

### AI Analyst Tests

```bash
pytest -q ai_analyst/tests
```

### Full Test Suite

```bash
make test-all
```

## Makefile Reference

| Command | Purpose |
| --- | --- |
| make test-web | run browser tests |
| make test-ai | run AI analyst tests |
| make test-all | run both suites |
| make run-web | start static server |
| make run-api | run FastAPI interface |
| make run-docker | run full stack |

## Python AI Analyst

### Setup

```bash
pip install -r ai_analyst/requirements.txt
```

Create:

```text
ai_analyst/.env
```

```dotenv
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
```

Missing keys automatically trigger manual mode.

### Execution Modes

| Mode | Behavior |
| --- | --- |
| manual | generates prompt packs for external AI |
| hybrid | uses available API keys |
| automated | full API execution |

### CLI Commands

#### Check model availability

```bash
python ai_analyst/cli.py status
```

#### Run analysis

```bash
python ai_analyst/cli.py run \
  --instrument XAUUSD \
  --session NY \
  --mode hybrid \
  --d1 charts/d1.png \
  --h4 charts/h4.png \
  --h1 charts/h1.png \
  --m15 charts/m15.png
```

#### Arbiter synthesis

```bash
python ai_analyst/cli.py arbiter --run-id <run-id>
```

#### List history

```bash
python ai_analyst/cli.py history
```

#### Replay run

```bash
python ai_analyst/cli.py replay --run-id <run-id>
```

Useful for prompt development and regression testing.

## Analyst Personas

Each run dispatches four analysts.

### DEFAULT_ANALYST

Balanced multi-timeframe analysis.

### RISK_OFFICER

Focuses on invalidation and downside.

### PROSECUTOR

Attempts to disprove the trade thesis.

### ICT_PURIST

ICT / Smart Money Concepts specialist.

## Arbiter Node

The Arbiter synthesizes analyst outputs into:

`FinalVerdict`

Includes:

- Trade decision
- Approved setups
- Confidence score
- No-trade conditions
- Reasoning summary

## Market Data Pipeline (New)

AI Trade Analyst now includes a Market Data Officer responsible for maintaining canonical price data.

Responsibilities:

- Tick ingestion
- Tick → 1m candle generation
- Derived timeframe generation
- Gap detection
- Incremental updates
- AI-ready data packaging

Example structure:

```text
market_data/
   XAUUSD/
      canonical/
         1m.parquet

      derived/
         5m.parquet
         15m.parquet
         1h.parquet
         4h.parquet
         1d.parquet

      reports/
         gap_report.json
```

This pipeline allows the AI system to reason over true numerical market state instead of visual inference from screenshots.

## V3 Browser App Phase Plan

`G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8 → G9 → G10 → G11 → G12`

All phases are now complete.

## Import / Export Schema Contracts

Ticket and AAR payloads are governed by JSON schemas.

Location:

```text
docs/schema/
```

Compatibility rules:

- Additive changes preferred
- Breaking changes require version bump

Migrations implemented in:

```text
app/scripts/state/migrations.js
```

## License

MIT License.

## Contribution Philosophy

This project prioritizes:

- Deterministic workflows
- Schema-backed state
- Auditable trade decisions
- Modular AI orchestration
- Reproducible analysis pipelines

Future contributors should assume that structured market data is the primary analytical substrate, with visual chart artifacts treated as optional supporting context.
