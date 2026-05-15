"""Anthropic Claude adapter — direct Anthropic API via the ``anthropic`` SDK.

Hexagonal role
--------------
Outbound adapter implementing ``LlmPort``.  Uses the official Anthropic
Python SDK to call Claude models directly (not via AWS Bedrock).

Compatible with the ``AnthropicShared`` utility pattern: when ``api_key``
is empty the SDK auto-reads ``ANTHROPIC_API_KEY`` from the environment.
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
class AnthropicClaudeConfig(LlmConfig):
    """Configuration specific to the Anthropic direct-API adapter.

    When ``api_key`` is empty the SDK falls back to the
    ``ANTHROPIC_API_KEY`` environment variable — identical to the
    ``AnthropicShared`` pattern.
    """

    api_key: str = ""
    model_name: str = "claude-sonnet-4-20250514"
    max_text_length: int = 200_000
    max_tokens: int = 4096
    temperature: float = 0.7
    stop_sequences: List[str] = field(default_factory=list)
    max_retries: int = 5
    retry_base_delay: float = 5.0
    fallback_model_name: str = ""
    fallback_after_retries: int = 2


class AnthropicClaudeAdapter(LlmPort):
    """LLM adapter that calls the Anthropic Messages API directly.

    Requires the ``anthropic`` package::

        pip install anthropic
    """

    VERSION: str = "1.0.10"  # inject_version

    def __init__(
        self,
        logger: Loggable | None = None,
        config: AnthropicClaudeConfig | None = None,
    ) -> None:
        self.config = config or AnthropicClaudeConfig()
        self.logger = logger or logging.getLogger("anthropic_claude")
        self._initialize_client()
        self.logger.info(
            "Initialized AnthropicClaudeAdapter",
            model=self.config.model_name,
        )

    def _initialize_client(self) -> None:
        """Create the Anthropic SDK client.

        If ``api_key`` is set it is passed explicitly; otherwise the SDK
        reads ``ANTHROPIC_API_KEY`` from the environment automatically.
        """
        try:
            import anthropic

            kwargs: dict[str, Any] = {}
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key

            self.client = anthropic.Anthropic(**kwargs)
        except Exception as exc:
            self.logger.error("Failed to initialize Anthropic client", error=str(exc))
            raise ModelInvocationError(
                f"Anthropic client initialization failed: {exc}"
            ) from exc

    def _validate_input(self, text: str) -> None:
        if not text or not isinstance(text, str):
            raise ValueError("Input text must be a non-empty string")
        if len(text) > self.config.max_text_length:
            raise TextTooLongError(
                f"Input text length ({len(text)}) exceeds maximum "
                f"({self.config.max_text_length})"
            )

    # Models that use adaptive thinking instead of temperature sampling.
    _ADAPTIVE_THINKING_PREFIXES = ("claude-opus-4-7",)

    def _model_uses_adaptive_thinking(self) -> bool:
        """Return True if the configured model uses adaptive thinking (no temperature)."""
        return self.config.model_name.startswith(self._ADAPTIVE_THINKING_PREFIXES)

    @staticmethod
    def _build_content_blocks(
        prompt: str, content_blocks: list[ContentBlock] | None
    ) -> str | list[dict[str, Any]]:
        """Return plain string or Anthropic multi-block content list."""
        if not content_blocks:
            return prompt

        parts: list[dict[str, Any]] = []
        for block in content_blocks:
            if block.content_type == ContentType.TEXT:
                parts.append({"type": "text", "text": block.data})
            elif block.content_type == ContentType.IMAGE:
                parts.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type,
                            "data": block.data,
                        },
                    }
                )
            elif block.content_type == ContentType.DOCUMENT:
                parts.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type,
                            "data": block.data,
                        },
                    }
                )
        # append the text prompt at the end so the model sees it last
        parts.append({"type": "text", "text": prompt})
        return parts

    def _call_api_with_retries(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Call Anthropic API with retry logic for overload (529) errors."""
        import anthropic as _anthropic

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            if (
                attempt == self.config.fallback_after_retries
                and self.config.fallback_model_name
            ):
                kwargs["model"] = self.config.fallback_model_name
                self.logger.warning(
                    "Switching to fallback model",
                    fallback_model=self.config.fallback_model_name,
                    after_retries=self.config.fallback_after_retries,
                )

            try:
                response = self.client.messages.create(**kwargs)
                return {
                    "response": response.content[0].text,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                    "model": response.model,
                    "stop_reason": response.stop_reason,
                }
            except _anthropic.APIStatusError as exc:
                if exc.status_code != 529:
                    raise
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        "Anthropic API overloaded, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        model=kwargs["model"],
                    )
                    time.sleep(delay)
                else:
                    self.logger.error("Anthropic API overloaded after all retries")

        raise ModelInvocationError(f"Anthropic API error: {last_exc}") from last_exc

    def _call_structured_api_with_retries(
        self, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Call Anthropic API for structured response with retry logic."""
        import anthropic as _anthropic

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            if (
                attempt == self.config.fallback_after_retries
                and self.config.fallback_model_name
            ):
                kwargs["model"] = self.config.fallback_model_name

            try:
                response = self.client.messages.create(**kwargs)
                tool_block = next(
                    (b for b in response.content if b.type == "tool_use"),
                    None,
                )
                if tool_block is None:
                    raise ModelInvocationError(
                        "Anthropic response did not contain a tool_use block"
                    )
                return {
                    "response": tool_block.input,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                    "model": response.model,
                    "stop_reason": response.stop_reason,
                }
            except _anthropic.APIStatusError as exc:
                if exc.status_code != 529:
                    raise ModelInvocationError(f"Anthropic API error: {exc}") from exc
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        "Anthropic API overloaded, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    time.sleep(delay)

        raise ModelInvocationError(
            f"Anthropic API error after retries: {last_exc}"
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
        """Call the Anthropic Messages API and return the response.

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

            kwargs: dict[str, Any] = {
                "model": self.config.model_name,
                "max_tokens": max_tokens or self.config.max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_content_blocks(prompt, content_blocks),
                    }
                ],
            }
            if not self._model_uses_adaptive_thinking():
                kwargs["temperature"] = (
                    temperature if temperature is not None else self.config.temperature
                )
            if system_prompt:
                kwargs["system"] = system_prompt

            seqs = (
                stop_sequences
                if stop_sequences is not None
                else self.config.stop_sequences
            )
            if seqs:
                kwargs["stop_sequences"] = seqs

            return self._call_api_with_retries(kwargs)

        except (TextTooLongError, ValueError):
            raise
        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("Anthropic API error", error=str(exc))
            raise ModelInvocationError(f"Anthropic API error: {exc}") from exc

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
        """Call Anthropic Messages API with tool-use to get structured output.

        The schema is passed as ``input_schema`` of a tool definition.
        ``tool_choice`` forces the model to use that specific tool,
        guaranteeing structured JSON output conforming to the schema.
        """
        try:
            self._validate_input(prompt)
            self.logger.debug(
                "Generating structured response",
                prompt_length=len(prompt),
                model=self.config.model_name,
                tool_name=tool_name,
            )

            kwargs: dict[str, Any] = {
                "model": self.config.model_name,
                "max_tokens": max_tokens or self.config.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [
                    {
                        "name": tool_name,
                        "description": tool_description
                        or f"Structured extraction via {tool_name}",
                        "input_schema": schema,
                    }
                ],
                "tool_choice": {"type": "tool", "name": tool_name},
            }
            if not self._model_uses_adaptive_thinking():
                kwargs["temperature"] = (
                    temperature if temperature is not None else self.config.temperature
                )
            if system_prompt:
                kwargs["system"] = system_prompt

            return self._call_structured_api_with_retries(kwargs)

        except (TextTooLongError, ValueError):
            raise
        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("Anthropic structured API error", error=str(exc))
            raise ModelInvocationError(f"Anthropic API error: {exc}") from exc

    # ------------------------------------------------------------------
    # Multi-turn tool calling — translate OpenAI <-> Anthropic shape
    # ------------------------------------------------------------------

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
        """Single-turn tool-calling step (OpenAI shape in/out, Anthropic native internally)."""
        try:
            self.logger.debug(
                "chat_with_tools",
                model=self.config.model_name,
                n_messages=len(messages),
                n_tools=len(tools),
            )

            anthropic_messages = self._oai_messages_to_anthropic(messages)
            anthropic_tools = self._oai_tools_to_anthropic(tools)
            anthropic_tool_choice = self._oai_tool_choice_to_anthropic(tool_choice)

            kwargs: dict[str, Any] = {
                "model": self.config.model_name,
                "max_tokens": max_tokens or self.config.max_tokens,
                "messages": anthropic_messages,
                "tools": anthropic_tools,
                "tool_choice": anthropic_tool_choice,
            }
            if not self._model_uses_adaptive_thinking():
                kwargs["temperature"] = (
                    temperature if temperature is not None else self.config.temperature
                )
            if system_prompt:
                kwargs["system"] = system_prompt

            return self._call_tool_api_with_retries(kwargs)

        except ModelInvocationError:
            raise
        except Exception as exc:
            self.logger.error("Anthropic chat_with_tools error", error=str(exc))
            raise ModelInvocationError(f"Anthropic API error: {exc}") from exc

    # ----- translation helpers -----

    @staticmethod
    def _oai_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """``[{type:function, function:{name, description, parameters}}]`` →
        ``[{name, description, input_schema}]``."""
        out = []
        for t in tools:
            fn = t.get("function", t)
            out.append(
                {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object"}),
                }
            )
        return out

    @staticmethod
    def _oai_tool_choice_to_anthropic(tc: Any) -> dict[str, Any]:
        if tc == "auto":
            return {"type": "auto"}
        if tc == "required":
            return {"type": "any"}
        if tc == "none":
            return {"type": "none"}  # ignored by Anthropic, but keep symmetry
        if isinstance(tc, dict) and tc.get("type") == "function":
            return {"type": "tool", "name": tc["function"]["name"]}
        return {"type": "auto"}

    @staticmethod
    def _oai_messages_to_anthropic(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Translate OpenAI message history → Anthropic content-block messages.

        Conversion rules:

        - ``user / content=str``        → ``user / [{type:text}]``
        - ``assistant / content + tool_calls``
                                        → ``assistant / [text-block?, tool_use…]``
        - ``tool / tool_call_id``       → ``user  / [{type:tool_result}]``

        Adjacent tool-result messages targeting the same assistant turn are
        coalesced into one ``user`` message (Anthropic requirement).
        """
        import json as _json

        out: list[dict[str, Any]] = []
        pending_tool_results: list[dict[str, Any]] = []

        def _flush_tool_results():
            if pending_tool_results:
                out.append({"role": "user", "content": list(pending_tool_results)})
                pending_tool_results.clear()

        for m in messages:
            role = m.get("role")
            if role == "system":
                # Anthropic system prompt is a separate kwarg; skip here.
                continue

            if role == "tool":
                pending_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m.get("content", ""),
                    }
                )
                continue

            _flush_tool_results()

            if role == "assistant":
                blocks: list[dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    fn = tc["function"]
                    args = fn.get("arguments")
                    if isinstance(args, str):
                        try:
                            args = _json.loads(args) if args else {}
                        except _json.JSONDecodeError:
                            args = {"_raw": args}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": fn["name"],
                            "input": args or {},
                        }
                    )
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
            elif role == "user":
                content = m.get("content", "")
                if isinstance(content, str):
                    out.append({"role": "user", "content": [{"type": "text", "text": content}]})
                else:
                    out.append({"role": "user", "content": content})

        _flush_tool_results()
        return out

    def _call_tool_api_with_retries(
        self, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Call Anthropic for a tool-using turn; return assistant-message dict in OAI shape."""
        import json as _json
        import time as _time

        import anthropic as _anthropic

        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            if (
                attempt == self.config.fallback_after_retries
                and self.config.fallback_model_name
            ):
                kwargs["model"] = self.config.fallback_model_name
            try:
                response = self.client.messages.create(**kwargs)

                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for blk in response.content:
                    if blk.type == "text":
                        text_parts.append(blk.text)
                    elif blk.type == "tool_use":
                        tool_calls.append(
                            {
                                "id": blk.id,
                                "type": "function",
                                "function": {
                                    "name": blk.name,
                                    "arguments": _json.dumps(blk.input or {}),
                                },
                            }
                        )

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(text_parts) if text_parts else None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls

                stop = (
                    "tool_use"
                    if response.stop_reason == "tool_use"
                    else (response.stop_reason or "end_turn")
                )

                return {
                    "message": assistant_msg,
                    "stop_reason": stop,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                    "model": response.model,
                }
            except _anthropic.APIStatusError as exc:
                if exc.status_code != 529:
                    raise ModelInvocationError(f"Anthropic API error: {exc}") from exc
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_base_delay * (2**attempt)
                    self.logger.warning(
                        "Anthropic overloaded (chat_with_tools), retrying",
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    _time.sleep(delay)
                else:
                    self.logger.error("Anthropic overloaded after all retries")

        raise ModelInvocationError(f"Anthropic API error: {last_exc}") from last_exc
