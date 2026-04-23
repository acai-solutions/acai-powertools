"""Tests for ``acai.ai_embedding`` — config, factory, normalization, and adapters.

All tests mock external SDK clients so no real API calls are made.
"""

import io
import json
import math
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from acai.ai_embedding import (
    ConfigurationError,
    create_embedder,
)
from acai.ai_embedding.adapters.outbound.openai_ada_embedder import (
    OpenAIAdaConfig,
    OpenAIAdaEmbedder,
)
from acai.ai_embedding.adapters.outbound.openai_large_embedder import (
    OpenAILargeConfig,
    OpenAILargeEmbedder,
)
from acai.ai_embedding.adapters.outbound.voyageai_embedder import (
    VoyageAIConfig,
    VoyageAIEmbedder,
)
from acai.ai_embedding.domain import (
    EmbedderConfig,
    EmbeddingError,
    EmbeddingResult,
    ModelInvocationError,
    MultimodalEmbeddingResult,
    TextTooLongError,
)
from acai.ai_embedding.ports import EmbedderPort

try:
    import boto3  # noqa: F401

    _has_boto3 = True
except ImportError:
    _has_boto3 = False


# ── helpers ───────────────────────────────────────────────────────────


def _l2_norm(vec):
    return math.sqrt(sum(x * x for x in vec))


def _make_voyage_embedder(logger, **overrides) -> VoyageAIEmbedder:
    """Build a VoyageAIEmbedder with a mocked voyageai.Client."""
    defaults = {"api_key": "test-key", "model_name": "voyage-3-large"}
    defaults.update(overrides)
    cfg = VoyageAIConfig(**defaults)
    with patch.object(VoyageAIEmbedder, "_initialize_client"):
        embedder = VoyageAIEmbedder(logger=logger, config=cfg)
    embedder.client = MagicMock()
    return embedder


# ── EmbedderConfig validation ────────────────────────────────────────


class TestEmbedderConfig:
    def test_defaults(self):
        cfg = EmbedderConfig()
        assert cfg.max_text_length == 8192  # nosec B101
        assert cfg.timeout_seconds == 30  # nosec B101
        assert cfg.retry_attempts == 3  # nosec B101

    def test_negative_max_text_length_raises(self):
        with pytest.raises(ConfigurationError, match="max_text_length"):
            EmbedderConfig(max_text_length=-1)

    def test_zero_max_text_length_raises(self):
        with pytest.raises(ConfigurationError, match="max_text_length"):
            EmbedderConfig(max_text_length=0)

    def test_zero_timeout_raises(self):
        with pytest.raises(ConfigurationError, match="timeout_seconds"):
            EmbedderConfig(timeout_seconds=0)

    def test_custom_values(self):
        cfg = EmbedderConfig(max_text_length=500, timeout_seconds=10, retry_attempts=5)
        assert cfg.max_text_length == 500  # nosec B101
        assert cfg.timeout_seconds == 10  # nosec B101
        assert cfg.retry_attempts == 5  # nosec B101


# ── VoyageAIConfig ───────────────────────────────────────────────────


class TestVoyageAIConfig:
    def test_defaults(self):
        cfg = VoyageAIConfig()
        assert cfg.model_name == "voyage-3-large"  # nosec B101
        assert cfg.normalize is True  # nosec B101
        assert cfg.input_type is None  # nosec B101
        assert cfg.max_batch_size == 128  # nosec B101

    def test_custom_model(self):
        cfg = VoyageAIConfig(model_name="voyage-3")
        assert cfg.model_name == "voyage-3"  # nosec B101

    def test_inherits_base_validation(self):
        with pytest.raises(ConfigurationError):
            VoyageAIConfig(max_text_length=-1)


# ── normalization ────────────────────────────────────────────────────


class TestNormalization:
    def test_unit_vector(self):
        result = VoyageAIEmbedder._normalize([3.0, 4.0])
        assert len(result) == 2  # nosec B101
        assert abs(_l2_norm(result) - 1.0) < 1e-9  # nosec B101

    def test_already_normalized(self):
        vec = [1.0, 0.0, 0.0]
        result = VoyageAIEmbedder._normalize(vec)
        assert result == pytest.approx(vec)  # nosec B101

    def test_zero_vector_unchanged(self):
        result = VoyageAIEmbedder._normalize([0.0, 0.0])
        assert result == [0.0, 0.0]  # nosec B101

    def test_high_dimensional(self):
        vec = [float(i) for i in range(1, 129)]
        result = VoyageAIEmbedder._normalize(vec)
        assert abs(_l2_norm(result) - 1.0) < 1e-9  # nosec B101

    def test_negative_values(self):
        result = VoyageAIEmbedder._normalize([-3.0, 4.0])
        assert abs(_l2_norm(result) - 1.0) < 1e-9  # nosec B101
        assert result[0] < 0  # nosec B101


# ── VoyageAIEmbedder ─────────────────────────────────────────────────


class TestVoyageAIEmbedder:
    def test_get_embedding_calls_get_embeddings(self, logger):
        embedder = _make_voyage_embedder(logger)
        embedder.client.embed.return_value = SimpleNamespace(
            embeddings=[[0.6, 0.8]], total_tokens=5
        )
        result = embedder.get_embedding("hello")
        assert isinstance(result, EmbeddingResult)  # nosec B101
        assert len(result.vector) == 2  # nosec B101
        assert result.model == "voyage-3-large"  # nosec B101
        assert result.text == "hello"  # nosec B101
        assert result.dimension == 2  # nosec B101
        assert result.normalized is True  # nosec B101
        assert result.input_type is None  # nosec B101
        assert result.token_count == 5  # nosec B101

    def test_get_embeddings_returns_list(self, logger):
        embedder = _make_voyage_embedder(logger)
        embedder.client.embed.return_value = SimpleNamespace(
            embeddings=[[0.6, 0.8], [0.0, 1.0]], total_tokens=10
        )
        result = embedder.get_embeddings(["hello", "world"])
        assert len(result) == 2  # nosec B101
        assert all(isinstance(r, EmbeddingResult) for r in result)  # nosec B101
        assert result[0].text == "hello"  # nosec B101
        assert result[1].text == "world"  # nosec B101
        assert result[0].dimension == 2  # nosec B101
        # token_count is None for batch > 1
        assert result[0].token_count is None  # nosec B101

    def test_normalization_applied_when_enabled(self, logger):
        embedder = _make_voyage_embedder(logger, normalize=True)
        embedder.client.embed.return_value = SimpleNamespace(
            embeddings=[[3.0, 4.0]], total_tokens=3
        )
        result = embedder.get_embeddings(["test"])
        assert abs(_l2_norm(result[0].vector) - 1.0) < 1e-9  # nosec B101
        assert result[0].normalized is True  # nosec B101

    def test_normalization_skipped_when_disabled(self, logger):
        embedder = _make_voyage_embedder(logger, normalize=False)
        raw = [3.0, 4.0]
        embedder.client.embed.return_value = SimpleNamespace(
            embeddings=[raw.copy()], total_tokens=3
        )
        result = embedder.get_embeddings(["test"])
        assert result[0].vector == raw  # nosec B101
        assert result[0].normalized is False  # nosec B101

    def test_input_type_passed_to_sdk(self, logger):
        embedder = _make_voyage_embedder(logger, input_type="query")
        embedder.client.embed.return_value = SimpleNamespace(
            embeddings=[[1.0, 0.0]], total_tokens=2
        )
        result = embedder.get_embeddings(["test"])
        _, kwargs = embedder.client.embed.call_args
        assert kwargs["input_type"] == "query"  # nosec B101
        assert result[0].input_type == "query"  # nosec B101

    def test_model_name_passed_to_sdk(self, logger):
        embedder = _make_voyage_embedder(logger, model_name="voyage-3-lite")
        embedder.client.embed.return_value = SimpleNamespace(
            embeddings=[[1.0, 0.0]], total_tokens=2
        )
        embedder.get_embeddings(["test"])
        _, kwargs = embedder.client.embed.call_args
        assert kwargs["model"] == "voyage-3-lite"  # nosec B101


# ── input validation ─────────────────────────────────────────────────


class TestInputValidation:
    def test_empty_list_raises(self, logger):
        embedder = _make_voyage_embedder(logger)
        with pytest.raises(ValueError, match="non-empty"):
            embedder.get_embeddings([])

    def test_non_string_raises(self, logger):
        embedder = _make_voyage_embedder(logger)
        with pytest.raises(ValueError, match="non-empty strings"):
            embedder.get_embeddings([123])  # type: ignore[list-item]

    def test_empty_string_raises(self, logger):
        embedder = _make_voyage_embedder(logger)
        with pytest.raises(ValueError, match="non-empty strings"):
            embedder.get_embeddings([""])

    def test_text_too_long_raises(self, logger):
        embedder = _make_voyage_embedder(logger, max_text_length=10)
        with pytest.raises(TextTooLongError):
            embedder.get_embeddings(["x" * 100])

    def test_batch_too_large_raises(self, logger):
        embedder = _make_voyage_embedder(logger, max_batch_size=2)
        with pytest.raises(ValueError, match="Batch size"):
            embedder.get_embeddings(["a", "b", "c"])


