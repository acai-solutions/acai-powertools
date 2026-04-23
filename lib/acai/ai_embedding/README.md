# acai.ai_embedding

A multi-provider text-embedding module built on **hexagonal architecture** principles.  
Swap between OpenAI, AWS Bedrock Titan, and Voyage AI with a single flag — your application code never changes.

---

## Architecture

```
acai/ai_embedding/
├── __init__.py                        # Public API + create_embedder() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── embedder_port.py              # EmbedderPort ABC
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── embedder_config.py            # EmbedderConfig dataclass
│   ├── embedding_result.py           # EmbeddingResult value object
│   └── exceptions.py                 # EmbeddingError → TextTooLongError, ModelInvocationError, ConfigurationError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       ├── bedrock_titan_embedder.py  # AWS Bedrock Titan adapter
│       ├── openai_large_embedder.py   # OpenAI text-embedding-3-large adapter
│       ├── openai_ada_embedder.py     # OpenAI text-embedding-ada-002 adapter
│       └── voyageai_embedder.py       # Voyage AI adapter
├── _example/
│   ├── bedrock_titan_example.py       # Bedrock Titan usage demo
│   ├── openai_large_example.py        # OpenAI large usage demo
│   ├── openai_ada_example.py          # OpenAI Ada usage demo
│   ├── voyageai_example.py            # Voyage AI usage demo
│   ├── embedding_example.py           # General embedding demo
│   └── demo_embedding.ipynb           # Interactive notebook
└── _test/
    └── test_llm_embedding.py          # Unit tests (mocked)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/embedder_port.py` | Abstract contract (`EmbedderPort` ABC). All application code depends *only* on this. |
| **Config VO** | `domain/embedder_config.py` | `EmbedderConfig` dataclass shared by all adapters. |
| **Result VO** | `domain/embedding_result.py` | `EmbeddingResult` — immutable value object with vector, model, dimension, etc. |
| **Exceptions** | `domain/exceptions.py` | `EmbeddingError` → `TextTooLongError`, `ModelInvocationError`, `ConfigurationError`. |
| **Adapters** | `adapters/outbound/` | Four driven adapters: Bedrock Titan, OpenAI Large, OpenAI Ada, Voyage AI. |
| **Factory** | `__init__.py` → `create_embedder()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `EmbedderPort` and `EmbeddingResult`; it never imports an adapter directly.

---

## Quick start

```python
from acai.logging import create_logger
from acai.ai_embedding import create_embedder

logger = create_logger()

# OpenAI text-embedding-3-large (default)
embedder = create_embedder(logger, provider="openai_large", api_key="sk-...")
result = embedder.get_embedding("Swiss civil code article 1")
print(result.dimension, result.model)

# Batch embeddings
results = embedder.get_embeddings(["text one", "text two"])
```

### Provider selection

```python
# AWS Bedrock Titan
embedder = create_embedder(logger, provider="bedrock_titan", aws_profile="my-profile", region="eu-central-1")

# OpenAI Ada
embedder = create_embedder(logger, provider="openai_ada", api_key="sk-...")

# Voyage AI
embedder = create_embedder(logger, provider="voyageai", api_key="pa-...")
```

---

## API reference

### `create_embedder(logger, *, provider, api_key, aws_profile, region, model_name) → EmbedderPort`

Factory function (composition root).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `provider` | `str` | `"openai_large"` | One of `"openai_large"`, `"openai_ada"`, `"bedrock_titan"`, `"voyageai"`. |
| `api_key` | `str` | `""` | API key for OpenAI or Voyage adapters. |
| `aws_profile` | `str \| None` | `None` | AWS profile name (Bedrock only). |
| `region` | `str` | `"eu-central-1"` | AWS region (Bedrock only). |
| `model_name` | `str \| None` | `None` | Override the default model name. |

### `EmbedderPort` (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_embedding` | `(text: str) -> EmbeddingResult` | Generate an embedding for a single text. |
| `get_embeddings` | `(texts: list[str]) -> list[EmbeddingResult]` | Generate embeddings for multiple texts. |
| `multimodal_embed` | `(inputs: list[list[Any]], model: str, input_type: str \| None = None) -> MultimodalEmbeddingResult` | Generate embeddings for multimodal input (text/image), where supported by provider. |

### Multimodal support matrix

| Provider | `multimodal_embed` behavior |
|----------|-----------------------------|
| `voyageai` | Native multimodal embedding via Voyage API. |
| `bedrock_titan` | Native multimodal embedding for Titan multimodal models. |
| `openai_ada` | Text-only fallback: extracts and embeds string content from each multimodal input. |
| `openai_large` | Text-only fallback: extracts and embeds string content from each multimodal input. |

### `EmbedderConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_text_length` | `int` | `8192` | Maximum input text length in characters. |
| `timeout_seconds` | `int` | `30` | Request timeout. |
| `retry_attempts` | `int` | `3` | Number of retry attempts. |

### `EmbeddingResult` (frozen dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `vector` | `list[float]` | The embedding vector. |
| `model` | `str` | Model identifier (e.g. `"text-embedding-3-large"`). |
| `text` | `str` | The original input text. |
| `dimension` | `int` | Length of the embedding vector. |
| `normalized` | `bool` | Whether the vector has unit L2 norm. |
| `input_type` | `str \| None` | Role hint for asymmetric models (`"query"` / `"document"`). |
| `token_count` | `int \| None` | Tokens consumed for this text. |

### `MultimodalEmbeddingResult` (frozen dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `embeddings` | `list[list[float]]` | One embedding vector per multimodal input item. |
| `model` | `str` | Model identifier used for the multimodal call. |
| `total_tokens` | `int` | Total tokens consumed for the request. |
| `image_pixels` | `int` | Total image pixels processed (if available). |
| `text_tokens` | `int` | Total text tokens processed (if available). |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `EmbeddingError` | `Exception` | Base class for all embedding errors. |
| `TextTooLongError` | `EmbeddingError` | Input exceeds `max_text_length`. |
| `ModelInvocationError` | `EmbeddingError` | API call failures. |
| `ConfigurationError` | `EmbeddingError` | Invalid config values. |

---

## Testing

```bash
cd shared/python
pytest acai/ai_embedding/_test/ -v
```
