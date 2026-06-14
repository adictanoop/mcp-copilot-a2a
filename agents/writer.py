"""Writer agent — produces the final C-suite competitive intelligence brief."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import cast

import structlog

from agents.base import BaseAgent
from schemas.messages import (
    AnalysisOutput,
    PipelineState,
    ResearchOutput,
    WriterOutput,
    schema_json,
)

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a senior analyst writing for a C-suite audience with 90 seconds "
    "to read this. No filler. No hedging. Every sentence must contain a fact "
    "or a recommendation. Executive summary max 150 words. Exactly 3 "
    "recommendations, each actionable within 30 days. Return ONLY valid JSON "
    "matching this schema:\n"
    "{schema}"
)


class WriterAgent(BaseAgent):
    """Produces the final competitive intelligence brief."""

    def run(self, state: PipelineState) -> PipelineState:
        """Execute writing phase.

        1. Parse research and analysis from state
        2. Build comprehensive writing prompt
        3. Call LLM for final brief generation
        4. Return updated state with WriterOutput
        """
        company = state["company"]
        logger.info("writer_start", company=company)

        try:
            # Step 1: Get inputs
            research_data = state.get("research")
            analysis_data = state.get("analysis")

            if not research_data or not analysis_data:
                raise ValueError(
                    "Both research and analysis data required for writing"
                )

            research = ResearchOutput.model_validate(research_data)
            analysis = AnalysisOutput.model_validate(analysis_data)

            # Step 2: Build comprehensive prompt
            scores_table = self._build_scores_context(analysis)
            gaps_list = "\n".join(f"- {g}" for g in analysis.strategic_gaps)

            prompt = (
                f"Write a competitive intelligence brief for {company}.\n\n"
                f"=== RESEARCH DATA ===\n"
                f"Competitors: {', '.join(research.competitors)}\n"
                f"Research confidence: {research.confidence}\n\n"
                f"=== ANALYSIS DATA ===\n"
                f"Top threat: {analysis.top_threat}\n"
                f"Framework: {analysis.framework}\n\n"
                f"Competitor scores:\n{scores_table}\n\n"
                f"Strategic gaps:\n{gaps_list}\n\n"
                f"=== INSTRUCTIONS ===\n"
                f"Generate:\n"
                f"1. executive_summary: Max 150 words. Dense with facts.\n"
                f"2. competitor_matrix: A markdown table with columns: "
                f"Competitor | Pricing | Features | Market Position | Threat Level | Summary\n"
                f"3. recommendations: EXACTLY 3 actionable recommendations. "
                f"Each must be doable within 30 days. Be specific.\n"
                f"4. brief_markdown: Full competitive brief document in markdown "
                f"format, including all sections above plus analysis details.\n"
                f"5. generated_at: Use this timestamp: {datetime.now(timezone.utc).isoformat()}\n"
            )

            system = SYSTEM_PROMPT.format(schema=schema_json(WriterOutput))

            # Step 3: Call LLM
            output: WriterOutput = cast(WriterOutput, self._call_llm(prompt, system, WriterOutput))

            # Step 4: Update state
            state["output"] = output.model_dump(mode="json")
            logger.info(
                "writer_done",
                company=company,
                summary_words=len(output.executive_summary.split()),
                recommendations=len(output.recommendations),
            )

        except Exception as e:
            return self._handle_error(e, state)

        return state

    @staticmethod
    def _build_scores_context(analysis: AnalysisOutput) -> str:
        """Format competitor scores as readable text for the LLM prompt."""
        lines = []
        for s in analysis.scores:
            lines.append(
                f"- {s.name}: Pricing={s.pricing}/10, Features={s.features}/10, "
                f"Market={s.market_position}/10, Threat={s.threat_level}/10 — {s.summary}"
            )
        return "\n".join(lines)
