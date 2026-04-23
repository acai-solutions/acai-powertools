"""
Solution 1: Store files to the local file system
=================================================

Demonstrates using the acai logging and storage libraries to
persist text and JSON files locally with structured logging.

Run::

    cd hl2/shared/python && pip install -e .
    cd hl2/solution1
    python store_files.py
"""

from dataclasses import dataclass
from pathlib import Path

from acai.logging import LoggerConfig, LoggerContext, LogLevel, create_logger
from acai.storage import StorageConfig, create_storage


@dataclass
class LawArticle:
    sr_number: str
    title: str
    language: str
    summary: str


def main() -> None:
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)

    # ── Logger ────────────────────────────────────────────────────────
    logger = create_logger(
        LoggerConfig(
            service_name="store-files",
            log_level=LogLevel.DEBUG,
            log_dir=Path(__file__).resolve().parent / "logs",
        )
    )

    # ── Storage ───────────────────────────────────────────────────────
    config = StorageConfig(allowed_extensions={"txt", "json"})
    storage = create_storage(logger, config)

    # ── 1. Save and read a plain text file ────────────────────────────
    with LoggerContext(logger, {"step": "text-files"}):
        txt_path = output_dir / "readme.txt"
        storage.save(txt_path, "This file was created by the store_files solution.")
        logger.info("Saved text file", path=str(txt_path))

        content = storage.read(txt_path)
        logger.info("Read text file", length=len(content))

    # ── 2. Save and read JSON with dataclasses ────────────────────────
    with LoggerContext(logger, {"step": "json-files"}):
        articles = [
            LawArticle("SR 210", "Zivilgesetzbuch", "de", "Swiss Civil Code"),
            LawArticle(
                "SR 220", "Obligationenrecht", "de", "Swiss Code of Obligations"
            ),
            LawArticle("SR 311.0", "Strafgesetzbuch", "de", "Swiss Criminal Code"),
        ]

        json_path = output_dir / "articles.json"
        storage.save_json(json_path, articles)
        logger.info("Saved JSON file", path=str(json_path), count=len(articles))

        loaded = storage.read_json(json_path, data_type=LawArticle)
        for article in loaded:
            logger.debug(
                "Loaded article", sr_number=article.sr_number, title=article.title
            )

        logger.info("Read JSON file", count=len(loaded))

    # ── 3. Verify existence ───────────────────────────────────────────
    logger.info(
        "File check",
        readme_exists=storage.exists(txt_path),
        articles_exists=storage.exists(json_path),
        missing_exists=storage.exists(output_dir / "missing.txt"),
    )

    logger.info("Done — files stored in output/")


if __name__ == "__main__":
    main()
