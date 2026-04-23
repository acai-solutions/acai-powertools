from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class TextSearchResult:
    """Immutable value object returned by full-text search.

    Attributes
    ----------
    record_id:
        Unique identifier of the matching document.
    content:
        The text content that matched.
    score:
        Relevance score (ts_rank or BM25 score).
    metadata:
        Arbitrary key/value metadata attached to the record.
    """

    record_id: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