# ── SDK error handling ───────────────────────────────────────────────


class TestErrorHandling:
    def test_sdk_error_raises_model_invocation_error(self, logger):
        embedder = _make_voyage_embedder(logger)
        embedder.client.embed.side_effect = RuntimeError("API down")
        with pytest.raises(ModelInvocationError, match="VoyageAI embedding error"):
            embedder.get_embeddings(["test"])

    def test_client_init_failure_raises(self, logger):
        cfg = VoyageAIConfig(api_key="bad")
        with patch.dict("sys.modules", {"voyageai": MagicMock()}) as _:
            import sys

            sys.modules["voyageai"].Client.side_effect = RuntimeError("bad key")
            with pytest.raises(ModelInvocationError, match="initialization failed"):
                VoyageAIEmbedder(logger=logger, config=cfg)


# ── exception hierarchy ──────────────────────────────────────────────


class TestExceptions:
    def test_text_too_long_is_embedding_error(self):
        assert issubclass(TextTooLongError, EmbeddingError)  # nosec B101

    def test_model_invocation_is_embedding_error(self):
        assert issubclass(ModelInvocationError, EmbeddingError)  # nosec B101

    def test_configuration_is_embedding_error(self):
        assert issubclass(ConfigurationError, EmbeddingError)  # nosec B101


# ── factory ──────────────────────────────────────────────────────────


class TestFactory:
    def test_unknown_provider_raises(self, logger):
        with pytest.raises(ConfigurationError, match="Unknown provider"):
            create_embedder(logger, provider="not_real")

    @patch.object(VoyageAIEmbedder, "_initialize_client")
    def test_voyageai_provider(self, mock_init, logger):
        embedder = create_embedder(logger, provider="voyageai", api_key="k")
        assert isinstance(embedder, VoyageAIEmbedder)  # nosec B101

    @patch.object(VoyageAIEmbedder, "_initialize_client")
    def test_voyageai_model_override(self, mock_init, logger):
        embedder = create_embedder(
            logger, provider="voyageai", api_key="k", model_name="voyage-3"
        )
        assert embedder.config.model_name == "voyage-3"  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_openai_large_provider(self, mock_openai, logger):
        embedder = create_embedder(logger, provider="openai_large", api_key="k")
        from acai.ai_embedding.adapters.outbound.openai_large_embedder import (
            OpenAILargeEmbedder,
        )

        assert isinstance(embedder, OpenAILargeEmbedder)  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_openai_ada_provider(self, mock_openai, logger):
        embedder = create_embedder(logger, provider="openai_ada", api_key="k")
        from acai.ai_embedding.adapters.outbound.openai_ada_embedder import (
            OpenAIAdaEmbedder,
        )

        assert isinstance(embedder, OpenAIAdaEmbedder)  # nosec B101

    @pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
    def test_bedrock_titan_provider(self, logger):
        with patch("boto3.Session") as mock_session_cls:
            mock_session_cls.return_value = MagicMock()
            embedder = create_embedder(logger, provider="bedrock_titan")
        from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
            BedrockTitanEmbedder,
        )

        assert isinstance(embedder, BedrockTitanEmbedder)  # nosec B101


# ── port contract ────────────────────────────────────────────────────


class TestPortContract:
    def test_voyageai_implements_port(self, logger):
        embedder = _make_voyage_embedder(logger)
        assert isinstance(embedder, EmbedderPort)  # nosec B101


class TestOpenAILargeMultimodalFallback:
    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_multimodal_embed_extracts_text(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=0, embedding=[0.1, 0.2]),
                SimpleNamespace(index=1, embedding=[0.3, 0.4]),
            ],
            usage=SimpleNamespace(prompt_tokens=7),
        )

        embedder = OpenAILargeEmbedder(
            logger=logger,
            config=OpenAILargeConfig(openai_api_key="k"),
        )
        result = embedder.multimodal_embed(
            [["hello", object()], ["world"]],
            model="text-embedding-3-large",
        )

        assert isinstance(result, MultimodalEmbeddingResult)  # nosec B101
        assert result.embeddings == [[0.1, 0.2], [0.3, 0.4]]  # nosec B101
        assert result.model == "text-embedding-3-large"  # nosec B101
        assert result.total_tokens == 0  # nosec B101
        assert result.text_tokens == 0  # nosec B101

        _, kwargs = mock_client.embeddings.create.call_args
        assert kwargs["input"] == ["hello", "world"]  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_multimodal_embed_without_text_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger,
            config=OpenAILargeConfig(openai_api_key="k"),
        )

        with pytest.raises(ModelInvocationError, match="only support text"):
            embedder.multimodal_embed([[object()]], model="text-embedding-3-large")


