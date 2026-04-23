from dataclasses import dataclass
from pathlib import Path

from .exceptions import ValidationError


@dataclass
class StorageConfig:
    """Configuration value object shared across storage adapters."""

    encoding: str = "utf-8"
    backup_enabled: bool = True
    max_file_size: int = 100 * 1024 * 1024  # 100 MB
    temp_dir: Path | None = None
    allowed_extensions: set[str] | None = None

    def __post_init__(self) -> None:
        if self.max_file_size <= 0:
            raise ValidationError("max_file_size must be positive")
        if self.temp_dir is not None and not isinstance(self.temp_dir, Path):
            self.temp_dir = Path(self.temp_dir)
        if self.allowed_extensions is not None and not isinstance(
            self.allowed_extensions, set
        ):
            self.allowed_extensions = set(self.allowed_extensions)
