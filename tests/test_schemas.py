"""Tests for Pydantic schema validation."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from schemas.messages import (
    AnalysisOutput,
    CompetitorScore,
    PipelineState,
    ResearchOutput,
    SearchResult,
    WriterOutput,
)


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_valid_search_result(self):
        result = SearchResult(
            url="https://example.com",
            title="Test",
            content="Content here",
            score=0.85,
        )
        assert result.score == 0.85

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            SearchResult(
                url="https://example.com",
                title="Test",
                content="Content",
                score=1.5,
            )


class TestResearchOutput:
    """Tests for ResearchOutput model."""

    def test_valid_research(self):
        research = ResearchOutput(
            company="Notion",
            competitors=["Obsidian", "Coda", "Confluence"],
            confidence=0.9,
        )
        assert len(research.competitors) == 3

    def test_too_few_competitors(self):
        with pytest.raises(ValidationError):
            ResearchOutput(
                company="Notion",
                competitors=["Obsidian"],
                confidence=0.9,
            )

    def test_too_many_competitors(self):
        with pytest.raises(ValidationError):
            ResearchOutput(
                company="Notion",
                competitors=[f"Comp{i}" for i in range(10)],
                confidence=0.9,
            )


class TestCompetitorScore:
    """Tests for CompetitorScore model."""

    def test_valid_scores(self):
        score = CompetitorScore(
            name="Obsidian",
            pricing=8,
            features=7,
            market_position=6,
            threat_level=7,
            summary="Strong open-source competitor",
        )
        assert score.pricing == 8

    def test_score_below_minimum(self):
        """Scores must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            CompetitorScore(
                name="Test",
                pricing=0,
                features=5,
                market_position=5,
                threat_level=5,
                summary="Test",
            )
        assert "pricing" in str(exc_info.value)

    def test_score_above_maximum(self):
        """Scores must be <= 10."""
        with pytest.raises(ValidationError) as exc_info:
            CompetitorScore(
                name="Test",
                pricing=5,
                features=11,
                market_position=5,
                threat_level=5,
                summary="Test",
            )
        assert "features" in str(exc_info.value)

    def test_all_scores_at_boundary(self):
        """All scores at minimum (1) and maximum (10)."""
        min_score = CompetitorScore(
            name="Min",
            pricing=1,
            features=1,
            market_position=1,
            threat_level=1,
            summary="Minimum",
        )
        max_score = CompetitorScore(
            name="Max",
            pricing=10,
            features=10,
            market_position=10,
            threat_level=10,
            summary="Maximum",
        )
        assert min_score.pricing == 1
        assert max_score.pricing == 10

    def test_negative_score_rejected(self):
        """Negative scores must be rejected."""
        with pytest.raises(ValidationError):
            CompetitorScore(
                name="Test",
                pricing=-1,
                features=5,
                market_position=5,
                threat_level=5,
                summary="Test",
            )


class TestAnalysisOutput:
    """Tests for AnalysisOutput model."""

    def test_valid_analysis(self, sample_analysis_output):
        analysis = AnalysisOutput.model_validate(sample_analysis_output)
        assert analysis.top_threat == "Obsidian"
        assert len(analysis.scores) == 3

    def test_empty_scores_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisOutput(
                scores=[],
                framework="Test",
                top_threat="None",
                strategic_gaps=["Gap 1"],
            )


class TestWriterOutput:
    """Tests for WriterOutput model."""

    def test_valid_writer_output(self, sample_writer_output):
        output = WriterOutput.model_validate(sample_writer_output)
        assert len(output.recommendations) == 3

    def test_too_many_recommendations(self):
        """WriterOutput must have exactly 3 recommendations."""
        with pytest.raises(ValidationError) as exc_info:
            WriterOutput(
                executive_summary="Short summary of competition.",
                competitor_matrix="| Competitor | Score |\n|---|---|",
                recommendations=["Rec 1", "Rec 2", "Rec 3", "Rec 4"],
                brief_markdown="# Brief",
            )
        assert "3 recommendations" in str(exc_info.value)

    def test_too_few_recommendations(self):
        """WriterOutput must have exactly 3 recommendations."""
        with pytest.raises(ValidationError) as exc_info:
            WriterOutput(
                executive_summary="Short summary.",
                competitor_matrix="| Competitor | Score |\n|---|---|",
                recommendations=["Rec 1", "Rec 2"],
                brief_markdown="# Brief",
            )
        assert "3 recommendations" in str(exc_info.value)

    def test_executive_summary_too_long(self):
        """Executive summary must be <= 150 words."""
        long_summary = " ".join(["word"] * 200)
        with pytest.raises(ValidationError) as exc_info:
            WriterOutput(
                executive_summary=long_summary,
                competitor_matrix="| Test |",
                recommendations=["Rec 1", "Rec 2", "Rec 3"],
                brief_markdown="# Brief",
            )
        assert "150 words" in str(exc_info.value)

    def test_executive_summary_at_limit(self):
        """150 words exactly should be accepted."""
        exactly_150 = " ".join(["word"] * 150)
        output = WriterOutput(
            executive_summary=exactly_150,
            competitor_matrix="| Test |",
            recommendations=["Rec 1", "Rec 2", "Rec 3"],
            brief_markdown="# Brief",
        )
        assert len(output.executive_summary.split()) == 150

    def test_generated_at_default(self):
        """generated_at should default to current time."""
        output = WriterOutput(
            executive_summary="Short summary.",
            competitor_matrix="| Test |",
            recommendations=["Rec 1", "Rec 2", "Rec 3"],
            brief_markdown="# Brief",
        )
        assert output.generated_at is not None


class TestPipelineState:
    """Tests for PipelineState TypedDict."""

    def test_pipeline_state_carries_error(self):
        """PipelineState should carry error without raising."""
        state: PipelineState = {
            "company": "Notion",
            "research": None,
            "analysis": None,
            "output": None,
            "error": "Tavily returned 0 results",
            "failed_at": "validate_input",
        }
        assert state["error"] == "Tavily returned 0 results"
        assert state["failed_at"] == "validate_input"
        assert state["company"] == "Notion"

    def test_pipeline_state_no_error(self):
        """PipelineState with no error."""
        state: PipelineState = {
            "company": "Notion",
            "research": {"company": "Notion", "competitors": ["Obsidian"]},
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        assert state["error"] is None
        assert state["research"] is not None

    def test_pipeline_state_partial_results(self):
        """PipelineState can have partial results when error occurs mid-pipeline."""
        state: PipelineState = {
            "company": "Notion",
            "research": {"company": "Notion", "competitors": ["Obsidian", "Coda", "Confluence"]},
            "analysis": None,
            "output": None,
            "error": "LLM parse failure in AnalystAgent",
            "failed_at": "AnalystAgent",
        }
        assert state["research"] is not None
        assert state["analysis"] is None
        assert state["error"] is not None
