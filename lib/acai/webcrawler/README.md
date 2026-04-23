# acai.webcrawler

A web-scraping module built on **hexagonal architecture** principles.  
Swap between Selenium, httpx, or any future adapter with a single flag — your application code never changes.

---

## Architecture

```
acai/webcrawler/
├── __init__.py                        # Public API + create_scraper() factory
├── website_scraper.py                 # Backward-compatibility shim
├── ports/                             # ── PORT (driven / secondary) ──
│   └── scraper_port.py                # WebScraperPort ABC (get_page, extract_content, cleanup)
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── scraper_config.py              # WebConfig dataclass
│   └── exceptions.py                  # ScraperException → WebOperationError, ConfigurationError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       └── selenium_scraper.py        # Selenium Chrome WebDriver adapter
├── _example/
│   └── local_example.py              # Local development demo (requires Chrome)
└── _test/
    └── test_selenium_scraper.py       # Unit tests (mocked — no browser required)
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/scraper_port.py` | Abstract contract (`WebScraperPort` ABC). All domain code depends *only* on this. Provides context-manager support (`__enter__` / `__exit__`). |
| **Exceptions** | `domain/exceptions.py` | `ScraperException` → `WebOperationError`, `ConfigurationError`. |
| **Config VO** | `domain/scraper_config.py` | `WebConfig` dataclass shared by all adapters. Validated in `__post_init__`. |
| **Selenium adapter** | `adapters/outbound/selenium_scraper.py` | Driven adapter for Chrome WebDriver. Headless mode, retries, content-aware waiting. |
| **Factory** | `__init__.py` → `create_scraper()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `WebScraperPort`; it never imports an adapter directly.

---

## Quick start

### Local development

```python
from acai.logging import create_logger
from acai.webcrawler import create_scraper

logger  = create_logger()
scraper = create_scraper(logger=logger)

page = scraper.get_page("https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de")
result = scraper.extract_content(page)
print(result["length"])

scraper.cleanup()
```

### With configuration

```python
from acai.webcrawler import create_scraper, WebConfig

config = WebConfig(
    headless=True,
    default_timeout=5,
    page_load_delay=1.0,
    base_url="https://www.fedlex.admin.ch",
    retry_attempts=3,
    retry_delay=1.0,
)

scraper = create_scraper(logger=logger, config=config)
```

### Context manager (recommended)

```python
with create_scraper(logger, config) as scraper:
    page = scraper.get_page("/eli/cc/24/233_245_233/de")
    result = scraper.extract_content(page)
# WebDriver is automatically cleaned up here
```

---

## API reference

### Factory

```python
create_scraper(
    logger: Loggable,
    config: WebConfig | None = None,
) -> WebScraperPort
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `logger` | `Loggable` | *(required)* | A `Loggable` instance for operational logging. |
| `config` | `WebConfig \| None` | `None` | Configuration. When `None`, sensible defaults are used. |

### WebScraperPort (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_page` | `(url: str) -> Optional[BeautifulSoup]` | Fetch and parse a web page. Relative URLs are prepended with `base_url`. Returns `None` if the page has no meaningful content after all retries. |
| `extract_content` | `(page: BeautifulSoup) -> Dict[str, Any]` | Extract relevant content from a parsed page. Returns `{"content", "length", "error"}`. Tries `#content`, `.content`, `main`, then falls back to `<body>`. |
| `cleanup` | `() -> None` | Release held resources (browser instances, connections). |
| `__enter__` | `() -> WebScraperPort` | Context-manager entry. |
| `__exit__` | `(…) -> None` | Calls `cleanup()` on context-manager exit. |

### WebConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `headless` | `bool` | `False` | Run Chrome in headless mode (no visible window). |
| `default_timeout` | `int` | `3` | Seconds to wait for elements before timing out. Must be > 0. |
| `page_load_delay` | `float` | `1.0` | Seconds to wait after page load when no content element is found. Must be ≥ 0. |
| `base_url` | `str` | `"https://www.fedlex.admin.ch"` | Prepended to relative URLs passed to `get_page()`. |
| `retry_attempts` | `int` | `3` | Number of attempts per `get_page()` call. |
| `retry_delay` | `float` | `1.0` | Seconds to wait between retries. |
| `driver_path` | `str \| None` | `None` | Explicit path to ChromeDriver binary. Must exist on disk if set. |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `ScraperException` | `Exception` | Base class for all scraper errors. |
| `WebOperationError` | `ScraperException` | Navigation failures, driver init errors, exhausted retries. |
| `ConfigurationError` | `ScraperException` | Invalid config values (negative timeout, missing driver path). |

---

## SeleniumScraper features

### Headless mode

Set `headless=True` in `WebConfig` to run Chrome without a visible window — ideal for CI/CD and server environments.

### Automatic retries

`get_page()` retries up to `retry_attempts` times with `retry_delay` between attempts. After all retries are exhausted, a `WebOperationError` is raised.

### Content-aware waiting

Before returning the page source, the adapter waits for common content selectors (`#content`, `.content`, `main`, `#main`, `.main-content`, `#main-content`). If none are found, it falls back to `page_load_delay`.

### Relative URL resolution

URLs that don't start with `http://` or `https://` are automatically prepended with `base_url`:

```python
scraper.get_page("/eli/cc/24/233_245_233/de")
# → navigates to https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de
```

### Content extraction

`extract_content()` returns a dict with three keys:

```python
{
    "content": <Tag>,   # BeautifulSoup Tag (or None)
    "length":  1234,    # Character count of the matched content
    "error":   None,    # Error message string (or None on success)
}
```

---

## Testing

Run the unit tests (no browser required — Selenium is fully mocked):

```bash
cd hl2/shared/python
python -m pytest acai/webcrawler/_test/ -v
```

| Class | Tests | What it verifies |
|-------|-------|------------------|
| `TestWebConfig` | 6 | Defaults, timeout/delay/driver_path validation |
| `TestExtractContent` | 4 | `<main>`, `#content`, `<body>` fallback, missing content |
| `TestGetPage` | 4 | Success path, relative URL prepending, retry logic, exhausted retries |
| `TestCleanup` | 3 | Driver quit, idempotency, context-manager lifecycle |
| `TestExceptions` | 2 | Exception hierarchy (`WebOperationError`, `ConfigurationError`) |
| `TestFactory` | 3 | `create_scraper()` return type, config forwarding, init failure |

---

## Extending — implementing a new adapter

1. Create `acai/webcrawler/adapters/outbound/my_adapter.py`.
2. Subclass `WebScraperPort` and implement all three methods (`get_page`, `extract_content`, `cleanup`).
3. Wire it into `create_scraper()` in `__init__.py` behind a new flag.

```python
class MyAdapter(WebScraperPort):
    def get_page(self, url: str) -> Optional[BeautifulSoup]: ...
    def extract_content(self, page: BeautifulSoup) -> Dict[str, Any]: ...
    def cleanup(self) -> None: ...
```
