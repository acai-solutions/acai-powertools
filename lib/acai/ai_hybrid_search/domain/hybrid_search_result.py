from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class HybridSearchResult:
    """Immutable value object produced by hybrid (semantic + keyword) retrieval.

    Attributes
    ----------
    record_id:
        Unique identifier of the matching document.
    content:
        The text content of the document.
    semantic_score:
        Cosine-similarity score from the vector search (0 if absent).
    text_score:
        Full-text relevance score (0 if absent).
    hybrid_score:
        Combined score (e.g. Reciprocal Rank Fusion).
    metadata:
        Arbitrary key/value metadata attached to the record.
    """

    record_id: str
    content: str
    semantic_score: float = 0.0
    text_score: float = 0.0
    hybrid_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
