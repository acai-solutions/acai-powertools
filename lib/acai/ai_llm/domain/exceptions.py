"""LLM exception hierarchy."""


class LlmError(Exception):
    """Base exception for all LLM-related errors."""


class ModelInvocationError(LlmError):
    """Raised when the model invocation fails."""


class TextTooLongError(LlmError):
    """Raised when the input text exceeds the maximum allowed length."""


class ConfigurationError(LlmError):
    """LLM configuration is invalid."""
