from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass
class EmbedderConfig:
    """Configuration value object shared across embedding adapters."""

    max_text_length: int = 8192
    timeout_seconds: int = 30
    retry_attempts: int = 3

    def __post_init__(self) -> None:
        if self.max_text_length <= 0:
            raise ConfigurationError("max_text_length must be positive")
        if self.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive")
