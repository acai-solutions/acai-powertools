import os

from acai.logging import LoggerContext, create_lambda_logger
from acai.logging.domain import Logger, LoggerConfig

__all__ = ["setup_logging", "Logger", "LoggerContext"]


def setup_logging(service_name: str, log_level: str | None = None) -> Logger:
    config = LoggerConfig(
        service_name=service_name,
        log_level=log_level or os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    return create_lambda_logger(config)
