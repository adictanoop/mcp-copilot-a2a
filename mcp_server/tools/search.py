"""Tavily search tool with retry and fallback query logic."""

from __future__ import annotations

import os
from typing import Any

import structlog
from tavily import TavilyClient
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from constants import DEFAULT_SEARCH_MAX_RESULTS, DEFAULT_SEARCH_RETRIES

logger = structlog.get_logger(__name__)


def _get_client() -> TavilyClient:
    """Create a Tavily client from environment variables."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY environment variable is required")
    return TavilyClient(api_key=api_key)


@retry(
    stop=stop_after_attempt(DEFAULT_SEARCH_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def _tavily_search(client: TavilyClient, query: str, max_results: int = DEFAULT_SEARCH_MAX_RESULTS) -> list[dict[str, Any]]:
    """Execute a Tavily search with retries."""
    logger.info("tavily_search_executing", query=query, max_results=max_results)
    response = client.search(query=query, max_results=max_results)
    return response.get("results", [])


def search_competitors(company: str) -> list[dict[str, Any]]:
    """
    Search for competitors of a given company using Tavily.

    Primary query: "{company} competitors"
    Fallback query: "{company} alternatives"

    Returns list of search results with url, title, content, score.
    """
    client = _get_client()

    # Primary query
    primary_query = f"{company} competitors"
    logger.info("search_competitors_start", company=company, query=primary_query)

    results = _tavily_search(client, primary_query)

    if not results:
        # Fallback query
        fallback_query = f"{company} alternatives"
        logger.warn(
            "search_competitors_fallback",
            company=company,
            primary_query=primary_query,
            fallback_query=fallback_query,
        )
        results = _tavily_search(client, fallback_query)

    logger.info("search_competitors_done", company=company, result_count=len(results))

    return [
        {
            "url": r.get("url", ""),
            "title": r.get("title", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        }
        for r in results
    ]


def validate_company_has_results(company: str) -> bool:
    """
    Check if Tavily returns any results for the company.
    Used in the input validation gate.

    Returns True if results found, False otherwise.
    """
    try:
        results = search_competitors(company)
        return len(results) > 0
    except Exception:
        logger.exception("validate_company_search_failed", company=company)
        return False
