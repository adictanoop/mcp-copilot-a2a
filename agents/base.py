"""Base agent with structured LLM output enforcement and error handling."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Type

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr, ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from schemas.messages import PipelineState, StructuredOutputError, schema_json
from constants import (
    DEFAULT_NVIDIA_BASE_URL,
    DEFAULT_NVIDIA_MODEL,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_MAX_TOKENS,
)

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base agent with structured output enforcement.

    Every LLM call:
    1. Includes response format instructions in system prompt
    2. Requests JSON only — no markdown, no preamble
    3. Parses with Pydantic immediately
    4. On parse failure: retries once with correction prompt
    5. On second failure: raises StructuredOutputError
    """

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            model=os.environ.get("NVIDIA_MODEL", DEFAULT_NVIDIA_MODEL),
            api_key=SecretStr(os.environ.get("NVIDIA_API_KEY", "")),
            base_url=os.environ.get("NVIDIA_BASE_URL", DEFAULT_NVIDIA_BASE_URL),
            temperature=DEFAULT_LLM_TEMPERATURE,
            max_completion_tokens=DEFAULT_LLM_MAX_TOKENS,
        )
        self.agent_name = self.__class__.__name__
        logger.info("agent_initialized", agent=self.agent_name)

    def _call_llm(
        self,
        prompt: str,
        system: str,
        response_model: Type[BaseModel],
    ) -> BaseModel:
        """Call the LLM and enforce structured output with retry."""
        
        system_with_directive = (
            system + "\n\n"
            "CRITICAL INSTRUCTION:\n"
            "You MUST output a valid JSON *instance* containing the actual data.\n"
            "DO NOT output the JSON Schema definition (i.e. no '$defs', no 'properties').\n"
            "DO NOT output any text before or after the JSON object."
        )


        raw_response = ""
        first_error_msg = ""

        # First attempt
        try:
            raw_response = self._invoke_llm(prompt, system_with_directive)
            return self._parse_response(raw_response, response_model)
        except (ValidationError, json.JSONDecodeError, ValueError) as first_error:
            first_error_msg = str(first_error)
            logger.warn(
                "llm_parse_failed_first_attempt",
                agent=self.agent_name,
                error=first_error_msg,
                raw_response=raw_response[:500],
            )

        # Retry with correction prompt
        try:
            correction_system = (
                f"You returned invalid JSON. Return a valid JSON instance of the schema "
                f"with no additional text, no markdown formatting, no code fences.\n"
                f"CRITICAL: Do NOT output the JSON Schema definitions. Output an actual data instance!\n"
                f"Schema for reference:\n{schema_json(response_model)}"
            )
            correction_prompt = (
                f"Your previous response was invalid. Here was the error:\n"
                f"{first_error_msg}\n\n"
                f"Original request: {prompt}\n\n"
                f"Return ONLY valid JSON matching the schema. No explanation."
            )
            raw_response = self._invoke_llm(correction_prompt, correction_system)
            return self._parse_response(raw_response, response_model)
        except (ValidationError, json.JSONDecodeError, ValueError) as second_error:
            logger.error(
                "llm_parse_failed_second_attempt",
                agent=self.agent_name,
                error=str(second_error),
                raw_response=raw_response[:500],
            )
            raise StructuredOutputError(
                f"Failed to get valid structured output from LLM after 2 attempts: "
                f"{second_error}",
                raw_response=raw_response,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def _invoke_llm(self, prompt: str, system: str) -> str:
        """Invoke the LLM with retries for transient failures."""
        logger.info(
            "llm_invoke",
            agent=self.agent_name,
            prompt_length=len(prompt),
            system_length=len(system),
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        response = self.llm.invoke(messages)
        content = str(response.content)

        logger.info(
            "llm_response_received",
            agent=self.agent_name,
            response_length=len(content),
        )

        return content

    def _parse_response(self, raw: str, response_model: Type[BaseModel]) -> BaseModel:
        """Parse and validate LLM response against a Pydantic model.

        Handles common LLM output issues:
        - Strips markdown code fences
        - Strips leading/trailing whitespace
        - Extracts JSON from mixed content
        """
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        # Try to find JSON object in the content
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx : end_idx + 1]

        parsed = json.loads(cleaned)
        return response_model.model_validate(parsed)

    def _handle_error(self, error: Exception, state: PipelineState) -> PipelineState:
        """Handle errors by setting state fields instead of raising.

        Sets error message and failed_at stage name.
        Logs the error with structlog.
        Never raises - always returns updated state.
        """
        error_msg = f"{type(error).__name__}: {str(error)}"
        logger.error(
            "agent_error",
            agent=self.agent_name,
            error=error_msg,
            company=state.get("company", "unknown"),
        )

        state["error"] = error_msg
        state["failed_at"] = self.agent_name
        return state

    @abstractmethod
    def run(self, state: PipelineState) -> PipelineState:
        # Execute agent logic on pipeline state
        pass

