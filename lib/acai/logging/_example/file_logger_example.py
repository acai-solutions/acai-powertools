"""
Example: FileLogger backed by LocalFileStorage
===============================================

Run directly::

    python -m acai.logging._example.file_logger_example

Demonstrates the ``FileLogger`` adapter that persists log lines via a
``StorageWriter`` instead of using Python's ``logging`` module directly.
"""

import shutil
import tempfile
from pathlib import Path

from acai.logging import LoggerConfig, LogLevel, create_local_logger, create_logger
from acai.storage import create_storage


def main() -> None:
    work_dir = Path(tempfile.mkdtemp(prefix="acai_filelog_example_"))

    # Bootstrap logger (console) used by the storage adapter itself
    bootstrap = create_logger(
        LoggerConfig(service_name="bootstrap", log_level=LogLevel.WARNING)
    )
    storage = create_storage(bootstrap)

    log_path = work_dir / "app.log"

    try:
        # ── 1. Text-format FileLogger ─────────────────────────────────
        logger = create_local_logger(
            LoggerConfig(service_name="my-app", log_level=LogLevel.DEBUG),
            storage=storage,
            log_path=str(log_path),
        )

        logger.info("Application started")
        logger.debug("Loading config", source="env")
        logger.warning("Slow query", table="laws", duration_ms=430)
        logger.error("Connection lost", host="db.example.com")

        # Flush buffered lines to storage
        logger.flush()

        print("── Text log ────────────────────────────────────")
        print(storage.read(log_path))

        # ── 2. JSON-format FileLogger ─────────────────────────────────
        json_log_path = work_dir / "app.jsonl"
        json_logger = create_local_logger(
            LoggerConfig(
                service_name="my-app-json", log_level=LogLevel.DEBUG, json_output=True
            ),
            storage=storage,
            log_path=str(json_log_path),
        )

        json_logger.info("Pipeline started", step="50_create_embeddings")
        json_logger.debug("Processing batch", batch_id=7, size=256)
        json_logger.flush()

        print("── JSON log ────────────────────────────────────")
        print(storage.read(json_log_path))

        # ── 3. Level filtering ────────────────────────────────────────
        filtered_path = work_dir / "filtered.log"
        filtered = create_local_logger(
            LoggerConfig(service_name="filtered", log_level=LogLevel.WARNING),
            storage=storage,
            log_path=str(filtered_path),
        )

        filtered.debug("This should NOT appear")
        filtered.info("This should NOT appear either")
        filtered.warning("This SHOULD appear")
        filtered.error("This SHOULD appear too")
        filtered.flush()

        print("── Filtered log (WARNING+) ─────────────────────")
        print(storage.read(filtered_path))

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"Cleaned up {work_dir}")


if __name__ == "__main__":
    main()
