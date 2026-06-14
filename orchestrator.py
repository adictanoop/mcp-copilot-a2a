"""LangGraph pipeline orchestrator.

StateGraph: validate_input → researcher → analyst → writer → END
Any node that sets state.error routes directly to END.
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.analyst import AnalystAgent
from agents.researcher import ResearcherAgent
from agents.writer import WriterAgent
from mcp_server.tools.search import validate_company_has_results
from schemas.messages import PipelineState
from constants import GENERIC_COMPANY_NAMES

logger = structlog.get_logger(__name__)

# Use the constant from constants.py
GENERIC_NAMES = GENERIC_COMPANY_NAMES

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent singletons (initialized once)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_researcher: ResearcherAgent | None = None
_analyst: AnalystAgent | None = None
_writer: WriterAgent | None = None


def _get_researcher() -> ResearcherAgent:
    global _researcher
    if _researcher is None:
        _researcher = ResearcherAgent()
    return _researcher


def _get_analyst() -> AnalystAgent:
    global _analyst
    if _analyst is None:
        _analyst = AnalystAgent()
    return _analyst


def _get_writer() -> WriterAgent:
    global _writer
    if _writer is None:
        _writer = WriterAgent()
    return _writer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Graph Nodes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def validate_input(state: PipelineState) -> PipelineState:
    """Validate company name before pipeline execution.

    Rejects:
    - Empty or <2 character names
    - Generic/blacklisted names
    - Names with zero Tavily results (after fallback query)
    """
    company = state.get("company", "").strip()
    logger.info("validate_input_start", company=company)

    # Check empty / too short
    if not company or len(company) < 2:
        state["error"] = "Company name must be at least 2 characters"
        state["failed_at"] = "validate_input"
        logger.warn("validation_failed_short", company=company)
        return state

    # Check generic names
    if company.lower() in GENERIC_NAMES:
        state["error"] = (
            f'"{company}" is too generic. Please provide a specific company name '
            f"(e.g., Notion, Slack, Figma)"
        )
        state["failed_at"] = "validate_input"
        logger.warn("validation_failed_generic", company=company)
        return state

    # Check Tavily results exist
    try:
        has_results = validate_company_has_results(company)
        if not has_results:
            state["error"] = (
                f'No competitive data found for "{company}". '
                f"Please verify the company name and try again."
            )
            state["failed_at"] = "validate_input"
            logger.warn("validation_failed_no_results", company=company)
            return state
    except Exception as e:
        state["error"] = f"Search validation failed: {str(e)}"
        state["failed_at"] = "validate_input"
        logger.error("validation_search_error", company=company, error=str(e))
        return state

    # Update state with cleaned company name
    state["company"] = company
    logger.info("validate_input_passed", company=company)
    return state


def run_researcher(state: PipelineState) -> PipelineState:
    """Execute the researcher agent."""
    return _get_researcher().run(state)


def run_analyst(state: PipelineState) -> PipelineState:
    """Execute the analyst agent."""
    return _get_analyst().run(state)


def run_writer(state: PipelineState) -> PipelineState:
    """Execute the writer agent."""
    return _get_writer().run(state)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Conditional routing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def should_continue(state: PipelineState) -> str:
    """Route to END if error is set, otherwise continue to next node."""
    if state.get("error"):
        logger.info(
            "pipeline_routing_to_end",
            error=state["error"],
            failed_at=state.get("failed_at"),
        )
        return "end"
    return "continue"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Build the graph
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline.

    Flow:
        validate_input → researcher → analyst → writer → END
        Any error → END
    """
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("validate_input", validate_input)
    graph.add_node("researcher", run_researcher)
    graph.add_node("analyst", run_analyst)
    graph.add_node("writer", run_writer)

    # Set entry point
    graph.set_entry_point("validate_input")

    # Conditional edges: each node checks for error before continuing
    graph.add_conditional_edges(
        "validate_input",
        should_continue,
        {"continue": "researcher", "end": END},
    )
    graph.add_conditional_edges(
        "researcher",
        should_continue,
        {"continue": "analyst", "end": END},
    )
    graph.add_conditional_edges(
        "analyst",
        should_continue,
        {"continue": "writer", "end": END},
    )
    graph.add_edge("writer", END)

    return graph


