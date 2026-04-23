from __future__ import annotations

import socket
import time
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
        session_name: str | None = None,
    ) -> boto3.Session | None:
        """Assume *role_arn* and return a boto3 Session with temporary credentials.

        ``session_name`` is forwarded as ``RoleSessionName`` so CloudTrail
        events can be traced back to the caller. When omitted, a name is
        generated from the host name and current epoch time.
        """
        try:
            kwargs: dict[str, str] = {}
            if region_name:
                kwargs["region_name"] = region_name

            sts_client = self._base_session.client("sts", **kwargs)

            self.logger.debug(f"Assuming role {role_arn}")
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name or _default_session_name(),
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


def _default_session_name() -> str:
    """Build a CloudTrail-friendly RoleSessionName: ``acai-<host>-<epoch>``."""
    try:
        host = socket.gethostname().split(".", 1)[0][:32] or "unknown"
    except Exception:
        host = "unknown"
    return f"acai-{host}-{int(time.time())}"
