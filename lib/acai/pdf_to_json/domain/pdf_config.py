from dataclasses import dataclass

from .exceptions import ConfigurationError


@dataclass
class PdfParserConfig:
    """Configuration value object for PDF parser adapters."""

    extract_images: bool = True
    extract_tables: bool = True
    image_format: str = "png"
    image_dpi: int = 150
    image_render_scale: float = 2.0
    image_instance_min_width: float = 8.0
    image_instance_min_height: float = 8.0
    image_instance_min_area: float = 256.0
    table_strategy: str = "lines_strict"

    def __post_init__(self) -> None:
        if self.image_format not in ("png", "jpeg", "jpg"):
            raise ConfigurationError(
                f"Unsupported image_format '{self.image_format}', "
                "must be one of: png, jpeg, jpg"
            )
        if self.image_dpi <= 0:
            raise ConfigurationError("image_dpi must be positive")
        if self.image_render_scale <= 0:
            raise ConfigurationError("image_render_scale must be positive")
        if self.image_instance_min_width < 0:
            raise ConfigurationError("image_instance_min_width must be non-negative")
        if self.image_instance_min_height < 0:
            raise ConfigurationError("image_instance_min_height must be non-negative")
        if self.image_instance_min_area < 0:
            raise ConfigurationError("image_instance_min_area must be non-negative")
