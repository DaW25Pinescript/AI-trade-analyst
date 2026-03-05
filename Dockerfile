FROM python:3.11-slim

WORKDIR /workspace

# Install Python dependencies at build time (not at container start).
# Leverage layer caching: requirements are re-installed only when the file changes.
COPY ai_analyst/requirements.txt ai_analyst/requirements.txt
RUN pip install --no-cache-dir -r ai_analyst/requirements.txt

# Copy the full repo. In dev mode the volume mount in docker-compose.yml
# overlays this with the live source tree.
COPY . .

# ── Production hardening: run as non-root ────────────────────────────────────
# The appuser has no home directory, no login shell, and no sudo access.
# In dev mode the volume mount may override ownership, which is fine —
# the non-root constraint is enforced in docker-compose.prod.yml.
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /workspace
USER appuser

CMD ["uvicorn", "ai_analyst.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
