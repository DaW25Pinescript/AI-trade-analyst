# AI Trade Analyst — Production Security Checklist

Post-Security/API Hardening phase. Describes what the system does after this phase lands.

## 1. TLS Termination

- [ ] TLS must be terminated before traffic reaches the FastAPI process (reverse proxy, load balancer, or cloud ingress).
- The application does not terminate TLS itself. In production (`ENVIRONMENT=production`), HSTS headers are added and HTTP origins are rejected from CORS.

## 2. CORS Origin Configuration

- **Env var:** `ALLOWED_ORIGINS` (comma-separated list of allowed origins)
- **Default:** `http://localhost:8080, http://127.0.0.1:8080` (development only)
- **Production:** Set to your HTTPS domain(s). HTTP origins are automatically stripped when `ENVIRONMENT=production`.
- [ ] Set `ALLOWED_ORIGINS` to production HTTPS origins before deployment.

## 3. API Key Authentication

- **Env var:** `AI_ANALYST_API_KEY`
- **Behavior:** If unset or empty, all `/analyse` and `/analyse/stream` requests are rejected 401.
- **Header:** `X-API-Key: <value>`
- **Local development:** Set `AI_ANALYST_API_KEY=dev-key` (or any non-empty value) in `.env`.
- **Production:** Use a strong random secret. Rotate by changing the env var and restarting.
- [ ] Set `AI_ANALYST_API_KEY` to a strong secret before deployment.
- [ ] Rotate the key periodically and after any suspected compromise.

## 4. Rate Limiting

- **Env vars:** `RATE_LIMIT_REQUESTS` (default: 10), `RATE_LIMIT_WINDOW_S` (default: 60)
- In-process sliding-window limiter per client IP. Returns 429 when exceeded.
- Suitable for single-instance deployment. For multi-instance, add external rate limiting (e.g. at the load balancer or API gateway).
- [ ] Tune `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_S` for expected production load.

## 5. Timeout Configuration

| Parameter | Env var | Default | Protects |
|---|---|---|---|
| Graph execution | `GRAPH_TIMEOUT_SECONDS` | 120s | Prevents indefinite analysis hangs. Returns 504. |
| LLM call (analyst module) | `LLM_CALL_TIMEOUT_S` | 60s | Prevents provider stalls in `call_llm()`. |
| LLM call (graph pipeline) | Hardcoded 45s | 45s | Already hardened in `acompletion_with_retry()`. |

- [ ] Verify timeout values are appropriate for your provider latency profile.

## 6. Request Size Limits

| Limit | Env var | Default | Scope |
|---|---|---|---|
| Global body size | `MAX_REQUEST_BODY_MB` | 10 MB | All requests (Content-Length check). Returns 413. |
| Per-image upload | `MAX_IMAGE_SIZE_MB` | 5 MB | Each chart upload. Streaming read with magic-byte validation. |
| Screenshot count | Hardcoded | 4 (3 clean + 1 overlay) | Pydantic model validation. |

- [ ] Adjust `MAX_REQUEST_BODY_MB` if larger payloads are needed.

## 7. LLM Provider Spend Limits

- **Env var:** `MAX_COST_PER_RUN_USD` (optional)
- When set, logs a warning if a pipeline run exceeds the ceiling. Does not block — monitoring only.
- [ ] Configure provider-side spend limits and budget caps (OpenAI, Anthropic, etc.) for production.
- [ ] Set `MAX_COST_PER_RUN_USD` as a per-run warning threshold.

## 8. Logging and Secret Masking

- All logged errors pass through `_mask_secrets()` which redacts patterns matching API keys, bearer tokens, and `*_API_KEY=` values.
- Client-facing error responses are sanitised: RuntimeError and generic exceptions return safe generic messages. Internal detail is preserved in server logs only.
- [ ] Verify log output does not contain secrets after deployment by inspecting sample log entries.

## 9. Security Headers

Applied to all responses via `SecurityHeadersMiddleware`:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` (production only)

## 10. Input Sanitisation

All user-provided text fields (`instrument`, `session`, `market_regime`, `news_risk`, `no_trade_windows`, `open_positions`) are sanitised before reaching LLM prompts. Validation failures return 422.
