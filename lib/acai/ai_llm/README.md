# acai.ai_llm

A hexagonal LLM module for Claude (Anthropic direct API and AWS Bedrock).  
Swap between providers with a single flag — your application code never changes.

---

## Architecture

```
acai/ai_llm/
├── __init__.py                        # Public API + create_llm() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── llm_port.py                   # LlmPort ABC
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── llm_config.py                 # LlmConfig dataclass
│   ├── llm_pricing.py                # LlmPricingTable
│   ├── content_block.py              # ContentBlock value object
│   └── exceptions.py                 # LlmError → ModelInvocationError, TextTooLongError, ConfigurationError
├── application/                       # ── APPLICATION SERVICES ──
│   └── prompt_evaluation_report.py   # HTML evaluation report generator
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       ├── anthropic_claude_adapter.py   # Anthropic direct API adapter
│       ├── bedrock_claude_adapter.py     # AWS Bedrock adapter
│       └── openai_adapter.py             # OpenAI adapter
└── _test/
    └── (unit tests)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/llm_port.py` | Abstract contract (`LlmPort` ABC). All application code depends *only* on this. |
| **Config VO** | `domain/llm_config.py` | `LlmConfig` dataclass shared by all adapters. |
| **Exceptions** | `domain/exceptions.py` | `LlmError` → `ModelInvocationError`, `TextTooLongError`, `ConfigurationError`. |
| **Content Block** | `domain/content_block.py` | Multi-modal content value object (text, image, document). |
| **Pricing** | `domain/llm_pricing.py` | Token pricing lookup table. |
| **Application** | `application/prompt_evaluation_report.py` | HTML report for prompt evaluation results. |
| **Anthropic adapter** | `adapters/outbound/anthropic_claude_adapter.py` | Driven adapter using the Anthropic SDK directly. |
| **Bedrock adapter** | `adapters/outbound/bedrock_claude_adapter.py` | Driven adapter using Claude via AWS Bedrock. |
| **OpenAI adapter** | `adapters/outbound/openai_adapter.py` | Driven adapter using the OpenAI SDK. |
| **Factory** | `__init__.py` → `create_llm()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `LlmPort`; it never imports an adapter directly.

---

## Quick start

### Anthropic direct API (default)

```python
from acai.logging import create_logger
from acai.ai_llm import create_llm

logger = create_logger()
llm = create_llm(logger, provider="anthropic", api_key="sk-ant-...")

response = llm.get_response(
    prompt="What is article 1 of the Swiss civil code?",
    system_prompt="You are a Swiss law expert.",
)
print(response["response"])
```

### AWS Bedrock

```python
llm = create_llm(
    logger,
    provider="bedrock_claude",
    aws_profile="my-profile",
    region="eu-central-1",
    max_tokens=8192,
    temperature=0.3,
)
```

---

## API reference

### `create_llm(logger, *, provider, api_key, aws_profile, region, model_name, max_tokens, temperature) → LlmPort`

Factory function (composition root).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `provider` | `str` | `"anthropic"` | One of `"anthropic"` or `"bedrock_claude"`. |
| `api_key` | `str` | `""` | API key (Anthropic only). |
| `aws_profile` | `str \| None` | `None` | AWS profile name (Bedrock only). |
| `region` | `str` | `"eu-central-1"` | AWS region (Bedrock only). |
| `model_name` | `str \| None` | `None` | Override the default model name. |
| `max_tokens` | `int` | `4096` | Maximum tokens in the response. |
| `temperature` | `float` | `0.7` | Sampling temperature (0.0-1.0). |

### `LlmPort` (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_response` | `(prompt, system_prompt=None, temperature=None, max_tokens=None) -> dict` | Generate a response. Returns `{"response": str, "usage": dict, "model": str}`. |

### `LlmConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_text_length` | `int` | `200000` | Maximum input text length. |
| `max_tokens` | `int` | `4096` | Maximum response tokens. |
| `temperature` | `float` | `0.7` | Sampling temperature (0.0-1.0). |
| `retry_attempts` | `int` | `3` | Number of retry attempts. |
| `timeout_seconds` | `int` | `60` | Request timeout. |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `LlmError` | `Exception` | Base class for all LLM errors. |
| `ModelInvocationError` | `LlmError` | API call failures. |
| `TextTooLongError` | `LlmError` | Input exceeds `max_text_length`. |
| `ConfigurationError` | `LlmError` | Invalid config values. |

### Backward compatibility

`LlmProtocol` is re-exported as an alias for `LlmPort`, and `PromptError` as an alias for `LlmError`,
so existing code using the old names continues to work.

---

## Testing

```bash
cd shared/python
pytest acai/ai_llm/_test/ -v
```
