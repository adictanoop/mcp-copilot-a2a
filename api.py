"""FastAPI application for the Competitive Intelligence Pipeline."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field

from orchestrator import run_pipeline, run_comparison
from schemas.messages import WriterOutput
from constants import (
    DEFAULT_NVIDIA_BASE_URL,
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_KEEPALIVE_TIMEOUT,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Structlog configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        os.environ.get("LOG_LEVEL", "INFO")
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Request / Response models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""

    company: str = Field(..., min_length=2, description="Company name to analyze")


class CompareRequest(BaseModel):
    """Request body for /compare endpoint."""

    company_a: str = Field(..., min_length=2, description="First company name")
    company_b: str = Field(..., min_length=2, description="Second company name")


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""

    status: str
    chroma: bool
    llm: bool


class ErrorResponse(BaseModel):
    """Error response with partial pipeline state."""

    error: str
    failed_at: str | None = None
    partial_state: dict | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Lifespan
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan — log startup and shutdown."""
    logger.info("app_starting", port=DEFAULT_API_PORT)
    yield
    logger.info("app_shutting_down")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# App
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(
    title="Competitive Intelligence Pipeline",
    description="AI-powered competitive analysis in 90 seconds",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Request logging middleware
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    """Log every request with duration_ms."""
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)

    logger.info(
        "http_request",
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    return response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the HTML frontend."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Competitive Intelligence Pipeline</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
            padding-top: 40px;
        }
        
        .header h1 {
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #555;
        }
        
        input[type="text"] {
            width: 100%;
            padding: 12px 16px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            width: 100%;
            padding: 14px 24px;
            font-size: 16px;
            font-weight: 600;
            color: white;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
            color: #667eea;
        }
        
        .loading.active {
            display: block;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .result {
            display: none;
        }
        
        .result.active {
            display: block;
        }
        
        .result h2 {
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .result h3 {
            color: #764ba2;
            margin-top: 30px;
            margin-bottom: 15px;
        }
        
        .result h4 {
            color: #555;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        
        .result p {
            margin-bottom: 15px;
            color: #555;
        }
        
        .result ul, .result ol {
            margin-left: 20px;
            margin-bottom: 15px;
        }
        
        .result li {
            margin-bottom: 8px;
            color: #555;
        }
        
        .result table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        .result table th,
        .result table td {
            padding: 12px;
            text-align: left;
            border: 1px solid #e0e0e0;
        }
        
        .result table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #667eea;
        }
        
        .result table tr:hover {
            background: #f8f9fa;
        }
        
        .result code {
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        
        .result pre {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 15px 0;
        }
        
        .result blockquote {
            border-left: 4px solid #667eea;
            padding-left: 20px;
            margin: 20px 0;
            color: #666;
            font-style: italic;
        }
        
        .error {
            display: none;
            background: #fee;
            border-left: 4px solid #c00;
            padding: 15px;
            border-radius: 8px;
            color: #c00;
            margin-bottom: 20px;
        }
        
        .error.active {
            display: block;
        }
        
        .meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
            font-size: 0.9em;
            color: #888;
        }
        
        .new-analysis {
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
        }
        
        .new-analysis:hover {
            background: #667eea;
            color: white;
        }
        
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2em;
            }
            
            .card {
                padding: 20px;
            }
            
            .meta {
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Competitive Intelligence</h1>
            <p>AI-powered competitive analysis in 90 seconds</p>
        </div>
        
        <div class="card">
            <form id="analyzeForm">
                <div class="form-group">
                    <label for="company">Company Name</label>
                    <input 
                        type="text" 
                        id="company" 
                        name="company" 
                        placeholder="e.g., Notion, Slack, Figma"
                        required
                        autocomplete="off"
                    >
                </div>
                <button type="submit" id="submitBtn">Analyze Competitors</button>
            </form>
            
            <div class="error" id="error"></div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p><strong>Analyzing competitive landscape...</strong></p>
                <p>This typically takes 60-90 seconds</p>
            </div>
        </div>
        
        <div class="card result" id="result">
            <div id="briefContent"></div>
            <div class="meta">
                <span id="timestamp"></span>
                <button class="new-analysis" onclick="resetForm()">New Analysis</button>
            </div>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('analyzeForm');
        const submitBtn = document.getElementById('submitBtn');
        const loading = document.getElementById('loading');
        const result = document.getElementById('result');
        const error = document.getElementById('error');
        const briefContent = document.getElementById('briefContent');
        const timestamp = document.getElementById('timestamp');
        const companyInput = document.getElementById('company');
        
        // Simple markdown to HTML converter
        function markdownToHtml(markdown) {
            let html = markdown;
            
            // Headers
            html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
            html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
            html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
            
            // Bold
            html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
            html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
            
            // Italic
            html = html.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
            html = html.replace(/_(.+?)_/g, '<em>$1</em>');
            
            // Code
            html = html.replace(/`(.+?)`/g, '<code>$1</code>');
            
            // Links
            html = html.replace(/\\[(.+?)\\]\\((.+?)\\)/g, '<a href="$2" target="_blank">$1</a>');
            
            // Tables
            const tableRegex = /(\\|.*\\|[\\r\\n]+)+/g;
            html = html.replace(tableRegex, function(match) {
                const rows = match.trim().split('\\n');
                let tableHtml = '<table>';
                
                rows.forEach((row, index) => {
                    if (index === 1 && row.includes('---')) return; // Skip separator row
                    
                    const cells = row.split('|').filter(cell => cell.trim());
                    const tag = index === 0 ? 'th' : 'td';
                    
                    tableHtml += '<tr>';
                    cells.forEach(cell => {
                        tableHtml += `<${tag}>${cell.trim()}</${tag}>`;
                    });
                    tableHtml += '</tr>';
                });
                
                tableHtml += '</table>';
                return tableHtml;
            });
            
            // Lists
            html = html.replace(/^\\* (.+)$/gim, '<li>$1</li>');
            html = html.replace(/^- (.+)$/gim, '<li>$1</li>');
            html = html.replace(/^\\d+\\. (.+)$/gim, '<li>$1</li>');
            html = html.replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>');
            
            // Blockquotes
            html = html.replace(/^> (.+)$/gim, '<blockquote>$1</blockquote>');
            
            // Line breaks and paragraphs
            html = html.replace(/\\n\\n/g, '</p><p>');
            html = '<p>' + html + '</p>';
            
            // Clean up empty paragraphs
            html = html.replace(/<p><\\/p>/g, '');
            html = html.replace(/<p>(<h[1-6]>)/g, '$1');
            html = html.replace(/(<\\/h[1-6]>)<\\/p>/g, '$1');
            html = html.replace(/<p>(<table>)/g, '$1');
            html = html.replace(/(<\\/table>)<\\/p>/g, '$1');
            html = html.replace(/<p>(<ul>)/g, '$1');
            html = html.replace(/(<\\/ul>)<\\/p>/g, '$1');
            
            return html;
        }
        
        function formatTimestamp(isoString) {
            const date = new Date(isoString);
            return date.toLocaleString('en-US', {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
        }
        
        function showError(message) {
            error.textContent = message;
            error.classList.add('active');
            loading.classList.remove('active');
            submitBtn.disabled = false;
        }
        
        function hideError() {
            error.classList.remove('active');
            error.textContent = '';
        }
        
        function resetForm() {
            form.style.display = 'block';
            result.classList.remove('active');
            companyInput.value = '';
            companyInput.focus();
        }
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const company = companyInput.value.trim();
            
            if (!company) {
                showError('Please enter a company name');
                return;
            }
            
            // Reset UI
            hideError();
            submitBtn.disabled = true;
            loading.classList.add('active');
            result.classList.remove('active');
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ company }),
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    // Handle error responses
                    const errorMsg = data.error || 'Analysis failed. Please try again.';
                    showError(errorMsg);
                    return;
                }
                
                // Success - render the brief
                loading.classList.remove('active');
                form.style.display = 'none';
                result.classList.add('active');
                
                // Convert markdown to HTML and display
                briefContent.innerHTML = markdownToHtml(data.brief_markdown);
                timestamp.textContent = `Generated ${formatTimestamp(data.generated_at)}`;
                
            } catch (err) {
                showError('Network error. Please check your connection and try again.');
                console.error('Error:', err);
            }
        });
        
        // Focus on input on page load
        companyInput.focus();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


