# acai.ai_text_search

A full-text search module built on **hexagonal architecture** principles.  
Currently backed by PostgreSQL native full-text search (`tsvector` / `tsquery`).

---

## Architecture

```
acai/ai_text_search/
├── __init__.py                        # Public API + create_text_search() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── text_search_port.py           # TextSearchPort ABC
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── text_search_config.py         # TextSearchConfig dataclass
│   ├── text_search_result.py         # TextSearchResult value object
│   └── exceptions.py                 # TextSearchError, ConfigurationError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       └── pg_fulltext_search.py     # PostgreSQL FTS adapter
└── _test/
    └── (unit tests)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/text_search_port.py` | Abstract contract (`TextSearchPort` ABC). Application code depends *only* on this. |
| **Config VO** | `domain/text_search_config.py` | `TextSearchConfig` — language, table, and column settings. |
| **Result VO** | `domain/text_search_result.py` | `TextSearchResult` — immutable value object with score and metadata. |
| **Exceptions** | `domain/exceptions.py` | `TextSearchError`, `ConfigurationError`. |
| **PG adapter** | `adapters/outbound/pg_fulltext_search.py` | Driven adapter using PostgreSQL `ts_rank` and `to_tsquery`. |
| **Factory** | `__init__.py` → `create_text_search()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `TextSearchPort`; it never imports an adapter directly.

---

## Quick start

```python
from acai.logging import create_logger
from acai.ai_text_search import create_text_search

logger = create_logger()

search = create_text_search(
    logger,
    host="localhost",
    port=5432,
    dbname="lawbot",
    user="postgres",
    password="secret",
    language="german",
    table="app.law_embeddings",
    content_column="embedding_text",
    id_column="external_id",
)

results = search.search("Vertragsrecht", top_k=10)

for r in results:
    print(r.record_id, r.score, r.content[:80])

search.close()
```

---

## API reference

### `create_text_search(logger, *, provider, host, port, dbname, user, password, language, table, content_column, id_column) → TextSearchPort`

Factory function (composition root).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `provider` | `str` | `"pg_fulltext"` | Search backend. Currently only `"pg_fulltext"`. |
| `host` | `str` | `"localhost"` | Database host. |
| `port` | `int` | `5432` | Database port. |
| `dbname` | `str` | `"postgres"` | Database name. |
| `user` | `str` | `"postgres"` | Database user. |
| `password` | `str` | `""` | Database password. |
| `language` | `str` | `"german"` | PostgreSQL text-search dictionary. |
| `table` | `str` | `"app.law_embeddings"` | Fully-qualified table name. |
| `content_column` | `str` | `"embedding_text"` | Column containing searchable text. |
| `id_column` | `str` | `"external_id"` | Column used as record identifier. |

### `TextSearchPort` (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `search` | `(query_text, *, top_k=10) -> list[TextSearchResult]` | Find the most relevant documents for the query. |
| `close` | `() -> None` | Release database connections. |

### `TextSearchConfig` (frozen dataclass)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `language` | `str` | `"german"` | PostgreSQL text-search dictionary. |
| `table` | `str` | `"app.law_embeddings"` | Fully-qualified table name. |
| `content_column` | `str` | `"embedding_text"` | Column containing searchable text. |
| `id_column` | `str` | `"external_id"` | Column used as record identifier. |

### `TextSearchResult` (frozen dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | `str` | Unique document identifier. |
| `content` | `str` | The matched text content. |
| `score` | `float` | Relevance score (`ts_rank`). |
| `metadata` | `dict[str, Any]` | Arbitrary key/value metadata. |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `TextSearchError` | `Exception` | Base class for all text-search errors. |
| `ConfigurationError` | `TextSearchError` | Invalid config values or unknown provider. |

---

## Testing

```bash
cd shared/python
pytest acai/ai_text_search/_test/ -v
```
