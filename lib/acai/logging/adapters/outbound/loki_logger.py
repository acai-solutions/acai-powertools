import json
import logging
import os
import time
import traceback
from typing import Any, Dict, Optional, Union

import requests
from acai.logging.ports import LoggerPort, LogLevel


class LokiLogger(LoggerPort):
    """Grafana Loki implementation of :class:`LoggerPort`.

    Hexagonal role
    ──────────────
    Driven adapter.  Sends log messages to a Loki instance using the HTTP
    push API, with runtime log-level filtering and structured logging.

    Environment variables (can be overridden via arguments):
    ─────────────────────────────────────────────────────────
    * **LOKI_ENABLED** - ``"true"`` to activate (default: ``"false"``).
    * **LOKI_URL** - Push endpoint URL.
    * **LOKI_API_TOKEN** - Bearer token for authentication.
    * **LOKI_USERNAME** / **LOKI_PASSWORD** - Basic auth credentials.
    * **SERVICE_NAME** - Service identifier (default: ``"my-service"``).
    * **LOG_LEVEL** - Initial log level (DEBUG, INFO, …).
    """

    VERSION: str = "1.0.9"  # inject_version

    def __init__(
        self,
        loki_url: Optional[str] = None,
        service_name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        timeout: int = 2,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        enabled: Optional[bool] = None,
        use_env: bool = True,
        level: Union[LogLevel, int, str, None] = None,
    ) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else (
                os.getenv("LOKI_ENABLED", "false").lower() == "true"
                if use_env
                else False
            )
        )

        self.loki_url = loki_url or (os.getenv("LOKI_URL") if use_env else None)
        self.token = token or (os.getenv("LOKI_API_TOKEN") if use_env else None)
        self.username = username or (os.getenv("LOKI_USERNAME") if use_env else None)
        self.password = password or (os.getenv("LOKI_PASSWORD") if use_env else None)
        self.auth_enabled = bool(self.token or (self.username and self.password))

        self.timeout = timeout

        self.service_name = service_name or os.getenv("SERVICE_NAME", "my-service")
        self.labels: Dict[str, str] = {"job": self.service_name}
        if labels:
            self.labels.update(labels)

        self._fallback_logger = logging.getLogger("loki-fallback")
        if not self._fallback_logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self._fallback_logger.addHandler(handler)
            self._fallback_logger.setLevel(logging.INFO)

        initial = level if level is not None else os.getenv("LOG_LEVEL", LogLevel.INFO)
        self.set_level(initial)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._min_level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        if not self.enabled:
            return
        if not self.loki_url:
            self._fallback_logger.warning(
                "[LOKI] Logging enabled but LOKI_URL not set."
            )
            return

        numeric = self._to_native(level)
        if numeric < self._min_level:
            return

        level_str = (
            level.name.lower() if isinstance(level, LogLevel) else str(level).lower()
        )
        full_msg = self._format_message(message, **kwargs)
        stream = self.labels.copy()
        stream["level"] = level_str

        payload = {
            "streams": [
                {
                    "stream": stream,
                    "values": [[str(int(time.time() * 1e9)), full_msg]],
                }
            ]
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        auth = None
        if self.auth_enabled:
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            else:
                auth = (self.username, self.password)

        try:
            requests.post(
                self.loki_url,
                json=payload,
                headers=headers,
                auth=auth,
                timeout=self.timeout,
            )
        except Exception as exc:
            self._fallback_logger.warning("[LOKI] Logging failed: %s", exc)

    # ── internals ─────────────────────────────────────────────────────

    @staticmethod
    def _format_message(message: str, **kwargs: Any) -> str:
        if kwargs.pop("exc_info", None):
            return f"{message}\n{traceback.format_exc()}"
        if kwargs:
            try:
                return f"{message} {json.dumps(kwargs)}"
            except (TypeError, ValueError):
                extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
                return f"{message} {extras}"
        return message

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
