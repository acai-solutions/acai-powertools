"""
Outbound adapter — persists and queries embeddings in PostgreSQL via pgvector.

Uses psycopg2 with parameterised queries.  The target table is created
automatically (``CREATE TABLE IF NOT EXISTS``) on first use so no
external migration tool is strictly required for simple setups.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

import psycopg2
import psycopg2.extras
from acai.ai_vector_store.domain import (
    ConnectionError,
    QueryError,
    SearchResult,
    VectorRecord,
    VectorStoreConfig,
)
from acai.ai_vector_store.ports import VectorStorePort
from acai.logging.ports import Loggable
from pgvector.psycopg2 import register_vector
from psycopg2 import sql as pgsql

# ── adapter-specific config ──────────────────────────────────────────


@dataclass
class PgvectorConfig(VectorStoreConfig):
    """Configuration for the pgvector PostgreSQL adapter."""

    dsn: str = ""
    host: str = "localhost"
    port: int = 5432
    dbname: str = "postgres"
    user: str = "postgres"
    password: str = ""

    def build_dsn(self) -> str:
        """Return the DSN string — explicit *dsn* wins over individual fields."""
        if self.dsn:
            return self.dsn
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )


# ── distance-metric helpers ──────────────────────────────────────────

_OPERATOR = {
    "cosine": "<=>",
    "l2": "<->",
    "inner_product": "<#>",
}

_INDEX_OPS = {
    "cosine": "vector_cosine_ops",
    "l2": "vector_l2_ops",
    "inner_product": "vector_ip_ops",
}


# ── adapter ──────────────────────────────────────────────────────────


class PgvectorStore(VectorStorePort):
    """Driven adapter implementing ``VectorStorePort`` for PostgreSQL + pgvector."""

    VERSION: str = "1.0.8"  # inject_version

    def __init__(
        self,
        logger: Loggable,
        config: PgvectorConfig,
    ) -> None:
        self._logger = logger
        self._config = config
        self._connect()

    # ── VectorStorePort implementation ────────────────────────────────

    def upsert(self, records: list[VectorRecord]) -> int:
        if not records:
            return 0

        stmt = pgsql.SQL("""
            INSERT INTO {tbl} (id, text, embedding, metadata)
            VALUES (%(id)s, %(text)s, %(embedding)s, %(metadata)s)
            ON CONFLICT (id) DO UPDATE SET
                text      = EXCLUDED.text,
                embedding = EXCLUDED.embedding,
                metadata  = EXCLUDED.metadata;
        """).format(tbl=self._table_identifier)

        rows = [self._record_to_params(r) for r in records]
        try:
            with self._conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, stmt, rows, page_size=100)
            self._conn.commit()
            self._logger.info(f"Upserted {len(rows)} records")
            return len(rows)
        except psycopg2.Error as exc:
            self._conn.rollback()
            raise QueryError(f"Upsert failed: {exc}") from exc

    def search(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        filter_metadata: dict | None = None,
    ) -> list[SearchResult]:
        op = pgsql.SQL(_OPERATOR[self._config.distance_metric])
        tbl = self._table_identifier

        conditions = pgsql.SQL("")
        params: dict[str, Any] = {"query_vec": vector, "top_k": top_k}

        if filter_metadata:
            clauses = []
            for i, (key, value) in enumerate(filter_metadata.items()):
                pkey = f"fk_{i}"
                pval = f"fv_{i}"
                clauses.append(
                    pgsql.SQL("metadata->>%({pkey})s = %({pval})s").format(
                        pkey=pgsql.SQL(pkey), pval=pgsql.SQL(pval)
                    )
                )
                params[pkey] = key
                params[pval] = str(value)
            conditions = pgsql.SQL("WHERE ") + pgsql.SQL(" AND ").join(clauses)

        stmt = pgsql.SQL("""
            SELECT id, text, embedding, metadata,
                   embedding {op} %(query_vec)s AS distance
            FROM   {tbl}
            {conditions}
            ORDER BY distance
            LIMIT  %(top_k)s;
        """).format(op=op, tbl=tbl, conditions=conditions)

        try:
            with self._conn.cursor() as cur:
                cur.execute(stmt, params)
                rows = cur.fetchall()

            results: list[SearchResult] = []
            for row in rows:
                record = VectorRecord(
                    id=row[0],
                    text=row[1],
                    vector=list(row[2]),
                    metadata=row[3] if isinstance(row[3], dict) else json.loads(row[3]),
                )
                results.append(SearchResult(record=record, score=float(row[4])))
            return results
        except psycopg2.Error as exc:
            raise QueryError(f"Search failed: {exc}") from exc

    def delete(self, ids: list[str]) -> int:
        if not ids:
            return 0

        stmt = pgsql.SQL("DELETE FROM {tbl} WHERE id = ANY(%(ids)s);").format(
            tbl=self._table_identifier
        )

        try:
            with self._conn.cursor() as cur:
                cur.execute(stmt, {"ids": ids})
            self._conn.commit()
            deleted = cur.rowcount
            self._logger.info(f"Deleted {deleted} records")
            return deleted
        except psycopg2.Error as exc:
            self._conn.rollback()
            raise QueryError(f"Delete failed: {exc}") from exc

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._logger.info("PostgreSQL connection closed")

    # ── context manager ───────────────────────────────────────────────

    def __enter__(self) -> "PgvectorStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self._conn.rollback()
        self.close()

    # ── table bootstrap ───────────────────────────────────────────────

    def ensure_table(self) -> None:
        """Create the embeddings table and index if they don't exist yet."""
        tbl = self._table_identifier
        dim = pgsql.Literal(self._config.dimension)
        ops = pgsql.SQL(_INDEX_OPS[self._config.distance_metric])
        idx_name = pgsql.Identifier(f"idx_{self._config.table}_embedding")

        ddl = pgsql.SQL("""
            CREATE EXTENSION IF NOT EXISTS vector;

            CREATE TABLE IF NOT EXISTS {tbl} (
                id       TEXT PRIMARY KEY,
                text     TEXT NOT NULL,
                embedding vector({dim}) NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'
            );

            CREATE INDEX IF NOT EXISTS {idx}
            ON {tbl}
            USING ivfflat (embedding {ops})
            WITH (lists = 100);
        """).format(tbl=tbl, dim=dim, idx=idx_name, ops=ops)
        try:
            with self._conn.cursor() as cur:
                cur.execute(ddl)
            self._conn.commit()
            self._logger.info(f"Ensured table {tbl} exists (dim={dim})")
        except psycopg2.Error as exc:
            self._conn.rollback()
            raise QueryError(f"Table creation failed: {exc}") from exc

    # ── private helpers ───────────────────────────────────────────────

    @property
    def _qualified_table(self) -> str:
        return f"{self._config.schema}.{self._config.table}"

    @property
    def _table_identifier(self) -> pgsql.Composable:
        """Return a safely-quoted ``schema.table`` SQL identifier."""
        return pgsql.SQL(".").join(
            [
                pgsql.Identifier(self._config.schema),
                pgsql.Identifier(self._config.table),
            ]
        )

    def _connect(self) -> None:
        try:
            dsn = self._config.build_dsn()
            self._conn = psycopg2.connect(dsn)
            self._conn.autocommit = False
            register_vector(self._conn)
            self._logger.info("Connected to PostgreSQL (pgvector)")
        except psycopg2.Error as exc:
            raise ConnectionError(f"Failed to connect: {exc}") from exc

    @staticmethod
    def _record_to_params(record: VectorRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "text": record.text,
            "embedding": record.vector,
            "metadata": json.dumps(record.metadata, ensure_ascii=False),
        }
