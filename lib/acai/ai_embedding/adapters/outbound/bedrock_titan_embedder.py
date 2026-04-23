import base64
import io
import json
from dataclasses import dataclass
from typing import Any, List, Optional

import boto3
from acai.ai_embedding.domain import (
    EmbedderConfig,
    EmbeddingResult,
    ModelInvocationError,
    MultimodalEmbeddingResult,
    TextTooLongError,
)
from acai.ai_embedding.ports import EmbedderPort
from acai.logging.ports import Loggable
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


@dataclass
class BedrockTitanConfig(EmbedderConfig):
    """Configuration for Amazon Bedrock Titan embedding adapter."""

    aws_profile: Optional[str] = None
    bedrock_service_name: str = "bedrock-runtime"
    bedrock_service_region: str = "eu-central-1"
    max_text_length: int = 8000


class BedrockTitanEmbedder(EmbedderPort):
    """Adapter for generating text embeddings using Amazon Bedrock Titan."""

    VERSION: str = "1.0.0"  # inject_version
    MODEL_ID = "amazon.titan-embed-text-v1"

    def __init__(self, logger: Loggable, config: Optional[BedrockTitanConfig] = None):
        self.config = config or BedrockTitanConfig()
        self.logger = logger
        self._initialize_client()
        self.logger.info(
            "Initialized BedrockTitanEmbedder",
            region=self.config.bedrock_service_region,
        )

    def _initialize_client(self) -> None:
        try:
            session = (
                boto3.Session(profile_name=self.config.aws_profile)
                if self.config.aws_profile
                else boto3.Session()
            )
            client_config = Config(
                retries={"max_attempts": self.config.retry_attempts},
                connect_timeout=self.config.timeout_seconds,
                read_timeout=self.config.timeout_seconds,
            )
            self.bedrock = session.client(
                service_name=self.config.bedrock_service_name,
                region_name=self.config.bedrock_service_region,
                config=client_config,
            )
        except (BotoCoreError, ClientError) as e:
            self.logger.error("Failed to initialize AWS client", error=str(e))
            raise ModelInvocationError(f"AWS client initialization failed: {str(e)}")

    def _validate_input(self, text: str) -> None:
        if not text or not isinstance(text, str):
            raise ValueError("Input text must be a non-empty string")
        if len(text) > self.config.max_text_length:
            raise TextTooLongError(
                f"Input text length ({len(text)}) exceeds maximum allowed "
                f"length ({self.config.max_text_length})"
            )

    def get_embedding(self, text: str) -> EmbeddingResult:
        try:
            self._validate_input(text)
            self.logger.debug("Generating embedding", length=len(text))

            response = self.bedrock.invoke_model(
                modelId=self.MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"inputText": text}),
            )
            response_body = json.loads(response["body"].read())

            if "embedding" not in response_body:
                raise ModelInvocationError(
                    "Unexpected response format: 'embedding' field missing"
                )

            embedding = response_body["embedding"]
            token_count = response_body.get("inputTextTokenCount")
            self.logger.debug(
                "Successfully generated embedding", dimension=len(embedding)
            )
            return EmbeddingResult(
                vector=embedding,
                model=self.MODEL_ID,
                text=text,
                dimension=len(embedding),
                normalized=True,
                token_count=token_count,
            )

        except (BotoCoreError, ClientError) as e:
            self.logger.error("AWS service error while getting embedding", error=str(e))
            raise ModelInvocationError(f"AWS service error: {str(e)}")
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse model response", error=str(e))
            raise ModelInvocationError(f"Invalid model response format: {str(e)}")

    def get_embeddings(self, texts: List[str]) -> List[EmbeddingResult]:
        return [self.get_embedding(text) for text in texts]

    def _process_input_item(self, item: Any) -> tuple[str, Optional[str], int]:
        """Process a single input item (text or image).

        Returns tuple of (text_parts joined, image_base64, image_pixels).
        """
        if isinstance(item, str):
            return item, None, 0
        buf = io.BytesIO()
        item.save(buf, format="PNG")
        image_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        image_pixels = item.size[0] * item.size[1]
        return "", image_base64, image_pixels

    def _process_input_items(
        self, input_items: List[Any]
    ) -> tuple[str, Optional[str], int]:
        """Process all items in a single input."""
        text_parts: List[str] = []
        image_base64: Optional[str] = None
        total_pixels = 0

        for item in input_items:
            text, image_b64, pixels = self._process_input_item(item)
            if text:
                text_parts.append(text)
            if image_b64:
                image_base64 = image_b64
                total_pixels += pixels

        return " ".join(text_parts), image_base64, total_pixels

    def multimodal_embed(
        self,
        inputs: List[List[Any]],
        model: str,
        input_type: Optional[str] = None,
    ) -> MultimodalEmbeddingResult:
        """Generate embeddings for multimodal inputs via Bedrock Titan.

        Each element of *inputs* is a list of content items — strings are
        treated as text, PIL Images are encoded to base64 for the
        ``inputImage`` field.  The *model* should be a Titan multimodal
        model such as ``amazon.titan-embed-image-v1``.
        """
        try:
            self.logger.debug(
                "Generating multimodal embeddings",
                count=len(inputs),
                model=model,
            )

            embeddings: List[List[float]] = []
            total_tokens = 0
            total_image_pixels = 0

            for input_items in inputs:
                text_content, image_base64, image_pixels = self._process_input_items(
                    input_items
                )
                total_image_pixels += image_pixels

                body: dict[str, Any] = {}
                if text_content:
                    body["inputText"] = text_content
                if image_base64:
                    body["inputImage"] = image_base64

                if not body:
                    raise ModelInvocationError(
                        "Each input must contain at least one text or image item"
                    )

                response = self.bedrock.invoke_model(
                    modelId=model,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )
                response_body = json.loads(response["body"].read())

                if "embedding" not in response_body:
                    raise ModelInvocationError(
                        "Unexpected response format: 'embedding' field missing"
                    )

                embeddings.append(response_body["embedding"])
                total_tokens += response_body.get("inputTextTokenCount", 0)

            self.logger.debug(
                "Successfully generated multimodal embeddings",
                count=len(embeddings),
                total_tokens=total_tokens,
                image_pixels=total_image_pixels,
            )

            return MultimodalEmbeddingResult(
                embeddings=embeddings,
                model=model,
                total_tokens=total_tokens,
                image_pixels=total_image_pixels,
                text_tokens=total_tokens,
            )

        except (BotoCoreError, ClientError) as e:
            self.logger.error(
                "AWS service error during multimodal embedding", error=str(e)
            )
            raise ModelInvocationError(f"AWS service error: {str(e)}")
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse model response", error=str(e))
            raise ModelInvocationError(f"Invalid model response format: {str(e)}")
