# acai.logging

A structured logging module built on **hexagonal architecture** principles.  
Swap between console output, file-based logging, and AWS CloudWatch with a single flag — your application code never changes.

---

## Architecture

```
acai/logging/
├── __init__.py                        # Public API + create_logger() factory
├── log_level.py                       # LogLevel enum (DEBUG → CRITICAL)
├── ports/                             # ── PORT (driven / secondary) ──
│   └── logger_port.py                 # LoggerPort ABC + Loggable Protocol
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── logger_config.py               # LoggerConfig dataclass
│   └── logger.py                      # Logger service (context stack, Lambda decorator)
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       ├── console_logger.py          # stdout (text / JSON)
│       ├── file_logger.py             # Persists via StorageWriter (acai.storage)
│       ├── cloudwatch_logger.py       # AWS Lambda PowerTools → CloudWatch
│       ├── multi_logger.py            # Composite fan-out to multiple adapters
│       ├── elasticsearch_logger.py    # Elasticsearch / OpenSearch
│       ├── aws_opensearch_logger.py   # AWS OpenSearch with SigV4
│       ├── logzio_logger.py           # Logz.io HTTP shipping
│       └── loki_logger.py             # Grafana Loki
├── _example/
│   ├── local_example.py               # Local development demo
│   ├── lambda_example.py              # AWS Lambda demo
│   ├── file_logger_example.py         # File logger with StorageWriter demo
│   └── demo_logging.ipynb             # Interactive test notebook
└── _test/
    └── test_file_logger.py            # Unit tests for FileLogger adapter
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/logger_port.py` | Abstract contract (`LoggerPort` ABC) + structural typing (`Loggable` Protocol). All domain code depends *only* on this. |
| **Domain service** | `domain/logger.py` | `Logger` — decorates any adapter with a context stack, noisy-logging suppression, flush support, and a Lambda decorator. Pure logic, **no I/O**. |
| **Config VO** | `domain/logger_config.py` | `LoggerConfig` dataclass shared by all adapters. |
| **Console adapter** | `adapters/outbound/console_logger.py` | Driven adapter for local / CLI workloads. Supports text and JSON format. |
| **File adapter** | `adapters/outbound/file_logger.py` | Driven adapter that persists log lines via an `acai.storage.StorageWriter`, keeping file I/O decoupled. Buffers lines and flushes on demand. |
| **CloudWatch adapter** | `adapters/outbound/cloudwatch_logger.py` | Driven adapter for AWS Lambda. Wraps *aws-lambda-powertools* `Logger`. |
| **Multi adapter** | `adapters/outbound/multi_logger.py` | Composite adapter that fans out to multiple `LoggerPort` adapters. Context management is done via the wrapping `Logger` domain service, not the adapter. |
| **Factory** | `__init__.py` → `create_logger()` | Composition root that wires adapter → domain → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `Logger` and `LoggerPort`; it never imports an adapter directly.

---

## Quick start

### Local development (console)

```python
from acai.logging import create_logger

logger = create_logger()            # ConsoleLogger, text format, INFO level
logger.info("Hello", user="alice")  # 2026-03-23 10:00:00 - INFO - Hello | user=alice
```

### Local development (JSON output)

```python
from pathlib import Path
from acai.logging import create_logger, LoggerConfig, LogLevel

config = LoggerConfig(
    service_name="law-bot",
    log_level=LogLevel.DEBUG,
    json_output=True,
)
logger = create_logger(config)
logger.info("Pipeline started", step="30_crawl_fedlex_xml")
# {"timestamp": "...", "level": "INFO", "logger": "law-bot", "message": "Pipeline started", "step": "30_crawl_fedlex_xml"}
```

### File logging via StorageWriter

```python
from acai.logging import create_local_logger, LoggerConfig, LogLevel
from acai.storage.adapters.outbound.local_file_storage import LocalFileStorage

storage = LocalFileStorage(base_dir=\"./logs\")
config = LoggerConfig(service_name=\"law-bot\", log_level=LogLevel.DEBUG, json_output=True)
logger = create_local_logger(config, storage=storage, log_path=\"app.log\")

logger.info("Persisted via StorageWriter")
logger.flush()  # writes buffered lines to storage
```

### AWS Lambda (CloudWatch)

```python
from acai.logging import create_lambda_logger, LoggerConfig, LogLevel

config = LoggerConfig(service_name="law-bot-lambda", log_level=LogLevel.INFO)
logger = create_lambda_logger(config)

@logger.inject_lambda_context(include_event=True, include_cold_start=True)
def handler(event, context):
    logger.info("Processing", record_count=len(event.get("records", [])))
    return {"statusCode": 200}
```

---

## API reference

### `create_logger(config=None) → Logger`

Factory function — creates a `Logger` backed by `ConsoleLogger`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `LoggerConfig \| None` | `None` | Configuration. When `None`, sensible defaults are used. |

### `create_lambda_logger(config=None) → Logger`

Factory for AWS Lambda — creates a `Logger` backed by `CloudWatchLogger`.

### `create_local_logger(config=None, *, storage, log_path) → Logger`

Factory for file-based logging — creates a `Logger` backed by `FileLogger`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `LoggerConfig \| None` | `None` | Configuration. |
| `storage` | `StorageWriter` | — | Storage adapter for writing log files. |
| `log_path` | `str` | — | File path for log output. |

