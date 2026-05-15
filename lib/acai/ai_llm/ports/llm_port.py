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

    VERSION: str = "1.0.10"  # inject_version

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

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        """Single-turn tool-calling step in an agentic loop.

        Sends the full conversation *messages* plus the available *tools*
        to the model and returns the assistant's next message — which may
        contain ``tool_calls`` the caller has to execute and feed back as
        a follow-up message.

        The wire format is OpenAI-style (canonical here, since OpenAI and
        Mistral use it natively; Anthropic adapters translate internally).

        Parameters
        ----------
        messages:
            OpenAI-style chat history. Each dict is one of:

            - ``{"role": "user",      "content": str}``
            - ``{"role": "assistant", "content": str | None,
                  "tool_calls": [{"id": str, "type": "function",
                                  "function": {"name": str,
                                               "arguments": json_str}}]}``
            - ``{"role": "tool",      "tool_call_id": str, "content": str}``
        tools:
            OpenAI tool-schema list, e.g.::

                [{"type": "function",
                  "function": {"name": "...", "description": "...",
                               "parameters": <json-schema>}}]
        system_prompt:
            Optional system instruction (overrides any system message
            embedded in *messages*; recommended to pass via this argument).
        temperature, max_tokens:
            Override config defaults.
        tool_choice:
            ``"auto"`` (default), ``"none"``, ``"required"``, or a specific
            ``{"type": "function", "function": {"name": ...}}`` dict.

        Returns
        -------
        dict with at least:

            - ``"message"`` (dict): The assistant message in OpenAI shape,
              ready to be appended to *messages* by the caller. Will
              contain ``"tool_calls"`` when ``stop_reason == "tool_use"``.
            - ``"stop_reason"`` (str): ``"tool_use"``, ``"end_turn"``, …
            - ``"usage"`` (dict): Token usage statistics.
            - ``"model"`` (str): Model identifier.

        Notes
        -----
        Adapters that don't support multi-turn tool calling raise
        :class:`NotImplementedError`. The *driver* (loop) lives in
        ``rag_pipeline.article_tool.run_tool_loop`` so that retries,
        max-iterations, and tool dispatch stay outside the adapter.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support chat_with_tools(). "
            "Use OpenAI, Mistral, or Anthropic-Claude adapters."
        )
