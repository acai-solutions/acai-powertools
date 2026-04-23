"""Tests for ``acai.logging`` — FileLogger adapter."""

import json

import pytest
from acai.logging import LoggerConfig, LogLevel, create_local_logger, create_logger
from acai.logging.adapters.outbound.file_logger import FileLogger
from acai.logging.domain.logger import Logger
from acai.storage import create_storage

# ── fixtures (storage needs a bootstrap logger) ──────────────────────


@pytest.fixture()
def storage():
    bootstrap = create_logger(
        LoggerConfig(service_name="bootstrap", log_level=LogLevel.WARNING)
    )
    return create_storage(bootstrap)


# ── FileLogger: text format ──────────────────────────────────────────


class TestFileLoggerText:
    def test_log_and_flush(self, storage, work_dir):
        log_path = work_dir / "app.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.DEBUG)
        fl.log(LogLevel.INFO, "hello")
        fl.flush()
        content = storage.read(log_path)
        assert "INFO" in content  # nosec B101
        assert "hello" in content  # nosec B101

    def test_multiple_lines(self, storage, work_dir):
        log_path = work_dir / "multi.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.DEBUG)
        fl.log(LogLevel.INFO, "line1")
        fl.log(LogLevel.WARNING, "line2")
        fl.flush()
        lines = storage.read(log_path).strip().splitlines()
        assert len(lines) == 2  # nosec B101
        assert "line1" in lines[0]  # nosec B101
        assert "line2" in lines[1]  # nosec B101

    def test_extra_fields_appended(self, storage, work_dir):
        log_path = work_dir / "extra.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.DEBUG)
        fl.log(LogLevel.INFO, "with extras", item_id=42, source="api")
        fl.flush()
        content = storage.read(log_path)
        assert "item_id=42" in content  # nosec B101
        assert "source=api" in content  # nosec B101

    def test_append_across_flushes(self, storage, work_dir):
        log_path = work_dir / "append.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.DEBUG)
        fl.log(LogLevel.INFO, "first")
        fl.flush()
        fl.log(LogLevel.INFO, "second")
        fl.flush()
        lines = storage.read(log_path).strip().splitlines()
        assert len(lines) == 2  # nosec B101


# ── FileLogger: JSON format ──────────────────────────────────────────


class TestFileLoggerJson:
    def test_json_output(self, storage, work_dir):
        log_path = work_dir / "app.jsonl"
        fl = FileLogger(
            storage=storage, log_path=log_path, level=LogLevel.DEBUG, json_output=True
        )
        fl.log(LogLevel.INFO, "json line", step="embed")
        fl.flush()
        content = storage.read(log_path).strip()
        parsed = json.loads(content)
        assert parsed["level"] == "INFO"  # nosec B101
        assert parsed["message"] == "json line"  # nosec B101
        assert parsed["step"] == "embed"  # nosec B101
        assert "timestamp" in parsed  # nosec B101

    def test_logger_name_in_json(self, storage, work_dir):
        log_path = work_dir / "named.jsonl"
        fl = FileLogger(
            storage=storage,
            log_path=log_path,
            json_output=True,
            logger_name="my-svc",
            level=LogLevel.DEBUG,
        )
        fl.log(LogLevel.DEBUG, "test")
        fl.flush()
        parsed = json.loads(storage.read(log_path).strip())
        assert parsed["logger"] == "my-svc"  # nosec B101


# ── FileLogger: level filtering ──────────────────────────────────────


class TestFileLoggerLevelFiltering:
    def test_below_level_suppressed(self, storage, work_dir):
        log_path = work_dir / "filtered.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.WARNING)
        fl.log(LogLevel.DEBUG, "should not appear")
        fl.log(LogLevel.INFO, "should not appear either")
        fl.log(LogLevel.WARNING, "should appear")
        fl.flush()
        content = storage.read(log_path)
        assert "should appear" in content  # nosec B101
        assert "should not appear" not in content  # nosec B101

    def test_set_level_changes_threshold(self, storage, work_dir):
        log_path = work_dir / "dynamic.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.ERROR)
        fl.log(LogLevel.WARNING, "blocked")
        fl.set_level(LogLevel.DEBUG)
        fl.log(LogLevel.WARNING, "allowed")
        fl.flush()
        content = storage.read(log_path)
        assert "blocked" not in content  # nosec B101
        assert "allowed" in content  # nosec B101

    def test_flush_noop_when_empty(self, storage, work_dir):
        log_path = work_dir / "empty.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=LogLevel.DEBUG)
        fl.flush()
        assert not storage.exists(log_path)  # nosec B101


# ── FileLogger: level conversion ─────────────────────────────────────


class TestFileLoggerLevelConversion:
    def test_string_level(self, storage, work_dir):
        log_path = work_dir / "str.log"
        fl = FileLogger(storage=storage, log_path=log_path, level="warning")
        fl.log(LogLevel.INFO, "hidden")
        fl.log(LogLevel.WARNING, "visible")
        fl.flush()
        content = storage.read(log_path)
        assert "hidden" not in content  # nosec B101
        assert "visible" in content  # nosec B101

    def test_int_level(self, storage, work_dir):
        log_path = work_dir / "int.log"
        fl = FileLogger(storage=storage, log_path=log_path, level=30)
        fl.log(20, "hidden")
        fl.log(30, "visible")
        fl.flush()
        content = storage.read(log_path)
        assert "hidden" not in content  # nosec B101
        assert "visible" in content  # nosec B101


# ── create_local_logger factory ───────────────────────────────────────


class TestCreateLoggerWithStorage:
    def test_factory_creates_file_logger(self, storage, work_dir):
        log_path = work_dir / "factory.log"
        logger = create_local_logger(
            LoggerConfig(service_name="factory-test", log_level=LogLevel.DEBUG),
            storage=storage,
            log_path=str(log_path),
        )
        assert isinstance(logger, Logger)  # nosec B101

    def test_factory_requires_log_path(self, storage):
        with pytest.raises(ValueError, match="log_path is required"):
            create_local_logger(LoggerConfig(), storage=storage)

    def test_factory_end_to_end(self, storage, work_dir):
        log_path = work_dir / "e2e.log"
        logger = create_local_logger(
            LoggerConfig(service_name="e2e", log_level=LogLevel.DEBUG),
            storage=storage,
            log_path=str(log_path),
        )
        logger.info("end to end test")
        logger.flush()
        content = storage.read(log_path)
        assert "end to end test" in content  # nosec B101
