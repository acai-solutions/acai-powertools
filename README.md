# acai-powertools

<!-- LOGO -->
<a href="https://acai.gmbh">    
  <img src="https://github.com/acai-solutions/acai.public/raw/main/logo/logo_github_readme.png" alt="acai logo" title="ACAI" align="right" height="75" />
</a>

<!-- SHIELDS -->
[![Maintained by acai.gmbh][acai-shield]][acai-url]
![module-version-shield]  
![terraform-tested-shield]
![opentofu-tested-shield]    
![aws-tested-shield]
![aws-esc-tested-shield]  

<!-- BEGIN_ACAI_DOCS -->
## Overview

`acai-powertools` contains the **ACAI** shared Python library (`lib/acai/`), providing reusable modules for AI embedding, LLM integration, hybrid search, logging, storage, vector search, web scraping, and XML parsing.

- Target runtime: **Python 3.12**
- Primary environment: **AWS Lambda**
- Design approach: **Selective Hexagonal Architecture (Ports & Adapters where valuable)**

> **Guiding philosophy:** Use abstraction where it adds value, not by default.

---

## Modules

### Hexagonal modules (Ports & Adapters)

| Module | Port | Adapters | Description |
|--------|------|----------|-------------|
| [`ai_embedding`](lib/acai/ai_embedding/) | `EmbedderPort` | `BedrockTitanEmbedder`, `OpenAILargeEmbedder`, `OpenAIAdaEmbedder`, `VoyageAIEmbedder` | Multi-provider text embedding |
| [`ai_hybrid_search`](lib/acai/ai_hybrid_search/) | `HybridSearchPort` | `RRFHybridSearchAdapter` | Reciprocal Rank Fusion over semantic + keyword search |
| [`ai_llm`](lib/acai/ai_llm/) | `LlmPort` | `AnthropicClaudeAdapter`, `BedrockClaudeAdapter` | Claude LLM integration (direct API & AWS Bedrock) |
| [`ai_text_search`](lib/acai/ai_text_search/) | `TextSearchPort` | `PgFulltextSearchAdapter` | PostgreSQL native full-text search |
| [`ai_vector_store`](lib/acai/ai_vector_store/) | `VectorStorePort` | `PgvectorStore` | pgvector-based similarity search |
| [`logging`](lib/acai/logging/) | `LoggerPort` / `Loggable` | `ConsoleLogger`, `FileLogger`, `CloudWatchLogger` | Structured logging with context stack |
| [`pdf_to_json`](lib/acai/pdf_to_json/) | `PdfParserPort` | `PyMuPdfParser` | PDF → structured JSON (text, images, tables) |
| [`storage`](lib/acai/storage/) | `StoragePort` | `LocalFileStorage`, `S3Storage` (stub) | File persistence with atomic writes |
| [`webcrawler`](lib/acai/webcrawler/) | `WebScraperPort` | `SeleniumScraper` | Web scraping with Selenium |
| [`xml_parser`](lib/acai/xml_parser/) | `XmlParserPort` | `LxmlParser` | Swiss AKN legal-document parsing |

### Utility modules

| Module | Description |
|--------|-------------|
| [`ai_tools`](lib/acai/ai_tools/) | BM25 search index, text editor tool, Claude tool schemas |
| [`aws_helper`](lib/acai/aws_helper/) | AWS SDK wrappers (sessions, STS, S3, CloudWatch, Organizations, OU path resolver, SNS) |
| [`python_helper`](lib/acai/python_helper/) | Hashing, datetime conversion, JSON utilities |

Each module has its own README with architecture details, quick start, and API reference.

---

## Quick start

```bash
cd lib
pip install -e .
```

```python
from acai.logging import create_logger
from acai.ai_embedding import create_embedder

logger = create_logger()
embedder = create_embedder(logger, provider="openai_large", api_key="sk-...")

result = embedder.get_embedding("Swiss civil code article 1")
print(result.dimension, result.model)
```

---

## Project structure

