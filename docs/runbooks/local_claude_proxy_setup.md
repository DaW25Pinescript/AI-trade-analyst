# Local Claude Proxy Setup Guide

## 1. What This Is

CLIProxyAPI exposes your Claude Max subscription as an OpenAI-compatible local HTTP endpoint (`/v1/chat/completions`, `/v1/models`). This allows any tool that speaks the OpenAI API format — including LiteLLM — to route requests through your Claude Max account without requiring a separate API key or billing relationship.

## 2. Why It Exists

- **Personal use / local dev**: Run the AI Trade Analyst pipeline against Claude Max without accumulating per-token API charges.
- **Reduced API spend**: Claude Max is a flat-rate subscription; routing through the local proxy eliminates variable costs during development and testing.
- **Compatible tooling**: The OpenAI-compatible endpoint means LiteLLM, the OpenAI Python SDK, and other standard tools work without modification.

## 3. Required Local Setup

**Prerequisites:**
- Windows machine (CLIProxyAPI is a Windows executable)
- Claude Max subscription (active)
- Directory: `C:\cliproxyapi\`
- Executable: `C:\cliproxyapi\cli-proxy-api.exe`
- Config file: `C:\cliproxyapi\config.yaml`

Download CLIProxyAPI and place the executable in `C:\cliproxyapi\`. Create the config file as described below.

## 4. Recommended config.yaml

Create `C:\cliproxyapi\config.yaml` with the following known-good local-only configuration:

```yaml
host: "127.0.0.1"
port: 8317
auth-dir: "~/.cli-proxy-api"
api-keys: []
debug: false
remote-management:
  allow-remote: false
  secret-key: ""
  disable-control-panel: false
```

Key points:
- `host: "127.0.0.1"` ensures the proxy listens only on localhost — not exposed to the network.
- `port: 8317` is the default port used throughout this project's configuration.
- `api-keys: []` means no API key is required for local connections (safe because it's localhost-only).

## 5. Authentication

Before first use, authenticate with your Claude Max account:

```powershell
cd C:\cliproxyapi
.\cli-proxy-api.exe --claude-login
```

This opens a browser window for OAuth authentication. Complete the login flow. The auth tokens are stored in the directory specified by `auth-dir` (`~/.cli-proxy-api` by default).

## 6. Starting the Proxy

```powershell
cd C:\cliproxyapi
.\cli-proxy-api.exe
```

The proxy starts and listens on `http://127.0.0.1:8317`. You should see output confirming the server is running.

## 7. Testing /v1/models

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8317/v1/models" -Method GET
```

**curl:**
```bash
curl http://127.0.0.1:8317/v1/models
```

Expected: A JSON response listing available Claude models.

## 8. Testing /v1/chat/completions

**PowerShell:**
```powershell
$body = @{
    model = "claude-sonnet-4-5-20250929"
    messages = @(
        @{ role = "user"; content = "Say hello in one sentence." }
    )
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Uri "http://127.0.0.1:8317/v1/chat/completions" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

**curl:**
```bash
curl http://127.0.0.1:8317/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5-20250929",
    "messages": [{"role": "user", "content": "Say hello in one sentence."}]
  }'
```

Expected: A JSON response with the model's reply.

## 9. Python OpenAI SDK Verification

Minimal working snippet to verify the proxy works from Python:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8317/v1",
    api_key="not-needed",
)

response = client.chat.completions.create(
    model="claude-sonnet-4-5-20250929",
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)

print(response.choices[0].message.content)
```

If this prints a response, the proxy is working correctly and the AI Trade Analyst pipeline can route through it.
