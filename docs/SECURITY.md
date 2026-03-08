# Security & Deployment Hardening Guide

This document covers the steps required to deploy the AI Trade Analyst securely
beyond the default local development setup.

The default `docker compose up` configuration is **localhost-only** and is not
suitable for exposure to the public internet without the hardening steps below.

---

## 1. Always Run Behind HTTPS

The FastAPI server (`ai-analyst-api`) and the static app server (`app-static`)
are plain HTTP services. They must never be exposed directly on a public port.
Place a TLS-terminating reverse proxy in front of both.

**Recommended options:**

- **Caddy** (automatic HTTPS via Let's Encrypt — easiest):
  ```
  analyst.example.com {
      reverse_proxy localhost:8000
  }

  app.example.com {
      reverse_proxy localhost:8080
  }
  ```

- **nginx** with Certbot:
  ```nginx
  server {
      listen 443 ssl;
      server_name analyst.example.com;

      ssl_certificate     /etc/letsencrypt/live/analyst.example.com/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/analyst.example.com/privkey.pem;

      location / {
          proxy_pass http://127.0.0.1:8000;
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      }
  }

  server {
      listen 80;
      server_name analyst.example.com;
      return 301 https://$host$request_uri;
  }
  ```

Do not expose ports 8000 or 8080 through your firewall. Bind them to
`127.0.0.1` only in production:

```yaml
# docker-compose.yml (production override)
ports:
  - "127.0.0.1:8000:8000"
  - "127.0.0.1:8080:8080"
```

---

## 2. Configure CORS for Your Domain

By default the API allows requests from `http://localhost:8080` only.
For any non-local deployment set the `ALLOWED_ORIGINS` environment variable
to a comma-separated list of the exact origins your browser app is served from.

```bash
# .env or compose environment block
ALLOWED_ORIGINS=https://app.example.com
```

A wildcard (`*`) is never used — only the origins you list are permitted.
The API restricts methods to `GET` and `POST`.

---

## 3. Rate Limiting

### In-application rate limiter

The FastAPI server includes a sliding-window rate limiter on `POST /analyse`.
Defaults: **10 requests per 60 seconds per client IP**.

Override via environment variables:

```bash
RATE_LIMIT_REQUESTS=5   # max requests per window
RATE_LIMIT_WINDOW_S=60  # window size in seconds
```

The in-process limiter is suitable for single-instance deployments. It resets
when the process restarts and is **not shared across multiple workers**.

### nginx-level rate limiting (recommended for multi-worker or internet-facing)

Add this to your nginx config for a harder outer gate:

```nginx
limit_req_zone $binary_remote_addr zone=analyse_limit:10m rate=5r/m;

server {
    location /analyse {
        limit_req zone=analyse_limit burst=2 nodelay;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

---

## 4. API Key Storage

All LLM provider keys and data source keys are read from environment variables.
**Never commit API keys to the repository.**

Required keys are listed in `ai_analyst/.env.example`. Copy it to
`ai_analyst/.env` and fill in your values. This file is excluded from git
via `.gitignore`.

**MRO data source keys** (`FINNHUB_API_KEY`, `FRED_API_KEY`) follow the same
pattern — see `docs/api_key_setup.md`.

In production, prefer injecting secrets via your platform's secret manager
(AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault) rather than
writing a `.env` file on disk.

---

## 5. Per-Run Cost Ceiling

To prevent runaway LLM spend, set a hard per-run cost ceiling:

```bash
MAX_COST_PER_RUN_USD=0.50   # abort and log a warning if a single run exceeds $0.50
```

The server will complete the run but emit a warning in the logs when the
ceiling is breached. Set this conservatively for your expected usage.

---

## 6. Image Upload Size Limit

The default maximum per-image upload size is **5 MB**. Adjust via:

```bash
MAX_IMAGE_SIZE_MB=3   # reject images larger than 3 MB
```

Keep this as low as your chart screenshot workflow allows to reduce memory
pressure per request.

---

## 7. Static File Server in Production

`python -m http.server` (used by the `app-static` Docker service) is a
development convenience only — it has no authentication, no access controls,
and no TLS. For production, serve the `app/` directory with nginx:

```nginx
server {
    listen 443 ssl;
    server_name app.example.com;

    root /var/www/ai-trade-analyst;
    index app/index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

Copy the `app/` directory to your web root and remove the `app-static` Docker
service entirely.

---

## 8. Docker Container Hardening

Run the API container as a non-root user. Add to your `Dockerfile`:

```dockerfile
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser
```

Disable privilege escalation in your compose file:

```yaml
ai-analyst-api:
  security_opt:
    - no-new-privileges:true
  read_only: true
  tmpfs:
    - /tmp
```

---

## 9. Network Isolation

Restrict inter-service communication to an internal Docker network and expose
only the proxy port to the host:

```yaml
networks:
  internal:
    driver: bridge

services:
  ai-analyst-api:
    networks: [internal]
    ports: []   # not exposed directly

  nginx:
    networks: [internal]
    ports:
      - "443:443"
      - "80:80"
```

---

## 10. Vulnerability Scanning

`pip-audit` runs automatically in CI on every pull request for both
`ai_analyst` and `macro_risk_officer` dependency sets. To run locally:

```bash
pip install pip-audit
pip-audit -r ai_analyst/requirements.txt
pip-audit -r macro_risk_officer/requirements.txt
```

Fix or pin around any reported CVEs before merging.

---

## Reporting Vulnerabilities

To report a security vulnerability in this project, open an issue in the
repository and label it `security`. For sensitive disclosures, contact the
maintainer directly via the profile linked on the repository page.
