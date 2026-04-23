"""
Example: AWS Lambda logging with CloudWatch
============================================

Deploy this module as a Lambda handler.  The **CloudWatchLogger** adapter
sends structured JSON logs to CloudWatch via *aws-lambda-powertools*.

Wire-up::

    # In your Lambda entry-point module
    from acai.logging._example.lambda_example import handler   # noqa

Key points
----------
* ``create_logger(use_cloudwatch=True)`` selects the CloudWatch adapter.
* ``inject_lambda_context`` decorator automatically captures request ID,
  cold-start status, function name, and (optionally) the event payload.
* ``push_context`` / ``pop_context`` let you add request-scoped keys that
  appear in every log line until popped.
"""

from acai.logging import LoggerConfig, LogLevel, create_lambda_logger

# ── Logger bootstrap (runs once per cold start) ─────────────────────
config = LoggerConfig(
    service_name="law-bot-lambda",
    log_level=LogLevel.DEBUG,
    json_output=True,  # CloudWatch always uses JSON, but this flag
)  # is passed through for consistency.

logger = create_lambda_logger(config)


# ── Lambda handler ───────────────────────────────────────────────────


@logger.inject_lambda_context(
    include_event=True,  # log the incoming event (truncated to 1 kB)
    include_context=True,  # log function name, request ID, memory, …
    include_response=False,  # set True to log the return value
    include_cold_start=True,  # tag the first invocation
    log_exceptions=True,  # auto-log unhandled exceptions
    extra_context={  # static keys added to every log line
        "team": "data-engineering",
        "project": "law-bot",
    },
)
def handler(event: dict, context: object) -> dict:
    """Sample Lambda handler that processes a law document embedding request."""

    # Every log line inside the handler automatically includes the Lambda
    # context injected by the decorator (request_id, cold_start, etc.).
    logger.info(
        "Received embedding request", record_count=len(event.get("records", []))
    )

    # Add request-scoped context that persists for the duration of a loop
    for i, record in enumerate(event.get("records", [])):
        logger.push_context({"record_index": i, "doc_id": record.get("id")})
        logger.debug("Processing record")

        # ... your embedding / DB logic here ...

        logger.info("Record processed successfully")
        logger.pop_context()

    # After the loop the context stack is clean again
    logger.info("All records processed")

    return {"statusCode": 200, "body": "OK"}


# ── For local smoke-testing ──────────────────────────────────────────
if __name__ == "__main__":
    # Simulate a Lambda invocation locally.
    # CloudWatchLogger will write JSON to stdout, which you can inspect.
    class _FakeContext:
        aws_request_id = "local-test-id"
        function_name = "law-bot-lambda-local"
        function_version = "$LATEST"
        memory_limit_in_mb = 256
        log_group_name = "/aws/lambda/law-bot-lambda-local"
        log_stream_name = "2026/03/23/[$LATEST]abc123"

        @staticmethod
        def get_remaining_time_in_millis() -> int:
            return 300_000

    fake_event = {
        "records": [
            {"id": "SR-210", "language": "de"},
            {"id": "SR-311", "language": "fr"},
        ]
    }

    result = handler(fake_event, _FakeContext())
    print(f"\nHandler returned: {result}")
