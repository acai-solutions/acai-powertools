"""
Sample usage of acai logger in a Lambda-like Python function.
"""

from acai.logging import LoggerConfig, LoggerContext, LogLevel, create_lambda_logger

# Initialize logger (you can set a name or use default)
logger = create_lambda_logger(
    LoggerConfig(service_name="lambda-demo", log_level=LogLevel.DEBUG)
)


@logger.inject_lambda_context()
def lambda_handler(event, context):
    logger.info("Lambda handler started.")
    logger.debug(f"Received event: {event}")
    try:
        # Simulate some processing
        result = {"message": "Hello from ACAI Logger!", "input": event}

        with LoggerContext(logger, {"stage": "reporting"}):
            logger.info("Start Reporting")

        # Using context manager
        with LoggerContext(logger, {"user_id": "123", "request_id": "abc"}):
            logger.info("Processing request")
            with LoggerContext(logger, {"operation": "database_query"}):
                logger.debug("Executing SQL query")

        logger.log("Info", "This is an info message")

        logger.info("Processing successful.")

        return result
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise


if __name__ == "__main__":
    # Example local test
    sample_event = {"foo": "bar"}
    print(lambda_handler(sample_event, None))
