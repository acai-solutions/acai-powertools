from __future__ import annotations

from abc import ABC, abstractmethod

from acai.ai_text_search.domain.text_search_result import TextSearchResult


class TextSearchPort(ABC):
    """Outbound port for full-text / keyword search.

    Hexagonal role
    ──────────────
    This is a *driven* (secondary) port.  Application services depend only
    on this interface; concrete adapters (PostgreSQL ts_vector, BM25, …)
    implement it.
    """

    VERSION: str = "1.0.10"  # inject_version

    @abstractmethod
    def search(
        self,
        query_text: str,
        *,
        top_k: int = 10,
    ) -> list[TextSearchResult]:
        """Find the ``top_k`` most relevant documents for *query_text*.

        Parameters
        ----------
        query_text:
            The user query in natural language.
        top_k:
            Maximum number of results.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
        ...
