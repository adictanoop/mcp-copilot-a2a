FROM python:3.11-slim AS base

# Install curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY schemas/ schemas/
COPY mcp_server/ mcp_server/
COPY agents/ agents/
COPY orchestrator.py .
COPY api.py .
COPY constants.py .

# Copy tests (for in-container test runs)
COPY tests/ tests/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
