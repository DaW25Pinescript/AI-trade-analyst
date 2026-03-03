# Claude Code FastAPI Wrapper (Experimental)

Private local wrapper for `claude -p` with an OpenAI-compatible `POST /v1/chat/completions` shape.

## Run

```bash
cd services/claude_code_api
export CLAUDE_CODE_API_KEY=dev-only-key
uvicorn app:app --host 127.0.0.1 --port 8787
```

## Security

- Binds localhost by default (`127.0.0.1`)
- Requires `X-API-Key` header matching `CLAUDE_CODE_API_KEY`

## Endpoints

- `GET /health`
- `POST /v1/chat/completions`
