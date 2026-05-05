from __future__ import annotations

import socket
import time
from typing import Any

import boto3
from acai.logging import Loggable
from botocore.config import Config

DEFAULT_STS_CONFIG: Config = Config(
    retries={"max_attempts": 5, "mode": "adaptive"},
)


class StsClient:
    """Thin wrapper around STS ``assume_role`` with constructor-injected logger."""

    def __init__(
        self,
        logger: Loggable,
        base_session: boto3.Session | None = None,
        config: Config | None = None,
    ) -> None:
        self.logger = logger
        self._base_session: Any = base_session or boto3
        self._config: Config = config or DEFAULT_STS_CONFIG

    def assume_role(
        self,
        role_arn: str,
        region_name: str | None = None,
        session_name: str | None = None,
        duration_seconds: int | None = None,
        external_id: str | None = None,
        policy: str | None = None,
        tags: list[dict[str, str]] | None = None,
        transitive_tag_keys: list[str] | None = None,
        config: Config | None = None,
    ) -> boto3.Session | None:
        """Assume *role_arn* and return a boto3 Session with temporary credentials.

        ``session_name`` is forwarded as ``RoleSessionName`` so CloudTrail
        events can be traced back to the caller. When omitted, a name is
        generated from the host name and current epoch time.

        ``region_name`` is applied both to the STS client used for the
        AssumeRole call **and** to the returned session, so downstream
        clients created from it inherit the region.

        Returns ``None`` on any failure; the full traceback is logged via
        ``logger.exception`` for diagnosis.
        """
        try:
            client_kwargs: dict[str, Any] = {"config": config or self._config}
            if region_name:
                client_kwargs["region_name"] = region_name

            sts_client = self._base_session.client("sts", **client_kwargs)

            assume_kwargs: dict[str, Any] = {
                "RoleArn": role_arn,
                "RoleSessionName": session_name or _default_session_name(),
            }
            if duration_seconds is not None:
                assume_kwargs["DurationSeconds"] = duration_seconds
            if external_id is not None:
                assume_kwargs["ExternalId"] = external_id
            if policy is not None:
                assume_kwargs["Policy"] = policy
            if tags is not None:
                assume_kwargs["Tags"] = tags
            if transitive_tag_keys is not None:
                assume_kwargs["TransitiveTagKeys"] = transitive_tag_keys

            self.logger.debug(f"Assuming role {role_arn}")
            response = sts_client.assume_role(**assume_kwargs)

            creds = response["Credentials"]
            session = boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=region_name,
            )
            self.logger.debug(f"Assumed role {role_arn}")
            return session

        except Exception:
            self.logger.exception(f"Was not able to assume role {role_arn}")
            return None


def _default_session_name() -> str:
    """Build a CloudTrail-friendly RoleSessionName: ``acai-<host>-<epoch>``."""
    try:
        host = socket.gethostname().split(".", 1)[0][:32] or "unknown"
    except Exception:
        host = "unknown"
    return f"acai-{host}-{int(time.time())}"
