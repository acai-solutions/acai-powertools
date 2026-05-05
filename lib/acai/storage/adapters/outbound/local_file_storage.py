import json
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Generator, List, Optional, Type, TypeVar, Union

from acai.logging.ports import Loggable
from acai.storage.domain import FileOperationError, StorageConfig, ValidationError
from acai.storage.ports import StoragePort

T = TypeVar("T")


class LocalFileStorage(StoragePort):
    """Outbound adapter — persists data on the local filesystem.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``StoragePort``.  Provides atomic writes,
    optional backups, extension validation, and JSON (de)serialisation.
    """

    VERSION: str = "1.0.8"  # inject_version

    def __init__(
        self,
        logger: Loggable,
        config: StorageConfig | None = None,
    ) -> None:
        self._logger = logger
        self._config = config or StorageConfig()
        self._setup_temp_dir()

    # ── StoragePort implementation ────────────────────────────────────

    def read(self, path: Union[str, Path], *, encoding: str = "utf-8") -> str:
        try:
            if not self.exists(path):
                self._logger.info(
                    "File does not exist, returning empty string", path=str(path)
                )
                return ""

            file_path = self._validate(path, check_exists=True)
            enc = encoding or self._config.encoding
            self._logger.debug("Reading file", path=str(file_path))

            with open(file_path, "r", encoding=enc) as fh:
                content = fh.read()

            self._logger.info("File read successfully", path=str(file_path))
            return content

        except (FileOperationError, ValidationError):
            raise
        except Exception as exc:
            msg = f"Failed to read {path}: {exc}"
            self._logger.error(msg)
            raise FileOperationError(msg) from exc

    def read_json(
        self,
        path: Union[str, Path],
        data_type: Optional[Type[T]] = None,
    ) -> Union[Any, T, List[T]]:
        try:
            if not self.exists(path):
                self._logger.info(
                    "File does not exist, returning empty dict", path=str(path)
                )
                return {}

            raw = self.read(path)
            parsed = json.loads(raw)

            if data_type is None:
                return parsed
            if isinstance(parsed, list):
                return [data_type(**item) for item in parsed]
            if isinstance(parsed, dict):
                return data_type(**parsed)
            raise ValidationError(
                "JSON content must be a dict or list for dataclass deserialisation"
            )

        except (FileOperationError, ValidationError):
            raise
        except json.JSONDecodeError as exc:
            msg = f"JSON decode error in {path}: {exc}"
            self._logger.error(msg)
            raise FileOperationError(msg) from exc
        except TypeError as exc:
            msg = f"Type error during deserialisation of {path}: {exc}"
            self._logger.error(msg)
            raise ValidationError(msg) from exc
        except Exception as exc:
            msg = f"Failed to read JSON from {path}: {exc}"
            self._logger.error(msg)
            raise FileOperationError(msg) from exc

    def save(
        self,
        path: Union[str, Path],
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> None:
        try:
            if not isinstance(content, str):
                raise ValidationError("content must be a string")

            file_path = self._validate(path, check_exists=False)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            enc = encoding or self._config.encoding

            self._logger.debug("Saving file", path=str(file_path))

            with self._atomic_write(file_path, "w", enc) as fh:
                fh.write(content)

            self._logger.info("File saved successfully", path=str(file_path))

        except (FileOperationError, ValidationError):
            raise
        except Exception as exc:
            msg = f"Failed to save {path}: {exc}"
            self._logger.error(msg)
            raise FileOperationError(msg) from exc

    def save_json(
        self,
        path: Union[str, Path],
        data: Any,
        *,
        indent: int = 2,
    ) -> None:
        def _default(obj: Any) -> Any:
            if is_dataclass(obj) and not isinstance(obj, type):
                return asdict(obj)
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            raise TypeError(
                f"Object of type {type(obj).__name__} is not JSON serialisable"
            )

        try:
            json_text = json.dumps(
                data, ensure_ascii=False, indent=indent, default=_default
            )
            file_path = Path(path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(json_text)

            self._logger.info("JSON saved successfully", path=str(file_path))

        except TypeError as exc:
            raise FileOperationError(f"Serialisation error: {exc}") from exc
        except Exception as exc:
            raise FileOperationError(f"Failed to save JSON to {path}: {exc}") from exc

    def exists(self, path: Union[str, Path]) -> bool:
        try:
            return Path(path).resolve().is_file()
        except Exception:
            return False

    def list_dir(self, path: Union[str, Path], *, pattern: str = "*") -> List[str]:
        try:
            dir_path = Path(path).resolve()
            if not dir_path.is_dir():
                self._logger.debug("Directory does not exist", path=str(dir_path))
                return []
            return [f.name for f in dir_path.glob(pattern) if f.is_file()]
        except Exception as exc:
            self._logger.error(f"Error listing directory {path}: {exc}")
            return []

    # ── context manager for cleanup ───────────────────────────────────

    def cleanup(self) -> None:
        try:
            if self._config.temp_dir and self._config.temp_dir.exists():
                for pattern in ("*.tmp", "*.bak"):
                    for f in self._config.temp_dir.glob(pattern):
                        f.unlink()
        except Exception as exc:
            self._logger.error("Cleanup error", error=str(exc))

    def __enter__(self) -> "LocalFileStorage":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()

    # ── private helpers ───────────────────────────────────────────────

    def _setup_temp_dir(self) -> None:
        if self._config.temp_dir is None:
            self._config.temp_dir = Path(tempfile.gettempdir()) / "acai_storage"
        self._config.temp_dir.mkdir(parents=True, exist_ok=True)

    def _validate(self, path: Union[str, Path], *, check_exists: bool = False) -> Path:
        try:
            resolved = Path(path).resolve()

            if check_exists and not resolved.is_file():
                raise ValidationError(f"File does not exist: {resolved}")

            if self._config.allowed_extensions is not None:
                ext = resolved.suffix.lstrip(".")
                if ext not in self._config.allowed_extensions:
                    raise ValidationError(
                        f"Extension '.{ext}' not allowed. Allowed: {self._config.allowed_extensions}"
                    )

            return resolved
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(f"Invalid path: {path} — {exc}") from exc

    def _create_backup_if_enabled(self, file_path: Path) -> Path | None:
        if self._config.backup_enabled and file_path.exists():
            backup_path = self._config.temp_dir / f"{file_path.name}.bak"
            shutil.copy2(file_path, backup_path)
            return backup_path
        return None

    def _validate_file_size(self, temp_path: Path) -> None:
        if temp_path.stat().st_size > self._config.max_file_size:
            raise FileOperationError(
                f"File size exceeds limit of {self._config.max_file_size} bytes"
            )

    def _move_file_with_fallback(self, temp_path: Path, file_path: Path) -> None:
        try:
            temp_path.replace(file_path)
        except OSError as exc:
            if exc.errno == 18:
                shutil.move(str(temp_path), str(file_path))
            else:
                raise

    def _restore_backup(self, backup_path: Path | None, file_path: Path) -> None:
        if backup_path and backup_path.exists():
            shutil.move(str(backup_path), str(file_path))

    @contextmanager
    def _atomic_write(
        self, file_path: Path, mode: str, encoding: str
    ) -> Generator[Any, None, None]:
        if self._config.temp_dir is None:
            raise FileOperationError("Temporary directory not initialized")
        temp_path = self._config.temp_dir / f"{file_path.name}.tmp"
        backup_path = self._create_backup_if_enabled(file_path)

        try:
            with open(temp_path, mode, encoding=encoding) as fh:
                yield fh

            self._validate_file_size(temp_path)
            self._move_file_with_fallback(temp_path, file_path)

            if backup_path and backup_path.exists():
                backup_path.unlink()

        except Exception:
            self._restore_backup(backup_path, file_path)
            raise
        finally:
            if temp_path.exists():
                temp_path.unlink()
