"""
Sample Lambda that imports the inline-injected helper module
`acme.logging_factory` (baked into the Lambda layer via `inline_files`).
"""

import acme.logging_factory as factory
from acme.logging_factory import LoggerContext, setup_logging

logger = setup_logging(service_name="lambda-inline-demo", log_level="DEBUG")


@logger.inject_lambda_context()
def lambda_handler(event, context):
    logger.info("Lambda handler started.")
    logger.debug(f"Received event: {event}")

    with LoggerContext(logger, {"stage": "inline_demo"}):
        logger.info("Helper module loaded from layer")

    result = {
        "message": "Hello from Lambda using inline helper from layer!",
        "factory_module_path": factory.__file__,
        "input": event,
    }

    logger.info("Processing successful.")
    return result


if __name__ == "__main__":
    print(lambda_handler({"foo": "bar"}, None))