# ── domain value objects ─────────────────────────────────────────────


class TestEmbeddingResult:
    def test_to_dict_round_trip(self):
        result = EmbeddingResult(
            vector=[0.1, 0.2, 0.3],
            model="test-model",
            text="hello",
            dimension=3,
            normalized=True,
            input_type="query",
            token_count=5,
        )
        d = result.to_dict()
        assert d["vector"] == [0.1, 0.2, 0.3]  # nosec B101
        assert d["model"] == "test-model"  # nosec B101
        assert d["text"] == "hello"  # nosec B101
        assert d["dimension"] == 3  # nosec B101
        assert d["normalized"] is True  # nosec B101
        assert d["input_type"] == "query"  # nosec B101
        assert d["token_count"] == 5  # nosec B101

    def test_to_dict_optional_defaults(self):
        result = EmbeddingResult(
            vector=[1.0], model="m", text="t", dimension=1, normalized=False
        )
        d = result.to_dict()
        assert d["input_type"] is None  # nosec B101
        assert d["token_count"] is None  # nosec B101

    def test_frozen_immutability(self):
        result = EmbeddingResult(
            vector=[1.0], model="m", text="t", dimension=1, normalized=False
        )
        with pytest.raises(AttributeError):
            result.model = "changed"  # type: ignore[misc]

    def test_frozen_immutability_vector(self):
        result = EmbeddingResult(
            vector=[1.0], model="m", text="t", dimension=1, normalized=False
        )
        with pytest.raises(AttributeError):
            result.vector = [2.0]  # type: ignore[misc]


class TestMultimodalEmbeddingResult:
    def test_defaults(self):
        result = MultimodalEmbeddingResult(embeddings=[[0.1]], model="m")
        assert result.total_tokens == 0  # nosec B101
        assert result.image_pixels == 0  # nosec B101
        assert result.text_tokens == 0  # nosec B101

    def test_frozen_immutability(self):
        result = MultimodalEmbeddingResult(embeddings=[[0.1]], model="m")
        with pytest.raises(AttributeError):
            result.model = "changed"  # type: ignore[misc]

    def test_custom_values(self):
        result = MultimodalEmbeddingResult(
            embeddings=[[0.1], [0.2]],
            model="mm-model",
            total_tokens=100,
            image_pixels=50000,
            text_tokens=80,
        )
        assert len(result.embeddings) == 2  # nosec B101
        assert result.model == "mm-model"  # nosec B101
        assert result.total_tokens == 100  # nosec B101
        assert result.image_pixels == 50000  # nosec B101
        assert result.text_tokens == 80  # nosec B101


# ── OpenAI Large text embedding ──────────────────────────────────────


class TestOpenAILargeConfig:
    def test_defaults(self):
        cfg = OpenAILargeConfig()
        assert cfg.model_name == "text-embedding-3-large"  # nosec B101
        assert cfg.max_text_length == 8192  # nosec B101
        assert cfg.encoding_format == "float"  # nosec B101
        assert cfg.max_batch_size == 2048  # nosec B101

    def test_inherits_base_validation(self):
        with pytest.raises(ConfigurationError):
            OpenAILargeConfig(max_text_length=-1)


class TestOpenAILargeEmbedder:
    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_get_embedding_single(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.5, 0.5])],
            usage=SimpleNamespace(prompt_tokens=3),
        )

        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        result = embedder.get_embedding("hello")

        assert isinstance(result, EmbeddingResult)  # nosec B101
        assert result.vector == [0.5, 0.5]  # nosec B101
        assert result.model == "text-embedding-3-large"  # nosec B101
        assert result.text == "hello"  # nosec B101
        assert result.dimension == 2  # nosec B101
        assert result.normalized is True  # nosec B101
        assert result.token_count == 3  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_get_embeddings_batch(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=0, embedding=[0.1, 0.2]),
                SimpleNamespace(index=1, embedding=[0.3, 0.4]),
            ],
            usage=SimpleNamespace(prompt_tokens=6),
        )

        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        results = embedder.get_embeddings(["a", "b"])

        assert len(results) == 2  # nosec B101
        assert results[0].text == "a"  # nosec B101
        assert results[1].text == "b"  # nosec B101
        # token_count is None for batch > 1
        assert results[0].token_count is None  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_get_embeddings_respects_index_order(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        # Return out-of-order indices
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[0.9, 0.9]),
                SimpleNamespace(index=0, embedding=[0.1, 0.1]),
            ],
            usage=SimpleNamespace(prompt_tokens=4),
        )

        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        results = embedder.get_embeddings(["first", "second"])

        assert results[0].vector == [0.1, 0.1]  # nosec B101
        assert results[1].vector == [0.9, 0.9]  # nosec B101


