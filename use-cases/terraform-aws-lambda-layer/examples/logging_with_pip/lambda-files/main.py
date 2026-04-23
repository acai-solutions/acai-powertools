"""
Sample usage of acai logger combined with the requests library and
aws-lambda-powertools — all bundled via pip_requirements into the same
Lambda layer.
"""

from importlib.metadata import version

import aws_lambda_powertools
import requests
from acai.logging import LoggerConfig, LoggerContext, LogLevel, create_lambda_logger

logger = create_lambda_logger(
    LoggerConfig(service_name="lambda-pip-demo", log_level=LogLevel.DEBUG)
)


@logger.inject_lambda_context()
def lambda_handler(event, context):
    logger.info("Lambda handler started.")
    logger.debug(f"Received event: {event}")

    powertools_version = version("aws-lambda-powertools")
    requests_version = version("requests")
    logger.info(f"aws-lambda-powertools version: {powertools_version}")
    logger.info(f"requests version: {requests_version}")

    try:
        with LoggerContext(logger, {"stage": "http_call"}):
            logger.info("Calling httpbin.org to verify requests library works")
            response = requests.get("https://httpbin.org/get", timeout=10)
            response.raise_for_status()
            logger.info(f"HTTP status: {response.status_code}")

        result = {
            "message": "Hello from ACAI Logger + pip requests!",
            "http_status": response.status_code,
            "powertools_version": powertools_version,
            "powertools_module_path": aws_lambda_powertools.__file__,
            "requests_version": requests_version,
            "input": event,
        }

        logger.info("Processing successful.")
        return result
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise


if __name__ == "__main__":
    sample_event = {"foo": "bar"}
    print(lambda_handler(sample_event, None))
