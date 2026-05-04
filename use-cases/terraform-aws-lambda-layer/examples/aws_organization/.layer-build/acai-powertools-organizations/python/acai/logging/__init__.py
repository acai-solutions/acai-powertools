"""
acai.logging — Hexagonal logging module
========================================

Public surface
--------------
- ``LoggerPort``, ``LogLevel``  — port contract (depend on this)
- ``LoggerConfig``              — shared configuration value object
- ``Logger``, ``LoggerContext``    — domain service (context stack + Lambda decorator)
- ``create_logger()``              — factory that wires adapters for you

Adapters (import directly when needed)
--------------------------------------
- ``acai.logging.adapters.ConsoleLogger``
- ``acai.logging.adapters.AwsLambdaPtLogger``
- ``acai.logging.adapters.CloudWatchLogger``
- ``acai.logging.adapters.FileLogger``
"""

from __future__ import annotations

from acai.logging.domain import Logger, LoggerConfig, LoggerContext
from acai.logging.log_level import LogLevel
from acai.logging.ports import Loggable, LoggerPort


# acai_tags start: [console]
def create_logger(config: LoggerConfig | None = None) -> Logger:
    """Factory that builds a ready-to-use ``Logger``.

    Parameters
    ----------
    config:
        Optional configuration.  Defaults are sensible for local development.
    """
    if config is None:
        config = LoggerConfig()

    from acai.logging.adapters.outbound.console_logger import ConsoleLogger

    adapter = ConsoleLogger(
        logger_name=config.service_name,
        level=config.log_level,
        json_output=config.json_output,
    )

    logger = Logger(adapter)
    logger.disable_noisy_logging()
    return logger


# acai_tags end: [console]


# acai_tags start: [aws]
def create_lambda_logger(
    config: LoggerConfig | None = None,
) -> Logger:
    """Factory that builds a ready-to-use ``Logger``.

    Parameters
    ----------
    config:
        Optional configuration.  Defaults are sensible for local development.
    """
    if config is None:
        config = LoggerConfig()

    from acai.logging.adapters.outbound.aws_lambda_pt_logger import AwsLambdaPtLogger

    adapter = AwsLambdaPtLogger(
        service=config.service_name,
        level=config.log_level,
        use_powertools=config.log_format != "FLAT",
    )

    logger = Logger(adapter)
    logger.disable_noisy_logging()
    return logger


# acai_tags end: [aws]


# acai_tags start: [local]
# isort: off
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from acai.storage.ports import StorageWriter
# isort: on


def create_local_logger(
    config: LoggerConfig | None = None,
    *,
    storage: StorageWriter,
    log_path: str | None = None,
) -> Logger:
    """Factory that builds a ready-to-use ``Logger``.

    Parameters
    ----------
    config:
        Optional configuration.  Defaults are sensible for local development.
    storage:
        When provided (together with *log_path*), the underlying adapter is
        ``FileLogger`` which persists log lines via the given ``StorageWriter``.
    log_path:
        File path used by ``FileLogger``.  Required when *storage* is set.
    """
    if config is None:
        config = LoggerConfig()

    if log_path is None:
        raise ValueError("log_path is required when storage is provided")
    from acai.logging.adapters.outbound.file_logger import FileLogger

    adapter: LoggerPort = FileLogger(
        storage=storage,
        log_path=log_path,
        level=config.log_level,
        json_output=config.json_output,
        logger_name=config.service_name,
    )

    logger = Logger(adapter)
    logger.disable_noisy_logging()
    return logger


# acai_tags end: [local]


__all__ = [
    "LoggerPort",
    "Loggable",
    "LogLevel",
    "LoggerConfig",
    "Logger",
    "LoggerContext",
    "create_logger",
    # acai_tags start: [aws]
    "create_lambda_logger",
    # acai_tags end: [aws]
    # acai_tags start: [local]
    "create_local_logger",
    # acai_tags end: [local]
]