```
acai-powertools/
├── lib/
│   ├── pyproject.toml              # Package config (setuptools, pytest)
│   └── acai/                       # Root package
│       ├── ai_embedding/           # Hexagonal — multi-provider embeddings
│       ├── ai_hybrid_search/       # Hexagonal — RRF hybrid retrieval
│       ├── ai_llm/                 # Hexagonal — Claude LLM
│       ├── ai_text_search/         # Hexagonal — PostgreSQL FTS
│       ├── ai_vector_store/        # Hexagonal — pgvector store
│       ├── logging/                # Hexagonal — structured logging
│       ├── pdf_to_json/            # Hexagonal — PDF parsing to JSON
│       ├── storage/                # Hexagonal — file persistence
│       ├── webcrawler/             # Hexagonal — Selenium scraping
│       ├── xml_parser/             # Hexagonal — AKN XML parsing
│       ├── ai_tools/               # Utility — BM25, text editor, schemas
│       ├── aws_helper/             # Utility — AWS SDK wrappers
│       └── python_helper/          # Utility — general helpers
└── use-cases/
    ├── terraform-aws-lambda-layer/ # Terraform module + build script for Lambda layer
    └── local-example-1/            # Demo: logging + storage usage
```

### Hexagonal module layout

```
acai/<module>/
├── __init__.py           # Public API + create_*() factory
├── ports/                # Abstract base classes (contracts)
├── domain/               # Config dataclasses, value objects, exceptions
├── adapters/outbound/    # Concrete implementations
├── _test/                # Unit tests (mocked, no real API calls)
└── _example/            # Runnable demos (.py and .ipynb)
```

---

## Architectural principles

### Apply Hexagonal Architecture selectively

Use full ports & adapters **only when**:
- Multiple implementations are expected (e.g., OpenAI vs Bedrock)
- External systems are involved
- Swappability or test isolation is valuable

Avoid unnecessary abstraction for simple utilities, thin wrappers, or pure in-memory logic.

### Dependency rules

- Application code depends on **ports**, not adapters
- Adapters depend on ports, domain models, and external SDKs
- Wiring happens at the **composition root** (`create_*()` factories)

### Public API

Each module defines its public API in `__init__.py`. Consumers import only from:

```python
from acai.<module> import ...
```

### Domain modeling

- `@dataclass(frozen=True)` for value objects (`EmbeddingResult`, `VectorRecord`, etc.)
- Configuration via dataclasses with `__post_init__` validation
- Each module defines a base exception with specific subclasses

---

## Exception handling

- Each module defines base + specific exceptions
- Adapters translate external exceptions into domain exceptions

---

## Testing

Tests live in `_test/` inside each module. Each module can be validated independently:

```bash
cd lib
pytest acai/<module>/_test       # single module
pytest                            # full suite
```

File naming: `test_<name>.py`. Mock all external SDKs — no real API calls.

---

## Examples

Examples live in `_example/` inside each module:
- Each adapter gets `<adapter>_example.py`
- Optional notebooks for exploration
- Use `.env` + `python-dotenv` for secrets
- Excluded from pytest discovery

---

## Coding standards

- Full type hints on all function signatures
- `from __future__ import annotations` for forward references
- No mutable defaults — use `None` with conditionals
- Docstrings for all ports, adapters, domain models, and public functions
- `dataclasses` for config and DTOs; `ABC` for ports; `Protocol` for lightweight interfaces
- Secrets exclusively from environment variables via `python-dotenv`

---

<!-- AUTHORS -->
## Authors

This module is maintained by [ACAI GmbH][acai-url].

<!-- LICENSE -->
## License

See [LICENSE][license-url] for full details.

<!-- COPYRIGHT -->
<br />
<br />
<p align="center">Copyright &copy; 2026 ACAI GmbH</p>

[acai-shield]: https://img.shields.io/badge/maintained_by-acai.gmbh-CB224B?style=flat
[acai-url]: https://acai.gmbh
[module-version-shield]: https://img.shields.io/badge/module_version-1.1.4-CB224B?style=flat
[terraform-tested-shield]: https://img.shields.io/badge/terraform-%3E%3D1.5.7_tested-844FBA?style=flat&logo=terraform&logoColor=white
[opentofu-tested-shield]: https://img.shields.io/badge/opentofu-%3E%3D1.6_tested-FFDA18?style=flat&logo=opentofu&logoColor=black
[aws-tested-shield]: https://img.shields.io/badge/AWS-%E2%9C%93_tested-FF9900?style=flat&logo=amazonaws&logoColor=white
[aws-esc-tested-shield]: https://img.shields.io/badge/AWS_ESC-%E2%9C%93_tested-003399?
[license-url]: ./LICENSE.md