class TestOpenAILargeValidation:
    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_empty_list_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        with pytest.raises(ValueError, match="non-empty"):
            embedder.get_embeddings([])

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_non_string_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        with pytest.raises(ValueError, match="non-empty strings"):
            embedder.get_embeddings([123])  # type: ignore[list-item]

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_empty_string_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        with pytest.raises(ValueError, match="non-empty strings"):
            embedder.get_embeddings([""])

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_text_too_long_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger,
            config=OpenAILargeConfig(openai_api_key="k", max_text_length=10),
        )
        with pytest.raises(TextTooLongError):
            embedder.get_embeddings(["x" * 100])

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_batch_too_large_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger,
            config=OpenAILargeConfig(openai_api_key="k", max_batch_size=2),
        )
        with pytest.raises(ValueError, match="Batch size"):
            embedder.get_embeddings(["a", "b", "c"])


class TestOpenAILargeErrorHandling:
    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_auth_error(self, mock_openai, logger):
        from openai import AuthenticationError

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.side_effect = AuthenticationError(
            message="bad key",
            response=MagicMock(status_code=401),
            body=None,
        )
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="Invalid OpenAI API key"):
            embedder.get_embeddings(["test"])

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_rate_limit_error(self, mock_openai, logger):
        from openai import RateLimitError

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.side_effect = RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="Too many requests"):
            embedder.get_embeddings(["test"])

    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_generic_openai_error(self, mock_openai, logger):
        from openai import OpenAIError

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.side_effect = OpenAIError("boom")
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="OpenAI service error"):
            embedder.get_embeddings(["test"])


# ── OpenAI Ada adapter ───────────────────────────────────────────────


class TestOpenAIAdaConfig:
    def test_defaults(self):
        cfg = OpenAIAdaConfig()
        assert cfg.model_name == "text-embedding-ada-002"  # nosec B101
        assert cfg.max_text_length == 8192  # nosec B101

    def test_inherits_base_validation(self):
        with pytest.raises(ConfigurationError):
            OpenAIAdaConfig(max_text_length=-1)


class TestOpenAIAdaEmbedder:
    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_get_embedding_single(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
            usage=SimpleNamespace(total_tokens=4),
        )

        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        result = embedder.get_embedding("hello")

        assert result.vector == [0.1, 0.2, 0.3]  # nosec B101
        assert result.model == "text-embedding-ada-002"  # nosec B101
        assert result.text == "hello"  # nosec B101
        assert result.dimension == 3  # nosec B101
        assert result.normalized is True  # nosec B101
        assert result.token_count == 4  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_get_embeddings_delegates_per_text(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0])],
            usage=SimpleNamespace(total_tokens=2),
        )

        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        results = embedder.get_embeddings(["a", "b"])

        assert len(results) == 2  # nosec B101
        assert mock_client.embeddings.create.call_count == 2  # nosec B101


class TestOpenAIAdaValidation:
    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_empty_string_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        with pytest.raises(ValueError, match="non-empty string"):
            embedder.get_embedding("")

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_non_string_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        with pytest.raises(ValueError, match="non-empty string"):
            embedder.get_embedding(123)  # type: ignore[arg-type]

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_text_too_long_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k", max_text_length=5)
        )
        with pytest.raises(TextTooLongError):
            embedder.get_embedding("x" * 100)


class TestOpenAIAdaErrorHandling:
    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_auth_error(self, mock_openai, logger):
        from openai import AuthenticationError

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.side_effect = AuthenticationError(
            message="bad key",
            response=MagicMock(status_code=401),
            body=None,
        )
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="Invalid OpenAI API key"):
            embedder.get_embedding("test")

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_rate_limit_error(self, mock_openai, logger):
        from openai import RateLimitError

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.side_effect = RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="Too many requests"):
            embedder.get_embedding("test")

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_generic_openai_error(self, mock_openai, logger):
        from openai import OpenAIError

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.side_effect = OpenAIError("boom")
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="OpenAI service error"):
            embedder.get_embedding("test")


