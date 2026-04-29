"""Amazon Bedrock Claude adapter — calls Claude via AWS Bedrock.

Hexagonal role
--------------
Outbound adapter implementing ``LlmPort``.  Delegates to the existing
``AmazonClaude35`` implementation for backward compatibility.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import boto3
from acai.ai_llm.domain.content_block import ContentBlock, ContentType
from acai.ai_llm.domain.exceptions import ModelInvocationError, TextTooLongError
from acai.ai_llm.domain.llm_config import LlmConfig
from acai.ai_llm.ports.llm_port import LlmPort
from acai.logging import Loggable
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


@dataclass
class BedrockClaudeConfig(LlmConfig):
    """Configuration specific to the Bedrock Claude adapter."""

    aws_profile: str | None = None
    bedrock_service_name: str = "bedrock-runtime"
    bedrock_service_region: str = "eu-central-1"
    model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"


class BedrockClaudeAdapter(LlmPort):
    """LLM adapter that calls Claude 3.5 Sonnet via Amazon Bedrock."""

    VERSION: str = "1.0.6"  # inject_version

    def __init__(
        self,
        logger: Loggable | None = None,
        config: BedrockClaudeConfig | None = None,
    ) -> None:
        self.config = config or BedrockClaudeConfig()
        self.logger = logger or logging.getLogger("bedrock_claude")
        self._initialize_client()
        self.logger.info(
            "Initialized BedrockClaudeAdapter",
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
        except (BotoCoreError, ClientError) as exc:
            self.logger.error("Failed to initialize AWS client", error=str(exc))
            raise ModelInvocationError(f"AWS client init failed: {exc}") from exc

    def _validate_input(self, text: str) -> None:
        if not text or not isinstance(text, str):
            raise ValueError("Input text must be a non-empty string")
        if len(text) > self.config.max_text_length:
            raise TextTooLongError(
                f"Input text length ({len(text)}) exceeds maximum "
                f"({self.config.max_text_length})"
            )

    @staticmethod
    def _build_content_blocks(
        prompt: str, content_blocks: list[ContentBlock] | None
    ) -> str | list[dict[str, Any]]:
        """Return plain string or Anthropic multi-block content list."""
        if not content_blocks:
            return prompt

        parts: list[dict[str, Any]] = []
        for block in content_blocks:
            if block.content_type == ContentType.TEXT:
                parts.append({"type": "text", "text": block.data})
            elif block.content_type == ContentType.IMAGE:
                parts.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type,
                            "data": block.data,
                        },
                    }
                )
            elif block.content_type == ContentType.DOCUMENT:
                parts.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type,
                            "data": block.data,
                        },
                    }
                )
        parts.append({"type": "text", "text": prompt})
        return parts

    def get_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        content_blocks: list[ContentBlock] | None = None,
    ) -> dict[str, Any]:
        try:
            self._validate_input(prompt)
            self.logger.debug("Generating response", prompt_length=len(prompt))

            content = self._build_content_blocks(prompt, content_blocks)
            messages = [{"role": "user", "content": content}]
            body: dict[str, Any] = {
                "messages": messages,
                "max_tokens": max_tokens or self.config.max_tokens,
                "temperature": (
                    temperature if temperature is not None else self.config.temperature
                ),
                "anthropic_version": "bedrock-2023-05-31",
            }
            if system_prompt:
                body["system"] = system_prompt

            response = self.bedrock.invoke_model(
                modelId=self.config.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())

            if "content" not in response_body:
                raise ModelInvocationError(
                    "Unexpected response: 'content' field missing"
                )

            return {
                "response": response_body["content"][0]["text"],
                "usage": response_body.get("usage", {}),
                "model": self.config.model_id,
            }

        except (TextTooLongError, ValueError):
            raise
        except (BotoCoreError, ClientError) as exc:
            self.logger.error("AWS service error", error=str(exc))
            raise ModelInvocationError(f"AWS service error: {exc}") from exc
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to parse model response", error=str(exc))
            raise ModelInvocationError(f"Invalid response format: {exc}") from exc
        except Exception as exc:
            self.logger.error("Unexpected error", error=str(exc))
            raise ModelInvocationError(f"Unexpected error: {exc}") from exc
