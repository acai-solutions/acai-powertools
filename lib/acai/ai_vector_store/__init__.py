"""
acai.ai_vector_store — Hexagonal vector-store module
=====================================================

Public surface
--------------
- ``VectorStorePort``           — port contract (depend on this)
- ``VectorStoreConfig``         — shared configuration value object
- ``VectorRecord``              — immutable record value object
- ``SearchResult``              — immutable search-result value object
- ``VectorStoreError``, ``ConnectionError``, ``QueryError``,
  ``ConfigurationError``        — exceptions
- ``create_vector_store()``     — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.ai_vector_store.adapters.PgvectorStore``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.ai_vector_store.domain import (
    ConfigurationError,
    ConnectionError,
    QueryError,
    SearchResult,
    VectorRecord,
    VectorStoreConfig,
    VectorStoreError,
)
from acai.ai_vector_store.ports import VectorStorePort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_vector_store(
    logger: Loggable,
    *,
    provider: str = "pgvector",
    dsn: str = "",
    host: str = "localhost",
    port: int = 5432,
    dbname: str = "postgres",
    user: str = "postgres",
    password: str = "",
    table: str = "embeddings",
    schema: str = "public",
    dimension: int = 1024,
    distance_metric: str = "cosine",
) -> VectorStorePort:
    """Factory that builds a ready-to-use ``VectorStorePort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter.
    provider:
        One of ``"pgvector"``.
    dsn:
        Full DSN string.  When provided, individual host/port/… fields
        are ignored.
    host, port, dbname, user, password:
        Connection parameters (used when *dsn* is empty).
    table:
        Target table name.
    schema:
        Database schema.
    dimension:
        Embedding vector dimension.
    distance_metric:
        One of ``"cosine"``, ``"l2"``, ``"inner_product"``.
    """
    if provider == "pgvector":
        from acai.ai_vector_store.adapters.outbound.pgvector_store import (
            PgvectorConfig,
            PgvectorStore,
        )

        cfg = PgvectorConfig(
            dsn=dsn,
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            table=table,
            schema=schema,
            dimension=dimension,
            distance_metric=distance_metric,
        )
        return PgvectorStore(logger=logger, config=cfg)

    raise ConfigurationError(f"Unknown provider '{provider}'. Choose from: pgvector")


__all__ = [
    "VectorStorePort",
    "VectorStoreConfig",
    "VectorRecord",
    "SearchResult",
    "VectorStoreError",
    "ConnectionError",
    "QueryError",
    "ConfigurationError",
    "create_vector_store",
]
