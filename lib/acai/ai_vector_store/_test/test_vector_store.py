"""Tests for ``acai.ai_vector_store`` — config, domain objects, factory, and adapter.

All tests mock psycopg2 so no real database connection is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from acai.ai_vector_store import (
    ConfigurationError,
    create_vector_store,
)
from acai.ai_vector_store.adapters.outbound.pgvector_store import (
    PgvectorConfig,
    PgvectorStore,
)
from acai.ai_vector_store.domain import (
    ConnectionError,
    QueryError,
    SearchResult,
    VectorRecord,
    VectorStoreConfig,
    VectorStoreError,
)
from acai.ai_vector_store.ports import VectorStorePort

# ── helpers ───────────────────────────────────────────────────────────


def _make_pgvector_store(logger, **overrides) -> PgvectorStore:
    """Build a PgvectorStore with a mocked psycopg2 connection."""
    defaults = {
        "dsn": "host=localhost dbname=test",
        "table": "test_embeddings",
        "schema": "public",
        "dimension": 3,
    }
    defaults.update(overrides)
    cfg = PgvectorConfig(**defaults)
    with (
        patch(
            "acai.ai_vector_store.adapters.outbound.pgvector_store.psycopg2"
        ) as mock_pg,
        patch("acai.ai_vector_store.adapters.outbound.pgvector_store.register_vector"),
    ):
        # psycopg2.Error must be a real exception subclass for 'except' to work
        mock_pg.Error = type("Error", (Exception,), {})
        mock_conn = MagicMock()
        mock_pg.connect.return_value = mock_conn
        store = PgvectorStore(logger=logger, config=cfg)
    store._conn = mock_conn
    return store


def _sample_record(
    id: str = "rec-1", text: str = "hello", vector=None, **meta
) -> VectorRecord:
    return VectorRecord(
        id=id,
        text=text,
        vector=vector or [0.1, 0.2, 0.3],
        metadata=meta,
    )


# ── VectorStoreConfig validation ─────────────────────────────────────


class TestVectorStoreConfig:
    def test_defaults(self):
        cfg = VectorStoreConfig()
        assert cfg.table == "embeddings"  # nosec B101
        assert cfg.schema == "public"  # nosec B101
        assert cfg.dimension == 1024  # nosec B101
        assert cfg.distance_metric == "cosine"  # nosec B101

    def test_negative_dimension_raises(self):
        with pytest.raises(ConfigurationError, match="dimension"):
            VectorStoreConfig(dimension=-1)

    def test_zero_dimension_raises(self):
        with pytest.raises(ConfigurationError, match="dimension"):
            VectorStoreConfig(dimension=0)

    def test_invalid_distance_metric_raises(self):
        with pytest.raises(ConfigurationError, match="distance_metric"):
            VectorStoreConfig(distance_metric="manhattan")

    def test_empty_table_raises(self):
        with pytest.raises(ConfigurationError, match="table"):
            VectorStoreConfig(table="")

    def test_custom_values(self):
        cfg = VectorStoreConfig(
            table="my_vectors", schema="app", dimension=768, distance_metric="l2"
        )
        assert cfg.table == "my_vectors"  # nosec B101
        assert cfg.schema == "app"  # nosec B101
        assert cfg.dimension == 768  # nosec B101
        assert cfg.distance_metric == "l2"  # nosec B101


# ── PgvectorConfig ──────────────────────────────────────────────────


class TestPgvectorConfig:
    def test_dsn_wins(self):
        cfg = PgvectorConfig(dsn="host=db port=5433 dbname=prod")
        assert cfg.build_dsn() == "host=db port=5433 dbname=prod"  # nosec B101

    def test_fields_from_parts(self):
        cfg = PgvectorConfig(
            host="db", port=5433, dbname="prod", user="u", password="p"  # nosec B106
        )
        dsn = cfg.build_dsn()
        assert "host=db" in dsn  # nosec B101
        assert "port=5433" in dsn  # nosec B101
        assert "dbname=prod" in dsn  # nosec B101

    def test_inherits_base_validation(self):
        with pytest.raises(ConfigurationError):
            PgvectorConfig(dimension=-1)


# ── VectorRecord ─────────────────────────────────────────────────────


class TestVectorRecord:
    def test_is_frozen(self):
        rec = _sample_record()
        with pytest.raises(AttributeError):
            rec.id = "other"  # type: ignore[misc]

    def test_default_metadata_is_empty(self):
        rec = VectorRecord(id="x", text="t", vector=[1.0])
        assert rec.metadata == {}  # nosec B101

    def test_metadata_preserved(self):
        rec = _sample_record(law="SR 210")
        assert rec.metadata == {"law": "SR 210"}  # nosec B101


# ── SearchResult ─────────────────────────────────────────────────────


class TestSearchResult:
    def test_is_frozen(self):
        sr = SearchResult(record=_sample_record(), score=0.95)
        with pytest.raises(AttributeError):
            sr.score = 0.5  # type: ignore[misc]

    def test_fields(self):
        rec = _sample_record()
        sr = SearchResult(record=rec, score=0.42)
        assert sr.record is rec  # nosec B101
        assert sr.score == 0.42  # nosec B101


# ── PgvectorStore — upsert ──────────────────────────────────────────


class TestUpsert:
    def test_empty_list_returns_zero(self, logger):
        store = _make_pgvector_store(logger)
        assert store.upsert([]) == 0  # nosec B101

    def test_upsert_calls_execute_batch(self, logger):
        store = _make_pgvector_store(logger)
        records = [_sample_record("a"), _sample_record("b")]

        with patch(
            "acai.ai_vector_store.adapters.outbound.pgvector_store.psycopg2.extras"
        ) as mock_extras:
            result = store.upsert(records)

        assert result == 2  # nosec B101
        mock_extras.execute_batch.assert_called_once()
        store._conn.commit.assert_called_once()

    def test_upsert_error_raises_query_error(self, logger):
        store = _make_pgvector_store(logger)
        import psycopg2

        store._conn.cursor.return_value.__enter__ = MagicMock(
            side_effect=psycopg2.Error("boom")
        )

        with pytest.raises(QueryError, match="Upsert failed"):
            store.upsert([_sample_record()])


# ── PgvectorStore — search ──────────────────────────────────────────


class TestSearch:
    def test_search_returns_results(self, logger):
        store = _make_pgvector_store(logger)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("id1", "hello", [0.1, 0.2, 0.3], {"k": "v"}, 0.05),
        ]
        store._conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)

        results = store.search([0.1, 0.2, 0.3], top_k=5)

        assert len(results) == 1  # nosec B101
        assert isinstance(results[0], SearchResult)  # nosec B101
        assert results[0].record.id == "id1"  # nosec B101
        assert results[0].score == 0.05  # nosec B101

    def test_search_with_filter(self, logger):
        store = _make_pgvector_store(logger)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        store._conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)

        store.search([0.1, 0.2, 0.3], filter_metadata={"law": "210"})
        mock_cursor.execute.assert_called_once()
        sql = str(mock_cursor.execute.call_args[0][0])
        assert "WHERE" in sql  # nosec B101
        assert "metadata" in sql  # nosec B101


# ── PgvectorStore — delete ──────────────────────────────────────────


class TestDelete:
    def test_empty_list_returns_zero(self, logger):
        store = _make_pgvector_store(logger)
        assert store.delete([]) == 0  # nosec B101


# ── PgvectorStore — context manager ─────────────────────────────────


class TestContextManager:
    def test_close_on_exit(self, logger):
        store = _make_pgvector_store(logger)
        store._conn.closed = False
        with store:
            pass
        store._conn.close.assert_called_once()

    def test_rollback_on_exception(self, logger):
        store = _make_pgvector_store(logger)
        store._conn.closed = False
        with pytest.raises(RuntimeError):
            with store:
                raise RuntimeError("oops")
        store._conn.rollback.assert_called_once()


# ── exception hierarchy ──────────────────────────────────────────────


class TestExceptions:
    def test_connection_is_vector_store_error(self):
        assert issubclass(ConnectionError, VectorStoreError)  # nosec B101

    def test_query_is_vector_store_error(self):
        assert issubclass(QueryError, VectorStoreError)  # nosec B101

    def test_configuration_is_vector_store_error(self):
        assert issubclass(ConfigurationError, VectorStoreError)  # nosec B101


# ── factory ──────────────────────────────────────────────────────────


class TestFactory:
    def test_unknown_provider_raises(self, logger):
        with pytest.raises(ConfigurationError, match="Unknown provider"):
            create_vector_store(logger, provider="not_real")

    def test_pgvector_provider(self, logger):
        with (
            patch(
                "acai.ai_vector_store.adapters.outbound.pgvector_store.psycopg2"
            ) as mock_pg,
            patch(
                "acai.ai_vector_store.adapters.outbound.pgvector_store.register_vector"
            ),
        ):
            mock_pg.Error = type("Error", (Exception,), {})
            mock_pg.connect.return_value = MagicMock()
            store = create_vector_store(
                logger,
                provider="pgvector",
                dsn="host=localhost dbname=test",
                dimension=3,
            )
        assert isinstance(store, VectorStorePort)  # nosec B101
        assert isinstance(store, PgvectorStore)  # nosec B101


# ── port contract ────────────────────────────────────────────────────


class TestPortContract:
    def test_pgvector_implements_port(self, logger):
        store = _make_pgvector_store(logger)
        assert isinstance(store, VectorStorePort)  # nosec B101
