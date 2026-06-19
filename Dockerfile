# ──────────────────────────────────────────────────────────────────────────────
# Elsevier Paper Alert Agent — Dockerfile
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Security: run as non-root
RUN useradd --create-home --shell /bin/bash agent
WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=agent:agent . .

# Create runtime directories
RUN mkdir -p logs && chown agent:agent logs

USER agent

# SQLite database and logs persist in /app (mount a volume in production)
VOLUME ["/app/logs", "/app/papers.db"]

CMD ["python", "main.py"]
