from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass
class VectorStoreConfig:
    """Configuration value object shared across vector-store adapters."""

    table: str = "embeddings"
    schema: str = "public"
    dimension: int = 1024
    distance_metric: str = "cosine"

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise ConfigurationError("dimension must be positive")
        allowed_metrics = {"cosine", "l2", "inner_product"}
        if self.distance_metric not in allowed_metrics:
            raise ConfigurationError(
                f"distance_metric must be one of {allowed_metrics}, "
                f"got '{self.distance_metric}'"
            )
        if not self.table:
            raise ConfigurationError("table must be a non-empty string")
