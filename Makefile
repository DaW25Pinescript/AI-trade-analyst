# ─────────────────────────────────────────────────────────────────────────────
# AI Trade Analyst – Makefile
#
# Targets:
#   test-web    → Node test suite (browser app / gate / schema logic)
#   test-ai     → pytest suite (Python AI analyst pipeline)
#   test-all    → both suites in sequence
#   run-web     → static file server for app/ (http://localhost:8080/app/)
#   run-api     → FastAPI server on port 8000 (requires installed deps)
#   run-docker  → both services via Docker Compose
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: test-web test-ai test-all run-web run-api run-docker

# Run the Node test suite from the repo root.
# Covers gate/scoring determinism, schema enum stability, and metrics fixtures.
test-web:
	node --test tests/*.js

# Run the pytest suite for the Python AI analyst pipeline.
# Must cd into ai_analyst/ so pytest.ini (testpaths, asyncio_mode) is picked up.
test-ai:
	cd ai_analyst && pytest -q

# Run both suites — minimum bar before opening a PR.
test-all: test-web test-ai

# Serve the static app locally with Python's built-in HTTP server.
# Open http://localhost:8080/app/ once running.
run-web:
	python3 -m http.server 8080

# Start the FastAPI pipeline server on port 8000.
# Prerequisite: pip install -r ai_analyst/requirements.txt
run-api:
	python3 -m uvicorn ai_analyst.api.main:app --host 0.0.0.0 --port 8000

# Start both services (API + static) via Docker Compose.
run-docker:
	docker compose up
