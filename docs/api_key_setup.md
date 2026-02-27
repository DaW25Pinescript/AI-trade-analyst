## AI Analyst — API Key Setup Guide

This guide explains how to configure API keys for the `ai_analyst` pipeline so the CLI can run in **hybrid** and **automated** modes. Manual mode does **not** require any keys.

The Python package expects keys to be provided via environment variables, typically loaded from a local `.env` file in the `ai_analyst/` directory.

> **Note:** You can use **manual mode** (`--mode manual`) without setting any keys. Hybrid/automated modes simply skip providers that do not have keys configured.

---

## 1. Locate the `.env.example` file

Inside the `ai_analyst/` directory you will find:

- `.env.example` – template listing all supported provider variables

Copy it to `.env`:

```bash
cd ai_analyst
cp .env.example .env   # On Windows PowerShell: copy .env.example .env
```

The `cli.py` module automatically loads `.env` from this directory:

- `from dotenv import load_dotenv`
- `load_dotenv(Path(__file__).parent / ".env")`

---

## 2. Supported providers and env vars

The exact set of variables is defined in `core/api_key_manager.py`, but the typical pattern is:

- `OPENAI_API_KEY` – for OpenAI / GPT‑4o
- `ANTHROPIC_API_KEY` – for Claude
- `GOOGLE_API_KEY` – for Gemini
- `XAI_API_KEY` – for Grok

Each env var maps to one or more concrete model identifiers used by the pipeline (see `graph/analyst_nodes.py` and `core/api_key_manager.py`).

Example `.env` contents:

```dotenv
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
XAI_API_KEY=...
```

You can leave any provider blank; the system will treat that analyst slot as **manual** in hybrid mode.

---

## 3. Verifying keys with `cli status`

After editing `.env`, run:

```bash
cd ai_analyst
python cli.py status
```

The CLI will print:

- Which env vars are set (`✅`) vs missing (`❌`)
- The **recommended mode**:
  - `manual` – no keys; all analysts will be manual
  - `hybrid` – some keys; a mix of API and manual analysts
  - `automated` – all analysts have API models available

You do **not** have to manually choose `hybrid` vs `manual` in most cases:

- If you pass `--mode hybrid` and no keys are present, the CLI downgrades to `manual` and prints an info message.

---

## 4. Running the CLI with keys configured

### Manual mode (no keys required)

```bash
cd ai_analyst
python cli.py run \
  --instrument XAUUSD \
  --session NY \
  --mode manual \
  --h4 charts/h4.png \
  --h1 charts/h1.png \
  --m15 charts/m15.png \
  --m5 charts/m5.png
```

This generates a **Manual Prompt Pack** in:

- `ai_analyst/output/runs/{run_id}/manual_prompts/`

Follow the `README.txt` instructions in that folder, then run:

```bash
python cli.py arbiter --run-id <run_id>
```

### Hybrid mode (some keys present)

```bash
python cli.py run \
  --instrument XAUUSD \
  --session NY \
  --mode hybrid \
  --h4 charts/h4.png \
  --h1 charts/h1.png
```

- Analysts backed by providers with configured keys run via API.
- Remaining analysts fall back to manual prompts in the prompt pack.

### Automated mode (all keys present)

```bash
python cli.py run \
  --instrument XAUUSD \
  --session NY \
  --mode automated \
  --h4 charts/h4.png \
  --h1 charts/h1.png \
  --m15 charts/m15.png
```

All analysts run via API. The Final Verdict is produced immediately; no prompt pack is generated.

---

## 5. Troubleshooting

- **`python cli.py status` shows all ❌**  
  - Confirm you created `.env` in the `ai_analyst/` directory (same folder as `cli.py`).  
  - Make sure variable names exactly match those in `.env.example`.  
  - If running from an IDE, ensure the working directory is `ai_analyst/`.

- **Integration tests complain about missing keys**  
  - The v1.3 CLI integration tests are written to pass even with zero keys configured by exercising **manual mode** and stubbed API calls (via `litellm` monkeypatching).  
  - For real API calls during local experiments, configure keys as above and re-run `python cli.py run ...`.

- **Rate limits or provider errors**  
  - Use `--mode hybrid` so that some analysts can still be run manually when a provider is flaky.  
  - The pipeline treats missing/failed analysts as warnings, but enforces a minimum of two valid analyst outputs before the arbiter runs.

