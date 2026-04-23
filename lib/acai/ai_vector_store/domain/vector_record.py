from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class VectorRecord:
    """Immutable value object representing a single stored embedding.

    Attributes
    ----------
    id:
        Unique external identifier (used as upsert key).
    text:
        The original text that was embedded.
    vector:
        The embedding vector (list of floats).
    metadata:
        Arbitrary key-value pairs the caller wants to persist alongside
        the vector (e.g. law_sr_number, article_id, …).
    """

    id: str
    text: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
