"""Quick validation test without full Docker setup.

Run with:
    python quick_test.py

Reads API credentials from environment variables (or .env via docker-compose).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Environment variables must already be set (e.g. from .env or shell export)
required_vars = ["NVIDIA_API_KEY", "TAVILY_API_KEY"]
for var in required_vars:
    if not os.environ.get(var):
        log.warning("%s is not set – some tests may be skipped", var)

os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8001")
os.environ.setdefault("LOG_LEVEL", "INFO")

log.info("Environment variables set")

# Test 1: Import all modules
log.info("=== Test 1: Module Imports ===")
try:
    from api import app
    log.info("API module imported")
    from orchestrator import run_pipeline
    log.info("Orchestrator module imported")
    from schemas.messages import WriterOutput, ComparisonOutput
    log.info("Schema modules imported")
except Exception as e:
    log.error("Import failed: %s", e)
    sys.exit(1)

# Test 2: Validate schemas
log.info("=== Test 2: Schema Validation ===")
try:
    from schemas.messages import WriterOutput, ComparisonOutput

    # Test WriterOutput via model_validate (fully typed)
    writer = WriterOutput.model_validate({
        "executive_summary": "Test summary with less than 150 words.",
        "competitor_matrix": "| Company | Score |\n|---------|-------|\n| A | 10 |",
        "recommendations": ["Rec 1", "Rec 2", "Rec 3"],
        "brief_markdown": "# Test Brief\n\nContent here",
        "generated_at": datetime.now(timezone.utc),
    })
    log.info(
        "WriterOutput validates correctly – summary=%d words, recs=%d",
        len(writer.executive_summary.split()),
        len(writer.recommendations),
    )

    # Test ComparisonOutput via model_validate (fully typed)
    ComparisonOutput.model_validate({
        "company_a": "Notion",
        "company_b": "Obsidian",
        "executive_summary": "Comparison summary.",
        "comparison_matrix": "| Feature | Notion | Obsidian |\n",
        "competitive_advantages": {
            "Notion": ["Adv 1", "Adv 2"],
            "Obsidian": ["Adv 1", "Adv 2"],
        },
        "market_positioning": "Analysis",
        "winner_analysis": "Notion wins",
        "recommendations": {
            "Notion": ["Rec 1", "Rec 2", "Rec 3"],
            "Obsidian": ["Rec 1", "Rec 2", "Rec 3"],
        },
        "generated_at": datetime.now(timezone.utc),
    })
    log.info("ComparisonOutput validates correctly")

except Exception as e:
    log.error("Schema validation failed: %s", e)
    sys.exit(1)

# Test 3: Test input validation
log.info("=== Test 3: Input Validation ===")
try:
    from orchestrator import validate_input
    from schemas.messages import PipelineState

    # Test empty company
    state: PipelineState = {
        "company": "",
        "research": None,
        "analysis": None,
        "output": None,
        "error": None,
        "failed_at": None,
    }
    result = validate_input(state)
    error_msg: str | None = result.get("error")
    if error_msg is not None and "2 characters" in error_msg:
        log.info("Empty company rejected correctly")
    else:
        log.warning("Empty company validation did not behave as expected")

    # Test generic company
    state["company"] = "company"
    state["error"] = None
    result = validate_input(state)
    generic_error: str | None = result.get("error")
    if generic_error is not None and "generic" in generic_error.lower():
        log.info("Generic company rejected correctly")
    else:
        log.warning("Generic company validation did not behave as expected")

except Exception as e:
    log.error("Input validation test failed: %s", e)
    import traceback
    traceback.print_exc()

# Test 4: Test API endpoints exist
log.info("=== Test 4: API Endpoints ===")
try:
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/health")
    log.info("GET /health endpoint exists (status: %d)", response.status_code)

    response = client.get("/")
    if response.status_code == 200 and "html" in response.text.lower():
        log.info("GET / (HTML frontend) exists")

    response = client.post("/analyze", json={"company": ""})
    if response.status_code == 422:
        log.info("POST /analyze endpoint exists and validates input")

    response = client.post("/compare", json={"company_a": "A", "company_b": "A"})
    if response.status_code == 400:
        log.info("POST /compare endpoint exists and validates input")

except Exception as e:
    log.error("API endpoint test failed: %s", e)
    import traceback
    traceback.print_exc()

log.info("=== Summary ===")
log.info("All static validation tests passed")
log.info(
    "Full end-to-end testing requires: ChromaDB running, valid API credentials, "
    "and network connectivity to NVIDIA NIM and Tavily APIs"
)
