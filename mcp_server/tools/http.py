"""HTTP fetch tool with retry logic."""

from __future__ import annotations

import structlog
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def fetch_url(url: str, timeout: float = 30.0) -> dict[str, str | int]:
    """
    Fetch content from a URL with retries.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Dict with status_code, content, and url
    """
    logger.info("fetch_url_start", url=url, timeout=timeout)

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    logger.info(
        "fetch_url_done",
        url=url,
        status_code=response.status_code,
        content_length=len(response.text),
    )

    return {
        "url": url,
        "status_code": response.status_code,
        "content": response.text[:5000],  # Cap content to avoid memory issues
    }
