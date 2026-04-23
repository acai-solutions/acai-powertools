"""acai.ai_llm.adapters — Concrete LLM adapter implementations."""

from __future__ import annotations

__all__ = [
    "AnthropicClaudeAdapter",
    "BedrockClaudeAdapter",
    "LocalLlmAdapter",
    "OpenAIAdapter",
]


def __getattr__(name: str):
    if name == "AnthropicClaudeAdapter":
        from acai.ai_llm.adapters.outbound.anthropic_claude_adapter import (
            AnthropicClaudeAdapter,
        )

        return AnthropicClaudeAdapter
    if name == "BedrockClaudeAdapter":
        from acai.ai_llm.adapters.outbound.bedrock_claude_adapter import (
            BedrockClaudeAdapter,
        )

        return BedrockClaudeAdapter
    if name == "LocalLlmAdapter":
        from acai.ai_llm.adapters.outbound.local_llm_adapter import LocalLlmAdapter

        return LocalLlmAdapter
    if name == "OpenAIAdapter":
        from acai.ai_llm.adapters.outbound.openai_adapter import OpenAIAdapter

        return OpenAIAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
