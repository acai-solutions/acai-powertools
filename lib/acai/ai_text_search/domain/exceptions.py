class TextSearchError(Exception):
    """Base exception for text-search errors."""


class ConfigurationError(TextSearchError):
    """Raised when configuration is invalid or incomplete."""
