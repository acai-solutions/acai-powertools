# acai-powertools

## Overview

`acai-powertools` contains the **acai** shared Python library (`lib/acai/`), providing reusable modules for AI embedding, LLM integration, hybrid search, text search, logging, storage, vector search, web scraping, and XML parsing.

- Target runtime: **Python 3.12**
- Primary environment: **AWS Lambda**
- Design approach: **Selective Hexagonal Architecture (Ports & Adapters where valuable)**

> **Guiding philosophy:** Use abstraction where it adds value, not by default.

## Hexagonal Architecture — Applied Selectively

Use full ports & adapters **only when**:
- Multiple implementations are expected (e.g., OpenAI vs Bedrock embedders)
- External systems are involved (databases, APIs, cloud services)
- Swappability or test isolation is valuable

Avoid unnecessary abstraction for simple utilities, thin library wrappers, or pure in-memory logic.

### Module structure (hexagonal modules)

```
acai/<module>/
├── ports/            # Abstract base classes (ABCs) — the contracts
│   └── <name>_port.py
├── domain/           # Value objects, config dataclasses, exceptions
│   ├── <name>_config.py
│   ├── <name>_models.py   (if needed)
│   └── exceptions.py
├── adapters/
│   └── outbound/     # Concrete implementations of the port
│       └── <impl>.py
├── _test/            # Unit tests (mocked, no real API calls)
│   ├── __init__.py
│   └── test_<name>.py
├── _example/        # Runnable usage demos (.py and .ipynb)
│   ├── <adapter>_example.py
│   └── demo_<module>.ipynb
└── __init__.py       # Public surface: re-exports ports, domain, factory
```

### Hexagonal modules

| Module | Port | Adapters |
|--------|------|----------|
| `ai_embedding` | `EmbedderPort` | `BedrockTitanEmbedder`, `OpenAILargeEmbedder`, `OpenAIAdaEmbedder`, `VoyageAIEmbedder` |
| `ai_hybrid_search` | `HybridSearchPort` | `RRFHybridSearchAdapter` |
| `ai_llm` | `LlmPort` | `AnthropicClaudeAdapter`, `BedrockClaudeAdapter` |
| `ai_text_search` | `TextSearchPort` | `PgFulltextSearchAdapter` |
| `ai_vector_store` | `VectorStorePort` | `PgvectorStore` |
| `logging` | `LoggerPort` / `Loggable` | `ConsoleLogger`, `FileLogger`, `CloudWatchLogger` |
| `storage` | `StoragePort` (`StorageReader`, `StorageWriter`) | `LocalFileStorage`, `S3Storage` (stub) |
| `webcrawler` | `WebScraperPort` | `SeleniumScraper` |
| `xml_parser` | `XmlParserPort` | `LxmlParser` |

### Non-hexagonal utility modules

`ai_tools`, `boto3_helper`, `python_helper` — flat utility code without hexagonal structure. Each must still have an `__init__.py` with a docstring and `__all__`.

## Dependency & API Rules

- **Depend on ports, not adapters.** Application code imports the port ABC and domain models from `__init__.py`. Adapter imports happen only at the composition root or in examples.
- **Public API via `__init__.py`.** Consumers import only from `from acai.<module> import ...`.
- **Factory functions** (`create_<module>()`) are provided for convenience but not enforced as the only construction pattern.
- **Value objects are immutable.** Use `@dataclass(frozen=True)` for result/record types like `EmbeddingResult`, `VectorRecord`, `SearchResult`.
- **Configuration via dataclasses.** Each module has a base `*Config` dataclass with `__post_init__` validation. Adapters extend with adapter-specific fields (e.g. `OpenAIAdaConfig(EmbedderConfig)`). Prefer composition over inheritance.
- **Logging is injected.** Adapters receive a `Loggable` protocol instance in `__init__`. Prefer compatibility with `logging.Logger`.
- **Every package has `__init__.py`.** All directories that are Python packages must have `__init__.py` — including `_test/`, utility modules, and the root `acai/` package. Include a module docstring and `__all__` where applicable.

## Coding Standards

### Type hints
- **All** function signatures must have parameter types and return type annotations.
- Use `from __future__ import annotations` for forward references.
- Prefer `X | None` over `Optional[X]` (Python 3.12).

### No mutable defaults
- Never use mutable defaults in function signatures (e.g. `def f(x: dict = {})`).
- Use `None` with a conditional: `def f(x: dict[str, Any] | None = None)` → `x = x or {}`.

### Imports
- Consistent import style within adapter `__init__.py` files (eager or lazy, not mixed).
- Relative imports within a module. Absolute `acai.*` imports across modules.

### Docstrings
- All port ABCs, adapter classes, domain models, and public functions must have docstrings.
- Module-level docstrings in every `__init__.py`.

### Exception handling
- Each hex module defines a base exception (e.g. `EmbeddingError`) with specific subclasses.
- Adapters catch SDK-specific exceptions and re-raise as domain exceptions.

### General
- `dataclasses` for config and DTOs.
- `ABC` for port contracts, `Protocol` for lightweight interfaces (e.g. `Loggable`).
- Secrets exclusively from environment variables via `python-dotenv`.
- Never hardcode API keys, passwords, or hostnames.
- In comments us - instead of –

## `_test/` folders — Testing conventions

- Tests live in `_test/` inside each module (not a top-level `tests/` dir).
- Every `_test/` folder must contain an `__init__.py` (empty is fine).
- File naming: `test_<name>.py` — discovered by pytest via `python_files = ["test_*.py"]`.
- **Always mock external SDKs** (`unittest.mock.patch`, `MagicMock`). No real API calls in tests.
- Import domain models and adapters directly in test code.
- Prefer local fixtures; use `acai/conftest.py` only for truly shared fixtures.
- pytest config is in `lib/pyproject.toml`.
- Each module must be testable independently: `pytest acai/<module>/_test`
- Full test suite: `cd lib && pytest`

## `_example/` folders — Example conventions

- Examples live in `_example/` inside each module.
- Each adapter gets its own runnable `<adapter>_example.py`.
- Optional Jupyter notebooks (`demo_<module>.ipynb`) for interactive exploration.
- Credentials via `.env` files (never committed). Load with `python-dotenv`.
- `_example/` is excluded from pytest discovery (`norecursedirs`).

## Tech stack

- **Key libraries**: openai, boto3, psycopg2, selenium, beautifulsoup4, pydantic, pgvector, numpy, voyageai, lxml
- **Package config**: `lib/pyproject.toml` (setuptools, editable install `pip install -e .`)
- **Test framework**: pytest
