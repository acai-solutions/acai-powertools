"""
acai.ai_embedding — Hexagonal embedding module
===============================================

Public surface
--------------
- ``EmbedderPort``          — port contract (depend on this)
- ``EmbedderConfig``        — shared configuration value object
- ``EmbeddingError``, ``TextTooLongError``, ``ModelInvocationError``,
  ``ConfigurationError`` — exceptions
- ``create_embedder()``     — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.ai_embedding.adapters.BedrockTitanEmbedder``
- ``acai.ai_embedding.adapters.OpenAILargeEmbedder``
- ``acai.ai_embedding.adapters.OpenAIAdaEmbedder``
- ``acai.ai_embedding.adapters.VoyageAIEmbedder``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.ai_embedding.domain import (
    ConfigurationError,
    EmbedderConfig,
    EmbeddingError,
    EmbeddingResult,
    ModelInvocationError,
    MultimodalEmbeddingResult,
    TextTooLongError,
)
from acai.ai_embedding.ports import EmbedderPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_embedder(
    logger: Loggable,
    *,
    provider: str = "openai_large",
    api_key: str = "",
    aws_profile: str | None = None,
    region: str = "eu-central-1",
    model_name: str | None = None,
) -> EmbedderPort:
    """Factory that builds a ready-to-use ``EmbedderPort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter.
    provider:
        One of ``"openai_large"``, ``"openai_ada"``, ``"bedrock_titan"``,
        ``"voyageai"``.
    api_key:
        API key for OpenAI or Voyage adapters.
    aws_profile:
        AWS profile name (Bedrock adapter only).
    region:
        AWS region (Bedrock adapter only).
    model_name:
        Override the default model name for any adapter.
    """
    if provider == "bedrock_titan":
        from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
            BedrockTitanConfig,
            BedrockTitanEmbedder,
        )

        cfg = BedrockTitanConfig(
            aws_profile=aws_profile,
            bedrock_service_region=region,
        )
        return BedrockTitanEmbedder(logger=logger, config=cfg)

    if provider == "openai_large":
        from acai.ai_embedding.adapters.outbound.openai_large_embedder import (
            OpenAILargeConfig,
            OpenAILargeEmbedder,
        )

        cfg = OpenAILargeConfig(openai_api_key=api_key)
        if model_name:
            cfg.model_name = model_name
        return OpenAILargeEmbedder(logger=logger, config=cfg)

    if provider == "openai_ada":
        from acai.ai_embedding.adapters.outbound.openai_ada_embedder import (
            OpenAIAdaConfig,
            OpenAIAdaEmbedder,
        )

        cfg = OpenAIAdaConfig(openai_api_key=api_key)
        if model_name:
            cfg.model_name = model_name
        return OpenAIAdaEmbedder(logger=logger, config=cfg)

    if provider == "voyageai":
        from acai.ai_embedding.adapters.outbound.voyageai_embedder import (
            VoyageAIConfig,
            VoyageAIEmbedder,
        )

        cfg = VoyageAIConfig(api_key=api_key)
        if model_name:
            cfg.model_name = model_name
        return VoyageAIEmbedder(logger=logger, config=cfg)

    raise ConfigurationError(
        f"Unknown provider '{provider}'. "
        "Choose from: openai_large, openai_ada, bedrock_titan, voyageai"
    )


__all__ = [
    "EmbedderPort",
    "EmbedderConfig",
    "EmbeddingResult",
    "MultimodalEmbeddingResult",
    "EmbeddingError",
    "TextTooLongError",
    "ModelInvocationError",
    "ConfigurationError",
    "create_embedder",
]