# Compiled graph with checkpointer
_checkpointer = MemorySaver()
_compiled_graph = build_graph().compile(checkpointer=_checkpointer)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def run_pipeline(company: str) -> PipelineState:
    """Run the full competitive intelligence pipeline.

    Args:
        company: Company name to analyze

    Returns:
        PipelineState with results or error information
    """
    import uuid

    thread_id = str(uuid.uuid4())
    logger.info("pipeline_start", company=company, thread_id=thread_id)

    initial_state: PipelineState = {
        "company": company,
        "research": None,
        "analysis": None,
        "output": None,
        "error": None,
        "failed_at": None,
    }

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        final_state: PipelineState = cast(
            PipelineState, _compiled_graph.invoke(initial_state, config=config)
        )
    except Exception as e:
        logger.exception("pipeline_unexpected_error", company=company)
        final_state = initial_state
        final_state["error"] = f"Pipeline unexpected error: {str(e)}"
        final_state["failed_at"] = "orchestrator"

    logger.info(
        "pipeline_complete",
        company=company,
        thread_id=thread_id,
        has_output=final_state.get("output") is not None,
        error=final_state.get("error"),
        failed_at=final_state.get("failed_at"),
    )

    return final_state


def run_comparison(company_a: str, company_b: str) -> dict:
    """Run comparison analysis for two companies.

    Args:
        company_a: First company name
        company_b: Second company name

    Returns:
        Dict with comparison results or error information
    """
    import uuid
    from schemas.messages import ComparisonOutput, schema_json

    thread_id = str(uuid.uuid4())
    logger.info("comparison_start", company_a=company_a, company_b=company_b, thread_id=thread_id)

    result: dict[str, Any] = {
        "company_a": company_a,
        "company_b": company_b,
        "comparison": None,
        "error": None,
        "failed_at": None,
    }

    try:
        # Run pipeline for company A
        logger.info("comparison_analyzing_company_a", company=company_a)
        state_a = run_pipeline(company_a)
        
        if state_a.get("error"):
            result["error"] = f"Analysis failed for {company_a}: {state_a['error']}"
            result["failed_at"] = f"company_a_{state_a.get('failed_at', 'unknown')}"
            return result

        # Run pipeline for company B
        logger.info("comparison_analyzing_company_b", company=company_b)
        state_b = run_pipeline(company_b)
        
        if state_b.get("error"):
            result["error"] = f"Analysis failed for {company_b}: {state_b['error']}"
            result["failed_at"] = f"company_b_{state_b.get('failed_at', 'unknown')}"
            return result

        # Generate comparison using writer agent
        logger.info("comparison_generating_comparison")
        writer = _get_writer()
        
        # Build comparison prompt
        comparison_prompt = f"""
Compare {company_a} and {company_b} based on their competitive intelligence analysis.

# {company_a} Analysis:
Research: {state_a.get('research', {})}
Analysis: {state_a.get('analysis', {})}
Report: {state_a.get('output', {})}

# {company_b} Analysis:
Research: {state_b.get('research', {})}
Analysis: {state_b.get('analysis', {})}
Report: {state_b.get('output', {})}

Generate a comprehensive head-to-head comparison that:
1. Compares key metrics, market position, features, and pricing
2. Identifies competitive advantages for each company
3. Analyzes market positioning and strategic differentiation
4. Determines which company has a stronger competitive position
5. Provides 3 actionable recommendations for each company

Return ONLY valid JSON matching this schema:
{schema_json(ComparisonOutput)}
"""

        system_prompt = f"""You are a strategic business analyst creating head-to-head company comparisons.

Analyze both companies fairly and objectively. Focus on:
- Market positioning and competitive advantages
- Feature/product differentiation
- Pricing and business model comparison
- Strategic strengths and weaknesses
- Actionable recommendations for each company

Return ONLY valid JSON with no additional text, no markdown formatting, no code fences.
"""

        try:
            comparison_result = writer._call_llm(
                comparison_prompt,
                system_prompt,
                ComparisonOutput
            )
            comparison_output = cast(ComparisonOutput, comparison_result)
            result["comparison"] = comparison_output.model_dump()
            logger.info("comparison_success", company_a=company_a, company_b=company_b)
            
        except Exception as e:
            logger.exception("comparison_generation_failed", company_a=company_a, company_b=company_b)
            result["error"] = f"Comparison generation failed: {str(e)}"
            result["failed_at"] = "comparison_generation"

    except Exception as e:
        logger.exception("comparison_unexpected_error", company_a=company_a, company_b=company_b)
        result["error"] = f"Comparison unexpected error: {str(e)}"
        result["failed_at"] = "comparison_orchestrator"

    logger.info(
        "comparison_complete",
        company_a=company_a,
        company_b=company_b,
        thread_id=thread_id,
        has_comparison=result.get("comparison") is not None,
        error=result.get("error"),
    )

    return result
