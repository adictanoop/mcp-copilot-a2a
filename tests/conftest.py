"""Shared test fixtures and configuration."""

from __future__ import annotations

import os

import pytest

# Set test environment variables before any imports
os.environ.setdefault("NVIDIA_API_KEY", "test-key-not-real")
os.environ.setdefault("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
os.environ.setdefault("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")
os.environ.setdefault("CHROMA_HOST", "localhost")
os.environ.setdefault("CHROMA_PORT", "8000")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture
def sample_search_results() -> list[dict]:
    """Sample Tavily search results."""
    return [
        {
            "url": "https://example.com/notion-competitors",
            "title": "Top Notion Competitors in 2024",
            "content": (
                "Notion faces competition from Obsidian, Coda, and Confluence. "
                "Obsidian offers offline-first note-taking with a plugin ecosystem. "
                "Coda provides doc-based workflows. Confluence remains the enterprise standard."
            ),
            "score": 0.95,
        },
        {
            "url": "https://example.com/productivity-tools",
            "title": "Best Productivity Tools Compared",
            "content": (
                "Linear competes with Notion in project management. Monday.com "
                "targets similar enterprise users. ClickUp offers an all-in-one platform."
            ),
            "score": 0.88,
        },
        {
            "url": "https://example.com/workspace-tools",
            "title": "Workspace Tool Comparison",
            "content": (
                "Miro competes in whiteboarding. Airtable in database workflows. "
                "Slite for team knowledge management."
            ),
            "score": 0.82,
        },
    ]


@pytest.fixture
def sample_research_output() -> dict:
    """Sample ResearchOutput as dict."""
    return {
        "company": "Notion",
        "competitors": ["Obsidian", "Coda", "Confluence", "Linear", "ClickUp"],
        "raw_results": [],
        "timestamp": "2024-01-01T00:00:00",
        "confidence": 0.9,
    }


@pytest.fixture
def sample_analysis_output() -> dict:
    """Sample AnalysisOutput as dict."""
    return {
        "scores": [
            {
                "name": "Obsidian",
                "pricing": 9,
                "features": 7,
                "market_position": 6,
                "threat_level": 7,
                "summary": "Free, offline-first, strong plugin ecosystem threatens Notion's power users.",
            },
            {
                "name": "Confluence",
                "pricing": 5,
                "features": 6,
                "market_position": 8,
                "threat_level": 6,
                "summary": "Atlassian integration makes it the enterprise default.",
            },
            {
                "name": "Coda",
                "pricing": 6,
                "features": 8,
                "market_position": 4,
                "threat_level": 5,
                "summary": "Doc-based workflows appeal to the same prosumer segment.",
            },
        ],
        "framework": "Competitive Scoring Matrix",
        "top_threat": "Obsidian",
        "strategic_gaps": [
            "No offline-first capability",
            "Limited whiteboarding features",
            "No startup-specific pricing tier",
        ],
    }


@pytest.fixture
def sample_writer_output() -> dict:
    """Sample WriterOutput as dict."""
    return {
        "executive_summary": (
            "Notion faces strong competition from Obsidian in the power-user segment "
            "and Confluence in enterprise. Obsidian's free, offline-first model threatens "
            "Notion's core knowledge management use case. Coda competes for the same "
            "prosumer budget with superior doc-based workflows."
        ),
        "competitor_matrix": (
            "| Competitor | Pricing | Features | Market Position | Threat Level | Summary |\n"
            "|---|---|---|---|---|---|\n"
            "| Obsidian | 9 | 7 | 6 | 7 | Free offline-first tool |\n"
            "| Confluence | 5 | 6 | 8 | 6 | Enterprise default |\n"
            "| Coda | 6 | 8 | 4 | 5 | Doc-based workflows |"
        ),
        "recommendations": [
            "Invest in offline-first capability to counter Obsidian's core advantage",
            "Launch a startup pricing tier under $5/user/month to block Linear and ClickUp expansion",
            "Acquire or partner with a whiteboard tool to close the Miro gap",
        ],
        "brief_markdown": "# Competitive Intelligence Brief: Notion\n\n...",
        "generated_at": "2024-01-01T00:00:00",
    }