class TestOpenAIAdaMultimodalFallback:
    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_multimodal_embed_extracts_text(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.5, 0.5])],
            usage=SimpleNamespace(total_tokens=3),
        )

        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        result = embedder.multimodal_embed(
            [["hello world"]], model="text-embedding-ada-002"
        )

        assert isinstance(result, MultimodalEmbeddingResult)  # nosec B101
        assert len(result.embeddings) == 1  # nosec B101
        assert result.model == "text-embedding-ada-002"  # nosec B101
        assert result.text_tokens == result.total_tokens  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_multimodal_embed_warns_non_text(self, mock_openai, logger):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.5])],
            usage=SimpleNamespace(total_tokens=2),
        )

        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        # Should succeed, ignoring non-text items
        result = embedder.multimodal_embed([["hello", object()]], model="ada")
        assert len(result.embeddings) == 1  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_multimodal_embed_no_text_raises(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        with pytest.raises(ModelInvocationError, match="only support text"):
            embedder.multimodal_embed([[object()]], model="ada")


# ── Bedrock Titan adapter ────────────────────────────────────────────


@pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
class TestBedrockTitanConfig:
    def test_defaults(self):
        from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
            BedrockTitanConfig,
        )

        cfg = BedrockTitanConfig()
        assert cfg.bedrock_service_region == "eu-central-1"  # nosec B101
        assert cfg.bedrock_service_name == "bedrock-runtime"  # nosec B101
        assert cfg.aws_profile is None  # nosec B101
        assert cfg.max_text_length == 8000  # nosec B101

    def test_inherits_base_validation(self):
        from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
            BedrockTitanConfig,
        )

        with pytest.raises(ConfigurationError):
            BedrockTitanConfig(max_text_length=-1)


def _make_bedrock_embedder(logger):
    """Build a BedrockTitanEmbedder with a mocked boto3 client."""
    from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
        BedrockTitanConfig,
        BedrockTitanEmbedder,
    )

    cfg = BedrockTitanConfig()
    with patch.object(BedrockTitanEmbedder, "_initialize_client"):
        embedder = BedrockTitanEmbedder(logger=logger, config=cfg)
    embedder.bedrock = MagicMock()
    return embedder


def _bedrock_response(embedding, token_count=5):
    """Create a mock Bedrock invoke_model response."""
    body = json.dumps(
        {
            "embedding": embedding,
            "inputTextTokenCount": token_count,
        }
    ).encode()
    return {"body": io.BytesIO(body)}


@pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
class TestBedrockTitanEmbedder:
    def test_get_embedding_single(self, logger):
        embedder = _make_bedrock_embedder(logger)
        embedder.bedrock.invoke_model.return_value = _bedrock_response([0.1, 0.2], 3)

        result = embedder.get_embedding("hello")

        assert result.vector == [0.1, 0.2]  # nosec B101
        assert result.model == "amazon.titan-embed-text-v1"  # nosec B101
        assert result.text == "hello"  # nosec B101
        assert result.dimension == 2  # nosec B101
        assert result.normalized is True  # nosec B101
        assert result.token_count == 3  # nosec B101

    def test_get_embeddings_calls_per_text(self, logger):
        embedder = _make_bedrock_embedder(logger)
        # Each call needs a fresh BytesIO stream
        embedder.bedrock.invoke_model.side_effect = lambda **kw: _bedrock_response(
            [1.0]
        )

        results = embedder.get_embeddings(["a", "b"])

        assert len(results) == 2  # nosec B101
        assert embedder.bedrock.invoke_model.call_count == 2  # nosec B101

    def test_missing_embedding_field_raises(self, logger):
        embedder = _make_bedrock_embedder(logger)
        body = json.dumps({"inputTextTokenCount": 1}).encode()
        embedder.bedrock.invoke_model.return_value = {"body": io.BytesIO(body)}

        with pytest.raises(ModelInvocationError, match="embedding.*missing"):
            embedder.get_embedding("test")

    def test_invalid_json_raises(self, logger):
        embedder = _make_bedrock_embedder(logger)
        embedder.bedrock.invoke_model.return_value = {"body": io.BytesIO(b"not json")}

        with pytest.raises(ModelInvocationError, match="Invalid model response"):
            embedder.get_embedding("test")


@pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
class TestBedrockTitanValidation:
    def test_empty_text_raises(self, logger):
        embedder = _make_bedrock_embedder(logger)
        with pytest.raises(ValueError, match="non-empty string"):
            embedder.get_embedding("")

    def test_non_string_raises(self, logger):
        embedder = _make_bedrock_embedder(logger)
        with pytest.raises(ValueError, match="non-empty string"):
            embedder.get_embedding(123)  # type: ignore[arg-type]

    def test_text_too_long_raises(self, logger):
        from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
            BedrockTitanConfig,
            BedrockTitanEmbedder,
        )

        cfg = BedrockTitanConfig(max_text_length=5)
        with patch.object(BedrockTitanEmbedder, "_initialize_client"):
            embedder = BedrockTitanEmbedder(logger=logger, config=cfg)
        with pytest.raises(TextTooLongError):
            embedder.get_embedding("x" * 100)


@pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
class TestBedrockTitanErrorHandling:
    def test_botocore_error_raises(self, logger):
        from botocore.exceptions import BotoCoreError

        embedder = _make_bedrock_embedder(logger)
        embedder.bedrock.invoke_model.side_effect = BotoCoreError()

        with pytest.raises(ModelInvocationError, match="AWS service error"):
            embedder.get_embedding("test")

    def test_client_init_failure(self, logger):
        from acai.ai_embedding.adapters.outbound.bedrock_titan_embedder import (
            BedrockTitanConfig,
            BedrockTitanEmbedder,
        )
        from botocore.exceptions import BotoCoreError

        with patch("boto3.Session", side_effect=BotoCoreError()):
            with pytest.raises(ModelInvocationError, match="initialization failed"):
                BedrockTitanEmbedder(logger=logger, config=BedrockTitanConfig())


@pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
class TestBedrockTitanMultimodal:
    def test_text_only_input(self, logger):
        embedder = _make_bedrock_embedder(logger)
        body = json.dumps(
            {
                "embedding": [0.5, 0.5],
                "inputTextTokenCount": 4,
            }
        ).encode()
        embedder.bedrock.invoke_model.return_value = {"body": io.BytesIO(body)}

        result = embedder.multimodal_embed(
            [["hello world"]], model="amazon.titan-embed-image-v1"
        )

        assert isinstance(result, MultimodalEmbeddingResult)  # nosec B101
        assert result.embeddings == [[0.5, 0.5]]  # nosec B101
        assert result.model == "amazon.titan-embed-image-v1"  # nosec B101
        assert result.total_tokens == 4  # nosec B101

    def test_image_input(self, logger):
        embedder = _make_bedrock_embedder(logger)
        body = json.dumps(
            {
                "embedding": [0.1, 0.2],
                "inputTextTokenCount": 0,
            }
        ).encode()
        embedder.bedrock.invoke_model.return_value = {"body": io.BytesIO(body)}

        # Mock a PIL-like image
        mock_image = MagicMock()
        mock_image.size = (100, 200)
        mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(b"png"))

        result = embedder.multimodal_embed(
            [[mock_image]], model="amazon.titan-embed-image-v1"
        )

        assert result.image_pixels == 20000  # nosec B101
        assert len(result.embeddings) == 1  # nosec B101

    def test_text_plus_image_input(self, logger):
        embedder = _make_bedrock_embedder(logger)
        body = json.dumps(
            {
                "embedding": [0.3, 0.4],
                "inputTextTokenCount": 2,
            }
        ).encode()
        embedder.bedrock.invoke_model.return_value = {"body": io.BytesIO(body)}

        mock_image = MagicMock()
        mock_image.size = (50, 50)
        mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(b"png"))

        result = embedder.multimodal_embed(
            [["caption text", mock_image]], model="amazon.titan-embed-image-v1"
        )

        assert result.total_tokens == 2  # nosec B101
        assert result.image_pixels == 2500  # nosec B101
        # Verify the body sent included both text and image
        call_kwargs = embedder.bedrock.invoke_model.call_args[1]
        sent_body = json.loads(call_kwargs["body"])
        assert "inputText" in sent_body  # nosec B101
        assert "inputImage" in sent_body  # nosec B101

    def test_empty_input_raises(self, logger):
        embedder = _make_bedrock_embedder(logger)

        with pytest.raises(ModelInvocationError, match="at least one text or image"):
            embedder.multimodal_embed([[]], model="amazon.titan-embed-image-v1")

    def test_missing_embedding_in_response_raises(self, logger):
        embedder = _make_bedrock_embedder(logger)
        body = json.dumps({"inputTextTokenCount": 1}).encode()
        embedder.bedrock.invoke_model.return_value = {"body": io.BytesIO(body)}

        with pytest.raises(ModelInvocationError, match="embedding.*missing"):
            embedder.multimodal_embed([["text"]], model="amazon.titan-embed-image-v1")


