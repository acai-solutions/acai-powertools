from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union

from acai.pdf_to_json.domain.pdf_models import ParsedPdfDocument


class PdfParserPort(ABC):
    """Outbound port defining the contract every PDF parser adapter must fulfil.

    Two entry points:
    - ``parse_file``  — read from a file path (delegates to the storage hex)
    - ``parse_bytes`` — parse an in-memory byte stream directly
    """

    VERSION: str = "1.0.10"  # inject_version

    @abstractmethod
    def parse_file(self, pdf_path: Union[str, Path]) -> ParsedPdfDocument:
        """Parse a PDF located at *pdf_path* and return a structured document.

        Parameters
        ----------
        pdf_path:
            Filesystem path to the PDF file.

        Returns
        -------
        ParsedPdfDocument

        Raises
        ------
        PdfParseError
            If the file cannot be parsed.
        """
        ...

    @abstractmethod
    def parse_bytes(
        self, data: bytes, *, source_name: str = "<bytes>"
    ) -> ParsedPdfDocument:
        """Parse a PDF from raw bytes and return a structured document.

        Parameters
        ----------
        data:
            Raw PDF bytes (e.g. downloaded from an API or read by the caller).
        source_name:
            An optional label used in log messages and error reports.

        Returns
        -------
        ParsedPdfDocument

        Raises
        ------
        PdfParseError
            If the data cannot be parsed.
        """
        ...

    def __enter__(self) -> "PdfParserPort":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass
