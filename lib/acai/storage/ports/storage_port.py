from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional, Type, TypeVar, Union

T = TypeVar("T")


class StorageReader(ABC):
    """Read-only storage port."""

    @abstractmethod
    def read(self, path: Union[str, Path], *, encoding: str = "utf-8") -> str:
        """Read raw text content. Returns ``""`` if the path does not exist."""
        ...

    @abstractmethod
    def read_json(
        self,
        path: Union[str, Path],
        data_type: Optional[Type[T]] = None,
    ) -> Union[Any, T, List[T]]:
        """Read and deserialise JSON. Returns ``{}`` if the path does not exist."""
        ...

    @abstractmethod
    def exists(self, path: Union[str, Path]) -> bool:
        """Return ``True`` if *path* exists in the store."""
        ...

    @abstractmethod
    def list_dir(self, path: Union[str, Path], *, pattern: str = "*") -> List[str]:
        """List filenames in *path* matching *pattern*. Returns ``[]`` if directory does not exist."""
        ...


class StorageWriter(ABC):
    """Write-only storage port."""

    @abstractmethod
    def save(
        self,
        path: Union[str, Path],
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> None:
        """Persist raw text content."""
        ...

    @abstractmethod
    def save_json(
        self,
        path: Union[str, Path],
        data: Any,
        *,
        indent: int = 2,
    ) -> None:
        """Serialise *data* to JSON and persist."""
        ...


class StoragePort(StorageReader, StorageWriter, ABC):
    """Combined read/write storage port.

    Hexagonal role
    ──────────────
    Driven (secondary) port.  Domain code depends only on this interface;
    concrete adapters (local filesystem, S3, …) implement it.
    """

    VERSION: str = "1.1.4"  # inject_version
    ...
