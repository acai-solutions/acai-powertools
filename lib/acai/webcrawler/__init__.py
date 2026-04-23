"""
acai.webcrawler — Hexagonal web scraping module
================================================

Public surface
--------------
- ``WebScraperPort``        — port contract (depend on this)
- ``WebConfig``             — shared configuration value object
- ``ScraperException``, ``WebOperationError``, ``ConfigurationError`` — exceptions
- ``create_scraper()``      — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.webcrawler.adapters.SeleniumScraper``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.webcrawler.domain import (
    ConfigurationError,
    ScraperException,
    WebConfig,
    WebOperationError,
)
from acai.webcrawler.ports import WebScraperPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_scraper(
    logger: Loggable,
    config: WebConfig | None = None,
) -> WebScraperPort:
    """Factory that builds a ready-to-use ``WebScraperPort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter for operational logging.
    config:
        Optional configuration.  Defaults are sensible for local development.
    """
    from acai.webcrawler.adapters.outbound.selenium_scraper import SeleniumScraper

    if config is None:
        config = WebConfig()
    return SeleniumScraper(logger=logger, config=config)


__all__ = [
    "WebScraperPort",
    "WebConfig",
    "ScraperException",
    "WebOperationError",
    "ConfigurationError",
    "create_scraper",
]
