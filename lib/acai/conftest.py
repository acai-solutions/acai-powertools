"""Shared pytest fixtures for all acai test suites."""

from pathlib import Path

import pytest
from acai.logging import LoggerConfig, LogLevel, create_logger
from acai.logging.ports import LoggerPort
from acai.storage import create_storage
from acai.storage.ports import StoragePort


@pytest.fixture()
def work_dir(tmp_path: Path) -> Path:
    """Unique working directory for a single test, auto-cleaned by pytest."""
    return tmp_path / "acai_tests"


@pytest.fixture()
def logger() -> LoggerPort:
    """Quiet console logger (WARNING+) for tests that need a LoggerPort."""
    return create_logger(LoggerConfig(service_name="test", log_level=LogLevel.WARNING))


@pytest.fixture()
def storage(logger: LoggerPort) -> StoragePort:
    """LocalFileStorage wired through the factory."""
    return create_storage(logger)
