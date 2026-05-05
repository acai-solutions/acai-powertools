"""Reciprocal Rank Fusion (RRF) hybrid search adapter.

Merges results from a **semantic** search (``VectorStorePort`` or any
callable returning scored records) and a **keyword** search
(``TextSearchPort``) using the RRF formula::

    score(d) = 1 / (k + rank_semantic(d)) + 1 / (k + rank_keyword(d))

where *k* is a smoothing constant (default 60, per the original
Cormack et al. 2009 paper).  Documents appearing in only one list
receive only the single-list contribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

from acai.ai_hybrid_search.domain.hybrid_search_result import HybridSearchResult
from acai.ai_hybrid_search.ports.hybrid_search_port import HybridSearchPort
from acai.logging.ports import Loggable

# Type aliases for the two retrieval callbacks.
# Each returns a list of (record_id, content, score, metadata).
SemanticSearchFn = Callable[
    [list[float], int],
    List[Tuple[str, str, float, Dict[str, Any]]],
]
TextSearchFn = Callable[
    [str, int],
    List[Tuple[str, str, float, Dict[str, Any]]],
]


@dataclass(frozen=True)
class RRFConfig:
    """Configuration for Reciprocal Rank Fusion.

    Attributes
    ----------
    k:
        Smoothing constant.  Higher values reduce the influence of
        high-ranking outliers.  60 is the standard default.
    semantic_weight:
        Multiplicative weight for the semantic rank contribution.
    text_weight:
        Multiplicative weight for the keyword rank contribution.
    fetch_multiplier:
        How many results to fetch from each source as a multiple of
        ``top_k`` (to improve recall before fusion).
    """

    k: int = 60
    semantic_weight: float = 1.0
    text_weight: float = 1.0
    fetch_multiplier: int = 3


class RRFHybridSearchAdapter(HybridSearchPort):
    """Hybrid search using Reciprocal Rank Fusion.

    Hexagonal role
    ──────────────
    Outbound adapter implementing ``HybridSearchPort``.
    Delegates to injected semantic and keyword search functions.
    """

    VERSION: str = "1.0.8"  # inject_version

    def __init__(
        self,
        logger: Loggable,
        semantic_search_fn: SemanticSearchFn,
        text_search_fn: TextSearchFn,
        config: RRFConfig | None = None,
    ) -> None:
        self._logger = logger
        self._semantic_fn = semantic_search_fn
        self._text_fn = text_search_fn
        self._config = config or RRFConfig()

    def search(
        self,
        query_text: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
    ) -> List[HybridSearchResult]:
        cfg = self._config
        fetch_k = top_k * cfg.fetch_multiplier

        # --- Retrieve from both sources ---
        semantic_hits = self._semantic_fn(query_vector, fetch_k)
        text_hits = self._text_fn(query_text, fetch_k)

        # --- Build rank maps (1-based) ---
        semantic_ranks: Dict[str, int] = {}
        semantic_data: Dict[str, Tuple[str, float, Dict[str, Any]]] = {}
        for rank, (rid, content, score, meta) in enumerate(semantic_hits, 1):
            semantic_ranks[rid] = rank
            semantic_data[rid] = (content, score, meta)

        text_ranks: Dict[str, int] = {}
        text_data: Dict[str, Tuple[str, float, Dict[str, Any]]] = {}
        for rank, (rid, content, score, meta) in enumerate(text_hits, 1):
            text_ranks[rid] = rank
            text_data[rid] = (content, score, meta)

        # --- Normalise text scores to [0, 1] (max-norm) ---
        max_text_score = (
            max((score for _, score, _ in text_data.values()), default=1.0) or 1.0
        )
        text_data = {
            rid: (content, score / max_text_score, meta)
            for rid, (content, score, meta) in text_data.items()
        }

        # --- Merge via RRF ---
        all_ids = set(semantic_ranks) | set(text_ranks)
        scored: list[HybridSearchResult] = []

        for rid in all_ids:
            sem_rank = semantic_ranks.get(rid)
            txt_rank = text_ranks.get(rid)

            rrf_score = 0.0
            if sem_rank is not None:
                rrf_score += cfg.semantic_weight / (cfg.k + sem_rank)
            if txt_rank is not None:
                rrf_score += cfg.text_weight / (cfg.k + txt_rank)

            # Pick best content + merge metadata
            sem_content, sem_score, sem_meta = semantic_data.get(rid, ("", 0.0, {}))
            txt_content, txt_score, txt_meta = text_data.get(rid, ("", 0.0, {}))
            content = sem_content or txt_content
            metadata = {**sem_meta, **txt_meta}

            scored.append(
                HybridSearchResult(
                    record_id=rid,
                    content=content,
                    semantic_score=sem_score,
                    text_score=txt_score,
                    hybrid_score=rrf_score,
                    metadata=metadata,
                )
            )

        scored.sort(key=lambda r: r.hybrid_score, reverse=True)
        results = scored[:top_k]

        self._logger.info(
            "Hybrid search completed (RRF)",
            semantic_hits=len(semantic_hits),
            text_hits=len(text_hits),
            merged=len(all_ids),
            returned=len(results),
        )
        return results
