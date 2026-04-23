# acai.ai_vector_store

A vector-database module built on **hexagonal architecture** principles.  
Currently backed by PostgreSQL with the pgvector extension. Swap adapters without changing application code.

---

## Architecture

```
acai/ai_vector_store/
├── __init__.py                        # Public API + create_vector_store() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── vector_store_port.py          # VectorStorePort ABC
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── vector_store_config.py        # VectorStoreConfig dataclass
│   ├── vector_record.py              # VectorRecord value object
│   ├── search_result.py              # SearchResult value object
│   └── exceptions.py                 # VectorStoreError → ConnectionError, QueryError, ConfigurationError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       └── pgvector_store.py         # pgvector PostgreSQL adapter
├── _example/
│   └── (usage demos)
└── _test/
    └── (unit tests)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/vector_store_port.py` | Abstract contract (`VectorStorePort` ABC). Application code depends *only* on this. |
| **Config VO** | `domain/vector_store_config.py` | `VectorStoreConfig` — table, schema, dimension, distance metric. |
| **Record VO** | `domain/vector_record.py` | `VectorRecord` — immutable record with id, text, vector, metadata. |
| **Result VO** | `domain/search_result.py` | `SearchResult` — wraps a `VectorRecord` with a similarity score. |
| **Exceptions** | `domain/exceptions.py` | `VectorStoreError` → `ConnectionError`, `QueryError`, `ConfigurationError`. |
| **pgvector adapter** | `adapters/outbound/pgvector_store.py` | Driven adapter using PostgreSQL pgvector extension. |
| **Factory** | `__init__.py` → `create_vector_store()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `VectorStorePort`; it never imports an adapter directly.

---

## Quick start

```python
from acai.logging import create_logger
from acai.ai_vector_store import create_vector_store, VectorRecord

logger = create_logger()

store = create_vector_store(
    logger,
    host="localhost",
    port=5432,
    dbname="lawbot",
    user="postgres",
    password="secret",
    table="law_embeddings",
    dimension=1024,
    distance_metric="cosine",
)

# Upsert records
records = [
    VectorRecord(id="art-1", text="Article 1 ...", vector=[0.1, 0.2, ...], metadata={"law_sr_number": "210"}),
]
store.upsert(records)

# Similarity search
results = store.search(query_vector, top_k=10, filter_metadata={"law_sr_number": "210"})

for r in results:
    print(r.record.id, r.score)

store.close()
```

---

## API reference

### `create_vector_store(logger, *, provider, dsn, host, port, dbname, user, password, table, schema, dimension, distance_metric) → VectorStorePort`

Factory function (composition root).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `provider` | `str` | `"pgvector"` | Storage backend. Currently only `"pgvector"`. |
| `dsn` | `str` | `""` | Full DSN string. When set, individual host/port/… are ignored. |
| `host` | `str` | `"localhost"` | Database host. |
| `port` | `int` | `5432` | Database port. |
| `dbname` | `str` | `"postgres"` | Database name. |
| `user` | `str` | `"postgres"` | Database user. |
| `password` | `str` | `""` | Database password. |
| `table` | `str` | `"embeddings"` | Target table name. |
| `schema` | `str` | `"public"` | Database schema. |
| `dimension` | `int` | `1024` | Embedding vector dimension. |
| `distance_metric` | `str` | `"cosine"` | One of `"cosine"`, `"l2"`, `"inner_product"`. |

### `VectorStorePort` (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `upsert` | `(records: list[VectorRecord]) -> int` | Insert or update records. Returns rows affected. |
| `search` | `(vector, *, top_k=10, filter_metadata=None) -> list[SearchResult]` | Similarity search. |
| `delete` | `(ids: list[str]) -> int` | Delete records by external id. Returns rows deleted. |
| `close` | `() -> None` | Release the database connection. |

### `VectorStoreConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `table` | `str` | `"embeddings"` | Target table name. |
| `schema` | `str` | `"public"` | Database schema. |
| `dimension` | `int` | `1024` | Embedding vector dimension. Must be > 0. |
| `distance_metric` | `str` | `"cosine"` | One of `"cosine"`, `"l2"`, `"inner_product"`. |

### `VectorRecord` (frozen dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique external identifier (upsert key). |
| `text` | `str` | The original text that was embedded. |
| `vector` | `list[float]` | The embedding vector. |
| `metadata` | `dict[str, Any]` | Arbitrary key-value pairs (e.g. `law_sr_number`, `article_id`). |

### `SearchResult` (frozen dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `record` | `VectorRecord` | The matching record. |
| `score` | `float` | Similarity score (interpretation depends on distance metric). |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `VectorStoreError` | `Exception` | Base class for all vector-store errors. |
| `ConnectionError` | `VectorStoreError` | Database connection failures. |
| `QueryError` | `VectorStoreError` | Query execution failures. |
| `ConfigurationError` | `VectorStoreError` | Invalid config values or unknown provider. |

---

## Testing

```bash
cd shared/python
pytest acai/ai_vector_store/_test/ -v
```
