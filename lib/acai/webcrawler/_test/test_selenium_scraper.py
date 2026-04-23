"""Tests for ``acai.webcrawler`` — SeleniumScraper adapter.

All tests mock the Selenium WebDriver so no real browser is required.
"""

from unittest.mock import MagicMock, patch

import pytest
from acai.webcrawler import (
    ConfigurationError,
    WebConfig,
    WebOperationError,
    create_scraper,
)
from acai.webcrawler.adapters.outbound.selenium_scraper import SeleniumScraper
from acai.webcrawler.ports.scraper_port import WebScraperPort
from bs4 import BeautifulSoup

# ── helpers ───────────────────────────────────────────────────────────


SIMPLE_HTML = """
<html>
<head><title>Test Page</title></head>
<body>
  <main><p>Main content</p></main>
</body>
</html>
"""

CONTENT_DIV_HTML = """
<html>
<body>
  <div id="content"><h1>Title</h1><p>Body text</p></div>
</body>
</html>
"""

BARE_HTML = """
<html>
<body><p>Only a body</p></body>
</html>
"""

EMPTY_HTML = "<html><head></head></html>"


def _make_scraper(logger, config=None) -> SeleniumScraper:
    """Build a SeleniumScraper with a mocked Chrome WebDriver."""
    with patch("acai.webcrawler.adapters.outbound.selenium_scraper.webdriver.Chrome"):
        return SeleniumScraper(logger=logger, config=config or WebConfig())


# ── WebConfig validation ─────────────────────────────────────────────


class TestWebConfig:
    def test_defaults(self):
        cfg = WebConfig()
        assert cfg.headless is False  # nosec B101
        assert cfg.default_timeout == 3  # nosec B101
        assert cfg.page_load_delay == 1.0  # nosec B101
        assert cfg.retry_attempts == 3  # nosec B101

    def test_negative_timeout_raises(self):
        with pytest.raises(ConfigurationError, match="positive"):
            WebConfig(default_timeout=-1)

    def test_zero_timeout_raises(self):
        with pytest.raises(ConfigurationError, match="positive"):
            WebConfig(default_timeout=0)

    def test_negative_page_load_delay_raises(self):
        with pytest.raises(ConfigurationError, match="negative"):
            WebConfig(page_load_delay=-0.5)

    def test_nonexistent_driver_path_raises(self):
        with pytest.raises(ConfigurationError, match="does not exist"):
            WebConfig(driver_path="/no/such/chromedriver")

    def test_custom_config(self):
        cfg = WebConfig(headless=True, default_timeout=10, retry_attempts=5)
        assert cfg.headless is True  # nosec B101
        assert cfg.default_timeout == 10  # nosec B101
        assert cfg.retry_attempts == 5  # nosec B101


# ── extract_content ──────────────────────────────────────────────────


class TestExtractContent:
    def test_extracts_main_element(self, logger):
        scraper = _make_scraper(logger)
        page = BeautifulSoup(SIMPLE_HTML, "html.parser")
        result = scraper.extract_content(page)
        assert result["content"] is not None  # nosec B101
        assert result["length"] > 0  # nosec B101
        assert result["error"] is None  # nosec B101

    def test_extracts_content_div(self, logger):
        scraper = _make_scraper(logger)
        page = BeautifulSoup(CONTENT_DIV_HTML, "html.parser")
        result = scraper.extract_content(page)
        assert result["content"] is not None  # nosec B101
        assert "Title" in result["content"].get_text()  # nosec B101

    def test_falls_back_to_body(self, logger):
        scraper = _make_scraper(logger)
        page = BeautifulSoup(BARE_HTML, "html.parser")
        result = scraper.extract_content(page)
        assert result["content"] is not None  # nosec B101
        assert "Only a body" in result["content"].get_text()  # nosec B101

    def test_no_content_sets_error(self, logger):
        scraper = _make_scraper(logger)
        page = BeautifulSoup(EMPTY_HTML, "html.parser")
        result = scraper.extract_content(page)
        assert result["error"] is not None  # nosec B101


# ── get_page ─────────────────────────────────────────────────────────


