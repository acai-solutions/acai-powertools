from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any, List, Optional, Type, TypeVar, Union

import boto3
import botocore
from acai.logging import Loggable
from acai.storage.domain import FileOperationError, ValidationError
from acai.storage.ports import StoragePort

T = TypeVar("T")


class S3Storage(StoragePort):
    """Outbound adapter — persists data in an AWS S3 bucket.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``StoragePort``.  Uses a raw boto3 S3
    *client* (not resource) so it stays lightweight and testable.
    """

    VERSION: str = "1.0.6"  # inject_version

    def __init__(
        self,
        logger: Loggable,
        bucket: str,
        prefix: str = "",
        boto3_session: Optional[boto3.Session] = None,
    ) -> None:
        self._logger = logger
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        session = boto3_session or boto3
        self._client: Any = session.client("s3")
        self._logger.info(f"S3Storage initialised for s3://{bucket}/{self._prefix}")

    # ── StorageReader ─────────────────────────────────────────────────

    def read(self, path: Union[str, Path], *, encoding: str = "utf-8") -> str:
        key = self._resolve_key(path)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            body: bytes = response["Body"].read()
            self._logger.debug(f"Read {len(body)} bytes from s3://{self._bucket}/{key}")
            return body.decode(encoding)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                self._logger.info(f"Key does not exist, returning empty string: {key}")
                return ""
            raise FileOperationError(
                f"Failed to read s3://{self._bucket}/{key}: {e}"
            ) from e

    def read_json(
        self,
        path: Union[str, Path],
        data_type: Optional[Type[T]] = None,
    ) -> Union[Any, T, List[T]]:
        raw = self.read(path)
        if not raw:
            return {}

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise FileOperationError(f"JSON decode error for {path}: {e}") from e

        if data_type is None:
            return parsed
        try:
            if isinstance(parsed, list):
                return [data_type(**item) for item in parsed]
            if isinstance(parsed, dict):
                return data_type(**parsed)
        except TypeError as e:
            raise ValidationError(f"Deserialisation error for {path}: {e}") from e
        raise ValidationError(
            "JSON content must be a dict or list for dataclass deserialisation"
        )

    def exists(self, path: Union[str, Path]) -> bool:
        key = self._resolve_key(path)
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except botocore.exceptions.ClientError:
            return False

    def list_dir(self, path: Union[str, Path], *, pattern: str = "*") -> List[str]:
        prefix = self._resolve_key(path).rstrip("/") + "/"
        result: List[str] = []
        paginator = self._client.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(
                Bucket=self._bucket, Prefix=prefix, Delimiter="/"
            ):
                for obj in page.get("Contents", []):
                    name = PurePosixPath(obj["Key"]).name
                    if name and fnmatch(name, pattern):
                        result.append(name)
        except botocore.exceptions.ClientError as e:
            self._logger.error(f"Error listing s3://{self._bucket}/{prefix}: {e}")
            return []
        self._logger.debug(
            f"Listed {len(result)} objects in s3://{self._bucket}/{prefix}"
        )
        return result

    # ── StorageWriter ─────────────────────────────────────────────────

    def save(
        self,
        path: Union[str, Path],
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> None:
        if not isinstance(content, str):
            raise ValidationError("content must be a string")
        key = self._resolve_key(path)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=content.encode(encoding),
            )
            self._logger.info(f"Saved to s3://{self._bucket}/{key}")
        except botocore.exceptions.ClientError as e:
            raise FileOperationError(
                f"Failed to save s3://{self._bucket}/{key}: {e}"
            ) from e

    def save_json(
        self,
        path: Union[str, Path],
        data: Any,
        *,
        indent: int = 2,
    ) -> None:
        def _default(obj: Any) -> Any:
            if is_dataclass(obj) and not isinstance(obj, type):
                return asdict(obj)
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serialisable"
            )

        try:
            json_text = json.dumps(
                data, ensure_ascii=False, indent=indent, default=_default
            )
        except TypeError as e:
            raise FileOperationError(f"Serialisation error: {e}") from e

        self.save(path, json_text)

    # ── private helpers ───────────────────────────────────────────────

    def _resolve_key(self, path: Union[str, Path]) -> str:
        """Combine prefix and path into a full S3 key."""
        relative = str(path).replace("\\", "/").lstrip("/")
        if self._prefix:
            return f"{self._prefix}/{relative}"
        return relative
