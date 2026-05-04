from dataclasses import dataclass
from typing import Literal, Union

from acai.logging.log_level import LogLevel

LogFormat = Literal["JSON", "FLAT"]


@dataclass
class LoggerConfig:
    """Configuration value object shared across all logging adapters."""

    service_name: str = "app"
    log_level: Union[LogLevel, int, str] = LogLevel.INFO
    json_output: bool = False
    # Output format: "JSON" uses Powertools structured logging,
    # "FLAT" forces the stdlib fallback with plain text output.
    log_format: LogFormat = "JSON"
