# Local Development — Docker Compose

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose plugin v2)
- API keys for the AI models used by the pipeline

## API Key Setup

Copy the example env file and fill in your keys:

```bash
cp ai_analyst/.env.example ai_analyst/.env
# Edit ai_analyst/.env with your actual API keys
```

The API container loads `ai_analyst/.env` automatically via `env_file` in `docker-compose.yml`.

## Starting the Stack

```bash
# First start — builds the API image (pip install runs here, not at startup)
docker compose up --build

# Subsequent starts — skips rebuild if requirements haven't changed
docker compose up

# Wait until both containers are healthy before returning
docker compose up --wait

# Force a rebuild (e.g. after adding a new dependency to requirements.txt)
docker compose up --build
```

## Service URLs

| Service | URL | Notes |
|---------|-----|-------|
| Browser app | http://localhost:8080/app/ | Trade ticket UI |
| FastAPI docs | http://localhost:8000/docs | Interactive Swagger UI |
| Health check | http://localhost:8000/health | `{"status":"ok","version":"..."}` |

The browser app is pre-configured with `http://localhost:8000` as the analysis server URL.

## Stopping

```bash
docker compose down
```

## Rebuilding After Dependency Changes

If you add a package to `ai_analyst/requirements.txt`:

```bash
docker compose up --build
```

## Logs

```bash
# Stream all service logs
docker compose logs -f

# API service only
docker compose logs -f ai-analyst-api
```

## Notes

- **CORS**: The API allows cross-origin requests from `localhost:8080` so the browser app can reach `localhost:8000` without preflight errors.
- **Hot reload**: The repo root is volume-mounted into both containers, so Python source changes are reflected immediately when running with `--reload` (add `--reload` to the uvicorn command in `docker-compose.yml` for development).
- **Startup time**: The first `docker compose up --build` installs all Python dependencies at image build time. Subsequent starts take only a few seconds.
