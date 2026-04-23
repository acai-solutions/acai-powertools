class StorageError(Exception):
    """Base exception for all storage operations."""


class FileOperationError(StorageError):
    """A low-level I/O operation failed."""


class ValidationError(StorageError):
    """Input validation (path, extension, size, …) failed."""
