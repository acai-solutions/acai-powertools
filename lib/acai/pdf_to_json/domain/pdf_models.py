from __future__ import annotations

import base64
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ContentType(Enum):
    """Discriminator for elements in a parsed PDF page."""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


@dataclass
class PdfTextBlock:
    """A contiguous block of text extracted from a PDF page."""

    content: str = ""
    font_name: Optional[str] = None
    font_size: Optional[float] = None


@dataclass
class PdfImage:
    """An image extracted from a PDF page.

    ``data`` holds the raw bytes; ``data_base64`` is a convenience
    property for JSON serialisation.
    """

    data: bytes = field(default=b"", repr=False)
    width: int = 0
    height: int = 0
    format: str = "png"

    @property
    def data_base64(self) -> str:
        return base64.b64encode(self.data).decode("ascii") if self.data else ""


@dataclass
class PdfTableCell:
    """A single cell inside a PDF table."""

    text: str = ""
    row: int = 0
    col: int = 0


@dataclass
class PdfTable:
    """A table extracted from a PDF page, represented as a list of rows."""

    rows: List[List[str]] = field(default_factory=list)


@dataclass
class PdfPageElement:
    """One content block inside a page — text, image, or table."""

    type: ContentType
    text_block: Optional[PdfTextBlock] = None
    image: Optional[PdfImage] = None
    table: Optional[PdfTable] = None


@dataclass
class PdfPage:
    """A single page with its ordered content elements."""

    page_number: int = 0
    width: float = 0.0
    height: float = 0.0
    elements: List[PdfPageElement] = field(default_factory=list)


@dataclass
class PdfMetadata:
    """Metadata extracted from the PDF document info dict."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    page_count: int = 0


@dataclass
class ParsedPdfDocument:
    """Complete result of parsing a PDF document."""

    metadata: PdfMetadata
    pages: List[PdfPage]

    # ------------------------------------------------------------------
    # Convenience serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-friendly nested dict.

        Images are encoded as base64 strings so the output can round-trip
        through ``json.dumps`` / ``json.loads``.
        """

        def _serialise_element(elem: PdfPageElement) -> dict:
            d: dict = {"type": elem.type.value}
            if elem.text_block is not None:
                d["text_block"] = {
                    "content": elem.text_block.content,
                    "font_name": elem.text_block.font_name,
                    "font_size": elem.text_block.font_size,
                }
            if elem.image is not None:
                d["image"] = {
                    "width": elem.image.width,
                    "height": elem.image.height,
                    "format": elem.image.format,
                    "data_base64": elem.image.data_base64,
                }
            if elem.table is not None:
                d["table"] = {"rows": elem.table.rows}
            return d

        return {
            "metadata": {
                "title": self.metadata.title,
                "author": self.metadata.author,
                "subject": self.metadata.subject,
                "creator": self.metadata.creator,
                "producer": self.metadata.producer,
                "page_count": self.metadata.page_count,
            },
            "pages": [
                {
                    "page_number": p.page_number,
                    "width": p.width,
                    "height": p.height,
                    "elements": [_serialise_element(e) for e in p.elements],
                }
                for p in self.pages
            ],
        }
