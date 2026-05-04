from __future__ import annotations

import json
from typing import Any

from acai.logging import Loggable


class SnsClient:
    """Thin wrapper around SNS ``publish`` with constructor-injected logger."""

    def __init__(self, logger: Loggable, boto3_client: Any) -> None:
        self.logger = logger
        self.sns_client = boto3_client

    def publish(
        self,
        topic_arn: str,
        subject_text: str,
        event_json: Any,
        message_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Publish a JSON message to an SNS topic."""
        if message_attributes is None:
            message_attributes = {}
        try:
            self.logger.info(
                f"Sending to SNS ({topic_arn}) message_attributes {json.dumps(message_attributes)}"
            )

            message_text = json.dumps({"default": json.dumps(event_json, indent=4)})
            response = self.sns_client.publish(
                TopicArn=topic_arn,
                Subject=subject_text,
                Message=message_text,
                MessageStructure="json",
                MessageAttributes=message_attributes,
            )
            return response
        except Exception as e:
            self.logger.error(f"Was not able to send to SNS {topic_arn}: {e}")
            return None


# Backward compatibility: module-level function that wraps the class
def send_to_sns(
    custom_logger: Loggable,
    boto3_client: Any,
    topic_arn: str,
    subject_text: str,
    event_json: Any,
    message_attributes: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Publish a JSON message to an SNS topic."""
    client = SnsClient(custom_logger, boto3_client)
    return client.publish(topic_arn, subject_text, event_json, message_attributes)
