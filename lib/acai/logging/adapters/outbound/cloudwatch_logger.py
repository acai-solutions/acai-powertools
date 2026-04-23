from __future__ import annotations

import json
import time
from typing import Any, Union

from acai.logging.ports import LoggerPort, LogLevel


class CloudWatchLogger(LoggerPort):
    """Outbound adapter — writes log events directly to a CloudWatch Log Group
    via the ``boto3`` ``logs`` client.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``LoggerPort``.  Suitable when you need to
    write to *arbitrary* CloudWatch Log Groups (not just the Lambda default
    log group).  Requires an initialised ``boto3.client("logs")``.

    Each ``log()`` call is translated into a single ``put_log_events`` API
    call using the current millisecond timestamp.
    """

    VERSION: str = "1.1.4"  # inject_version

    def __init__(
        self,
        boto3_logs_client: Any,
        log_group_name: str,
        log_stream_name: str,
        level: Union[LogLevel, int, str] = LogLevel.INFO,
        json_output: bool = True,
    ) -> None:
        self._client = boto3_logs_client
        self._log_group = log_group_name
        self._log_stream = log_stream_name
        self._json_output = json_output
        self._level: int = self._to_native(level)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        native = self._to_native(level)
        if native < self._level:
            return

        timestamp = int(round(time.time() * 1000))

        if self._json_output:
            payload: dict[str, Any] = {
                "timestamp": timestamp,
                "level": LogLevel.level_name(native),
                "message": message,
            }
            if kwargs:
                payload.update(kwargs)
            body = json.dumps(payload, default=str)
        else:
            body = message
            if kwargs:
                body += " | " + " ".join(f"{k}={v}" for k, v in kwargs.items())

        self._client.put_log_events(
            logGroupName=self._log_group,
            logStreamName=self._log_stream,
            logEvents=[{"timestamp": timestamp, "message": body}],
        )

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
