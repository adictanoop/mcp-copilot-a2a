"""Researcher agent — identifies competitors using search + LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import cast

import structlog

from agents.base import BaseAgent
from schemas.messages import (
    PipelineState,
    ResearchOutput,
    SearchResult,
    schema_json,
)
from mcp_server.tools.search import search_competitors
from mcp_server.tools.memory import store_research, retrieve_research

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an expert competitive intelligence researcher. Given a company "
    "name, identify its top 3-8 direct competitors. Focus on companies that "
    "compete for the same budget, same user, same use case. Exclude tangential "
    "tools. Return ONLY valid JSON matching this schema:\n"
    "{schema}"
)


class ResearcherAgent(BaseAgent):
    """Identifies competitors via Tavily search and LLM analysis."""

    def run(self, state: PipelineState) -> PipelineState:
        """Execute research phase.

        1. Search for competitor information via Tavily
        2. Check for past research in ChromaDB
        3. Send context to LLM for structured competitor identification
        4. Store results in ChromaDB
        5. Return updated state
        """
        company = state["company"]
        logger.info("researcher_start", company=company)

        try:
            # Step 1: Search for competitor data
            raw_results = search_competitors(company)
            search_results = [
                SearchResult(
                    url=r["url"],
                    title=r["title"],
                    content=r["content"],
                    score=r["score"],
                )
                for r in raw_results
            ]

            # Step 2: Check for past research
            past_research = []
            try:
                past_research = retrieve_research(company, n_results=3)
            except Exception:
                logger.warn("past_research_retrieval_failed", company=company)

            # Step 3: Build prompt with search context
            search_context = "\n\n".join(
                f"Source: {r.title} ({r.url})\n{r.content}"
                for r in search_results[:10]
            )

            past_context = ""
            if past_research:
                past_context = (
                    "\n\nPrevious research found:\n"
                    + json.dumps(past_research[:2], default=str, indent=2)
                )

            prompt = (
                f"Research the competitive landscape for: {company}\n\n"
                f"Search results:\n{search_context}"
                f"{past_context}\n\n"
                f"Identify 3-8 direct competitors. For the company field, use "
                f'exactly: "{company}". Set confidence between 0 and 1 based '
                f"on how well the search results cover the competitive landscape. "
                f"Set timestamp to the current time: {datetime.now(timezone.utc).isoformat()}. "
                f"For raw_results, return an empty list []."
            )

            system = SYSTEM_PROMPT.format(schema=schema_json(ResearchOutput))

            # Step 4: Call LLM with structured output enforcement
            research: ResearchOutput = cast(ResearchOutput, self._call_llm(prompt, system, ResearchOutput))

            # Attach raw search results that may have been omitted by LLM
            if not research.raw_results:
                research = research.model_copy(update={"raw_results": search_results})

            # Step 5: Store in ChromaDB
            try:
                store_research(company, research.model_dump(mode="json"))
                logger.info("research_stored", company=company)
            except Exception:
                logger.warn("research_storage_failed", company=company)

            # Update state
            state["research"] = research.model_dump(mode="json")
            logger.info(
                "researcher_done",
                company=company,
                competitors=research.competitors,
                confidence=research.confidence,
            )

        except Exception as e:
            return self._handle_error(e, state)

        return state
