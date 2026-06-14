"""
MCP Server exposing competitive intelligence tools.

Can be run standalone via:
    python -m mcp_server.server

Or imported in-process by agents for direct tool invocation.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.search import search_competitors, validate_company_has_results
from mcp_server.tools.memory import store_research, retrieve_research, check_health
from mcp_server.tools.http import fetch_url

# Create MCP server instance
mcp = FastMCP("competitive-intelligence")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Register tools
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def tool_search_competitors(company: str) -> list[dict]:
    """Search for competitors of a given company using web search.

    Args:
        company: The company name to find competitors for

    Returns:
        List of search results with url, title, content, and score
    """
    return search_competitors(company)


@mcp.tool()
def tool_validate_company(company: str) -> bool:
    """Validate that a company name returns search results.

    Args:
        company: The company name to validate

    Returns:
        True if search results were found, False otherwise
    """
    return validate_company_has_results(company)


@mcp.tool()
def tool_store_research(company: str, data: dict) -> str:
    """Store competitive research data in vector memory.

    Args:
        company: The company name
        data: Serialized research output dict

    Returns:
        Document ID of stored research
    """
    return store_research(company, data)


@mcp.tool()
def tool_retrieve_research(company: str, n_results: int = 5) -> list[dict]:
    """Retrieve past competitive research from vector memory.

    Args:
        company: The company name to search for
        n_results: Maximum number of results to return

    Returns:
        List of past research documents
    """
    return retrieve_research(company, n_results)


@mcp.tool()
def tool_fetch_url(url: str) -> dict:
    """Fetch content from a URL.

    Args:
        url: The URL to fetch

    Returns:
        Dict with status_code, content, and url
    """
    return fetch_url(url)


@mcp.tool()
def tool_check_memory_health() -> bool:
    """Check if the vector memory (ChromaDB) is healthy.

    Returns:
        True if ChromaDB is reachable, False otherwise
    """
    return check_health()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Standalone entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    mcp.run()
