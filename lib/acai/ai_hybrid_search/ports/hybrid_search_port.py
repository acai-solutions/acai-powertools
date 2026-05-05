from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from acai.ai_hybrid_search.domain.hybrid_search_result import HybridSearchResult


class HybridSearchPort(ABC):
    """Port for hybrid retrieval combining semantic and keyword search.

    Hexagonal role
    ──────────────
    This is a *driven* (secondary) port.  Application services depend only
    on this interface; concrete strategies (RRF, weighted sum, …)
    implement it.
    """

    VERSION: str = "1.0.8"  # inject_version

    @abstractmethod
    def search(
        self,
        query_text: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
    ) -> List[HybridSearchResult]:
        """Hybrid search combining semantic similarity and keyword matching.

        Parameters
        ----------
        query_text:
            The user query in natural language (for keyword search).
        query_vector:
            The embedding vector of the user query (for semantic search).
        top_k:
            Maximum number of merged results.
        """
        ...
