class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""


class TextTooLongError(EmbeddingError):
    """Raised when input text exceeds maximum length."""


class ModelInvocationError(EmbeddingError):
    """Raised when there's an error invoking the model."""


class ConfigurationError(EmbeddingError):
    """Embedding configuration is invalid."""
