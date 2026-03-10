# Secrets Manager Integration Guide

This document describes how to inject API keys and sensitive configuration
into the AI Trade Analyst without using `.env` files on disk.

All configuration is read from environment variables — no code changes are
needed regardless of which secret injection method you use.

---

## Required Secrets

| Variable | Purpose | Required |
|----------|---------|----------|
| `ANTHROPIC_API_KEY` | Claude Sonnet / Haiku | Yes (primary analyst) |
| `OPENAI_API_KEY` | GPT-4o / GPT-4o-mini | Yes (primary analyst) |
| `GOOGLE_API_KEY` | Gemini 1.5 Pro | Optional |
| `XAI_API_KEY` | Grok Vision / Grok-3 | Optional |
| `FINNHUB_API_KEY` | MRO event calendar | Optional |
| `FRED_API_KEY` | MRO macro series | Optional |
| `ALLOWED_ORIGINS` | CORS whitelist | Production only |

---

## AWS Secrets Manager

### Store the secret

```bash
aws secretsmanager create-secret \
  --name ai-trade-analyst/prod \
  --secret-string '{
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "OPENAI_API_KEY": "sk-...",
    "GOOGLE_API_KEY": "...",
    "XAI_API_KEY": "...",
    "FINNHUB_API_KEY": "...",
    "FRED_API_KEY": "...",
    "ALLOWED_ORIGINS": "https://app.example.com"
  }'
```

### ECS Task Definition (recommended)

Reference the secret directly in your ECS task definition — no `.env` file needed:

```json
{
  "containerDefinitions": [{
    "name": "ai-analyst-api",
    "secrets": [
      {
        "name": "ANTHROPIC_API_KEY",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123456:secret:ai-trade-analyst/prod:ANTHROPIC_API_KEY::"
      },
      {
        "name": "OPENAI_API_KEY",
        "valueFrom": "arn:aws:secretsmanager:us-east-1:123456:secret:ai-trade-analyst/prod:OPENAI_API_KEY::"
      }
    ]
  }]
}
```

### Docker entrypoint injection

For non-ECS Docker deployments, fetch at container start:

```bash
#!/bin/bash
# entrypoint.sh — fetch secrets before starting the app
eval "$(aws secretsmanager get-secret-value \
  --secret-id ai-trade-analyst/prod \
  --query SecretString --output text \
  | python3 -c 'import sys,json; [print(f"export {k}={v}") for k,v in json.loads(sys.stdin.read()).items()]')"

exec uvicorn ai_analyst.api.main:app --host 0.0.0.0 --port 8000
```

---

## GCP Secret Manager

### Store the secret

```bash
echo -n '{"ANTHROPIC_API_KEY":"sk-ant-...","OPENAI_API_KEY":"sk-..."}' \
  | gcloud secrets create ai-trade-analyst --data-file=-
```

### Cloud Run

Mount as an environment variable in your Cloud Run service:

```bash
gcloud run deploy ai-analyst-api \
  --set-secrets="ANTHROPIC_API_KEY=ai-trade-analyst:latest" \
  --set-secrets="OPENAI_API_KEY=ai-trade-analyst:latest"
```

### GKE Secret Volume

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: ai-analyst-api
      envFrom:
        - secretRef:
            name: ai-trade-analyst
```

---

## HashiCorp Vault

### Store the secret

```bash
vault kv put secret/ai-trade-analyst \
  ANTHROPIC_API_KEY="sk-ant-..." \
  OPENAI_API_KEY="sk-..." \
  GOOGLE_API_KEY="..." \
  XAI_API_KEY="..."
```

### Vault Agent Sidecar (Kubernetes)

Use the Vault Agent Injector to mount secrets as environment variables:

```yaml
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "ai-trade-analyst"
  vault.hashicorp.com/agent-inject-secret-env: "secret/ai-trade-analyst"
  vault.hashicorp.com/agent-inject-template-env: |
    {{- with secret "secret/ai-trade-analyst" -}}
    {{ range $k, $v := .Data.data }}
    export {{ $k }}={{ $v }}
    {{ end }}
    {{- end -}}
```

### Docker entrypoint injection

```bash
#!/bin/bash
eval "$(vault kv get -format=json secret/ai-trade-analyst \
  | python3 -c 'import sys,json; d=json.loads(sys.stdin.read())["data"]["data"]; [print(f"export {k}={v}") for k,v in d.items()]')"

exec uvicorn ai_analyst.api.main:app --host 0.0.0.0 --port 8000
```

---

## Key Rotation

All LLM provider keys should be rotated regularly (recommended: monthly).

1. Generate a new key from the provider dashboard.
2. Update the secret in your secret manager.
3. Restart or redeploy the service — the new key takes effect immediately.
4. Revoke the old key from the provider dashboard.

The application reads keys at startup — no hot-reload mechanism exists.
A zero-downtime rotation strategy is to run two replicas, update the secret,
then perform a rolling restart.

---

## Verifying Secret Injection

After deployment, confirm secrets are injected correctly:

```bash
# Check that the health endpoint responds (confirms app started with valid config)
curl -s https://your-domain.com/health | jq .

# Check logs for any missing-key warnings
docker logs ai-analyst-api 2>&1 | grep -i "key\|secret\|auth"
```

The application logs a warning at startup for each missing optional key
and raises an error if no analyst keys are configured at all.
