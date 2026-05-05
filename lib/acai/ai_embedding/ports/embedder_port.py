from abc import ABC, abstractmethod
from typing import Any, List, Optional

from acai.ai_embedding.domain.embedding_result import (
    EmbeddingResult,
    MultimodalEmbeddingResult,
)


class EmbedderPort(ABC):
    """Outbound port defining the contract every embedding adapter must fulfil.

    Hexagonal role
    ──────────────
    This is a *driven* (secondary) port.  Domain code and application services
    depend only on this interface; concrete adapters (OpenAI, Bedrock Titan,
    Anthropic, …) implement it.
    """

    VERSION: str = "1.0.9"  # inject_version

    @abstractmethod
    def get_embedding(self, text: str) -> EmbeddingResult:
        """Generate an embedding result for the given text."""
        ...

    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embedding results for multiple texts."""
        ...

    def multimodal_embed(
        self,
        inputs: List[List[Any]],
        model: str,
        input_type: Optional[str] = None,
    ) -> MultimodalEmbeddingResult:
        """Generate embeddings for multimodal inputs (images, text+image, etc.).

        Each element of *inputs* is a list of content items (str, PIL.Image, etc.).
        Not all adapters support this — the default raises NotImplementedError.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support multimodal embedding"
        )
