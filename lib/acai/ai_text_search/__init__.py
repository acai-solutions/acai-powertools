"""
acai.ai_text_search — Hexagonal full-text search module
========================================================

Public surface
--------------
- ``TextSearchPort``        — port contract (depend on this)
- ``TextSearchConfig``      — search configuration value object
- ``TextSearchResult``      — immutable search-result value object
- ``TextSearchError``, ``ConfigurationError`` — exceptions
- ``create_text_search()``  — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.ai_text_search.adapters.outbound.pg_fulltext_search.PgFulltextSearchAdapter``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.ai_text_search.domain import (
    ConfigurationError,
    TextSearchConfig,
    TextSearchError,
    TextSearchResult,
)
from acai.ai_text_search.ports import TextSearchPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_text_search(
    logger: Loggable,
    *,
    provider: str = "pg_fulltext",
    host: str = "localhost",
    port: int = 5432,
    dbname: str = "postgres",
    user: str = "postgres",
    password: str = "",
    language: str = "german",
    table: str = "app.law_embeddings",
    content_column: str = "embedding_text",
    id_column: str = "external_id",
) -> TextSearchPort:
    """Factory that builds a ready-to-use ``TextSearchPort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter.
    provider:
        One of ``"pg_fulltext"``.
    """
    if provider == "pg_fulltext":
        from acai.ai_text_search.adapters.outbound.pg_fulltext_search import (
            PgFulltextConfig,
            PgFulltextSearchAdapter,
        )

        cfg = PgFulltextConfig(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            search=TextSearchConfig(
                language=language,
                table=table,
                content_column=content_column,
                id_column=id_column,
            ),
        )
        return PgFulltextSearchAdapter(logger=logger, config=cfg)

    raise ConfigurationError(
        f"Unknown text-search provider '{provider}'. Choose from: pg_fulltext"
    )


__all__ = [
    "TextSearchPort",
    "TextSearchConfig",
    "TextSearchResult",
    "TextSearchError",
    "ConfigurationError",
    "create_text_search",
]
