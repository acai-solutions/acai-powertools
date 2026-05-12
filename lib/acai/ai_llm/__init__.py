"""
acai.ai_llm — Hexagonal LLM module
====================================

Public surface
--------------
- ``LlmPort``               — port contract (depend on this)
- ``LlmConfig``             — shared configuration value object
- ``LlmError``, ``ModelInvocationError``, ``TextTooLongError``,
  ``ConfigurationError``    — exceptions
- ``create_llm()``          — factory that wires adapters
- ``generate_prompt_evaluation_report()`` — HTML evaluation report

Adapters (import directly when needed)
--------------------------------------
- ``acai.ai_llm.adapters.AnthropicClaudeAdapter``
- ``acai.ai_llm.adapters.BedrockClaudeAdapter``
- ``acai.ai_llm.adapters.LocalLlmAdapter``
- ``acai.ai_llm.adapters.MistralAdapter``
- ``acai.ai_llm.adapters.OpenAIAdapter``

Backward compatibility
----------------------
- ``LlmProtocol`` — alias for ``LlmPort``
- ``PromptError`` — alias for ``LlmError``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.ai_llm.application import generate_prompt_evaluation_report
from acai.ai_llm.domain import (
    ConfigurationError,
    ContentBlock,
    ContentType,
    LlmConfig,
    LlmError,
    LlmPricingTable,
    ModelInvocationError,
    TextTooLongError,
)
from acai.ai_llm.ports import LlmPort

# Backward compatibility aliases
LlmProtocol = LlmPort
PromptError = LlmError

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def _create_anthropic_llm(
    logger: Loggable,
    api_key: str,
    model_name: str | None,
    max_tokens: int,
    temperature: float,
    fallback_model_name: str,
) -> LlmPort:
    from acai.ai_llm.adapters.outbound.anthropic_claude_adapter import (
        AnthropicClaudeAdapter,
        AnthropicClaudeConfig,
    )

    cfg = AnthropicClaudeConfig(
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        fallback_model_name=fallback_model_name,
    )
    if model_name:
        cfg.model_name = model_name
    return AnthropicClaudeAdapter(logger=logger, config=cfg)


def _create_bedrock_claude_llm(
    logger: Loggable,
    aws_profile: str | None,
    region: str,
    model_name: str | None,
    max_tokens: int,
    temperature: float,
) -> LlmPort:
    from acai.ai_llm.adapters.outbound.bedrock_claude_adapter import (
        BedrockClaudeAdapter,
        BedrockClaudeConfig,
    )

    cfg = BedrockClaudeConfig(
        aws_profile=aws_profile,
        bedrock_service_region=region,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if model_name:
        cfg.model_id = model_name
    return BedrockClaudeAdapter(logger=logger, config=cfg)


def _create_openai_llm(
    logger: Loggable,
    api_key: str,
    model_name: str | None,
    max_tokens: int,
    temperature: float,
    price_per_input_token: float,
    price_per_output_token: float,
) -> LlmPort:
    from acai.ai_llm.adapters.outbound.openai_adapter import (
        OpenAIAdapter,
        OpenAIConfig,
    )

    cfg = OpenAIConfig(
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        price_per_input_token=price_per_input_token,
        price_per_output_token=price_per_output_token,
    )
    if model_name:
        cfg.model_name = model_name
    return OpenAIAdapter(logger=logger, config=cfg)


def _create_mistral_llm(
    logger: Loggable,
    api_key: str,
    model_name: str | None,
    max_tokens: int,
    temperature: float,
    price_per_input_token: float,
    price_per_output_token: float,
) -> LlmPort:
    from acai.ai_llm.adapters.outbound.mistral_adapter import (
        MistralAdapter,
        MistralConfig,
    )

    cfg = MistralConfig(
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        price_per_input_token=price_per_input_token,
        price_per_output_token=price_per_output_token,
    )
    if model_name:
        cfg.model_name = model_name
    return MistralAdapter(logger=logger, config=cfg)


def _create_local_llm(
    logger: Loggable,
    api_key: str,
    model_name: str | None,
    max_tokens: int,
    temperature: float,
    base_url: str,
) -> LlmPort:
    from acai.ai_llm.adapters.outbound.local_llm_adapter import (
        LocalLlmAdapter,
        LocalLlmConfig,
    )

    cfg = LocalLlmConfig(
        base_url=base_url,
        api_key=api_key or "local",
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if model_name:
        cfg.model_name = model_name
    return LocalLlmAdapter(logger=logger, config=cfg)


def create_llm(
    logger: Loggable,
    *,
    provider: str = "anthropic",
    api_key: str = "",
    aws_profile: str | None = None,
    region: str = "eu-central-1",
    model_name: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    fallback_model_name: str = "",
    price_per_input_token: float = 0.0,
    price_per_output_token: float = 0.0,
    base_url: str = "http://localhost:11434/v1",
) -> LlmPort:
    """Factory that builds a ready-to-use ``LlmPort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter.
    provider:
        One of ``"anthropic"`` or ``"bedrock_claude"``.
    api_key:
        API key (Anthropic adapter only).
    aws_profile:
        AWS profile name (Bedrock adapter only).
    region:
        AWS region (Bedrock adapter only).
    model_name:
        Override the default model name.
    max_tokens:
        Maximum tokens for the response.
    temperature:
        Sampling temperature.
    fallback_model_name:
        Optional fallback model to use after repeated overload errors.
    """
    if provider == "anthropic":
        return _create_anthropic_llm(
            logger, api_key, model_name, max_tokens, temperature, fallback_model_name
        )

    if provider == "bedrock_claude":
        return _create_bedrock_claude_llm(
            logger, aws_profile, region, model_name, max_tokens, temperature
        )

    if provider == "openai":
        return _create_openai_llm(
            logger,
            api_key,
            model_name,
            max_tokens,
            temperature,
            price_per_input_token,
            price_per_output_token,
        )

    if provider == "mistral":
        return _create_mistral_llm(
            logger,
            api_key,
            model_name,
            max_tokens,
            temperature,
            price_per_input_token,
            price_per_output_token,
        )

    if provider == "local":
        return _create_local_llm(
            logger, api_key, model_name, max_tokens, temperature, base_url
        )

    raise ConfigurationError(
        f"Unknown provider '{provider}'. Choose from: anthropic, bedrock_claude, local, mistral, openai"
    )


__all__ = [
    # Hexagonal public API
    "LlmPort",
    "LlmConfig",
    "LlmPricingTable",
    "ContentBlock",
    "ContentType",
    "LlmError",
    "ModelInvocationError",
    "TextTooLongError",
    "ConfigurationError",
    "create_llm",
    "generate_prompt_evaluation_report",
    # Backward compatibility aliases
    "LlmProtocol",
    "PromptError",
]
