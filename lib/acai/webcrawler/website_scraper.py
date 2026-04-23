"""Backward-compatibility shim — use ``acai.webcrawler`` instead."""

from acai.webcrawler.adapters.outbound.selenium_scraper import (
    SeleniumScraper as WebScraper,
)
from acai.webcrawler.domain.exceptions import (
    ConfigurationError,
    ScraperException,
    WebOperationError,
)
from acai.webcrawler.domain.scraper_config import WebConfig

__all__ = [
    "WebConfig",
    "WebScraper",
    "ScraperException",
    "WebOperationError",
    "ConfigurationError",
]