class TestGetPage:
    def test_returns_soup_on_success(self, logger):
        scraper = _make_scraper(logger, WebConfig(page_load_delay=0, retry_delay=0))
        scraper._driver.page_source = SIMPLE_HTML
        scraper._wait_for_element = MagicMock(return_value=True)

        page = scraper.get_page("https://example.com")
        assert isinstance(page, BeautifulSoup)  # nosec B101
        assert page.title.string == "Test Page"  # nosec B101

    def test_prepends_base_url_for_relative_path(self, logger):
        cfg = WebConfig(
            base_url="https://www.fedlex.admin.ch", page_load_delay=0, retry_delay=0
        )
        scraper = _make_scraper(logger, cfg)
        scraper._driver.page_source = SIMPLE_HTML
        scraper._wait_for_element = MagicMock(return_value=True)

        scraper.get_page("/eli/cc/24/233_245_233/de")
        scraper._driver.get.assert_called_once_with(
            "https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de"
        )

    def test_retries_on_failure(self, logger):
        cfg = WebConfig(retry_attempts=3, page_load_delay=0, retry_delay=0)
        scraper = _make_scraper(logger, cfg)
        scraper._driver.get.side_effect = [Exception("net"), Exception("net"), None]
        scraper._driver.page_source = SIMPLE_HTML
        scraper._wait_for_element = MagicMock(return_value=True)

        page = scraper.get_page("https://example.com")
        assert isinstance(page, BeautifulSoup)  # nosec B101
        assert scraper._driver.get.call_count == 3  # nosec B101

    def test_raises_after_all_retries_exhausted(self, logger):
        cfg = WebConfig(retry_attempts=2, page_load_delay=0, retry_delay=0)
        scraper = _make_scraper(logger, cfg)
        scraper._driver.get.side_effect = Exception("persistent error")

        with pytest.raises(WebOperationError, match="Failed to get page"):
            scraper.get_page("https://example.com")


# ── cleanup ──────────────────────────────────────────────────────────


class TestCleanup:
    def test_cleanup_quits_driver(self, logger):
        scraper = _make_scraper(logger)
        mock_driver = scraper._driver

        scraper.cleanup()
        mock_driver.quit.assert_called_once()
        assert scraper._driver is None  # nosec B101

    def test_cleanup_idempotent(self, logger):
        scraper = _make_scraper(logger)
        scraper.cleanup()
        scraper.cleanup()  # second call is a no-op

    def test_context_manager_calls_cleanup(self, logger):
        with patch(
            "acai.webcrawler.adapters.outbound.selenium_scraper.webdriver.Chrome"
        ):
            with SeleniumScraper(logger=logger) as scraper:
                mock_driver = scraper._driver
            mock_driver.quit.assert_called_once()


# ── exception hierarchy ──────────────────────────────────────────────


class TestExceptions:
    def test_web_operation_error_is_scraper_exception(self):
        from acai.webcrawler.domain.exceptions import ScraperException

        assert issubclass(WebOperationError, ScraperException)  # nosec B101

    def test_configuration_error_is_scraper_exception(self):
        from acai.webcrawler.domain.exceptions import ScraperException

        assert issubclass(ConfigurationError, ScraperException)  # nosec B101


# ── factory ───────────────────────────────────────────────────────────


class TestFactory:
    def test_create_scraper_returns_selenium(self, logger):
        with patch(
            "acai.webcrawler.adapters.outbound.selenium_scraper.webdriver.Chrome"
        ):
            scraper = create_scraper(logger)
            assert isinstance(scraper, SeleniumScraper)  # nosec B101
            assert isinstance(scraper, WebScraperPort)  # nosec B101

    def test_create_scraper_with_config(self, logger):
        cfg = WebConfig(headless=True, default_timeout=10)
        with patch(
            "acai.webcrawler.adapters.outbound.selenium_scraper.webdriver.Chrome"
        ):
            scraper = create_scraper(logger, cfg)
            assert scraper._config.headless is True  # nosec B101
            assert scraper._config.default_timeout == 10  # nosec B101

    def test_driver_init_failure_raises(self, logger):
        with patch(
            "acai.webcrawler.adapters.outbound.selenium_scraper.webdriver.Chrome",
            side_effect=Exception("no chrome"),
        ):
            with pytest.raises(WebOperationError):
                create_scraper(logger)
