class VectorStoreError(Exception):
    """Base exception for all vector-store operations."""


class ConnectionError(VectorStoreError):
    """Failed to connect to (or lost connection with) the vector database."""


class QueryError(VectorStoreError):
    """A read or write query failed."""


class ConfigurationError(VectorStoreError):
    """Vector-store configuration is invalid."""
