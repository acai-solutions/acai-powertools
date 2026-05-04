import logging
from enum import Enum
from typing import Union


class LogLevel(Enum):
    """Log severity levels used across all logging ports and adapters."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

    @classmethod
    def to_native(cls, level: Union["LogLevel", int, str]) -> int:
        """Convert any level representation to a native ``logging`` int."""
        if isinstance(level, cls):
            return level.value
        if isinstance(level, int):
            return level
        if isinstance(level, str):
            return getattr(logging, level.upper(), logging.INFO)
        return logging.INFO

    @classmethod
    def level_name(cls, native: int) -> str:
        """Return the human-readable name for a native level int."""
        _MAP = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        return _MAP.get(native, f"LVL{native}")
