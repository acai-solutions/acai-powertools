from __future__ import annotations

from typing import Any

import boto3
import botocore
from acai.aws_helper.sts import StsClient
from acai.logging import Loggable

_DEFAULT_RETRY = {"max_attempts": 10, "mode": "adaptive"}


class AwsSessionManager:
    def __init__(
        self,
        logger: Loggable,
        remote_role_arn: str,
        config: botocore.config.Config | None = None,
    ) -> None:
        self.logger = logger
        self.remote_role_arn = remote_role_arn
        self.base_config = config or botocore.config.Config(retries=_DEFAULT_RETRY)
        self._sts = StsClient(logger)
        self.remote_region_sessions: dict[str, boto3.Session] = {}
        self.remote_region_clients: dict[str, dict[str, Any]] = {}
        self.warned_sessions: set[str] = set()
        self.warned_clients: set[tuple[str, str]] = set()

    def get_sts_session(self, region: str) -> boto3.Session | None:
        if region not in self.remote_region_sessions:
            self.logger.debug(
                f"Creating new STS session for account in region {region}"
            )
            session = self._sts.assume_role(self.remote_role_arn, region_name=region)
            if session is None:
                if region not in self.warned_sessions:
                    self.logger.warning(f"Failed to assume role for region {region}")
                    self.warned_sessions.add(region)
            else:
                self.remote_region_sessions[region] = session
        return self.remote_region_sessions.get(region)

    def get_client(self, boto3_service_name: str, region: str) -> Any | None:
        """Return a cached boto3 client for *boto3_service_name* in *region*.

        Creates the STS session and client on first call; subsequent calls
        return the cached instance.
        """
        clients_for_region = self.remote_region_clients.setdefault(region, {})

        if boto3_service_name not in clients_for_region:
            sts_session = self.get_sts_session(region)
            if sts_session is None:
                return None

            regional_config = self.base_config.merge(
                botocore.config.Config(region_name=region)
            )
            client = sts_session.client(boto3_service_name, config=regional_config)
            clients_for_region[boto3_service_name] = client
            self.logger.debug(
                f"Created new client for {boto3_service_name} in region {region}"
            )

        return clients_for_region[boto3_service_name]

    def get_member_client(self, boto3_service_name: str, region: str) -> Any | None:
        try:
            return self.get_client(boto3_service_name, region)
        except Exception as e:
            warning_key = (region, boto3_service_name)
            if warning_key not in self.warned_clients:
                self.logger.warning(
                    f"Error getting or creating client for {boto3_service_name} in region {region}: {e}"
                )
                self.warned_clients.add(warning_key)
            return None
