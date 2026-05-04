import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
except ImportError:
    raise ImportError(
        "elasticsearch package is required for ElasticsearchLogger. "
        "Install it with: pip install elasticsearch>=8.0.0"
    )

from acai.logging.ports import LoggerPort, LogLevel


class ElasticsearchLogger(LoggerPort):
    """Elasticsearch implementation of :class:`LoggerPort`.

    Hexagonal role
    ──────────────
    Driven adapter.  Sends log messages directly to an Elasticsearch cluster
    for centralized logging, searching, and analysis.

    Environment variables (can be overridden via arguments):
    ─────────────────────────────────────────────────────────
    * **ES_HOSTS** - Comma-separated list of hosts (default: localhost:9200)
    * **ES_USERNAME** / **ES_PASSWORD** - Basic auth credentials
    * **ES_API_KEY** - API key for authentication
    * **ES_CLOUD_ID** - Elastic Cloud ID
    * **ES_INDEX_PREFIX** - Index prefix (default: logs)
    * **ES_CA_CERTS** - Path to CA certificates
    * **LOG_LEVEL** - Initial log level (DEBUG, INFO, …)
    """

    VERSION: str = "1.0.6"  # inject_version

    def __init__(
        self,
        service: str = "acai-service",
        level: Union[LogLevel, int, str, None] = None,
        *,
        hosts: Optional[List[str]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        cloud_id: Optional[str] = None,
        index_prefix: Optional[str] = None,
        ca_certs: Optional[str] = None,
        verify_certs: bool = True,
        timeout: int = 30,
        max_retries: int = 3,
        retry_on_timeout: bool = True,
        bulk_size: int = 100,
        flush_interval: float = 5.0,
    ) -> None:
        self.service = service
        self.index_prefix = index_prefix or os.getenv("ES_INDEX_PREFIX", "logs")

        # Buffer for batching logs
        self._log_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._bulk_size = bulk_size
        self._flush_interval = flush_interval
        self._last_flush = time.time()

        # Connection configuration
        self.hosts = hosts or self._parse_hosts(os.getenv("ES_HOSTS", "localhost:9200"))
        self.username = username or os.getenv("ES_USERNAME")
        self.password = password or os.getenv("ES_PASSWORD")
        self.api_key = api_key or os.getenv("ES_API_KEY")
        self.cloud_id = cloud_id or os.getenv("ES_CLOUD_ID")
        self.ca_certs = ca_certs or os.getenv("ES_CA_CERTS")
        self.verify_certs = verify_certs
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_on_timeout = retry_on_timeout

        # Initialize client
        self._client = self._create_client()
        self._index_template_created = False

        initial = level if level is not None else os.getenv("LOG_LEVEL", LogLevel.INFO)
        self.set_level(initial)

        self._ensure_index_template()

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._native_level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        native_level = self._to_native(level)
        if native_level < self._native_level:
            return

        log_doc = self._create_log_document(level, message, **kwargs)

        with self._buffer_lock:
            self._log_buffer.append(log_doc)
            should_flush = (
                len(self._log_buffer) >= self._bulk_size
                or time.time() - self._last_flush >= self._flush_interval
            )
            if should_flush:
                self._flush_buffer()

    # ── public helpers ────────────────────────────────────────────────

    def flush(self) -> None:
        """Manually flush all pending log messages."""
        with self._buffer_lock:
            self._flush_buffer()

    def close(self) -> None:
        """Flush remaining messages and close the client."""
        self.flush()
        if hasattr(self._client, "close"):
            self._client.close()

    # ── internals ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_hosts(hosts_str: str) -> List[str]:
        return [h.strip() for h in hosts_str.split(",") if h.strip()]

    def _create_client(self) -> Elasticsearch:
        params: Dict[str, Any] = {
            "hosts": self.hosts,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_on_timeout": self.retry_on_timeout,
            "verify_certs": self.verify_certs,
        }
        if self.cloud_id:
            params["cloud_id"] = self.cloud_id
        if self.api_key:
            params["api_key"] = self.api_key
        elif self.username and self.password:
            params["basic_auth"] = (self.username, self.password)
        if self.ca_certs:
            params["ca_certs"] = self.ca_certs

        try:
            client = Elasticsearch(**params)
            if not client.ping():
                raise ConnectionError("Failed to connect to Elasticsearch cluster")
            return client
        except Exception as exc:
            raise ConnectionError(
                f"Failed to initialise Elasticsearch client: {exc}"
            ) from exc

    def _ensure_index_template(self) -> None:
        if self._index_template_created:
            return
        template_name = f"{self.index_prefix}-template"
        template_body = {
            "index_patterns": [f"{self.index_prefix}-*"],
            "template": {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "5s",
                },
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "level": {"type": "keyword"},
                        "level_numeric": {"type": "integer"},
                        "message": {
                            "type": "text",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            },
                        },
                        "service": {"type": "keyword"},
                        "context": {"type": "object"},
                        "tags": {"type": "keyword"},
                        "exception": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "keyword"},
                                "message": {"type": "text"},
                                "traceback": {"type": "text"},
                            },
                        },
                    }
                },
            },
        }
        try:
            self._client.indices.put_index_template(
                name=template_name, body=template_body
            )
            self._index_template_created = True
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Failed to create index template: %s", exc
            )

    def _get_index_name(self) -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y.%m.%d")
        return f"{self.index_prefix}-{date_str}"

    def _extract_exception_info(self, exc_info: Any) -> Dict[str, Any]:
        import traceback as tb_mod

        if isinstance(exc_info, BaseException):
            tb = "".join(
                tb_mod.format_exception(
                    type(exc_info), exc_info, exc_info.__traceback__
                )
            )
            return {
                "type": type(exc_info).__name__,
                "message": str(exc_info),
                "traceback": tb,
            }
        if isinstance(exc_info, tuple):
            tb = "".join(tb_mod.format_exception(*exc_info))
            return {
                "type": exc_info[0].__name__ if exc_info[0] else "Unknown",
                "message": str(exc_info[1]) if exc_info[1] else "",
                "traceback": tb,
            }
        if exc_info is True:
            import sys

            ei = sys.exc_info()
            tb = "".join(tb_mod.format_exception(*ei))
            return {
                "type": ei[0].__name__ if ei[0] else "Unknown",
                "message": str(ei[1]) if ei[1] else "",
                "traceback": tb,
            }
        return {}

    def _extract_context(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        context = {}
        for key, value in kwargs.items():
            if key == "traceback":
                continue
            try:
                json.dumps(value)
                context[key] = value
            except (TypeError, ValueError):
                context[key] = str(value)
        return context

    def _create_log_document(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        native = self._to_native(level)

        exc_info = kwargs.pop("exc_info", None)
        tags = kwargs.pop("tags", [])

        doc: Dict[str, Any] = {
            "@timestamp": now.isoformat(),
            "level": logging.getLevelName(native),
            "level_numeric": native,
            "message": message,
            "service": self.service,
        }

        if exc_info:
            doc["exception"] = self._extract_exception_info(exc_info)

        context = self._extract_context(kwargs)
        if context:
            doc["context"] = context
        if tags:
            doc["tags"] = tags if isinstance(tags, list) else [tags]

        doc["_id"] = str(uuid4())
        return doc

    def _flush_buffer(self) -> None:
        if not self._log_buffer:
            return
        buffer_copy = self._log_buffer.copy()
        self._log_buffer.clear()
        self._last_flush = time.time()

        try:
            index_name = self._get_index_name()
            actions = []
            for doc in buffer_copy:
                doc_id = doc.pop("_id", str(uuid4()))
                actions.append({"_index": index_name, "_id": doc_id, "_source": doc})

            if actions:
                _ok, failed = bulk(
                    self._client,
                    actions,
                    chunk_size=self._bulk_size,
                    timeout=f"{self.timeout}s",
                )
                if failed:
                    logging.getLogger(__name__).warning(
                        "%d log messages failed to index", len(failed)
                    )
        except Exception as exc:
            logging.getLogger(__name__).error(
                "Error flushing logs to Elasticsearch: %s", exc
            )

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            logging.debug("Elasticsearch close failed during cleanup", exc_info=True)
