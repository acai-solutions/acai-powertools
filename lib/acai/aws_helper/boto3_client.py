from __future__ import annotations

import os
from typing import Any

import boto3
from acai.logging import Loggable
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

REGION: str = os.environ.get("AWS_REGION", "us-east-1")

DEFAULT_RETRY_CONFIG: Config = Config(
    retries={
        "max_attempts": 5,
        "mode": "adaptive",
    },
    max_pool_connections=50,
)


class Boto3ClientFactory:
    """Factory for creating boto3 clients and resources with retry configuration."""

    def __init__(
        self,
        logger: Loggable,
        region: str | None = None,
        config: Config | None = None,
    ) -> None:
        self.logger = logger
        self.region = region or REGION
        self.config = config or DEFAULT_RETRY_CONFIG

    def get_client(
        self,
        service_name: str,
        region: str | None = None,
        custom_config: Config | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a boto3 client for *service_name*.

        Args:
            service_name: AWS service name (e.g. ``'s3'``, ``'sns'``, ``'lambda'``).
            region: AWS region override (defaults to instance region).
            custom_config: Custom :class:`botocore.config.Config`
                override (defaults to instance config).
            **kwargs: Additional arguments forwarded to :func:`boto3.client`.

        Returns:
            A boto3 client for the requested service.
        """
        client_region = region or self.region
        config = custom_config or self.config

        try:
            self.logger.debug(
                f"Creating boto3 client for {service_name} in {client_region}"
            )
            client = boto3.client(
                service_name, region_name=client_region, config=config, **kwargs
            )
            self.logger.info(
                f"Successfully created boto3 client for {service_name} in {client_region}"
            )
            return client

        except NoCredentialsError as e:
            self.logger.error(f"AWS credentials not found for {service_name}: {e}")
            raise

        except ClientError as e:
            self.logger.error(f"Failed to create boto3 client for {service_name}: {e}")
            raise

    def get_resource(
        self,
        service_name: str,
        region: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a boto3 resource for *service_name*.

        Args:
            service_name: AWS service name (e.g. ``'s3'``, ``'dynamodb'``).
            region: AWS region override (defaults to instance region).
            **kwargs: Additional arguments forwarded to :func:`boto3.resource`.

        Returns:
            A boto3 resource for the requested service.
        """
        client_region = region or self.region

        try:
            self.logger.debug(
                f"Creating boto3 resource for {service_name} in {client_region}"
            )
            resource = boto3.resource(service_name, region_name=client_region, **kwargs)
            self.logger.info(
                f"Successfully created boto3 resource for {service_name} in {client_region}"
            )
            return resource

        except Exception as e:
            self.logger.error(
                f"Failed to create boto3 resource for {service_name}: {e}"
            )
            raise


# Backward compatibility: module-level functions that wrap the class
def get_aws_client(
    logger: Loggable,
    service_name: str,
    region: str | None = None,
    custom_config: Config | None = None,
    **kwargs: Any,
) -> Any:
    """Create a boto3 client with retry configuration."""
    factory = Boto3ClientFactory(logger, region, custom_config)
    return factory.get_client(service_name, **kwargs)


def get_boto3_resource(
    logger: Loggable,
    service_name: str,
    region: str | None = None,
    **kwargs: Any,
) -> Any:
    """Create a boto3 resource with standardised logging."""
    factory = Boto3ClientFactory(logger, region)
    return factory.get_resource(service_name, **kwargs)
