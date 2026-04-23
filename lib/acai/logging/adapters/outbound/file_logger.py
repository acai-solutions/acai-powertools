import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from acai.logging.ports import LoggerPort, LogLevel
from acai.storage.ports import StorageWriter


class FileLogger(LoggerPort):
    """Outbound adapter — logs to a file via a ``StorageWriter``.

    Hexagonal role
    ──────────────
    Driven adapter implementing ``LoggerPort``.  Instead of managing file
    handles directly, it delegates persistence to a ``StorageWriter`` adapter
    (e.g. ``LocalFileStorage``, ``S3Storage``), keeping infrastructure
    concerns decoupled.

    Each ``log()`` call appends one line to the target path.  Existing
    content is preserved across calls within the same adapter instance.
    """

    VERSION: str = "1.1.4"  # inject_version

    def __init__(
        self,
        storage: StorageWriter,
        log_path: Union[str, Path],
        level: Union[LogLevel, int, str] = LogLevel.INFO,
        json_output: bool = False,
        logger_name: str = "file",
    ) -> None:
        self._storage = storage
        self._log_path = Path(log_path)
        self._json_output = json_output
        self._logger_name = logger_name
        self._buffer: list[str] = []
        self._level: int = self._to_native(level)

    # ── LoggerPort implementation ─────────────────────────────────────

    def set_level(self, level: Union[LogLevel, int, str]) -> None:
        self._level = self._to_native(level)

    def log(
        self, level: Union[LogLevel, int, str], message: str, **kwargs: Any
    ) -> None:
        native = self._to_native(level)
        if native < self._level:
            return

        exc_info = kwargs.pop("exc_info", None)
        line = (
            self._format_json(native, message, kwargs)
            if self._json_output
            else self._format_text(native, message, kwargs)
        )

        if exc_info:
            import traceback

            if isinstance(exc_info, BaseException):
                tb = "".join(
                    traceback.format_exception(
                        type(exc_info), exc_info, exc_info.__traceback__
                    )
                )
            elif isinstance(exc_info, tuple):
                tb = "".join(traceback.format_exception(*exc_info))
            else:
                import sys

                tb = "".join(traceback.format_exception(*sys.exc_info()))
            line += "\n" + tb.rstrip()

        self._buffer.append(line)

    def flush(self) -> None:
        """Write buffered log lines to storage and clear the buffer."""
        if not self._buffer:
            return
        content = "\n".join(self._buffer) + "\n"
        self._append(content)
        self._buffer.clear()

    # ── formatting ────────────────────────────────────────────────────

    def _format_text(
        self, native_level: int, message: str, extra: dict[str, Any]
    ) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        level_name = self._level_name(native_level)
        line = f"{ts} - {level_name} - {message}"
        if extra:
            line += " | " + " ".join(f"{k}={v}" for k, v in extra.items())
        return line

    def _format_json(
        self, native_level: int, message: str, extra: dict[str, Any]
    ) -> str:
        data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": self._level_name(native_level),
            "logger": self._logger_name,
            "message": message,
        }
        if extra:
            data.update(extra)
        return json.dumps(data, default=str)

    # ── private helpers ───────────────────────────────────────────────

    def _append(self, content: str) -> None:
        """Append *content* to the log file via the storage adapter."""
        from acai.storage.ports import StorageReader

        existing = ""
        if isinstance(self._storage, StorageReader):
            existing = self._storage.read(self._log_path)

        self._storage.save(self._log_path, existing + content)

    @staticmethod
    def _level_name(native: int) -> str:
        return LogLevel.level_name(native)

    @staticmethod
    def _to_native(level: Union[LogLevel, int, str]) -> int:
        return LogLevel.to_native(level)
