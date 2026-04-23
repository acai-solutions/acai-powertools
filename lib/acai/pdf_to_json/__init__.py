"""
acai.pdf_to_json — Hexagonal PDF-to-JSON module
================================================

Public surface
--------------
- ``PdfParserPort``            — port contract (depend on this)
- ``PdfParserConfig``          — shared configuration value object
- ``ParsedPdfDocument``, ``PdfPage``, ``PdfPageElement``, etc. — domain models
- ``PdfParserError``, ``PdfParseError``, ``ConfigurationError`` — exceptions
- ``create_pdf_parser()``      — factory that wires adapters

Adapters (import directly when needed)
--------------------------------------
- ``acai.pdf_to_json.adapters.PyMuPdfParser``
- ``acai.pdf_to_json.adapters.DoclingParser``

Input modes
-----------
- **File path** — ``parser.parse_file("path/to/doc.pdf")``
- **Byte stream** — ``parser.parse_bytes(raw_bytes)``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from acai.pdf_to_json.domain import (
    ConfigurationError,
    ContentType,
    ParsedPdfDocument,
    PdfImage,
    PdfMetadata,
    PdfPage,
    PdfPageElement,
    PdfParseError,
    PdfParserConfig,
    PdfParserError,
    PdfTable,
    PdfTableCell,
    PdfTextBlock,
)
from acai.pdf_to_json.ports import PdfParserPort

if TYPE_CHECKING:
    from acai.logging.ports import Loggable


def create_pdf_parser(
    logger: Loggable,
    config: PdfParserConfig | None = None,
    *,
    use_docling: bool = False,
) -> PdfParserPort:
    """Factory that builds a ready-to-use ``PdfParserPort``.

    Parameters
    ----------
    logger:
        A ``Loggable`` instance used by the adapter for operational logging.
    config:
        Optional configuration.  Defaults extract text, images, and tables.
    use_docling:
        When ``True``, uses the ``DoclingParser`` adapter (requires ``docling``).
        Otherwise ``PyMuPdfParser`` is used (requires ``pymupdf``).
    """
    if config is None:
        config = PdfParserConfig()

    if use_docling:
        from acai.pdf_to_json.adapters.outbound.docling_parser import DoclingParser

        return DoclingParser(logger=logger, config=config)

    from acai.pdf_to_json.adapters.outbound.pymupdf_parser import PyMuPdfParser

    return PyMuPdfParser(logger=logger, config=config)


__all__ = [
    "PdfParserPort",
    "PdfParserConfig",
    "ContentType",
    "ParsedPdfDocument",
    "PdfImage",
    "PdfMetadata",
    "PdfPage",
    "PdfPageElement",
    "PdfTable",
    "PdfTableCell",
    "PdfTextBlock",
    "PdfParserError",
    "PdfParseError",
    "ConfigurationError",
    "create_pdf_parser",
]
