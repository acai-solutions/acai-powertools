from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup


class WebScraperPort(ABC):
    """Outbound port defining the contract every web scraper adapter must fulfil.

    Hexagonal role
    ──────────────
    This is a *driven* (secondary) port.  Domain code and application services
    depend only on this interface; concrete adapters (Selenium, httpx, …)
    implement it.
    """

    VERSION: str = "1.0.0"  # inject_version

    @abstractmethod
    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page, returning a BeautifulSoup object."""
        ...

    @abstractmethod
    def extract_content(self, page: BeautifulSoup) -> Dict[str, Any]:
        """Extract relevant content from a parsed page."""
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Release any held resources (browser instances, connections, etc.)."""
        ...

    def __enter__(self) -> "WebScraperPort":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
