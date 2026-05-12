"""Mistral adapter — calls Mistral models via La Plateforme (api.mistral.ai).

Hexagonal role
--------------
Outbound adapter implementing ``LlmPort``.  Uses the ``openai`` Python SDK
pointed at Mistral's OpenAI-compatible endpoint.

Key properties of La Plateforme:
- EU-hosted, GDPR-compliant — data stays in the EU.
- All Mistral models available (Large 3, Large 3 2512, etc.).
- 262k context window on Large 3.
- OpenAI SDK compatible: ``base_url="https://api.mistral.ai/v1"``.

When ``api_key`` is empty the SDK falls back to the ``MISTRAL_API_KEY``
environment variable.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, List

from acai.ai_llm.domain.content_block import ContentBlock, ContentType
from acai.ai_llm.domain.exceptions import ModelInvocationError, TextTooLongError
from acai.ai_llm.domain.llm_config import LlmConfig
from acai.ai_llm.ports.llm_port import LlmPort
from acai.logging import Loggable


@dataclass
class MistralConfig(LlmConfig):
    """Configuration specific to the Mistral adapter.

    When ``api_key`` is empty the adapter reads ``MISTRAL_API_KEY`` from
    the environment — matching the Mistral SDK convention.
    """

    base_url: str = "https://api.mistral.ai/v1"
    api_key: str = ""
    model_name: str = "mistral-large-latest"
    max_text_length: int = 262_000
    max_tokens: int = 4096
    temperature: float = 0.7
    stop_sequences: List[str] = field(default_factory=list)
    max_retries: int = 5
    retry_base_delay: float = 5.0
    price_per_input_token: float = 0.50 / 1_000_000   # $0.50 / 1M
    price_per_output_token: float = 1.50 / 1_000_000   # $1.50 / 1M


class MistralAdapter(LlmPort):
    """LLM adapter that calls Mistral models via La Plateforme.

    Requires the ``openai`` package (Mistral's API is OpenAI-compatible)::

        pip install openai

    Example::

        from acai.ai_llm.adapters.outbound.mistral_adapter import (
            MistralAdapter, MistralConfig,
        )

        adapter = MistralAdapter(
            config=MistralConfig(
                api_key="your-mistral-key",
                model_name="mistral-large-latest",
            )
        )
        result = adapter.get_response("Was ist ein Mietvertrag?")
        print(result["response"])
    """

    VERSION: str = "1.0.9"  # inject_version

    def __init__(
        self,
        logger: Loggable | None = None,
        config: MistralConfig | None = None,
    ) -> None:
        self.config = config or MistralConfig()
        self.logger = logger or logging.getLogger("mistral")
        self._initialize_client()
        self.logger.info(
            "Initialized MistralAdapter",
            model=self.config.model_name,
            base_url=self.config.base_url,
        )

    def _initialize_client(self) -> None:
        try:
            import openai

            api_key = (
                self.config.api_key
                or os.environ.get("MISTRAL_API_KEY", "")
            )
            if not api_key:
                raise ModelInvocationError(
                    "No Mistral API key provided. Set api_key in MistralConfig "
                    "or the MISTRAL_API_KEY environment variable."
                )

            self.client = openai.OpenAI(
                api_key=api_key,
                base_url=self.config.base_url,
            )
        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("Failed to initialize Mistral client", error=str(exc))
            raise ModelInvocationError(
                f"Mistral client initialization failed: {exc}"
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
        """Return plain string or OpenAI-style multi-block content list."""
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
                # Mistral doesn't natively support document blocks — pass as text.
                parts.append(
                    {
                        "type": "text",
                        "text": f"[Document: {block.filename or block.media_type}]\n{block.data}",
                    }
                )
        parts.append({"type": "text", "text": prompt})
        return parts

    def _call_api_with_retries(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Call Mistral API with retry logic for rate-limit (429) errors."""
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
                        "Mistral rate limited, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                else:
                    self.logger.error("Mistral rate limited after all retries")

        raise ModelInvocationError(f"Mistral API error: {last_exc}") from last_exc

    def _call_structured_api_with_retries(
        self, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Call Mistral API for structured (tool-use) responses with retries."""
        import json as _json

        import openai as _openai

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                usage = response.usage

                if not choice.message.tool_calls:
                    raise ModelInvocationError(
                        "Mistral response did not contain tool_calls"
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
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        "Mistral rate limited, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)
                else:
                    self.logger.error("Mistral rate limited after all retries")

        raise ModelInvocationError(f"Mistral API error: {last_exc}") from last_exc

    def get_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop_sequences: list[str] | None = None,
        content_blocks: list[ContentBlock] | None = None,
    ) -> dict[str, Any]:
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
                "max_tokens": max_tokens or self.config.max_tokens,
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
            self.logger.error("Mistral API error", error=str(exc))
            raise ModelInvocationError(f"Mistral API error: {exc}") from exc

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
        """Call Mistral with function calling for structured output."""
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
                "max_tokens": max_tokens or self.config.max_tokens,
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
                        },
                    }
                ],
                "tool_choice": "any",
            }

            return self._call_structured_api_with_retries(kwargs)

        except (TextTooLongError, ValueError):
            raise
        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("Mistral structured API error", error=str(exc))
            raise ModelInvocationError(f"Mistral API error: {exc}") from exc
