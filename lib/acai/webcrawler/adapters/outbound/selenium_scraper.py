import time
from typing import Any, Dict, Optional

from acai.logging.ports import Loggable
from acai.webcrawler.domain.exceptions import WebOperationError
from acai.webcrawler.domain.scraper_config import WebConfig
from acai.webcrawler.ports.scraper_port import WebScraperPort
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class SeleniumScraper(WebScraperPort):
    """Outbound adapter — scrapes web pages via Selenium Chrome WebDriver.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``WebScraperPort``.
    """

    VERSION: str = "1.1.4"  # inject_version

    def __init__(self, logger: Loggable, config: Optional[WebConfig] = None) -> None:
        self._logger = logger
        self._config = config or WebConfig()
        self._driver: Optional[webdriver.Chrome] = None
        self._initialize_driver()

    def _initialize_driver(self) -> None:
        try:
            service = None
            if self._config.driver_path:
                service = Service(executable_path=self._config.driver_path)

            self._driver = webdriver.Chrome(
                service=service,
                options=self._build_chrome_options(),
            )
            self._logger.info("Successfully initialized Chrome WebDriver")

        except WebDriverException as exc:
            msg = f"WebDriver initialization failed: {exc}"
            self._logger.error(msg)
            raise WebOperationError(msg) from exc
        except Exception as exc:
            msg = f"Unexpected error during driver initialization: {exc}"
            self._logger.error(msg)
            raise WebOperationError(msg) from exc

    def _build_chrome_options(self) -> Options:
        options = Options()
        if self._config.headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        self._logger.debug(f"Chrome options: headless={self._config.headless}")
        return options

    # ── WebScraperPort implementation ─────────────────────────────────

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        retries = self._config.retry_attempts

        self._logger.info(f"Fetching page: {url}")
        for attempt in range(retries):
            try:
                if not url.startswith(("http://", "https://")):
                    url = f"{self._config.base_url.rstrip('/')}/{url.lstrip('/')}"
                    self._logger.debug(f"Resolved relative URL to: {url}")

                self._driver.get(url)

                # Single combined selector — avoids sequential 5s timeouts
                combined_selector = (
                    "#content, .content, main, #main, .main-content, #main-content"
                )
                content_found = self._wait_for_element(
                    By.CSS_SELECTOR,
                    combined_selector,
                    timeout=5,
                )

                if not content_found:
                    self._logger.debug(
                        f"No content selector matched, waiting {self._config.page_load_delay}s for page load"
                    )
                    time.sleep(self._config.page_load_delay)
                    if len(self._driver.page_source) < 100:
                        self._logger.warning(
                            f"Page source too short ({len(self._driver.page_source)} chars) on attempt {attempt + 1}/{retries}"
                        )
                        if attempt < retries - 1:
                            time.sleep(self._config.retry_delay)
                            continue
                        return None
                else:
                    self._logger.debug(f"Content selector matched for {url}")

                self._logger.info(f"Successfully fetched page: {url}")
                return BeautifulSoup(self._driver.page_source, "html.parser")

            except Exception as exc:
                self._logger.error(f"Attempt {attempt + 1}/{retries} failed: {exc}")
                if attempt < retries - 1:
                    time.sleep(self._config.retry_delay)
                    continue
                raise WebOperationError(
                    f"Failed to get page for URL {url} after {retries} attempts"
                ) from exc

    def extract_content(self, page: BeautifulSoup) -> Dict[str, Any]:
        result: Dict[str, Any] = {"content": None, "length": 0, "error": None}
        self._logger.debug("Extracting content from page")

        try:
            for selector in [
                "#content",
                ".content",
                "main",
                "#main",
                ".main-content",
                "#main-content",
            ]:
                content = page.select_one(selector)
                if content:
                    result["content"] = content
                    result["length"] = len(str(content))
                    self._logger.debug(
                        f"Matched selector '{selector}', content length: {result['length']}"
                    )
                    break

            if not result["content"]:
                body = page.find("body")
                if body:
                    result["content"] = body
                    result["length"] = len(str(body))
                    self._logger.debug(
                        f"Fell back to <body>, content length: {result['length']}"
                    )
                else:
                    result["error"] = "No content found"
                    self._logger.warning("No content found in page")

        except Exception as exc:
            result["error"] = f"Error extracting content: {exc}"
            self._logger.error(f"Error extracting content: {exc}")

        return result

    def cleanup(self) -> None:
        if self._driver:
            try:
                self._driver.quit()
                self._logger.info("Successfully closed Chrome WebDriver")
            except Exception as exc:
                self._logger.error(f"Error closing Chrome WebDriver: {exc}")
            finally:
                self._driver = None

    # ── adapter-specific helpers ──────────────────────────────────────

    def _wait_for_element(
        self,
        by: By,
        value: str,
        timeout: Optional[int] = None,
        condition: str = "presence",
    ) -> Optional[Any]:
        timeout = timeout or self._config.default_timeout
        conditions = {
            "presence": EC.presence_of_element_located,
            "visibility": EC.visibility_of_element_located,
            "clickable": EC.element_to_be_clickable,
        }

        try:
            self._logger.debug(
                f"Waiting for element '{value}' ({condition}, timeout={timeout}s)"
            )
            wait_condition = conditions.get(condition, EC.presence_of_element_located)
            return WebDriverWait(self._driver, timeout).until(
                wait_condition((by, value))
            )
        except TimeoutException:
            self._logger.debug(f"Timeout waiting for element '{value}'")
            return None
        except Exception as exc:
            self._logger.error(f"Error waiting for element {value}: {exc}")
            return None

    def __del__(self) -> None:
        self.cleanup()
