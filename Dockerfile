FROM python:3.11-slim

WORKDIR /workspace

# Install Python dependencies at build time (not at container start).
# Leverage layer caching: requirements are re-installed only when the file changes.
COPY ai_analyst/requirements.txt ai_analyst/requirements.txt
RUN pip install --no-cache-dir -r ai_analyst/requirements.txt

# Copy the full repo. In dev mode the volume mount in docker-compose.yml
# overlays this with the live source tree.
COPY . .

CMD ["uvicorn", "ai_analyst.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
