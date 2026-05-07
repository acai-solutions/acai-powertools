import json
import logging
import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

from acai.logging.log_level import LogLevel
from acai.logging.ports import LoggerPort


class Logger:
    """Domain service that decorates a ``LoggerPort`` with a context stack.

    Hexagonal role
    ──────────────
    This is an *application service* (not an adapter).  It lives inside the
    hexagon and delegates actual I/O to the injected ``LoggerPort`` adapter.
    It satisfies the ``Loggable`` protocol so it can be passed anywhere a
    logger-like object is expected.
    """

    def __init__(self, logger: LoggerPort):
        self._logger = logger
        self._context_stack: list[dict[str, Any]] = []

    # ── context stack ─────────────────────────────────────────────────

    def push_context(self, context: dict[str, Any]) -> None:
        if context:
            self._context_stack.append(context.copy())

    def pop_context(self) -> dict[str, Any] | None:
        return self._context_stack.pop() if self._context_stack else None

    def get_current_context(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for ctx in self._context_stack:
            merged.update(ctx)
        return merged

    def clear_context(self) -> None:
        self._context_stack.clear()

    # aliases used by aws-lambda-powertools convention
    append_keys = push_context
    remove_keys = pop_context

    # ── LoggerPort delegation ─────────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._logger.set_level(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        merged = self.get_current_context()
        merged.update(kwargs)
        try:
            self._logger.log(level, message, **merged)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Logger failed: %s. Message: %s", exc, message
            )

    # ── convenience helpers ───────────────────────────────────────────

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
        kwargs.pop("exc_info", None)
        self.log(LogLevel.ERROR, message, exc_info=True, **kwargs)

    def flush(self) -> None:
        """Flush buffered output via the underlying adapter."""
        self._logger.flush()

    # ── utilities ─────────────────────────────────────────────────────

    def disable_noisy_logging(self) -> None:
        for name in ("boto3", "botocore", "nose", "s3transfer", "urllib3"):
            logging.getLogger(name).setLevel(logging.WARNING)

    def inject_lambda_context(
        self,
        handler: Optional[Callable] = None,
        include_event: bool = True,
        include_context: bool = True,
        include_response: bool = False,
        include_cold_start: bool = True,
        log_exceptions: bool = True,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        """Decorator that enriches logs with AWS Lambda invocation metadata.

        Supports both ``@logger.inject_lambda_context`` (no parentheses)
        and ``@logger.inject_lambda_context(...)`` (with keyword arguments).
        """

        def decorator(handler: Callable) -> Callable:
            is_cold_start = True

            @wraps(handler)
            def wrapper(event: Any, context: Any) -> Any:
                nonlocal is_cold_start

                ctx = self._build_lambda_context(
                    event,
                    context,
                    include_event=include_event,
                    include_context=include_context,
                    include_cold_start=include_cold_start,
                    is_cold_start=is_cold_start,
                    extra_context=extra_context,
                )
                if include_cold_start:
                    is_cold_start = False

                with LoggerContext(self, ctx):
                    return self._run_handler(
                        handler,
                        event,
                        context,
                        include_response=include_response,
                        log_exceptions=log_exceptions,
                    )

            return wrapper

        # Support @inject_lambda_context without parentheses
        if handler is not None:
            return decorator(handler)
        return decorator

    def _build_lambda_context(
        self,
        event: Any,
        context: Any,
        *,
        include_event: bool,
        include_context: bool,
        include_cold_start: bool,
        is_cold_start: bool,
        extra_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}

        if include_context and context:
            ctx.update(
                {
                    "aws_request_id": getattr(context, "aws_request_id", None),
                    "function_name": getattr(context, "function_name", None),
                    "function_version": getattr(context, "function_version", None),
                    "memory_limit_mb": getattr(context, "memory_limit_in_mb", None),
                    "remaining_time_ms": getattr(
                        context, "get_remaining_time_in_millis", lambda: None
                    )(),
                    "log_group_name": getattr(context, "log_group_name", None),
                    "log_stream_name": getattr(context, "log_stream_name", None),
                }
            )

        if include_event and event:
            try:
                event_str = json.dumps(event, default=str)
                if len(event_str) > 1000:
                    event_str = event_str[:1000] + "... [truncated]"
                ctx["event"] = event_str
            except (TypeError, ValueError):
                ctx["event"] = str(event)[:1000]

        if include_cold_start:
            ctx["cold_start"] = is_cold_start

        if extra_context:
            ctx.update(extra_context)

        return ctx

    def _run_handler(
        self,
        handler: Callable,
        event: Any,
        context: Any,
        *,
        include_response: bool,
        log_exceptions: bool,
    ) -> Any:
        try:
            self.info("Lambda function started", handler_name=handler.__name__)
            result = handler(event, context)

            if include_response:
                try:
                    resp = json.dumps(result, default=str)
                    if len(resp) > 500:
                        resp = resp[:500] + "... [truncated]"
                    self.info("Lambda function completed", response=resp)
                except (TypeError, ValueError):
                    self.info(
                        "Lambda function completed",
                        response=str(result)[:500],
                    )
            else:
                self.info("Lambda function completed successfully")

            return result

        except Exception as exc:
            if log_exceptions:
                self.error(
                    "Lambda function failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    traceback=traceback.format_exc(),
                )
            raise


class LoggerContext:
    """Context manager for scoped context push/pop on a ``Logger``."""

    def __init__(self, logger: Logger, context_dict: Dict[str, Any]):
        self._logger = logger
        self._context = context_dict
        self._pushed = False

    def __enter__(self) -> "LoggerContext":
        self._logger.push_context(self._context)
        self._pushed = True
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._pushed:
            self._logger.pop_context()
