"""Analyst agent — scores competitors and identifies strategic gaps."""

from __future__ import annotations

import json
from typing import cast

import structlog

from agents.base import BaseAgent
from schemas.messages import (
    AnalysisOutput,
    PipelineState,
    ResearchOutput,
    schema_json,
)

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a senior strategy consultant. Score each competitor using the "
    "provided research. Scores must be integers 1-10. Be harsh — a 10 means "
    "existential threat. A 1 means negligible. Return ONLY valid JSON "
    "matching this schema:\n"
    "{schema}"
)


class AnalystAgent(BaseAgent):
    """Scores competitors and identifies strategic positioning."""

    def run(self, state: PipelineState) -> PipelineState:
        """Execute analysis phase.

        1. Parse research output from state
        2. Build analysis prompt with competitor data
        3. Call LLM for scoring and gap analysis
        4. Return updated state
        """
        company = state["company"]
        logger.info("analyst_start", company=company)

        try:
            # Step 1: Get research data
            research_data = state.get("research")
            if not research_data:
                raise ValueError("No research data available for analysis")

            research = ResearchOutput.model_validate(research_data)

            # Step 2: Build prompt
            competitor_list = ", ".join(research.competitors)
            search_context = ""
            if research.raw_results:
                search_context = "\n\nSupporting research:\n" + "\n".join(
                    f"- {r.title}: {r.content[:200]}" for r in research.raw_results[:8]
                )

            prompt = (
                f"Analyze the competitive landscape for {company}.\n\n"
                f"Competitors identified: {competitor_list}\n"
                f"{search_context}\n\n"
                f"For each competitor, provide:\n"
                f"- pricing: How competitive is their pricing? (1=not competitive, 10=highly competitive)\n"
                f"- features: How does their feature set compare? (1=weak, 10=superior)\n"
                f"- market_position: How strong is their market position? (1=weak, 10=dominant)\n"
                f"- threat_level: Overall threat to {company}? (1=negligible, 10=existential)\n"
                f"- summary: One-sentence competitive summary\n\n"
                f"Also identify:\n"
                f"- framework: The analysis framework you used (e.g. 'Competitive Scoring Matrix')\n"
                f"- top_threat: Name of the single highest-threat competitor\n"
                f"- strategic_gaps: List of gaps in {company}'s competitive position\n\n"
                f"Be specific and harsh. No filler. Score integers only 1-10."
            )

            system = SYSTEM_PROMPT.format(schema=schema_json(AnalysisOutput))

            # Step 3: Call LLM
            analysis: AnalysisOutput = cast(AnalysisOutput, self._call_llm(prompt, system, AnalysisOutput))

            # Step 4: Update state
            state["analysis"] = analysis.model_dump(mode="json")
            logger.info(
                "analyst_done",
                company=company,
                top_threat=analysis.top_threat,
                competitors_scored=len(analysis.scores),
                gaps=len(analysis.strategic_gaps),
            )

        except Exception as e:
            return self._handle_error(e, state)

        return state
