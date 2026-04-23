from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class EmbeddingResult:
    """Immutable value object returned by every embedding adapter.

    Attributes
    ----------
    vector:
        The embedding vector (list of floats).
    model:
        Identifier of the model that produced the embedding
        (e.g. ``"text-embedding-3-large"``, ``"voyage-3-large"``).
    text:
        The original input text that was embedded.
    dimension:
        Length of the embedding vector — useful for pgvector
        ``vector(N)`` column definitions.
    normalized:
        Whether the vector has unit L2 norm.  When ``True``, cosine
        similarity equals dot product, enabling faster queries.
    input_type:
        Role hint passed to asymmetric models (e.g. ``"query"`` vs
        ``"document"``).  ``None`` for symmetric models.
    token_count:
        Number of tokens the model consumed for *this* text.
        ``None`` when the API only reports batch-level usage.
    """

    vector: List[float]
    model: str
    text: str
    dimension: int
    normalized: bool
    input_type: Optional[str] = None
    token_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector": self.vector,
            "model": self.model,
            "text": self.text,
            "dimension": self.dimension,
            "normalized": self.normalized,
            "input_type": self.input_type,
            "token_count": self.token_count,
        }


@dataclass(frozen=True)
class MultimodalEmbeddingResult:
    """Result from a multimodal embedding call (images, text+image, etc.).

    Attributes
    ----------
    embeddings:
        List of embedding vectors, one per input.
    model:
        Identifier of the model that produced the embeddings.
    total_tokens:
        Total tokens consumed by the request.
    image_pixels:
        Total image pixels processed.
    text_tokens:
        Total text tokens processed.
    """

    embeddings: List[List[float]]
    model: str
    total_tokens: int = 0
    image_pixels: int = 0
    text_tokens: int = 0