async def send_slack_notification(company: str, executive_summary: str) -> bool:
    """Send executive summary to Slack webhook.

    Args:
        company: Company name that was analyzed
        executive_summary: Executive summary text to send

    Returns:
        True if notification sent successfully, False otherwise
    """
    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    
    if not slack_webhook_url:
        logger.debug("slack_notification_skipped", reason="SLACK_WEBHOOK_URL not configured")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "text": f"*Competitive Analysis Complete: {company}*\n\n{executive_summary}",
                "unfurl_links": False,
                "unfurl_media": False,
            }
            
            response = await client.post(
                slack_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code == 200:
                logger.info("slack_notification_sent", company=company)
                return True
            else:
                logger.warn(
                    "slack_notification_failed",
                    company=company,
                    status_code=response.status_code,
                    response=response.text[:200],
                )
                return False
                
    except Exception as e:
        logger.error(
            "slack_notification_error",
            company=company,
            error=str(e),
        )
        return False


@app.post("/analyze", response_model=None)
async def analyze(request: AnalyzeRequest) -> JSONResponse:
    """Run the competitive intelligence pipeline.

    Returns WriterOutput on success, or 422 with error details on failure.
    Sends executive summary to Slack if SLACK_WEBHOOK_URL is configured.
    Timeout: 120 seconds.
    """
    company = request.company.strip()
    logger.info("analyze_request", company=company)

    start = time.monotonic()

    try:
        # Run pipeline (synchronous — LangGraph is sync)
        state = run_pipeline(company)
    except Exception as e:
        logger.exception("analyze_unexpected_error", company=company)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected pipeline error: {str(e)}",
        )

    duration_ms = round((time.monotonic() - start) * 1000, 2)

    # Check for pipeline errors
    if state.get("error"):
        logger.warn(
            "analyze_pipeline_error",
            company=company,
            error=state["error"],
            failed_at=state.get("failed_at"),
            duration_ms=duration_ms,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": state["error"],
                "failed_at": state.get("failed_at"),
                "partial_state": {
                    "company": state.get("company"),
                    "has_research": state.get("research") is not None,
                    "has_analysis": state.get("analysis") is not None,
                },
            },
        )

    # Success — return WriterOutput
    output = state.get("output")
    if not output:
        logger.error("analyze_no_output", company=company, duration_ms=duration_ms)
        raise HTTPException(
            status_code=500,
            detail="Pipeline completed but produced no output",
        )

    logger.info("analyze_success", company=company, duration_ms=duration_ms)

    # Send Slack notification (non-blocking, doesn't affect response)
    if output.get("executive_summary"):
        await send_slack_notification(company, output["executive_summary"])

    return JSONResponse(status_code=200, content=output)


