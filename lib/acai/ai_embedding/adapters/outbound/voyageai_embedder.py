import math
from dataclasses import dataclass
from typing import Any, List, Optional

from acai.ai_embedding.domain import (
    EmbedderConfig,
    EmbeddingResult,
    ModelInvocationError,
    MultimodalEmbeddingResult,
    TextTooLongError,
)
from acai.ai_embedding.ports import EmbedderPort
from acai.logging.ports import Loggable


@dataclass
class VoyageAIConfig(EmbedderConfig):
    """Configuration for the Voyage AI embedding adapter.

    Voyage AI provides embedding models at https://www.voyageai.com.
    This adapter uses the ``voyageai`` Python SDK.
    """

    api_key: str = ""
    model_name: str = "voyage-3-large"
    max_text_length: int = 32000
    max_batch_size: int = 128
    input_type: Optional[str] = None  # "query" | "document" | None
    normalize: bool = True


class VoyageAIEmbedder(EmbedderPort):
    """Adapter for generating text embeddings via the Voyage AI service."""

    VERSION: str = "1.1.4"  # inject_version

    def __init__(self, logger: Loggable, config: VoyageAIConfig):
        self.config = config
        self.logger = logger
        self._initialize_client()
        self.logger.info(
            "Initialized VoyageAIEmbedder",
            model=self.config.model_name,
        )

    def _initialize_client(self) -> None:
        try:
            import voyageai

            self.client = voyageai.Client(api_key=self.config.api_key)
        except Exception as e:
            self.logger.error("Failed to initialize VoyageAI client", error=str(e))
            raise ModelInvocationError(
                f"VoyageAI client initialization failed: {str(e)}"
            )

    @staticmethod
    def _normalize(vector: List[float]) -> List[float]:
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            return vector
        return [x / norm for x in vector]

    def _validate_input(self, texts: List[str]) -> None:
        if not texts or not isinstance(texts, list):
            raise ValueError("Input must be a non-empty list of strings")
        if not all(isinstance(text, str) and text for text in texts):
            raise ValueError("All inputs must be non-empty strings")
        if len(texts) > self.config.max_batch_size:
            raise ValueError(
                f"Batch size ({len(texts)}) exceeds maximum ({self.config.max_batch_size})"
            )
        for text in texts:
            if len(text) > self.config.max_text_length:
                raise TextTooLongError(
                    f"Input text length ({len(text)}) exceeds maximum "
                    f"({self.config.max_text_length})"
                )

    def get_embedding(self, text: str) -> EmbeddingResult:
        return self.get_embeddings([text])[0]

    def get_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        self._validate_input(texts)
        try:
            self.logger.debug("Generating embeddings", count=len(texts))

            kwargs = {
                "texts": texts,
                "model": self.config.model_name,
            }
            if self.config.input_type:
                kwargs["input_type"] = self.config.input_type

            result = self.client.embed(**kwargs)

            embeddings = result.embeddings
            if self.config.normalize:
                embeddings = [self._normalize(e) for e in embeddings]

            self.logger.debug(
                "Successfully generated embeddings",
                count=len(embeddings),
                dimension=len(embeddings[0]),
            )
            token_count = (
                getattr(result, "total_tokens", None) if len(texts) == 1 else None
            )
            return [
                EmbeddingResult(
                    vector=vec,
                    model=self.config.model_name,
                    text=txt,
                    dimension=len(vec),
                    normalized=self.config.normalize,
                    input_type=self.config.input_type,
                    token_count=token_count,
                )
                for vec, txt in zip(embeddings, texts)
            ]

        except Exception as e:
            self.logger.error("VoyageAI embedding error", error=str(e))
            raise ModelInvocationError(f"VoyageAI embedding error: {str(e)}")

    def multimodal_embed(
        self,
        inputs: List[List[Any]],
        model: str,
        input_type: Optional[str] = None,
    ) -> MultimodalEmbeddingResult:
        try:
            self.logger.debug(
                "Generating multimodal embeddings", count=len(inputs), model=model
            )

            kwargs: dict[str, Any] = {
                "inputs": inputs,
                "model": model,
            }
            if input_type:
                kwargs["input_type"] = input_type

            result = self.client.multimodal_embed(**kwargs)

            embeddings = result.embeddings
            if self.config.normalize:
                embeddings = [self._normalize(e) for e in embeddings]

            self.logger.debug(
                "Successfully generated multimodal embeddings",
                count=len(embeddings),
                total_tokens=result.total_tokens,
                image_pixels=result.image_pixels,
            )

            return MultimodalEmbeddingResult(
                embeddings=embeddings,
                model=model,
                total_tokens=result.total_tokens,
                image_pixels=result.image_pixels,
                text_tokens=result.text_tokens,
            )

        except Exception as e:
            self.logger.error("VoyageAI multimodal embedding error", error=str(e))
            raise ModelInvocationError(f"VoyageAI multimodal embedding error: {str(e)}")
