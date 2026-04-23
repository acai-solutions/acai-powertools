from dataclasses import dataclass

from .vector_record import VectorRecord


@dataclass(frozen=True)
class SearchResult:
    """Immutable value object returned by similarity search.

    Attributes
    ----------
    record:
        The matching ``VectorRecord``.
    score:
        Similarity score (interpretation depends on the distance metric).
    """

    record: VectorRecord
    score: float
