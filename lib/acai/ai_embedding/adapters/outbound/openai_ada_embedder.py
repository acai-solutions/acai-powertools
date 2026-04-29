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
from openai import AuthenticationError, OpenAI, OpenAIError, RateLimitError


@dataclass
class OpenAIAdaConfig(EmbedderConfig):
    """Configuration for OpenAI text-embedding-ada-002 adapter."""

    openai_api_key: str = ""
    model_name: str = "text-embedding-ada-002"
    max_text_length: int = 8192


class OpenAIAdaEmbedder(EmbedderPort):
    """Adapter for generating text embeddings using OpenAI text-embedding-ada-002."""

    VERSION: str = "1.0.6"  # inject_version

    def __init__(self, logger: Loggable, config: OpenAIAdaConfig):
        self.config = config
        self.logger = logger
        self.client = OpenAI(
            api_key=config.openai_api_key,
            timeout=config.timeout_seconds,
        )
        self.logger.info("Initialized OpenAIAdaEmbedder", model=self.config.model_name)

    def _validate_input(self, text: str) -> None:
        if not text or not isinstance(text, str):
            raise ValueError("Input text must be a non-empty string")
        if len(text) > self.config.max_text_length:
            raise TextTooLongError(
                f"Input text length ({len(text)}) exceeds maximum "
                f"({self.config.max_text_length})"
            )

    def get_embedding(self, text: str) -> EmbeddingResult:
        try:
            self._validate_input(text)
            self.logger.debug("Generating embedding", length=len(text))

            response = self.client.embeddings.create(
                model=self.config.model_name, input=text
            )
            embedding = response.data[0].embedding
            token_count = getattr(response.usage, "total_tokens", None)
            self.logger.debug(
                "Successfully generated embedding", dimension=len(embedding)
            )
            return EmbeddingResult(
                vector=embedding,
                model=self.config.model_name,
                text=text,
                dimension=len(embedding),
                normalized=True,
                token_count=token_count,
            )

        except AuthenticationError as e:
            self.logger.error("Authentication failed", error=str(e))
            raise ModelInvocationError("Invalid OpenAI API key")
        except RateLimitError as e:
            self.logger.error("Rate limit exceeded", error=str(e))
            raise ModelInvocationError("Too many requests to OpenAI API")
        except OpenAIError as e:
            self.logger.error("OpenAI service error", error=str(e))
            raise ModelInvocationError(f"OpenAI service error: {str(e)}")

    def get_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        return [self.get_embedding(text) for text in texts]

    def multimodal_embed(
        self,
        inputs: List[List[Any]],
        model: str,
        input_type: Optional[str] = None,
    ) -> MultimodalEmbeddingResult:
        """Generate embeddings for multimodal inputs (text-only fallback).

        OpenAI embedding models only support text.  This method extracts
        string items from each input list and embeds the concatenated text.
        Non-text items are skipped with a warning.
        """
        try:
            self.logger.debug(
                "Generating multimodal embeddings (text-only fallback)",
                count=len(inputs),
                model=model,
            )

            texts: List[str] = []
            for input_items in inputs:
                text_parts = [item for item in input_items if isinstance(item, str)]
                if not text_parts:
                    raise ModelInvocationError(
                        "OpenAI embeddings only support text inputs; "
                        "no text content found in input"
                    )
                non_text = [item for item in input_items if not isinstance(item, str)]
                if non_text:
                    self.logger.warning(
                        "Ignoring non-text items in multimodal input",
                        non_text_count=len(non_text),
                    )
                texts.append(" ".join(text_parts))

            results = self.get_embeddings(texts)
            total_tokens = sum(r.token_count or 0 for r in results)

            self.logger.debug(
                "Successfully generated multimodal embeddings (text-only)",
                count=len(results),
                total_tokens=total_tokens,
            )

            return MultimodalEmbeddingResult(
                embeddings=[r.vector for r in results],
                model=model,
                total_tokens=total_tokens,
                text_tokens=total_tokens,
            )

        except (AuthenticationError, RateLimitError) as e:
            self.logger.error("OpenAI error during multimodal embedding", error=str(e))
            raise ModelInvocationError(f"OpenAI error: {str(e)}")
        except OpenAIError as e:
            self.logger.error(
                "OpenAI service error during multimodal embedding", error=str(e)
            )
            raise ModelInvocationError(f"OpenAI service error: {str(e)}")
