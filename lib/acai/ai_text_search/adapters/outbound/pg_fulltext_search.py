"""PostgreSQL full-text search adapter using ``tsvector`` / ``tsquery``.

Uses ``ts_rank_cd`` (cover density) for relevance scoring, which rewards
proximity between matching terms — well suited for legal texts where
article numbers and keywords appear close together.

Requirements
------------
- PostgreSQL ≥ 12
- The target column (``embedding_text``) must be of type ``text``.
  A generated ``tsvector`` column or GIN index is recommended for
  production workloads but not required (the adapter builds the
  ``tsvector`` on the fly if no materialised column exists).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import psycopg2
from acai.ai_text_search.domain.text_search_config import TextSearchConfig
from acai.ai_text_search.domain.text_search_result import TextSearchResult
from acai.ai_text_search.ports.text_search_port import TextSearchPort
from acai.logging.ports import Loggable
from psycopg2 import sql as pgsql


@dataclass(frozen=True)
class PgFulltextConfig:
    """Connection + search parameters."""

    host: str = "localhost"
    port: int = 5432
    dbname: str = "postgres"
    user: str = "postgres"
    password: str = ""
    search: TextSearchConfig = TextSearchConfig()


class PgFulltextSearchAdapter(TextSearchPort):
    """Full-text search via PostgreSQL ``ts_rank_cd``.

    Hexagonal role
    ──────────────
    Outbound adapter implementing ``TextSearchPort``.
    """

    VERSION: str = "1.0.8"  # inject_version

    def __init__(self, logger: Loggable, config: PgFulltextConfig) -> None:
        self._logger = logger
        self._config = config
        self._conn_params: Dict[str, Any] = {
            "host": config.host,
            "port": config.port,
            "dbname": config.dbname,
            "user": config.user,
            "password": config.password,
        }
        self._logger.info(
            "Initialized PgFulltextSearchAdapter",
            host=config.host,
            dbname=config.dbname,
            language=config.search.language,
        )

    @staticmethod
    def _validate_identifier(name: str) -> None:
        """Reject identifiers that don't look like safe SQL names."""
        import re

        for part in name.split("."):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
                raise ValueError(f"Invalid SQL identifier: {name!r}")

    @staticmethod
    def _sql_identifier(dotted_name: str) -> pgsql.Composable:
        """Turn ``'schema.table'`` into ``Identifier('schema') + . + Identifier('table')``."""
        parts = dotted_name.split(".")
        return pgsql.SQL(".").join(pgsql.Identifier(p) for p in parts)

    @staticmethod
    def _build_or_query_parts(
        language: str, query_text: str
    ) -> tuple[pgsql.Composable, list[str]]:
        """Build a parameterised OR ``tsquery`` expression.

        Returns a tuple of (sql_fragment, params) where *sql_fragment*
        is a ``psycopg2.sql.Composable`` and *params* is the list of
        token strings.  Each token is stemmed via ``plainto_tsquery``
        and the results are joined with ``||`` (OR).

        This avoids the overly strict AND behaviour of a single
        ``plainto_tsquery`` call on the entire input, which fails when
        the query is a keyword-rich LLM-rewritten retrieval text.
        """
        import re

        lang_id = pgsql.Literal(language)
        tokens = [t.strip(" ,;.\n") for t in re.split(r"[,;\n]+|\s+", query_text)]
        tokens = [t for t in tokens if len(t) >= 2]
        if not tokens:
            fragment = pgsql.SQL("plainto_tsquery({}, %s)").format(lang_id)
            return fragment, [query_text]
        parts = [pgsql.SQL("plainto_tsquery({}, %s)").format(lang_id) for _ in tokens]
        return pgsql.SQL(" || ").join(parts), tokens

    def search(
        self,
        query_text: str,
        *,
        top_k: int = 10,
    ) -> List[TextSearchResult]:
        """Full-text search using ``ts_rank_cd``.

        Builds a ``tsquery`` from *query_text* by OR-ing individual
        terms (each stemmed via ``plainto_tsquery``).  This ensures
        keyword-rich retrieval queries match articles that contain
        *any* of the search terms, not just all of them.
        """
        cfg = self._config.search

        or_query_sql, token_params = self._build_or_query_parts(
            cfg.language, query_text
        )

        self._validate_identifier(cfg.table)
        self._validate_identifier(cfg.id_column)
        self._validate_identifier(cfg.content_column)

        query = pgsql.SQL("""
            SELECT
                {id_col},
                {content_col},
                ts_rank_cd(
                    to_tsvector({lang}, {content_col}),
                    query
                ) AS rank,
                article,
                law_number,
                law_name,
                law_url,
                law_headings
            FROM {tbl},
                 (SELECT {or_query}) AS sub(query)
            WHERE to_tsvector({lang}, {content_col}) @@ query
            ORDER BY rank DESC
            LIMIT %s
        """).format(
            id_col=pgsql.Identifier(cfg.id_column),
            content_col=pgsql.Identifier(cfg.content_column),
            lang=pgsql.Literal(cfg.language),
            tbl=self._sql_identifier(cfg.table),
            or_query=or_query_sql,
        )

        try:
            with psycopg2.connect(**self._conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO app, public;")
                    cur.execute(query, (*token_params, top_k))

                    results = [
                        TextSearchResult(
                            record_id=row[0],
                            content=row[1],
                            score=float(row[2]),
                            metadata={
                                "article": row[3] or "",
                                "law_number": row[4] or "",
                                "law_name": row[5] or "",
                                "law_url": row[6] or "",
                                "headings": row[7] or [],
                            },
                        )
                        for row in cur.fetchall()
                    ]

            self._logger.debug(
                "Full-text search completed",
                query_length=len(query_text),
                results=len(results),
            )
            return results

        except Exception as exc:
            self._logger.error("Full-text search failed", error=str(exc))
            raise

    def close(self) -> None:
        """No persistent connection to close."""
