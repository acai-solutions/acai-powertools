"""LLM port — driven (secondary) port for language model adapters.

Hexagonal role
--------------
This is a *driven* (secondary) port.  Domain code and application services
depend only on this interface; concrete adapters (Anthropic, Bedrock Claude, …)
implement it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from acai.ai_llm.domain.content_block import ContentBlock


class LlmPort(ABC):
    """Abstract base class every LLM adapter must implement."""

    VERSION: str = "1.0.11"  # inject_version

    @abstractmethod
    def get_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        content_blocks: list[ContentBlock] | None = None,
    ) -> dict[str, Any]:
        """Generate a response for the given prompt.

        Parameters
        ----------
        prompt:
            The user prompt to send to the model.
        system_prompt:
            Optional system-level instruction.
        temperature:
            Sampling temperature override.
        max_tokens:
            Maximum tokens in the response override.
        content_blocks:
            Optional list of multi-modal content blocks (images, PDFs, …).
            When provided the adapter builds a multi-block message that
            includes these blocks alongside the text *prompt*.

        Returns
        -------
        dict with at least:
            - ``"response"`` (str): The generated text.
            - ``"usage"`` (dict): Token usage statistics.
            - ``"model"`` (str): Model identifier.
        """
        ...

    def get_structured_response(
        self,
        prompt: str,
        schema: dict[str, Any],
        tool_name: str = "extract",
        tool_description: str = "",
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Generate a structured response constrained by a JSON schema.

        Uses provider-specific tool-use / function-calling APIs to guarantee
        schema-conformant output.

        Parameters
        ----------
        prompt:
            The user message content.
        schema:
            A JSON Schema dict defining the expected output structure.
        tool_name:
            Name of the tool/function passed to the provider API.
        tool_description:
            Description of the tool/function.
        system_prompt:
            Optional system-level instruction.
        temperature:
            Sampling temperature override.
        max_tokens:
            Maximum tokens in the response override.

        Returns
        -------
        dict with at least:
            - ``"response"`` (dict): The parsed structured output.
            - ``"usage"`` (dict): Token usage statistics.
            - ``"model"`` (str): Model identifier.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support structured output. "
            "Use an adapter that implements get_structured_response()."
        )
