# AI Trade Analyst — Setup Guide

## Prerequisites

- Python 3.11+
- Git

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/DaW25Pinescript/AI-trade-analyst.git
cd AI-trade-analyst

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Install in editable mode with dev dependencies
pip install -e ".[dev,mdo,mro]"

# 4. Verify the install
python -c "import ai_analyst, analyst, market_data_officer, macro_risk_officer; print('All packages OK')"

# 5. Run the full test suite
pytest
```

## Package Structure

The repo contains four Python packages, all declared in one `pyproject.toml`:

| Package | Purpose |
|---------|---------|
| `ai_analyst` | LLM execution graph, API server, CLI |
| `analyst` | Trade analysis orchestration (pre-filter, personas, arbiter) |
| `market_data_officer` | Market data feed, structure analysis, officer contracts |
| `macro_risk_officer` | Macro event reasoning engine |

All cross-package imports use fully-qualified paths (e.g., `from market_data_officer.officer.contracts import MarketPacketV2`).

## Running Tests

```bash
# All tests (combined)
pytest

# Per-package
pytest ai_analyst/tests
pytest market_data_officer/tests
pytest macro_risk_officer/tests
pytest tests                     # Root integration tests
```

## Running the API Server

```bash
uvicorn ai_analyst.api.main:app --reload --host 127.0.0.1 --port 8000
```

## Optional Dependencies

| Extra | Installs | Used by |
|-------|----------|---------|
| `dev` | pytest, pytest-asyncio, pytest-cov | Test suite |
| `mdo` | apscheduler | MDO scheduler |
| `mro` | yfinance, modal | MRO data ingestion |

## Windows Users

Double-click `RUN.bat` from the repo root for automated bootstrap (creates venv, installs deps, starts backend + UI).
