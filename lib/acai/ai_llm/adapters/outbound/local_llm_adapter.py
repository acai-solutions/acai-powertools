"""LocalLlmAdapter — calls any OpenAI-compatible local inference server.

Hexagonal role
--------------
Outbound adapter implementing ``LlmPort``.  Uses the ``openai`` Python SDK
pointed at a custom ``base_url``, which makes it compatible with:

- **Ollama**  ``http://localhost:11434/v1``
- **vLLM**   ``http://localhost:8000/v1``
- **llama.cpp server**  ``http://localhost:8080/v1``
- Any other server that implements the OpenAI Chat Completions API.

When ``api_key`` is empty it defaults to ``"local"`` — most local servers
ignore the key but the SDK requires a non-empty string.
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
class LocalLlmConfig(LlmConfig):
    """Configuration for the local OpenAI-compatible adapter.

    ``base_url`` must point to the ``/v1`` endpoint of your local server, e.g.:
    - Ollama:    ``http://localhost:11434/v1``
    - vLLM:     ``http://localhost:8000/v1``
    """

    base_url: str = "http://localhost:11434/v1"
    api_key: str = "local"
    model_name: str = "llama3.1:8b"
    max_text_length: int = 128_000
    max_tokens: int = 4096
    temperature: float = 0.7
    stop_sequences: List[str] = field(default_factory=list)
    max_retries: int = 3
    retry_base_delay: float = 2.0


class LocalLlmAdapter(LlmPort):
    """LLM adapter for local OpenAI-compatible inference servers.

    Requires the ``openai`` package::

        pip install openai

    Example — Ollama::

        from acai.ai_llm.adapters.outbound.local_llm_adapter import (
            LocalLlmAdapter, LocalLlmConfig,
        )

        adapter = LocalLlmAdapter(
            config=LocalLlmConfig(
                base_url="http://localhost:11434/v1",
                model_name="llama3.1:8b",
            )
        )
        result = adapter.get_response("Was ist die Hauptstadt von Bayern?")
        print(result["response"])

    Example — vLLM::

        adapter = LocalLlmAdapter(
            config=LocalLlmConfig(
                base_url="http://localhost:8000/v1",
                model_name="meta-llama/Meta-Llama-3-8B-Instruct",
                api_key="token-abc",
            )
        )
    """

    VERSION: str = "1.0.6"  # inject_version

    def __init__(
        self,
        logger: Loggable | None = None,
        config: LocalLlmConfig | None = None,
    ) -> None:
        self.config = config or LocalLlmConfig()
        self.logger = logger or logging.getLogger("local_llm")
        self._initialize_client()
        self.logger.info(
            "Initialized LocalLlmAdapter",
            model=self.config.model_name,
            base_url=self.config.base_url,
        )

    def _initialize_client(self) -> None:
        try:
            import openai

            self.client = openai.OpenAI(
                api_key=self.config.api_key or "local",
                base_url=self.config.base_url,
            )
        except Exception as exc:
            self.logger.error("Failed to initialize local LLM client", error=str(exc))
            raise ModelInvocationError(
                f"Local LLM client initialization failed: {exc}"
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
        """Return plain string or OpenAI-compatible multi-block content list."""
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
                # Most local servers don't support file blocks yet — fall back
                # to embedding the base64 data as a text description so the
                # model at least receives the content.
                parts.append(
                    {
                        "type": "text",
                        "text": f"[Document: {block.filename or block.media_type}]\n{block.data}",
                    }
                )
        parts.append({"type": "text", "text": prompt})
        return parts

    def _call_api_with_retries(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Call the local API with retry logic for transient connection errors."""
        import openai as _openai

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                return {
                    "response": choice.message.content or "",
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    "model": response.model,
                    "stop_reason": choice.finish_reason,
                }
            except _openai.APIConnectionError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        f"Local LLM server unreachable, retrying (attempt={attempt + 1}, delay={delay}, base_url={self.config.base_url})"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"Local LLM server unreachable after all retries (base_url={self.config.base_url})"
                    )
            except _openai.APIStatusError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        f"Local LLM server error, retrying (attempt={attempt + 1}, delay={delay}, status_code={exc.status_code})"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"Local LLM server error after all retries (status_code={exc.status_code})"
                    )

        raise ModelInvocationError(
            f"Local LLM API error after {self.config.max_retries} retries: {last_exc}"
        ) from last_exc

    def get_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop_sequences: list[str] | None = None,
        content_blocks: list[ContentBlock] | None = None,
    ) -> dict[str, Any]:
        """Call the local inference server and return the response.

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
            Optional multi-modal content blocks (text, images).

        Returns
        -------
        dict with keys ``response``, ``usage``, ``model``, ``stop_reason``.
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
            self.logger.error(f"Local LLM API error: {exc}")
            raise ModelInvocationError(f"Local LLM API error: {exc}") from exc
