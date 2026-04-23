# acai.boto3_helper

Utility module providing AWS SDK (boto3) wrappers for common services.  
No hexagonal architecture — flat utility code with convenience classes.

---

## Components

```
acai/boto3_helper/
├── __init__.py          # Public API
├── session.py           # AwsSessionManager — cross-account/region session management
├── sts.py               # STS client wrapper (assume-role)
├── s3.py                # S3 operations
├── cloudwatch.py        # CloudWatch API wrapper
├── organizations.py     # AWS Organizations API
└── sns.py               # SNS notifications
```

---

## AwsSessionManager

Manages boto3 sessions with cross-account role assumption, regional client caching, and adaptive retries.

```python
from acai.logging import create_logger
from acai.boto3_helper.session import AwsSessionManager

logger = create_logger()

manager = AwsSessionManager(
    logger=logger,
    remote_role_arn="arn:aws:iam::123456789012:role/CrossAccountRole",
)

# Get a cached client for any service/region
s3_client = manager.get_client("s3", "eu-central-1")
cw_client = manager.get_client("cloudwatch", "us-east-1")
```

### Key features

- **Session caching** — STS sessions and clients are created once and reused.
- **Cross-account access** — Automatic role assumption via STS.
- **Adaptive retries** — Default retry config with max 10 attempts and adaptive mode.
- **Regional support** — Manage clients across any AWS region.

### Methods

| Method | Description |
|--------|-------------|
| `get_sts_session(region)` | Get or create an STS session for a region. |
| `get_client(service, region)` | Get or create a cached boto3 client. |
| `get_member_client(service, region)` | Same as `get_client` with error suppression. |

---

## Service wrappers

| Module | Description |
|--------|-------------|
| `sts.py` | STS client — `assume_role()` for cross-account sessions. |
| `s3.py` | S3 operations (upload, download, list). |
| `cloudwatch.py` | CloudWatch metrics and logs. |
| `organizations.py` | AWS Organizations account listing. |
| `sns.py` | SNS topic publishing. |

All wrappers accept a `Loggable` logger instance for operational logging.