### `LoggerConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `service_name` | `str` | `"app"` | Logger/service identifier |
| `log_level` | `LogLevel \| int \| str` | `LogLevel.INFO` | Minimum log level |
| `json_output` | `bool` | `False` | Emit JSON lines instead of text |

### `LoggerPort` (abstract base class)

Every adapter implements this interface:

```python
def set_level(level)    # change log level at runtime
def log(level, msg, **kw)
def debug(msg, **kw)
def info(msg, **kw)
def warning(msg, **kw)
def error(msg, **kw)
def critical(msg, **kw)
def exception(msg, **kw)
def flush()             # flush buffered output (no-op by default)
```

### `Loggable` (Protocol)

Structural interface satisfied by both `Logger` and `LoggerPort` adapters.  
Use as the type hint when a component needs to call log methods but should not care whether it receives a raw adapter or the domain `Logger` service.

### `Logger` (domain service)

Wraps any `LoggerPort` adapter and adds:

| Method | Description |
|--------|-------------|
| `push_context(dict)` | Add key-value pairs to every subsequent log call |
| `pop_context()` | Remove the most recently pushed context |
| `get_current_context()` | Return merged context from all stack layers |
| `clear_context()` | Remove all pushed contexts |
| `flush()` | Delegate to underlying adapter's `flush()` |
| `disable_noisy_logging()` | Silence boto3, botocore, urllib3, etc. |
| `inject_lambda_context(...)` | Decorator for Lambda handlers (see below) |

### `LoggerContext`

Context manager for automatic push/pop:

```python
with LoggerContext(logger, {"request_id": "abc"}):
    logger.info("scoped log")   # includes request_id
# automatically popped here — even on exceptions
```

### `inject_lambda_context` decorator

```python
@logger.inject_lambda_context(
    include_event=True,       # log the event payload (truncated to 1 kB)
    include_context=True,     # log function name, request ID, memory limit, …
    include_response=False,   # log the handler return value
    include_cold_start=True,  # tag first invocation with cold_start=True
    log_exceptions=True,      # auto-log unhandled exceptions with traceback
    extra_context={...},      # static keys added to every log line
)
def handler(event, context):
    ...
```

---

## Adapters

### `ConsoleLogger`

Uses Python's `logging` module. Supports:

- **Text format** — human-readable with `key=value` pairs appended
- **JSON format** — one JSON object per line (structured logging)

```python
from acai.logging.adapters.outbound.console_logger import ConsoleLogger
adapter = ConsoleLogger(logger_name="my-app", level=LogLevel.DEBUG, json_output=True)
```

### `FileLogger`

Persists log lines via an `acai.storage.StorageWriter` adapter, keeping file I/O fully decoupled. Buffers lines in memory and writes on `flush()`.

- Supports **text** and **JSON** format
- Works with any `StorageWriter` (local filesystem, S3, etc.)
- Call `flush()` to write buffered lines to storage

```python
from acai.logging.adapters.outbound.file_logger import FileLogger
from acai.storage.adapters.outbound.local_file_storage import LocalFileStorage

storage = LocalFileStorage(base_dir="./logs")
adapter = FileLogger(storage=storage, log_path="app.log", level=LogLevel.DEBUG, json_output=True)
adapter.log(LogLevel.INFO, "Hello from FileLogger")
adapter.flush()
```

### `CloudWatchLogger`

Wraps `aws_lambda_powertools.Logger`. Requires the `aws-lambda-powertools` package.

```python
from acai.logging.adapters.outbound.cloudwatch_logger import CloudWatchLogger
adapter = CloudWatchLogger(service="my-lambda", level=LogLevel.INFO)
```

Reads `LOG_LEVEL` from environment when no explicit level is provided.

---

## Testing

Run the unit tests:

```bash
python -m pytest _test/
```

Or open the interactive notebook:

```
_example/demo_logging.ipynb
```

The notebook tests all 10 areas:

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | Console text | All five log levels produce output |
| 2 | Console JSON | Output is valid JSON with correct fields |
| 3 | File logger | Log lines are buffered, flushed, and persisted via StorageWriter |
| 4 | Context stack | `push_context` / `pop_context` merge and remove keys |
| 5 | LoggerContext | `with` block auto-pops, even on exceptions |
| 6 | Dynamic level | `set_level(WARNING)` suppresses DEBUG/INFO |
| 7 | CloudWatch (mocked) | Adapter delegates to `aws_lambda_powertools.Logger` |
| 8 | Lambda decorator | Injects request ID, cold-start flag, function name |
| 9 | Factory | `create_logger()` accepts default and custom config |
| 10 | Error resilience | Logger prints fallback instead of crashing |

---

## Adding a new adapter

1. Create `adapters/outbound/my_adapter.py` implementing `LoggerPort`
2. Implement `set_level()` and `log()` — the five convenience methods are inherited
3. (Optional) Add a branch in `create_logger()` or inject the adapter directly:

```python
from acai.logging.domain import Logger
from my_package import MyAdapter

logger = Logger(MyAdapter(...))
logger.info("works with any adapter")
```

---

## Dependencies

| Package | Required for | Required? |
|---------|-------------|-----------|
| Python ≥ 3.12 | `X \| None` union syntax | Yes |
| `aws-lambda-powertools` | `CloudWatchLogger` adapter | Only for Lambda |
