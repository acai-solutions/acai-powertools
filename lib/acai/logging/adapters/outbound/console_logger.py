import json
import logging
from typing import Any, Union

from acai.logging.ports import LoggerPort, LogLevel


class _JsonFormatter(logging.Formatter):
    """Formats each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra: dict = getattr(record, "extra_fields", {})
        if extra:
            data.update(extra)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


class _TextFormatter(logging.Formatter):
    """Human-readable formatter that appends structured extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        extra: dict = getattr(record, "extra_fields", {})
        if extra:
            message += " | " + " ".join(f"{k}={v}" for k, v in extra.items())
        return message


class ConsoleLogger(LoggerPort):
    """Outbound adapter — logs to the console (stdout/stderr).

    Hexagonal role
    ──────────────
    Driven adapter implementing ``LoggerPort``.  Suitable for local development,
    CLI tools, and non-Lambda workloads.
    """

    VERSION: str = "1.0.10"  # inject_version

    def __init__(
        self,
        logger_name: str = "console",
        log_format: str = "%(asctime)s - %(levelname)s - %(message)s",
        level: Union[LogLevel, int, str] = LogLevel.INFO,
        json_output: bool = False,
    ):
        self._logger = logging.getLogger(logger_name)

        if not self._logger.handlers:
            formatter: logging.Formatter = (
                _JsonFormatter() if json_output else _TextFormatter(log_format)
            )

            # Console handler
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            self._logger.addHandler(console)
            self._logger.propagate = False

        self.set_level(level)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._logger.setLevel(self._to_native(level))

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        native = self._to_native(level)
        exc_info = kwargs.pop("exc_info", None)
        extra = {"extra_fields": kwargs} if kwargs else {}
        self._logger.log(native, message, exc_info=exc_info, extra=extra)

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
