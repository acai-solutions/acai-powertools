"""
Example: Local console logging
==============================

Run directly::

    python -m acai.logging._example.local_example

This wires the **ConsoleLogger** adapter through the ``create_logger`` factory.
"""

from acai.logging import LoggerConfig, LoggerContext, LogLevel, create_logger


def main() -> None:
    # ── 1. Minimal setup (console only, text format) ──────────────────
    logger = create_logger()

    logger.debug("Application starting")
    logger.info("Processing item", item_id=42, source="api")
    logger.warning("Slow response", latency_ms=1240)

    # ── 2. JSON output ────────────────────────────────────────────────
    config = LoggerConfig(
        service_name="law-bot-pipeline",
        log_level=LogLevel.DEBUG,
        json_output=True,
    )
    json_logger = create_logger(config)

    json_logger.info("Pipeline step started", step="30_crawl_fedlex_xml")
    json_logger.debug("Parsing document", doc_id="SR-210", language="de")
    json_logger.error("Parsing failed", doc_id="SR-999", reason="malformed XML")

    # ── 3. Context stack ──────────────────────────────────────────────
    #   push_context / pop_context attach metadata to every subsequent log
    #   until popped — useful for request-scoped information.

    logger.push_context({"request_id": "abc-123", "user": "admin"})
    logger.info("Handling request")  # includes request_id + user
    logger.info("Querying database", table="laws")
    logger.pop_context()

    logger.info("Context removed — this line has no extra metadata")

    # ── 4. Using LoggerContext as a context manager ───────────────────
    with LoggerContext(logger, {"batch_id": "batch-7", "source": "fedlex"}):
        logger.info("Batch processing started")
        logger.debug("Processing record 1/100")
        logger.debug("Processing record 2/100")
    # context is automatically popped here

    logger.info("Done — no batch context attached")

    # ── 5. Dynamic log level change ───────────────────────────────────
    logger.set_level(LogLevel.WARNING)
    logger.debug("This will NOT appear (level is WARNING)")
    logger.warning("This WILL appear")
    logger.set_level(LogLevel.DEBUG)


if __name__ == "__main__":
    main()
