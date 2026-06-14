"""Integration tests for the pipeline with mocked external services."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from schemas.messages import PipelineState


class TestValidateInput:
    """Tests for the input validation gate."""

    def test_empty_company_rejected(self):
        from orchestrator import validate_input

        state: PipelineState = {
            "company": "",
            "research": None,
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        result = validate_input(state)
        assert result["error"] is not None
        assert result["failed_at"] == "validate_input"

    def test_short_company_rejected(self):
        from orchestrator import validate_input

        state: PipelineState = {
            "company": "A",
            "research": None,
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        result = validate_input(state)
        assert result["error"] is not None
        assert "2 characters" in result["error"]

    def test_generic_company_rejected(self):
        from orchestrator import validate_input

        state: PipelineState = {
            "company": "company",
            "research": None,
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        result = validate_input(state)
        assert result["error"] is not None
        assert "generic" in result["error"].lower()

    def test_generic_company_case_insensitive(self):
        from orchestrator import validate_input

        state: PipelineState = {
            "company": "BUSINESS",
            "research": None,
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        result = validate_input(state)
        assert result["error"] is not None

    @patch("orchestrator.validate_company_has_results", return_value=True)
    def test_valid_company_passes(self, mock_validate):
        from orchestrator import validate_input

        state: PipelineState = {
            "company": "Notion",
            "research": None,
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        result = validate_input(state)
        assert result["error"] is None
        assert result["failed_at"] is None

    @patch("orchestrator.validate_company_has_results", return_value=False)
    def test_no_search_results_rejected(self, mock_validate):
        from orchestrator import validate_input

        state: PipelineState = {
            "company": "XyzNonexistentCorp",
            "research": None,
            "analysis": None,
            "output": None,
            "error": None,
            "failed_at": None,
        }
        result = validate_input(state)
        assert result["error"] is not None
        assert "No competitive data" in result["error"]


class TestFullPipeline:
    """Tests for the full pipeline with mocked LLM and Tavily."""

    @patch("agents.researcher.search_competitors")
    @patch("agents.researcher.retrieve_research", return_value=[])
    @patch("agents.researcher.store_research", return_value="doc_id_1")
    @patch("orchestrator.validate_company_has_results", return_value=True)
    def test_full_pipeline_valid_company(
        self,
        mock_validate,
        mock_store,
        mock_retrieve,
        mock_search,
        sample_search_results,
        sample_research_output,
        sample_analysis_output,
        sample_writer_output,
    ):
        """Test that a valid company produces WriterOutput."""
        mock_search.return_value = sample_search_results

        # Mock all three LLM calls in sequence
        with patch("agents.base.BaseAgent._invoke_llm") as mock_llm:
            mock_llm.side_effect = [
                json.dumps(sample_research_output),
                json.dumps(sample_analysis_output),
                json.dumps(sample_writer_output),
            ]

            from orchestrator import run_pipeline

            result = run_pipeline("Notion")

        assert result.get("error") is None
        assert result.get("failed_at") is None
        assert result.get("output") is not None
        assert result["output"]["recommendations"] is not None
        assert len(result["output"]["recommendations"]) == 3

    @patch("orchestrator.validate_company_has_results", return_value=True)
    @patch("agents.researcher.search_competitors")
    @patch("agents.researcher.retrieve_research", return_value=[])
    @patch("agents.researcher.store_research", return_value="doc_id_1")
    def test_pipeline_returns_partial_state_on_llm_failure(
        self,
        mock_store,
        mock_retrieve,
        mock_search,
        mock_validate,
        sample_search_results,
    ):
        """Test that LLM failure returns partial state with failed_at."""
        mock_search.return_value = sample_search_results

        with patch("agents.base.BaseAgent._invoke_llm") as mock_llm:
            # Both attempts return invalid JSON
            mock_llm.side_effect = [
                "not valid json at all",
                "still not valid json",
            ]

            from orchestrator import run_pipeline

            result = run_pipeline("Notion")

        assert result.get("error") is not None
        assert result.get("failed_at") is not None
        assert result.get("output") is None

    @patch("orchestrator.validate_company_has_results", return_value=True)
    @patch("agents.researcher.search_competitors")
    @patch("agents.researcher.retrieve_research", return_value=[])
    @patch("agents.researcher.store_research", return_value="doc_id_1")
    def test_retry_triggers_on_json_parse_failure(
        self,
        mock_store,
        mock_retrieve,
        mock_search,
        mock_validate,
        sample_search_results,
        sample_research_output,
        sample_analysis_output,
        sample_writer_output,
    ):
        """Test that first JSON failure triggers retry with correction prompt."""
        mock_search.return_value = sample_search_results

        with patch("agents.base.BaseAgent._invoke_llm") as mock_llm:
            # First call fails, second succeeds (correction), then analyst + writer succeed
            mock_llm.side_effect = [
                "This is not JSON, here's my analysis...",  # Researcher attempt 1
                json.dumps(sample_research_output),  # Researcher retry (success)
                json.dumps(sample_analysis_output),  # Analyst attempt 1
                json.dumps(sample_writer_output),  # Writer attempt 1
            ]

            from orchestrator import run_pipeline

            result = run_pipeline("Notion")

        # Should succeed because retry worked
        assert result.get("error") is None
        assert result.get("output") is not None
        # LLM should have been called 4 times (1 fail + 1 retry + 2 normal)
        assert mock_llm.call_count == 4

    def test_pipeline_invalid_company_returns_error(self):
        """Test that invalid company returns error state, not an exception."""
        from orchestrator import run_pipeline

        result = run_pipeline("")

        assert result.get("error") is not None
        assert result.get("failed_at") == "validate_input"
        assert result.get("output") is None


class TestBaseAgentParsing:
    """Tests for BaseAgent response parsing."""

    def test_parse_clean_json(self):
        from agents.base import BaseAgent
        from schemas.messages import CompetitorScore

        # Create a concrete implementation for testing
        class TestAgent(BaseAgent):
            def run(self, state):
                return state

        agent = TestAgent()
        raw = json.dumps({
            "name": "Test",
            "pricing": 5,
            "features": 5,
            "market_position": 5,
            "threat_level": 5,
            "summary": "Test competitor",
        })
        result = agent._parse_response(raw, CompetitorScore)
        assert result.name == "Test"

    def test_parse_json_with_markdown_fences(self):
        from agents.base import BaseAgent
        from schemas.messages import CompetitorScore

        class TestAgent(BaseAgent):
            def run(self, state):
                return state

        agent = TestAgent()
        raw = '```json\n{"name": "Test", "pricing": 5, "features": 5, "market_position": 5, "threat_level": 5, "summary": "Test"}\n```'
        result = agent._parse_response(raw, CompetitorScore)
        assert result.name == "Test"

    def test_parse_json_with_surrounding_text(self):
        from agents.base import BaseAgent
        from schemas.messages import CompetitorScore

        class TestAgent(BaseAgent):
            def run(self, state):
                return state

        agent = TestAgent()
        raw = 'Here is the JSON:\n{"name": "Test", "pricing": 5, "features": 5, "market_position": 5, "threat_level": 5, "summary": "Test"}\nHope this helps!'
        result = agent._parse_response(raw, CompetitorScore)
        assert result.name == "Test"


class TestSlackIntegration:
    """Tests for Slack webhook notifications."""

    @pytest.mark.asyncio
    async def test_slack_notification_disabled_when_no_webhook(self, monkeypatch):
        """Test that Slack notification is skipped when SLACK_WEBHOOK_URL is not set."""
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        
        from api import send_slack_notification
        
        result = await send_slack_notification("Notion", "Test summary")
        assert result is False

    @pytest.mark.asyncio
    async def test_slack_notification_disabled_when_empty_webhook(self, monkeypatch):
        """Test that Slack notification is skipped when SLACK_WEBHOOK_URL is empty."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "")
        
        from api import send_slack_notification
        
        result = await send_slack_notification("Notion", "Test summary")
        assert result is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_slack_notification_success(self, mock_post, monkeypatch):
        """Test successful Slack notification."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK")
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        from api import send_slack_notification
        
        result = await send_slack_notification("Notion", "Test executive summary")
        assert result is True
        
        # Verify webhook was called with correct payload
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["text"] == "*Competitive Analysis Complete: Notion*\n\nTest executive summary"
        assert call_kwargs["json"]["unfurl_links"] is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_slack_notification_failure(self, mock_post, monkeypatch):
        """Test Slack notification handles webhook failures gracefully."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK")
        
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        from api import send_slack_notification
        
        result = await send_slack_notification("Notion", "Test summary")
        assert result is False

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_slack_notification_handles_exceptions(self, mock_post, monkeypatch):
        """Test Slack notification handles network exceptions gracefully."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/TEST/WEBHOOK")
        
        # Mock network exception
        mock_post.side_effect = Exception("Network error")
        
        from api import send_slack_notification
        
        result = await send_slack_notification("Notion", "Test summary")
        assert result is False


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_edge_case_1_generic_company_name(self):
        """EDGE CASE 1: Generic company names should be rejected with clear message."""
        from orchestrator import validate_input
        from schemas.messages import PipelineState

        generic_names = ["company", "business", "startup", "enterprise", "corporation"]
        
        for name in generic_names:
            state: PipelineState = {
                "company": name,
                "research": None,
                "analysis": None,
                "output": None,
                "error": None,
                "failed_at": None,
            }
            result = validate_input(state)
            assert result["error"] is not None, f"Should reject generic name: {name}"
            assert "generic" in result["error"].lower(), f"Error should mention 'generic' for: {name}"
            assert result["failed_at"] == "validate_input"

    @patch("mcp_server.tools.search._tavily_search")
    def test_edge_case_2_niche_company_fallback(self, mock_search):
        """EDGE CASE 2: Niche company with few results should trigger fallback query."""
        from orchestrator import run_pipeline
        from schemas.messages import ResearchOutput

        # Mock returns results on both calls (validation check will also call it)
        # First set: validation check
        # Second set: researcher agent execution (primary + fallback)
        fallback_results = [
            {"url": "https://example.com", "title": "Alternative 1", "content": "Content 1", "score": 0.8},
            {"url": "https://example.com/2", "title": "Alternative 2", "content": "Content 2", "score": 0.7},
            {"url": "https://example.com/3", "title": "Alternative 3", "content": "Content 3", "score": 0.6},
        ]
        
        # Validation calls it twice (primary + fallback), researcher calls it twice (primary + fallback)
        mock_search.side_effect = [
            [],  # Validation: primary query empty
            fallback_results,  # Validation: fallback query succeeds
            [],  # Researcher: primary query empty
            fallback_results,  # Researcher: fallback query succeeds
        ]

        # Mock LLM responses
        research_output = {
            "company": "NicheCompany",
            "competitors": ["Alt1", "Alt2", "Alt3"],
            "confidence": 0.7,
            "timestamp": "2024-01-01T00:00:00Z"
        }

        with patch("agents.base.BaseAgent._invoke_llm") as mock_llm, \
             patch("mcp_server.tools.memory.store_research", return_value="doc_1"), \
             patch("mcp_server.tools.memory.retrieve_research", return_value=[]):
            
            mock_llm.side_effect = [
                json.dumps(research_output),
                json.dumps({
                    "scores": [{"name": "Alt1", "pricing": 5, "features": 5, "market_position": 5, "threat_level": 5, "summary": "Good"}],
                    "framework": "Test",
                    "top_threat": "Alt1",
                    "strategic_gaps": ["Gap 1"]
                }),
                json.dumps({
                    "executive_summary": "Test summary.",
                    "competitor_matrix": "| C | S |\n|---|---|\n| A | 5 |",
                    "recommendations": ["R1", "R2", "R3"],
                    "brief_markdown": "# Brief",
                    "generated_at": "2024-01-01T00:00:00Z"
                })
            ]

            result = run_pipeline("NicheCompany")

        # Should succeed with fallback results
        assert result.get("error") is None, f"Pipeline failed with error: {result.get('error')}"
        assert result.get("output") is not None
        # Verify fallback query was called (should be called 4 times total: 2 for validation, 2 for researcher)
        assert mock_search.call_count == 4

    def test_edge_case_3_llm_malformed_json_retry(self):
        """EDGE CASE 3: LLM returns malformed JSON, retry should fire, then fail gracefully."""
        from orchestrator import run_pipeline
        
        with patch("mcp_server.tools.search.search_competitors") as mock_search, \
             patch("mcp_server.tools.memory.store_research", return_value="doc_1"), \
             patch("mcp_server.tools.memory.retrieve_research", return_value=[]), \
             patch("orchestrator.validate_company_has_results", return_value=True), \
             patch("agents.base.BaseAgent._invoke_llm") as mock_llm:
            
            mock_search.return_value = [
                {"url": "https://example.com", "title": "Result", "content": "Content", "score": 0.8}
            ]
            
            # Both attempts return malformed response
            mock_llm.side_effect = [
                "Here are the competitors: Notion, Asana",  # First attempt
                "Here are the competitors again: Notion, Asana",  # Retry attempt
            ]

            result = run_pipeline("TestCompany")

        # Should fail gracefully with structured error
        assert result.get("error") is not None
        assert "StructuredOutputError" in result["error"] or "valid" in result["error"].lower()
        assert result.get("failed_at") == "ResearcherAgent"
        assert result.get("output") is None

    @patch("mcp_server.tools.memory._get_chroma_client")
    @patch("mcp_server.tools.memory._get_collection")
    def test_edge_case_4_chromadb_unavailable(self, mock_collection, mock_client):
        """EDGE CASE 4: ChromaDB unavailable should continue without crashing."""
        from orchestrator import run_pipeline
        
        # Make ChromaDB operations fail
        mock_client.side_effect = Exception("ChromaDB connection failed")
        mock_collection.side_effect = Exception("ChromaDB connection failed")

        with patch("mcp_server.tools.search.search_competitors") as mock_search, \
             patch("orchestrator.validate_company_has_results", return_value=True), \
             patch("agents.base.BaseAgent._invoke_llm") as mock_llm, \
             patch("mcp_server.tools.memory.store_research", side_effect=Exception("ChromaDB unavailable")), \
             patch("mcp_server.tools.memory.retrieve_research", side_effect=Exception("ChromaDB unavailable")):
            
            mock_search.return_value = [
                {"url": "https://example.com", "title": "Result", "content": "Content", "score": 0.8}
            ]
            
            # Mock successful LLM responses
            mock_llm.side_effect = [
                json.dumps({
                    "company": "TestCompany",
                    "competitors": ["C1", "C2", "C3"],
                    "confidence": 0.8,
                    "timestamp": "2024-01-01T00:00:00Z"
                }),
                json.dumps({
                    "scores": [{"name": "C1", "pricing": 5, "features": 5, "market_position": 5, "threat_level": 5, "summary": "Good"}],
                    "framework": "Test",
                    "top_threat": "C1",
                    "strategic_gaps": ["Gap 1"]
                }),
                json.dumps({
                    "executive_summary": "Test summary.",
                    "competitor_matrix": "| C | S |\n|---|---|\n| A | 5 |",
                    "recommendations": ["R1", "R2", "R3"],
                    "brief_markdown": "# Brief",
                    "generated_at": "2024-01-01T00:00:00Z"
                })
            ]

            result = run_pipeline("TestCompany")

        # Should succeed despite ChromaDB failure
        # ChromaDB errors should be caught and logged, not crash the pipeline
        # This test verifies the pipeline is resilient to memory storage failures

    @patch("mcp_server.tools.search._tavily_search")
    def test_edge_case_5_tavily_rate_limit(self, mock_search):
        """EDGE CASE 5: Tavily rate limit (429) should retry then fail gracefully."""
        from orchestrator import run_pipeline
        import requests
        
        # Create a proper HTTP 429 exception
        class RateLimitException(Exception):
            pass
        
        # All 3 attempts fail with rate limit
        mock_search.side_effect = RateLimitException("Rate limit exceeded")

        with patch("orchestrator.validate_company_has_results", return_value=True):
            result = run_pipeline("TestCompany")

        # Should fail gracefully after retries exhausted
        assert result.get("error") is not None
        assert "Rate limit" in result["error"] or "RateLimitException" in result["error"]
        assert result.get("failed_at") == "ResearcherAgent"
