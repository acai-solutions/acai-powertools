"""LLM configuration value object."""

from __future__ import annotations

from dataclasses import dataclass

from acai.ai_llm.domain.exceptions import ConfigurationError


@dataclass
class LlmConfig:
    """Base configuration shared across LLM adapters.

    Adapter-specific subclasses may extend this with extra fields
    (e.g. ``aws_profile`` for Bedrock, ``api_key`` for Anthropic).
    """

    max_text_length: int = 200_000
    max_tokens: int = 4096
    temperature: float = 0.7
    retry_attempts: int = 3
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if self.max_text_length <= 0:
            raise ConfigurationError("max_text_length must be positive")
        if self.max_tokens <= 0:
            raise ConfigurationError("max_tokens must be positive")
        if not (0.0 <= self.temperature <= 1.0):
            raise ConfigurationError("temperature must be between 0.0 and 1.0")