# ── VoyageAI multimodal ─────────────────────────────────────────────


class TestVoyageAIMultimodal:
    def test_multimodal_embed_basic(self, logger):
        embedder = _make_voyage_embedder(logger)
        embedder.client.multimodal_embed.return_value = SimpleNamespace(
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            total_tokens=10,
            image_pixels=5000,
            text_tokens=8,
        )

        result = embedder.multimodal_embed(
            [["text", MagicMock()], ["other text"]],
            model="voyage-multimodal-3",
        )

        assert isinstance(result, MultimodalEmbeddingResult)  # nosec B101
        assert len(result.embeddings) == 2  # nosec B101
        assert result.model == "voyage-multimodal-3"  # nosec B101
        assert result.total_tokens == 10  # nosec B101
        assert result.image_pixels == 5000  # nosec B101
        assert result.text_tokens == 8  # nosec B101

    def test_multimodal_embed_normalization(self, logger):
        embedder = _make_voyage_embedder(logger, normalize=True)
        embedder.client.multimodal_embed.return_value = SimpleNamespace(
            embeddings=[[3.0, 4.0]],
            total_tokens=5,
            image_pixels=0,
            text_tokens=5,
        )

        result = embedder.multimodal_embed([["text"]], model="voyage-multimodal-3")

        assert abs(_l2_norm(result.embeddings[0]) - 1.0) < 1e-9  # nosec B101

    def test_multimodal_embed_no_normalization(self, logger):
        embedder = _make_voyage_embedder(logger, normalize=False)
        raw = [3.0, 4.0]
        embedder.client.multimodal_embed.return_value = SimpleNamespace(
            embeddings=[raw.copy()],
            total_tokens=5,
            image_pixels=0,
            text_tokens=5,
        )

        result = embedder.multimodal_embed([["text"]], model="voyage-multimodal-3")

        assert result.embeddings[0] == raw  # nosec B101

    def test_multimodal_embed_input_type_forwarded(self, logger):
        embedder = _make_voyage_embedder(logger)
        embedder.client.multimodal_embed.return_value = SimpleNamespace(
            embeddings=[[1.0, 0.0]],
            total_tokens=2,
            image_pixels=0,
            text_tokens=2,
        )

        embedder.multimodal_embed(
            [["text"]], model="voyage-multimodal-3", input_type="query"
        )

        _, kwargs = embedder.client.multimodal_embed.call_args
        assert kwargs["input_type"] == "query"  # nosec B101

    def test_multimodal_embed_sdk_error_raises(self, logger):
        embedder = _make_voyage_embedder(logger)
        embedder.client.multimodal_embed.side_effect = RuntimeError("API down")

        with pytest.raises(ModelInvocationError, match="VoyageAI multimodal"):
            embedder.multimodal_embed([["text"]], model="voyage-multimodal-3")


# ── port contract (all adapters) ─────────────────────────────────────


class TestPortContractAllAdapters:
    @patch("acai.ai_embedding.adapters.outbound.openai_large_embedder.OpenAI")
    def test_openai_large_implements_port(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAILargeEmbedder(
            logger=logger, config=OpenAILargeConfig(openai_api_key="k")
        )
        assert isinstance(embedder, EmbedderPort)  # nosec B101

    @patch("acai.ai_embedding.adapters.outbound.openai_ada_embedder.OpenAI")
    def test_openai_ada_implements_port(self, mock_openai, logger):
        mock_openai.return_value = MagicMock()
        embedder = OpenAIAdaEmbedder(
            logger=logger, config=OpenAIAdaConfig(openai_api_key="k")
        )
        assert isinstance(embedder, EmbedderPort)  # nosec B101

    @pytest.mark.skipif(not _has_boto3, reason="boto3 not installed")
    def test_bedrock_titan_implements_port(self, logger):
        embedder = _make_bedrock_embedder(logger)
        assert isinstance(embedder, EmbedderPort)  # nosec B101


class TestBasePortMultimodalDefault:
    def test_default_multimodal_raises_not_implemented(self, logger):
        """A minimal concrete port that doesn't override multimodal_embed."""

        class _MinimalEmbedder(EmbedderPort):
            def get_embedding(self, text):
                return EmbeddingResult(
                    vector=[0.0], model="m", text=text, dimension=1, normalized=False
                )

            def get_embeddings(self, texts):
                return [self.get_embedding(t) for t in texts]

        embedder = _MinimalEmbedder()
        with pytest.raises(NotImplementedError, match="does not support multimodal"):
            embedder.multimodal_embed([["text"]], model="any")