@app.post("/compare", response_model=None)
async def compare(request: CompareRequest):
    """Run head-to-head company comparison analysis.

    Returns ComparisonOutput on success, or 422 with error details on failure.
    Timeout: 240 seconds (runs two full pipelines).
    """
    company_a = request.company_a.strip()
    company_b = request.company_b.strip()
    logger.info("compare_request", company_a=company_a, company_b=company_b)

    # Validate companies are different
    if company_a.lower() == company_b.lower():
        raise HTTPException(
            status_code=400,
            detail="Cannot compare a company with itself. Please provide two different companies.",
        )

    start = time.monotonic()

    try:
        # Run comparison (synchronous — LangGraph is sync)
        result = run_comparison(company_a, company_b)
    except Exception as e:
        logger.exception("compare_unexpected_error", company_a=company_a, company_b=company_b)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected comparison error: {str(e)}",
        )

    duration_ms = round((time.monotonic() - start) * 1000, 2)

    # Check for comparison errors
    if result.get("error"):
        logger.warn(
            "compare_error",
            company_a=company_a,
            company_b=company_b,
            error=result["error"],
            failed_at=result.get("failed_at"),
            duration_ms=duration_ms,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": result["error"],
                "failed_at": result.get("failed_at"),
                "company_a": result.get("company_a"),
                "company_b": result.get("company_b"),
            },
        )

    # Success — return ComparisonOutput
    comparison = result.get("comparison")
    if not comparison:
        logger.error("compare_no_output", company_a=company_a, company_b=company_b, duration_ms=duration_ms)
        raise HTTPException(
            status_code=500,
            detail="Comparison completed but produced no output",
        )

    logger.info("compare_success", company_a=company_a, company_b=company_b, duration_ms=duration_ms)

    return JSONResponse(status_code=200, content=comparison)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check — actually pings ChromaDB and NVIDIA NIM."""
    chroma_ok = False
    llm_ok = False

    # Check ChromaDB
    try:
        from mcp_server.tools.memory import check_health

        chroma_ok = check_health()
    except Exception:
        logger.warn("health_chroma_failed")

    # Check NVIDIA NIM
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            base_url = os.environ.get("NVIDIA_BASE_URL", DEFAULT_NVIDIA_BASE_URL)
            api_key = os.environ.get("NVIDIA_API_KEY", "")
            response = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            llm_ok = response.status_code in (200, 401)  # 401 = key works, endpoint exists
    except Exception:
        logger.warn("health_llm_failed")

    status = "ok" if (chroma_ok and llm_ok) else "degraded"

    return HealthResponse(status=status, chroma=chroma_ok, llm=llm_ok)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=DEFAULT_API_HOST,
        port=DEFAULT_API_PORT,
        timeout_keep_alive=DEFAULT_KEEPALIVE_TIMEOUT,
    )
