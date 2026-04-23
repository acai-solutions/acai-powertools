from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .exceptions import ConfigurationError


@dataclass
class WebConfig:
    """Configuration value object for web scraper adapters."""

    headless: bool = False
    default_timeout: int = 3
    page_load_delay: float = 1.0
    base_url: str = "https://www.fedlex.admin.ch"
    retry_attempts: int = 3
    retry_delay: float = 1.0
    driver_path: Optional[str] = None

    def __post_init__(self) -> None:
        if self.default_timeout <= 0:
            raise ConfigurationError("default_timeout must be positive")
        if self.page_load_delay < 0:
            raise ConfigurationError("page_load_delay cannot be negative")
        if self.driver_path and not Path(self.driver_path).exists():
            raise ConfigurationError(f"Driver path does not exist: {self.driver_path}")
