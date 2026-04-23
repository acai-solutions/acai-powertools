from __future__ import annotations

from typing import Any

import boto3
from acai.logging import Loggable


class StsClient:
    """Thin wrapper around STS ``assume_role`` with constructor-injected logger."""

    def __init__(
        self,
        logger: Loggable,
        base_session: boto3.Session | None = None,
    ) -> None:
        self.logger = logger
        self._base_session: Any = base_session or boto3

    def assume_role(
        self,
        role_arn: str,
        region_name: str | None = None,
    ) -> boto3.Session | None:
        """Assume *role_arn* and return a boto3 Session with temporary credentials."""
        try:
            kwargs: dict[str, str] = {}
            if region_name:
                kwargs["region_name"] = region_name

            sts_client = self._base_session.client("sts", **kwargs)

            self.logger.debug(f"Assuming role {role_arn}")
            response = sts_client.assume_role(
                RoleArn=role_arn, RoleSessionName="RemoteSession"
            )

            creds = response["Credentials"]
            session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
            )
            self.logger.debug(f"Assumed role {role_arn}")
            return session

        except Exception as e:
            self.logger.warning(f"Was not able to assume role {role_arn}: {e}")
            return None
