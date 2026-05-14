from __future__ import annotations

from abc import ABC, abstractmethod

from acai.ai_vector_store.domain.search_result import SearchResult
from acai.ai_vector_store.domain.vector_record import VectorRecord


class VectorStorePort(ABC):
    """Outbound port defining the contract every vector-store adapter must fulfil.

    Hexagonal role
    ──────────────
    This is a *driven* (secondary) port.  Application services depend only
    on this interface; concrete adapters (pgvector, in-memory, …) implement it.
    """

    VERSION: str = "1.0.11"  # inject_version

    @abstractmethod
    def upsert(self, records: list[VectorRecord]) -> int:
        """Insert or update embedding records. Returns the number of rows affected."""
        ...

    @abstractmethod
    def search(
        self,
        vector: list[float],
        *,
        top_k: int = 10,
        filter_metadata: dict | None = None,
    ) -> list[SearchResult]:
        """Find the ``top_k`` most similar records to *vector*.

        Parameters
        ----------
        vector:
            Query embedding.
        top_k:
            Maximum number of results.
        filter_metadata:
            Optional exact-match filter on metadata keys
            (e.g. ``{"law_sr_number": "210"}``).
        """
        ...

    @abstractmethod
    def delete(self, ids: list[str]) -> int:
        """Delete records by their external ids. Returns the number of rows deleted."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release the underlying connection / resources."""
        ...
