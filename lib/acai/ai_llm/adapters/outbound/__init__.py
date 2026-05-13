"""Outbound LLM adapters."""

from __future__ import annotations

__all__ = [
    # acai_tags start: [anthropic]
    "AnthropicClaudeAdapter",
    # acai_tags end: [anthropic]
    # acai_tags start: [aws]
    "BedrockClaudeAdapter",
    # acai_tags end: [aws]
    # acai_tags start: [local]
    "LocalLlmAdapter",
    # acai_tags end: [local]
    # acai_tags start: [openai]
    "OpenAIAdapter",
    # acai_tags end: [openai]
]


def __getattr__(name: str):
    # acai_tags start: [anthropic]
    if name == "AnthropicClaudeAdapter":
        from acai.ai_llm.adapters.outbound.anthropic_claude_adapter import (
            AnthropicClaudeAdapter,
        )

        return AnthropicClaudeAdapter
    # acai_tags end: [anthropic]
    # acai_tags start: [aws]
    if name == "BedrockClaudeAdapter":
        from acai.ai_llm.adapters.outbound.bedrock_claude_adapter import (
            BedrockClaudeAdapter,
        )

        return BedrockClaudeAdapter
    # acai_tags end: [aws]
    # acai_tags start: [local]
    if name == "LocalLlmAdapter":
        from acai.ai_llm.adapters.outbound.local_llm_adapter import LocalLlmAdapter

        return LocalLlmAdapter
    # acai_tags end: [local]
    # acai_tags start: [openai]
    if name == "OpenAIAdapter":
        from acai.ai_llm.adapters.outbound.openai_adapter import OpenAIAdapter

        return OpenAIAdapter
    # acai_tags end: [openai]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
