from __future__ import annotations

from datetime import datetime
from typing import Any

import boto3
import botocore
from acai.logging import Loggable


class S3ObjectManager:
    def __init__(self, logger: Loggable, boto3_resource: Any) -> None:
        self.logger = logger
        self.boto3_resource = boto3_resource
        self.cache: dict[str, bytes] = {}
        self.last_modified_cache: dict[str, datetime] = {}
        self.logger.info("S3ObjectManager initialized")

    def get_cached_object(self, bucket_name: str, full_key: str) -> bytes | None:
        try:
            self.logger.debug(
                f"Attempting to get object: {full_key} from bucket: {bucket_name}"
            )

            cached_content = self.cache.get(full_key)
            cached_last_modified = self.last_modified_cache.get(full_key)

            if cached_content is not None and cached_last_modified is not None:
                summary = self.boto3_resource.ObjectSummary(bucket_name, full_key)
                if summary.last_modified <= cached_last_modified:
                    self.logger.debug(f"Using cached content for {full_key}")
                    return cached_content

            self.logger.info(f"Fetching updated content from S3 bucket for {full_key}")
            s3_object = self.boto3_resource.Object(bucket_name, full_key)
            response: dict[str, Any] = s3_object.get()
            file_content: bytes = response["Body"].read()

            self.cache[full_key] = file_content
            self.last_modified_cache[full_key] = s3_object.last_modified

            return file_content
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self.logger.warning(
                    f"Object {full_key} does not exist in bucket {bucket_name}"
                )
                return None
            self.logger.error(f"Error getting object {full_key}: {e}")
            raise

    # ¦ get_local_cache
    def get_local_cache(self) -> dict[str, Any]:
        return self.cache

    def get_objects_from_bucket(
        self, bucket_name: str, prefix: str
    ) -> list[dict[str, bytes | str]]:
        self.logger.info(
            f"Getting objects from bucket {bucket_name} with prefix {prefix}, {len(self.cache)} items in cache"
        )
        result: list[dict[str, bytes | str]] = []
        my_bucket: boto3.resources.factory.s3.Bucket = self.boto3_resource.Bucket(
            bucket_name
        )
        for file in my_bucket.objects.filter(Prefix=prefix).all():
            if self.get_full_path(file.key) == prefix[:-1]:
                body: bytes | None = self.get_cached_object(bucket_name, file.key)
                if body is not None:
                    result.append({"objectKey": file.key, "content": body})
        self.logger.debug(f"Retrieved {len(result)} objects from bucket {bucket_name}")
        return result

    def get_object_from_bucket(self, bucket_name: str, full_key: str) -> str | None:
        self.logger.debug(f"Getting object {full_key} from bucket {bucket_name}")
        try:
            cached_content: bytes | None = self.get_cached_object(bucket_name, full_key)
            if cached_content is not None:
                return cached_content.decode("utf-8")
            else:
                self.logger.warning(
                    f"Object {full_key} does not exist in bucket {bucket_name}"
                )
                return None
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error getting object {full_key}: {str(e)}")
            raise

    def put_object_to_bucket(
        self, bucket_name: str, full_key: str, some_binary_data: bytes
    ) -> dict[str, Any]:
        self.logger.info(f"Putting object {full_key} to bucket {bucket_name}")
        s3_object = self.boto3_resource.Object(bucket_name, full_key)
        result: dict[str, Any] = s3_object.put(Body=some_binary_data)
        # Refresh metadata so cache reflects the just-written object
        s3_object.reload()
        self.cache[full_key] = some_binary_data
        self.last_modified_cache[full_key] = s3_object.last_modified
        self.logger.debug(f"Successfully put object {full_key} to bucket {bucket_name}")
        return result

    @staticmethod
    def get_full_path(object_key: str) -> str:
        folder_levels: list[str] = object_key.split("/")[:-1]
        return "/".join(folder_levels)

    @staticmethod
    def get_parent_folder_name(object_key: str) -> str:
        folder_levels: list[str] = object_key.split("/")
        if len(folder_levels) >= 2:
            return folder_levels[-2]
        return ""

    @staticmethod
    def get_object_name(object_key: str) -> str:
        return object_key.split("/")[-1]
