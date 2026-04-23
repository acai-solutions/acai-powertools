class ScraperException(Exception):
    """Base exception for all scraper-related errors."""


class WebOperationError(ScraperException):
    """A web operation (navigation, element interaction) failed."""


class ConfigurationError(ScraperException):
    """Scraper configuration is invalid."""
