from abc import ABC, abstractmethod
from typing import Any, Protocol, Union, runtime_checkable

from acai.logging.log_level import LogLevel


@runtime_checkable
class Loggable(Protocol):
    """Structural interface satisfied by both ``Logger`` and ``LoggerPort`` adapters.

    Use this as the type hint when a component needs to *call* log methods
    but should not care whether it receives a raw adapter or the domain
    ``Logger`` service.
    """

    # fmt: off
    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        ...

    def debug(self, message: str, **kwargs: Any) -> None:
        ...

    def info(self, message: str, **kwargs: Any) -> None:
        ...

    def warning(self, message: str, **kwargs: Any) -> None:
        ...

    def error(self, message: str, **kwargs: Any) -> None:
        ...

    def critical(self, message: str, **kwargs: Any) -> None:
        ...
    # fmt: on


class LoggerPort(ABC):
    """
    Outbound port defining the contract every logging adapter must fulfil.

    Hexagonal role
    ──────────────
    This is a *driven* (secondary) port.  Domain code and application services
    depend only on this interface; concrete adapters (console, CloudWatch, …)
    implement it.
    """

    VERSION: str = "1.0.6"  # inject_version

    # fmt: off
    @abstractmethod
    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        ...

    @abstractmethod
    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        ...
    # fmt: on

    # ── convenience helpers (implemented in terms of `log`) ───────────

    def debug(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.ERROR, message, exc_info=True, **kwargs)

    def flush(self) -> None:
        """Flush buffered output.  No-op by default; override in adapters that buffer."""
