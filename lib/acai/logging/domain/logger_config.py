from dataclasses import dataclass
from typing import Union

from acai.logging.log_level import LogLevel


@dataclass
class LoggerConfig:
    """Configuration value object shared across all logging adapters."""

    service_name: str = "app"
    log_level: Union[LogLevel, int, str] = LogLevel.INFO
    json_output: bool = False
