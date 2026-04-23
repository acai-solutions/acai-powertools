from __future__ import annotations

import json
import time
from typing import Any

from acai.logging import Loggable
from botocore.exceptions import ClientError


class CloudWatchClient:
    def __init__(
        self, logger: Loggable, boto3_logs_client: Any, log_group_name: str
    ) -> None:
        self.logger = logger
        self.group_name = log_group_name
        self.cw_client = boto3_logs_client

    def send_to_cw(self, log_stream_name: str, object_to_send: Any) -> None:
        """Write *object_to_send* as a single log event to CloudWatch Logs.

        Sequence tokens are no longer required (deprecated since 2023).
        """
        self.logger.debug(f"Send to {self.group_name}/{log_stream_name}")
        timestamp = int(round(time.time() * 1000))
        message = json.dumps(object_to_send)

        try:
            self.cw_client.put_log_events(
                logGroupName=self.group_name,
                logStreamName=log_stream_name,
                logEvents=[{"timestamp": timestamp, "message": message}],
            )
        except ClientError as e:
            self.logger.error(
                f"Failed to write to {self.group_name}/{log_stream_name}: {e}"
            )
            raise
