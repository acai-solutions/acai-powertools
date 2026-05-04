"""OpenAI adapter — calls OpenAI chat-completion models.

Hexagonal role
--------------
Outbound adapter implementing ``LlmPort``.  Uses the official ``openai``
Python SDK.  Supports text, image, and document (PDF) content blocks.

When ``api_key`` is empty the SDK auto-reads ``OPENAI_API_KEY`` from the
environment.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, List

from acai.ai_llm.domain.content_block import ContentBlock, ContentType
from acai.ai_llm.domain.exceptions import ModelInvocationError, TextTooLongError
from acai.ai_llm.domain.llm_config import LlmConfig
from acai.ai_llm.ports.llm_port import LlmPort
from acai.logging import Loggable


@dataclass
class OpenAIConfig(LlmConfig):
    """Configuration specific to the OpenAI adapter.

    When ``api_key`` is empty the SDK falls back to the
    ``OPENAI_API_KEY`` environment variable.
    """

    api_key: str = ""
    model_name: str = "gpt-4o"
    max_text_length: int = 200_000
    max_tokens: int = 4096
    temperature: float = 0.7
    stop_sequences: List[str] = field(default_factory=list)
    max_retries: int = 5
    retry_base_delay: float = 5.0
    price_per_input_token: float = 0.0
    price_per_output_token: float = 0.0


class OpenAIAdapter(LlmPort):
    """LLM adapter that calls the OpenAI Chat Completions API.

    Requires the ``openai`` package::

        pip install openai
    """

    VERSION: str = "1.0.6"  # inject_version

    def __init__(
        self,
        logger: Loggable | None = None,
        config: OpenAIConfig | None = None,
    ) -> None:
        self.config = config or OpenAIConfig()
        self.logger = logger or logging.getLogger("openai")
        self._initialize_client()
        self.logger.info(
            "Initialized OpenAIAdapter",
            model=self.config.model_name,
        )

    def _initialize_client(self) -> None:
        try:
            import openai

            kwargs: dict[str, Any] = {}
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key

            self.client = openai.OpenAI(**kwargs)
        except Exception as exc:
            self.logger.error("Failed to initialize OpenAI client", error=str(exc))
            raise ModelInvocationError(
                f"OpenAI client initialization failed: {exc}"
            ) from exc

    def _validate_input(self, text: str) -> None:
        if not text or not isinstance(text, str):
            raise ValueError("Input text must be a non-empty string")
        if len(text) > self.config.max_text_length:
            raise TextTooLongError(
                f"Input text length ({len(text)}) exceeds maximum "
                f"({self.config.max_text_length})"
            )

    @staticmethod
    def _build_content_blocks(
        prompt: str, content_blocks: list[ContentBlock] | None
    ) -> str | list[dict[str, Any]]:
        """Return plain string or OpenAI multi-block content list."""
        if not content_blocks:
            return prompt

        parts: list[dict[str, Any]] = []
        for block in content_blocks:
            if block.content_type == ContentType.TEXT:
                parts.append({"type": "text", "text": block.data})
            elif block.content_type == ContentType.IMAGE:
                data_uri = f"data:{block.media_type};base64,{block.data}"
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    }
                )
            elif block.content_type == ContentType.DOCUMENT:
                data_uri = f"data:{block.media_type};base64,{block.data}"
                item: dict[str, Any] = {
                    "type": "file",
                    "file": {"file_data": data_uri},
                }
                if block.filename:
                    item["file"]["filename"] = block.filename
                parts.append(item)
        # append the text prompt at the end
        parts.append({"type": "text", "text": prompt})
        return parts

    def _call_api_with_retries(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Call OpenAI API with retry logic for rate-limit (429) errors."""
        import openai as _openai

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                input_cost = input_tokens * self.config.price_per_input_token
                output_cost = output_tokens * self.config.price_per_output_token
                return {
                    "response": choice.message.content or "",
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "input_cost": round(input_cost, 6),
                        "output_cost": round(output_cost, 6),
                        "total_cost": round(input_cost + output_cost, 6),
                    },
                    "model": response.model,
                    "stop_reason": choice.finish_reason,
                }
            except _openai.RateLimitError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        "OpenAI rate limited, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                else:
                    self.logger.error("OpenAI rate limited after all retries")

        raise ModelInvocationError(f"OpenAI API error: {last_exc}") from last_exc

    def get_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop_sequences: list[str] | None = None,
        content_blocks: list[ContentBlock] | None = None,
    ) -> dict[str, Any]:
        """Call the OpenAI Chat Completions API and return the response.

        Parameters
        ----------
        prompt:
            User message content.
        system_prompt:
            Optional system instruction prepended to the conversation.
        temperature:
            Sampling temperature (overrides config default).
        max_tokens:
            Maximum response tokens (overrides config default).
        stop_sequences:
            Optional stop sequences (overrides config default).
        content_blocks:
            Optional multi-modal content blocks (images, PDFs, …).

        Returns
        -------
        dict with keys ``response``, ``usage``, ``model``.
        """
        try:
            self._validate_input(prompt)
            self.logger.debug(
                "Generating response",
                prompt_length=len(prompt),
                model=self.config.model_name,
            )

            messages: list[dict[str, Any]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            content = self._build_content_blocks(prompt, content_blocks)
            messages.append({"role": "user", "content": content})

            kwargs: dict[str, Any] = {
                "model": self.config.model_name,
                "max_completion_tokens": max_tokens or self.config.max_tokens,
                "temperature": (
                    temperature if temperature is not None else self.config.temperature
                ),
                "messages": messages,
            }

            seqs = (
                stop_sequences
                if stop_sequences is not None
                else self.config.stop_sequences
            )
            if seqs:
                kwargs["stop"] = seqs

            return self._call_api_with_retries(kwargs)

        except (TextTooLongError, ValueError):
            raise
        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("OpenAI API error", error=str(exc))
            raise ModelInvocationError(f"OpenAI API error: {exc}") from exc

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
        """Call OpenAI Chat Completions with function calling (strict mode).

        The schema is passed as ``parameters`` of a function tool with
        ``strict: true``, guaranteeing the response matches the schema exactly.
        """
        import json as _json

        import openai as _openai

        try:
            self._validate_input(prompt)
            self.logger.debug(
                "Generating structured response",
                prompt_length=len(prompt),
                model=self.config.model_name,
                tool_name=tool_name,
            )

            messages: list[dict[str, Any]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            kwargs: dict[str, Any] = {
                "model": self.config.model_name,
                "max_completion_tokens": max_tokens or self.config.max_tokens,
                "temperature": (
                    temperature if temperature is not None else self.config.temperature
                ),
                "messages": messages,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool_description
                            or f"Structured extraction via {tool_name}",
                            "parameters": schema,
                            "strict": True,
                        },
                    }
                ],
                "tool_choice": {
                    "type": "function",
                    "function": {"name": tool_name},
                },
            }

            last_exc: Exception | None = None
            for attempt in range(self.config.max_retries + 1):
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    choice = response.choices[0]
                    usage = response.usage

                    if not choice.message.tool_calls:
                        raise ModelInvocationError(
                            "OpenAI response did not contain tool_calls"
                        )

                    tool_call = choice.message.tool_calls[0]
                    parsed = _json.loads(tool_call.function.arguments)

                    input_tokens = usage.prompt_tokens if usage else 0
                    output_tokens = usage.completion_tokens if usage else 0
                    input_cost = input_tokens * self.config.price_per_input_token
                    output_cost = output_tokens * self.config.price_per_output_token

                    return {
                        "response": parsed,
                        "usage": {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "input_cost": round(input_cost, 6),
                            "output_cost": round(output_cost, 6),
                            "total_cost": round(input_cost + output_cost, 6),
                        },
                        "model": response.model,
                        "stop_reason": choice.finish_reason,
                    }
                except _openai.RateLimitError as exc:
                    last_exc = exc
                    if attempt < self.config.max_retries:
                        import time

                        delay = self.config.retry_base_delay * (2**attempt)
                        self.logger.warning(
                            "OpenAI rate limited, retrying",
                            attempt=attempt + 1,
                            delay=delay,
                        )
                        time.sleep(delay)
                    else:
                        self.logger.error("OpenAI rate limited after all retries")

            raise ModelInvocationError(f"OpenAI API error: {last_exc}") from last_exc

        except (TextTooLongError, ValueError):
            raise
        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("OpenAI structured API error", error=str(exc))
            raise ModelInvocationError(f"OpenAI API error: {exc}") from exc
