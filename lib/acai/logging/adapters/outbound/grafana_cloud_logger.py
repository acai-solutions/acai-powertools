import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import requests
from acai.logging.ports import LoggerPort, LogLevel


class GrafanaCloudLogger(LoggerPort):
    """Grafana Cloud OTLP implementation of :class:`LoggerPort`.

    Hexagonal role
    ──────────────
    Driven adapter.  Sends log messages to Grafana Cloud via the OpenTelemetry
    (OTLP/HTTP) logs endpoint with batching and automatic flushing.

    Environment variables (can be overridden via arguments):
    ─────────────────────────────────────────────────────────
    * **GRAFANA_CLOUD_OTLP_URL** - OTLP endpoint URL
      (e.g. ``https://<stack>.grafana.net/otlp/v1/logs``)
    * **GRAFANA_CLOUD_INSTANCE_ID** - Instance ID (basic auth username)
    * **GRAFANA_CLOUD_API_TOKEN** - API token (basic auth password)
    * **SERVICE_NAME** - Service identifier (default: ``"acai-service"``)
    * **DEPLOYMENT_ENVIRONMENT** - Deployment environment label
    * **LOG_LEVEL** - Initial log level (DEBUG, INFO, …)
    """

    VERSION: str = "1.0.7"  # inject_version

    # OTLP severity numbers aligned with OpenTelemetry spec
    _SEVERITY_MAP: Dict[int, tuple[int, str]] = {
        logging.DEBUG: (5, "DEBUG"),
        logging.INFO: (9, "INFO"),
        logging.WARNING: (13, "WARN"),
        logging.ERROR: (17, "ERROR"),
        logging.CRITICAL: (21, "FATAL"),
    }

    def __init__(
        self,
        service_name: Optional[str] = None,
        level: Union[LogLevel, int, str, None] = None,
        *,
        otlp_url: Optional[str] = None,
        instance_id: Optional[str] = None,
        api_token: Optional[str] = None,
        environment: Optional[str] = None,
        extra_resource_attrs: Optional[Dict[str, str]] = None,
        timeout: int = 5,
        bulk_size: int = 50,
        flush_interval: float = 5.0,
    ) -> None:
        self.service_name = service_name or os.getenv("SERVICE_NAME", "acai-service")
        self.otlp_url = otlp_url or os.getenv("GRAFANA_CLOUD_OTLP_URL")
        self.instance_id = instance_id or os.getenv("GRAFANA_CLOUD_INSTANCE_ID")
        self.api_token = api_token or os.getenv("GRAFANA_CLOUD_API_TOKEN")
        self.environment = environment or os.getenv("DEPLOYMENT_ENVIRONMENT", "")
        self.timeout = timeout

        # Resource attributes (OTel convention)
        self._resource_attrs: Dict[str, str] = {
            "service.name": self.service_name,
        }
        if self.environment:
            self._resource_attrs["deployment.environment"] = self.environment
        if extra_resource_attrs:
            self._resource_attrs.update(extra_resource_attrs)

        # Buffer for batching logs
        self._log_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._bulk_size = bulk_size
        self._flush_interval = flush_interval
        self._last_flush = time.time()

        # Fallback logger for adapter-internal errors
        self._fallback = logging.getLogger("grafana-cloud-fallback")
        if not self._fallback.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self._fallback.addHandler(handler)
            self._fallback.setLevel(logging.WARNING)

        initial = level if level is not None else os.getenv("LOG_LEVEL", LogLevel.INFO)
        self.set_level(initial)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._min_level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        numeric = self._to_native(level)
        if numeric < self._min_level:
            return

        record = self._build_log_record(numeric, message, **kwargs)

        with self._buffer_lock:
            self._log_buffer.append(record)
            should_flush = (
                len(self._log_buffer) >= self._bulk_size
                or time.time() - self._last_flush >= self._flush_interval
            )
            if should_flush:
                self._flush_buffer()

    def flush(self) -> None:
        """Manually flush all pending log messages."""
        with self._buffer_lock:
            self._flush_buffer()

    def close(self) -> None:
        """Flush remaining messages."""
        self.flush()

    # ── internals ─────────────────────────────────────────────────────

    def _build_log_record(
        self, numeric_level: int, message: str, **kwargs: Any
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        time_unix_nano = str(int(now.timestamp() * 1e9))

        severity_number, severity_text = self._SEVERITY_MAP.get(
            numeric_level, (9, "INFO")
        )

        # Build attributes from kwargs
        attributes: List[Dict[str, Any]] = []
        exc_info = kwargs.pop("exc_info", None)

        for key, value in kwargs.items():
            attributes.append({"key": key, "value": {"stringValue": str(value)}})

        body = message
        if exc_info:
            body = f"{message}\n{traceback.format_exc()}"

        return {
            "timeUnixNano": time_unix_nano,
            "severityNumber": severity_number,
            "severityText": severity_text,
            "body": {"stringValue": body},
            "attributes": attributes,
        }

    def _build_otlp_payload(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        resource_attributes = [
            {"key": k, "value": {"stringValue": v}}
            for k, v in self._resource_attrs.items()
        ]

        return {
            "resourceLogs": [
                {
                    "resource": {"attributes": resource_attributes},
                    "scopeLogs": [
                        {
                            "scope": {"name": "acai.logging", "version": self.VERSION},
                            "logRecords": records,
                        }
                    ],
                }
            ]
        }

    def _flush_buffer(self) -> None:
        """Send buffered records to Grafana Cloud. Must be called under lock."""
        if not self._log_buffer:
            return

        records = self._log_buffer.copy()
        self._log_buffer.clear()
        self._last_flush = time.time()

        if not self.otlp_url:
            self._fallback.warning(
                "[GRAFANA] GRAFANA_CLOUD_OTLP_URL not set — dropping %d records",
                len(records),
            )
            return

        payload = self._build_otlp_payload(records)

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        auth = None
        if self.instance_id and self.api_token:
            auth = (self.instance_id, self.api_token)

        try:
            resp = requests.post(
                self.otlp_url,
                data=json.dumps(payload),
                headers=headers,
                auth=auth,
                timeout=self.timeout,
            )
            if resp.status_code >= 400:
                self._fallback.warning(
                    "[GRAFANA] OTLP push failed (HTTP %d): %s",
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception as exc:
            self._fallback.warning("[GRAFANA] OTLP push failed: %s", exc)

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
