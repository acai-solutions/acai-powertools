"""
acai.ai_hybrid_search — Hexagonal hybrid-retrieval module
==========================================================

Combines semantic (vector) search with keyword (full-text) search
using Reciprocal Rank Fusion (RRF).

Public surface
--------------
- ``HybridSearchPort``      — port contract (depend on this)
- ``HybridSearchResult``    — immutable value object
- ``HybridSearchError``     — base exception
- ``create_hybrid_search()``— factory that wires the RRF adapter

Adapters (import directly when needed)
--------------------------------------
- ``acai.ai_hybrid_search.adapters.outbound.rrf_hybrid_search.RRFHybridSearchAdapter``
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple

from acai.ai_hybrid_search.domain import HybridSearchError, HybridSearchResult
from acai.ai_hybrid_search.ports import HybridSearchPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable

# Re-export type aliases for convenience.
SemanticSearchFn = Callable[
    [list[float], int],
    List[Tuple[str, str, float, Dict[str, Any]]],
]
TextSearchFn = Callable[
    [str, int],
    List[Tuple[str, str, float, Dict[str, Any]]],
]


def create_hybrid_search(
    logger: Loggable,
    *,
    semantic_search_fn: SemanticSearchFn,
    text_search_fn: TextSearchFn,
    k: int = 60,
    semantic_weight: float = 0.5,
    fetch_multiplier: int = 3,
) -> HybridSearchPort:
    """Factory that builds a ready-to-use ``HybridSearchPort`` (RRF strategy).

    Parameters
    ----------
    logger:
        A ``Loggable`` instance.
    semantic_search_fn:
        Callable ``(vector, top_k) -> [(id, content, score, metadata), …]``.
    text_search_fn:
        Callable ``(query_text, top_k) -> [(id, content, score, metadata), …]``.
    k:
        RRF smoothing constant (default 60).
    semantic_weight:
        Weight for the semantic rank contribution (0.0-1.0).
        Text weight is derived as ``1 - semantic_weight``.
    fetch_multiplier:
        Fetch ``top_k * fetch_multiplier`` from each source before merging.
    """
    from acai.ai_hybrid_search.adapters.outbound.rrf_hybrid_search import (
        RRFConfig,
        RRFHybridSearchAdapter,
    )

    cfg = RRFConfig(
        k=k,
        semantic_weight=semantic_weight,
        text_weight=1.0 - semantic_weight,
        fetch_multiplier=fetch_multiplier,
    )
    return RRFHybridSearchAdapter(
        logger=logger,
        semantic_search_fn=semantic_search_fn,
        text_search_fn=text_search_fn,
        config=cfg,
    )


__all__ = [
    "HybridSearchPort",
    "HybridSearchResult",
    "HybridSearchError",
    "create_hybrid_search",
    "SemanticSearchFn",
    "TextSearchFn",
]
