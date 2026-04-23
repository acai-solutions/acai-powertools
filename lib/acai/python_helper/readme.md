# acai.python_helper

Utility module providing general-purpose helpers for hashing, datetime conversion, and JSON operations.  
No hexagonal architecture — flat utility code.

---

## Components

```
acai/python_helper/
├── __init__.py            # Public API: get_16_bytes_hash, datetime_to_yyyymmdd_hhmmss, aws_timestamp_to_yyyymmdd_hhmmss
├── utils.py               # BLAKE2b hashing
├── datetime_utils.py      # Datetime formatting helpers
├── json_helper.py         # JSON utilities
└── _test/
    └── (unit tests)
```

---

## Hashing

```python
from acai.python_helper import get_16_bytes_hash

hash_hex = get_16_bytes_hash("Swiss civil code article 1")
# Returns a 32-character hex string (BLAKE2b, 16-byte digest)
```

Useful for generating deterministic, compact identifiers from text content.

---

## Datetime utilities

```python
from acai.python_helper import datetime_to_yyyymmdd_hhmmss, aws_timestamp_to_yyyymmdd_hhmmss
from datetime import datetime

# Format a Python datetime
formatted = datetime_to_yyyymmdd_hhmmss(datetime.now())
# "20260327_143022"

# Format an AWS timestamp
formatted = aws_timestamp_to_yyyymmdd_hhmmss(aws_timestamp)
```

---

## Public API

| Function | Module | Description |
|----------|--------|-------------|
| `get_16_bytes_hash(input_string)` | `utils.py` | BLAKE2b 16-byte hex hash of the input string. |
| `datetime_to_yyyymmdd_hhmmss(dt)` | `datetime_utils.py` | Format a `datetime` as `YYYYMMDD_HHMMSS`. |
| `aws_timestamp_to_yyyymmdd_hhmmss(ts)` | `datetime_utils.py` | Convert an AWS timestamp to `YYYYMMDD_HHMMSS`. |

---

## Testing

```bash
cd shared/python
pytest acai/python_helper/_test/ -v
```
