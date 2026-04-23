# acai.xml_parser

An XML parsing module built on **hexagonal architecture** principles.  
Parses Swiss AKN (Akoma Ntoso) legal documents into structured domain models.

---

## Architecture

```
acai/xml_parser/
├── __init__.py                        # Public API + create_xml_parser() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── xml_parser_port.py            # XmlParserPort ABC
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── xml_config.py                 # XmlParserConfig dataclass
│   ├── xml_models.py                 # ParsedArticle, LawMetadata, ParsedLawDocument
│   └── exceptions.py                 # XmlParserError → XmlParseError, ConfigurationError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       └── lxml_parser.py            # lxml-based adapter for AKN documents
├── _example/
│   └── (usage demos)
└── _test/
    └── (unit tests)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/xml_parser_port.py` | Abstract contract (`XmlParserPort` ABC) with context-manager support. Application code depends *only* on this. |
| **Config VO** | `domain/xml_config.py` | `XmlParserConfig` — AKN namespace URI, XML namespace, language. |
| **Domain models** | `domain/xml_models.py` | `ParsedArticle`, `LawMetadata`, `ParsedLawDocument`. |
| **Exceptions** | `domain/exceptions.py` | `XmlParserError` → `XmlParseError`, `ConfigurationError`. |
| **lxml adapter** | `adapters/outbound/lxml_parser.py` | Driven adapter using lxml to parse AKN XML. |
| **Factory** | `__init__.py` → `create_xml_parser()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `XmlParserPort` and domain models; it never imports an adapter directly.

---

## Quick start

```python
from acai.logging import create_logger
from acai.xml_parser import create_xml_parser

logger = create_logger()
parser = create_xml_parser(logger)

doc = parser.parse("path/to/fedlex-document.xml")

print(doc.metadata.law_name)
print(doc.metadata.law_number)
print(doc.metadata.short_form)

for article in doc.articles:
    print(article.article, article.headings, len(article.paragraphs))
```

### With custom configuration

```python
from acai.xml_parser import create_xml_parser, XmlParserConfig

config = XmlParserConfig(
    akn_namespace_uri="http://docs.oasis-open.org/legaldocml/ns/akn/3.0",
    language="de",
)
parser = create_xml_parser(logger, config=config)
```

### Context manager

```python
with create_xml_parser(logger) as parser:
    doc = parser.parse("path/to/document.xml")
```

---

## API reference

### `create_xml_parser(logger, config=None) → XmlParserPort`

Factory function (composition root).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `config` | `XmlParserConfig \| None` | `None` | Configuration. Defaults target Swiss AKN documents. |

### `XmlParserPort` (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `parse` | `(xml_path: str \| Path) -> ParsedLawDocument` | Parse an XML file into a structured law document. |
| `__enter__` | `() -> XmlParserPort` | Context-manager entry. |
| `__exit__` | `(…) -> None` | Context-manager exit. |

### `XmlParserConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `akn_namespace_uri` | `str` | `"http://docs.oasis-open.org/legaldocml/ns/akn/3.0"` | AKN namespace URI. |
| `xml_namespace_uri` | `str` | `"http://www.w3.org/XML/1998/namespace"` | XML namespace URI. |
| `language` | `str` | `"de"` | Document language. |

### Domain models

#### `ParsedLawDocument`

| Field | Type | Description |
|-------|------|-------------|
| `metadata` | `LawMetadata` | Law-level metadata. |
| `articles` | `list[ParsedArticle]` | Extracted articles. |

#### `LawMetadata`

| Field | Type | Description |
|-------|------|-------------|
| `law_number` | `str \| None` | SR number (e.g. `"210"`). |
| `law_name` | `str \| None` | Full law title. |
| `short_form` | `str \| None` | Abbreviated name (e.g. `"ZGB"`). |

#### `ParsedArticle`

| Field | Type | Description |
|-------|------|-------------|
| `article` | `str` | Article identifier (e.g. `"Art. 1"`). |
| `headings` | `list[str]` | Section headings above this article. |
| `level` | `int` | Nesting level in the document structure. |
| `paragraphs` | `list[str]` | Paragraph texts in the article. |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `XmlParserError` | `Exception` | Base class for all XML parser errors. |
| `XmlParseError` | `XmlParserError` | File cannot be parsed (malformed XML, missing elements). |
| `ConfigurationError` | `XmlParserError` | Invalid config values. |

---

## Testing

```bash
cd shared/python
pytest acai/xml_parser/_test/ -v
```
