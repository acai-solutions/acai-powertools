import inspect
import logging
import os
from typing import Any, Union

from acai.logging.ports import LoggerPort, LogLevel

try:
    from aws_lambda_powertools import Logger as PowerToolsLogger

    _HAS_POWERTOOLS = True
except ImportError:
    _HAS_POWERTOOLS = False


class AwsLambdaPtLogger(LoggerPort):
    """Outbound adapter — logs via *aws-lambda-powertools* ``Logger`` if available,
    otherwise falls back to the standard ``logging`` module.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``LoggerPort``.  Designed for AWS Lambda
    functions where structured logging with request context, correlation IDs,
    and CloudWatch Logs Insights integration is desired.
    """

    VERSION: str = "1.0.5"

    def __init__(
        self,
        service: str = "my-service",
        level: Union[LogLevel, int, str, None] = None,
    ):
        if _HAS_POWERTOOLS:
            self._logger = PowerToolsLogger(service=service)
        else:
            self._logger = logging.getLogger(service)
            if not self._logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(
                    logging.Formatter(
                        f"%(asctime)s %(levelname)s [{service}] %(message)s"
                    )
                )
                self._logger.addHandler(handler)
        initial = level if level is not None else os.getenv("LOG_LEVEL", "INFO")
        self.set_level(initial)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        native = self._to_native(level)
        if hasattr(self._logger, "_logger"):
            # PowerTools Logger wraps a stdlib logger internally
            self._logger._logger.setLevel(native)
        else:
            self._logger.setLevel(native)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        native = self._to_native(level)
        caller_location = self._get_caller_location()
        if _HAS_POWERTOOLS and kwargs:
            # PowerToolsLogger: append extra keys as structured data,
            # then remove them after logging to avoid leaking state.
            self._logger.append_keys(location=caller_location, **kwargs)
            self._logger.log(native, message, stacklevel=self._STACKLEVEL)
            self._logger.remove_keys(["location"] + list(kwargs.keys()))
        elif kwargs:
            # stdlib fallback: include extras in the message
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            self._logger.log(native, f"{message} | {extras}")
        else:
            if _HAS_POWERTOOLS:
                self._logger.append_keys(location=caller_location)
                self._logger.log(native, message, stacklevel=self._STACKLEVEL)
                self._logger.remove_keys(["location"])
            else:
                self._logger.log(native, message)

    # ── helpers ───────────────────────────────────────────────────────

    # Number of internal frames between business code and this adapter:
    #   business_code -> Logger.log/info/... -> LoggerPort.log -> here
    _ACAI_FRAME_MODULES = frozenset(
        {
            "acai.logging.domain.logger",
            "acai.logging.adapters.outbound.aws_lambda_pt_logger",
        }
    )

    def _get_caller_location(self) -> str:
        """Walk the stack to find the first frame outside the acai logging layer."""
        for frame_info in inspect.stack():
            module = frame_info.frame.f_globals.get("__name__", "")
            if module not in self._ACAI_FRAME_MODULES:
                filename = os.path.basename(frame_info.filename)
                return f"{filename}:{frame_info.lineno}"
        return "unknown"

    # Prevent PowerTools from overwriting our explicit location key.
    # stacklevel high enough so PT itself doesn't resolve a meaningful frame.
    _STACKLEVEL = 100

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
