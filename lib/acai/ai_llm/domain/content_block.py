"""Content block value objects for multi-modal LLM input."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContentType(Enum):
    """Supported content block types."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"


@dataclass(frozen=True)
class ContentBlock:
    """A single content block inside a user message.

    Parameters
    ----------
    content_type:
        Kind of content (text, image, document).
    data:
        Plain text for ``TEXT`` blocks, **base64-encoded** bytes for
        ``IMAGE`` and ``DOCUMENT`` blocks.
    media_type:
        MIME type — required for ``IMAGE`` (e.g. ``"image/png"``) and
        ``DOCUMENT`` (e.g. ``"application/pdf"``).  Ignored for ``TEXT``.
    filename:
        Optional filename hint for ``DOCUMENT`` blocks.
    """

    content_type: ContentType
    data: str
    media_type: str | None = None
    filename: str | None = None

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("ContentBlock.data must not be empty")
        if self.content_type in (ContentType.IMAGE, ContentType.DOCUMENT):
            if not self.media_type:
                raise ValueError(
                    f"media_type is required for {self.content_type.value} blocks"
                )

    # -- convenience constructors ------------------------------------------

    @classmethod
    def text(cls, text: str) -> ContentBlock:
        return cls(content_type=ContentType.TEXT, data=text)

    @classmethod
    def image(cls, base64_data: str, media_type: str) -> ContentBlock:
        return cls(
            content_type=ContentType.IMAGE,
            data=base64_data,
            media_type=media_type,
        )

    @classmethod
    def document(
        cls, base64_data: str, media_type: str, filename: str | None = None
    ) -> ContentBlock:
        return cls(
            content_type=ContentType.DOCUMENT,
            data=base64_data,
            media_type=media_type,
            filename=filename,
        )
