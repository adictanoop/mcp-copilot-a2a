"""Pydantic schemas and TypedDict state for the Competitive Intelligence Pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, TypedDict

from pydantic import BaseModel, Field, field_validator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Custom Exceptions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class StructuredOutputError(Exception):
    """Raised when LLM output fails Pydantic validation after retries."""

    def __init__(self, message: str, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Search & Research Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SearchResult(BaseModel):
    """A single search result from Tavily."""

    url: str = Field(..., description="URL of the search result")
    title: str = Field(..., description="Title of the search result")
    content: str = Field(..., description="Snippet or content from the result")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score 0-1")


class ResearchOutput(BaseModel):
    """Output from the researcher agent."""

    company: str = Field(..., description="Target company name")
    competitors: list[str] = Field(
        ...,
        min_length=3,
        max_length=8,
        description="List of 3-8 direct competitors",
    )
    raw_results: list[SearchResult] = Field(
        default_factory=list, description="Raw search results"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When research was conducted"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score 0-1"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Analysis Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CompetitorScore(BaseModel):
    """Score for a single competitor."""

    name: str = Field(..., description="Competitor name")
    pricing: int = Field(..., ge=1, le=10, description="Pricing competitiveness 1-10")
    features: int = Field(..., ge=1, le=10, description="Feature parity 1-10")
    market_position: int = Field(
        ..., ge=1, le=10, description="Market position strength 1-10"
    )
    threat_level: int = Field(
        ..., ge=1, le=10, description="Overall threat level 1-10"
    )
    summary: str = Field(..., description="Brief competitive summary")


class AnalysisOutput(BaseModel):
    """Output from the analyst agent."""

    scores: list[CompetitorScore] = Field(
        ..., min_length=1, description="Scored competitors"
    )
    framework: str = Field(
        ..., description="Analysis framework used (e.g. Porter's Five Forces)"
    )
    top_threat: str = Field(..., description="Name of the highest-threat competitor")
    strategic_gaps: list[str] = Field(
        ..., min_length=1, description="Identified strategic gaps"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Writer Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WriterOutput(BaseModel):
    """Final competitive intelligence brief."""

    executive_summary: str = Field(
        ..., description="Executive summary, max 150 words"
    )
    competitor_matrix: str = Field(
        ..., description="Markdown table comparing competitors"
    )
    recommendations: list[str] = Field(
        ..., description="Exactly 3 actionable recommendations"
    )
    brief_markdown: str = Field(
        ..., description="Full competitive brief in markdown"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Generation timestamp"
    )

    @field_validator("executive_summary")
    @classmethod
    def validate_executive_summary_length(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count > 150:
            raise ValueError(
                f"Executive summary must be ≤150 words, got {word_count}"
            )
        return v

    @field_validator("recommendations")
    @classmethod
    def validate_exactly_three_recommendations(cls, v: list[str]) -> list[str]:
        if len(v) != 3:
            raise ValueError(
                f"Exactly 3 recommendations required, got {len(v)}"
            )
        return v


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Comparison Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComparisonOutput(BaseModel):
    """Head-to-head comparison of two companies."""

    company_a: str = Field(..., description="First company name")
    company_b: str = Field(..., description="Second company name")
    executive_summary: str = Field(
        ..., description="Executive summary of the comparison, max 200 words"
    )
    comparison_matrix: str = Field(
        ..., description="Markdown table comparing both companies across key dimensions"
    )
    competitive_advantages: dict[str, list[str]] = Field(
        ..., description="Key advantages for each company (company name -> list of advantages)"
    )
    market_positioning: str = Field(
        ..., description="Analysis of how both companies are positioned in the market"
    )
    winner_analysis: str = Field(
        ..., description="Which company has the stronger position and why"
    )
    recommendations: dict[str, list[str]] = Field(
        ..., description="Strategic recommendations for each company (company name -> 3 recommendations)"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Generation timestamp"
    )

    @field_validator("executive_summary")
    @classmethod
    def validate_executive_summary_length(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count > 200:
            raise ValueError(
                f"Executive summary must be ≤200 words, got {word_count}"
            )
        return v

    @field_validator("recommendations")
    @classmethod
    def validate_recommendations_structure(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        for company, recs in v.items():
            if len(recs) != 3:
                raise ValueError(
                    f"Exactly 3 recommendations required for {company}, got {len(recs)}"
                )
        return v


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pipeline State (LangGraph TypedDict)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PipelineState(TypedDict, total=False):
    """Shared state passed through LangGraph nodes."""

    company: str
    research: Optional[dict]  # Serialized ResearchOutput
    analysis: Optional[dict]  # Serialized AnalysisOutput
    output: Optional[dict]  # Serialized WriterOutput
    error: Optional[str]
    failed_at: Optional[str]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def schema_json(model: type[BaseModel]) -> str:
    """Return a compact JSON schema string for use in LLM prompts."""
    return json.dumps(model.model_json_schema(), indent=2)
