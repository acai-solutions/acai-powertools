"""Tests for ``acai.logging`` — ConsoleLogger adapter (text & JSON)."""

import io
import json
import logging

import pytest
from acai.logging import LoggerConfig, LogLevel, create_logger
from acai.logging.adapters.outbound.console_logger import (
    ConsoleLogger,
    _JsonFormatter,
    _TextFormatter,
)
from acai.logging.domain.logger import Logger

# ── ConsoleLogger: factory basics ─────────────────────────────────────


class TestConsoleLoggerFactory:
    def test_default_creation(self):
        logger = create_logger()
        assert isinstance(logger, Logger)  # nosec B101

    def test_with_config(self):
        cfg = LoggerConfig(
            service_name="test-console",
            log_level=LogLevel.DEBUG,
            json_output=True,
        )
        logger = create_logger(cfg)
        # Should not raise
        logger.info("test message")

    def test_set_level(self):
        logger = create_logger(LoggerConfig(log_level=LogLevel.DEBUG))
        logger.set_level(LogLevel.ERROR)
        # No assertion beyond "doesn't crash"; console output is hard to capture


# ── ConsoleLogger: text output ────────────────────────────────────────


class TestConsoleLoggerTextOutput:
    @pytest.fixture(autouse=True)
    def _unique_logger(self):
        """Give each test a unique logger name to avoid handler leakage."""
        self._counter = getattr(type(self), "_counter", 0) + 1
        type(self)._counter = self._counter
        self.logger_name = f"test_console_text_{self._counter}"

    def _make(self, level=LogLevel.DEBUG, **kw):
        adapter = ConsoleLogger(logger_name=self.logger_name, level=level, **kw)
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_TextFormatter("%(levelname)s|%(message)s"))
        logging.getLogger(self.logger_name).addHandler(handler)
        return adapter, buf

    def test_all_five_levels(self):
        adapter, buf = self._make()
        adapter.debug("d")
        adapter.info("i")
        adapter.warning("w")
        adapter.error("e")
        adapter.critical("c")
        output = buf.getvalue()
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert lvl in output  # nosec B101

    def test_extra_fields_in_text(self):
        adapter, buf = self._make()
        adapter.info("msg", user="alice", action="login")
        output = buf.getvalue()
        assert "user=alice" in output  # nosec B101
        assert "action=login" in output  # nosec B101

    def test_level_filtering_suppresses_below(self):
        adapter, buf = self._make(level=LogLevel.WARNING)
        adapter.debug("hidden-debug")
        adapter.info("hidden-info")
        adapter.warning("visible-warn")
        output = buf.getvalue()
        assert "hidden-debug" not in output  # nosec B101
        assert "hidden-info" not in output  # nosec B101
        assert "visible-warn" in output  # nosec B101

    def test_set_level_dynamic(self):
        adapter, buf = self._make(level=LogLevel.DEBUG)
        adapter.info("before")
        adapter.set_level(LogLevel.ERROR)
        adapter.info("suppressed")
        adapter.error("after")
        output = buf.getvalue()
        assert "before" in output  # nosec B101
        assert "suppressed" not in output  # nosec B101
        assert "after" in output  # nosec B101

    def test_string_level_init(self):
        adapter = ConsoleLogger(logger_name=f"{self.logger_name}_str", level="warning")
        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.setFormatter(logging.Formatter("%(levelname)s|%(message)s"))
        logging.getLogger(f"{self.logger_name}_str").addHandler(h)
        adapter.info("hidden")
        adapter.warning("shown")
        output = buf.getvalue()
        assert "hidden" not in output  # nosec B101
        assert "shown" in output  # nosec B101


# ── ConsoleLogger: JSON output ────────────────────────────────────────


class TestConsoleLoggerJsonOutput:
    @pytest.fixture(autouse=True)
    def _unique_logger(self):
        self._counter = getattr(type(self), "_counter", 0) + 1
        type(self)._counter = self._counter
        self.logger_name = f"test_console_json_{self._counter}"

    def _make(self, level=LogLevel.DEBUG):
        adapter = ConsoleLogger(
            logger_name=self.logger_name, level=level, json_output=True
        )
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(_JsonFormatter())
        logging.getLogger(self.logger_name).addHandler(handler)
        return adapter, buf

    def _parse_first_json(self, buf):
        for line in buf.getvalue().strip().splitlines():
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    def test_valid_json_structure(self):
        adapter, buf = self._make()
        adapter.info("hello-json")
        parsed = self._parse_first_json(buf)
        assert parsed is not None  # nosec B101
        assert parsed["message"] == "hello-json"  # nosec B101
        assert parsed["level"] == "INFO"  # nosec B101
        assert "timestamp" in parsed  # nosec B101
        assert "logger" in parsed  # nosec B101

    def test_extra_fields_in_json(self):
        adapter, buf = self._make()
        adapter.info("with-extras", doc_id="SR-210", lang="de")
        parsed = self._parse_first_json(buf)
        assert parsed["doc_id"] == "SR-210"  # nosec B101
        assert parsed["lang"] == "de"  # nosec B101

    def test_logger_name_in_json(self):
        adapter, buf = self._make()
        adapter.info("test")
        parsed = self._parse_first_json(buf)
        assert parsed["logger"] == self.logger_name  # nosec B101
