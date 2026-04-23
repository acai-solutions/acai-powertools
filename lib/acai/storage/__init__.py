"""
acai.storage — Hexagonal storage module
========================================

Public surface
--------------
- ``StoragePort``, ``StorageReader``, ``StorageWriter`` — port contracts
- ``StorageConfig``              — shared configuration value object
- ``StorageError``, ``FileOperationError``, ``ValidationError`` — exceptions
- ``create_storage()``           — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.storage.adapters.LocalFileStorage``
- ``acai.storage.adapters.S3Storage``  (stub — not yet implemented)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.storage.domain import (
    FileOperationError,
    StorageConfig,
    StorageError,
    ValidationError,
)
from acai.storage.ports import StoragePort, StorageReader, StorageWriter

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_storage(
    logger: Loggable,
    config: StorageConfig | None = None,
    *,
    use_s3: bool = False,
    bucket: str = "",
    prefix: str = "",
) -> StoragePort:
    """Factory that builds a ready-to-use ``StoragePort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter for operational logging.
    config:
        Optional configuration.  Defaults are sensible for local development.
    use_s3:
        When ``True``, the ``S3Storage`` adapter is used (requires boto3).
        Otherwise ``LocalFileStorage`` is used.
    bucket:
        S3 bucket name (only used when *use_s3* is ``True``).
    prefix:
        S3 key prefix (only used when *use_s3* is ``True``).
    """
    if config is None:
        config = StorageConfig()

    if use_s3:
        from acai.storage.adapters.outbound.s3_storage import S3Storage

        return S3Storage(logger=logger, bucket=bucket, prefix=prefix)
    else:
        from acai.storage.adapters.outbound.local_file_storage import LocalFileStorage

        return LocalFileStorage(logger=logger, config=config)


__all__ = [
    "StoragePort",
    "StorageReader",
    "StorageWriter",
    "StorageConfig",
    "StorageError",
    "FileOperationError",
    "ValidationError",
    "create_storage",
]
