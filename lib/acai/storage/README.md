# acai.storage

A file-storage module built on **hexagonal architecture** principles.  
Swap between local filesystem and AWS S3 with a single flag — your application code never changes.

---

## Architecture

```
acai/storage/
├── __init__.py                        # Public API + create_storage() factory
├── ports/                             # ── PORT (driven / secondary) ──
│   └── storage_port.py               # StorageReader, StorageWriter, StoragePort ABCs
├── domain/                            # ── INSIDE THE HEXAGON ──
│   ├── storage_config.py             # StorageConfig dataclass
│   └── exceptions.py                 # StorageError → FileOperationError, ValidationError
├── adapters/                          # ── OUTSIDE THE HEXAGON ──
│   └── outbound/
│       ├── local_file_storage.py     # Local filesystem (atomic writes, backups)
│       └── s3_storage.py             # AWS S3 (stub — not yet implemented)
└── examples/
    ├── __init__.py
    └── test_storage.ipynb            # Interactive test notebook
```

### Hexagonal mapping

| Concept | File(s) | Purpose |
|---------|---------|---------|
| **Port** | `ports/storage_port.py` | Abstract contracts (`StorageReader`, `StorageWriter`, `StoragePort`). All domain code depends *only* on these. |
| **Exceptions** | `domain/exceptions.py` | `StorageError` → `FileOperationError`, `ValidationError`. |
| **Config VO** | `domain/storage_config.py` | `StorageConfig` dataclass shared by all adapters. |
| **Local adapter** | `adapters/outbound/local_file_storage.py` | Driven adapter for local / CLI workloads. Provides atomic writes, backups, extension validation, and JSON (de)serialisation with dataclass support. |
| **S3 adapter** | `adapters/outbound/s3_storage.py` | Driven adapter for AWS S3 (stub — raises `NotImplementedError`). |
| **Factory** | `__init__.py` → `create_storage()` | Composition root that wires adapter → caller. |

> **Dependency rule:** domain → port ← adapter.  
> Application code imports `StoragePort`; it never imports an adapter directly.

---

## Quick start

### Local development

```python
from acai.logging import create_logger
from acai.storage import create_storage

logger  = create_logger()
storage = create_storage(logger=logger)

# Save & read text
storage.save("output/report.txt", "Hello, world!")
text = storage.read("output/report.txt")

# Save & read JSON
storage.save_json("output/data.json", {"key": "value"})
data = storage.read_json("output/data.json")
```

### With configuration

```python
from acai.storage import create_storage, StorageConfig

config = StorageConfig(
    encoding="utf-8",
    backup_enabled=True,
    max_file_size=50 * 1024 * 1024,       # 50 MB
    allowed_extensions={"json", "txt", "csv"},
)

storage = create_storage(logger=logger, config=config)
```

### Future — S3 storage

```python
storage = create_storage(
    logger=logger,
    use_s3=True,
    bucket="my-bucket",
    prefix="data/v1/",
)
```

> The S3 adapter is currently a stub. All methods raise `NotImplementedError`.

---

## API reference

### Factory

```python
create_storage(
    logger: LoggerPort,
    config: StorageConfig | None = None,
    *,
    use_s3: bool = False,
    bucket: str = "",
    prefix: str = "",
) -> StoragePort
```

### StoragePort (port contract)

| Method | Signature | Description |
|--------|-----------|-------------|
| `read` | `(path, *, encoding="utf-8") -> str` | Read raw text. Returns `""` if the path does not exist. |
| `read_json` | `(path, data_type=None) -> Any` | Read & deserialise JSON. Returns `{}` if the path does not exist. Pass a `data_type` to hydrate dataclasses. |
| `save` | `(path, content, *, encoding="utf-8") -> None` | Persist raw text content (atomic write). |
| `save_json` | `(path, data, *, indent=2) -> None` | Serialise to JSON and persist. Supports dataclasses via `dataclasses.asdict`. |
| `exists` | `(path) -> bool` | Check whether a file exists. |

### StorageConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `encoding` | `str` | `"utf-8"` | Default file encoding. |
| `backup_enabled` | `bool` | `True` | Create `.bak` backups before overwriting. |
| `max_file_size` | `int` | `104857600` (100 MB) | Maximum file size in bytes for atomic writes. |
| `temp_dir` | `Path \| None` | `None` (auto) | Directory for `.tmp` / `.bak` files. Defaults to `<system-tmp>/acai_storage`. |
| `allowed_extensions` | `set[str] \| None` | `None` (any) | Restrict writes to these file extensions (without dot). |

### Exceptions

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `StorageError` | `Exception` | Base class for all storage errors. |
| `FileOperationError` | `StorageError` | I/O failures, size-limit violations, serialisation errors. |
| `ValidationError` | `StorageError` | Invalid paths, disallowed extensions, bad config values. |

---

## LocalFileStorage features

### Atomic writes

Writes go to a temporary file first. Only after the write succeeds is the temp file atomically moved to the target path. If the process crashes mid-write, the original file is untouched.

### Backup & restore

When `backup_enabled=True` (the default), the existing file is copied to a `.bak` file before overwriting. If the write fails, the backup is automatically restored.

### Extension validation

Set `allowed_extensions` in `StorageConfig` to restrict writes to specific file types:

```python
config = StorageConfig(allowed_extensions={"json", "txt"})
storage = create_storage(logger=logger, config=config)
storage.save("data.csv", "a,b,c")  # raises ValidationError
```

### Size limits

Files exceeding `max_file_size` are rejected after writing (the temp file is cleaned up and no data is persisted).

### JSON with dataclasses

`save_json` automatically converts dataclass instances via `dataclasses.asdict`. `read_json` can hydrate them back:

```python
from dataclasses import dataclass

@dataclass
class User:
    name: str
    age: int

storage.save_json("user.json", User("Alice", 30))
user = storage.read_json("user.json", data_type=User)
```

### Context manager

Use as a context manager to automatically clean up temp/backup files on exit:

```python
with LocalFileStorage(logger=logger) as storage:
    storage.save("data.txt", "content")
# .tmp and .bak files are cleaned up
```

---

## Testing

Open `examples/test_storage.ipynb` and run all cells. The notebook covers:

| # | Test | What it verifies |
|---|------|------------------|
| 0 | Setup & imports | Module wiring, factory |
| 1 | Factory `create_storage()` | Returns `LocalFileStorage` with default config |
| 2 | Text save & read | Round-trip text persistence |
| 3 | JSON save & read | Plain dicts and `@dataclass` instances |
| 4 | Missing files | `read()` → `""`, `read_json()` → `{}` |
| 5 | Nested directories | Parent dirs auto-created |
| 6 | Extension validation | `ValidationError` on disallowed extensions |
| 7 | File size limit | `FileOperationError` on oversized writes |
| 8 | Context manager | `__enter__` / `__exit__` lifecycle |
| 9 | S3 stub | All methods raise `NotImplementedError` |

A **Cleanup** cell removes the temp directory and a **Summary** cell prints pass/fail counts.

---

## Extending — implementing a new adapter

1. Create `acai/storage/adapters/outbound/my_adapter.py`.
2. Subclass `StoragePort` and implement all five methods (`read`, `read_json`, `save`, `save_json`, `exists`).
3. Wire it into `create_storage()` in `__init__.py` behind a new flag.

```python
class MyAdapter(StoragePort):
    def read(self, path, *, encoding="utf-8") -> str: ...
    def read_json(self, path, data_type=None): ...
    def save(self, path, content, *, encoding="utf-8") -> None: ...
    def save_json(self, path, data, *, indent=2) -> None: ...
    def exists(self, path) -> bool: ...
```
