from __future__ import annotations

import logging
from typing import Any, List, Union

from acai.logging.ports import LoggerPort, LogLevel


class MultiLogger(LoggerPort):
    """Composite adapter that fans out log calls to multiple :class:`LoggerPort` adapters.

    Hexagonal role
    ──────────────
    Driven (composite) adapter.  Implements ``LoggerPort`` by delegating to
    an internal list of adapters, so the consumer only ever depends on the
    port interface.

    Context management (``push_context`` / ``pop_context``) is a domain
    concern handled by the ``Logger`` service that wraps this adapter —
    not by the adapter itself.

    Example::

        multi = MultiLogger([ConsoleLogger(), LokiLogger(), OpenSearchLogger()])
        logger = Logger(multi)
        logger.info("booted")          # sent to all three adapters
    """

    VERSION: str = "1.0.8"  # inject_version

    def __init__(self, loggers: List[LoggerPort]) -> None:
        self.loggers = loggers

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        for logger in self.loggers:
            logger.set_level(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        for logger in self.loggers:
            try:
                logger.log(level, message, **kwargs)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "MultiLogger delegate failed: %s. Message: %s", exc, message
                )

    def flush(self) -> None:
        """Flush all underlying adapters."""
        for logger in self.loggers:
            logger.flush()
