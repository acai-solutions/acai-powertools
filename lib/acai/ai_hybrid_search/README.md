# acai.ai_hybrid_search

A hybrid-retrieval module built on **hexagonal architecture** principles.  
Combines semantic (vector) search with keyword (full-text) search using Reciprocal Rank Fusion (RRF).

---

## Architecture

```
acai/ai_hybrid_search/
├── __init__.py                        # Public API + create_hybrid_search() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── hybrid_search_port.py         # HybridSearchPort ABC
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── hybrid_search_result.py       # HybridSearchResult value object
│   └── exceptions.py                 # HybridSearchError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       └── rrf_hybrid_search.py      # Reciprocal Rank Fusion adapter
└── _test/
    └── (unit tests)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/hybrid_search_port.py` | Abstract contract (`HybridSearchPort` ABC). Application code depends *only* on this. |
| **Result VO** | `domain/hybrid_search_result.py` | `HybridSearchResult` — immutable value object with semantic, text, and hybrid scores. |
| **Exceptions** | `domain/exceptions.py` | `HybridSearchError`. |
| **RRF adapter** | `adapters/outbound/rrf_hybrid_search.py` | Driven adapter using Reciprocal Rank Fusion to merge results. |
| **Factory** | `__init__.py` → `create_hybrid_search()` | Composition root that wires search functions → adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `HybridSearchPort`; it never imports an adapter directly.

---

## Quick start

```python
from acai.logging import create_logger
from acai.ai_hybrid_search import create_hybrid_search

logger = create_logger()

# Provide your own semantic and text search callables
hybrid = create_hybrid_search(
    logger,
    semantic_search_fn=my_vector_search,   # (vector, top_k) -> [(id, content, score, metadata), …]
    text_search_fn=my_text_search,         # (query, top_k) -> [(id, content, score, metadata), …]
    semantic_weight=0.6,
)

results = hybrid.search(
    query_text="Vertragsrecht",
    query_vector=embedding_vector,
    top_k=10,
)

for r in results:
    print(r.record_id, r.hybrid_score)
```

---

## API reference

### `create_hybrid_search(logger, *, semantic_search_fn, text_search_fn, k, semantic_weight, fetch_multiplier) → HybridSearchPort`

Factory function (composition root).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `semantic_search_fn` | `SemanticSearchFn` | *(required)* | Callable `(vector, top_k) -> [(id, content, score, metadata), …]`. |
| `text_search_fn` | `TextSearchFn` | *(required)* | Callable `(query_text, top_k) -> [(id, content, score, metadata), …]`. |
| `k` | `int` | `60` | RRF smoothing constant. |
| `semantic_weight` | `float` | `0.5` | Weight for semantic rank (0.0-1.0). Text weight = `1 - semantic_weight`. |
| `fetch_multiplier` | `int` | `3` | Fetch `top_k * fetch_multiplier` from each source before merging. |

### `HybridSearchPort` (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `search` | `(query_text, query_vector, *, top_k=10) -> list[HybridSearchResult]` | Hybrid search combining semantic similarity and keyword matching. |

### `HybridSearchResult` (frozen dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | `str` | Unique document identifier. |
| `content` | `str` | The document text. |
| `semantic_score` | `float` | Cosine-similarity score from vector search. |
| `text_score` | `float` | Full-text relevance score. |
| `hybrid_score` | `float` | Combined RRF score. |
| `metadata` | `dict[str, Any]` | Arbitrary key/value metadata. |

### Type aliases

| Alias | Signature |
|-------|-----------|
| `SemanticSearchFn` | `Callable[[list[float], int], list[tuple[str, str, float, dict]]]` |
| `TextSearchFn` | `Callable[[str, int], list[tuple[str, str, float, dict]]]` |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `HybridSearchError` | `Exception` | Base class for all hybrid-search errors. |

---

## How RRF works

Reciprocal Rank Fusion merges ranked lists from different retrieval systems:

$$\text{RRF}(d) = \sum_{r \in R} \frac{w_r}{k + \text{rank}_r(d)}$$

Where $k$ is the smoothing constant, $w_r$ is the weight for ranker $r$, and $\text{rank}_r(d)$ is the rank of document $d$ in ranker $r$'s result list.

---

## Testing

```bash
cd shared/python
pytest acai/ai_hybrid_search/_test/ -v
```
