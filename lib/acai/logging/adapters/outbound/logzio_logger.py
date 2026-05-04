import json
import logging
import os
import time
import traceback
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import requests
from acai.logging.ports import LoggerPort, LogLevel


class LogzioLogger(LoggerPort):
    """Logz.io implementation of :class:`LoggerPort`.

    Hexagonal role
    ──────────────
    Driven adapter.  Buffers log messages and sends them to Logz.io via HTTPS.

    Environment variables (can be overridden via arguments):
    ─────────────────────────────────────────────────────────
    * **LOGZIO_ENABLED** - ``"true"`` to activate (default: ``"false"``).
    * **LOGZIO_TOKEN** - Logz.io shipping token.
    * **LOGZIO_URL** - Listener URL (default: ``https://listener.logz.io:8071``).
    * **SERVICE_NAME** - Service identifier (default: ``"my-service"``).
    * **LOG_LEVEL** - Initial log level (DEBUG, INFO, …).
    """

    VERSION: str = "1.0.7"  # inject_version

    def __init__(
        self,
        logzio_token: Optional[str] = None,
        logzio_url: Optional[str] = None,
        service_name: Optional[str] = None,
        timeout: int = 3,
        enabled: Optional[bool] = None,
        use_env: bool = True,
        retry_count: int = 3,
        buffer_size: int = 100,
        additional_fields: Optional[Dict[str, Any]] = None,
        level: Union[LogLevel, int, str, None] = None,
    ) -> None:
        self.enabled = (
            enabled
            if enabled is not None
            else (
                os.getenv("LOGZIO_ENABLED", "false").lower() == "true"
                if use_env
                else False
            )
        )
        self.token = logzio_token or (os.getenv("LOGZIO_TOKEN") if use_env else None)
        self.url = logzio_url or (
            os.getenv("LOGZIO_URL", "https://listener.logz.io:8071")
            if use_env
            else None
        )
        if self.url and not self._is_valid_url(self.url):
            self._get_fallback_logger().warning(
                "[LOGZIO] Invalid URL: %s, falling back", self.url
            )
            self.url = "https://listener.logz.io:8071"

        self.service_name = service_name or os.getenv("SERVICE_NAME", "my-service")
        self.timeout = timeout
        self.retry_count = retry_count
        self.headers = {"Content-Type": "application/json"}

        self.buffer_size = buffer_size
        self.log_buffer: List[Dict[str, Any]] = []

        self.additional_fields = additional_fields or {}
        for env_key, fld in [("ENV", "environment"), ("HOSTNAME", "host")]:
            val = os.getenv(env_key)
            if val and fld not in self.additional_fields:
                self.additional_fields[fld] = val

        self._fallback_logger: Optional[logging.Logger] = None

        initial = level if level is not None else os.getenv("LOG_LEVEL", LogLevel.INFO)
        self.set_level(initial)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._min_level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        if not self.enabled or not self.token:
            return

        numeric = self._to_native(level)
        if numeric < self._min_level:
            return

        payload = self._format_payload(level, message, **kwargs)
        self.log_buffer.append(payload)

        if len(self.log_buffer) >= self.buffer_size or numeric >= LogLevel.ERROR.value:
            self._flush_buffer()

    # ── internals ─────────────────────────────────────────────────────

    def _format_payload(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> Dict[str, Any]:
        level_str = (
            level.name.lower() if isinstance(level, LogLevel) else str(level).lower()
        )
        entry: Dict[str, Any] = {
            "@timestamp": int(time.time() * 1000),
            "level": level_str,
            "message": message,
            "service": self.service_name,
        }
        entry.update(self.additional_fields)

        if kwargs.pop("exc_info", None):
            entry["exception"] = traceback.format_exc()

        entry.update(kwargs)
        return entry

    def _flush_buffer(self) -> None:
        if not self.log_buffer:
            return
        logs_to_send = self.log_buffer.copy()
        self.log_buffer.clear()

        bulk_payload = "\n".join(json.dumps(log) for log in logs_to_send)

        for attempt in range(self.retry_count):
            try:
                response = requests.post(
                    f"{self.url}?token={self.token}",
                    data=bulk_payload,
                    headers=self.headers,
                    timeout=self.timeout,
                )
                if response.status_code < 400:
                    break
                if response.status_code >= 500 and attempt < self.retry_count - 1:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    self._get_fallback_logger().warning(
                        "[LOGZIO] Failed to send logs: %s %s",
                        response.status_code,
                        response.text,
                    )
                    break
            except (requests.RequestException, ConnectionError) as exc:
                if attempt >= self.retry_count - 1:
                    self._get_fallback_logger().warning(
                        "[LOGZIO] Logging failed after %s attempts: %s",
                        self.retry_count,
                        exc,
                    )

    def _get_fallback_logger(self) -> logging.Logger:
        if self._fallback_logger is None:
            self._fallback_logger = logging.getLogger("logzio-fallback")
            if not self._fallback_logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(
                    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
                )
                self._fallback_logger.addHandler(handler)
                self._fallback_logger.setLevel(logging.WARNING)
        return self._fallback_logger

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)

    def __del__(self) -> None:
        if hasattr(self, "log_buffer") and self.log_buffer:
            try:
                self._flush_buffer()
            except Exception:
                logging.debug("Logz.io flush failed during cleanup", exc_info=True)
