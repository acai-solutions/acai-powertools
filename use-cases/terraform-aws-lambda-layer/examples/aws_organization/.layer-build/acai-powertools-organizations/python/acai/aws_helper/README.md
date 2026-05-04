# acai.aws_helper

Utility module providing AWS SDK (boto3) wrappers for common services.
No hexagonal architecture — flat utility code with convenience classes.

---

## Components

```
acai/aws_helper/
├── __init__.py          # Public API
├── boto3_client.py      # Boto3ClientFactory — generic client/resource factory
├── session.py           # AwsSessionManager — cross-account/region session manager
├── sts.py               # StsClient — assume-role wrapper
├── s3.py                # S3ObjectManager — cached object access
├── cloudwatch.py        # CloudWatchClient — log-event writer
├── organizations.py     # OrganizationsHelper — accounts, OUs, tags
├── ou_path_resolver.py  # OuPathResolver — resolve OU path strings to IDs
└── sns.py               # SnsClient — JSON message publisher
```

---

## Boto3ClientFactory

Generic factory for boto3 clients/resources with sensible retry defaults
(`max_attempts=5`, `mode=adaptive`, `max_pool_connections=50`).

```python
from acai.logging import create_logger
from acai.aws_helper.boto3_client import Boto3ClientFactory

logger = create_logger()
factory = Boto3ClientFactory(logger, region="eu-central-1")

s3 = factory.get_client("s3")
ddb = factory.get_resource("dynamodb")
```

Module-level convenience functions `get_aws_client()` and `get_boto3_resource()`
are provided for backward compatibility.

---

## AwsSessionManager

Manages boto3 sessions with cross-account role assumption, regional client
caching, and adaptive retries (`max_attempts=10`, `mode=adaptive`).

```python
from acai.logging import create_logger
from acai.aws_helper.session import AwsSessionManager

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
| `get_member_client(service, region)` | Same as `get_client` with error suppression and one-shot warning. |

---

## OuPathResolver

Standalone helper (no acai package dependencies) that resolves AWS Organizations
OU path strings (e.g. `/root/Workloads/Prod/`) to OU IDs. Supports wildcard
segments (`*`) and validates that the current session is in the expected org.

```python
import boto3
import logging
from acai.aws_helper.ou_path_resolver import OuPathResolver

resolver = OuPathResolver(logging.getLogger(), boto3.client("organizations"))

resolver.validate_org(expected_org_id="o-12345", expected_root_ou_id="r-ab12")

resolved = resolver.resolve_ou_paths([
    "/root/Core/Security/",
    "/Workloads/Prod/",
    "/root/Workloads/*",   # wildcard expansion
])
```

`resolve_ou_paths_with_assignments()` carries arbitrary payloads alongside
each resolved OU and merges payloads when multiple input paths resolve to the
same OU. `resolve_ou_tree()` walks the entire tree and returns every path
with its OU ID and depth level.

---

## OrganizationsHelper

Extends `OuPathResolver` with cached account/OU lookups.

```python
from acai.logging import create_logger
from acai.aws_helper.organizations import OrganizationsHelper

helper = OrganizationsHelper(create_logger())

accounts = helper.list_accounts(only_active=True)
ou_id = helper.get_ou_id("123456789012")
context = helper.get_member_account_context("123456789012")
# → accountId, accountName, accountStatus, accountTags,
#   ouId, ouIdWithPath, ouName, ouNameWithPath, ouTags
```

Includes `list_child_ous()`, `list_accounts_for_parent()`,
`list_all_accounts_by_list()`, `list_all_accounts_by_parent()`, `get_tags()`,
plus inherited `validate_org()`, `resolve_ou_paths()`, `resolve_ou_tree()`.

---

## Service wrappers

| Class / module | Description |
|---------------|-------------|
| `StsClient` (`sts.py`) | `assume_role()` returning a boto3 `Session` with temporary credentials. CloudTrail-friendly default `RoleSessionName` (`acai-<host>-<epoch>`). |
| `S3ObjectManager` (`s3.py`) | Object retrieval with in-memory `last_modified`-aware cache. |
| `CloudWatchClient` (`cloudwatch.py`) | Single-event `put_log_events` writer (no sequence-token handling — deprecated since 2023). |
| `SnsClient` (`sns.py`) | JSON publish to SNS topic with optional message attributes. Module-level `send_to_sns()` retained for backward compatibility. |

All wrappers accept a `Loggable` logger instance for operational logging.
