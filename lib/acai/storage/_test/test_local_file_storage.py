"""Tests for ``acai.storage`` — LocalFileStorage adapter."""

from dataclasses import dataclass

import pytest
from acai.storage import (
    FileOperationError,
    StorageConfig,
    ValidationError,
    create_storage,
)
from acai.storage.adapters.outbound.local_file_storage import LocalFileStorage

# ── helpers ───────────────────────────────────────────────────────────


@dataclass
class SampleRecord:
    id: int
    name: str


# ── text read / write ────────────────────────────────────────────────


class TestTextReadWrite:
    def test_save_and_read(self, storage, work_dir):
        path = work_dir / "hello.txt"
        storage.save(path, "hello world")
        assert storage.read(path) == "hello world"  # nosec B101

    def test_overwrite(self, storage, work_dir):
        path = work_dir / "overwrite.txt"
        storage.save(path, "first")
        storage.save(path, "second")
        assert storage.read(path) == "second"  # nosec B101

    def test_read_missing_returns_empty(self, storage, work_dir):
        assert storage.read(work_dir / "missing.txt") == ""  # nosec B101

    def test_exists_true(self, storage, work_dir):
        path = work_dir / "exists.txt"
        storage.save(path, "data")
        assert storage.exists(path) is True  # nosec B101

    def test_exists_false(self, storage, work_dir):
        assert storage.exists(work_dir / "no.txt") is False  # nosec B101

    def test_nested_directories_created(self, storage, work_dir):
        path = work_dir / "a" / "b" / "c" / "deep.txt"
        storage.save(path, "deep")
        assert storage.read(path) == "deep"  # nosec B101

    def test_save_rejects_non_string(self, storage, work_dir):
        with pytest.raises(ValidationError):
            storage.save(work_dir / "bad.txt", 123)  # type: ignore[arg-type]


# ── JSON read / write ────────────────────────────────────────────────


class TestJsonReadWrite:
    def test_dict_round_trip(self, storage, work_dir):
        path = work_dir / "data.json"
        data = {"key": "value", "count": 42}
        storage.save_json(path, data)
        loaded = storage.read_json(path)
        assert loaded == data  # nosec B101

    def test_list_of_dicts_round_trip(self, storage, work_dir):
        path = work_dir / "records.json"
        records = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        storage.save_json(path, records)
        loaded = storage.read_json(path)
        assert loaded == records  # nosec B101

    def test_dataclass_serialisation(self, storage, work_dir):
        path = work_dir / "dc.json"
        records = [SampleRecord(1, "alpha"), SampleRecord(2, "beta")]
        storage.save_json(path, records)
        loaded = storage.read_json(path, data_type=SampleRecord)
        assert loaded == records  # nosec B101

    def test_single_dataclass(self, storage, work_dir):
        path = work_dir / "single.json"
        record = SampleRecord(99, "gamma")
        storage.save_json(path, record)
        loaded = storage.read_json(path, data_type=SampleRecord)
        assert loaded == record  # nosec B101

    def test_read_json_missing_returns_empty_dict(self, storage, work_dir):
        assert storage.read_json(work_dir / "nope.json") == {}  # nosec B101

    def test_malformed_json_raises(self, storage, work_dir):
        path = work_dir / "bad.json"
        storage.save(path, "not-json{{{")
        with pytest.raises(FileOperationError):
            storage.read_json(path)


# ── extension validation ─────────────────────────────────────────────


class TestExtensionValidation:
    def test_allowed_extension_passes(self, logger, work_dir):
        cfg = StorageConfig(allowed_extensions={"txt", "json"})
        s = LocalFileStorage(logger=logger, config=cfg)
        path = work_dir / "ok.txt"
        s.save(path, "fine")
        assert s.read(path) == "fine"  # nosec B101

    def test_disallowed_extension_raises(self, logger, work_dir):
        cfg = StorageConfig(allowed_extensions={"txt"})
        s = LocalFileStorage(logger=logger, config=cfg)
        with pytest.raises(ValidationError, match="not allowed"):
            s.save(work_dir / "bad.xml", "<root/>")


# ── size validation ──────────────────────────────────────────────────


class TestSizeValidation:
    def test_oversized_file_raises(self, logger, work_dir):
        cfg = StorageConfig(max_file_size=10)
        s = LocalFileStorage(logger=logger, config=cfg)
        with pytest.raises(FileOperationError):
            s.save(work_dir / "big.txt", "x" * 100)


# ── config validation ────────────────────────────────────────────────


class TestStorageConfig:
    def test_negative_max_file_size_raises(self):
        with pytest.raises(ValidationError):
            StorageConfig(max_file_size=-1)

    def test_defaults(self):
        cfg = StorageConfig()
        assert cfg.encoding == "utf-8"  # nosec B101
        assert cfg.backup_enabled is True  # nosec B101
        assert cfg.allowed_extensions is None  # nosec B101


# ── factory ───────────────────────────────────────────────────────────


class TestFactory:
    def test_create_storage_returns_local(self, logger):
        s = create_storage(logger)
        assert isinstance(s, LocalFileStorage)  # nosec B101

    def test_create_storage_with_config(self, logger):
        cfg = StorageConfig(backup_enabled=False)
        s = create_storage(logger, cfg)
        assert isinstance(s, LocalFileStorage)  # nosec B101


# ── context manager ──────────────────────────────────────────────────


class TestContextManager:
    def test_context_manager_cleanup(self, logger, work_dir):
        with LocalFileStorage(logger=logger) as s:
            s.save(work_dir / "ctx.txt", "hello")
            assert s.read(work_dir / "ctx.txt") == "hello"  # nosec B101
