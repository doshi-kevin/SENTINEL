# syntax=docker/dockerfile:1.6
#
# Sentinel-Z — single-stage runtime image
# Builds the Python detection backend + FastAPI server.
# The frontend (Next.js) lives in frontend/ and has its own Dockerfile.
#
# Usage:
#   docker build -t sentinel-z:latest .
#   docker run -p 8000:8000 -v $(pwd)/data:/app/data sentinel-z:latest

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for native wheels (scikit-learn / numpy avoid heavy compilation
# when --prefer-binary; we still need libgomp1 at runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libgomp1 \
      git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching.
COPY pyproject.toml ./
COPY README.md ./

RUN pip install --upgrade pip setuptools wheel \
 && pip install --prefer-binary -e ".[ml,viz]"

# Project source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY MODEL_CARD.md STRESS_TEST_REPORT.md ./
COPY INVESTIGATION_REPORT.md ./
COPY models/ ./models/

# Sample data for smoke runs (full datasets must be mounted at /app/data)
RUN mkdir -p /app/data /app/data/model_ready

# Drop privileges
RUN useradd --uid 10001 --create-home --shell /bin/bash sentinel \
 && chown -R sentinel:sentinel /app
USER sentinel

# REST API on 8000; WebSocket also served from the same port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/status').read()" || exit 1

# Default: serve the API. Override for batch jobs:
#   docker run sentinel-z:latest python scripts/ingest_e5.py
CMD ["uvicorn", "sentinel_z.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
