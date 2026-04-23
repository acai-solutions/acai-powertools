"""
Example: Web scraping with Selenium
====================================

Run directly::

    python -m acai.webcrawler._example.local_example

Demonstrates page fetching, content extraction, configuration,
context-manager cleanup, and the ``create_scraper`` factory.

Requirements
------------
- Google Chrome installed
- ChromeDriver on PATH (or specify ``driver_path`` in ``WebConfig``)
"""

import sys
from pathlib import Path

_this_dir = Path(__file__).resolve().parent
_shared_python = _this_dir.parent.parent.parent  # …/shared/python
if str(_shared_python) not in sys.path:
    sys.path.insert(0, str(_shared_python))

from acai.logging import LoggerConfig, LoggerContext, LogLevel, create_logger
from acai.webcrawler import WebConfig, create_scraper


def main() -> None:
    logger = create_logger(
        LoggerConfig(service_name="scraper-example", log_level=LogLevel.DEBUG)
    )

    config = WebConfig(
        headless=True,
        default_timeout=5,
        page_load_delay=1.0,
        base_url="https://www.fedlex.admin.ch",
    )

    # ── 1. Context-manager lifecycle ──────────────────────────────────
    with create_scraper(logger, config) as scraper:

        # ── 2. Fetch a page ──────────────────────────────────────────
        with LoggerContext(logger, {"step": "fetch"}):
            url = "https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de"
            logger.info("Fetching page", url=url)
            page = scraper.get_page(url)

            if page is None:
                logger.warning("Page returned None", url=url)
                return

            logger.info(
                "Page fetched", title=page.title.string if page.title else "n/a"
            )

        # ── 3. Extract content ────────────────────────────────────────
        with LoggerContext(logger, {"step": "extract"}):
            result = scraper.extract_content(page)
            if result["error"]:
                logger.error("Extraction error", error=result["error"])
            else:
                logger.info(
                    "Content extracted",
                    length=result["length"],
                    has_content=result["content"] is not None,
                )

    # ── 4. Config validation ──────────────────────────────────────────
    try:
        WebConfig(default_timeout=-1)
        print("ERROR — should have raised ConfigurationError")
    except Exception as exc:
        logger.info("Config validation works", error=str(exc))

    logger.info("Done — scraper cleaned up via context manager")


if __name__ == "__main__":
    main()
