__all__ = ["PgvectorStore", "PgvectorConfig"]


def __getattr__(name: str):
    if name in ("PgvectorStore", "PgvectorConfig"):
        from .outbound.pgvector_store import PgvectorConfig, PgvectorStore

        return {"PgvectorStore": PgvectorStore, "PgvectorConfig": PgvectorConfig}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
