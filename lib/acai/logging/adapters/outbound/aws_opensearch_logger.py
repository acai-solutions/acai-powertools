import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Optional, Union

from acai.logging.ports import LoggerPort, LogLevel


class AwsOpenSearchLogger(LoggerPort):
    """AWS OpenSearch implementation of :class:`LoggerPort`.

    Hexagonal role
    ──────────────
    Driven adapter.  Logs are written directly to an OpenSearch index using the
    REST API with SigV4 authentication.

    Environment variables (can be overridden via arguments):
    ─────────────────────────────────────────────────────────
    * **OPENSEARCH_HOST** - FQDN of the OpenSearch-compatible endpoint.
    * **OPENSEARCH_REGION** - AWS region (default: ``AWS_REGION`` or *us-east-1*).
    * **OPENSEARCH_PORT** - Port (defaults to 443).
    * **OPENSEARCH_INDEX** - Index name (defaults to ``logs-{service}``).
    * **LOG_LEVEL** - Initial log level (DEBUG, INFO, …).
    """

    VERSION: str = "1.1.4"  # inject_version

    def __init__(
        self,
        service: str = "my-service",
        level: Union[LogLevel, int, str, None] = None,
        *,
        host: Optional[str] = None,
        region: Optional[str] = None,
        port: Optional[int] = None,
        index: Optional[str] = None,
    ) -> None:
        import boto3
        from opensearchpy import OpenSearch, RequestsHttpConnection  # type: ignore
        from requests_aws4auth import AWS4Auth  # type: ignore

        self.service = service
        self._index_initialized = False
        self._executor_lock = threading.Lock()

        # ── Connection ────────────────────────────────────────────────
        self.host = host or os.getenv("OPENSEARCH_HOST")
        if not self.host:
            raise ValueError(
                "OpenSearch host must be provided via argument or OPENSEARCH_HOST env var"
            )
        self.region = (
            region
            or os.getenv("OPENSEARCH_REGION")
            or os.getenv("AWS_REGION", "us-east-1")
        )
        self.port = int(port or os.getenv("OPENSEARCH_PORT", 443))

        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("No AWS credentials found for SigV4 authentication")
        self._auth = AWS4Auth(
            creds.access_key,
            creds.secret_key,
            self.region,
            "es",
            session_token=creds.token,
        )
        self._client = OpenSearch(
            hosts=[{"host": self.host, "port": self.port}],
            http_auth=self._auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=3,
            max_retries=1,
            retry_on_timeout=False,
        )

        self.index = index or os.getenv("OPENSEARCH_INDEX", f"logs-{service}")
        initial = level if level is not None else os.getenv("LOG_LEVEL", LogLevel.INFO)
        self.set_level(initial)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._native_level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        native_level = self._to_native(level)
        if native_level < self._native_level:
            return

        doc = {
            "@timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": logging.getLevelName(native_level),
            "service": self.service,
            "message": message,
            "extra": kwargs or {},
        }

        threading.Thread(
            target=self._index_background, args=(doc,), daemon=True
        ).start()

    # ── internals ─────────────────────────────────────────────────────

    def _index_background(self, doc: dict) -> None:
        with self._executor_lock:
            if not self._index_initialized:
                try:
                    self._client.indices.create(
                        index=self.index,
                        body={
                            "settings": {
                                "number_of_shards": 1,
                                "number_of_replicas": 1,
                            },
                            "mappings": {
                                "properties": {
                                    "@timestamp": {"type": "date"},
                                    "level": {"type": "keyword"},
                                    "service": {"type": "keyword"},
                                    "message": {"type": "text"},
                                    "extra": {"type": "object", "enabled": True},
                                }
                            },
                        },
                        ignore=[400],
                        params={"timeout": "1s"},
                    )
                except Exception:
                    logging.debug("OpenSearch index init failed", exc_info=True)
                finally:
                    self._index_initialized = True

        try:
            self._client.index(index=self.index, body=doc, params={"timeout": "1s"})
        except Exception:
            logging.debug("OpenSearch index write failed", exc_info=True)

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
